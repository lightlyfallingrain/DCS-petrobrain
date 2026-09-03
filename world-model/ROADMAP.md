# World Model Builder — Roadmap

Decisions locked in for this phase:

- **Theatre**: Syria (first).
- **Stack**: Python 3.11+, type-hinted, `mypy --strict`. Spatial libraries TBD during Milestone 1-2.
- **Machines**: DCS on Windows, dev on Mac, manual-copy workflow (`WORKFLOW.md`).

Milestones below are from `../docs/concept/WORLD_MODEL_BUILDER.md` — status tracked here as work proceeds.

- [x] **M0 — Repo + research notebook.** Scaffold done. DCS version + Syria theatre presence recorded in `research/`.
- [x] **M1 — One coordinate.** Prove DCS x/z ↔ lat/lon for Syria against a known real-world control point. Measure error. Done: `src/coordinates/` (pyproj-based, theatre-agnostic), three real-world ARP control points (Damascus, Latakia, Beirut), measured residual ~1.0-1.3km (DCS terrain-art placement error, not transform error). See `research/2026-09-03-m1-coordinate-transform-verification.md`.
- [ ] **M2 — Raster understanding.** Read Syria's `RasterCharts`: tile hierarchy, dimensions, scales, registration. Render a known DCS coordinate onto the raster.
- [ ] **M3 — OSM overlay.** Small OSM region around the known location, transformed into DCS/raster space. Diagnostic overlay, quantify displacement.
- [ ] **M4 — DCS elevation.** Sample DCS terrain elevation over a small region, compare against external DEM.
- [ ] **M5 — First persistent model.** Small geographic DB (~20×20 km test region): elevation, roads, settlements, water, named places. Implement `describe_position(...)`.
- [ ] **M6 — Terrain semantics.** One derived feature class (ridges/valleys). Validate usefulness from an Mi-24 cockpit perspective.
- [ ] **M7 — Full theatre pipeline.** Only after M5/M6 prove reliable on the small region.

Not doing yet (see concept doc "Things Not To Do Yet"): Petrovich dialogue, speech, embeddings, screenshot interpretation, full-theatre processing, elaborate distributed architecture.
