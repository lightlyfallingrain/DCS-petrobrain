### Implementation Summary

Built Stages A-F of the plan: a vectorised geomorphons classifier, vectorised Zhang-Suen thinning
plus the ported junction-walking tracer, a vectorised DCS-lattice SRTM resampler, per-SRTM-tile
margin/clip tiling, the resumable per-tile cache (built in from the first pass, per the user's own
instruction), and `build/pipeline.py`'s terrain stage rewired to run off `srtm_tile_paths` directly.
The retired marker-controlled-watershed mechanism (`terrain/curvature.py` and the basin/divide
machinery in `terrain/features.py`) is deleted. Stage G (full-theatre build) is explicitly not run
here, per the project's execution-boundary rule.

### Files Changed

- `world-model/src/terrain/curvature.py` — **deleted**. Watershed-seeding steps with no geomorphons
  equivalent.
- `world-model/src/terrain/geomorphons.py` — **new**. Vectorised NaN/void-aware port of
  `tools/spike_geomorphons.py`'s `geomorphons()`.
- `world-model/src/terrain/resample.py` — **new**. Vectorised bilinear SRTM-tile sampling onto a
  DCS-metre lattice (`sample_tiles_bilinear`, `lattice_coords`, `resample_window`), replacing
  `ingest_srtm.py`'s per-cell loop for this module's own finer lattice.
- `world-model/src/terrain/skeleton.py` — **new**. `family_mask`, `close_mask`, vectorised `thin`
  (Zhang-Suen), `close_and_thin`, and `trace` (the junction-walking tracer, ported verbatim from
  `tools/spike_junction_walk.py`'s `polylines()`).
- `world-model/src/terrain/features.py` — **rewritten**. `TerrainComponent` trimmed to
  cells/points/elevation_range_m/orientation_deg (no basin fields); `component_from_trace` replaces
  the old `_build_component`; `_chaikin_smooth`/`_smooth_for_storage` ported verbatim from
  `feature/landform-curve-smoothing` (commit `ecdf3e2`); `to_stored_features` adapted (no
  `basin_width_m` tag — no basin exists to measure the width of).
- `world-model/src/terrain_cache/` — **new package**: `schema.py`, `models.py`, `paths.py`,
  `hashing.py`, `writer.py`, `reader.py` — the per-SRTM-tile resumable cache, mirroring
  `osm_cache/`'s layout with the one deliberate structural deviation the plan specifies (per-tile
  transactions mutated in place at the canonical path, not a `.tmp`-then-rename whole-file swap).
- `world-model/src/build/ingest_terrain.py` — **rewritten**. New signature: `srtm_tile_paths` +
  `theatre` + `region` + `cache_path` in, not a pre-loaded `ElevationGrid` + watershed knobs. Owns
  the whole per-tile pipeline (bbox sizing, margin, resample, classify, mask, close+thin, trace,
  clip-to-core via `_split_core_segments`, smooth, wrap) plus the cache check/write and per-tile
  progress logging. `ingest_terrain_chunk` (M8's chunk-scoped variant) is **removed**, not ported —
  see "Notable Discoveries" below.
- `world-model/src/build/pipeline.py` — rewired. The terrain-semantics stage now gates on
  `existing_srtm_tile_paths` directly (captured once, ahead of the SRTM grid-insert block) instead
  of `elevation_source_id is not None`, and calls the new `ingest_terrain` with the tile paths/
  region/cache path rather than reading back the stored grid. `add_probe_chunk`'s chunk-scoped
  terrain step is removed (see below); its `smoothing_window_cells`/`seed_footprint_cells`/
  `relief_threshold_m`/`width_ceiling_m`/`min_cell_count` parameters are dropped from its signature
  (no remaining caller passed them explicitly except the removed call itself).
- `world-model/src/coordinates/__init__.py` — added `dcs_to_wgs84_array`, the vectorised
  counterpart to `dcs_to_wgs84` the plan's design decision 1 calls for (coordinate math stays
  centralized in this subsystem, per the project invariant).
- `world-model/src/store/models.py` — `StoredFeature`'s "Reserved on ridge/valley rows" docstring
  updated: `basin_width_m` bullet removed (no basin, no width gate); `adjacent_feature_ids`'s
  rationale re-worded to not cite the deleted `grow_basins`/`basin_ids` mechanism.
- `world-model/src/probe_store/reader.py` — `load_chunk_elevation_window`'s docstring updated to
  note it has no terrain consumer any more (kept as a general-purpose accessor, still exercised by
  `test_probe_store.py`).
- `world-model/tools/inspect_terrain.py` — **rewritten**. The old PIL-based basin-colour visualiser
  (watershed-era) is replaced with an aligned-hillshade renderer over the new geomorphons pipeline,
  using Pillow (an existing dependency) rather than matplotlib (what the prior spike's own render
  tooling used, never added to `pyproject.toml` — this is diagnostic tooling, but still shouldn't
  need an unapproved dependency).
- `world-model/pyproject.toml` — no dependency changes (numpy/scipy stay pinned exactly as before).
  The comment block scoping those two libraries was re-scoped from the deleted `terrain.curvature`
  to the new `terrain.geomorphons`/`terrain.resample`/`terrain.skeleton`.
- `world-model/data/renders/coastal-hills-geomorphons.png` — the aligned-hillshade acceptance render
  for the coastal-hills window (centre `(-5000, 15000)`, 8 km radius), produced by the new
  `tools/inspect_terrain.py` against the real `data/raw/dem/syria-full` tiles (read from the main
  checkout's filesystem path, since a fresh worktree has no `data/` at all — gitignored). `data/
  renders/` is **not** gitignored (unlike `data/raw`/`processed`/`world-model`), matching the
  precedent set by the prior watershed-resolution spike's own committed renders.
- `world-model/ROADMAP.md` — `WM-B6` entry gained an "Implementation status" subsection recording
  what's built, the reproduction numbers, the two real discrepancies found (min_cells default,
  junction-walk mechanics), the M8 chunk-pipeline gap, what Stage D/E's acceptance checks were *not*
  run against real multi-tile/interrupted-process data, and the Stage G run command.

### Tests Added

- `tests/test_geomorphons.py` (6 tests) — synthetic DEM profiles (flat, single ridge, single
  valley, ramp) with known expected classes; void-center and void-neighbour handling.
- `tests/test_resample.py` (6 tests) — `lattice_coords`' convention; `sample_tiles_bilinear`'s flat/
  outside-every-tile/void-corner cases and agreement with `SrtmTile.height_at`'s scalar form;
  `resample_window` end-to-end shape.
- `tests/test_skeleton.py` (9 tests) — `family_mask`/`close_mask`; `thin` checked **bit-for-bit**
  against a ported pixel-by-pixel Zhang-Suen reference (`tools/spike_geomorphons.py`'s own `thin()`)
  on a random blob and a thick diagonal band; `trace`'s straight-line/min-cells/max-turn behaviour,
  and the isolated-junction spur/X-junction behaviour (see "Notable Discoveries").
- `tests/test_terrain_cache.py` (9 tests) — fresh-cache absence, meta round-trip, identity-match
  rules, per-tile write/overwrite, `build_complete` gating, cross-tile `load_all_features`, reset.
- `tests/test_terrain_features.py` (9 tests, **rewritten**) — `component_from_trace`'s point/
  elevation/orientation construction; `_chaikin_smooth`/`_smooth_for_storage` (ported, re-tested
  against the new call shape); `to_stored_features`'s tags, with explicit no-`basin_width_m`
  assertions.
- `tests/test_ingest_terrain.py` (6 tests, **rewritten**) — flat tile -> no features; missing tile
  path skipped; sloped tile -> a real ridge tagged with the caller's `source_id`; second run is a
  full cache hit; a parameter change invalidates the whole cache; a different tile set forces full
  reprocessing and then itself becomes a cache hit on the next run.
- `tests/test_probe_chunk_pipeline.py` (**edited**, not rewritten) — the one test that asserted
  specific chunk-scoped ridge/valley extraction results is renamed and rewritten to assert the new,
  honest behaviour (`terrain_skipped=True`, `terrain_stats=None`, `"ridge"`/`"valley"` chunk
  coverage staying `UNQUERIED` rather than `QUERIED_WITH_DATA`); the other three tests only needed
  their now-nonexistent `min_cell_count=...` keyword argument removed.
- `tests/test_pipeline_build_region.py` — **no changes needed**. The existing SRTM-wiring tests
  (`test_build_region_srtm_tile_paths_becomes_the_primary_elevation_grid`,
  `..._given_but_missing_is_skipped_not_an_error`) already asserted `terrain_skipped`/`terrain_stats`
  in a shape the new mechanism satisfies unchanged (a flat 2x2 fake tile produces zero ridge/valley
  features either way) — confirmed by running them, not assumed.
- `tests/test_terrain_curvature.py` — **deleted**, per the plan's own "What must be rewritten"
  section; the whole module (`smooth_grid`/`find_basin_seeds`) is gone.

### Checks

(world-model/ — the only subproject touched)

- `ruff format --check`: pass (9 files needed reformatting after first draft, applied and
  re-verified clean)
- `ruff check`: pass (fixed: two unnecessary `int()` casts in `ingest_terrain.py`; B023
  loop-variable-in-closure warnings in `skeleton.py`'s `trace`, suppressed with `noqa` and a comment
  explaining why the closure is safe there — the nested function is defined and fully consumed
  within the same loop iteration before the captured variables are reassigned; an unused `pytest`
  import and a `dict()`-vs-literal nit in two new test files)
- `mypy --strict` (run from inside `world-model/`, per the project's CWD-only config-discovery
  rule): pass, 71 source files
- `pytest -q`: **508 passed, 3 skipped** (baseline on `main` in this worktree: 494 passed/3 skipped
  per the task brief; net addition consistent with the new/rewritten test modules above)

### Notable Discoveries

- **The plan's own citation of `min_cells=3` names the wrong spike file's default.** The plan's
  point 6 and the "noise removal" paragraph both point at `spike_geomorphons.py`'s `trace(...,
  min_cells=3)` — but that is the *naive* cut-at-every-junction tracer, explicitly superseded. The
  actual reference implementation this plan says to port (`tools/spike_junction_walk.py`'s
  `polylines()`) defaults to `min_cells=4`. Verified by reproducing the accepted coastal-hills
  window: `3` gives 448 ridge / 418 valley lines (way over the accepted 312/273); `4` gives 299/289,
  far closer. `terrain.skeleton.DEFAULT_MIN_LINE_LENGTH_CELLS` is set to `4`, with a comment
  recording why, rather than silently following the plan's citation.

- **The junction-walk's real mechanism is order-dependent, not an explicit best-pairing
  computation — a genuine gap between the plan's description and the ported reference code.** The
  plan's design decision 5 describes "pair up incident branches by direction, greedy by smallest
  angular deviation," written before the real spike file was located. What `tools/
  spike_junction_walk.py`'s `polylines()` (and this port's `terrain.skeleton.trace`) actually does:
  every degree-!=-2 node (every true endpoint *and* every junction) walks into each of its own
  unused neighbours in the outer loop's iteration order; a junction's own edges go to whichever walk
  reaches them first. On a real, dense skeleton, a long approach chain from a distant endpoint
  usually "wins the race" to a junction before the junction's own entry in the outer loop claims its
  edges — which is what produces the multi-kilometre continuous crests seen on the real window. But
  on an **isolated** synthetic junction with no approach chain (every arm the same short length, as
  in a hand-built fixture), there is no such chain to win, and the junction splits into N separate
  stubs meeting there — not the two-crossing-lines or pair-and-continue behaviour the plan's prose
  describes. Confirmed directly: an isolated 3-arm spur splits into 3 stubs (lengths 4/5/6, all
  starting at the junction cell); an isolated 4-arm X splits into 4 equal stubs. This is a property
  of the reference algorithm being ported, not a defect introduced here — documented at length in
  `terrain/skeleton.py`'s module docstring and exercised by `tests/test_skeleton.py`'s spur/
  X-junction tests, which assert the real (verified) behaviour rather than the plan's idealised one.
  Worth flagging to whoever picks up Stage 5 (the callout): the "genuine X-junction" case the plan
  asked to be checked is real and checkable, but its actual behaviour is less predictable than the
  plan assumed — it depends on which approach chain happens to reach the junction first, not a
  symmetric or principled tie-break.

- **Reproduction against the accepted render is close but not exact: 299 ridge / 289 valley lines,
  longest ridge 7.18 km / valley 7.70 km, against the accepted 312 / 273 and 8.3 km / 6.5 km** (same
  window: centre `(-5000, 15000)`, 8 km radius, lookup 15 cells, flatness 1°, ridge = ridge+peak,
  valley = valley+pit). Per the task's own instruction, this gap is reported rather than tuned away.
  What was checked and ruled out as the cause: thinning is bit-for-bit identical to a ported
  pixel-by-pixel reference on the real window's own ridge mask (3098 skeleton cells, exact match);
  masking/closing use the documented 3x3 structuring element and `close_iterations=1`; the
  `min_cells` fix above accounts for most of a much larger initial gap (448/418 at `min_cells=3`).
  The remaining ~4-6% residual is most plausibly environment/data drift (this session's `data/raw/
  dem/syria-full` on the main checkout vs. whatever the original interactive spike session held,
  never committed) rather than a mechanism defect — the render
  (`data/renders/coastal-hills-geomorphons.png`) shows the same qualitative result the user accepted
  (continuous multi-kilometre crests through junctions, not fragmented stubs). Flagging for the
  user's own judgement rather than asserting it is fine.

- **A real plan gap, found and handled rather than silently worked around: M8's chunk-scoped
  terrain pipeline has no geomorphons equivalent, and the plan never says what should happen to
  it.** `build.pipeline.add_probe_chunk` called `build.ingest_terrain.ingest_terrain_chunk` (the
  watershed mechanism's chunk-scoped variant, run over a single probe chunk + 1-cell border).
  Geomorphons' processing unit is a whole SRTM tile with a multi-kilometre margin (the `lookup_cells`
  floor alone needs ~1.35 km of real context); a 5 km probe chunk is the wrong unit entirely, and
  the plan's own scope note ("Stage 3-5... stay unbuilt") doesn't mention M8 at all. Decision made
  here: remove chunk-scoped ridge/valley extraction from `add_probe_chunk` rather than attempt to
  force geomorphons into a chunk-sized window it wasn't designed for. Grid/surface-type chunk
  ingestion is unaffected; `ProbeChunkReport.terrain_stats`/`terrain_skipped` are kept on the
  dataclass for shape compatibility but always come back `None`/`True` now. This is a narrowing of
  real behaviour (the old mechanism's own docstring already called the chunk-scoped case "an
  accepted, non-crashing degenerate case" that routinely produced no features anyway), not a
  regression — but it is a real scope decision the plan didn't make, so it's named here rather than
  buried in a diff. One test (`test_add_probe_chunk_ingests_grids_and_terrain_features`) asserted
  specific ridge/valley counts from this path and is rewritten.

- **Region-bbox clipping of terrain output is unaddressed by the plan, and this implementation
  doesn't invent one.** The plan treats "one SRTM tile = one processing window" as independent of
  whatever region a caller is building, with no mention of clipping a tile's extracted features down
  to a smaller region's own bbox. A region-scoped build (e.g. `latakia-20km`) therefore stores
  whatever ridge/valley lines its given tile(s) produce across their *whole* tile extent, not just
  the region's own footprint — for a small test region fed a tiny/flat fixture tile this is
  invisible (zero features either way), but a real region-scoped build against a real, sloped SRTM
  tile would insert features well outside the region's intended bbox. Left unaddressed per the
  plan's own silence on it, documented here so it isn't rediscovered as a surprise during a real
  `latakia-20km` rebuild.

- **Stage D (tile-boundary seam handling) and Stage E (kill-mid-build resume) were not acceptance-
  tested against real multi-tile adjacency or a literal interrupted process.** `_split_core_segments`
  and the per-tile cache transactions are exercised by unit tests (`test_ingest_terrain.py`'s
  multi-tile cache test, `test_terrain_cache.py`'s per-tile write/reset tests) and are reasoned
  correct from the per-tile-transaction design, but no test actually builds two adjacent real SRTM
  tiles and checks the seam behaviour by eye, nor kills a real `ingest_terrain` process mid-tile-loop
  and confirms resumption. Flagging per the plan's own "Risks & unknowns" section, which named both
  as real-but-unverified.

### Performance fix: bounded terrain-ingest memory, O(N) Chaikin check (`b4d38cf`)

Applied `performance.md`'s findings ahead of the user's planned full-theatre build.

**Item 1 (blocking): per-tile streaming inserts.** `ingest_terrain` no longer returns/accumulates a
whole-theatre `list[StoredFeature]` — it takes an `on_tile_features` callback, invoked once per tile
(cache hit or freshly processed, already retagged with `source_id`) with just that tile's features.
`build/pipeline.py`'s new `_flush_terrain_tile` callback calls `insert_features` immediately per
tile, mirroring the existing OSM streaming-ingest `_flush_nodes`/`_flush_ways`/`_flush_areas`
pattern. The whole-build cache-hit fast path (previously one `load_all_features` call — the same
unbounded shape, just on a warm rebuild) now folds into the same per-tile loop, so a warm rebuild is
bounded per tile too; `load_all_features` itself is untouched (still used by `test_terrain_cache.py`)
but `ingest_terrain` no longer calls it. The final `[replace(...) for f in cache_features]`
second-list copy performance.md flagged as a transient doubling is gone entirely — retagging now
happens per tile, inside the loop, so there is never a second full-size list.

**Transactional behaviour decision**: one `insert_features` call (one SQLite transaction) per tile,
not one atomic transaction for the whole stage. Chosen to follow the same rule the cache already
applies to itself rather than invent a second one, per the task's own framing — `open_for_build`
always deletes-and-recreates the base region store from scratch, so a crash mid-stage leaves a
partial base store, but the *next* build overwrites it entirely rather than resuming from it; nothing
ever reads a half-written base store as "the build". Resumability lives entirely in the terrain
*cache* (`terrain_cache/`), which already tracks per-tile completion independently via
`write_tile_features`/`mark_build_complete` — unaffected by this change, since it was already
per-tile. This is the same tradeoff `build.pipeline`'s OSM/road/junction streaming stages made
earlier (see their own comments), not a new pattern.

**Measured before/after** (real Syria SRTM tiles, `data/raw/dem/syria-full`, read-only from the main
checkout — no full-theatre build run):

- 27 real tiles sampled across the full theatre grid, streamed through the new `on_tile_features`
  callback (nothing retained across tiles, as the real pipeline now does): peak RSS **plateaus at
  1752.8 MB** after the third tile (the one with the largest single-tile feature count, 31,024) and
  stays flat through to 293,331 cumulative features — it does not grow further as more tiles are
  processed. `performance.md`'s own old-code numbers at a comparable cumulative-feature count
  (218,162 features -> 5.33 GB, linear in cumulative count) predict roughly 6-7 GB at this run's
  scale; the new code holds flat at 1.75 GB. Peak memory is now bounded by the largest single tile's
  own feature set, not by cumulative theatre feature count — confirming the fix.
- A new test, `test_ingest_terrain_streams_one_call_per_tile_not_one_theatre_wide_call`, asserts the
  streaming contract directly (one `on_tile_features` call per tile, both for a fresh build and a
  warm whole-build cache hit) rather than relying only on the memory measurement.

**Item 2: O(N) Chaikin deviation check.** `_chaikin_smooth_with_support` tracks, for every output
point, the inclusive `(lo, hi)` range of *original* point indices whose convex combination produced
it — a Chaikin point's support can only grow by merging its two parents' ranges each pass, so at
`DEFAULT_CHAIKIN_ITERATIONS=4` the window stays a handful of points wide regardless of line length.
`_smooth_for_storage` now checks each smoothed point against `distance_point_polyline(point,
points[lo:hi+1])` — its own local window — instead of the whole original polyline, turning the
deviation check from O(line_length^2) into O(line_length). `_chaikin_smooth` itself (and its existing
tests) is untouched; the new function is a separate implementation `_smooth_for_storage` calls
instead.

Checking a window ⊆ the full polyline can only ever report a distance ≥ the true whole-polyline
minimum (fewer candidate segments to minimize over), never less — so this can only make the
half-cell fallback trigger in cases the full scan would also have triggered, never accept a smoothing
the full scan would have rejected. Empirically verified rather than just argued: re-ran both the
old (full-scan) and new (windowed) deviation check over every real traced line from the acceptance
window (588 lines) and separately over every real traced line from the heaviest profiled tile,
N35E036 (11,104 lines at this script's trace settings) — **zero mismatches** in either case; the
windowed check never changed a single line's accept/fallback decision or its smoothed geometry on
real data.

**Measured timing**: N35E036 (performance.md's own reference tile, 12,059 lines, previously 43.8s
total tile time with `distance_point_polyline`/`_smooth_for_storage` at 92%) now completes in
**6.87s** end to end (non-profiled). `cProfile` on the same tile shows `distance_point_segment` calls
dropped from 30.8M to ~3.1M and `_smooth_for_storage`'s own cumulative time from 40.2s to ~8s (profiler
overhead included). Re-running the same 27-tile theatre-wide sample used for the memory measurement
(which already includes this fix) gives **6.46s/tile average**, extrapolating to **~14.1 minutes for
a full 131-tile Syria build** — down from `performance.md`'s pre-fix ~25-minute estimate.

**Acceptance window unchanged.** `tools/inspect_terrain.py --srtm-dir <real syria-full>
--center -5000,15000 --radius-km 8` (same command `review.md` used) still reports **299 ridge / 289
valley lines, longest 7.18 km / 7.70 km**, and the rendered PNG is still byte-identical (same MD5) to
the committed `data/renders/coastal-hills-geomorphons.png`. Note this tool calls `terrain.geomorphons`/
`terrain.skeleton`/`terrain.features.component_from_trace` directly and never exercises
`_smooth_for_storage` or `ingest_terrain` — it was unaffected by construction, which is exactly why
the separate direct smoothed-geometry comparison above (588 + 11,104 real lines, zero mismatches) is
the actual evidence item 2 preserves geometry, not just this render.

### Checks (re-run after the performance fix)

- `ruff format --check src tests`: 116 files already formatted
- `ruff check src tests`: all checks passed
- `mypy --strict src` (run from inside `world-model/`): no issues, 71 source files
- `pytest tests -q`: **510 passed, 3 skipped** (509 baseline + 1 new streaming-contract test)
