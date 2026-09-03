# World Model Builder — Roadmap

Decisions locked in for this phase:

- **Theatre**: Syria (first).
- **Stack**: Python 3.11+, type-hinted, `mypy --strict`. Spatial libraries TBD during Milestone 1-2.
- **Machines**: DCS on Windows, dev on Mac, manual-copy workflow (`WORKFLOW.md`).

Milestones below are from `../docs/concept/WORLD_MODEL_BUILDER.md` — status tracked here as work proceeds.

- [x] **M0 — Repo + research notebook.** Scaffold done. DCS version + Syria theatre presence recorded in `research/`.
- [x] **M1 — One coordinate.** Prove DCS x/z ↔ lat/lon for Syria against a known real-world control point. Measure error. Done: `src/coordinates/` (pyproj-based, theatre-agnostic), three real-world ARP control points (Damascus, Latakia, Beirut), measured residual ~1.0-1.3km (DCS terrain-art placement error, not transform error). See `research/2026-09-03-m1-coordinate-transform-verification.md`.
- [x] **M2 — Raster understanding.** Read Syria's `RasterCharts`: tile hierarchy, dimensions, scales, registration. Render a known DCS coordinate onto the raster. Done: `src/raster/` (Pillow-based DDS loader + empirical x/z-arithmetic registration, `confidence="provisional"`), `tools/inspect_raster.py` (`scan`/`mark` diagnostic CLI), control-point + held-out-point tests. Registration fitted against Sivas/Kahramanmaras/Hama/Erzincan; independently validated against held-out Gemerek (~129m x-axis, ~5.5km z-axis residual). Scope note: this raster is scanned real-world cartography (Turkish JOG-A-class chart), not DCS-rendered geometry — feeds only the F10 paper-map mode; provenance-taxonomy follow-up still open, see `plans/m2-raster-understanding/plan.md` "Decisions Requiring User Input". `level` tile-suffix semantics (`-2`/`-1`/`00`/`01`) remain unresolved, no sample beyond `"00"`. See `research/2026-09-03-m2-rastercharts-recon.md`.
- [x] **M3 — OSM overlay.** Small OSM region around the known location, transformed into DCS/raster space. Diagnostic overlay, quantify displacement. Done: `src/osm/` (Overpass API fetch + in-memory parse), `tools/inspect_osm_overlay.py` diagnostic overlay CLI, control-point + transform tests, held-out Gemerek validation. Expected ~5.2 km z-axis displacement observed (consistent with M1/M2 residual), OSM coverage non-trivial (96 highways, 17 buildings), attribution rendered onto output PNG. Spatial-storage choice deferred to M5 (no DB needed yet). See `research/2026-09-03-m3-osm-overlay.md`.
- [x] **M4 — DCS elevation.** Sample DCS terrain elevation over a small region, compare against external DEM. Done: `src/elevation/` (`dcs_grid.py` parses `land.getHeight` live-probe output, `dem.py`'s `SrtmTile` parses SRTM `.hgt` with dynamic grid-size detection), `tools/dcs-mission-probe/elevation_probe.lua` (live-mission probe, io/lfs-based), `tools/inspect_elevation.py` (DCS-vs-SRTM delta report CLI). 100-point grid over the Gemerek bbox vs. a real SRTM3 tile: mean delta +13.89m, stddev 28.02m, range -86.09m to +69.19m — spatially clustered (west edge + one diagonal band), consistent with terrain-mesh-resolution mismatch rather than a systematic vertical datum offset. See `research/2026-09-03-m4-elevation-recon.md` (recon) and `.../2026-09-03-m4-dcs-elevation.md` (results).
- [ ] **M5 — First persistent model.** Small geographic DB (~20×20 km test region): elevation, roads, settlements, water, named places. Implement `describe_position(...)`.
- [ ] **M6 — Terrain semantics.** One derived feature class (ridges/valleys). Validate usefulness from an Mi-24 cockpit perspective.
- [ ] **M7 — Full theatre pipeline.** Only after M5/M6 prove reliable on the small region.

Not doing yet (see concept doc "Things Not To Do Yet"): Petrovich dialogue, speech, embeddings, screenshot interpretation, full-theatre processing, elaborate distributed architecture.
