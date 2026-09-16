"""Planar geometry primitives in the DCS x/z metre plane.

DCS's authoritative simulated space is a projected metric plane (M1 decision
-- `+proj=tmerc +axis=neu`, so `x` is the north component and `z` is the east
component), which means ordinary Euclidean geometry in (x, z) *is* distance
in metres with no geodesic math and no reprojection. That is the whole
justification for this module existing rather than reaching for a GIS
geometry library (see `plans/m5-first-persistent-model/plan.md` "Key
decision: spatial storage").

This module is used by both `build/` (bbox computation at ingest time) and
`query/` (nearest-feature search at read time). It is shared deliberately:
if the builder and the reader each grew their own distance/bbox math, they
could silently drift, and an R*Tree index only prunes correctly if its
bounding boxes agree exactly with the geometry a query later measures
against. Pure functions only -- no I/O, no dependencies beyond `math`.

Points are plain `tuple[float, float]` of `(x, z)`. Polygons and polylines
are `list[tuple[float, float]]` in point order; a polygon's ring may or may
not repeat its first point as its last -- `point_in_polygon` treats it as
implicitly closed either way.
"""

import math

Point = tuple[float, float]


def distance_point_point(a: Point, b: Point) -> float:
    """Euclidean distance between two (x, z) points, in metres."""
    return math.hypot(b[0] - a[0], b[1] - a[1])


def distance_point_segment(p: Point, a: Point, b: Point) -> float:
    """Distance from `p` to the segment `a`-`b`, in metres.

    Degenerate case: if `a == b`, the segment has zero length and this is
    just point-to-point distance.
    """
    ax, az = a
    bx, bz = b
    px, pz = p

    dx = bx - ax
    dz = bz - az
    length_sq = dx * dx + dz * dz
    if length_sq == 0.0:
        return distance_point_point(p, a)

    # Project p onto the infinite line through a-b, clamped to the segment.
    t = ((px - ax) * dx + (pz - az) * dz) / length_sq
    t = max(0.0, min(1.0, t))
    closest = (ax + t * dx, az + t * dz)
    return distance_point_point(p, closest)


def distance_point_polyline(p: Point, points: list[Point]) -> float:
    """Distance from `p` to the polyline through `points`, in metres.

    Raises `ValueError` if `points` is empty. A single-point "polyline" is
    treated as that point (point-to-point distance).
    """
    if not points:
        raise ValueError("distance_point_polyline requires at least one point")
    if len(points) == 1:
        return distance_point_point(p, points[0])
    return min(
        distance_point_segment(p, points[i], points[i + 1])
        for i in range(len(points) - 1)
    )


def point_in_polygon(p: Point, polygon: list[Point]) -> bool:
    """Ray-casting point-in-polygon test.

    `polygon` is a ring of `(x, z)` vertices in either winding order; it is
    treated as implicitly closed regardless of whether the first point is
    repeated as the last. Raises `ValueError` for fewer than 3 distinct
    vertices (not a polygon).

    A point exactly on an edge or vertex is treated as inside -- ray casting
    is inherently ambiguous on the boundary, and "inside" is the safer
    default for this project's use (`inside_settlement` should not flip to
    `false` from floating-point noise on a boundary point).
    """
    ring = polygon[:-1] if len(polygon) > 1 and polygon[0] == polygon[-1] else polygon
    if len(ring) < 3:
        raise ValueError("point_in_polygon requires at least 3 distinct vertices")

    px, pz = p
    n = len(ring)
    inside = False
    for i in range(n):
        ax, az = ring[i]
        bx, bz = ring[(i + 1) % n]

        if _point_on_segment(p, (ax, az), (bx, bz)):
            return True

        # Standard ray-casting: does the edge straddle the horizontal ray
        # extending in +x from p, at height z == pz?
        crosses = (az > pz) != (bz > pz)
        if crosses:
            x_at_pz = ax + (pz - az) / (bz - az) * (bx - ax)
            if px < x_at_pz:
                inside = not inside
    return inside


def _point_on_segment(p: Point, a: Point, b: Point) -> bool:
    """True if `p` lies on the closed segment `a`-`b` (within float tolerance)."""
    distance = distance_point_segment(p, a, b)
    return distance < 1e-9


def bearing_deg(a: Point, b: Point) -> float:
    """Compass bearing in degrees [0, 360) from `a` to `b`.

    0 deg is north (+x), 90 deg is east (+z), matching DCS's `+axis=neu`
    convention. Raises `ValueError` if `a == b` (bearing undefined).
    """
    dx = b[0] - a[0]
    dz = b[1] - a[1]
    if dx == 0.0 and dz == 0.0:
        raise ValueError("bearing_deg is undefined for a == b")
    bearing = math.degrees(math.atan2(dz, dx))
    return bearing % 360.0


_ORIENTATION_LABELS = ["N-S", "NE-SW", "E-W", "NW-SE"]


def orientation_label(bearing: float) -> str:
    """Bucket a bearing (or an axis bearing, e.g. a runway heading) into one
    of the four compass-axis labels: "N-S", "NE-SW", "E-W", "NW-SE".

    Reports the *axis* an orientation lies on rather than a directional
    compass point, since features like runways and roads are undirected
    lines -- a bearing of 2 deg and a bearing of 182 deg both describe the
    same "N-S" axis.
    """
    axis_angle = bearing % 180.0
    # Distance to each of the four 45-degree-spaced axis buckets (0, 45, 90,
    # 135), wrapping at 180.
    index = round(axis_angle / 45.0) % 4
    return _ORIENTATION_LABELS[index]


def bbox_of(points: list[Point]) -> tuple[float, float, float, float]:
    """Axis-aligned bounding box of `points` as `(min_x, max_x, min_z, max_z)`.

    Raises `ValueError` if `points` is empty.
    """
    if not points:
        raise ValueError("bbox_of requires at least one point")
    xs = [p[0] for p in points]
    zs = [p[1] for p in points]
    return (min(xs), max(xs), min(zs), max(zs))


# --- osm-landcover-optimization additions (Design D2-D5) -------------------
#
# `simplify_polyline`/`simplify_ring` (iterative Douglas-Peucker),
# `ring_area_m2` (shoelace), `polygon_contains` (ring-with-holes containment)
# and `signed_side_of_polyline` (coastline land/sea side) -- pure additions,
# no change to anything above this line. See `plans/
# osm-landcover-optimization/plan.md` Implementation Plan step 2 and Design
# D3/D5.


def _perpendicular_distance(p: Point, a: Point, b: Point) -> float:
    """Distance from `p` to the *infinite* line through `a`-`b` (not
    clamped to the segment, unlike `distance_point_segment`) -- the
    distance measure classic Douglas-Peucker simplification uses. Falls
    back to point-to-point distance when `a == b` (a zero-length
    reference segment has no line to measure against)."""
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    length = math.hypot(dx, dz)
    if length == 0.0:
        return distance_point_point(p, a)
    px, pz = p
    cross = dx * (pz - az) - dz * (px - ax)
    return abs(cross) / length


def simplify_polyline(points: list[Point], tol_m: float) -> list[Point]:
    """Iterative Douglas-Peucker simplification of an open polyline,
    dropping vertices within `tol_m` of the line between their surrounding
    kept vertices. `points[0]` and `points[-1]` are always kept. Iterative
    (an explicit stack, not recursion) so an unusually long vertex chain
    (a large forest/water relation's outer ring) cannot hit Python's
    recursion limit -- see the plan's Design D3.

    Fewer than 3 points is returned unchanged (nothing to simplify)."""
    if len(points) < 3:
        return list(points)

    keep = [False] * len(points)
    keep[0] = True
    keep[-1] = True
    stack: list[tuple[int, int]] = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue
        a, b = points[start], points[end]
        max_distance = -1.0
        max_index = -1
        for i in range(start + 1, end):
            distance = _perpendicular_distance(points[i], a, b)
            if distance > max_distance:
                max_distance = distance
                max_index = i
        if max_distance > tol_m:
            keep[max_index] = True
            stack.append((start, max_index))
            stack.append((max_index, end))

    return [p for p, k in zip(points, keep, strict=True) if k]


def simplify_ring(ring: list[Point], tol_m: float) -> list[Point] | None:
    """Douglas-Peucker simplification of a closed ring, preserving closure
    (the returned ring repeats its first point as its last, same as the
    input convention). Returns `None` if the ring degenerates below 3
    distinct vertices, either before or after simplification -- not a
    polygon any more, a counted drop for the caller (`build.ingest_osm`'s
    D3 ring pipeline).

    A ring has no natural start/end for Douglas-Peucker's "farthest point
    from the line between two anchors" step (its anchors would be the same
    point). Instead this picks the ring's farthest vertex from its first
    point as a second anchor, splits the ring into the two open chains
    between those two anchors, simplifies each chain independently, and
    rejoins them -- a standard closed-curve generalization of the
    open-polyline algorithm.
    """
    is_closed = len(ring) > 1 and ring[0] == ring[-1]
    open_ring = ring[:-1] if is_closed else list(ring)
    if len(open_ring) < 3:
        return None

    anchor_a = 0
    anchor_b = max(
        range(1, len(open_ring)),
        key=lambda i: distance_point_point(open_ring[0], open_ring[i]),
    )
    chain_1 = open_ring[anchor_a : anchor_b + 1]
    chain_2 = [*open_ring[anchor_b:], open_ring[anchor_a]]

    simplified_1 = simplify_polyline(chain_1, tol_m)
    simplified_2 = simplify_polyline(chain_2, tol_m)
    # Each simplified chain keeps both its own anchors; drop the trailing
    # anchor of each before concatenating so it isn't duplicated.
    merged = simplified_1[:-1] + simplified_2[:-1]

    distinct: list[Point] = []
    for point in merged:
        if not distinct or distinct[-1] != point:
            distinct.append(point)
    if len(distinct) >= 2 and distinct[0] == distinct[-1]:
        distinct.pop()

    if len(distinct) < 3:
        return None
    return [*distinct, distinct[0]]


def ring_area_m2(ring: list[Point]) -> float:
    """Unsigned area of `ring` in square metres, via the shoelace formula.
    `ring` is treated as implicitly closed regardless of whether the first
    point is repeated as the last (same convention as `point_in_polygon`).
    Returns `0.0` for fewer than 3 distinct vertices, rather than raising --
    callers computing a net area (outer minus holes) want a hole with too
    few vertices to contribute nothing, not a crash."""
    points = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    n = len(points)
    if n < 3:
        return 0.0
    signed_area_x2 = 0.0
    for i in range(n):
        x1, z1 = points[i]
        x2, z2 = points[(i + 1) % n]
        signed_area_x2 += x1 * z2 - x2 * z1
    return abs(signed_area_x2) / 2.0


def polygon_contains(p: Point, outer: list[Point], holes: list[list[Point]]) -> bool:
    """`True` iff `p` lies inside `outer` and outside every ring in `holes`
    -- a point inside (or on the boundary of, per `point_in_polygon`'s own
    boundary convention) a hole is not contained by the polygon, matching
    `store.reader`'s `inner_rings` containment rule (`plans/
    osm-landcover-optimization/plan.md` Design, substitution 2)."""
    if not point_in_polygon(p, outer):
        return False
    return not any(point_in_polygon(p, hole) for hole in holes)


def _unit_perpendicular(a: Point, b: Point) -> Point | None:
    """Unit vector perpendicular to `a`-`b`, rotated 90 degrees
    counter-clockwise in the (x, z) plane -- `None` if `a == b` (no
    direction to be perpendicular to). Matches `signed_side_of_polyline`'s
    sign convention: for this normal, `dot(p - a, normal)` has the same
    sign as `cross_dcs = (bx-ax)(pz-az) - (bz-az)(px-ax)`."""
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    length = math.hypot(dx, dz)
    if length == 0.0:
        return None
    return (-dz / length, dx / length)


def _vertex_pseudo_normal(points: list[Point], vertex_index: int) -> Point:
    """The angle-weighted pseudo-normal at an interior vertex shared by
    segments `(vertex_index-1, vertex_index)` and `(vertex_index,
    vertex_index+1)` -- the sum of each adjacent segment's *unit* normal
    (per `_unit_perpendicular`), then re-normalized. Summing unit (not
    length-scaled) normals is what makes this "angle-weighted": the
    resultant vector's direction bisects the angle between the two
    segments, without either segment's raw length skewing the result (see
    the plan's Design D5)."""
    prev = _unit_perpendicular(points[vertex_index - 1], points[vertex_index])
    nxt = _unit_perpendicular(points[vertex_index], points[vertex_index + 1])
    nx = (prev[0] if prev is not None else 0.0) + (nxt[0] if nxt is not None else 0.0)
    nz = (prev[1] if prev is not None else 0.0) + (nxt[1] if nxt is not None else 0.0)
    length = math.hypot(nx, nz)
    if length == 0.0:
        # The two segments' normals cancelled out (a near-180-degree
        # reversal at this vertex) -- fall back to whichever adjacent
        # segment has a well-defined normal at all.
        fallback = prev if prev is not None else nxt
        return fallback if fallback is not None else (0.0, 0.0)
    return (nx / length, nz / length)


def signed_side_of_polyline(p: Point, points: list[Point]) -> float:
    """Signed value whose sign says which side of the polyline `points`
    (in point order, at least 2 points) `p` lies on: negative means `p` is
    to the geographic left of the polyline's direction, positive means to
    the right -- matching `cross_dcs = (bx-ax)(pz-az) - (bz-az)(px-ax)` at
    the segment closest to `p` (see the plan's Design D5 for the coastline
    land/sea reading of this sign in DCS's `x`-north/`z`-east axes).

    Raises `ValueError` if `points` has fewer than 2 points.

    When the closest point on the polyline is (numerically) an interior
    vertex shared by two segments rather than strictly inside one segment,
    a single segment's own normal is an arbitrary, discontinuous choice --
    this uses the angle-weighted pseudo-normal at that vertex instead
    (`_vertex_pseudo_normal`), so the sign does not flip depending on which
    of the two segments happened to "win" the nearest-segment search.
    """
    if len(points) < 2:
        raise ValueError("signed_side_of_polyline requires at least 2 points")

    best_index = 0
    best_t = 0.0
    best_distance: float | None = None
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        dx, dz = b[0] - a[0], b[1] - a[1]
        length_sq = dx * dx + dz * dz
        if length_sq == 0.0:
            t = 0.0
        else:
            t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / length_sq
            t = max(0.0, min(1.0, t))
        closest = (a[0] + t * dx, a[1] + t * dz)
        distance = distance_point_point(p, closest)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_index = i
            best_t = t

    n = len(points)
    vertex_index: int | None = None
    if best_t <= 0.0 and best_index > 0:
        vertex_index = best_index
    elif best_t >= 1.0 and best_index < n - 2:
        vertex_index = best_index + 1

    if vertex_index is not None:
        normal = _vertex_pseudo_normal(points, vertex_index)
        vx, vz = points[vertex_index]
        return normal[0] * (p[0] - vx) + normal[1] * (p[1] - vz)

    a, b = points[best_index], points[best_index + 1]
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
