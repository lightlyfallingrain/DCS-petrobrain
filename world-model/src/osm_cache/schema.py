"""SQL DDL for the OSM classified-feature cache, and its own independent
schema-version discipline.

`OSM_CACHE_SCHEMA_VERSION` is a separate counter from `store.schema.
SCHEMA_VERSION` -- the two files have different lifecycles (the cache
survives the base store's delete-and-recreate rebuild), so a DDL change to
one must never be conflated with a version bump to the other. **This
constant must be bumped whenever `store.models.StoredFeature`'s shape
changes incompatibly** -- the cache's `feature` table mirrors that
dataclass field-for-field, and nothing enforces the two staying in sync
except this comment (same drift-risk class M8 flagged for
`probe_store.reader._load_grid_meta`).

The `feature` table is shaped like `store.schema`'s `feature` table with two
differences: `id` here has no relationship to the base store's own
`feature.id` (rows are re-inserted into the base store via `store.writer.
insert_features`, which assigns fresh ids), and there is no `feature_bbox`
R*Tree -- the cache is read by full sequential scan (`reader.
iter_cached_features`), never queried spatially.
"""

import sqlite3

OSM_CACHE_SCHEMA_VERSION = 1

# `OsmCacheMeta`'s own fields, stored as individual `meta` rows (mirrors
# `probe_store.schema.IDENTITY_META_KEYS`'s key/value shape) rather than one
# JSON blob, so a single mismatched field is independently readable/
# debuggable from the sqlite file directly. Shared here so `writer.py`
# (which writes these keys) and `reader.py` (which reads them back) can't
# drift apart on the key list.
META_FIELDS = (
    "pbf_sha256",
    "pbf_size_bytes",
    "classifier_version",
    "cache_schema_version",
    "region_name",
    "centre_x",
    "centre_z",
    "half_extent_x_m",
    "half_extent_z_m",
    "built_at",
)

# The `meta` key `writer.finalize_cache` stores the serialized
# `OsmIngestStats` under, and `reader.load_cached_stats` reads it back from.
STATS_META_KEY = "osm_ingest_stats_json"

_DDL = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE feature (
    id INTEGER PRIMARY KEY,
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
"""


def create_osm_cache_schema(conn: sqlite3.Connection) -> None:
    """Create the cache's tables on an empty connection. Raises
    `sqlite3.OperationalError` if the schema already exists. Does **not**
    record `OSM_CACHE_SCHEMA_VERSION` in `meta` -- unlike the base/probe
    stores, that happens once, at `writer.finalize_cache` time, alongside
    the rest of the cache's identity fields, since a cache under
    population at its `.tmp` path is not yet a valid, checkable cache."""
    conn.executescript(_DDL)
