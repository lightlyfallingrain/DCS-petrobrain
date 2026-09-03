# Todo

## Current Focus

World Model Builder — Milestone 0/1. See `world-model/ROADMAP.md` for full milestone list and status.

- [x] M0 — record installed DCS version + confirm Syria terrain present, in `world-model/research/`.
- [x] M1 (recon) — prove DCS x/z ↔ lat/lon transform for Syria against a known real-world control point; measure error. pydcs tmerc params confirmed against live install; real-world residual ~1.0-1.3km (terrain-placement error, not projection defect). See `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`.
- [x] M1 (implement) — `src/coordinates/` built per plan, control-point tests pass. Windows/WSL probes run: pydcs Syria tmerc params confirmed against live `coord.LOtoLL` (sub-meter match, 226 points); real-world residual ~1.0-1.3km vs published ARPs, explained as DCS terrain-placement error. See `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`.
- [x] M2 — Raster understanding. `src/raster/` (Pillow DDS loader + empirical registration), `tools/inspect_raster.py` diagnostic, control-point + held-out-point tests pass. See `world-model/ROADMAP.md` M2 entry and `plans/m2-raster-understanding/`.
- [x] M3 — OSM overlay. `src/osm/` (Overpass API fetch + in-memory parse), `tools/inspect_osm_overlay.py` diagnostic overlay, tests pass, held-out Gemerek validation. Attribution rendered onto output PNG. Spatial-storage choice deferred to M5. See `world-model/research/2026-09-03-m3-osm-overlay.md` and `plans/m3-osm-overlay/`.

## Milestones

Full sequence lives in `world-model/ROADMAP.md` (M0 through M7). Do not start Mission Interpreter or Petrobrain Runtime work — see root `CLAUDE.md` "Current priority".

## Deferred

- Spatial storage/library choice (GeoPackage vs SpatiaLite vs PostGIS) — deferred to M5; M3 confirmed no DB is needed yet (no point-in-polygon/nearest-neighbor/multi-feature-type join workload exists before `describe_position(...)`), see `world-model/research/2026-09-03-m3-osm-overlay.md`.
