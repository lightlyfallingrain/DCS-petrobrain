### Implementation Summary

## Stage 0 — Region model generalization + theatre census (2026-09-05)

Generalized `build.region.RegionDefinition` from a single square `half_extent_m` to
independent rectangular `half_extent_x_m`/`half_extent_z_m` (Locked Decision 2), registered the
new `syria-full` region from the confirmed padded bbox, and ran the existing `.routes` walk
against the whole (unclipped-in-effect) `syria-full` bbox to get real full-theatre road counts.
No `.sqlite` store was built -- Stage 0 is region-model + census only, per the plan's Execution
boundary.

### Files Changed

- `world-model/src/build/region.py` -- `RegionDefinition` gains `half_extent_x_m`/
  `half_extent_z_m` (was `half_extent_m`); added a `RegionDefinition.square(...)` convenience
  classmethod for the equal-extents case; `to_wgs84_envelope` computes corners from the two
  independent extents. `latakia-20km`/`gemerek-20km` re-registered via `.square(...)`, behavior
  unchanged. Added `syria-full`: centre `(-38239.9, 35166.9)`, half-extents `(413672.3,
  385608.0)` m, from `world-model/research/2026-09-05-m7-syria-theatre-extent.md`'s confirmed
  padded bbox (x in [-451,912.2, 375,432.4], z in [-350,441.1, 420,774.9], ~827.3 x 771.2 km).
- `world-model/src/store/models.py`, `schema.py`, `writer.py`, `reader.py` -- the persisted
  `Region` record's `half_extent_m` column split into `half_extent_x_m`/`half_extent_z_m`.
  `SCHEMA_VERSION` bumped 1 -> 2 (an incompatible DDL change, per `schema.py`'s own
  "bumped whenever the DDL changes incompatibly" convention). This is not a live-data migration
  concern: every `.sqlite` is always rebuilt from `data/raw/`, never patched in place, and no
  existing store is under version control.
- `world-model/src/build/ingest_towns.py`, `ingest_beacons.py`, `ingest_osm.py`,
  `ingest_roadnet.py` -- each module's `_within_region`/bbox-filter logic and public ingest
  function signature now take independent `half_extent_x_m`/`half_extent_z_m` instead of one
  `half_extent_m`, applying the x half-extent to the x axis and the z half-extent to the z axis.
  Square-region behavior is unchanged (callers still pass equal values for `latakia-20km`/
  `gemerek-20km`); this is what makes the generalization real for `syria-full`, not just a
  renamed field.
- `world-model/src/build/pipeline.py` -- `probe_grid_for_region` now derives `n_rows` from
  `half_extent_x_m` and `n_cols` from `half_extent_z_m` (matching `ElevationGrid`'s `(row, col)`
  -> `(origin_x + row*spacing, origin_z + col*spacing)` convention, where row varies along x and
  col along z); `build_region`'s calls into each `ingest_*` function and its `Region(...)`
  construction updated for the two-extent signature.
- `world-model/tools/analyze_m5_stage4_validation.py`, `measure_m5_stage5_perf.py` -- updated
  their own `half_extent_m` references (not covered by the mandated check commands, since
  `tools/` isn't in `ruff`/`mypy`'s checked paths, but left broken otherwise since they read
  `RegionDefinition`/the `region` table directly).
- `world-model/tests/test_region.py` (new) -- covers the generalization directly (see Tests
  Added).
- `world-model/tests/test_describe_position.py`, `test_ingest_beacons.py`,
  `test_pipeline_probe_grid.py`, `test_roadnet_rn4.py`, `test_store_roundtrip.py` -- mechanical
  call-site updates for the renamed/split field (kwarg/positional-arg changes only, no test
  intent changed).
- `world-model/tools/census_m7_stage0_roadnet.py` (new) -- measurement-only script: walks the
  real `Syria.routes` via `ingest_roadnet` (unchanged) against `syria-full`'s bbox and reports
  route counts. Builds no store.
- `world-model/research/2026-09-05-m7-stage0-roadnet-census.md` (new) -- dated results note for
  the census run (see Notable Discoveries below for the headline numbers).

### Tests Added

- `test_square_via_classmethod_sets_both_extents_equal` -- `RegionDefinition.square(...)` sets
  both extents from one `half_extent_m`.
- `test_square_region_envelope_matches_prior_square_only_behavior` -- **regression**: the
  generalized rectangular `to_wgs84_envelope` produces byte-identical corners, for a square
  region, to what the old square-only `centre +/- half_extent_m` formula would have produced.
- `test_latakia_20km_region_is_still_registered_as_a_square` -- pins that the real registered
  `latakia-20km` region still has equal x/z half-extents after the generalization.
- `test_rectangular_region_envelope_is_wider_on_its_longer_axis` -- a synthetic non-square
  region (x half-extent 10x the z half-extent) produces a WGS84 envelope decisively wider on
  the axis DCS x maps to (confirmed empirically: DCS x tracks latitude, z tracks longitude for
  Syria's tmerc projection) than the other -- not a square envelope forced from one extent.
- `test_syria_full_is_registered_with_the_confirmed_padded_bbox` -- pins `syria-full`'s
  centre/half-extents (and derived min/max bbox, footprint width) against the confirmed padded
  bbox numbers in the research note.

### Checks

- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass
- `mypy world-model/src` (`--strict` per `pyproject.toml`): pass, 38 source files
- `pytest world-model/tests -q`: pass, 165 passed

### Notable Discoveries

- **`.routes` full-theatre census result**: running `tools/census_m7_stage0_roadnet.py` against
  the real 2.25 GB `Syria.routes` with `syria-full`'s bbox gives `routes_found_whole_file =
  routes_in_region = 14,833` -- **every single route in the file falls inside the padded
  bbox**, and only **2 of 14,833** routes are flagged `clipped` (a point outside the bbox). This
  means the confirmed extent + 30 km/side padding is comfortably generous, not a tight fit, and
  that Stage 1's planned "remove the bbox clip for full-theatre roadnet ingest" will have no
  observable effect on road counts specifically (already noted in the new research note, so
  Stage 1 doesn't mistake "no count change" for a bug). `sync_loss_events` (220, ~1.48%) exactly
  matches M5's previously-measured whole-file rate, confirming it's a `.routes`-parser property
  independent of region bbox. Wall time (431.4 s) matches M5 Stage 5's 446 s baseline despite
  materializing full `StoredFeature` objects for virtually the whole file this time (Latakia's
  20x20 km clip discarded almost everything after the walk; `syria-full` keeps almost
  everything) -- no perf regression from the generalization.
- **The plan's own complexity estimate for the region-model change ("a small dataclass change
  plus updating the two call sites that compute corners/envelope") undercounted the real
  surface area.** Because `RegionDefinition.half_extent_m` is read directly (not through a
  shared helper) in `ingest_towns.py`, `ingest_beacons.py`, `ingest_osm.py`,
  `ingest_roadnet.py`, `pipeline.py`, and the persisted `store.models.Region`/`schema.py`/
  `writer.py`/`reader.py`, keeping `mypy --strict` clean after the rename required updating all
  of those, not just two call sites. This was necessary for correctness (not scope creep) --
  flagging it since a future session generalizing another shared field in this codebase should
  expect the same "many direct readers of one field" pattern rather than assuming a narrow
  blast radius from the plan's own estimate.
- **`world-model/docs/M7_FULL_THEATRE_RUN.md` (the user-facing Windows run-instructions doc) is
  intentionally not written yet.** It documents staging SRTM tiles and running the spot-check
  probe mission, neither of which exists until Stage 2's SRTM-primary elevation wiring lands --
  writing it now would either be empty scaffolding or get rewritten wholesale once Stage 1/2
  land. Deferred to whichever stage actually wires up the full-theatre build CLI path, not
  dropped.
- Two commits landed on this branch: one carrying architect/investigator artifacts that were
  already staged in the working tree but not yet committed from earlier in this session (the
  plan itself, both investigator research notes, the Kola distortion probe tool, investigator
  agent-memory updates), and a second with this Stage 0 implementation -- kept separate since
  neither this implementer session nor its commit authored the first set.

## Stage 1 — DCS-native vector layers, no elevation (2026-09-05)

Wired `build.pipeline.build_region` and `tools/build_world_model.py` to support building
`syria-full` (or any region) without an OSM cache, added a small full-theatre validation
module (`build.validate`) and its CLI (`tools/validate_m7_stage1.py`), extended
`tests/control_points.py` with a fourth scattered point (Aleppo), and wrote the required
"Execution boundary" run-instructions deliverable. Per the plan's Execution boundary, **no real
`syria-full.sqlite` was built** -- everything below was verified against small/synthetic
fixtures and the existing `latakia-20km`-scale test store, never the real 2.25 GB
`Syria.routes` or the real `towns.lua`/`beacons.lua`.

### Files Changed

- `world-model/src/build/pipeline.py` -- `build_region`'s `osm_cache_path` parameter changed
  from required (`Path`) to optional (`Path | None`), mirroring the existing `routes_path`/
  `probe_output_path` "absent is skipped, not an error" pattern: the OSM-insert/ingest block is
  now guarded by `if osm_cache_path is not None and osm_cache_path.exists()`, with a new
  `BuildReport.osm_skipped: bool` field set in the `else` branch. This was necessary because M7
  drops OSM from scope entirely (plan clarification 2) and `syria-full` has no Overpass cache
  at all -- unlike `routes_path`/`probe_output_path`, which are optional only because a fresh
  checkout might not have them staged yet, `osm_cache_path` for `syria-full` will never exist,
  by design, not by omission.
- `world-model/tools/build_world_model.py` -- the CLI's required-args check no longer demands
  `--osm-cache`; only `--towns`/`--beacons` are required (with defaults for `latakia-20km`).
  Added a "skipped" print line for OSM alongside the existing routes/probe skip lines, and a
  module-docstring block giving the exact `syria-full` invocation (explicit `--towns`,
  `--beacons`, `--routes`, no `--osm-cache`) plus a pointer to the new run-instructions doc.
- `world-model/src/build/validate.py` (new) -- Stage 1's validation logic: `check_road_count`
  (a real build's `road`-feature count within a tolerance band of Stage 0's real full-theatre
  census, `SYRIA_FULL_EXPECTED_ROAD_COUNT = 14_833`, from
  `world-model/research/2026-09-05-m7-stage0-roadnet-census.md`) and `spot_check_positions`
  (runs `query.describe_position` at a list of `SpotCheckPoint`s and summarizes whether a
  nearest road/settlement was found). Deliberately does not import `tests/control_points.py`'s
  `ControlPoint` -- `src/` must not depend on `tests/` fixtures; `SpotCheckPoint` is its own
  minimal type carrying only what a store-content sanity check needs (name, DCS x/z), not a
  published real-world lat/lon (that's the separate coordinate-tolerance check `describe_position`
  control-point tests already cover).
- `world-model/tools/validate_m7_stage1.py` (new) -- the CLI the run-instructions doc tells the
  user to run against their real `syria-full.sqlite`: reads real `feature` counts by `kind`
  directly via SQL, runs `check_road_count` against the real road count, runs
  `spot_check_positions` at all four `tests/control_points.py` points, and separately re-checks
  each point's `describe_position` lat/lon against its published real-world ARP (reusing
  `haversine_distance_m`). Prints one JSON report to stdout. Does not build or mutate anything
  -- read-only against an already-built store, matching `tools/analyze_m5_stage4_validation.py`'s
  established pattern.
- `world-model/tests/control_points.py` -- added a fourth control point, Aleppo International
  (OSAP), completing the plan's named Stage 1 spread ("Damascus, Aleppo, Beirut, Latakia").
  Its DCS `(x, z)` comes from `beacons.lua`'s real `airfield27_0` (ALEPPO NDB) `position` field
  (`world-model/research/2026-09-03-m5-nodes-lua-probe.txt` line 2773) rather than a fresh live
  `coord.LOtoLL` probe (no DCS access this session) -- still non-circular per M1 Finding 2,
  since the independently-published SkyVector ARP (N36°10.83'/E37°13.61') is used as the
  real-world reference, never the same beacon's own `positionGeo` field. Verified via
  `tools/report_control_point_errors.py` before committing: residual 688.7 m, comfortably
  inside the 1,500 m tolerance and consistent with the other three points' 960-1,315 m band.
- `world-model/tests/test_describe_position.py` -- added
  `test_describe_position_control_points_spread_across_theatre` (new test function; the
  existing `test_describe_position_control_point_latakia_arp` was not modified), looping the
  same non-circular tolerance-band check over all four `CONTROL_POINTS` instead of Latakia
  alone -- the "correctness checked at more than one location" coverage the plan's Stage 1
  calls for.
- `world-model/docs/M7_RUN_INSTRUCTIONS.md` (new) -- the plan's required "Execution boundary"
  deliverable for Stage 1: step-by-step instructions to stage the raw files (which, notably,
  turn out to already be locally staged on this machine -- see Notable Discoveries), run
  `build_world_model.py syria-full` with explicit paths and no `--osm-cache`, run
  `validate_m7_stage1.py`, and record the real result. Framed throughout around "this is your
  action, not something already done for you," per the plan's explicit DoD framing.

### Tests Added

- `world-model/tests/test_build_validate.py` (new) -- `spot_check_positions` finds a nearby
  road/settlement in a small synthetic store and correctly reports absence far outside
  coverage; `check_road_count` correctly buckets counts into/out of a tolerance band.
- `world-model/tests/test_pipeline_build_region.py` (new) --
  `test_build_region_rectangular_region_without_osm_cache`: a synthetic **rectangular**
  (non-square) region builds successfully with `osm_cache_path=None`, correctly clips an
  out-of-region town while keeping an in-region one, and reports every optional layer
  (`osm_skipped`, `roadnet_skipped`, `probe_skipped`, `terrain_skipped`) as skipped rather than
  erroring -- this is the exact shape of an M7 `syria-full`-style Stage 1 build.
  `test_build_region_osm_cache_path_given_but_missing_is_skipped_not_an_error`: a stale/wrong
  `--osm-cache` path degrades the same way a missing `--routes`/`--probe-output` already does.
  `parse_towns_lua`/`parse_beacons_lua` are monkeypatched (both raise `ValueError` unless given
  *exactly* 1,182/151 entries -- a real hand-written fixture file can't go through them), so
  this tests `build_region`'s wiring, not those parsers (already covered elsewhere).
- `test_describe_position_control_points_spread_across_theatre` (in
  `test_describe_position.py`) -- see Files Changed above.

### Checks

- `ruff format --check world-model/src world-model/tests`: pass (66 files)
- `ruff check world-model/src world-model/tests`: pass
- `mypy --strict world-model/src`: pass, 39 source files
- `mypy --strict` on the two touched/new `tools/` files individually (not part of the mandated
  command, but checked per project convention for new tool files): pass
- `pytest world-model/tests -q`: pass, 173 passed (was 165 after Stage 0; +8 new tests: 4 in
  `test_build_validate.py`, 2 in `test_pipeline_build_region.py`, 1 new control point pulling in
  no new test count by itself, 1 new `describe_position` test)

### Notable Discoveries

- **The raw files Stage 1 needs are already locally staged on this Mac** -- `world-model/data/
  raw/dcs/syria/map/towns.lua`, `.../beacons.lua`, and `.../roads/Syria.routes` (2,251,462,776
  bytes) all already exist from M5/Stage 0's work, confirmed by direct `ls` before writing the
  run-instructions doc (read-only check, no content read, no build run). Since these are
  already whole-theatre files (not region-clipped -- M5's finding, reconfirmed by Stage 0's
  census), **Stage 1's real build may not need any new Windows/WSL round-trip at all**, unlike
  what a from-scratch reading of the plan's "Windows DCS machine" framing might suggest. The
  run-instructions doc says this explicitly rather than assuming a fresh extraction is needed.
- **`build_region`'s OSM-required-ness was a real, previously-invisible blocker for M7.** Before
  this stage, `osm_cache_path: Path` was a required positional parameter with no absence
  handling, unlike `routes_path`/`probe_output_path` (already optional since M5). Since M7
  explicitly drops OSM (clarification 2) and `syria-full` has no cache file to point at, the
  CLI as it stood before this change would have hard-required a nonexistent/inapplicable file
  for the exact build the plan calls for. This wasn't mentioned explicitly in the plan's
  "Affected Modules" list (which focuses on SRTM/elevation wiring for Stage 2) -- flagging it
  as a real gap this stage had to close, not scope creep.
- **No live-DCS-probe path existed this session for a fresh Aleppo `coord.LOtoLL` control
  point** (matching the plan's own Risks note that Kola's projection params are similarly
  unverified live). Used `beacons.lua`'s already-decoded, already-DCS-authoritative
  `airfield27_0` position instead, cross-checked via `WebSearch`/`WebFetch` against SkyVector
  for the independent real-world ARP -- functionally equivalent to the existing control points
  in every way that matters for non-circularity (DCS-native x/z paired with an independently
  published lat/lon), just sourced from a static Lua file already on disk rather than a fresh
  live-mission run. Worth noting for any future control-point additions: `beacons.lua`'s
  `position` field is a legitimate, already-decoded source for this, not just `positionGeo`.

## Stage 2 — Elevation/surface-type grid at full theatre, SRTM-primary (2026-09-05)

Made SRTM the store's primary `elevation` grid source (`provenance="srtm"`), repurposed the
existing DCS live-probe path (`elevation_probe.lua`, `elevation.dcs_grid.parse_probe_output`)
to a scattered spot-check validation report rather than a full-grid ingest, and closed the
provenance gap `query.describe.describe_position` had been carrying since M5 (`elevation.source`/
`surface_type.provenance` were hardcoded `"dcs"` regardless of what actually produced the grid).
Per the plan's "Execution boundary": no real SRTM tile set was run against the real `syria-full`
bbox, and no real DCS live-mission probe was run -- everything below is verified against small/
synthetic fixtures, mirroring Stage 0/1's pattern. **`src/terrain/` was not touched** and M6's
ridge/valley classifier was not rerun anywhere in this stage, per the plan's lockout.

### Files Changed

- `world-model/src/store/schema.py` -- added a `grid.provenance TEXT` column; `SCHEMA_VERSION`
  bumped 2 -> 3 (an incompatible DDL change, per the module's own convention -- no live-data
  migration concern, every `.sqlite` is always rebuilt from `data/raw/`).
- `world-model/src/store/models.py` -- `ElevationGrid`/`SurfaceGrid` gain a required (no
  default) `provenance: str` field, positioned before `stats` so every existing positional-safe
  ordering stays valid. Required, not defaulted, so a caller cannot silently skip tagging a
  grid's source -- mirrors `StoredFeature.provenance`'s existing "never a bare collapsed value"
  contract, just for grids instead of features.
- `world-model/src/store/writer.py` (`insert_grid`), `reader.py` (`_GridMeta`,
  `_load_grid_meta`, `load_full_grid`) -- read/write the new column; `reader.py` gains a new
  public `grid_provenance(conn, grid_kind) -> str | None` accessor, mirroring the existing
  `grid_spacing_m` shape, so callers don't need to load the whole grid matrix just to learn its
  source.
- `world-model/src/elevation/dem.py` -- new `select_tile(tiles, lat, lon) -> SrtmTile | None`:
  linear-scan lookup for whichever of a list of tiles covers a given point. A full theatre needs
  many `.hgt` tiles (each a fixed 1x1 degree by format), so any full-theatre grid or
  multi-location report needs per-point tile selection, not one shared tile/origin -- this is
  the shared primitive both new modules below build on. Exported from `elevation/__init__.py`.
- `world-model/src/build/ingest_srtm.py` (new) -- `ingest_srtm_grid`: resamples one or more
  `SrtmTile`s onto the regular DCS-metre grid `build.pipeline.probe_grid_for_region` already
  defines for the (now-repurposed) probe grid, producing the primary `ElevationGrid`
  (`provenance="srtm"`, constant `GRID_PROVENANCE_SRTM`). A cell with no covering tile or a void
  sample is left `None` and counted in `SrtmIngestStats.points_void_or_uncovered` -- absence
  reported as absence, never guessed, matching every other ingest module's contract. Runs to
  completion rather than raising on a single bad cell, since a full-theatre grid should tolerate
  imperfect SRTM coverage at some cells.
- `world-model/src/build/ingest_probe.py` -- added `GRID_PROVENANCE_DCS_PROBE = "dcs_probe"`
  and passed it into both `ElevationGrid`/`SurfaceGrid` constructions -- the module's own
  behavior is otherwise unchanged (still parses `terrain_probe_*.lua` output into a full grid;
  still valid for `latakia-20km`-scale builds), it just now tags what it always implicitly was.
- `world-model/src/build/validate.py` -- added `ElevationAlignmentPoint`/
  `ElevationAlignmentReport`/`compare_probe_to_srtm`: generalizes M4's single-region Gemerek
  delta check (mean +13.89m, stddev 28.02m) to a scattered, multi-tile point set. Takes
  `elevation.dcs_grid.parse_probe_output`'s output (`elevation_probe.lua`'s existing,
  unmodified spot-check format -- plain named points, not the grid-indexed `r{row}c{col}`
  format `parse_terrain_probe_output` needs) plus a list of `SrtmTile`s, and reports per-point
  deltas plus mean/median/stddev/min/max. Deliberately independent of `sqlite3`/the built
  store -- answers "does DCS agree with SRTM here", not "what's in the store".
- `world-model/src/build/pipeline.py` -- `build_region` gains `srtm_tile_paths: list[Path] |
  None` and `srtm_grid_spacing_m: float = DEFAULT_SRTM_GRID_SPACING_M` (1000m default,
  independent of the pre-existing single-tile `srtm_tile_path` delta-stats parameter, which is
  untouched). The new SRTM-ingest stage runs *before* the existing probe/terrain-semantics
  block in execution order (though logged as stage "5" vs. probe's "6"/terrain's "7" -- stage
  numbers reflect the module's own count, not strict chronological log order, see the
  `_stage(name, index)` calls), specifically so that if a build ever supplies both
  `srtm_tile_paths` and `probe_output_path`, the probe-inserted `dcs_probe` elevation grid is
  always the more-recently-inserted one `load_full_grid(conn, "elevation")` sees inside the
  terrain-semantics block -- keeping M6's classifier locked to DCS-probe-sourced grids only,
  never accidentally fed an SRTM grid. In practice a real `syria-full` build supplies only
  `srtm_tile_paths` (Stage 2 repurposes the probe to spot-check, not a stored grid), so this
  ordering concern doesn't arise for M7's own builds -- documented so it doesn't surprise a
  future combination.
- `world-model/tools/build_world_model.py` -- CLI gains `--srtm-dir` (a directory of `.hgt`
  tiles, non-recursive glob of `*.hgt`/`*.HGT`, ingested as the primary grid) and
  `--srtm-grid-spacing-m` (default from `build.pipeline.DEFAULT_SRTM_GRID_SPACING_M`, exported
  as a public name specifically so the CLI can import it without a private-member import).
  Distinct from the pre-existing `--srtm-tile` (singular, delta-stats-only). Prints
  `srtm stats: ...` / `srtm: skipped` alongside the existing per-layer summary lines.
- `world-model/tools/validate_m7_stage2_elevation.py` (new) -- CLI wrapper around
  `compare_probe_to_srtm`, mirroring `validate_m7_stage1.py`'s pattern (a throwaway analysis
  script, not part of the pipeline). Unlike Stage 1's validator, needs no built `.sqlite` at
  all -- reads the probe output file and `.hgt` tiles directly, since the spot-check comparison
  is independent of what's been ingested into the store. Made executable (`chmod +x`) to match
  `validate_m7_stage1.py`'s convention (`build_world_model.py`'s own missing +x bit predates
  this stage and was left alone).
- `world-model/src/query/describe.py` -- `describe_position`'s `elevation.source`/
  `surface_type.provenance` now read `store.reader.grid_provenance` instead of a hardcoded
  `"dcs"` literal (present since M5 Stage 3) -- this is the actual fix for the provenance gap
  the plan calls out: before this change, a store built entirely from SRTM would have reported
  its elevation as `"dcs"`, which is simply false. Falls back to `"unavailable"` when no grid of
  that kind exists yet, same absence-as-absence convention as every other field. The `dcs_m`
  field name itself is unchanged (still holds whatever numeric value the grid has, regardless of
  source) -- renaming it was out of scope for this stage and would ripple into
  `tools/analyze_m5_stage4_validation.py`, which reads it directly; not done here.
- `world-model/docs/M7_RUN_INSTRUCTIONS.md` -- added a full "Stage 2" section: staging `.hgt`
  tiles (with the row-count-sizing tradeoff spelled out numerically), running the build with
  `--srtm-dir`, running the live-probe spot-check mission via `wsl-probe-sync` (the one step in
  all of M7 that cannot be done from already-staged files -- it needs the actual DCS install),
  running `validate_m7_stage2_elevation.py`, and recording the result.
- Test fixtures updated for the now-required `provenance` field:
  `tests/test_terrain_curvature.py` (2 sites, `"dcs_probe"`), `tests/test_terrain_features.py`,
  `tests/test_ingest_terrain.py` (1 site each, `"dcs_probe"`) -- these are M6 fixtures
  representing probe-origin grids conceptually, so `"dcs_probe"` is the correct tag even though
  M6 itself doesn't care about the field. `tests/test_store_reader.py` (4 sites: 3
  `"dcs_probe"`, 1 `"srtm"` -- the `"srtm"` one doubles as a provenance-round-trip assertion on
  `load_full_grid`). `tests/test_describe_position.py`'s `_fixture_conn_with_grid` (both grids
  now `"dcs_probe"`, and the two assertions that previously read `"dcs"` now read `"dcs_probe"`
  -- a required mechanical update to keep the test asserting the truth after the hardcoded-value
  bug fix above, not a weakening of the test's intent).

### Tests Added

- `world-model/tests/test_ingest_srtm.py` (new) -- `ingest_srtm_grid` samples every cell from a
  single covering tile; selects the *correct* tile per cell from a multi-tile list (deliberately
  puts the covering tile second, to catch a "always use tiles[0]" bug); leaves
  uncovered/void cells `None` rather than guessing.
- `world-model/tests/test_build_validate.py` -- `compare_probe_to_srtm` computes a hand-
  verifiable per-point delta and summary stats against a uniform-value tile; skips (not drops)
  a point outside every tile's coverage; returns null summary stats (not zeros or a crash) when
  every point is skipped.
- `world-model/tests/test_pipeline_build_region.py` -- `test_build_region_srtm_tile_paths_
  becomes_the_primary_elevation_grid`: a real (from-disk, `SrtmTile.from_file`-parseable, just
  minimal 2x2) synthetic `.hgt` tile builds a store whose `elevation` grid reads back
  `provenance == "srtm"` via both `grid_provenance` and `load_full_grid`, and confirms
  `terrain_skipped` stays `True` (M6 not triggered by an SRTM-only build).
  `test_build_region_srtm_tile_paths_given_but_missing_is_skipped_not_an_error`: a stale
  `--srtm-dir` path degrades the same way every other optional path already does.
- `world-model/tests/test_store_reader.py` -- `test_grid_provenance_distinguishes_srtm_from_
  dcs_probe`: an `elevation` grid tagged `"srtm"` and a `surface_type` grid tagged `"dcs_probe"`
  in the same store report their own distinct provenance, and are asserted `!=` each other --
  the store-layer half of the provenance-separation proof.
  `test_grid_provenance_returns_none_when_absent`.
- `world-model/tests/test_describe_position.py` -- `test_describe_position_elevation_source_
  reports_srtm_not_dcs` and `test_describe_position_elevation_source_reports_dcs_probe_not_srtm`:
  the end-to-end half of the proof, through `describe_position` itself rather than the reader
  layer -- an SRTM-sourced grid answers `elevation.source == "srtm"` (and asserts `!=
  "dcs_probe"`), a DCS-probe-sourced grid answers the reverse, using two independently-built
  fixture stores so this isn't just a hardcoded-string coincidence.

### Checks

- `ruff format --check world-model/src world-model/tests`: pass (68 files)
- `ruff check world-model/src world-model/tests`: pass
- `mypy world-model/src` (`--strict` per `pyproject.toml`): pass, 40 source files
- `mypy --strict` on the two new/touched `tools/` files individually (not part of the mandated
  command, but checked per project convention): pass
- `pytest world-model/tests -q`: pass, 186 passed (was 173 after Stage 1; +13 new tests: 4 in
  `test_ingest_srtm.py`, 3 in `test_build_validate.py`, 2 in `test_pipeline_build_region.py`, 2
  in `test_store_reader.py`, 2 in `test_describe_position.py`)

### Notable Discoveries

- **The plan's own "Affected Modules" list named `src/build/ingest_terrain.py` for SRTM-related
  adjustment, which would have meant touching M6's ridge/valley ingest module** -- but that
  directly conflicts with this same plan's later-added Locked Decision 5 ("M6's ridge/valley
  classifier is explicitly NOT rerun here ... locked out of M7 entirely"), which the plan's own
  revision note says was finalized *after* the Affected Modules section was drafted. Treated the
  explicit lockout (and this task's own explicit instruction) as authoritative and did not touch
  `src/terrain/` or `build/ingest_terrain.py` at all -- flagging the stale cross-reference in the
  plan for whoever revisits it, since a literal reading of "Affected Modules" alone would have
  led to reintroducing exactly what the lockout forbids.
- **Grid "most recent wins" ordering needed explicit attention once two elevation-grid producers
  could coexist in one store.** `store.reader`'s `_load_grid_meta` has always picked
  `ORDER BY id DESC LIMIT 1` for a given `grid.kind` -- fine when only one producer (the probe)
  ever wrote `"elevation"` rows. Adding SRTM as a second potential producer of the same `kind`
  meant insertion order in `build_region` now has real behavioral consequences (which grid a
  later `describe_position`/M6 terrain-ingest call actually reads) that didn't exist before this
  stage -- resolved by ordering the SRTM stage before the probe stage (see Files Changed above),
  but this is a real, not hypothetical, consideration for any future third `"elevation"`
  producer.
- **`store.models.ElevationGrid`/`SurfaceGrid.provenance` being a required (non-default) field
  meant every existing test fixture constructing either dataclass directly needed a mechanical
  update** -- 9 call sites across 5 test files, none of which changed test *intent* (see Stage
  0's implementation.md entry for the same "many direct readers of one field" pattern recurring
  here for a different field).
