"""Tests for `terrain.features`: connected-component grouping and
principal-axis line extraction over `terrain.curvature`'s per-cell output.

Reuses `test_terrain_curvature.py`'s row-3 ridge/valley fixture shape: a
straight, axis-aligned line is a genuine 4-connected component under
`_connected_components`' 4-connectivity, unlike a diagonal line (whose
cells only touch at corners, not edges) -- picking a diagonal fixture here
would have produced five isolated single-cell "components", not the one
five-cell line this module is meant to recover.
"""

import pytest

from store.models import ElevationGrid
from terrain.curvature import classify_curvature
from terrain.features import extract_components, to_stored_features

_SPACING_M = 100.0
_N = 7
_RIDGE_ROW = 3
_TEST_THRESHOLD_M = 3.0


def _grid(sign: float) -> ElevationGrid:
    samples: list[list[float | None]] = [
        [100.0 + sign * 10.0 * abs(row - _RIDGE_ROW) + 2.0 * col for col in range(_N)]
        for row in range(_N)
    ]
    return ElevationGrid(
        origin_x=0.0,
        origin_z=0.0,
        spacing_m=_SPACING_M,
        n_rows=_N,
        n_cols=_N,
        source_id=None,
        provenance="dcs_probe",
        stats={},
        samples=samples,
    )


def _ridge_grid() -> ElevationGrid:
    return _grid(sign=-1.0)


def _valley_grid() -> ElevationGrid:
    return _grid(sign=1.0)


def test_extract_components_recovers_single_ridge_line() -> None:
    grid = _ridge_grid()
    curvature_cells = classify_curvature(grid, threshold_m=_TEST_THRESHOLD_M)

    components = extract_components(grid, curvature_cells, min_cell_count=4)

    assert len(components) == 1
    component = components[0]
    assert component.kind == "ridge"
    assert len(component.cells) == 5
    assert {(c.row, c.col) for c in component.cells} == {
        (_RIDGE_ROW, col) for col in range(1, _N - 1)
    }


def test_extract_components_ridge_line_runs_east_west() -> None:
    grid = _ridge_grid()
    curvature_cells = classify_curvature(grid, threshold_m=_TEST_THRESHOLD_M)

    [component] = extract_components(grid, curvature_cells, min_cell_count=4)

    # The line runs along the column axis (constant row, varying col) --
    # z is DCS's east component, so this is a pure east-west line, bearing
    # 90 deg (see geometry.bearing_deg's 0=north/90=east convention).
    assert component.orientation_deg == pytest.approx(90.0)


def test_extract_components_elevation_range_matches_fixture() -> None:
    grid = _ridge_grid()
    curvature_cells = classify_curvature(grid, threshold_m=_TEST_THRESHOLD_M)

    [component] = extract_components(grid, curvature_cells, min_cell_count=4)

    # At row=_RIDGE_ROW, height = 100 + 2*col for col in [1, 5].
    assert component.elevation_range_m == pytest.approx((102.0, 110.0))


def test_extract_components_recovers_single_valley_line() -> None:
    grid = _valley_grid()
    curvature_cells = classify_curvature(grid, threshold_m=_TEST_THRESHOLD_M)

    components = extract_components(grid, curvature_cells, min_cell_count=4)

    assert len(components) == 1
    assert components[0].kind == "valley"
    assert len(components[0].cells) == 5


def test_extract_components_drops_components_below_min_cell_count() -> None:
    grid = _ridge_grid()
    curvature_cells = classify_curvature(grid, threshold_m=_TEST_THRESHOLD_M)

    components = extract_components(grid, curvature_cells, min_cell_count=6)

    assert components == []


def test_to_stored_features_shapes_and_provenance() -> None:
    grid = _ridge_grid()
    curvature_cells = classify_curvature(grid, threshold_m=_TEST_THRESHOLD_M)
    components = extract_components(grid, curvature_cells, min_cell_count=4)

    features = to_stored_features(
        components, source_id=7, position_uncertainty_m=grid.spacing_m
    )

    assert len(features) == 1
    feature = features[0]
    assert feature.kind == "ridge"
    assert feature.geom_type == "LineString"
    assert len(feature.geometry) == 5
    assert feature.provenance == {"geometry": "dcs_derived"}
    assert feature.confidence == {"geometry": "low"}
    assert feature.source_id == 7
    assert feature.position_uncertainty_m == grid.spacing_m
    assert feature.tags["cell_count"] == 5
    assert feature.tags["elevation_range_m"] == pytest.approx([102.0, 110.0])
    assert "orientation_deg" in feature.tags
