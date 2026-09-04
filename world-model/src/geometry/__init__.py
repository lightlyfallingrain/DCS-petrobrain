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
