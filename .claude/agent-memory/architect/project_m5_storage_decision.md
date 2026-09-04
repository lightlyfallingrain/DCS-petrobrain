---
name: m5-storage-decision
description: M5 chose stdlib sqlite3 + R*Tree over GeoPackage/SpatiaLite/PostGIS for the world-model spatial store; the reasoning and what would reverse it
metadata:
  type: project
---

M5 resolves the spatial-storage question deferred since M3: **one SQLite file per
theatre-region, stdlib `sqlite3`, geometry as JSON `[[x, z], ...]` in DCS metres, built-in
R*Tree for bbox pruning; QGIS access via a GeoJSON exporter, not by making the store a
GeoPackage.** Plan: `plans/m5-first-persistent-model/plan.md`.

**Why:** the decisive argument is not dependency-aversion — it is that **DCS x/z is a metric
projected plane, so Euclidean distance in x/z already equals distance in metres.** That removes
geodesic math, per-query reprojection, and CRS machinery, which is most of what a spatial stack
would be doing. What remains (point-point, point-segment, point-in-polygon, bbox) is ~100 lines
of testable planar geometry. Verified locally: this machine has **no** mod_spatialite, no GDAL,
no shapely; the venv's SQLite (3.53.4) *does* have ENABLE_RTREE + ENABLE_GEOPOLY and working
`enable_load_extension`. GeoPackage was rejected as *storage* specifically because DCS's PROJ
def uses `+axis=neu` and QGIS handling of a custom neu-axis SRS is unverified — a nominally
conformant GPKG could render transposed, the worst failure mode for a project whose stated
hazard is "convincing but wrong geography".

**How to apply:** treat this as reversible, not load-bearing. The schema is ordinary SQL, so
GPKG/SpatiaLite can later be added as an *exporter*, or swapped in behind `store/reader.py`'s
interface if M7's full-theatre workload proves Python-side geometry too slow. Do not re-litigate
the decision without one of those two triggers. Related: [[m5-region-selection-lesson]].
