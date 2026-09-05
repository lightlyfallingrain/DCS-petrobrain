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
