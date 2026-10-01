"""SQL DDL for the terrain-extraction cache, and its own independent
schema-version discipline.

**Why this cache cannot use `osm_cache`'s atomic-swap-at-the-end pattern.**
That cache's contract is "existence at the canonical path is the only
validity signal" -- a `.tmp` file populated across the *whole* pass,
`os.replace`d to its canonical name only once, atomically, at the end.
That is exactly what a resumable, per-tile cache must **not** do: a build
interrupted partway through would either leave nothing at the canonical
path (losing every tile already done, defeating resumability) or, if the
rename happened early, present a half-populated file as complete. Per
`plans/landform-geomorphons/plan.md`'s "The cache" section, this cache is
instead populated **at its canonical path directly**, with per-tile
completion rows mutated in place inside individual SQLite transactions --
SQLite's own atomic commit is the unit of durability, replacing the OS-level
rename.

`TERRAIN_CACHE_SCHEMA_VERSION` is a separate counter from `store.schema.
SCHEMA_VERSION`/`osm_cache.schema.OSM_CACHE_SCHEMA_VERSION` -- each cache
has its own lifecycle. Bump it whenever `store.models.StoredFeature`'s
shape changes incompatibly (the `feature` table mirrors it field-for-
field) or this file's own DDL changes.
"""

import sqlite3

TERRAIN_CACHE_SCHEMA_VERSION = 1

# `TerrainCacheMeta`'s own fields, stored as individual `meta` rows
# (mirrors `osm_cache.schema.META_FIELDS`'s key/value shape). `build_
# complete` is deliberately **not** here -- see `models.py`'s module
# docstring: it is not part of the cache's identity, it is the one thing a
# reader must check in addition to identity before trusting a bulk-copy
# fast path.
META_FIELDS = (
    "dem_identity",
    "extractor_version",
    "cache_schema_version",
    "region_name",
    "centre_x",
    "centre_z",
    "half_extent_x_m",
    "half_extent_z_m",
    "spacing_m",
    "margin_cells",
    "lookup_cells",
    "flat_deg",
    "close_iterations",
    "max_turn_cos",
    "min_line_length_cells",
    "chaikin_iterations",
    "built_at",
)

# The one `meta` key outside `META_FIELDS`/`TerrainCacheMeta` -- "has every
# planned tile completed", set only once, in its own transaction, by
# `writer.mark_build_complete`.
BUILD_COMPLETE_KEY = "build_complete"

_DDL = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE tile (
    tile_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    feature_count INTEGER NOT NULL
);

CREATE TABLE feature (
    id INTEGER PRIMARY KEY,
    tile_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    geom_type TEXT,
    geom_json TEXT,
    name TEXT,
    subtype TEXT,
    tags_json TEXT,
    source_ref TEXT,
    provenance_json TEXT,
    confidence_json TEXT,
    position_uncertainty_m REAL
);

CREATE INDEX feature_tile_id ON feature (tile_id);
"""


def create_terrain_cache_schema(conn: sqlite3.Connection) -> None:
    """Create the cache's tables on an empty connection. Raises
    `sqlite3.OperationalError` if the schema already exists."""
    conn.executescript(_DDL)
