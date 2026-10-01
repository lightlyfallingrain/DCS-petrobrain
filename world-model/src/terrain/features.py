"""Pure-geometry wrapping for geomorphons-derived ridge/valley lines --
Stage C of `plans/landform-geomorphons/plan.md`.

Everything basin-specific from the retired marker-controlled-watershed
mechanism is gone: `grow_basins`, `qualifying_ridges`/`qualifying_valleys`,
`_connected_components`, `_principal_axis`, `_seed_groups`,
`_basin_boundaries`, `_saddle_elevations`, `_minor_axis_extent_m`,
`_axis_sliced_line`, `_build_component`, `extract_components`, `Basin`,
`GridCell` -- a geomorphons line has no basin to belong to, so there is
nothing left for any of them to operate over. `TerrainComponent` keeps only
what a traced skeleton line actually has: its grid-index cells, its real
DCS x/z points, and its sampled elevation range.

`_chaikin_smooth`/`_smooth_for_storage` are ported verbatim (not merged --
see `plans/landform-geomorphons/plan.md`'s "Affected modules" note on why)
from `feature/landform-curve-smoothing` (commit `ecdf3e2`): a pure function
over `list[Point]` with no basin dependency, so it carries across this
rewrite unchanged. `to_stored_features` keeps the same `StoredFeature`
wrapping convention (`provenance={"geometry": "dcs_derived"}`,
`confidence={"geometry": "low"}`) and the `orientation_deg`/
`elevation_range_m` tags `query.describe`'s `NearbyTerrainFeature` already
reads -- `basin_width_m` is gone (no basin, no width gate); `cell_count`
now counts a traced line's own skeleton cells rather than a basin
component's.
"""

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import numpy as np
import numpy.typing as npt

from geometry import Point, distance_point_polyline
from store.models import StoredFeature

# `_smooth_for_storage`'s deviation cap, as a fraction of `position_
# uncertainty_m` (production sets this to `terrain_cache`'s own lattice
# `spacing_m` -- see `build.ingest_terrain`) -- half a grid cell, ported
# unchanged from the watershed-era rationale (the staircase is an artifact
# of lattice quantisation, not of the terrain).
_MAX_SMOOTHING_DEVIATION_FRACTION = 0.5

# Chaikin iterations for `_chaikin_smooth`, ported unchanged (see that
# commit's own tuning note: 4 passes kept the real `syria-full` theatre's
# staircase comfortably inside the half-cell deviation cap).
DEFAULT_CHAIKIN_ITERATIONS = 4


@dataclass(frozen=True)
class TerrainComponent:
    """One traced ridge/valley line -- the pure-geometry intermediate this
    module's tests exercise directly, before `to_stored_features` wraps it
    with store-facing provenance/confidence.

    `cells` are the skeleton's own `(row, col)` grid indices, in trace
    order; `points` are those same cells' real DCS x/z coordinates (the
    "honest polyline through actual sampled grid points" standard,
    unchanged from the watershed mechanism)."""

    kind: str
    cells: list[tuple[int, int]]
    points: list[Point]
    elevation_range_m: tuple[float, float]
    orientation_deg: float


def component_from_trace(
    kind: str,
    cells: list[tuple[int, int]],
    dem: npt.NDArray[np.float64],
    origin_x: float,
    origin_z: float,
    spacing_m: float,
) -> TerrainComponent:
    """Build a `TerrainComponent` from one `terrain.skeleton.trace` path:
    `cells` (row, col) indices into `dem` (a 2-D array of sampled
    elevations, `NaN` for void -- never read for a traced cell, since a
    skeleton cell always comes from a classified, and therefore sampled,
    DEM cell) become real DCS x/z `points` via `origin_x`/`origin_z`/
    `spacing_m` (the same per-tile lattice convention `terrain.resample`
    builds), plus the component's own sampled elevation range and
    orientation (first-to-last point bearing, mod 180 -- a line has no
    inherent direction)."""
    points = [
        (origin_x + row * spacing_m, origin_z + col * spacing_m) for row, col in cells
    ]
    elevations = [float(dem[row, col]) for row, col in cells]
    if points[0] != points[-1]:
        dx = points[-1][0] - points[0][0]
        dz = points[-1][1] - points[0][1]
        orientation_deg = math.degrees(math.atan2(dz, dx)) % 180.0
    else:
        orientation_deg = 0.0
    return TerrainComponent(
        kind=kind,
        cells=cells,
        points=points,
        elevation_range_m=(min(elevations), max(elevations)),
        orientation_deg=orientation_deg,
    )


def _chaikin_smooth(points: list[Point], iterations: int) -> list[Point]:
    """`iterations` passes of Chaikin corner-cutting over the open polyline
    `points`, first and last point held fixed. Each pass replaces every
    edge `(p_i, p_{i+1})` with two points at 1/4 and 3/4 along it; the
    limit of repeated passes is the uniform quadratic B-spline through the
    input points.

    Chosen over a centripetal Catmull-Rom spline for one reason: every
    point this produces is a fixed convex combination of exactly two
    *consecutive original points*, so it can never move past the segment
    it is cutting -- `_smooth_for_storage`'s deviation cap is then a
    property of the construction, checked rather than hoped for."""
    current = points
    for _ in range(iterations):
        if len(current) < 3:
            break
        smoothed: list[Point] = [current[0]]
        for (x0, z0), (x1, z1) in pairwise(current):
            smoothed.append((0.75 * x0 + 0.25 * x1, 0.75 * z0 + 0.25 * z1))
            smoothed.append((0.25 * x0 + 0.75 * x1, 0.25 * z0 + 0.75 * z1))
        smoothed.append(current[-1])
        current = smoothed
    return current


def _smooth_for_storage(
    points: list[Point],
    position_uncertainty_m: float,
    iterations: int = DEFAULT_CHAIKIN_ITERATIONS,
) -> list[Point]:
    """The geometry `to_stored_features` writes for one component: `points`
    run through `_chaikin_smooth`, or `points` itself unchanged if there
    are fewer than 3 of them (nothing to smooth) or if the smoothed curve's
    own *measured* maximum deviation from the original polyline exceeds
    half a grid cell (`_MAX_SMOOTHING_DEVIATION_FRACTION *
    position_uncertainty_m`) -- a belt-and-suspenders fallback, not an
    assumption that Chaikin's structural bound always holds for every
    input shape."""
    if len(points) < 3:
        return points
    smoothed = _chaikin_smooth(points, iterations)
    max_deviation_m = max(distance_point_polyline(p, points) for p in smoothed)
    if max_deviation_m > _MAX_SMOOTHING_DEVIATION_FRACTION * position_uncertainty_m:
        return points
    return smoothed


def to_stored_features(
    components: list[TerrainComponent],
    source_id: int | None,
    position_uncertainty_m: float,
) -> list[StoredFeature]:
    """Wrap each `TerrainComponent`'s pure geometry into a store-facing
    `StoredFeature`: `kind="ridge"`/`"valley"`, `LineString` geometry
    (Chaikin-smoothed, see `_smooth_for_storage`), `provenance=
    {"geometry": "dcs_derived"}`, `confidence={"geometry": "low"}`."""
    features: list[StoredFeature] = []
    for index, component in enumerate(components):
        min_elevation, max_elevation = component.elevation_range_m
        tags: dict[str, Any] = {
            "elevation_range_m": [min_elevation, max_elevation],
            "orientation_deg": component.orientation_deg,
            "cell_count": len(component.cells),
        }
        features.append(
            StoredFeature(
                kind=component.kind,
                geom_type="LineString",
                geometry=_smooth_for_storage(component.points, position_uncertainty_m),
                name=None,
                subtype=None,
                tags=tags,
                source_id=source_id,
                source_ref=f"{component.kind}_{index}",
                provenance={"geometry": "dcs_derived"},
                confidence={"geometry": "low"},
                position_uncertainty_m=position_uncertainty_m,
            )
        )
    return features
