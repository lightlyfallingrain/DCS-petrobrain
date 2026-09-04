"""SQL DDL for the world-model SQLite store, and schema-version discipline.

`SCHEMA_VERSION` is bumped whenever the DDL below changes in an
incompatible way. Because the database is always rebuilt from `data/raw/`
(never hand-edited), a version mismatch is not a migration problem -- it is
a signal that the `.sqlite` file on disk predates the code reading it and
must be rebuilt.
"""

import sqlite3

SCHEMA_VERSION = 1

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

CREATE TABLE region (
    name TEXT PRIMARY KEY,
    theatre TEXT,
    centre_x REAL,
    centre_z REAL,
    half_extent_m REAL,
    built_at TEXT
);

CREATE TABLE feature (
    id INTEGER PRIMARY KEY,
    kind TEXT,
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

CREATE TABLE grid (
    id INTEGER PRIMARY KEY,
    kind TEXT,
    origin_x REAL,
    origin_z REAL,
    spacing_m REAL,
    n_rows INT,
    n_cols INT,
    source_id INTEGER REFERENCES source(id),
    stats_json TEXT
);

CREATE TABLE grid_sample (
    grid_id INT,
    row INT,
    col INT,
    value REAL,
    PRIMARY KEY (grid_id, row, col)
) WITHOUT ROWID;
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables/indexes on an empty connection and record
    `SCHEMA_VERSION` in `meta`. Raises `sqlite3.OperationalError` if the
    schema already exists (callers building a fresh `.sqlite` should delete
    any prior file first -- see `build/pipeline.py`'s idempotent rebuild)."""
    conn.executescript(_DDL)
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def check_schema_version(conn: sqlite3.Connection) -> None:
    """Raise `ValueError` if the open database's `schema_version` does not
    match this code's `SCHEMA_VERSION`."""
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    if row is None:
        raise ValueError(
            "Database has no 'schema_version' meta row -- not a valid world-model store"
        )
    stored_version = int(row[0])
    if stored_version != SCHEMA_VERSION:
        raise ValueError(
            f"Database schema_version {stored_version} does not match "
            f"code's SCHEMA_VERSION {SCHEMA_VERSION} -- rebuild the database"
        )
