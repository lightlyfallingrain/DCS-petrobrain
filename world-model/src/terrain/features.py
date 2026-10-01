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


def _chaikin_smooth_with_support(
    points: list[Point], iterations: int
) -> tuple[list[Point], list[tuple[int, int]]]:
    """Same construction as `_chaikin_smooth` (kept separate rather than
    merged so `_chaikin_smooth`'s own existing tests stay exercising the
    plain function), but also tracks, for every output point, the
    inclusive `(lo, hi)` range of *original* `points` indices whose convex
    combination produced it.

    This is what lets `_smooth_for_storage`'s deviation check compare each
    smoothed point against only its own local slice of the original
    polyline instead of scanning the whole thing -- the O(line_length^2)
    cost `plans/landform-geomorphons/performance.md` measured at 92% of
    per-tile time (`distance_point_polyline` called against every original
    segment, for every one of the ~16x as many smoothed points, for every
    line). A Chaikin point is always a convex combination of a small,
    iteration-bounded window of consecutive original points -- each pass
    replaces an edge `(c_i, c_{i+1})` with two points that are each convex
    combinations of `c_i` and `c_{i+1}` alone, so a point's support can
    only grow by merging its two parents' ranges, never jump outside them.
    At `DEFAULT_CHAIKIN_ITERATIONS=4` that window stays a handful of
    points wide regardless of how long the original line is, turning the
    per-point check from O(line_length) into O(1) and the whole deviation
    check from O(line_length^2) into O(line_length)."""
    current = points
    support = [(i, i) for i in range(len(points))]
    for _ in range(iterations):
        if len(current) < 3:
            break
        new_points: list[Point] = [current[0]]
        new_support: list[tuple[int, int]] = [support[0]]
        for i in range(len(current) - 1):
            (x0, z0), (x1, z1) = current[i], current[i + 1]
            lo = min(support[i][0], support[i + 1][0])
            hi = max(support[i][1], support[i + 1][1])
            new_points.append((0.75 * x0 + 0.25 * x1, 0.75 * z0 + 0.25 * z1))
            new_support.append((lo, hi))
            new_points.append((0.25 * x0 + 0.75 * x1, 0.25 * z0 + 0.75 * z1))
            new_support.append((lo, hi))
        new_points.append(current[-1])
        new_support.append(support[-1])
        current = new_points
        support = new_support
    return current, support


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
    input shape.

    The deviation check compares each smoothed point only against the
    local slice of `points` it was actually constructed from
    (`_chaikin_smooth_with_support`'s per-point support window), not the
    whole original polyline -- see that function's docstring. Checking a
    (correct, construction-exact) subset of segments can only ever report
    a deviation greater than or equal to the true whole-polyline minimum
    distance, never less, so this can only make the fallback trigger in
    cases the full scan would also have triggered (or, in principle, a
    pathological case the full scan would not have) -- it never accepts a
    smoothing the full scan would have rejected."""
    if len(points) < 3:
        return points
    smoothed, support = _chaikin_smooth_with_support(points, iterations)
    cap_m = _MAX_SMOOTHING_DEVIATION_FRACTION * position_uncertainty_m
    for point, (lo, hi) in zip(smoothed, support, strict=True):
        if distance_point_polyline(point, points[lo : hi + 1]) > cap_m:
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
