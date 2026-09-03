---
name: project_m2_rastercharts
description: M2 RasterCharts/clipmap recon facts for Syria terrain, plus vegetation/contour API findings.
metadata:
  type: project
---

Syria: 1280 DXT5 DDS RasterCharts tiles are scanned real paper charts (JOG-A-like 1:250k, Turkey
terrain, UTM grid printed in-tile — independent registration path). forum.dcs.world blocks
WebFetch (403) — see [[forum-dcs-world-fetch]]. F10 satellite mode's likely asset is
`clipmaps/colortexture/` (separate dir, own probe script), not RasterCharts.

Stage 1 registration: z-axis ~9% residual (2pt), x-axis <0.2% residual (3pt) + graticule
cross-check ~1% agreement. x-tile-index increases SOUTH (opposite DCS +x), z-tile-index
increases EAST (same as DCS +z) — sign flip `registration.py` must encode.
confidence="provisional" justified.

**No documented tree/vegetation query API exists.** `Object.Category` = {UNIT, WEAPON, STATIC,
SCENERY, BASE} — no vegetation category. `SceneryObject` is ED-documented as "bridges,
buildings, etc" only. `land.getSurfaceType` enum = {LAND, SHALLOW_WATER, WATER, ROAD, RUNWAY} —
no FOREST value; an ED wishlist thread requests adding one (title only, not confirmed still
open). No community tooling found for extracting individual tree positions — only texture-
reskin mods ("Better Trees for ..."). Treat DCS forests as very likely a procedural/render-time
scatter, not discretely queryable objects, until an empirical `world.searchObjects(SCENERY,...)`
probe against a live mission proves otherwise. Fallback for a vegetation layer: OSM
landuse=forest/natural=wood polygons, cross-checked coarsely against DCS's own rendered forest
polygon shapes.

**Terrain-contour data does not need separate reverse-engineering.** Dense `land.getHeight`
grid sampling (already known available, same live-mission-only class as `coord.LOtoLL`) +
standard marching-squares/GDAL-contour algorithms is sufficient to derive contour-line-
equivalent geometry — this is exactly what `docs/concept/WORLD_MODEL_BUILDER.md` Milestone 4 +
"Elevation-derived features" already plans. F10's "Alt" map mode is very likely just a UI
rendering of data DCS already exposes elsewhere, not a separate asset worth cracking.

Caution: a screenshot the user labeled "Alt mode" (`alt-map.jpg`) actually has an on-screen HUD
readout saying "MAP" — the Map/Alt/Sat button state wasn't independently confirmed. Don't trust
user mode-labeling of F10 screenshots without checking the in-image HUD text yourself.
