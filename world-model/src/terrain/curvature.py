"""Landform-scale grid smoothing and basin-seed detection over a stored
elevation grid -- the first two steps of Stage 1's Option C (marker-
controlled watershed), per `plans/terrain-feature-probing/plan.md`.

Supersedes the per-cell discrete-Laplacian `classify_curvature`/
`CellCurvature`/`CurvatureClass` (removed): `research/2026-10-01-terrain-
features-full-build-inspection.md` found that mechanism measures
break-of-slope, not landform bodies -- a hill's own toe is genuinely
concave regardless of resolution, so it always pairs a parasitic `valley`
line along every `ridge`'s foot, and it has no notion of a basin's own
width or relief amplitude, so it cannot express the user's Bekaa-exclusion
rule (a kilometres-wide flat basin is not what a pilot means by "valley" at
Mi-24 flight-profile scale) as anything but a bolted-on second heuristic.

`numpy`/`scipy` are new `world-model` dependencies, scoped narrowly to this
module's two steps only (see `pyproject.toml`'s comment and the plan's
"New dependency" section) -- vectorized O(n) operations over a ~2.5M-cell
theatre grid where a hand-rolled nested loop would dominate the pipeline's
runtime for no benefit over a well-tested library call doing exactly this.
Basin growth (`terrain.features.grow_basins`) and axis/boundary extraction
stay stdlib, unchanged from before -- this is not blanket permission to
reach for numpy elsewhere in `world-model`.

Both functions are NaN/gap-aware in the same spirit as the old
`classify_curvature`'s "never fabricate from missing data" rule, loosened
from "every neighbour sampled" (an edge-sensitive derivative's requirement)
to "a majority of the window sampled" (an average's requirement, per the
plan's point 1): a cell whose smoothing window was mostly unsampled becomes
`None` rather than an average of too few real points.
"""

from dataclasses import replace

import numpy as np
from scipy import ndimage

from store.models import ElevationGrid

# Tuned by looking at real `latakia-20km`/Baalbek/Palmyra output
# (`research/2026-10-01-terrain-feature-probing-watershed-sweep.md`) at a
# processing spacing of 500 m -- a 3x3 window (1.5 km across at 500 m)
# smooths out 500 m cell-to-cell SRTM roughness while keeping genuine
# kilometre-scale relief distinct. Windows of 4+ cells collapse an entire
# 20 km test region into 1-2 basins (over-smoothed); 2 cells reproduces
# much of the old checkerboard noise as many small basins. See that note
# for the full sweep and the values rejected.
DEFAULT_SMOOTHING_WINDOW_CELLS = 3

# Footprint radius (in cells) `scipy.ndimage.minimum_filter` searches around
# each cell when deciding whether it is a *regional* minimum, not just a
# single noisy dip -- same window as the smoothing step, so a basin seed is
# never finer-grained than the surface it is seeded on.
DEFAULT_SEED_FOOTPRINT_CELLS = 3

# A cell needs at least this fraction of its smoothing window actually
# sampled to get a smoothed value at all -- "a majority of the window", per
# the plan's point 1 (loosened from `classify_curvature`'s "all four
# neighbours", since this is an average, not an edge-sensitive derivative).
DEFAULT_MIN_VALID_FRACTION = 0.5


def _grid_to_arrays(
    grid: ElevationGrid,
) -> tuple[np.typing.NDArray[np.float64], np.typing.NDArray[np.bool_]]:
    """`grid.samples` as a `(values, valid_mask)` pair of plain numpy
    arrays -- `values` holds `0.0` wherever `valid_mask` is `False`, so it
    is never read without checking the mask first."""
    valid = np.array(
        [[sample is not None for sample in row] for row in grid.samples],
        dtype=np.bool_,
    )
    values = np.array(
        [
            [sample if sample is not None else 0.0 for sample in row]
            for row in grid.samples
        ],
        dtype=np.float64,
    )
    return values, valid


def smooth_grid(
    grid: ElevationGrid,
    window_cells: int = DEFAULT_SMOOTHING_WINDOW_CELLS,
    min_valid_fraction: float = DEFAULT_MIN_VALID_FRACTION,
) -> ElevationGrid:
    """Box-smooth `grid` at a `window_cells` x `window_cells` footprint,
    gap-aware: the value and the sampled-mask are each box-filtered
    separately (`scipy.ndimage.uniform_filter`, which computes a mean, not
    a sum) and divided, so a cell's smoothed value is the mean of only the
    window's actually-sampled cells, never diluted by treating a gap as
    `0.0`. A cell whose window was sampled below `min_valid_fraction`
    becomes `None` rather than an average of too few real points.

    Returns a new `ElevationGrid` of the same shape/origin/spacing --
    `smooth_grid`'s output is itself a valid `ElevationGrid`, consumed by
    `find_basin_seeds` and `terrain.features.grow_basins` alike."""
    values, valid = _grid_to_arrays(grid)
    mask = valid.astype(np.float64)

    sum_values = ndimage.uniform_filter(
        values * mask, size=window_cells, mode="constant", cval=0.0
    )
    sum_mask = ndimage.uniform_filter(
        mask, size=window_cells, mode="constant", cval=0.0
    )

    with np.errstate(invalid="ignore", divide="ignore"):
        smoothed = sum_values / sum_mask
    keep = sum_mask >= min_valid_fraction

    samples: list[list[float | None]] = [
        [
            float(smoothed[row, col]) if keep[row, col] else None
            for col in range(grid.n_cols)
        ]
        for row in range(grid.n_rows)
    ]
    return replace(grid, samples=samples)


def find_basin_seeds(
    grid: ElevationGrid,
    footprint_cells: int = DEFAULT_SEED_FOOTPRINT_CELLS,
) -> list[tuple[int, int]]:
    """Regional minima of `grid` (typically `smooth_grid`'s output) at a
    `footprint_cells` x `footprint_cells` neighbourhood -- the standard
    marker-controlled-watershed seed input (`scipy.ndimage.minimum_filter`).
    Unsampled cells never qualify and never contribute their absence as a
    fake "very low" value: they are excluded from the filter's input by
    setting them to `+inf`, which can never be a window minimum."""
    values, valid = _grid_to_arrays(grid)
    searched = np.where(valid, values, np.inf)

    local_min = ndimage.minimum_filter(
        searched, size=footprint_cells, mode="constant", cval=np.inf
    )
    is_seed = valid & (searched == local_min)

    rows, cols = np.nonzero(is_seed)
    return list(zip(rows.tolist(), cols.tolist(), strict=True))
