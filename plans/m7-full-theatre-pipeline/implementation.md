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
