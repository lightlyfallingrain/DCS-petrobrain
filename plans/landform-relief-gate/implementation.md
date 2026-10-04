### Implementation Summary

Two defects fixed in the geomorphons ridge/valley pipeline (`WM-B6`), found by checking the
user's real `syria-full` build against his own acceptance criteria
(`plans/terrain-feature-probing/explore-notes.md`):

1. **No relief gate.** `terrain.features.filter_by_relief` drops any traced line whose own
   `elevation_range_m` span is below `DEFAULT_MIN_RELIEF_M = 50.0` m -- the floor of the user's
   "~50-150 m, maskable-behind" band. Wired into `build.ingest_terrain._process_tile`, applied
   before `to_stored_features`, so gated lines never reach the cache or the store. `min_relief_m`
   is a new `ingest_terrain`/`TerrainCacheMeta` knob (default `DEFAULT_MIN_RELIEF_M`).
2. **~16x-denser-than-DEM-supports stored geometry.** `terrain.features._decimate_for_storage`
   runs Douglas-Peucker (`geometry.simplify_polyline`, already in this codebase, used for OSM
   polygon simplification) over the Chaikin-smoothed line, verifying every real sampled point
   still sits within `_smooth_for_storage`'s existing half-cell deviation cap before accepting the
   decimated result -- falling back to the full smoothed geometry otherwise. `decimation_tolerance_
   fraction` (default `DEFAULT_DECIMATION_TOLERANCE_FRACTION = 0.25`, a quarter grid cell) is
   likewise a new knob threaded through `ingest_terrain`/`TerrainCacheMeta`.

Both knobs are tracked in `TerrainCacheMeta`'s invalidation key, and `EXTRACTOR_VERSION` was
bumped `1 -> 2` as the stated, explicit signal for "this pipeline change alone would change a
cache's output" -- on top of (not instead of) the fact that an old cache's `meta` table is simply
missing these two keys, which `terrain_cache.reader.load_cache_meta` already treats as "no stored
identity" and forces a full rebuild on its own.

### A real bug found and fixed during verification, not just the two named defects

The first working version of `_decimate_for_storage` checked each original sampled point only
against the *one* decimated segment its Chaikin support window pointed at (via a windowed
`distance_point_segment` call, mirroring `_smooth_for_storage`'s own windowed check). Verified
against real `syria-full` SRTM data, that check was wrong: it measured deviations of 70-155 m
(ridge fragment windows, real coordinates) where the true distance from the *whole* decimated
polyline (`distance_point_polyline`, which scans every segment) was 15-30 m. A point near a real
turn in a traced skeleton line can be far from the one segment its support window happens to name
while sitting close to a *different* decimated segment -- a windowed single-segment check cannot
see that, only a whole-polyline check can. Caught because the fixed theatre-build output's point
density barely dropped (92.5% of real lines fell back to full Chaikin density) when it should have
dropped by ~37x -- a number worth checking, not trusting. Rewritten to check every original point
against the whole decimated polyline directly: O(len(original_points) * len(decimated)), cheap
because the decimated line is always short -- far below the O(line_length^2) cost `plans/landform-
geomorphons/performance.md` already ruled out for the smoothed line. A real-data regression test
(`test_decimate_for_storage_checks_the_whole_decimated_line_not_one_segment`, real points from
`N35E035.hgt`) pins this down.

### Files Changed

- `world-model/src/terrain/features.py` -- `DEFAULT_MIN_RELIEF_M`, `filter_by_relief` (defect 1);
  `DEFAULT_DECIMATION_TOLERANCE_FRACTION`, `_decimate_for_storage` (defect 2, using `geometry.
  simplify_polyline`/`distance_point_polyline`); `_smooth_for_storage` now decimates after
  smoothing; `to_stored_features` gained a `decimation_tolerance_fraction` parameter.
- `world-model/src/build/ingest_terrain.py` -- `EXTRACTOR_VERSION` bumped `1 -> 2` (documented
  inline); `_process_tile`/`ingest_terrain` gained `min_relief_m`/`decimation_tolerance_fraction`
  parameters (defaults from `terrain.features`); `filter_by_relief` applied before
  `to_stored_features` in `_process_tile`.
- `world-model/src/terrain_cache/models.py` -- `TerrainCacheMeta` gained `min_relief_m`/
  `decimation_tolerance_fraction` fields, added to `_INVALIDATION_KEY_FIELDS`.
- `world-model/src/terrain_cache/schema.py` -- `META_FIELDS` gained the same two keys.
- `world-model/src/terrain_cache/reader.py` -- `_META_TYPES` gained the same two keys (both
  `float`).
- `world-model/tools/inspect_terrain.py` -- rewritten to apply the real stored pipeline (relief
  gate + `to_stored_features`'s smoothing/decimation) before rendering, instead of drawing the raw
  traced skeleton -- the render now shows exactly what a real build stores. Reports per-kind line
  counts, how many lines the relief gate dropped, and the raw/Chaikin/stored point-count chain.
  New `--min-relief-m`/`--decimation-tolerance-fraction` flags (defaults match production).
- `world-model/tests/test_terrain_features.py` -- new tests for `filter_by_relief` and
  `_decimate_for_storage` (including the real-data regression above); `test_smooth_for_storage_
  decimates_a_straight_crest_down` extends the existing smoothing coverage to the new decimation
  step.
- `world-model/tests/test_ingest_terrain.py` -- 7 existing calls gained an explicit
  `min_relief_m=0.0` (the shared `_write_tile` fixture traces a ridge that is flat *along its own
  length* by construction -- varies only across columns -- so at the new default `min_relief_m`
  it is correctly gated out; these tests are about other behaviour and isolate themselves from the
  new gate). New tests: the default gate rejecting that same fixture end-to-end, and a cache
  invalidation test for a `min_relief_m` change.
- `world-model/tests/test_terrain_cache.py` -- `_meta()` fixture helper gained the two new keys.
- `world-model/data/renders/{coastal-hills,baalbek,palmyra}-relief-gate.png` -- acceptance renders
  (see below), produced from the real `data/raw/dem/syria-full` tiles, read-only from the main
  checkout's filesystem (never copied/committed as data).

### Tests Added

- `test_filter_by_relief_drops_components_below_threshold` / `_keeps_components_at_or_above_
  threshold` / `_default_matches_documented_floor` -- the relief gate's threshold behaviour,
  including the exact Baalbek-adjacent 22 m case from the task brief.
- `test_decimate_for_storage_reduces_point_count_on_a_straight_run` -- decimation actually reduces
  point count on a near-straight line.
- `test_decimate_for_storage_never_exceeds_the_deviation_cap` -- the fallback path (a sharp zigzag
  with a tiny cap) returns the undecimated geometry.
- `test_decimate_for_storage_checks_the_whole_decimated_line_not_one_segment` -- the real-data
  regression for the windowed-check bug described above.
- `test_smooth_for_storage_decimates_a_straight_crest_down` -- `_smooth_for_storage`'s end-to-end
  smoothing-then-decimation path preserves the half-cell deviation guarantee.
- `test_ingest_terrain_default_relief_gate_drops_a_flat_along_crest_ridge` -- the gate applied at
  the `ingest_terrain` level, end to end, at the production default.
- `test_ingest_terrain_relief_gate_change_invalidates_the_whole_cache` -- `min_relief_m` is a
  tracked cache-identity field.

### Checks

(world-model/ -- the only subproject touched)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy --strict src` (run from inside `world-model/`): pass, 71 source files
- `pytest tests -q`: **539 passed, 3 skipped** (worktree baseline on `main`/`c8cfd18` was 530
  passed, 3 skipped -- the 9 new tests above account for the difference)

### Real-data verification (read-only against the user's actual builds/data; no full-theatre
build run, per the project's execution-boundary rule)

**Defect 1, measured directly against `world-model/data/world-model/syria-full.sqlite` (8.1 GB,
read-only, not modified):**

- `ridge=700142, valley=740255` -- exact match to the task's own figures.
- `>=50 m` keeps **234,799** (ridge 122,567 + valley 112,232) -- exact match to the task's stated
  16.3%.
- `>=100 m` keeps **92,820** (ridge 48,829 + valley 43,991) -- exact match to the task's stated
  6.4%.
- The specific Baalbek case the task names (nearest valley ~22 m of relief, elevation range
  1161.3-1183.4 m) is confirmed present in the real data and is exactly the kind of row the 50 m
  gate removes.

**Defect 2, measured two ways:**

- A 3,000-line random sample of real `>=50 m`-relief ridge/valley geometry from the *existing*
  (pre-fix) `syria-full.sqlite` -- i.e. geometry already at today's Chaikin-only density --
  decimated with the fixed algorithm: **20,295,778 -> 555,538 bytes, 36.5x reduction**, zero
  points exceeding the half-cell cap.
- A real region-scoped rebuild of `latakia-20km` (9 real SRTM tiles from `data/raw/dem/syria-full`,
  full pipeline via `tools/build_world_model.py`, not a synthetic fixture): stored ridge/valley
  geometry came out **36.7x smaller than the Chaikin-only (pre-decimation) point count** would have
  been (ridge median 5 points/line, valley median 6, down from a Chaikin-only median in the
  hundreds). Direct re-derivation of tile `N35E035`'s own 979 real ridge/valley lines confirmed
  **worst real deviation from the original sampled points: 32.3 m**, safely under the 45 m
  (half-cell) cap.

**Achieved max deviation bound, stated plainly: 32.3 m measured, 45.0 m cap, on real production
geometry** -- not a synthetic case.

### Theatre-wide extrapolation (explicitly extrapolated, not measured -- no full-theatre build run)

- **Feature count**: 234,799 ridge+valley features theatre-wide is a **direct measurement** (SQL
  query against the real store's existing `tags_json.elevation_range_m`), not an extrapolation --
  the relief gate's logic is a pure function of data already stored.
- **Store size**: extrapolated from the measured ~36.5x geometry-byte reduction and the 16.3%
  row-count retention. Current `feature` table is ~7.98 GB, of which ridge+valley geometry
  (`geom_json`) alone is ~5.72 GB (ridge 2.65 GB + valley 3.06 GB); the remaining ~2.26 GB is other
  kinds (roads, settlements, water, landcover, named places), untouched by this fix. New
  ridge+valley geometry extrapolates to **~25-45 MB** (two independent estimates: 5.72 GB x 0.163 /
  36.7 ~= 25 MB; per-line average byte size from the 3,000-line sample x 234,799 kept features ~=
  43 MB). Expected new `feature` table **~2.3 GB**, expected new store size **~2.4-2.5 GB** (down
  from 8.1 GB). The terrain cache (currently 7.4 GB, fully invalidated by this change) should land
  at a similar order of magnitude to the new `feature` table, since it holds the same gated/
  decimated geometry.

### Render paths (judge by eye, per this project's standing method for terrain decisions)

- `world-model/data/renders/coastal-hills-relief-gate.png` (centre `-5000,15000`, 8 km) -- ridge
  148 lines (151 dropped by the gate), valley 130 lines (159 dropped), 36.7x point reduction.
- `world-model/data/renders/baalbek-relief-gate.png` (centre `-114453.8,25280.8`, 20 km) -- ridge
  297 lines (611 dropped), valley 282 lines (672 dropped), 38.8x point reduction. **The Bekaa
  floor (the large flat basin) is completely clean of ridge/valley lines** -- every detection sits
  on the bordering slopes, visible by eye in the render.
- `world-model/data/renders/palmyra-relief-gate.png` (centre `-54775.0,217141.7`, 20 km) -- ridge
  107 lines (698 dropped), valley 59 lines (986 dropped), 36.7x point reduction. **Long isolated
  ridge chains crossing flat desert clearly survive** (a continuous ~6+ km diagonal chain visible
  through the middle of the render), confirming the gate removes noise without removing real
  isolated relief.

Both falsifiable checks the task named hold: **no Bekaa valley, Palmyra chains survive.**

### Notable Discoveries

- **The `_write_tile` test fixture in `test_ingest_terrain.py` traces a ridge that is flat along
  its own length by construction** (elevation varies only across columns, the crest itself sits at
  one constant height) -- a real limitation of using a linear-slope synthetic tile, not a defect in
  the relief gate. At the production default it is correctly gated to zero features, which broke 5
  existing tests until they were given `min_relief_m=0.0` to isolate them from this unrelated gate.
- **The windowed deviation check bug (see above) would have shipped a technically-safe but
  functionally-useless decimation** -- it never violated the cap (it was *more* conservative than
  necessary, not less), so nothing in the deviation guarantee itself would have caught it; only
  comparing the real built output's density against the expected ~37x reduction did. Recorded as a
  reminder that a safety check passing is not the same as the feature working.
- **`inspect_terrain.py`'s own density report had a labelling bug** during verification (comparing
  raw pre-Chaikin cell count to final stored count, understating the real reduction a decimation
  step achieves) -- fixed to report raw / Chaikin-expected / stored as three distinct numbers.
