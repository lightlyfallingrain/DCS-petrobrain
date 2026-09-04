"""Persistent spatial store: one SQLite file per theatre-region.

M5 decision (see `plans/m5-first-persistent-model/plan.md` "Key decision:
spatial storage" for the full rationale and rejected alternatives --
PostGIS, SpatiaLite, GeoPackage, FlatGeobuf/GeoParquet):

- **stdlib `sqlite3`, no new dependency.** DCS x/z is a metric projected
  plane, so the spatial predicates this project needs (point-to-point and
  point-to-segment distance, point-in-polygon, bbox pruning) are ordinary
  planar geometry (`geometry/`), not something that requires a GIS
  extension.
- **A built-in R*Tree virtual table for bbox pruning.** `SQLite`'s
  `ENABLE_RTREE` build option, populated by explicit insert in the same
  transaction as the feature row (`writer.py`) -- not database triggers, so
  there is exactly one place to read and debug the indexing logic.
- **Geometry stored as JSON coordinate arrays (`[[x, z], ...]`), not WKB.**
  Readable in any SQLite browser mid-debugging and cannot be silently
  mis-endianed; a WKB emitter can live in a future exporter if a GeoPackage
  writer is ever wanted.
- **DCS x/z metres is the one stored geometry.** lat/lon is always derived
  on read (via `coordinates.dcs_to_wgs84`), never stored as a second
  geometry that could drift out of sync with the DCS-authoritative one.

The database is always rebuildable from `data/raw/` (`build/pipeline.py`)
and is never treated as a second source of truth -- `SCHEMA_VERSION` in the
`meta` table exists so a stale file after a schema edit is a loud error, not
a silently misread one.
"""
