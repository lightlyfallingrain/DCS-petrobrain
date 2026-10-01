---
name: terrain-cache-resumable-fail-closed-approved
description: landform-geomorphons' per-tile resumable SQLite cache verified fail-closed; theatre-omission identity gap mirrors pre-existing osm_cache pattern
metadata:
  type: project
---

`terrain_cache/` (WM-B6, `feature/landform-geomorphons`, tip `cc68f48`) deliberately departs from
`osm_cache`'s `.tmp`-then-rename atomicity pattern to support per-tile resumability: it writes
directly to the cache's canonical path, with one SQLite transaction per tile as the durability unit.
Verified this is still fail-closed: no `PRAGMA synchronous=OFF`/WAL override anywhere in
`terrain_cache/` or `osm_cache/`, so a crash mid-tile rolls back cleanly (SQLite default journal) and
the tile is simply reprocessed on reopen — no corruption risk from the resumability design itself. A
genuinely corrupted cache file (truncated, bit-rot) is not caught explicitly and propagates as an
uncaught `sqlite3.DatabaseError` — a loud crash, which is the correct fail-closed behaviour here
(never silently serve partial/stale data), not a vulnerability.

**Identity-key gap, found but not blocking:** `terrain_cache/models.py::_INVALIDATION_KEY_FIELDS`
tracks `region_name`/`centre_x`/`centre_z`/`half_extent_*` but not `RegionDefinition.theatre`
(`build/region.py`). Two different theatres with coincidentally the same region name+centre+extent
would pass `cache_meta_matches` while the theatre-specific `dcs_to_wgs84_array` projection would
reinterpret the lattice as a different real-world location. Not realistically reachable: cache file
paths are derived from the region's own output store path (`terrain_cache_store_path(out_path)`),
which is itself keyed by `region.name` — a collision there would first collide on the base store
file, a bigger pre-existing problem. **`osm_cache.models.OsmCacheMeta`/`_INVALIDATION_KEY_FIELDS`
has the exact same omission** (confirmed in `build/pipeline.py`'s `OsmCacheMeta` construction, same
field set) — this is an existing project convention, not something this feature introduced. If a
future feature ever makes the same region name legitimately reusable across theatres, re-check both
cache identity keys for the `theatre` field.

**Memory accounting pattern confirmed sound:** `build/ingest_terrain.py::ingest_terrain`'s per-tile
loop accumulates only lightweight `StoredFeature` geometry across tiles (`cache_features` list); the
large per-tile raster arrays (`dem`/`classes`/`mask`/`skeleton`) are local to `_process_tile` and go
out of scope each iteration — no cross-tile raster accumulation in a long (131-tile) theatre run.
Reusable check for any future per-tile/per-chunk pipeline: confirm large intermediate arrays are
function-local, not held in a loop-level accumulator alongside the lightweight output.
