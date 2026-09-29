### Implementation Summary

Stages 1 and 2 of `plans/terrain-feature-probing/plan.md` only (Stages 3-5 out of scope, not
started). Base: `feature/terrain-landform-features` tip `63916e1`.

**Stage 1 (mechanism)**: the terrain-semantics (ridge/valley) stage in `build.pipeline.build_region`
was nested inside the DCS-probe branch, so it had never once run against an SRTM-sourced elevation
grid -- the grid every real `syria-full`-scale build actually supplies. Un-gated: it now runs
whenever any `elevation` grid was inserted (SRTM-only, probe-only, or probe-over-SRTM), attributed
to whichever `Source` row actually produced that grid via a newly tracked `elevation_source_id`
(SRTM is inserted first and overwritten by probe if both are supplied, matching the existing
"probe wins as most recent" `store.reader` behaviour the module docstring already described).

**Stage 2 (calibration)**: a region-scoped test build (`latakia-20km`, real SRTM `.hgt` tiles, no
theatre-wide run per the execution-boundary rule) swept four spacings (1000/500/250/100m) x several
curvature thresholds each, mirroring M6 Stage 2's own method. Result: `DEFAULT_SRTM_GRID_SPACING_M`
raised 1000.0 -> 500.0; curvature threshold and min-cell-count left unchanged (they transfer from
M6's DCS-probe tuning to SRTM data essentially unmodified, confirmed rather than assumed). Full
tables and the checkerboard-ceiling finding are in the dated research note.

### Files Changed
- `world-model/src/build/pipeline.py` — un-gated the terrain-semantics stage from the probe branch
  (Stage 1 commit); raised `DEFAULT_SRTM_GRID_SPACING_M` 1000.0 -> 500.0 (Stage 2 commit, separate
  per "mechanism and calibration never share a commit").
- `world-model/tests/test_pipeline_build_region.py` — updated
  `test_build_region_srtm_tile_paths_becomes_the_primary_elevation_grid`: its old assertion
  (`terrain_skipped is True` after an SRTM-only build) encoded exactly the gate Stage 1 removes.
  The fixture's flat, uniform-value tile correctly yields zero ridge/valley features once the stage
  runs, which the test now asserts instead.
- `world-model/docs/M7_RUN_INSTRUCTIONS.md` — updated the Stage 2 row-count sizing note to describe
  the new 500m default (was written describing 1000m as default, 500m as an alternative).
- `world-model/tools/build_world_model.py` — updated `--srtm-grid-spacing-m`'s docstring default
  mention (1000m -> 500m).
- `world-model/research/2026-09-29-terrain-feature-probing-spacing.md` — new dated research note:
  full sweep tables for all four spacings, the checkerboard-ceiling-is-spacing-invariant finding,
  the decision and why, disk-cost sizing, and confirmation that provenance distinguishability
  (SRTM vs. probe) already works via existing `source_id` joins with no schema change.

### Tests Added
No new test files. One existing test's assertions were updated (see above) to match the now-correct
un-gated behaviour; every other test in the suite was unaffected (`add_probe_chunk`'s own
`terrain_skipped` assertions, in `test_probe_chunk_pipeline.py`, exercise a separate M8 function
untouched by this change).

### Checks (world-model/)
- ruff format --check: pass
- ruff check: pass
- mypy --strict (`src`): pass, 62 source files
- pytest -q: 475 passed, 3 skipped (matches the stated baseline exactly; one existing test's
  assertions changed, none added or removed)

### Notable Discoveries
- **The checkerboard-noise ceiling M6 documented (2026-09-05) is spacing-invariant, not just
  threshold-invariant.** The plan anticipated a "process fine, store coarse" split as the likely
  outcome of Stage 1's spacing investigation (with sizing figures already laid out for exactly that
  case). The real finding was the opposite: finer processing spacing (250m, 100m) reproduces the
  same checkerboard noise pattern at higher cell density rather than resolving cleaner landmark
  lines at any threshold tested, so there is no benefit to decoupling processing spacing from
  storage spacing here. One grid, 500m, does both jobs. This is worth flagging because it directly
  contradicts the plan's stated expectation, not just fills in an unknown it left open.
- **500m SRTM data cross-validates almost exactly against M6's original DCS-probe-500m tuning**
  (10 ridge + 11 valley components vs. M6's 12 + 12, same region, same threshold) — a real,
  independent confirmation that DCS elevation and SRTM agree closely enough at this spacing that no
  new threshold search was actually needed, consistent with M6's own Finding 3 (DCS-vs-SRTM
  elevation agreement within ~30m).
- 1000m's failure mode is concrete, not just "coarse": valley components vanish entirely by
  threshold 30 in the sweep, well before the per-cell checkerboard signal has cleared — there is no
  threshold at 1000m that recovers both ridge and valley features together over this test region.
- Provenance distinguishability (SRTM-derived vs. probe-derived ridge/valley rows) required no code
  change — confirmed against a real built `.sqlite` that `source_id` already joins to a `source` row
  naming which grid produced it (`"SRTM .hgt tiles"` vs. `"terrain_probe (...)"`).
