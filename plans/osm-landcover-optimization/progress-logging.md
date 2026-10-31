# Progress logging: investigation and fix

Follow-up to the `osm-landcover-optimization` milestone (already merged into this branch) — the
user's live `syria-full` build against a pre-filtered `syria-theatre.osm.pbf` logged
`[3/8] OSM overlay (.osm.pbf): starting` and then nothing for 4+ minutes, making a working build
indistinguishable from a hang. This is the third time a build stage has gone silent for minutes
(Stage 5 junctions earlier, Stage 3 OSM overlay twice), each fixed ad hoc — this note documents a
systematic audit and a single shared mechanism instead.

**Scope note**: this work happened on the already-checked-out `feature/osm-landcover-optimization`
branch while the user's own `syria-full` build was running from the same checkout. Per the task's
strict rules, `world-model/data/world-model/syria-full*.sqlite` was never read/queried, no
`syria-full` build was run, and validation used only small real extracts (a Turkey country
extract, filtered with the project's own `osmium tags-filter` command) and synthetic fixtures in
scratch/test directories.

## Confirmed root cause

`world-model/src/osm/pbf.py`'s `_FeatureCollector._log_progress_if_due` counted elements
*delivered to Python callbacks* and logged every `_PROGRESS_LOG_INTERVAL_ELEMENTS = 500_000`.
Two things starve that counter, both confirmed by measurement, not assumed:

1. `stream_features` passes `osmium.filter.KeyFilter(*_CLASSIFIER_TAG_KEYS)` to `apply_file`,
   which stops any element whose tags don't match the classifier's vocabulary from ever reaching
   `node()`/`way()`/`relation()` — so the "elements seen" counter undercounts real progress badly
   for anything but a hot, densely-tagged region of the file.
2. `_FeatureCollector` defines `area()`, so `apply_file` runs libosmium's two-pass multipolygon
   assembly automatically. The first pass (finding relation members) runs entirely in C++ with
   *zero* Python callbacks — no `node()`/`way()`/`relation()` calls to increment any counter at
   all during that pass.

**Measured**: `stream_features` run end-to-end (real production code, no mocks) against a
160,387,119-byte tags-filtered extract (see "Test data" below) took 81.0s total and logged exactly
**one** progress line, at 68.3s in — then nothing until it finished. That reproduces the reported
symptom almost exactly (minutes of silence during a real Stage 3 run).

## Test data

No `-clipped.osm.pbf` files existed on disk (RUN.md §2.5 says they're deleted after use), and the
task forbade touching the user's own `syria-theatre.osm.pbf` input or running a `syria-full`
build. Built a fresh, larger, real extract instead, entirely in the scratch directory:

```
osmium tags-filter /mnt/f/dcs-world-model/syria/raw/osm/countries/turkey-260911.osm.pbf \
    -e world-model/tools/osm_tags_filter.txt \
    -o turkey-filtered.osm.pbf --overwrite
```

(the full, unclipped Turkey country extract — no geographic `osmium extract` clip — since the
Turkey extract is already the theatre's largest input per the task, and a bigger, unclipped file
is a *harder* test than the real merged/clipped theatre file, not an easier one). Result: 23s to
filter, 160,387,119 bytes, 31.6M nodes / 736K ways / 33.8K relations. Deleted from scratch at the
end of this session — not committed, not left in the repo.

## GIL-release finding (decides the C++-silent-stretch mechanism)

Before picking a mechanism for the no-Python-callback case, checked whether pyosmium 4.3.1's
`apply_file` releases the GIL periodically on its own (a prerequisite for a background heartbeat
thread to actually run). Measured directly: a `SimpleHandler` with `node()`/`way()`/`area()`/
`relation()` callbacks (so `apply_file` runs the same two-pass area assembly production code
does) processing the same filtered Turkey extract, with a background thread ticking a counter
every 1.0s throughout:

```
apply_file elapsed: 10.3s, handler.count=1141499
heartbeat ticks observed: 11 (expected ~10)
max gap between ticks: 1.01s, min: 1.00s
```

The heartbeat thread ticked on schedule for the *entire* call, including whatever stretch was the
silent first pass — confirms pyosmium releases the GIL periodically on its own, not just when
invoking a Python callback. This is what makes a background-thread heartbeat viable at all; if the
GIL were held for the whole call, no other thread could run until it returned.

`pyosmium`/`osmium` bindings expose no byte-offset or block-count progress API (`osmium.io.Reader`
only has `header()`/`eof()`/`close()`), so there is no way to get an *exact* progress signal during
the silent stretches — the heartbeat's percent-complete/ETA is therefore a **calibrated estimate**
(elapsed time against a file-size-based expected duration), always logged with `estimated=True` so
it prints with a leading `~`. The real counters (`elements_seen`, `nodes_kept`, `ways_kept`,
`areas_kept`) reported alongside it are exact, not estimated — this follows the coordinator's
mid-task guidance: "an estimate is fine... prefer the simplest mechanism that gives a regular
heartbeat plus a rough ETA... label estimates clearly."

Calibration constant (`osm/pbf.py`'s `_PBF_CALIBRATED_BYTES_PER_S = 1_980_000`): 160,387,119 bytes
/ 81.0s ≈ 1.98 MB/s, from the same Turkey-extract `stream_features` run above. One data point, not
a profiled average across tag densities/relation complexity — documented as such in the code
comment; good enough for a rough ETA, not treated as exact.

## Audit: every potentially long operation

| operation | can exceed ~30s at `syria-full` scale? | max silent gap before | max silent gap after | mechanism |
|---|---|---|---|---|
| `osm.pbf.stream_features` (`apply_file`, `KeyFilter` + two-pass area assembly) | **Yes, confirmed** — 81.0s measured on one 160MB extract; `syria-full`'s real merged 7-country file is larger | **68.3s measured** (one count-based log line, then silent to completion) | **30.0s measured** (heartbeat fires every interval regardless of Python-callback activity) | `progress.Heartbeat` (background thread) + `ThrottledProgress` with `estimated=True` |
| `roadnet.routes.iter_routes` (`.routes` 2.25GB `mmap` walk, Stage 4) | Yes (whole-file walk, real file is 2.25GB) | Already had a working 5s time-based logger (added in a prior session, commit `e8707a8`) — **not the reported bug** | Same coverage, migrated to the shared helper at the project's standard 30s interval | `ThrottledProgress` (loop returns to Python every route boundary) |
| `ingest_junctions.ingest_junctions_streaming` (Stage 5, chunk loop) | Yes (millions of roads/chunks at full-theatre scale) | Already had a working 30s time-based logger (prior session, commit `b260ee7`) — **not the reported bug** | Same coverage, migrated to the shared helper (message format unified; existing progress tests updated to match) | `ThrottledProgress` |
| `ingest_srtm.ingest_srtm_grid` (Stage 6, grid-resampling row loop) | Row-based (every 50 rows) not time-based; not empirically excessive at current tile-count/spacing, but the wrong *kind* of guarantee per the task ("time-based, not count-based") | Not measured to exceed 30s at present, but had no time-based bound — could silently drift with more tiles/coarser spacing/slower disk | Migrated to `ThrottledProgress`, so it is now bounded even if per-row cost changes | `ThrottledProgress` |
| **SRTM tile loading** (`SrtmTile.from_file` loop, previously *before* Stage 6's own `_stage(...)` block even started) | Measured 4.0s for the real 131-tile Syria SRTM set (~2.8MB/tile) on this machine's `F:` mount — currently well under 30s, but this loop had **zero** logging of any kind, not even the stage's own "starting" line, until after it finished | **4.0s fully silent, and the "[6/8]: starting" line itself was delayed by that whole 4.0s** — a real (if currently small) instance of the exact "silent before the stage even announces itself" bug class | Moved inside the `_stage(...)` block (so "starting" logs immediately) and given its own `ThrottledProgress` | `ThrottledProgress` |
| Cache-hit OSM read (`build.pipeline`'s `iter_cached_features`/`insert_features` loop, when the OSM cache hits) | Scales with cached feature count (could be hundreds of thousands to low millions at `syria-full` scale); **had no progress logging of any kind** before this fix | Whole stage could be silent (previously bounded only by how fast `insert_features` runs — see below) | `ThrottledProgress`, `done`=cumulative features inserted, `total`= exact per-kind sum from `OsmIngestStats` | `ThrottledProgress` |
| `store.writer.insert_features` (called per already-bounded batch, ≤50,000 features) | **Measured**: 50,000 synthetic `StoredFeature` rows → 0.78s (~64k rows/s) | n/a (well under 30s per call) | n/a — no change needed; the *caller* (cache-hit loop above) needed the instrumentation, not this function | none added |
| `store.writer.insert_grid` (grid-cell insert loop) | **Measured** at real `syria-full` SRTM scale: 828×772 = 639,216 cells → 0.79s (~812k cells/s) | n/a | n/a — no change needed | none added |
| `osm_cache.hashing.sha256_file` (`.osm.pbf` content hash, Stage 3 cache-check) | **Measured**: 160MB file → 0.16s (~1GB/s, streamed 1MB chunks) | n/a — even a 1GB+ input would be well under 30s at this throughput | n/a | none added |
| `osm_cache.writer.insert_cached_features` / `finalize_cache` | Same per-batch shape as `insert_features` above (measured fast); `finalize_cache`'s `executemany` over a handful of meta rows is trivial | n/a | n/a | none added |
| `build.ingest_probe`/`build.ingest_terrain` (Stages 7–8, in-memory grid computation) | **No** — M7 locks these stages out of `syria-full` entirely (`build.pipeline`'s own docstring: SRTM replaces the live probe as the primary full-theatre grid); the only realistic scale is a bounded probe grid (few thousand points) or one `store.chunks.CHUNK_SIZE_M`-bounded chunk (M8's `add_probe_chunk`) | n/a | n/a | none added — out of scope for `syria-full`, and bounded elsewhere |
| `store.schema.create_schema` / `open_for_build` (delete+recreate, DDL) | No — no data volume involved, pure DDL | n/a | n/a | none |
| Post-build summary (`tools/build_world_model.py`'s final print loop) | No — prints from the in-memory `BuildReport`, no DB queries | n/a | n/a | none |
| SQLite index/R\*Tree build, `VACUUM`, `ANALYZE` | **Does not exist in this pipeline** — `feature_bbox` is a `CREATE VIRTUAL TABLE ... USING rtree` populated incrementally inside `insert_features`, one row at a time alongside each `feature` insert, in the same transaction; grepped the whole `src/` tree for `VACUUM`/`CREATE INDEX`/`ANALYZE` — no matches anywhere in the pipeline | n/a | n/a | n/a |
| Stages 1–2 (`towns.lua`/`beacons.lua` regex parse) | No — small files, already documented "(fast)" in RUN.md, unchanged by this audit | n/a | n/a | none |

## Mechanism chosen for the C++-silent case, and why

`progress.Heartbeat`: a context manager that starts a background daemon thread calling a
caller-supplied `report_fn()` every `interval_s` seconds (default 30s, this project's standing
convention) from `__enter__` to `__exit__`, regardless of what the wrapped call is doing at that
moment. Chosen over the alternatives the task asked to evaluate:

- **(a) background heartbeat thread reading shared counters** — **chosen**. Confirmed viable by
  the GIL-release measurement above (a real prerequisite that was checked, not assumed). Simple:
  no change to pyosmium's own iteration model, works uniformly whether the main thread is inside
  `apply_file`'s C++ core or inside a nested Python callback's own DB-write work (the heartbeat
  covers the *whole* wrapped call, wall-clock, not just the parts that call back into Python).
- **(b) `osmium.FileProcessor` (pyosmium 4.x) instead of `SimpleHandler.apply_file`** — not
  pursued. Would mean re-deriving `_FeatureCollector`'s buffering/batching/area-assembly-count
  logic on a different iteration API, a much larger and riskier change than wrapping the existing
  call, for no benefit once (a) was confirmed to work — `FileProcessor` would still need the same
  KeyFilter to keep the M9 speed win, and still runs the same two-pass area assembly under the
  hood, so it doesn't obviously solve the "no signal during the first pass" problem any better.
- **(c) file-read byte-offset progress** — not available. `osmium.io` exposes no reader-position
  API (checked directly: `Reader`'s only methods are `close`/`eof`/`header`). Would require
  bypassing `SimpleHandler`/`apply_file` entirely for manual block-by-block reading, which is
  exactly the larger, riskier rewrite (b) already ruled out, for a signal (exact byte progress)
  that isn't actually needed — the coordinator's guidance during this task explicitly allows a
  calibrated time-based estimate instead.
- **(d) other** — none found that keeps the `KeyFilter` speed win cheaply; (a) is the simplest
  mechanism that gives a regular heartbeat plus a rough ETA, per the coordinator's stated
  preference.

## Shared mechanism

New module `world-model/src/progress.py`:

- `format_progress(operation, elapsed_s, done, total, estimated, **counters)` — pure formatter,
  builds `<operation>: <done>/<total or ?> (<pct if total known>, <key=value counters>, <elapsed>s
  elapsed[, ~<remaining>s remaining])`. Never uses scientific notation for large counts (guards
  against Python's `f'{v:g}'` flipping to `1e+06` above ~1e6, which real theatre-scale counts
  routinely exceed). `estimated=True` marks `done`/`total`/percent with a leading `~`.
- `ThrottledProgress` — construct once per operation, call `.maybe_log(...)` every loop iteration
  (cheap no-op except when `interval_s` has elapsed since the last line) or `.log(...)` to force an
  immediate line (an up-front "N items to process" line, or a heartbeat tick). Clock is injectable
  for deterministic tests.
- `Heartbeat` — background daemon thread calling a caller-supplied `report_fn()` every
  `interval_s`, from `__enter__` to `__exit__` (always stops/joins on exit, including on
  exception).

Both default to 30.0s (`DEFAULT_INTERVAL_S`) — "at most every 30s, at least every ~30s" is now a
project-wide constant, not a per-module judgment call.

## Migrated call sites

- `osm/pbf.py`'s `stream_features` — the count-based `_log_progress_if_due` removed entirely;
  `_FeatureCollector` now exposes `progress_counts()` (a plain dict snapshot, safe to read from
  another thread under the GIL); `apply_file` wrapped in `Heartbeat` + `ThrottledProgress` with
  `estimated=True` and the calibrated ETA.
- `build/ingest_srtm.py`'s row loop — migrated from `row % 50 == 0` to `ThrottledProgress`.
- `build/ingest_junctions.py`'s chunk loop — migrated its existing hand-rolled time-based logic
  onto `ThrottledProgress` (same behaviour, unified message shape — existing progress tests
  updated to match the new format, not weakened).
- `roadnet/routes.py`'s `.routes` walk — migrated its existing hand-rolled 5s time-based logic
  onto `ThrottledProgress` at the project's now-standard 30s interval.
- `build/pipeline.py` — two new instrumentation points that had none before:
  1. The OSM-cache-hit read loop (`iter_cached_features`/`insert_features`), `done`=cumulative
     features inserted, `total`=exact per-kind sum from the cache's own recorded `OsmIngestStats`.
  2. SRTM tile loading, moved inside Stage 6's `_stage(...)` block (previously ran, fully silent,
     *before* that block's own "starting" line) and given its own `ThrottledProgress`.

## Parse-time impact

Re-ran the same 160,387,119-byte Turkey extract through the *migrated* `stream_features` twice:

| run | total elapsed | log lines | max silent gap |
|---|---|---|---|
| baseline (unmigrated) | 81.0s | 1 | 68.3s |
| migrated, run 1 | 89.4s | 2 | 30.0s |
| migrated, run 2 | 83.8s | 2 | 30.0s |

The spread (81.0–89.4s) is within normal machine-load variance for this box, not a consistent
regression attributable to the heartbeat thread itself — a daemon thread sleeping and waking every
30s costs nothing measurable against an 80+ second parse. The KeyFilter speed win the plan
originally measured (7s vs 50s on its own small-region test) is unaffected — nothing about
`apply_file`'s own filtering/parsing logic changed, only how progress is reported around it.

## Tests

- `tests/test_progress.py` (new): `format_progress` (line shape, scientific-notation guard,
  `estimated` marking, remaining-time extrapolation), `ThrottledProgress` (throttling with an
  injected fake clock — first-call-always-logs, suppressed-within-interval, logs-again-after-
  interval, zero-interval-logs-every-call, `.log()` bypasses and resets the throttle), `Heartbeat`
  (report_fn called on a background thread, stops after `__exit__`, stops even when the wrapped
  block raises — short real intervals with loose `>= 1` assertions, not exact-count timing).
- `tests/test_osm_pbf.py`: unchanged (no test depended on the removed count-based logger's exact
  messages); full suite still passes against the rewritten `_FeatureCollector`.
- `tests/test_ingest_srtm.py`: added a progress test (interval forced to 0, asserts one line per
  row through the shared helper).
- `tests/test_ingest_junctions.py`: updated the two existing progress-format assertions to the new
  unified message shape (the old assertions checked exact strings from the removed hand-rolled
  logger).
- `tests/test_roadnet_routes.py`: added a progress test (interval forced to 0).
- `tests/test_pipeline_osm_cache.py`: added a progress test for the previously-uninstrumented
  cache-hit read loop (build twice against the *same* `out_path` so the second build is a genuine
  cache hit, not a miss against a fresh sibling cache file — a fixture-alignment mistake caught by
  the test's first failing run, then corrected).

## Check results

All run from `world-model/`, per `world-model/CLAUDE.md`'s Commands:

- `ruff format --check src tests` — 106 files, all formatted.
- `ruff check src tests` — all checks passed.
- `mypy src` (strict) — no issues found in 63 source files.
- `pytest tests -q` — 490 passed, 3 skipped (real-data-gated tests, no real `data/raw/` staged on
  this machine — expected, matches pre-existing skip conditions).

body-layer was not re-checked: it only imports `query.describe`, `query.line_of_sight`, and
`store.reader` (confirmed by inspecting `body-layer/src/perception/geometry.py`'s imports), none
of which this change touched.

## Durable rule

Added to `world-model/CLAUDE.md` (new "Progress reporting" section) and `world-model/docs/
CONVENTIONS.md` (new bullet): every build operation that can run longer than ~30s at `syria-full`
scale must report progress through `src/progress.py`; new stages must include it from the start,
not bolt it on after the next silent-build report. `RUN.md` §3.3's stage table updated to describe
the actual current log line shapes (previously described the pre-fix Stage 3 behaviour and the
pre-migration Stage 4/6 behaviour).
