---
name: project_m5_stage1_layout
description: M5 Stage 1 built src/geometry, src/dcs_data, src/store, src/build, src/query, and three CLI tools — offline layers only, roadnet/probe deferred
metadata:
  type: project
---

M5 Stage 1 (2026-09-04) landed the offline half of the World Model Builder's first persistent
store: `src/geometry/` (planar primitives shared by build+query), `src/dcs_data/` (towns.lua +
beacons.lua strict parsers), `src/store/` (SQLite + R*Tree, schema/models/writer/reader),
`src/build/` (region registry + towns/beacons/OSM ingest + pipeline), `src/query/describe.py`
(`describe_position`), and `tools/{build_world_model,describe_position,export_geojson}.py`.

**Why this matters for later stages**: `describe_position`'s `nearest_road` (DCS) and
`elevation`/`surface_type` are correctly `None`/null at this point — Stage 2 (`src/roadnet/`,
DCS-native `.routes`/`.rn4` parsing) and Stage 3 (elevation/surface-type probe) still need to be
wired into `build/pipeline.py` and `query/describe.py`. Don't be surprised these fields are empty
in a Stage-1-only build; that's the contract's honesty rule working, not a bug.

**Non-obvious design points worth knowing before touching this code**:
- `nearest_feature` in `store/reader.py` takes an optional `provenance_geometry` filter so
  `nearest_road` (DCS) and `nearest_road_osm` can share `kind="road"` in the same table and still
  be queried independently — needed because Stage 2 will add DCS roads with the same `kind` OSM
  roads already use.
- Regions are DCS-space squares (`build/region.py`'s `RegionDefinition`); the Overpass lat/lon
  envelope is always a *derived* padded box of the four corners, never the definition (Gemerek's
  corners disagree by ~0.008 deg latitude, so lat/lon-first would silently be the wrong shape).
- `ingest_beacons.py` is the only ingest module allowed to derive geometry (runway segments,
  airfield points) — everything else is transcription. This split is enforced by
  `test_ingest_beacons.py`'s provenance/uncertainty scope-guard test.
