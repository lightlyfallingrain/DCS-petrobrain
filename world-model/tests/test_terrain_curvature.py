"""Synthetic control-point tests for `terrain.curvature.classify_curvature`.

Hand-built 7x7 grids each encode one known feature -- a straight, row-3
ridge and a straight, row-3 valley -- via
`height(row, col) = 100 + 5*row (+/-) 10*abs(row - 3) + 2*col`. The `5*row`
and `2*col` terms are both linear in one axis; the discrete Laplacian of any
linear function is exactly zero, so they contribute nothing to curvature
while still giving the fixture non-constant elevation along the feature (see
`test_terrain_features.py`, which asserts `elevation_range_m` against this
same fixture). This isolates "does the classifier recover the known
feature's shape" from "does elevation vary along it" -- the algorithm's
"known control point" analogue to M1's coordinate control points, per the
plan's Stage 1 item.

`_TEST_THRESHOLD_M` is deliberately independent of
`curvature.DEFAULT_CURVATURE_THRESHOLD_M` (Stage 2's real-data-tuned
production default) -- this fixture's curvature magnitude (20.0, see
`_grid`'s `10.0 * abs(...)` coefficient) is a fixed algorithm control point,
not something that should silently start failing if the production default
is re-tuned again later.
"""

from store.models import ElevationGrid
from terrain.curvature import CurvatureClass, classify_curvature

_SPACING_M = 100.0
_N = 7
_RIDGE_ROW = 3
_TEST_THRESHOLD_M = 3.0


def _grid(sign: float) -> ElevationGrid:
    samples: list[list[float | None]] = [
        [
            100.0 + 5.0 * row + sign * 10.0 * abs(row - _RIDGE_ROW) + 2.0 * col
            for col in range(_N)
        ]
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


def test_classify_curvature_recovers_row_ridge() -> None:
    grid = _ridge_grid()

    cells = classify_curvature(grid, threshold_m=_TEST_THRESHOLD_M)
    ridge_cells = {
        (c.row, c.col) for c in cells if c.classification == CurvatureClass.RIDGE
    }

    assert ridge_cells == {(_RIDGE_ROW, col) for col in range(1, _N - 1)}


def test_classify_curvature_recovers_row_valley() -> None:
    grid = _valley_grid()

    cells = classify_curvature(grid, threshold_m=_TEST_THRESHOLD_M)
    valley_cells = {
        (c.row, c.col) for c in cells if c.classification == CurvatureClass.VALLEY
    }

    assert valley_cells == {(_RIDGE_ROW, col) for col in range(1, _N - 1)}


def test_classify_curvature_off_feature_cells_are_neither() -> None:
    grid = _ridge_grid()

    cells = classify_curvature(grid, threshold_m=_TEST_THRESHOLD_M)
    off_ridge = [c for c in cells if c.row != _RIDGE_ROW]

    assert all(c.classification == CurvatureClass.NEITHER for c in off_ridge)


def test_classify_curvature_skips_cells_with_unsampled_neighbours() -> None:
    grid = _ridge_grid()
    samples = [list(row) for row in grid.samples]
    samples[_RIDGE_ROW][2] = None
    grid_with_gap = ElevationGrid(
        origin_x=grid.origin_x,
        origin_z=grid.origin_z,
        spacing_m=grid.spacing_m,
        n_rows=grid.n_rows,
        n_cols=grid.n_cols,
        source_id=None,
        provenance="dcs_probe",
        stats={},
        samples=samples,
    )

    cells = classify_curvature(grid_with_gap, threshold_m=_TEST_THRESHOLD_M)
    classified_rc = {(c.row, c.col) for c in cells}

    # Every interior cell whose 4-neighbor window touches the gap at
    # (_RIDGE_ROW, 2) must be skipped entirely, not classified from a
    # fabricated value -- including the gap cell itself.
    assert (_RIDGE_ROW, 2) not in classified_rc
    assert (_RIDGE_ROW, 1) not in classified_rc  # east neighbour is the gap
    assert (_RIDGE_ROW, 3) not in classified_rc  # west neighbour is the gap
    assert (_RIDGE_ROW - 1, 2) not in classified_rc  # south neighbour is the gap
    assert (_RIDGE_ROW + 1, 2) not in classified_rc  # north neighbour is the gap
