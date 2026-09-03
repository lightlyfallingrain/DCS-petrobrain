---
name: project_m3_osm_overlay_plan
description: M3 (OSM overlay) plan — known location (Gemerek), Overpass fetch design, storage backlog resolved (deferred to M5)
metadata:
  type: project
---

M3 plan (`plans/m3-osm-overlay/plan.md`), written 2026-09-03, no investigator invocation needed —
M3 only consumes M1's `coordinates.wgs84_to_dcs` and M2's `raster.registration.dcs_to_tile_pixel`
as-is; it introduces no new DCS-internals unknown (OSM/Overpass is a well-documented external
system, not a DCS internal).

**Known location chosen: Gemerek** (39.18194°N, 36.06806°E), the M2 session-12 *held-out*
control point (tile `64maa00_x0_z0`, already-measured chart-pixel residual ≈129m x / ≈5.5km z).
Deliberately NOT one of M1's ARPs (Damascus/Latakia/Beirut — outside M2's registered raster sheet)
and NOT one of M2's registration *fit* points (Sivas/Kahramanmaraş/Hama — reusing a fit point
for the raster-alignment check would be circular). Fallback if Gemerek's OSM coverage is too
sparse (real risk, small rural town): Sivas — but note that's a fit point, not an independent
raster-accuracy check, only still useful for testing the new OSM pipeline itself.

**Bandwidth constraint (user hard requirement)**: single one-shot Overpass API query
(`overpass-api.de/api/interpreter`), bbox ~2.8km×3.4km around Gemerek, `out geom` so no
separate node-resolution pass, estimated <500KB (likely <100KB for this rural town size). Cached
to `data/raw/osm/<date>/` (already covered by `world-model/.gitignore`'s `data/raw/` rule).
Fetched via stdlib `urllib.request` — deliberately avoided adding `requests` as a new dependency
for a single-use HTTP call (AGENTS.md escalation trigger for new deps).

**Storage backlog resolved for M3, not decided generally**: `todo/todo.md`'s long-stale "decide
spatial storage during M1-M2" item is NOT being resolved to a real DB choice yet — M3's plan
explicitly defers to M5, with rationale (M3 only needs a raw JSON cache + in-memory dataclasses +
a rendered PNG/report, no queryable multi-feature index). Plan updates `todo/todo.md` and
`world-model/CLAUDE.md`'s "Spatial storage" line to say "deferred to M5, confirmed not needed for
M3" instead of leaving the stale "decide during M1-M2" text dangling.

**Module layout**: `src/osm/{overpass.py,features.py}` (pipeline: fetch+cache, parse — mirrors
`coordinates/`/`raster/` structure) + `tools/inspect_osm_overlay.py` (diagnostic CLI, mirrors
`tools/inspect_raster.py`'s `scan`/`mark` pattern) — the actual overlay-rendering/
displacement-report logic stays in `tools/` (diagnostic, not pipeline), matching how M2 kept
`inspect_raster.py` out of `src/`.

**Expected displacement is not a bug**: M1's ~1.0-1.3km DCS-vs-real-world residual plus M2's
raster z-axis ~8-9% tile-edge residual compose into low-single-digit-km expected OSM-vs-raster
displacement — the research note should say this explicitly, not re-litigate it as new.

**How to apply**: when this plan is picked up, Stage 1 (fetch + inspect raw JSON) gates whether
Gemerek or the Sivas fallback is actually used — check which was chosen before writing the CLI
around it. See [[project_m2_rastercharts_plan]] for the raster-registration background this plan
builds on.
