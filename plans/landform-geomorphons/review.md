### Review Summary

Reviewed `feature/landform-geomorphons` (tip `68e0f29`, confirmed via `git rev-parse HEAD` before
anything else — worktree checked out at the correct commit) against `plans/landform-geomorphons/
plan.md`, `implementation.md`, and `world-model/ROADMAP.md`'s `WM-B6` entry. Stages A-F are built as
scoped; Stage G (full-theatre) correctly left to the user.

All verification commands pass, matching the implementer's own claims exactly:

- `ruff format --check src tests`: 116 files already formatted
- `ruff check src tests`: all checks passed
- `mypy --strict src` (run from inside `world-model/`): no issues, 71 source files
- `pytest tests -q`: **508 passed, 3 skipped** (matches claim)
- `invariant-check`: all PASS (no omniscience, module independence, no `sys.path` smuggling, no
  bare `except`, no `BINOCULAR_RANGE_MULTIPLIER` regression — not relevant to this layer but ran
  clean repo-wide). The two WARN categories (`except: pass`, `type: ignore`) have zero hits in this
  branch's diff.
- No new dependency: `pyproject.toml`'s `dependencies` list is textually unchanged except a comment
  re-scoping; numpy/scipy pins untouched. `tools/inspect_terrain.py` uses Pillow (already a
  dependency), not matplotlib. Confirmed by reading the file and the diff — no stray import.

**Independently re-ran the coastal-hills acceptance window** (`tools/inspect_terrain.py
--srtm-dir <main-checkout's real data/raw/dem/syria-full> --center -5000,15000 --radius-km 8`)
against the real SRTM data. Output: **299 ridge / 289 valley lines, longest 7.18 km / 7.70 km** —
exactly matches the implementer's reported numbers, and the rendered PNG is **byte-identical**
(same MD5) to the committed `data/renders/coastal-hills-geomorphons.png`. The reproduction claim is
not just plausible, it's exactly reproducible. The residual gap against the originally-accepted
312/273 and 8.3/6.5 km is real and is honestly reported rather than tuned away, consistent with the
task's own instruction. Visually, the render shows continuous multi-kilometre ridge/valley lines
following the hillshade's real crests and draws, not fragmented stubs — the qualitative result the
user accepted.

**Verified the junction-walk is deterministic**, the specific risk named in this review's brief.
Ran `terrain.skeleton.trace` on an identical synthetic skeleton across four separate process
invocations, two with `PYTHONHASHSEED` pinned to different values and two with it unset (random):
all four produced byte-identical output. This holds because `trace`'s only non-array state is a
Python `set`/`dict` keyed by `tuple[int, int]`, and CPython does not salt integer (or int-tuple)
hashes — only `str`/`bytes` get the randomized-hash treatment — so iteration order over these
collections is stable across processes for a fixed input array. The order-dependence the
implementer flagged (which walk reaches a junction's edges first) is real and matches
`implementation.md`'s description, but it is a property of the *algorithm* (sensitive to which
synthetic fixture you hand it), not of *execution* (same input always produces the same output).
The cache's premise — identical SRTM input + identical knobs → identical geometry — holds.

**Verified the resumability mechanism directly**, since the one test named for it doesn't actually
exercise it (see Required Fixes). Hand-constructed a terrain cache with tile A marked complete and
tile B absent (simulating an interrupted build under a matching identity), then called
`ingest_terrain` with the same tile set/params: it reported `tiles_cache_hit=1, tiles_processed=1`
— tile A was skipped, tile B was processed. The resumability design works as the plan describes;
only the test coverage for it is missing.

### Required Fixes

- **`world-model/docs/M8_PROBE_STORE.md` is now stale and actively misleading, and it's the exact
  place root `CLAUDE.md` names as the pointer for an M8 reader** ("a few subproject-specific
  pointers worth having by name... `world-model/docs/M8_PROBE_STORE.md`"). It still says the probe
  store holds "fine elevation, `surface_type`, and ridge/valley features accumulated chunk by chunk
  via `build.pipeline.add_probe_chunk`" and its Performance section still costs "chunk-scoped
  ridge/valley classification" into the `add_probe_chunk` timing figure — both now false, since this
  branch removes chunk-scoped terrain extraction entirely (`add_probe_chunk`'s `"ridge"`/`"valley"`
  chunk coverage now stays `UNQUERIED` forever). The removal *is* well-recorded elsewhere —
  `ROADMAP.md`'s `WM-B6` "Implementation status" subsection, `build/pipeline.py`'s own docstring,
  `probe_store/reader.py`'s docstring, and `implementation.md` all describe it correctly — but the
  one document a future M8 reader is pointed to by name still describes the old, removed behaviour.
  Fix: update the "What lives where" bullet and the Performance section's chunk-scoped-terrain
  mention in `docs/M8_PROBE_STORE.md` to match current behaviour (grid/`surface_type` chunk
  ingestion only; no ridge/valley).

- **Region-bbox clipping gap is real, confirmed by reading `ingest_terrain`'s own docstring and
  code, and is not recorded in `ROADMAP.md`'s WM-B6 "Implementation status" at all** — only in
  `implementation.md`'s log. A region-scoped build (e.g. `latakia-20km`, the project's standard
  small-region dev/test loop) stores *every* ridge/valley line a covering SRTM tile produces across
  its *whole* ~1°×1° (~100×90 km at Syria's latitude) extent, not clipped to the region's own
  (typically ~20-40 km) bbox. This is invisible today only because the test fixtures are flat/tiny.
  The near-term consequence is bounded — the only build about to run for real is the user's own
  full-theatre rebuild (Stage G, riding along with `WM-B1`), where every tile *is* in-theatre and
  this gap doesn't manifest — but the very next region-scoped `latakia-20km` rebuild (used
  throughout this project's dev cycle for anything downstream of this work, e.g. the consumer-half
  rework the roadmap already names) will silently insert a geographically oversized set of
  ridge/valley rows into a store whose entire purpose is to stay small and fast. Required: add this
  gap to `ROADMAP.md`'s WM-B6 "Implementation status" subsection (parallel treatment to how the M8
  chunk-gap is already recorded there) so it isn't rediscovered as a surprise on the next region
  rebuild. An actual bbox-clip fix is not required before merging this branch (full-theatre is the
  only real near-term consumer), but it should be called out to the user explicitly as a known,
  not-yet-fixed limitation before anyone relies on a region-scoped terrain rebuild.

- **The one test named for cache resumability doesn't test resumability.**
  `test_ingest_terrain_resumes_a_partially_completed_cache` (`tests/test_ingest_terrain.py:191`)
  actually tests "a different tile set forces full invalidation, then a repeat run is a full cache
  hit" — both already covered by other tests in the same file. It never constructs a
  partially-complete cache *under one matching identity* and confirms the already-complete tile is
  skipped while the incomplete one is (re)processed, which is the actual mechanism `ingest_terrain`
  implements (`already_complete = completed_tile_ids(conn)` + per-tile branch) and the literal thing
  the plan's Stage E acceptance check (b) asked for. I verified by hand that the mechanism itself is
  correct (see Review Summary), so this is a coverage gap, not a live defect — but it's a cheap,
  important gap to close: this is the single piece of new infrastructure in this codebase (the
  OSM/probe caches are single-shot) and the one explicitly requested by the user ("too expensive to
  run at every world model rebuild... cache the extracted lines"). Add a test that writes a
  tile-complete row for one tile only under a matching `TerrainCacheMeta`, then calls
  `ingest_terrain` with the full tile set and asserts `tiles_cache_hit=1, tiles_processed=1` (the
  scenario I ran by hand during this review).

### Optional Refinements

- `pyproject.toml`'s `scipy.*` mypy-override comment still says "`terrain.curvature` is the only
  caller" of untyped scipy — `terrain.curvature` is deleted and `terrain.skeleton.close_mask` is now
  the (only) caller of `scipy.ndimage`. Cosmetic; doesn't affect correctness (the override is a
  blanket `module = "scipy.*"`, not scoped to one file), but worth correcting so a future reader
  doesn't conclude the override is dead and safe to remove. (optional)
- `src/roadnet/junctions.py` has a comment citing `terrain/curvature.py`'s threshold constant by
  name as a style precedent; that file no longer exists. Same cosmetic class as above. (optional)
- The junction-walk's actual behaviour (order-dependent, "whichever walk reaches a junction first,"
  not the plan's idealised "pair incident branches by direction") is honestly documented in three
  places (`skeleton.py`'s module docstring, `implementation.md`, `ROADMAP.md`) — no fix needed, just
  flagging for whoever picks up Stage 5 that the plan's own description of this mechanism should not
  be trusted over the code/tests, which this review already confirms are internally consistent.
  (informational, no action needed)

### Verdict

APPROVED WITH MINOR FIXES

All three required fixes are documentation/test-coverage items, not behavioural changes — no
production logic needs to change. Recommend: update `docs/M8_PROBE_STORE.md`, add the region-bbox
gap to `ROADMAP.md`'s WM-B6 entry, and add one resumability test to `test_ingest_terrain.py`. None
of these block the user's own Stage G full-theatre run, which is unaffected by any of them.

**For the user**: this branch is ready to merge once the three fixes above land (small, and can be
done directly rather than re-entering the full Implementer→Reviewer loop, per the project's own
"local, reversible" escalation threshold — these are documentation and test additions, not design
changes). The Stage G run command is in `ROADMAP.md`'s WM-B6 entry; nothing in this review changes
it. Before relying on a `latakia-20km` (or any other region-scoped) terrain rebuild for follow-on
work, remember the region-bbox gap above — it will store out-of-region geometry until fixed.

### Review Confidence

Full read. Read the plan, implementation log, and ROADMAP entry in full; read every new/rewritten
source module (`geomorphons.py`, `resample.py`, `skeleton.py`, all of `terrain_cache/`,
`ingest_terrain.py`, `features.py`, the `pipeline.py` diff) and the relevant test diffs in full, not
spot-checked. Ran all four verification commands directly against the checked-out tip. Independently
reproduced the acceptance numbers and render (byte-identical) against real data, independently
verified junction-walk determinism across process boundaries, and independently verified the
resumability mechanism by hand-constructing an interrupted-cache scenario — none of these were taken
on the implementer's word alone.
