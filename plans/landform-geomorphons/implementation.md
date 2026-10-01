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
