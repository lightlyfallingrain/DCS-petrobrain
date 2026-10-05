"""`divides_between`: counts distinct ridge crossings between two points.

`plans/terrain-feature-probing/plan.md` Revision 3, Decision 1-2
(2026-10-05). Against the real geomorphons output (234,799 landform rows,
no basin topology -- the marker-controlled-watershed mechanism that would
have produced basin adjacency "for free" was abandoned before shipping,
see the plan's superseded-banner note), "the valley the contact is in" is
not an object the store can answer. What the pilot's phrase actually needs
is answerable directly, though: *"target two o'clock, next valley"* is a
claim about what lies *between* observer and target, not about which named
basin the target occupies.

**This is not line-of-sight and must never sample elevation.**
`query.line_of_sight.line_of_sight_clear` keeps that job -- it answers "can
unit A see unit B" by sampling the `elevation` grid point-by-point along a
sightline. This module answers a different, purely planar question: how
many distinct ridge *lines* (named crossings, not terrain height) does the
straight observer->target segment cross. The two mechanisms share nothing
but the store they both read.

**Query-time, not a build-time tag** (Decision 1). The answer is
ownship-relative -- it changes every poll as the helicopter moves -- so it
cannot be precomputed per-feature at build time the way `adjacent_feature_
ids` would have been under the now-void watershed design. Measured cost
(Decision 1): a bbox query over the observer->target corridor returns ~5
lines at Baalbek density, ~19 at theatre average for a 5 km corridor, each
5-6 vertices -- cheaper than the `nearest_feature` call `query.describe.
describe_position` already makes on the same path. Callers must not cache
this against ownship-independent state (`body-layer`'s `belief.enrichment.
WorldEnrichmentCache`'s own docstring on why `relative_geometry` is never
cached applies identically here).
"""

from __future__ import annotations

import sqlite3
from typing import Final

from geometry import Point, distance_point_point
from store.reader import features_in_bbox

#: Crossings within this many metres of each other *along the observer->
#: target segment* count as one divide (Decision 2, rule 2). Collapses two
#: mechanical cases that would otherwise overcount a single real crest:
#: a continuous ridge stored as two fragments cut at an SRTM tile seam or a
#: declined skeleton-junction pairing (`plans/landform-geomorphons/plan.md`,
#: "clip, don't merge"), and the parallel sub-crests of one ridge mass.
#: Without this, one ridge mass can read as "2 divides crossed" and the
#: "next valley" feature silently never fires (>=2 divides means silence,
#: per `divides_between`'s own contract). First guess, tune by flying --
#: same status as `body-layer`'s `belief.enrichment.
#: TERRAIN_QUALIFIER_MAX_M`/`TERRAIN_DOMINANCE_FACTOR`.
DIVIDE_MERGE_M: Final[float] = 400.0


def _segment_intersection_t(
    o: Point, target: Point, a: Point, b: Point
) -> float | None:
    """The parameter `t` in `[0, 1]` along `o -> target` at which segment
    `a-b` crosses it, or `None` if the two segments do not cross within
    both their own bounds (including the parallel/collinear case, which is
    deliberately not special-cased -- a ridge line running exactly along
    the sightline is a geometry this project's real data does not produce,
    and treating it as "no crossing" rather than "infinite crossings" is
    the safe default either way: `divides_between`'s own contract already
    treats an undercount as the acceptable failure mode, never an
    overcount)."""
    ox, oz = o
    tx, tz = target
    ax, az = a
    bx, bz = b
    d1x, d1z = tx - ox, tz - oz
    d2x, d2z = bx - ax, bz - az
    denom = d1x * d2z - d1z * d2x
    if denom == 0.0:
        return None
    qpx, qpz = ax - ox, az - oz
    t = (qpx * d2z - qpz * d2x) / denom
    u = (qpx * d1z - qpz * d1x) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t
    return None


def divides_between(
    conn: sqlite3.Connection,
    theatre: str,
    observer: Point,
    target: Point,
) -> int:
    """The number of distinct ridge lines the straight segment
    `observer -> target` crosses, after merging crossings within
    `DIVIDE_MERGE_M` of each other along the segment into one divide
    (Decision 2).

    `theatre` is accepted for signature uniformity with this package's
    other ownship/observer-agnostic primitives (`query.line_of_sight.
    line_of_sight_clear` takes the identical, currently-unused parameter
    for the same reason) -- the geometry here is already in DCS-native
    `(x, z)`, so no coordinate conversion is needed.

    Returns `0` for a zero-length segment (`observer == target`) --
    nothing is crossed when there is no path to cross it on.

    **Fragment-gap undercount is accepted, not papered over** (Decision 2,
    rule 1): a continuous crest stored as two segments with a seam gap can
    let the sightline slip between them and read one fewer divide than the
    real terrain has. This costs a missing qualifier, never a wrong one --
    `divides_between`'s only caller (`body-layer`'s `belief.enrichment.
    terrain_divide_qualifier`) treats anything other than exactly `1` as
    "say nothing", so an undercount degrades to silence, not a false
    claim."""
    ox, oz = observer
    tx, tz = target
    segment_length_m = distance_point_point(observer, target)
    if segment_length_m == 0.0:
        return 0

    bbox = (min(ox, tx), max(ox, tx), min(oz, tz), max(oz, tz))
    candidates = features_in_bbox(conn, ["ridge"], bbox)

    crossing_positions_m: list[float] = []
    for feature in candidates:
        if feature.geom_type != "LineString":
            continue
        points = feature.geometry
        for i in range(len(points) - 1):
            t = _segment_intersection_t(observer, target, points[i], points[i + 1])
            if t is not None:
                crossing_positions_m.append(t * segment_length_m)

    if not crossing_positions_m:
        return 0

    crossing_positions_m.sort()
    divide_count = 1
    last_position_m = crossing_positions_m[0]
    for position_m in crossing_positions_m[1:]:
        if position_m - last_position_m > DIVIDE_MERGE_M:
            divide_count += 1
        last_position_m = position_m
    return divide_count
