"""Vectorised geomorphons classification -- Stage A of
`plans/landform-geomorphons/plan.md`.

A NaN/void-aware port of `tools/spike_geomorphons.py`'s `geomorphons()`
(branch `spike/terrain-detection-resolution`, commit `2ae0b3e`) -- the
mechanism the user accepted from its rendered output, replacing the
retired marker-controlled-watershed detector (`terrain.curvature`/
`terrain.features`'s basin-growth pipeline, deleted). Classifies each cell
of a DEM array directly against its own neighbourhood (Jasiewicz &
Stepinski 2013's ten-class geomorphon scheme), with no pre-smoothing pass
-- unlike the watershed mechanism, geomorphons has no basin-seeding step.

`dem` is a plain `float64` array with `NaN` marking a void or unsampled
cell (this module's own convention, matching every other ingest module's
"absence reported as absence" rule -- never a sentinel value). The eight
compass directions are walked out to `lookup_cells`, exactly as the
spike's `DIRS`/loop did; the only behavioural change here is vectorising
every per-cell Python loop into whole-array numpy operations, per the
plan's design decision 3 ("vectorise in-house, no new dependency") applied
to this module too -- the direction/lookup-distance loops stay (16 passes
worst case: 8 directions x bounded by `lookup_cells`, same iteration count
the spike already had), but every per-cell operation inside them is now a
single array expression rather than a nested Python loop over rows/cols.
"""

import math

import numpy as np
import numpy.typing as npt

# The ten geomorphon classes (Jasiewicz & Stepinski 2013), same ordering
# and names as the spike. `FLAT` doubles as "no classification" (also what
# a void/unsampled cell gets, see `geomorphons`'s final step) -- this
# module never emits `0`, since every real class is `>= FLAT == 1`; `0`
# unambiguously means "not classified".
FLAT, PEAK, RIDGE, SHOULDER, SPUR, SLOPE, HOLLOW, FOOTSLOPE, VALLEY, PIT = range(1, 11)

# The two feature families this plan extracts lines for (plan design
# decision 4) -- ridge lines from `ridge`+`peak` cells, valley lines from
# `valley`+`pit` cells. `spur`/`hollow` are deferred (plan point 7).
RIDGE_KINDS = (RIDGE, PEAK)
VALLEY_KINDS = (VALLEY, PIT)

# Compass directions walked for each cell: (d_row, d_col), N/NE/E/SE/S/SW/W/NW.
_DIRS = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]

# `_LOOKUP[plus][minus]` -> geomorphon class, `-1` for an unreachable
# combination (kept so a drive-by edit that produces one fails loudly
# rather than silently becoming `FLAT`). Verbatim from the spike.
_LOOKUP = np.array(
    [
        [FLAT, FLAT, FLAT, FOOTSLOPE, FOOTSLOPE, VALLEY, VALLEY, VALLEY, PIT],
        [FLAT, FLAT, FOOTSLOPE, FOOTSLOPE, FOOTSLOPE, VALLEY, VALLEY, VALLEY, -1],
        [FLAT, SHOULDER, SLOPE, SLOPE, HOLLOW, HOLLOW, VALLEY, -1, -1],
        [SHOULDER, SHOULDER, SLOPE, SLOPE, SLOPE, HOLLOW, -1, -1, -1],
        [SHOULDER, SHOULDER, SPUR, SLOPE, SLOPE, SLOPE, -1, -1, -1],
        [RIDGE, RIDGE, SPUR, SPUR, SLOPE, SLOPE, -1, -1, -1],
        [RIDGE, RIDGE, RIDGE, SPUR, SPUR, -1, -1, -1, -1],
        [RIDGE, RIDGE, RIDGE, RIDGE, -1, -1, -1, -1, -1],
        [PEAK, RIDGE, RIDGE, -1, -1, -1, -1, -1, -1],
    ],
    dtype=np.int64,
)

# Tuned against the accepted coastal-hills render (`tools/
# spike_junction_walk.py`'s module docstring): lookup radius 15 cells
# (~1.35 km at the 90m default lattice spacing), flatness tolerance 1 deg.
DEFAULT_LOOKUP_CELLS = 15
DEFAULT_FLAT_DEG = 1.0

# Sentinel the direction loop uses for "no real angle seen yet in this
# direction" -- must be far below any real `arctan` output (bounded to
# [-pi/2, pi/2]) so it never wins a `fmax` against a real angle.
_NO_ANGLE = -9e9


def geomorphons(
    dem: npt.NDArray[np.float64],
    spacing_m: float,
    lookup_cells: int = DEFAULT_LOOKUP_CELLS,
    flat_deg: float = DEFAULT_FLAT_DEG,
) -> npt.NDArray[np.int64]:
    """Classify every cell of `dem` (shape `(n_rows, n_cols)`, `NaN` for a
    void/unsampled cell) into one of the ten geomorphon classes, returning
    an `int64` array of the same shape. A void/unsampled cell (its own
    value is `NaN`) is always classified `0` ("not classified") regardless
    of what its neighbours look like -- a cell with no real elevation of
    its own cannot be meaningfully compared against anything.

    A neighbour cell that is itself a void/unsampled contributes no angle
    in that direction (treated as "never the extreme", matching the
    spike's own `nan_to_num(ang, nan=-9e9)` handling) -- it neither raises
    `plus` nor `minus`, it simply doesn't count, so a cell near a void
    patch is still classified from whichever real neighbours it has.
    """
    n_rows, n_cols = dem.shape
    flat = math.radians(flat_deg)
    plus = np.zeros(dem.shape, dtype=np.int64)
    minus = np.zeros(dem.shape, dtype=np.int64)

    for d_row, d_col in _DIRS:
        zenith = np.full(dem.shape, _NO_ANGLE, dtype=np.float64)
        nadir = np.full(dem.shape, _NO_ANGLE, dtype=np.float64)
        for k in range(1, lookup_cells + 1):
            shifted = np.full(dem.shape, np.nan, dtype=np.float64)
            row0, row1 = max(0, -d_row * k), n_rows - max(0, d_row * k)
            col0, col1 = max(0, -d_col * k), n_cols - max(0, d_col * k)
            shifted[row0:row1, col0:col1] = dem[
                row0 + d_row * k : row1 + d_row * k, col0 + d_col * k : col1 + d_col * k
            ]
            with np.errstate(invalid="ignore"):
                angle = np.arctan(
                    (shifted - dem) / (k * spacing_m * math.hypot(d_row, d_col))
                )
            zenith = np.fmax(zenith, np.nan_to_num(angle, nan=_NO_ANGLE))
            nadir = np.fmax(nadir, np.nan_to_num(-angle, nan=_NO_ANGLE))
        plus += (nadir > zenith + flat).astype(np.int64)
        minus += (zenith > nadir + flat).astype(np.int64)

    classes = _LOOKUP[plus, minus]
    classes = np.where(classes > 0, classes, 0)
    classes = np.where(np.isnan(dem), 0, classes)
    return classes.astype(np.int64)
