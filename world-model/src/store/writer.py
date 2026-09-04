"""Write-side primitives for the world-model store.

`insert_features` populates the `feature_bbox` R*Tree in the same
transaction as the `feature` row insert, by explicit SQL rather than a
database trigger -- one place to read this logic, one place to debug it.
Bbox bounds come from `geometry.bbox_of`, the same module `store/reader.py`
uses for its own geometry math, so build-time and query-time bboxes can
never silently disagree.
"""

import json
import sqlite3
from pathlib import Path

from geometry import bbox_of

from .models import ElevationGrid, Region, Source, StoredFeature, SurfaceGrid
from .schema import create_schema


def open_for_build(db_path: Path) -> sqlite3.Connection:
    """Open a fresh `.sqlite` file at `db_path` for a rebuild.

    Deletes any existing file first -- the store is always rebuilt from
    `data/raw/`, never patched in place (see the concept doc's "keep raw
    separate from derived so the database can be rebuilt"). Creates parent
    directories as needed.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    return conn


def insert_source(conn: sqlite3.Connection, source: Source) -> int:
    """Insert a `Source` row and return its assigned id."""
    cursor = conn.execute(
        "INSERT INTO source (name, fetched_at, raw_path, attribution, notes) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            source.name,
            source.fetched_at,
            source.raw_path,
            source.attribution,
            source.notes,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    assert row_id is not None
    return row_id


def insert_region(conn: sqlite3.Connection, region: Region) -> None:
    """Insert (or replace) a `Region` row."""
    conn.execute(
        "INSERT OR REPLACE INTO region "
        "(name, theatre, centre_x, centre_z, half_extent_m, built_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            region.name,
            region.theatre,
            region.centre_x,
            region.centre_z,
            region.half_extent_m,
            region.built_at,
        ),
    )
    conn.commit()


def insert_features(conn: sqlite3.Connection, features: list[StoredFeature]) -> None:
    """Insert `features` and their `feature_bbox` R*Tree rows in one
    transaction. Raises `ValueError` if a feature's `geometry` is empty
    (bbox is undefined)."""
    for feature in features:
        if not feature.geometry:
            raise ValueError(
                f"Cannot insert feature (kind={feature.kind!r}, "
                f"name={feature.name!r}) with empty geometry"
            )
        cursor = conn.execute(
            "INSERT INTO feature "
            "(kind, geom_type, geom_json, name, subtype, tags_json, "
            " source_id, source_ref, provenance_json, confidence_json, "
            " position_uncertainty_m) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                feature.kind,
                feature.geom_type,
                json.dumps([list(p) for p in feature.geometry]),
                feature.name,
                feature.subtype,
                json.dumps(feature.tags),
                feature.source_id,
                feature.source_ref,
                json.dumps(feature.provenance),
                json.dumps(feature.confidence),
                feature.position_uncertainty_m,
            ),
        )
        feature_id = cursor.lastrowid
        assert feature_id is not None

        min_x, max_x, min_z, max_z = bbox_of(feature.geometry)
        conn.execute(
            "INSERT INTO feature_bbox (id, min_x, max_x, min_z, max_z) "
            "VALUES (?, ?, ?, ?, ?)",
            (feature_id, min_x, max_x, min_z, max_z),
        )
    conn.commit()


def insert_grid(conn: sqlite3.Connection, grid: ElevationGrid | SurfaceGrid) -> int:
    """Insert a grid's metadata row and its `grid_sample` cells in one
    transaction. Returns the assigned `grid.id`. `kind` is derived from the
    dataclass type (`'elevation'` for `ElevationGrid`, `'surface_type'` for
    `SurfaceGrid`) so the caller cannot desync the two."""
    kind = "elevation" if isinstance(grid, ElevationGrid) else "surface_type"
    cursor = conn.execute(
        "INSERT INTO grid "
        "(kind, origin_x, origin_z, spacing_m, n_rows, n_cols, source_id, stats_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            kind,
            grid.origin_x,
            grid.origin_z,
            grid.spacing_m,
            grid.n_rows,
            grid.n_cols,
            grid.source_id,
            json.dumps(grid.stats),
        ),
    )
    grid_id = cursor.lastrowid
    assert grid_id is not None

    for row in range(grid.n_rows):
        for col in range(grid.n_cols):
            value = grid.samples[row][col] if row < len(grid.samples) else None
            if value is None:
                continue
            conn.execute(
                "INSERT INTO grid_sample (grid_id, row, col, value) VALUES (?, ?, ?, ?)",
                (grid_id, row, col, float(value)),
            )
    conn.commit()
    return grid_id
