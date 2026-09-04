---
name: project_pyproj_transformer_perf
description: coordinates.wgs84_to_dcs/dcs_to_wgs84 built a fresh pyproj.Transformer per call — invisible until M5's OSM-ingest scale, fixed with functools.cache
metadata:
  type: project
---

`coordinates/__init__.py`'s `dcs_to_wgs84`/`wgs84_to_dcs` called `Transformer.from_crs(...)`
fresh on every invocation. M1-M4 never pushed more than a few hundred calls through this path
(control points, small elevation grids), so the cost was invisible. M5 Stage 1's build pipeline
runs every OSM way vertex through it (~13,600 raw Overpass elements for a 20x20km region) and
this made a single region build take minutes of 100%-CPU time, dominated by CRS/pipeline setup
rather than actual coordinate math.

**Fix**: per-theatre `@functools.cache`-wrapped transformer builders
(`_dcs_to_wgs84_transformer`/`_wgs84_to_dcs_transformer`), keyed on theatre name. Public
signatures, behavior, and existing tests unchanged — pure performance fix. Full Latakia build:
>2m33s (killed) -> 0.59s.

**How to apply**: any future milestone that pushes more coordinates through this module (M6
ridge/valley extraction, M7 full-theatre ingest, a larger OSM bbox) should already benefit from
this cache — but if a *new* hot path bypasses `coordinates.dcs_to_wgs84`/`wgs84_to_dcs` (e.g.
calling `pyproj` directly), it will reintroduce the same problem. Treat repeated coordinate
transform calls over many points as a performance-sensitive path worth profiling before assuming
it's cheap.
