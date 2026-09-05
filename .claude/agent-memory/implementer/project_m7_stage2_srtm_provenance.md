---
name: project-m7-stage2-srtm-provenance
description: M7 Stage 2 (SRTM-primary elevation) results and the grid-provenance schema change it required.
metadata:
  type: project
---

M7 Stage 2 (2026-09-05) made SRTM the primary full-theatre `elevation`/`surface_type` source,
provenance-tagged `"srtm"` vs the pre-existing DCS-live-probe `"dcs_probe"`. Key facts for future
sessions touching `world-model/src/store/`, `elevation/`, or `build/ingest_*`:

- `grid.provenance` is a new required column (`SCHEMA_VERSION` bumped 2->3). `ElevationGrid`/
  `SurfaceGrid` now require a `provenance: str` field with no default -- any new/old test fixture
  constructing either dataclass directly must pass it, or `mypy --strict` fails immediately.
- `store.reader.grid_provenance(conn, grid_kind)` is the accessor `query.describe.
  describe_position` uses for `elevation.source`/`surface_type.provenance` -- previously both
  were a hardcoded `"dcs"` literal, silently wrong once a build could be SRTM-sourced. Fixed by
  reading the real value; existing tests asserting `"dcs"` had to become `"dcs_probe"`.
- `store.reader._load_grid_meta` picks `ORDER BY id DESC LIMIT 1` per `grid.kind` -- "most
  recent write wins" now has real consequences once two producers (SRTM ingest, DCS-probe
  ingest) can both write `kind="elevation"` rows in one build. `build.pipeline.build_region`
  deliberately runs the SRTM stage *before* the probe stage so the probe grid (if present) stays
  the one M6's terrain-ingest and `describe_position` see -- keeps M6 locked to DCS-probe-only
  grids per the plan's explicit lockout. Any future third elevation-grid producer needs the same
  ordering awareness, not just a naive insert-and-forget.
- `elevation.dem.select_tile(tiles, lat, lon)` is the new shared multi-tile lookup primitive
  (linear scan, fine at real-world tile-list sizes) -- reused by both `build.ingest_srtm`
  (primary grid ingest) and `build.validate.compare_probe_to_srtm` (spot-check delta report).
  Don't duplicate tile-selection logic elsewhere; extend this function instead.
- The plan's own "Affected Modules" list named `build/ingest_terrain.py` for SRTM adjustment,
  which directly conflicts with a Locked Decision added later in the same plan ("M6 not rerun in
  M7", `src/terrain/` untouched). When a plan's file list and its own locked decisions disagree,
  the locked decision (and any explicit task instruction) wins -- the file list can be stale from
  an earlier draft. See [[project_m7_stage0_region_generalization]] for the prior instance of
  this plan's own estimates undercounting real blast radius.
