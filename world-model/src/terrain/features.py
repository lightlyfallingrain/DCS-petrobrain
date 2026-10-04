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

from geometry import Point, distance_point_polyline, simplify_polyline
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

# `fix/landform-relief-gate` defect 1 -- there was no relief gate at all,
# and the retired marker-controlled-watershed mechanism's own
# `relief_threshold_m` (100.0) had no geomorphons equivalent, which is why
# the first geomorphons pass stored 89%/92% of ridges/valleys under 50 m
# of relief and classified the Bekaa floor as a valley (measured on the
# real `syria-full` build; see `plans/terrain-feature-probing/
# explore-notes.md`).
#
# The user's own criterion is "maskable-behind: sharp and/or high", worked
# out as a range-independent LOS-masking height against a 200 m AGL
# sightline: ~150 m of rise a quarter of the way to the target, ~100 m
# halfway, ~50 m three-quarters of the way, ~20 m close to the target --
# "~50-150 m of rise over a short horizontal run, scale-free". This picks
# the *floor* of that band (50 m) rather than a number tuned to produce a
# particular feature count: a feature's relief is a fixed property of the
# terrain, not of any one sightline, so a single scalar threshold has to
# cover every position along a plausible sightline a feature might sit on
# -- including close to the target, where even 50-100 m of relief still
# breaks LOS. Picking 100 m (the band's middle) would additionally drop
# every 50-100 m feature, discarding exactly the near-target cover/
# exposure information the explore-notes call out as the tactically
# important regime. Below 50 m, nothing in the stated band ever masks.
DEFAULT_MIN_RELIEF_M = 50.0

# `fix/landform-relief-gate` defect 2 -- stored geometry was ~16x denser
# than the source DEM supports (four Chaikin passes multiply point count
# ~16x; the median line carried one point per 5.6 m on a 90 m DEM). This
# is the `simplify_polyline` tolerance `_decimate_for_storage` runs on the
# *smoothed* curve, expressed (like `_MAX_SMOOTHING_DEVIATION_FRACTION`)
# as a fraction of `position_uncertainty_m`: a quarter of a grid cell,
# deliberately well inside the half-cell smoothing cap so decimation's
# own contribution to the final deviation-from-sampled-points bound still
# leaves headroom under that cap even when Chaikin's own (typically much
# smaller) deviation is added to it. `_decimate_for_storage` verifies this
# empirically against the cap rather than relying on the headroom alone --
# see that function's docstring.
DEFAULT_DECIMATION_TOLERANCE_FRACTION = 0.25


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


def filter_by_relief(
    components: list[TerrainComponent], min_relief_m: float = DEFAULT_MIN_RELIEF_M
) -> list[TerrainComponent]:
    """Drop traced lines whose own `elevation_range_m` span (max - min
    over the component's sampled cells) is below `min_relief_m` -- the
    relief gate the retired watershed mechanism had
    (`relief_threshold_m = 100.0`) and the first geomorphons pass shipped
    with no equivalent of (see `DEFAULT_MIN_RELIEF_M`'s docstring).

    Applied over the whole component's elevation span, not per vertex or
    per adjacent-cell step: geomorphons classifies a cell purely from its
    local line-of-sight pattern, with no notion of how much the terrain
    actually rises, so this is the one place that notion gets applied.
    A short flat stretch of an otherwise-tall ridge still keeps the whole
    ridge -- consistent with treating a traced crest as one feature
    elsewhere in this module."""
    return [
        component
        for component in components
        if component.elevation_range_m[1] - component.elevation_range_m[0]
        >= min_relief_m
    ]


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


def _decimate_for_storage(
    smoothed: list[Point],
    original_points: list[Point],
    tolerance_m: float,
    cap_m: float,
) -> list[Point]:
    """Reduce `smoothed` (already Chaikin-smoothed) toward DEM resolution
    via Douglas-Peucker (`geometry.simplify_polyline`), without ever
    letting the final line's deviation from the real sampled
    `original_points` exceed `cap_m` -- the same half-cell bound
    `_smooth_for_storage`'s own fallback already enforces, now checked
    again on the *decimated* geometry rather than assumed to still hold
    once points are removed.

    **Why this checks every original point against the whole decimated
    polyline, not a windowed per-segment slice** (an earlier version of
    this function tried exactly that, using `_chaikin_smooth_with_support`'s
    support windows the way `_smooth_for_storage`'s own check does, and it
    was wrong -- caught on real traced lines, not reasoned away). That
    check only bounds how far each *smoothed* point sits from its
    *nearest* original point in its support window
    (`distance_point_polyline` finds the closest point on a short
    polyline, not a per-point correspondence) -- it says nothing about
    the *other* original points sharing that same window if the raw
    traced path genuinely turns within it (a real, common case: a
    skeleton trace through a staircase of discrete cells turns often).
    Decimating across such a window can leave an original point well
    over 100 m from the resulting straight chord even though every
    individual bound along the way (Douglas-Peucker's own tolerance,
    `_smooth_for_storage`'s nearest-point check) measured clean --
    confirmed on a real `syria-full` SRTM tile. `tolerance_m` only
    bounds smoothed-vs-decimated deviation (what `simplify_polyline`
    measures); checking it alone, or checking it through a windowed
    proxy for the original points, both miss this.

    Checking every original point against the *whole* decimated
    polyline is unconditionally correct instead, and still cheap: the
    decimated line is always short (that is the point of decimating),
    so this is O(len(original_points) * len(decimated)), far below the
    O(line_length^2) cost `plans/landform-geomorphons/performance.md`
    already ruled out for the *smoothed* line (thousands of points) --
    here the larger operand is the raw cell count, typically tens to a
    few hundred per traced line."""
    if len(smoothed) < 3:
        return smoothed
    decimated = simplify_polyline(smoothed, tolerance_m)
    if len(decimated) >= len(smoothed):
        return smoothed
    if all(
        distance_point_polyline(point, decimated) <= cap_m for point in original_points
    ):
        return decimated
    return smoothed


def _smooth_for_storage(
    points: list[Point],
    position_uncertainty_m: float,
    iterations: int = DEFAULT_CHAIKIN_ITERATIONS,
    decimation_tolerance_fraction: float = DEFAULT_DECIMATION_TOLERANCE_FRACTION,
) -> list[Point]:
    """The geometry `to_stored_features` writes for one component: `points`
    run through `_chaikin_smooth` and then decimated back toward DEM
    resolution (`_decimate_for_storage`), or `points` itself unchanged if
    there are fewer than 3 of them (nothing to smooth) or if the smoothed
    curve's own *measured* maximum deviation from the original polyline
    exceeds half a grid cell (`_MAX_SMOOTHING_DEVIATION_FRACTION *
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
    smoothing the full scan would have rejected.

    Decimation only ever runs on geometry that already passed the
    smoothing deviation check above, and `_decimate_for_storage` runs its
    own independent deviation check against the same `cap_m` before
    accepting the decimated result -- so this function's return value
    always satisfies "maximum deviation from the sampled points stays
    below half a cell," whichever of smoothing/decimation ends up
    applied."""
    if len(points) < 3:
        return points
    smoothed, support = _chaikin_smooth_with_support(points, iterations)
    cap_m = _MAX_SMOOTHING_DEVIATION_FRACTION * position_uncertainty_m
    for point, (lo, hi) in zip(smoothed, support, strict=True):
        if distance_point_polyline(point, points[lo : hi + 1]) > cap_m:
            return points
    return _decimate_for_storage(
        smoothed,
        points,
        decimation_tolerance_fraction * position_uncertainty_m,
        cap_m,
    )


def to_stored_features(
    components: list[TerrainComponent],
    source_id: int | None,
    position_uncertainty_m: float,
    decimation_tolerance_fraction: float = DEFAULT_DECIMATION_TOLERANCE_FRACTION,
) -> list[StoredFeature]:
    """Wrap each `TerrainComponent`'s pure geometry into a store-facing
    `StoredFeature`: `kind="ridge"`/`"valley"`, `LineString` geometry
    (Chaikin-smoothed and decimated, see `_smooth_for_storage`),
    `provenance={"geometry": "dcs_derived"}`, `confidence=
    {"geometry": "low"}`."""
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
                geometry=_smooth_for_storage(
                    component.points,
                    position_uncertainty_m,
                    decimation_tolerance_fraction=decimation_tolerance_fraction,
                ),
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
