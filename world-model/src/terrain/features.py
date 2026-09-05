"""Connected-component grouping and principal-axis line extraction over
curvature-classified grid cells -- turns per-cell ridge/valley candidates
into `store.models.StoredFeature`-shaped `LineString` records the store
already knows how to hold (the general-purpose `feature` table needs no
schema change).

Two algorithm steps, both closed-form/stdlib (per the plan's "no numpy for a
problem this small" decision):

1. **Connected-component grouping** (`_connected_components`, 4-connectivity
   flood-fill over same-classification cells) turns a scatter of
   individually-classified cells into contiguous blobs. Components smaller
   than `min_cell_count` are dropped as noise (a first-guess floor, tuned in
   Stage 2 against real output over `latakia-20km` -- see
   `curvature.py`'s docstring on the same "first guess, tuned empirically"
   pattern).
2. **Principal-axis line extraction** (`_principal_axis`) -- a component's
   dominant direction is the largest eigenvector of its cell coordinates'
   2x2 covariance matrix, solved in closed form (a 2x2 symmetric matrix's
   eigenvalues are the roots of a quadratic -- no numpy needed). Cells are
   then ordered by their projection onto that axis and connected in order,
   producing an honest polyline through actual sampled grid points, not a
   smoothed curve.

`to_stored_features` sets `provenance = {"geometry": "dcs_derived"}` (not
`"dcs"`) on every emitted feature -- the source elevation samples are
DCS-native, but the ridge/valley *geometry* itself is this module's derived
analysis, not something DCS ever reports directly. This does not collide
with the `"dcs"`/`"osm"` provenance vocabulary used elsewhere in the store
(`query/describe.py` and `tools/export_geojson.py` both treat
`provenance["geometry"]` as an open string, not a fixed two-value enum --
confirmed before this module was wired into the pipeline, per the plan's
"Risks & Unknowns").
"""

import math
from dataclasses import dataclass

from store.models import ElevationGrid, StoredFeature
from terrain.curvature import CellCurvature, CurvatureClass

# Tuned empirically in Stage 2 alongside curvature.DEFAULT_CURVATURE_THRESHOLD_M
# -- see that module's docstring and
# world-model/research/2026-09-05-m6-terrain-semantics.md. 6 (rather than
# Stage 1's first-guess 4) drops more of the small noise-driven fragments a
# checkerboard-classified field produces, without discarding every
# multi-hundred-metre feature the region's real relief does contain.
DEFAULT_MIN_CELL_COUNT = 6

_KIND_BY_CLASS = {
    CurvatureClass.RIDGE: "ridge",
    CurvatureClass.VALLEY: "valley",
}


@dataclass(frozen=True)
class TerrainComponent:
    """One connected group of same-classification curvature cells, with its
    extracted principal-axis line -- the pure-geometry intermediate this
    module's tests exercise directly, before `to_stored_features` wraps it
    with store-facing provenance/confidence."""

    kind: str
    cells: list[CellCurvature]
    points: list[tuple[float, float]]
    elevation_range_m: tuple[float, float]
    orientation_deg: float


def _connected_components(
    cells_by_rc: dict[tuple[int, int], CellCurvature],
) -> list[list[CellCurvature]]:
    """4-connectivity flood-fill grouping of `cells_by_rc` (all assumed the
    same classification)."""
    visited: set[tuple[int, int]] = set()
    components: list[list[CellCurvature]] = []
    for start in cells_by_rc:
        if start in visited:
            continue
        stack = [start]
        visited.add(start)
        component: list[CellCurvature] = []
        while stack:
            rc = stack.pop()
            component.append(cells_by_rc[rc])
            row, col = rc
            for neighbour in (
                (row - 1, col),
                (row + 1, col),
                (row, col - 1),
                (row, col + 1),
            ):
                if neighbour in cells_by_rc and neighbour not in visited:
                    visited.add(neighbour)
                    stack.append(neighbour)
        components.append(component)
    return components


def _principal_axis(component: list[CellCurvature]) -> tuple[float, float]:
    """Unit vector `(row_component, col_component)` of the largest
    eigenvector of `component`'s cell-coordinate covariance matrix, solved
    in closed form (2x2 symmetric matrix -- no numpy needed)."""
    n = len(component)
    mean_row = sum(c.row for c in component) / n
    mean_col = sum(c.col for c in component) / n
    cov_rr = sum((c.row - mean_row) ** 2 for c in component) / n
    cov_cc = sum((c.col - mean_col) ** 2 for c in component) / n
    cov_rc = sum((c.row - mean_row) * (c.col - mean_col) for c in component) / n

    trace = cov_rr + cov_cc
    determinant = cov_rr * cov_cc - cov_rc * cov_rc
    discriminant = max(trace * trace / 4.0 - determinant, 0.0)
    lambda_max = trace / 2.0 + math.sqrt(discriminant)

    if cov_rc != 0.0:
        row_component, col_component = lambda_max - cov_cc, cov_rc
    elif cov_rr >= cov_cc:
        row_component, col_component = 1.0, 0.0
    else:
        row_component, col_component = 0.0, 1.0

    length = math.hypot(row_component, col_component)
    if length == 0.0:
        return 1.0, 0.0
    return row_component / length, col_component / length


def extract_components(
    grid: ElevationGrid,
    curvature_cells: list[CellCurvature],
    min_cell_count: int = DEFAULT_MIN_CELL_COUNT,
) -> list[TerrainComponent]:
    """Group `curvature_cells` (typically `curvature.classify_curvature`'s
    output) into connected ridge/valley components and extract each one's
    principal-axis line. Components smaller than `min_cell_count` are
    dropped as noise. `CurvatureClass.NEITHER` cells are ignored.

    Raises `ValueError` if a surviving component somehow has no sampled
    elevation at all -- unreachable in practice, since
    `classify_curvature` only emits cells whose own value (and every
    neighbour's) was sampled, but this project never fabricates a fallback
    for a missing fact.
    """
    components: list[TerrainComponent] = []
    for classification, kind in _KIND_BY_CLASS.items():
        cells_by_rc = {
            (c.row, c.col): c
            for c in curvature_cells
            if c.classification == classification
        }
        for component_cells in _connected_components(cells_by_rc):
            if len(component_cells) < min_cell_count:
                continue

            axis_row, axis_col = _principal_axis(component_cells)
            mean_row = sum(c.row for c in component_cells) / len(component_cells)
            mean_col = sum(c.col for c in component_cells) / len(component_cells)
            ordered = sorted(
                component_cells,
                key=lambda c: (
                    (c.row - mean_row) * axis_row + (c.col - mean_col) * axis_col
                ),
            )

            points = [
                (
                    grid.origin_x + c.row * grid.spacing_m,
                    grid.origin_z + c.col * grid.spacing_m,
                )
                for c in ordered
            ]
            sampled_elevations: list[float] = [
                elevation
                for c in ordered
                if (elevation := grid.samples[c.row][c.col]) is not None
            ]
            if not sampled_elevations:
                raise ValueError(
                    f"{kind} component at cells "
                    f"{[(c.row, c.col) for c in ordered]} has no sampled "
                    "elevation -- inconsistent with classify_curvature's "
                    "fully-sampled-window guarantee"
                )

            if len(points) >= 2 and points[0] != points[-1]:
                dx = points[-1][0] - points[0][0]
                dz = points[-1][1] - points[0][1]
                orientation_deg = math.degrees(math.atan2(dz, dx)) % 180.0
            else:
                orientation_deg = 0.0

            components.append(
                TerrainComponent(
                    kind=kind,
                    cells=ordered,
                    points=points,
                    elevation_range_m=(
                        min(sampled_elevations),
                        max(sampled_elevations),
                    ),
                    orientation_deg=orientation_deg,
                )
            )
    return components


def to_stored_features(
    components: list[TerrainComponent],
    source_id: int | None,
    position_uncertainty_m: float,
) -> list[StoredFeature]:
    """Wrap each `TerrainComponent`'s pure geometry into a store-facing
    `StoredFeature`: `kind="ridge"`/`"valley"`, `LineString` geometry,
    `provenance={"geometry": "dcs_derived"}` (see module docstring),
    `confidence={"geometry": "low"}` reflecting the source grid's coarseness
    (an established GIS analysis over real DCS elevation, but at a
    resolution too coarse to claim high positional confidence for a line
    feature -- see the plan's "Risks & Unknowns"). `position_uncertainty_m`
    is caller-supplied so it can track the source grid's actual
    `spacing_m`, not a hardcoded guess."""
    features: list[StoredFeature] = []
    for index, component in enumerate(components):
        min_elevation, max_elevation = component.elevation_range_m
        features.append(
            StoredFeature(
                kind=component.kind,
                geom_type="LineString",
                geometry=component.points,
                name=None,
                subtype=None,
                tags={
                    "elevation_range_m": [min_elevation, max_elevation],
                    "orientation_deg": component.orientation_deg,
                    "cell_count": len(component.cells),
                },
                source_id=source_id,
                source_ref=f"{component.kind}_{index}",
                provenance={"geometry": "dcs_derived"},
                confidence={"geometry": "low"},
                position_uncertainty_m=position_uncertainty_m,
            )
        )
    return features
