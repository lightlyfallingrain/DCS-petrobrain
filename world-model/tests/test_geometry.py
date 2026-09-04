"""Tests for `geometry`'s planar primitives against hand-computed answers,
including degenerate cases (zero-length segment, point on a polygon
vertex/edge, polygon wound both ways) -- see
`plans/m5-first-persistent-model/plan.md` "Tests" section.
"""

import pytest

from geometry import (
    bbox_of,
    bearing_deg,
    distance_point_point,
    distance_point_polyline,
    distance_point_segment,
    orientation_label,
    point_in_polygon,
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
