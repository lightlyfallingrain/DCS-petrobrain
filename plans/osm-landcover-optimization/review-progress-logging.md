# Review: progress-logging fix

Reviewed: `feature/osm-landcover-optimization`, commits `8957092..ed058f7` (8 commits, 18 files,
+1008/-108). Investigation note: `plans/osm-landcover-optimization/progress-logging.md`.
Verification method: read every diff hunk in the range directly (not the plan's prose alone),
independently re-ran the debugger's key measurements against real data on this machine
(`sha256_file` against the real 475 MB `syria-theatre.osm.pbf` on the `/mnt/f` drvfs mount;
`insert_features`/`insert_grid` against a synthetic benchmark using the real `store.schema`/
`store.writer` code), ran `ruff format --check`/`ruff check`/`mypy --strict`/`pytest` from
`world-model/`, reran `pytest` a second time and `test_progress.py` three times for flakiness, and
checked for `Heartbeat` thread leaks directly. No `syria-full*.sqlite` file was read or queried, no
`syria-full` build was run, and no user log/`run.sh` file was touched.

### Required Fixes

1. **`world-model/src/osm/pbf.py:365-369` — the final `collector.flush()` runs *outside* the
   `Heartbeat` context, so it is not covered by the heartbeat.**

   ```python
   with Heartbeat(_report, interval_s=_PROGRESS_LOG_INTERVAL_S):
       collector.apply_file(
           str(pbf_path), locations=True, idx="sparse_mem_array", filters=[key_filter]
       )
   collector.flush()   # <-- outside the `with` block
   ```

   `flush()` calls `on_nodes`/`on_ways`/`on_areas` on whatever partial batch is left below
   `batch_size`/`area_batch_size` (up to 50,000 nodes/ways or 5,000 areas) — in
   `build.pipeline`'s cache-miss branch, that means one more `insert_features` *and*
   `insert_cached_features` call, both real DB writes, with the heartbeat thread already stopped
   and joined. This directly contradicts the module docstring's own claim ("gives a heartbeat
   across the *whole* call, not just the parts that call back into Python") and the review
   question this task was built around ("does it cover the whole `apply_file`... plus `flush()`?").
   No test in `test_osm_pbf.py` covers this ordering either — it would have caught the gap.

   In practice this is low-risk today: I benchmarked the real `insert_features`/`insert_grid`
   functions directly (50,000 `StoredFeature` rows via `store.writer.insert_features` against a
   real `create_schema`'d SQLite file, including the `feature_bbox` R*Tree insert per row) and got
   0.77s — confirming the debugger's own number — so a final leftover batch, even doubled up for
   `insert_features` + `insert_cached_features`, is roughly 1.5s, nowhere near 30s. But the fix is
   a one-line move (put `collector.flush()` inside the `with Heartbeat(...)` block, or call
   `_report()` once more immediately after `flush()` returns) and removes any doubt rather than
   relying on today's batch sizes staying small forever.

2. **No regression test for the SRTM tile-loading fix in `world-model/src/build/pipeline.py`
   (~line 651-669, the `tile_load_progress` `ThrottledProgress` and the move of tile loading
   inside the `_stage(...)` block).** This is the exact bug class the whole investigation exists
   for — the plan's own words: "a real (if currently small) instance of the exact 'silent before
   the stage even announces itself' bug class." Every other migrated or newly-instrumented call
   site in this change got a dedicated test proving the wiring actually happened (not just that
   behavior is unaffected): `test_ingest_srtm.py`'s new `test_ingest_srtm_grid_logs_progress_via_
   the_shared_helper`, `test_roadnet_routes.py`'s equivalent, `test_ingest_junctions.py`'s updated
   assertions, `test_pipeline_osm_cache.py`'s new `test_cache_hit_read_logs_progress_via_the_
   shared_helper`. The SRTM tile-loading loop has no equivalent. Add one following the same
   pattern: build on the existing `test_build_region_srtm_tile_paths_becomes_the_primary_
   elevation_grid` fixture, monkeypatch `pipeline._PROGRESS_LOG_INTERVAL_S` to `0.0`, assert an
   `"ingest_srtm.load_tiles: "` line appears in `caplog`, and (ideally) assert the `"[6/8] SRTM
   elevation grid"` "starting" line's record index precedes the tile-load lines, to pin the actual
   reported bug (stage announces itself late) rather than only the new counter's existence.

### Optional Refinements

- `world-model/RUN.md` §3.3 row 3 documents the heartbeat log line as `osm.pbf: ~Ns/Ns (~x.x%,
  ...)`, implying an `s` suffix on the leading done/total pair. The actual line (verified by
  calling `format_progress` directly with realistic inputs) is `osm.pbf: ~34/55 (~61.8%,
  elements_seen=..., ..., 34s elapsed, ~21s remaining)` — no `s` suffix on the `~34/55` part, only
  on `elapsed`/`remaining`. One-line doc fix.
- Reusing `format_progress`'s generic `done`/`total` slot to carry *elapsed seconds* / *estimated
  total seconds* (rather than a real quantity like bytes or elements) for `osm.pbf`'s heartbeat
  works correctly — the percent and remaining-time math check out — but produces a slightly
  confusing `~34/55` that looks like an item count at a glance. Not a bug, just a readability nit;
  consider a code comment at the call site noting `done`/`total` here are seconds-as-progress-proxy,
  not a count.
- Five modules (`osm/pbf.py`, `build/ingest_srtm.py`, `build/ingest_junctions.py`,
  `roadnet/routes.py`, `build/pipeline.py`) each define their own local
  `_PROGRESS_LOG_INTERVAL_S = 30.0`, duplicating `progress.DEFAULT_INTERVAL_S`'s value instead of
  relying on it. This undercuts the plan's own framing ("a project-wide constant, not a per-module
  judgment call") — changing the interval today means touching 5 files, not 1. Low priority.
- `progress.Heartbeat.__exit__`'s `self._thread.join(timeout=self._interval_s + 5.0)` doesn't check
  whether the join actually succeeded. `daemon=True` means a stuck `report_fn` can't hang process
  exit, and no current `report_fn` implementation blocks indefinitely, so this is low risk — but a
  log warning on a timed-out join would surface a stuck heartbeat instead of silently leaking a
  thread.
- The plan's "audit: every potentially long operation" table doesn't list the legacy
  `osm_cache_path`/Overpass-JSON `elif` branch in `build/pipeline.py` (~line 541-565:
  `load_features(osm_cache_path)` + `ingest_osm(...)` + its own `insert_features` loop, entirely
  uninstrumented). I confirmed this is genuinely out of scope at `syria-full` scale — `RUN.md`
  explicitly documents `--osm-cache` as "small regions only, M3's live-Overpass path", and
  `--osm-pbf` always takes precedence when both are given — so there's no functional gap, just a
  table that could have explicitly called this branch out as locked out (the way stages 7/8 were),
  rather than silently omitting it.
- No test pins `format_progress`/`ThrottledProgress`'s `done=0` boundary (the specific
  no-division-by-zero case this review was asked to check). I confirmed the guard
  (`0 < done < total` before the `remaining_s` division) is correct by direct testing, and it's
  exercised indirectly by the throttle tests, but nothing asserts `done=0` explicitly. Low
  priority given the guard is trivially correct.

### Coverage Table

Verified directly (code read + targeted greps/benchmarks), not just taken from the plan:

| operation | can exceed ~30s at `syria-full` scale? | covered? | mechanism | notes |
|---|---|---|---|---|
| `osm.pbf.stream_features` — `apply_file` (both area-assembly passes + callback work) | Yes, measured | **Yes**, except `flush()` (Required Fix 1) | `Heartbeat` + `ThrottledProgress`, `estimated=True` | Heartbeat thread confirmed to tick regardless of GIL state; verified no thread leak |
| `roadnet.routes.iter_routes` (.routes 2.25GB mmap walk) | Yes | Yes | `ThrottledProgress`, 30s (was already-working 5s, migrated) | format matches RUN.md |
| `ingest_junctions.ingest_junctions_streaming` (chunk loop) | Yes | Yes | `ThrottledProgress`, 30s (already-working, migrated) | format matches RUN.md |
| `ingest_srtm.ingest_srtm_grid` (row loop) | Row-based before, now time-bounded | Yes | `ThrottledProgress` | tested (`test_ingest_srtm_grid_logs_progress_via_the_shared_helper`) |
| SRTM tile loading (`SrtmTile.from_file` loop in `pipeline.py`) | Currently ~4.0s, not yet excessive, but was fully silent and pre-stage-announce | Yes (code), **No test** (Required Fix 2) | `ThrottledProgress`, moved inside `_stage(...)` | |
| OSM cache-hit read (`iter_cached_features`/`insert_features`) | Could scale to millions of features | Yes | `ThrottledProgress`, exact `done`/`total` from `OsmIngestStats` | tested |
| `store.writer.insert_features` | Measured 0.77s/50,000 rows (**independently reproduced**, matches debugger's 0.78s) | n/a — caller instrumented instead | none needed | benchmark used real `create_schema`, including `feature_bbox` R*Tree insert |
| `store.writer.insert_grid` | Measured 0.80s/639,216 cells (**independently reproduced**, matches debugger's 0.79s) | n/a | none needed | |
| `osm_cache.hashing.sha256_file` | Measured 0.16s/160MB by debugger; **independently reproduced against the real 475,875,742-byte `syria-theatre.osm.pbf` on the actual `/mnt/f` drvfs mount**: 3.16s (~151 MB/s — slower than the debugger's ~1GB/s figure, likely a different/warmer cache state, but still >9x margin under 30s even at this file's real size) | n/a | none needed | this is the real theatre merge file, largest realistic input |
| `osm_cache.writer.insert_cached_features`/`finalize_cache` | Same per-batch shape as `insert_features`; `finalize_cache` is a handful of meta rows + `os.replace` | n/a, except the final-batch gap noted in Required Fix 1 | none | confirmed `insert_cached_features` is called from the same `_flush_nodes`/`_flush_ways`/`_flush_areas` closures the `Heartbeat`-wrapped `apply_file` drives, so mid-loop batches are covered; only the trailing `flush()` call is not |
| `build.ingest_probe`/`ingest_terrain` (Stages 7-8) | Locked out of `syria-full` (confirmed: gated behind `probe_output_path`, absent for `syria-full`) | n/a | none | confirmed by reading `build_region`'s stage 7/8 branch |
| Legacy `osm_cache_path` (Overpass-JSON) branch, `build/pipeline.py` ~541-565 | No — `RUN.md` documents this path as "small regions only"; `--osm-pbf` always takes precedence | n/a, not reachable at scale | none | **not listed in the plan's audit table**, but confirmed genuinely out of scope (Optional Refinement) |
| `store.schema.create_schema`/`open_for_build` | No — pure DDL | n/a | none | |
| Post-build summary (`tools/build_world_model.py`) | No — in-memory `BuildReport` only | n/a | none | confirmed, no DB queries in that file |
| SQLite index/`VACUUM`/`ANALYZE` | Does not exist in this pipeline | n/a | n/a | grepped, confirmed absent |
| `conn.close()` at end of `build_region` | No — no `PRAGMA journal_mode`/WAL set anywhere in `store/`; every stage already commits its own batches incrementally, so close has nothing large to flush | n/a | none | checked, no WAL/deferred-transaction risk |
| Stages 1-2 (`towns.lua`/`beacons.lua`) | No — small files | n/a | none | |

### Check Results

All run from `world-model/`:
- `ruff format --check src tests` — 106 files, all formatted.
- `ruff check src tests` — all checks passed.
- `mypy src` (strict) — no issues found in 63 source files.
- `pytest tests -q` — 490 passed, 3 skipped, run **twice**, identical result both times (11.87s,
  11.79s). `test_progress.py` alone run 3 times in isolation — 16 passed each time. Verified no
  `Heartbeat` thread leak directly (`threading.active_count()` before/after 20
  construct/enter/exit cycles: 1 before, 1 after).
- `body-layer`: not run in full — grepped `body-layer/src` for any import of `progress`,
  `ingest_srtm`, `ingest_junctions`, `roadnet.routes`, `osm.pbf`, or `build.pipeline`; zero matches
  (its only world-model coupling is `query.describe`/`query.line_of_sight`/`store.reader`, per
  `perception/geometry.py`, none of which this change touches). Confirms the plan's own claim; a
  full `body-layer` test run would not have added information here.

### Verdict

CHANGES REQUIRED — two required fixes, both small and mechanical (a one-line move in
`osm/pbf.py`, one new test in `test_pipeline_build_region.py` or `test_ingest_srtm.py` covering
the SRTM tile-load path). The core mechanism (`progress.py`'s `ThrottledProgress`/`Heartbeat`),
the GIL-release finding behind it, and every other migrated call site are sound, correctly wired
into `build.pipeline`, and covered by non-flaky, non-wall-clock-dependent tests. The coverage audit
is thorough and its "fast, no instrumentation needed" claims for `insert_features`/`insert_grid`/
`sha256_file` held up under independent re-measurement against real data, including the real
theatre-scale `.osm.pbf` on the actual `/mnt/f` mount.

### Review Confidence

Full read — every changed file in the commit range was read in full (not just the plan's prose),
every migrated call site was traced from its module into `build.pipeline`'s actual call graph, and
the debugger's key performance claims were independently reproduced against real data rather than
taken on trust.
