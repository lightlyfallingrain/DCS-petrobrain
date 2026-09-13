"""Tests for `store.reader` -- most importantly, that the R*Tree-pruned
`nearest_feature` agrees with a brute-force scan over the same synthetic
feature set. The brute-force reference lives here, not in `src/`, per
`plans/m5-first-persistent-model/plan.md`'s test spec: "this is how an
index is kept honest."
"""

import random
import sqlite3
from pathlib import Path

import pytest

from geometry import distance_point_point, distance_point_polyline, point_in_polygon
from store.models import ElevationGrid, StoredFeature, SurfaceGrid
from store.reader import (
    containing_polygons,
    grid_provenance,
    load_full_grid,
    nearest_feature,
    sample_grid,
)
from store.writer import insert_features, insert_grid, open_for_build


def _point_feature(
    feature_id_hint: int, x: float, z: float, kind: str = "named_place"
) -> StoredFeature:
    return StoredFeature(
        kind=kind,
        geom_type="Point",
        geometry=[(x, z)],
        name=f"point-{feature_id_hint}",
        subtype=None,
        tags={},
        source_id=None,
        source_ref=None,
        provenance={"geometry": "dcs"},
        confidence={"geometry": "high"},
        position_uncertainty_m=0.0,
    )


def _line_feature(
    feature_id_hint: int, points: list[tuple[float, float]], kind: str = "road"
) -> StoredFeature:
    return StoredFeature(
        kind=kind,
        geom_type="LineString",
        geometry=points,
        name=f"line-{feature_id_hint}",
        subtype=None,
        tags={},
        source_id=None,
        source_ref=None,
        provenance={"geometry": "dcs"},
        confidence={"geometry": "high"},
        position_uncertainty_m=0.0,
    )


def _brute_force_nearest(
    query: tuple[float, float], features: list[StoredFeature]
) -> tuple[StoredFeature, float]:
    best_feature = None
    best_distance = None
    for feature in features:
        if feature.geom_type == "Point":
            distance = distance_point_point(query, feature.geometry[0])
        elif feature.geom_type == "LineString":
            distance = distance_point_polyline(query, feature.geometry)
        else:
            ring = feature.geometry
            if ring[0] != ring[-1]:
                ring = [*ring, ring[0]]
            distance = (
                0.0
                if point_in_polygon(query, feature.geometry)
                else distance_point_polyline(query, ring)
            )
        if best_distance is None or distance < best_distance:
            best_feature, best_distance = feature, distance
    assert best_feature is not None
    assert best_distance is not None
    return best_feature, best_distance


def _build_synthetic_store(
    tmp_path: Path, features: list[StoredFeature]
) -> sqlite3.Connection:
    db_path = tmp_path / "synthetic.sqlite"
    conn = open_for_build(db_path)
    insert_features(conn, features)
    return conn


def test_nearest_feature_agrees_with_brute_force_over_random_points(
    tmp_path: Path,
) -> None:
    rng = random.Random(42)
    features = [
        _point_feature(i, rng.uniform(-5000, 5000), rng.uniform(-5000, 5000))
        for i in range(200)
    ]
    conn = _build_synthetic_store(tmp_path, features)
    try:
        for i in range(50):
            query = (rng.uniform(-6000, 6000), rng.uniform(-6000, 6000))
            indexed = nearest_feature(conn, ["named_place"], query[0], query[1])
            brute = _brute_force_nearest(query, features)

            assert indexed is not None
            indexed_feature, indexed_distance = indexed
            brute_feature, brute_distance = brute

            assert indexed_feature.name == brute_feature.name
            assert abs(indexed_distance - brute_distance) < 1e-6
    finally:
        conn.close()


def test_nearest_feature_agrees_with_brute_force_mixed_geometry(tmp_path: Path) -> None:
    rng = random.Random(7)
    features: list[StoredFeature] = []
    for i in range(50):
        cx, cz = rng.uniform(-5000, 5000), rng.uniform(-5000, 5000)
        features.append(_point_feature(i, cx, cz, kind="mixed"))
    for i in range(50):
        cx, cz = rng.uniform(-5000, 5000), rng.uniform(-5000, 5000)
        points = [(cx, cz), (cx + rng.uniform(-200, 200), cz + rng.uniform(-200, 200))]
        features.append(_line_feature(100 + i, points, kind="mixed"))

    conn = _build_synthetic_store(tmp_path, features)
    try:
        for i in range(30):
            query = (rng.uniform(-6000, 6000), rng.uniform(-6000, 6000))
            indexed = nearest_feature(conn, ["mixed"], query[0], query[1])
            brute = _brute_force_nearest(query, features)

            assert indexed is not None
            _, indexed_distance = indexed
            _, brute_distance = brute
            assert abs(indexed_distance - brute_distance) < 1e-6
    finally:
        conn.close()


def test_nearest_feature_returns_none_beyond_max_radius(tmp_path: Path) -> None:
    conn = _build_synthetic_store(tmp_path, [_point_feature(0, 0.0, 0.0)])
    try:
        result = nearest_feature(
            conn, ["named_place"], 100000.0, 100000.0, max_radius_m=500.0
        )
        assert result is None
    finally:
        conn.close()


def test_nearest_feature_filters_by_provenance_geometry(tmp_path: Path) -> None:
    dcs_road = StoredFeature(
        kind="road",
        geom_type="LineString",
        geometry=[(0.0, 0.0), (100.0, 0.0)],
        name=None,
        subtype=None,
        tags={},
        source_id=None,
        source_ref=None,
        provenance={"geometry": "dcs"},
        confidence={"geometry": "high"},
        position_uncertainty_m=0.0,
    )
    osm_road = StoredFeature(
        kind="road",
        geom_type="LineString",
        geometry=[(10.0, 5.0), (110.0, 5.0)],
        name="OSM Road",
        subtype="service",
        tags={},
        source_id=None,
        source_ref=None,
        provenance={"geometry": "osm"},
        confidence={"geometry": "medium"},
        position_uncertainty_m=1300.0,
    )
    conn = _build_synthetic_store(tmp_path, [dcs_road, osm_road])
    try:
        dcs_match = nearest_feature(
            conn, ["road"], 50.0, 5.0, provenance_geometry="dcs"
        )
        osm_match = nearest_feature(
            conn, ["road"], 50.0, 5.0, provenance_geometry="osm"
        )

        assert dcs_match is not None and dcs_match[0].provenance["geometry"] == "dcs"
        assert osm_match is not None and osm_match[0].provenance["geometry"] == "osm"
        assert osm_match[0].name == "OSM Road"
    finally:
        conn.close()


def test_containing_polygons_finds_point_inside_and_not_outside(tmp_path: Path) -> None:
    square = StoredFeature(
        kind="settlement",
        geom_type="Polygon",
        geometry=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
        name="Square Town",
        subtype="residential",
        tags={},
        source_id=None,
        source_ref=None,
        provenance={"geometry": "osm"},
        confidence={"geometry": "medium"},
        position_uncertainty_m=1300.0,
    )
    conn = _build_synthetic_store(tmp_path, [square])
    try:
        inside = containing_polygons(conn, ["settlement"], 50.0, 50.0)
        outside = containing_polygons(conn, ["settlement"], 500.0, 500.0)

        assert len(inside) == 1 and inside[0].name == "Square Town"
        assert outside == []
    finally:
        conn.close()


# --- inner_rings (holes, osm-landcover-optimization) ------------------


def _ringed_polygon() -> StoredFeature:
    """A 100x100 outer square with a 30x30 hole in the middle
    (30,30)-(60,60) -- the fixture both `containing_polygons` and
    `nearest_feature`/`_distance_to_feature`'s hole-aware tests below share."""
    return StoredFeature(
        kind="landcover",
        geom_type="Polygon",
        geometry=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
        name=None,
        subtype="forest",
        tags={
            "area_m2": 9100.0,
            "inner_rings": [[[30.0, 30.0], [60.0, 30.0], [60.0, 60.0], [30.0, 60.0]]],
        },
        source_id=None,
        source_ref=None,
        provenance={"geometry": "osm"},
        confidence={"geometry": "medium"},
        position_uncertainty_m=1300.0,
    )


def test_containing_polygons_excludes_a_point_inside_a_hole(tmp_path: Path) -> None:
    conn = _build_synthetic_store(tmp_path, [_ringed_polygon()])
    try:
        outside_hole = containing_polygons(conn, ["landcover"], 10.0, 10.0)
        inside_hole = containing_polygons(conn, ["landcover"], 45.0, 45.0)

        assert len(outside_hole) == 1
        assert inside_hole == []
    finally:
        conn.close()


def test_nearest_feature_reports_zero_distance_outside_the_hole(
    tmp_path: Path,
) -> None:
    conn = _build_synthetic_store(tmp_path, [_ringed_polygon()])
    try:
        match = nearest_feature(conn, ["landcover"], 10.0, 10.0)
        assert match is not None
        _, distance = match
        assert distance == 0.0
    finally:
        conn.close()


def test_nearest_feature_measures_distance_to_the_hole_ring_when_inside_it(
    tmp_path: Path,
) -> None:
    conn = _build_synthetic_store(tmp_path, [_ringed_polygon()])
    try:
        # Dead centre of the hole -- nearest hole edge is 15m away in any
        # direction; must not report 0.0 (that would mean "inside the
        # polygon"), and must not report distance to the *outer* ring.
        match = nearest_feature(conn, ["landcover"], 45.0, 45.0)
        assert match is not None
        _, distance = match
        assert distance == pytest.approx(15.0)
    finally:
        conn.close()


def test_sample_grid_elevation_bilinear_interpolation(tmp_path: Path) -> None:
    db_path = tmp_path / "grid.sqlite"
    conn = open_for_build(db_path)
    try:
        # 2x2 grid, spacing 100m, corner values chosen so bilinear
        # interpolation at the centre is easy to hand-verify: mean of the
        # four corners.
        grid = ElevationGrid(
            origin_x=0.0,
            origin_z=0.0,
            spacing_m=100.0,
            n_rows=2,
            n_cols=2,
            source_id=None,
            provenance="dcs_probe",
            stats={},
            samples=[[0.0, 100.0], [200.0, 300.0]],
        )
        insert_grid(conn, grid)

        centre_value = sample_grid(conn, "elevation", 50.0, 50.0)
        assert centre_value is not None
        assert abs(centre_value - 150.0) < 1e-9

        corner_value = sample_grid(conn, "elevation", 0.0, 0.0)
        assert corner_value == 0.0

        outside_value = sample_grid(conn, "elevation", -10.0, 0.0)
        assert outside_value is None
    finally:
        conn.close()


def test_sample_grid_surface_type_nearest_cell_not_interpolated(tmp_path: Path) -> None:
    db_path = tmp_path / "grid.sqlite"
    conn = open_for_build(db_path)
    try:
        grid = SurfaceGrid(
            origin_x=0.0,
            origin_z=0.0,
            spacing_m=100.0,
            n_rows=2,
            n_cols=2,
            source_id=None,
            provenance="dcs_probe",
            stats={},
            samples=[[1, 3], [4, 5]],  # LAND, WATER / ROAD, RUNWAY
        )
        insert_grid(conn, grid)

        # Nearest-cell, not interpolated: a point closer to the (0,0)=LAND
        # cell than any other must return exactly 1.0, not an averaged
        # value.
        near_land = sample_grid(conn, "surface_type", 10.0, 10.0)
        assert near_land == 1.0
    finally:
        conn.close()


def test_load_full_grid_returns_whole_matrix(tmp_path: Path) -> None:
    db_path = tmp_path / "grid.sqlite"
    conn = open_for_build(db_path)
    try:
        grid = ElevationGrid(
            origin_x=0.0,
            origin_z=0.0,
            spacing_m=100.0,
            n_rows=2,
            n_cols=2,
            source_id=None,
            provenance="srtm",
            stats={"points_expected": 4, "points_received": 4},
            samples=[[0.0, 100.0], [200.0, 300.0]],
        )
        insert_grid(conn, grid)

        loaded = load_full_grid(conn, "elevation")

        assert loaded is not None
        assert loaded.n_rows == 2
        assert loaded.n_cols == 2
        assert loaded.spacing_m == 100.0
        assert loaded.samples == [[0.0, 100.0], [200.0, 300.0]]
        assert loaded.stats == {"points_expected": 4, "points_received": 4}
        # Provenance must round-trip byte-for-byte, not just spacing/samples
        # -- see store/schema.py's version-3 note.
        assert loaded.provenance == "srtm"
    finally:
        conn.close()


def test_load_full_grid_leaves_missing_cells_none(tmp_path: Path) -> None:
    db_path = tmp_path / "grid.sqlite"
    conn = open_for_build(db_path)
    try:
        grid = ElevationGrid(
            origin_x=0.0,
            origin_z=0.0,
            spacing_m=100.0,
            n_rows=2,
            n_cols=2,
            source_id=None,
            provenance="dcs_probe",
            stats={},
            samples=[[0.0, None], [200.0, 300.0]],
        )
        insert_grid(conn, grid)

        loaded = load_full_grid(conn, "elevation")

        assert loaded is not None
        assert loaded.samples == [[0.0, None], [200.0, 300.0]]
    finally:
        conn.close()


def test_load_full_grid_returns_none_when_absent(tmp_path: Path) -> None:
    db_path = tmp_path / "grid.sqlite"
    conn = open_for_build(db_path)
    try:
        assert load_full_grid(conn, "elevation") is None
    finally:
        conn.close()


def test_grid_provenance_distinguishes_srtm_from_dcs_probe(tmp_path: Path) -> None:
    """The provenance invariant this module exists to enforce (M7 Stage 2,
    per `store/schema.py`'s version-3 note): an `elevation` grid built from
    SRTM and a `surface_type` grid built from the DCS live probe must each
    report their own real source, never a shared/hardcoded label -- this is
    what `query.describe.describe_position`'s `elevation.source`/
    `surface_type.provenance` fields read to answer that honestly."""
    db_path = tmp_path / "grid.sqlite"
    conn = open_for_build(db_path)
    try:
        insert_grid(
            conn,
            ElevationGrid(
                origin_x=0.0,
                origin_z=0.0,
                spacing_m=1000.0,
                n_rows=1,
                n_cols=1,
                source_id=None,
                provenance="srtm",
                stats={},
                samples=[[500.0]],
            ),
        )
        insert_grid(
            conn,
            SurfaceGrid(
                origin_x=0.0,
                origin_z=0.0,
                spacing_m=500.0,
                n_rows=1,
                n_cols=1,
                source_id=None,
                provenance="dcs_probe",
                stats={},
                samples=[[1]],
            ),
        )

        assert grid_provenance(conn, "elevation") == "srtm"
        assert grid_provenance(conn, "surface_type") == "dcs_probe"
        # The two grid kinds' provenance must never be conflated into one
        # value, even though both live in the same `grid` table.
        assert grid_provenance(conn, "elevation") != grid_provenance(
            conn, "surface_type"
        )
    finally:
        conn.close()


def test_grid_provenance_returns_none_when_absent(tmp_path: Path) -> None:
    db_path = tmp_path / "grid.sqlite"
    conn = open_for_build(db_path)
    try:
        assert grid_provenance(conn, "elevation") is None
    finally:
        conn.close()
