"""Read-only primitives for the world-model store.

`nearest_feature` and `containing_polygons` both go through `features_in_bbox`,
which is R*Tree-pruned; `nearest_feature`'s expanding-radius search (500 m,
2 km, 8 km, 30 km) exists because a single wide bbox query over a sparse
region wastes work, while a single narrow one may miss the true nearest
feature -- expanding stops as soon as a radius's candidate set contains a
feature whose *exact* geometry distance (not just bbox overlap) is within
that radius. Bbox overlap alone can never miss a feature whose true distance
is within the search radius, because a geometry's own bbox always contains
every point on it (see `test_store_reader.py`'s R*Tree-vs-brute-force
agreement test, which is what keeps this claim honest).
"""

import json
import sqlite3
from dataclasses import dataclass

from geometry import (
    Point,
    distance_point_point,
    distance_point_polyline,
    point_in_polygon,
)

from .models import ElevationGrid, Region, StoredFeature

_EXPANDING_RADII_M = (500.0, 2000.0, 8000.0, 30000.0)


def load_region(conn: sqlite3.Connection, name: str) -> Region | None:
    """Return the built `Region` row named `name`, or `None` if absent."""
    row = conn.execute(
        "SELECT name, theatre, centre_x, centre_z, half_extent_x_m, half_extent_z_m, "
        "built_at FROM region WHERE name = ?",
        (name,),
    ).fetchone()
    if row is None:
        return None
    return Region(
        name=row[0],
        theatre=row[1],
        centre_x=row[2],
        centre_z=row[3],
        half_extent_x_m=row[4],
        half_extent_z_m=row[5],
        built_at=row[6],
    )


def load_only_region(conn: sqlite3.Connection) -> Region | None:
    """Return the single `Region` row in this database, or `None` if the
    `region` table is empty. Each world-model `.sqlite` holds exactly one
    built region (the "one SQLite file per theatre-region" storage
    decision), so `query/describe.py` does not need a region name to answer
    the contract's `region` field."""
    row = conn.execute(
        "SELECT name, theatre, centre_x, centre_z, half_extent_x_m, half_extent_z_m, "
        "built_at FROM region LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return Region(
        name=row[0],
        theatre=row[1],
        centre_x=row[2],
        centre_z=row[3],
        half_extent_x_m=row[4],
        half_extent_z_m=row[5],
        built_at=row[6],
    )


def _row_to_feature(row: tuple[object, ...]) -> StoredFeature:
    (
        feature_id,
        kind,
        geom_type,
        geom_json,
        name,
        subtype,
        tags_json,
        source_id,
        source_ref,
        provenance_json,
        confidence_json,
        position_uncertainty_m,
    ) = row
    assert isinstance(geom_json, str)
    assert isinstance(tags_json, str)
    assert isinstance(provenance_json, str)
    assert isinstance(confidence_json, str)
    geometry: list[Point] = [(pt[0], pt[1]) for pt in json.loads(geom_json)]
    return StoredFeature(
        id=int(feature_id) if isinstance(feature_id, int) else None,
        kind=str(kind),
        geom_type=str(geom_type),
        geometry=geometry,
        name=str(name) if name is not None else None,
        subtype=str(subtype) if subtype is not None else None,
        tags=json.loads(tags_json),
        source_id=int(source_id) if isinstance(source_id, int) else None,
        source_ref=str(source_ref) if source_ref is not None else None,
        provenance=json.loads(provenance_json),
        confidence=json.loads(confidence_json),
        position_uncertainty_m=float(position_uncertainty_m)
        if isinstance(position_uncertainty_m, (int, float))
        else None,
    )


def all_features(
    conn: sqlite3.Connection, kinds: list[str] | None = None
) -> list[StoredFeature]:
    """Return every feature of one of `kinds` (or all kinds), with no bbox
    filtering. Used by `tools/export_geojson.py`, where the whole store is
    always wanted -- an R*Tree query would be pure overhead."""
    query = (
        "SELECT id, kind, geom_type, geom_json, name, subtype, tags_json, "
        "source_id, source_ref, provenance_json, confidence_json, "
        "position_uncertainty_m FROM feature"
    )
    params: list[object] = []
    if kinds is not None:
        placeholders = ",".join("?" for _ in kinds)
        query += f" WHERE kind IN ({placeholders})"
        params.extend(kinds)
    return [_row_to_feature(row) for row in conn.execute(query, params)]


def features_in_bbox(
    conn: sqlite3.Connection,
    kinds: list[str] | None,
    bbox: tuple[float, float, float, float],
) -> list[StoredFeature]:
    """Return every feature of one of `kinds` (or all kinds, if `None`)
    whose stored bbox overlaps `bbox = (min_x, max_x, min_z, max_z)`,
    pruned via the `feature_bbox` R*Tree index."""
    min_x, max_x, min_z, max_z = bbox
    candidate_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM feature_bbox "
            "WHERE max_x >= ? AND min_x <= ? AND max_z >= ? AND min_z <= ?",
            (min_x, max_x, min_z, max_z),
        )
    ]
    if not candidate_ids:
        return []

    placeholders = ",".join("?" for _ in candidate_ids)
    query = (
        "SELECT id, kind, geom_type, geom_json, name, subtype, tags_json, "
        "source_id, source_ref, provenance_json, confidence_json, "
        "position_uncertainty_m FROM feature WHERE id IN "
        f"({placeholders})"
    )
    params: list[object] = list(candidate_ids)
    if kinds is not None:
        kind_placeholders = ",".join("?" for _ in kinds)
        query += f" AND kind IN ({kind_placeholders})"
        params.extend(kinds)

    return [_row_to_feature(row) for row in conn.execute(query, params)]


def _distance_to_feature(x: float, z: float, feature: StoredFeature) -> float:
    point: Point = (x, z)
    if feature.geom_type == "Point":
        return distance_point_point(point, feature.geometry[0])
    if feature.geom_type == "LineString":
        return distance_point_polyline(point, feature.geometry)
    if feature.geom_type == "Polygon":
        if point_in_polygon(point, feature.geometry):
            return 0.0
        ring = feature.geometry
        if ring[0] != ring[-1]:
            ring = [*ring, ring[0]]
        return distance_point_polyline(point, ring)
    raise ValueError(f"Unknown geom_type {feature.geom_type!r}")


def nearest_feature(
    conn: sqlite3.Connection,
    kinds: list[str] | None,
    x: float,
    z: float,
    max_radius_m: float = 30000.0,
    provenance_geometry: str | None = None,
) -> tuple[StoredFeature, float] | None:
    """Find the nearest feature of one of `kinds` to `(x, z)`, searching an
    expanding radius (500 m, 2 km, 8 km, 30 km, capped at `max_radius_m`)
    until a feature whose exact distance is within the current radius is
    found. Returns `(feature, distance_m)`, or `None` if nothing of `kinds`
    lies within `max_radius_m`.

    `provenance_geometry`, if given, restricts candidates to features whose
    `provenance["geometry"]` equals it -- e.g. `query/describe.py` uses this
    to answer `nearest_road` (DCS-only) and `nearest_road_osm` (OSM-only)
    separately even though both share `kind == "road"`.
    """
    radii = [r for r in _EXPANDING_RADII_M if r <= max_radius_m]
    if not radii or radii[-1] < max_radius_m:
        radii.append(max_radius_m)

    for radius in radii:
        candidates = features_in_bbox(
            conn, kinds, (x - radius, x + radius, z - radius, z + radius)
        )
        if provenance_geometry is not None:
            candidates = [
                f
                for f in candidates
                if f.provenance.get("geometry") == provenance_geometry
            ]
        best: StoredFeature | None = None
        best_distance: float | None = None
        for feature in candidates:
            distance = _distance_to_feature(x, z, feature)
            if distance <= radius and (
                best_distance is None or distance < best_distance
            ):
                best, best_distance = feature, distance
        if best is not None:
            assert best_distance is not None
            return best, best_distance
    return None


def containing_polygons(
    conn: sqlite3.Connection, kinds: list[str] | None, x: float, z: float
) -> list[StoredFeature]:
    """Return every `Polygon` feature of one of `kinds` (or all kinds) whose
    ring contains `(x, z)`."""
    candidates = features_in_bbox(conn, kinds, (x, x, z, z))
    return [
        feature
        for feature in candidates
        if feature.geom_type == "Polygon" and point_in_polygon((x, z), feature.geometry)
    ]


@dataclass(frozen=True)
class _GridMeta:
    grid_id: int
    origin_x: float
    origin_z: float
    spacing_m: float
    n_rows: int
    n_cols: int
    source_id: int | None
    provenance: str | None
    stats_json: str


def grid_spacing_m(conn: sqlite3.Connection, grid_kind: str) -> float | None:
    """Return the stored grid's `spacing_m` for `grid_kind`, or `None` if no
    such grid has been built yet. `query/describe.py`'s `surface_type.
    sampled_at_m` uses this so the reported spacing always reflects what was
    actually built, not a hardcoded assumption."""
    meta = _load_grid_meta(conn, grid_kind)
    return None if meta is None else meta.spacing_m


def grid_provenance(conn: sqlite3.Connection, grid_kind: str) -> str | None:
    """Return the stored grid's `provenance` (`"srtm"` or `"dcs_probe"`) for
    `grid_kind`, or `None` if no such grid has been built yet.
    `query/describe.py`'s `elevation.source`/`surface_type.provenance` use
    this instead of a hardcoded label, so a store built from SRTM never gets
    silently reported as DCS-probed or vice versa -- see `store/schema.py`'s
    version-3 note and `store/models.py`'s `ElevationGrid.provenance`.
    `None` for a grid row written before this field existed (schema version
    2 or earlier), which `check_schema_version` already refuses to open, so
    in practice this is only `None` when no grid of `grid_kind` exists."""
    meta = _load_grid_meta(conn, grid_kind)
    return None if meta is None else meta.provenance


def _load_grid_meta(conn: sqlite3.Connection, grid_kind: str) -> _GridMeta | None:
    row = conn.execute(
        "SELECT id, origin_x, origin_z, spacing_m, n_rows, n_cols, source_id, "
        "provenance, stats_json FROM grid WHERE kind = ? ORDER BY id DESC LIMIT 1",
        (grid_kind,),
    ).fetchone()
    if row is None:
        return None
    return _GridMeta(
        grid_id=row[0],
        origin_x=row[1],
        origin_z=row[2],
        spacing_m=row[3],
        n_rows=row[4],
        n_cols=row[5],
        source_id=row[6],
        provenance=row[7],
        stats_json=row[8],
    )


def load_full_grid(conn: sqlite3.Connection, grid_kind: str) -> ElevationGrid | None:
    """Return the full `samples[row][col]` matrix for the most recent grid
    of `grid_kind`, or `None` if no such grid has been built yet.

    Unlike `sample_grid` (single interpolated point lookup), this reads
    every stored `grid_sample` row for the grid in one query -- for
    whole-grid analysis (`terrain.curvature`'s discrete-Laplacian
    classification, M6) rather than per-point queries. Missing cells stay
    `None`, matching `ElevationGrid.samples`' documented shape for a
    partial/sparse grid.
    """
    meta = _load_grid_meta(conn, grid_kind)
    if meta is None:
        return None

    samples: list[list[float | None]] = [
        [None] * meta.n_cols for _ in range(meta.n_rows)
    ]
    for row, col, value in conn.execute(
        "SELECT row, col, value FROM grid_sample WHERE grid_id = ?",
        (meta.grid_id,),
    ):
        samples[row][col] = float(value)

    return ElevationGrid(
        origin_x=meta.origin_x,
        origin_z=meta.origin_z,
        spacing_m=meta.spacing_m,
        n_rows=meta.n_rows,
        n_cols=meta.n_cols,
        source_id=meta.source_id,
        provenance=meta.provenance or "",
        stats=json.loads(meta.stats_json),
        samples=samples,
        id=meta.grid_id,
    )


def _grid_cell_value(
    conn: sqlite3.Connection, grid_id: int, row: int, col: int
) -> float | None:
    result = conn.execute(
        "SELECT value FROM grid_sample WHERE grid_id = ? AND row = ? AND col = ?",
        (grid_id, row, col),
    ).fetchone()
    return None if result is None else float(result[0])


def sample_grid(
    conn: sqlite3.Connection, grid_kind: str, x: float, z: float
) -> float | None:
    """Sample a stored grid at `(x, z)`.

    `grid_kind == "elevation"` uses bilinear interpolation across the four
    surrounding cells (`None` if any corner is unsampled or `(x, z)` falls
    outside the grid's coverage). `grid_kind == "surface_type"` uses
    nearest-cell lookup -- interpolating a categorical enum would be a
    category error, not a more precise answer.
    """
    meta = _load_grid_meta(conn, grid_kind)
    if meta is None:
        return None

    row_f = (x - meta.origin_x) / meta.spacing_m
    col_f = (z - meta.origin_z) / meta.spacing_m
    if not (0.0 <= row_f <= meta.n_rows - 1) or not (0.0 <= col_f <= meta.n_cols - 1):
        return None

    if grid_kind == "surface_type":
        row = round(row_f)
        col = round(col_f)
        return _grid_cell_value(conn, meta.grid_id, row, col)

    r0, c0 = int(row_f), int(col_f)
    r1 = min(r0 + 1, meta.n_rows - 1)
    c1 = min(c0 + 1, meta.n_cols - 1)
    t_row = row_f - r0
    t_col = col_f - c0

    v00 = _grid_cell_value(conn, meta.grid_id, r0, c0)
    v01 = _grid_cell_value(conn, meta.grid_id, r0, c1)
    v10 = _grid_cell_value(conn, meta.grid_id, r1, c0)
    v11 = _grid_cell_value(conn, meta.grid_id, r1, c1)
    if v00 is None or v01 is None or v10 is None or v11 is None:
        return None

    return (
        (1 - t_row) * (1 - t_col) * v00
        + (1 - t_row) * t_col * v01
        + t_row * (1 - t_col) * v10
        + t_row * t_col * v11
    )
