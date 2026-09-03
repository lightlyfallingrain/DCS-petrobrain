# Todo

## Current Focus

World Model Builder — Milestone 0/1. See `world-model/ROADMAP.md` for full milestone list and status.

- [x] M0 — record installed DCS version + confirm Syria terrain present, in `world-model/research/`.
- [x] M1 (recon) — prove DCS x/z ↔ lat/lon transform for Syria against a known real-world control point; measure error. pydcs tmerc params confirmed against live install; real-world residual ~1.0-1.3km (terrain-placement error, not projection defect). See `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`.
- [ ] M1 (implement) — build `src/coordinates/` per `plans/m1-coordinate-transform/plan.md`, with control-point tests.

## Milestones

Full sequence lives in `world-model/ROADMAP.md` (M0 through M7). Do not start Mission Interpreter or Petrobrain Runtime work — see root `CLAUDE.md` "Current priority".

## Deferred

- Spatial storage/library choice (GeoPackage vs SpatiaLite vs PostGIS) — decide during M1-M2, record rationale in `world-model/research/`.
