"""Discrete-Laplacian curvature classification over a stored elevation grid.

For every interior cell (edge cells have no full 4-neighbor window, and sit
on the region boundary anyway, not a genuine terrain discontinuity -- they
are excluded, not approximated), computes
`curvature = (north + south + east + west) - 4 * centre`, in metres over one
`spacing_m` step. Positive curvature means the cell sits below its
neighbours on both axes (locally concave -- a valley candidate); negative
curvature means it sits above them (locally convex -- a ridge candidate);
magnitude below `threshold_m` is classified as neither (flat ground or a
simple slope). This is a real, established terrain-analysis technique
(discrete curvature classification), not model inference over the numbers --
see `plans/m6-terrain-semantics/plan.md`'s "Terrain-analysis approach".

A cell with any `None` neighbour (grid edge, or a probe gap) is skipped
entirely rather than approximated -- a curvature value computed from a
missing sample would be a fabricated fact, contrary to the project's "code
owns factual state" invariant.

`DEFAULT_CURVATURE_THRESHOLD_M` was tuned empirically in Stage 2 against
`tools/inspect_terrain.py`'s visual output over the real `latakia-20km`
grid, not guessed blind (per the plan's Stage 2/4 items). The Stage 1
first-guess of 3.0 m classified ~71% of interior cells as ridge/valley over
the region's mountainous (An-Nusayriyah range) north-east quadrant --
visually a near-solid red/blue checkerboard, not usable ridge/valley lines.
Raising the threshold to 20.0 m (~40% of interior cells classified) still
shows real high-frequency alternation across that same rugged terrain, not
a resolution artefact that a slightly higher threshold clears up -- see
`world-model/research/2026-09-05-m6-terrain-semantics.md` for the full
Stage 2/3 findings, including the "checkerboard noise in high-relief
terrain" limitation this value does not eliminate, only reduce to a
workable level.
"""

from dataclasses import dataclass
from enum import Enum

from store.models import ElevationGrid

DEFAULT_CURVATURE_THRESHOLD_M = 20.0


class CurvatureClass(Enum):
    RIDGE = "ridge"
    VALLEY = "valley"
    NEITHER = "neither"


@dataclass(frozen=True)
class CellCurvature:
    """One interior grid cell's discrete-Laplacian curvature value and the
    classification it implies."""

    row: int
    col: int
    curvature_m: float
    classification: CurvatureClass


def classify_curvature(
    grid: ElevationGrid, threshold_m: float = DEFAULT_CURVATURE_THRESHOLD_M
) -> list[CellCurvature]:
    """Classify every interior cell of `grid` that has a fully-sampled
    4-neighbor window. Returns one `CellCurvature` per such cell, including
    `CurvatureClass.NEITHER` ones -- callers filter by classification (see
    `terrain.features.extract_components`)."""
    results: list[CellCurvature] = []
    for row in range(1, grid.n_rows - 1):
        for col in range(1, grid.n_cols - 1):
            centre = grid.samples[row][col]
            north = grid.samples[row - 1][col]
            south = grid.samples[row + 1][col]
            east = grid.samples[row][col + 1]
            west = grid.samples[row][col - 1]
            if (
                centre is None
                or north is None
                or south is None
                or east is None
                or west is None
            ):
                continue

            curvature = (north + south + east + west) - 4.0 * centre
            if curvature > threshold_m:
                classification = CurvatureClass.VALLEY
            elif curvature < -threshold_m:
                classification = CurvatureClass.RIDGE
            else:
                classification = CurvatureClass.NEITHER
            results.append(CellCurvature(row, col, curvature, classification))
    return results
