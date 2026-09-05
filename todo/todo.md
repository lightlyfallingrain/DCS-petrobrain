# Todo

## Current Focus

World Model Builder — Milestone 0/1. See `world-model/ROADMAP.md` for full milestone list and status.

- [x] M0 — record installed DCS version + confirm Syria terrain present, in `world-model/research/`.
- [x] M1 (recon) — prove DCS x/z ↔ lat/lon transform for Syria against a known real-world control point; measure error. pydcs tmerc params confirmed against live install; real-world residual ~1.0-1.3km (terrain-placement error, not projection defect). See `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`.
- [x] M1 (implement) — `src/coordinates/` built per plan, control-point tests pass. Windows/WSL probes run: pydcs Syria tmerc params confirmed against live `coord.LOtoLL` (sub-meter match, 226 points); real-world residual ~1.0-1.3km vs published ARPs, explained as DCS terrain-placement error. See `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`.
- [x] M2 — Raster understanding. `src/raster/` (Pillow DDS loader + empirical registration), `tools/inspect_raster.py` diagnostic, control-point + held-out-point tests pass. See `world-model/ROADMAP.md` M2 entry and `plans/m2-raster-understanding/`.
- [x] M3 — OSM overlay. `src/osm/` (Overpass API fetch + in-memory parse), `tools/inspect_osm_overlay.py` diagnostic overlay, tests pass, held-out Gemerek validation. Attribution rendered onto output PNG. Spatial-storage choice deferred to M5. See `world-model/research/2026-09-03-m3-osm-overlay.md` and `plans/m3-osm-overlay/`.
- [x] M4 — DCS elevation. `src/elevation/` (`land.getHeight` live-mission probe via io/lfs, SRTM3 `.hgt` parsing), `tools/inspect_elevation.py` diagnostic, control-point + real-fixture tests pass. 100-point Gemerek grid vs SRTM3: mean delta +13.89m, west-edge outlier traced to real terrain-mesh-resolution mismatch, not a bug. `MissionScripting.lua` io/lfs edit intentionally left in place (more probes expected M5+). See `world-model/research/2026-09-03-m4-dcs-elevation.md` and `plans/m4-dcs-elevation/`.
- [x] M5 — First persistent model. `src/store/` (stdlib `sqlite3` + R*Tree, JSON geometry), `src/roadnet/` (DCS-native `.routes` binary parser), `src/dcs_data/` (towns/beacons Lua parsers), `src/query/describe_position`. Region: Latakia (`latakia-20km`). Real store: 3,266 roads, 338 settlements, 117 water, 108 named places, 1,681-point elevation/surface_type probe grid at 100% coverage, 8.57 MB `.sqlite`. Two real defects found+fixed: `pyproj.Transformer` per-call rebuild (perf), roadnet resync denormalized-float validation gap (correctness). `.rn4` graph decoding, airfield taxiways/structures, Latakia SRTM tile, full-theatre resync audit deferred to M6+. See `world-model/research/2026-09-04-m5-first-persistent-model.md` and `plans/m5-first-persistent-model/`.

## Milestones

Full sequence lives in `world-model/ROADMAP.md` (M0 through M7). Do not start Mission Interpreter or Petrobrain Runtime work — see root `CLAUDE.md` "Current priority".

## Backlog

- [ ] **Incremental per-layer pipeline builds** — `build_region` currently deletes and recreates the entire `.sqlite` on every call, forcing a full rebuild of all layers each time. User-requested capability: run individual pipeline sections (e.g., roads only, elevation only, validation only) and *add* that data into an existing store, allowing staged builds and partial re-runs when debugging a single layer. Deferred post-M7 (raised during M7 DoD acceptance testing, explicitly not blocking). See `plans/m7-full-theatre-pipeline/` for context and `world-model/src/build/pipeline.py`'s `build_region` implementation.

## Deferred

- Spatial storage/library choice — resolved by M5: stdlib `sqlite3` + R*Tree, JSON geometry (not GeoPackage/SpatiaLite/PostGIS). See `world-model/research/2026-09-04-m5-first-persistent-model.md`.
