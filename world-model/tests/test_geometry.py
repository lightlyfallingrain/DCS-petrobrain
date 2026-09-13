"""Tests for `geometry`'s planar primitives against hand-computed answers,
including degenerate cases (zero-length segment, point on a polygon
vertex/edge, polygon wound both ways) -- see
`plans/m5-first-persistent-model/plan.md` "Tests" section.
"""

import pytest

from coordinates import wgs84_to_dcs
from geometry import (
    bbox_of,
    bearing_deg,
    distance_point_point,
    distance_point_polyline,
    distance_point_segment,
    orientation_label,
    point_in_polygon,
    polygon_contains,
    ring_area_m2,
    signed_side_of_polyline,
    simplify_polyline,
    simplify_ring,
)

# --- distance_point_point ---


def test_distance_point_point_3_4_5_triangle() -> None:
    assert distance_point_point((0.0, 0.0), (3.0, 4.0)) == pytest.approx(5.0)


def test_distance_point_point_same_point_is_zero() -> None:
    assert distance_point_point((10.0, -5.0), (10.0, -5.0)) == 0.0


# --- distance_point_segment ---


def test_distance_point_segment_perpendicular_drop() -> None:
    # Segment along x-axis from (0,0) to (10,0); point at (5, 3) is
    # perpendicular to the midpoint.
    assert distance_point_segment((5.0, 3.0), (0.0, 0.0), (10.0, 0.0)) == pytest.approx(
        3.0
    )


def test_distance_point_segment_clamps_beyond_endpoint() -> None:
    # Point is "past" the b endpoint, not perpendicular to the segment --
    # distance must be to b, not to the infinite line.
    assert distance_point_segment(
        (15.0, 0.0), (0.0, 0.0), (10.0, 0.0)
    ) == pytest.approx(5.0)


def test_distance_point_segment_zero_length_segment() -> None:
    # a == b: degenerate to point-to-point distance.
    assert distance_point_segment((3.0, 4.0), (0.0, 0.0), (0.0, 0.0)) == pytest.approx(
        5.0
    )


def test_distance_point_segment_point_on_segment_is_zero() -> None:
    assert distance_point_segment((5.0, 0.0), (0.0, 0.0), (10.0, 0.0)) == 0.0


# --- distance_point_polyline ---


def test_distance_point_polyline_picks_nearest_segment() -> None:
    polyline = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    # Closest to the vertical leg, not the horizontal one.
    assert distance_point_polyline((12.0, 5.0), polyline) == pytest.approx(2.0)


def test_distance_point_polyline_single_point_is_point_distance() -> None:
    assert distance_point_polyline((3.0, 4.0), [(0.0, 0.0)]) == pytest.approx(5.0)


def test_distance_point_polyline_empty_raises() -> None:
    with pytest.raises(ValueError):
        distance_point_polyline((0.0, 0.0), [])


# --- point_in_polygon ---

_SQUARE_CCW = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
_SQUARE_CW = list(reversed(_SQUARE_CCW))


@pytest.mark.parametrize("square", [_SQUARE_CCW, _SQUARE_CW], ids=["ccw", "cw"])
def test_point_in_polygon_interior_point(square: list[tuple[float, float]]) -> None:
    assert point_in_polygon((5.0, 5.0), square) is True


@pytest.mark.parametrize("square", [_SQUARE_CCW, _SQUARE_CW], ids=["ccw", "cw"])
def test_point_in_polygon_exterior_point(square: list[tuple[float, float]]) -> None:
    assert point_in_polygon((15.0, 5.0), square) is False


def test_point_in_polygon_on_vertex() -> None:
    assert point_in_polygon((0.0, 0.0), _SQUARE_CCW) is True


def test_point_in_polygon_on_edge() -> None:
    assert point_in_polygon((5.0, 0.0), _SQUARE_CCW) is True


def test_point_in_polygon_handles_explicitly_closed_ring() -> None:
    closed_ring = [*_SQUARE_CCW, _SQUARE_CCW[0]]
    assert point_in_polygon((5.0, 5.0), closed_ring) is True


def test_point_in_polygon_raises_for_fewer_than_3_vertices() -> None:
    with pytest.raises(ValueError):
        point_in_polygon((0.0, 0.0), [(0.0, 0.0), (1.0, 1.0)])


# --- bearing_deg ---


def test_bearing_deg_north() -> None:
    assert bearing_deg((0.0, 0.0), (1.0, 0.0)) == pytest.approx(0.0)


def test_bearing_deg_east() -> None:
    assert bearing_deg((0.0, 0.0), (0.0, 1.0)) == pytest.approx(90.0)


def test_bearing_deg_south() -> None:
    assert bearing_deg((0.0, 0.0), (-1.0, 0.0)) == pytest.approx(180.0)


def test_bearing_deg_west() -> None:
    assert bearing_deg((0.0, 0.0), (0.0, -1.0)) == pytest.approx(270.0)


def test_bearing_deg_raises_for_identical_points() -> None:
    with pytest.raises(ValueError):
        bearing_deg((1.0, 1.0), (1.0, 1.0))


# --- orientation_label ---


def test_orientation_label_north_south() -> None:
    assert orientation_label(0.0) == "N-S"
    assert orientation_label(179.0) == "N-S"


def test_orientation_label_east_west() -> None:
    assert orientation_label(90.0) == "E-W"


def test_orientation_label_diagonals() -> None:
    assert orientation_label(45.0) == "NE-SW"
    assert orientation_label(135.0) == "NW-SE"


def test_orientation_label_near_zero_runway_bearing() -> None:
    # The Latakia ILS-derived runway bearing (~0.31 deg, real data via
    # dcs_data.beacons) should read as the N-S axis.
    assert orientation_label(0.31) == "N-S"


# --- bbox_of ---


def test_bbox_of_multiple_points() -> None:
    assert bbox_of([(1.0, 5.0), (-3.0, 2.0), (4.0, -1.0)]) == (-3.0, 4.0, -1.0, 5.0)


def test_bbox_of_single_point() -> None:
    assert bbox_of([(2.0, 3.0)]) == (2.0, 2.0, 3.0, 3.0)


def test_bbox_of_empty_raises() -> None:
    with pytest.raises(ValueError):
        bbox_of([])


# --- simplify_polyline (osm-landcover-optimization, Design D3) -------------


def test_simplify_polyline_drops_point_within_tolerance() -> None:
    # (5, 0.1) is only 0.1m off the (0,0)-(10,0) line.
    result = simplify_polyline([(0.0, 0.0), (5.0, 0.1), (10.0, 0.0)], tol_m=1.0)
    assert result == [(0.0, 0.0), (10.0, 0.0)]


def test_simplify_polyline_keeps_point_beyond_tolerance() -> None:
    result = simplify_polyline([(0.0, 0.0), (5.0, 0.1), (10.0, 0.0)], tol_m=0.05)
    assert result == [(0.0, 0.0), (5.0, 0.1), (10.0, 0.0)]


def test_simplify_polyline_fewer_than_3_points_is_unchanged() -> None:
    assert simplify_polyline([(0.0, 0.0), (1.0, 1.0)], tol_m=1.0) == [
        (0.0, 0.0),
        (1.0, 1.0),
    ]
    assert simplify_polyline([], tol_m=1.0) == []


# --- simplify_ring (osm-landcover-optimization, Design D3) -----------------


def test_simplify_ring_drops_near_collinear_point_and_keeps_closure() -> None:
    # A 10x10 square with one extra vertex 0.05m off the bottom edge.
    ring = [
        (0.0, 0.0),
        (5.0, 0.05),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (0.0, 0.0),
    ]
    result = simplify_ring(ring, tol_m=1.0)
    assert result is not None
    assert result[0] == result[-1]
    assert result == [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (0.0, 0.0),
    ]


def test_simplify_ring_degenerate_below_3_vertices_returns_none() -> None:
    assert simplify_ring([(0.0, 0.0), (1.0, 1.0), (0.0, 0.0)], tol_m=1.0) is None


def test_simplify_ring_accepts_open_ring_input() -> None:
    # Same square, not explicitly closed on input.
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    result = simplify_ring(ring, tol_m=1.0)
    assert result is not None
    assert result[0] == result[-1]
    assert len(result) == 5


# --- ring_area_m2 (osm-landcover-optimization, Design D3) ------------------


def test_ring_area_m2_rectangle() -> None:
    rectangle = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
    assert ring_area_m2(rectangle) == pytest.approx(50.0)


def test_ring_area_m2_triangle() -> None:
    triangle = [(0.0, 0.0), (4.0, 0.0), (0.0, 3.0)]
    assert ring_area_m2(triangle) == pytest.approx(6.0)


def test_ring_area_m2_winding_order_does_not_matter() -> None:
    ccw = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
    cw = list(reversed(ccw))
    assert ring_area_m2(ccw) == pytest.approx(ring_area_m2(cw))


def test_ring_area_m2_fewer_than_3_vertices_is_zero() -> None:
    assert ring_area_m2([(0.0, 0.0), (1.0, 1.0)]) == 0.0


# --- polygon_contains (osm-landcover-optimization, Design substitution 2) --

_OUTER_SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
_HOLE_SQUARE = [(3.0, 3.0), (6.0, 3.0), (6.0, 6.0), (3.0, 6.0)]


def test_polygon_contains_point_inside_outer_and_outside_hole() -> None:
    assert polygon_contains((1.0, 1.0), _OUTER_SQUARE, [_HOLE_SQUARE]) is True


def test_polygon_contains_point_inside_hole_is_not_contained() -> None:
    assert polygon_contains((5.0, 5.0), _OUTER_SQUARE, [_HOLE_SQUARE]) is False


def test_polygon_contains_point_outside_outer_is_not_contained() -> None:
    assert polygon_contains((20.0, 20.0), _OUTER_SQUARE, [_HOLE_SQUARE]) is False


def test_polygon_contains_with_no_holes_matches_point_in_polygon() -> None:
    assert polygon_contains((5.0, 5.0), _OUTER_SQUARE, []) is True


# --- signed_side_of_polyline (osm-landcover-optimization, Design D5) -------


def test_signed_side_of_polyline_opposite_sides_have_opposite_signs() -> None:
    line = [(0.0, 0.0), (10.0, 0.0)]
    above = signed_side_of_polyline((5.0, 5.0), line)
    below = signed_side_of_polyline((5.0, -5.0), line)
    assert above > 0
    assert below < 0
    assert above == pytest.approx(-below)


def test_signed_side_of_polyline_convex_shared_vertex_pseudo_normal() -> None:
    # A left turn at (10, 0): east then north. The closest point to `p` is
    # the shared vertex itself (tied distance to both adjacent segments),
    # so the angle-weighted pseudo-normal, not either segment's own normal
    # alone, must decide the sign.
    points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    side = signed_side_of_polyline((12.0, -2.0), points)
    assert side == pytest.approx(-2.0 * (2**0.5))


def test_signed_side_of_polyline_concave_shared_vertex_pseudo_normal() -> None:
    # The mirrored, opposite-turning-direction case: a right turn at
    # (10, 0). Same tied-distance-to-vertex setup, opposite sign.
    points = [(0.0, 0.0), (10.0, 0.0), (10.0, -10.0)]
    side = signed_side_of_polyline((12.0, 2.0), points)
    assert side == pytest.approx(2.0 * (2**0.5))


def test_signed_side_of_polyline_raises_for_fewer_than_2_points() -> None:
    with pytest.raises(ValueError):
        signed_side_of_polyline((0.0, 0.0), [(1.0, 1.0)])


def test_signed_side_of_polyline_coastline_control_point() -> None:
    """D5's correctness gate: a real-geography, north-to-south Mediterranean
    coastline pushed through the real `wgs84_to_dcs` transform, not a
    hand-derived sign claim -- this is what actually proves the DCS
    x-north/z-east axis flip lands the "sea is to the west" reading
    correctly, rather than trusting the derivation on paper."""
    theatre = "Syria"
    coastline_lonlat = [(35.75, 35.60), (35.75, 35.45)]  # (lon, lat), north to south
    coastline_dcs = [wgs84_to_dcs(theatre, lat, lon) for lon, lat in coastline_lonlat]

    sea_point = wgs84_to_dcs(theatre, 35.52, 35.70)  # west of the coastline
    land_point = wgs84_to_dcs(theatre, 35.52, 35.80)  # east of the coastline

    sea_side = signed_side_of_polyline(sea_point, coastline_dcs)
    land_side = signed_side_of_polyline(land_point, coastline_dcs)

    # D1: the point is to the geographic left (land) when cross_dcs < 0.
    assert land_side < 0
    assert sea_side > 0
