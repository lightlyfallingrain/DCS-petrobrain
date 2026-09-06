"""SQL DDL for the probe store, and its own independent schema-version
discipline.

`PROBE_SCHEMA_VERSION` is a separate counter from `store.schema.
SCHEMA_VERSION` -- the two files have different lifecycles (see
`plans/m8-incremental-store/plan.md`'s "Storage architecture: two stores"),
so a DDL change to one must never be conflated with a version bump to the
other.

Every table is generic-by-`kind` -- no table or column is named after
elevation, `surface_type`, ridge or valley (see the plan's "Extensibility"
section). A new probe-tier data type is one new `grid` row (raster-shaped)
or a batch of new `feature` rows (vector-shaped) plus an ingest function; it
never requires `ALTER TABLE`.

`PROBE_SPACING_M` (100 m, locked) lives here rather than in `store.chunks`
because it is a probe-store-specific concept the base store's chunk lattice
(`store.chunks.CHUNK_SIZE_M`) has no reason to know about. The assertion
below -- chunk size must be an integer multiple of probe spacing, so every
chunk edge lands exactly on a probe grid cell boundary -- is exactly the
"assert this, don't assume it" instruction from the plan's locked
parameters table; it runs at import time, once, rather than being re-
verified (or silently trusted) at every chunk write.
"""

import sqlite3

from store.chunks import CHUNK_SIZE_M

PROBE_SCHEMA_VERSION = 1

PROBE_SPACING_M = 100.0

assert CHUNK_SIZE_M % PROBE_SPACING_M == 0, (
    f"CHUNK_SIZE_M ({CHUNK_SIZE_M}) must be an integer multiple of "
    f"PROBE_SPACING_M ({PROBE_SPACING_M}) so chunk edges land on probe grid "
    "cell boundaries"
)

_DDL = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE source (
    id INTEGER PRIMARY KEY,
    name TEXT,
    fetched_at TEXT,
    raw_path TEXT,
    attribution TEXT,
    notes TEXT
);

CREATE TABLE chunk_coverage (
    kind TEXT NOT NULL,
    chunk_ix INTEGER NOT NULL,
    chunk_iz INTEGER NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (kind, chunk_ix, chunk_iz)
) WITHOUT ROWID;

CREATE TABLE grid (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL UNIQUE,
    origin_x REAL NOT NULL,
    origin_z REAL NOT NULL,
    spacing_m REAL NOT NULL,
    source_id INTEGER REFERENCES source(id),
    provenance TEXT,
    stats_json TEXT
);

CREATE TABLE grid_sample (
    grid_id INTEGER NOT NULL,
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    value REAL,
    PRIMARY KEY (grid_id, row, col)
) WITHOUT ROWID;

CREATE TABLE feature (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    chunk_ix INTEGER NOT NULL,
    chunk_iz INTEGER NOT NULL,
    geom_type TEXT,
    geom_json TEXT,
    name TEXT,
    subtype TEXT,
    tags_json TEXT,
    source_id INTEGER REFERENCES source(id),
    source_ref TEXT,
    provenance_json TEXT,
    confidence_json TEXT,
    position_uncertainty_m REAL
);

CREATE VIRTUAL TABLE feature_bbox USING rtree(
    id,
    min_x, max_x,
    min_z, max_z
);
"""


def create_probe_schema(conn: sqlite3.Connection) -> None:
    """Create all probe-store tables on an empty connection and record
    `PROBE_SCHEMA_VERSION` in `meta`. Raises `sqlite3.OperationalError` if
    the schema already exists. Unlike `store.schema.create_schema`, this is
    called only once per probe-store *file* (see `writer.open_probe_store`
    -- the probe store accumulates across calls, it is never deleted and
    recreated)."""
    conn.executescript(_DDL)
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
        (str(PROBE_SCHEMA_VERSION),),
    )
    conn.commit()


def check_probe_schema_version(conn: sqlite3.Connection, schema: str = "main") -> None:
    """Raise `ValueError` if the probe store's `schema_version` does not
    match this code's `PROBE_SCHEMA_VERSION`.

    `schema` selects which attached database's `meta` table to read --
    `"main"` for a bare probe-store connection (`writer.open_probe_store`),
    or the alias a caller `ATTACH`ed the probe store under (e.g. `"probe"`
    in `query.describe.describe_position`).
    """
    row = conn.execute(
        f"SELECT value FROM {schema}.meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        raise ValueError(
            f"Database (schema={schema!r}) has no 'schema_version' meta row "
            "-- not a valid probe store"
        )
    stored_version = int(row[0])
    if stored_version != PROBE_SCHEMA_VERSION:
        raise ValueError(
            f"Probe store schema_version {stored_version} does not match "
            f"code's PROBE_SCHEMA_VERSION {PROBE_SCHEMA_VERSION} -- rebuild "
            "is not possible (the probe store is not rebuildable from raw "
            "data); this is a hard incompatibility"
        )
