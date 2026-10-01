"""Tests for `terrain.curvature`'s two Stage 1 (Option C) inputs:
`smooth_grid` (landform-scale, gap-aware box smoothing) and
`find_basin_seeds` (regional-minimum detection over the smoothed grid).

Rewritten (not extended) for the marker-controlled-watershed mechanism --
user-approved, per `plans/terrain-feature-probing/plan.md`'s "Decisions
Requiring User Input": the per-cell discrete-Laplacian `classify_curvature`/
`CellCurvature`/`CurvatureClass` this file used to test no longer exist.

Expected values below are computed by hand against `scipy.ndimage.
uniform_filter`'s/`minimum_filter`'s documented behaviour (`mode="constant"`,
`cval` as given) rather than re-deriving scipy's own correctness -- these
tests check this module's gap-handling and seed logic, not scipy itself.
"""

import pytest

from store.models import ElevationGrid
from terrain.curvature import find_basin_seeds, smooth_grid

_SPACING_M = 100.0


def _grid(samples: list[list[float | None]]) -> ElevationGrid:
    n_rows = len(samples)
    n_cols = len(samples[0])
    return ElevationGrid(
        origin_x=0.0,
        origin_z=0.0,
        spacing_m=_SPACING_M,
        n_rows=n_rows,
        n_cols=n_cols,
        source_id=None,
        provenance="srtm",
        stats={},
        samples=samples,
    )


# 5x5 grid, sequential values 1..25 except the centre, which is a probe
# gap -- chosen so every 3x3 window used below has an easily hand-summed
# value.
_SEQUENTIAL_GRID = [
    [1.0, 2.0, 3.0, 4.0, 5.0],
    [6.0, 7.0, 8.0, 9.0, 10.0],
    [11.0, 12.0, None, 14.0, 15.0],
    [16.0, 17.0, 18.0, 19.0, 20.0],
    [21.0, 22.0, 23.0, 24.0, 25.0],
]


def test_smooth_grid_preserves_shape_origin_and_spacing() -> None:
    grid = _grid(_SEQUENTIAL_GRID)

    smoothed = smooth_grid(grid, window_cells=3)

    assert smoothed.n_rows == grid.n_rows
    assert smoothed.n_cols == grid.n_cols
    assert smoothed.origin_x == grid.origin_x
    assert smoothed.origin_z == grid.origin_z
    assert smoothed.spacing_m == grid.spacing_m


def test_smooth_grid_gap_aware_excludes_unsampled_cell_from_the_average() -> None:
    grid = _grid(_SEQUENTIAL_GRID)

    smoothed = smooth_grid(grid, window_cells=3, min_valid_fraction=0.5)

    # The 3x3 window around (2, 2) is {7,8,9,12,None,14,17,18,19} -- 8 real
    # samples summing to 104. A gap-aware mean is 104/8 = 13.0; a naive
    # mean that treated the gap as 0.0 would give 104/9 ~= 11.56 instead --
    # this assertion is only satisfied by the gap-aware computation.
    assert smoothed.samples[2][2] == pytest.approx(13.0)


def test_smooth_grid_marks_cell_none_below_min_valid_fraction() -> None:
    grid = _grid(_SEQUENTIAL_GRID)

    # The 3x3 window around the (0, 0) corner only overlaps 4 real grid
    # cells (rows 0-1, cols 0-1); the other 5 window cells fall outside the
    # grid entirely. 4/9 ~= 0.44 is below the default 0.5 threshold.
    smoothed = smooth_grid(grid, window_cells=3, min_valid_fraction=0.5)

    assert smoothed.samples[0][0] is None


def test_smooth_grid_keeps_corner_when_fraction_threshold_is_lowered() -> None:
    grid = _grid(_SEQUENTIAL_GRID)

    # Same corner as above, but a caller willing to accept fewer sampled
    # cells per window gets a value instead of None -- 4/9 clears 0.4.
    smoothed = smooth_grid(grid, window_cells=3, min_valid_fraction=0.4)

    # Window cells actually present: 1, 2, 6, 7 -> mean 4.0.
    assert smoothed.samples[0][0] == pytest.approx(4.0)


def test_smooth_grid_never_fabricates_from_a_fully_unsampled_window() -> None:
    grid = _grid([[None, None, None], [None, None, None], [None, None, None]])

    smoothed = smooth_grid(grid, window_cells=3, min_valid_fraction=0.01)

    assert all(value is None for row in smoothed.samples for value in row)


def test_find_basin_seeds_recovers_a_single_bowl_minimum() -> None:
    samples: list[list[float | None]] = [
        [float((row - 2) ** 2 + (col - 2) ** 2) for col in range(5)] for row in range(5)
    ]
    grid = _grid(samples)

    seeds = find_basin_seeds(grid, footprint_cells=5)

    assert seeds == [(2, 2)]


def test_find_basin_seeds_never_returns_an_unsampled_cell() -> None:
    samples: list[list[float | None]] = [
        [float((row - 2) ** 2 + (col - 2) ** 2) for col in range(5)] for row in range(5)
    ]
    samples[2][2] = None  # the true minimum is now a gap
    grid = _grid(samples)

    seeds = find_basin_seeds(grid, footprint_cells=5)

    # The gap is never a seed (never treated as a fabricated low value);
    # the four cells at distance 1 (value 1.0) become the new regional
    # minima instead.
    assert (2, 2) not in seeds
    assert set(seeds) == {(1, 2), (3, 2), (2, 1), (2, 3)}


def test_find_basin_seeds_plateau_returns_every_candidate_cell() -> None:
    # A flat-bottomed dip: find_basin_seeds does no merging of its own --
    # that is terrain.features._seed_groups's job (tested in
    # test_terrain_features.py) -- so every plateau cell that is its own
    # neighbourhood's minimum comes back.
    grid = _grid([[5.0, 0.0, 0.0, 0.0, 5.0]])

    seeds = find_basin_seeds(grid, footprint_cells=3)

    assert set(seeds) == {(0, 1), (0, 2), (0, 3)}
