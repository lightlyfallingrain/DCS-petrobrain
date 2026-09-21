"""Tests for `belief.attention` -- `AttentionArea`, `area_contains`,
`effective_attention` (`plans/bl4-attention-events/plan.md`)."""

from __future__ import annotations

from belief.attention import (
    Attention,
    AttentionArea,
    RelativeSector,
    Sector,
    area_contains,
    area_wedge_deg,
    effective_attention,
    project_relative_area,
)
from perception.geometry import GeoPosition


def _area(
    *,
    area_id: str = "AREA_1",
    center: GeoPosition | None = None,
    radius_m: float | None = 1000.0,
    level: Attention = "watch",
    sector: Sector | None = None,
    relative_sector: RelativeSector | None = None,
    wedge_deg: tuple[float, float] | None = None,
    source: str = "console",
) -> AttentionArea:
    return AttentionArea(
        id=area_id,
        center=center if center is not None else GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        radius_m=radius_m,
        level=level,
        source=source,
        sector=sector,
        relative_sector=relative_sector,
        wedge_deg=wedge_deg,
    )


def test_area_contains_within_radius_no_sector() -> None:
    area = _area(radius_m=1000.0)
    inside = GeoPosition(x=500.0, z=0.0, alt_m=0.0)
    outside = GeoPosition(x=1500.0, z=0.0, alt_m=0.0)
    assert area_contains(area, inside) is True
    assert area_contains(area, outside) is False


def test_area_contains_respects_sector() -> None:
    # Sector "N" is centered on bearing 0 (true north, +x), +/-45 degrees.
    area = _area(radius_m=1000.0, sector="N")
    north = GeoPosition(x=500.0, z=0.0, alt_m=0.0)
    south = GeoPosition(x=-500.0, z=0.0, alt_m=0.0)
    assert area_contains(area, north) is True
    assert area_contains(area, south) is False


def test_area_contains_sector_boundary_is_inclusive() -> None:
    # Bearing 45 degrees is exactly the edge between sector "N" and "NE".
    area = _area(radius_m=1000.0, sector="N")
    edge = GeoPosition(x=500.0, z=500.0, alt_m=0.0)
    assert area_contains(area, edge) is True


def test_unbounded_area_contains_a_contact_far_outside_any_previous_radius() -> None:
    """`radius_m=None` skips the range test entirely -- a contact well
    beyond any radius this codebase has ever used (the old, invented
    `F10_SCAN_RADIUS_M = 3000.0` included) is still contained, as long as
    it is inside the wedge."""
    area = _area(radius_m=None, sector="N")
    far_north = GeoPosition(x=50000.0, z=0.0, alt_m=0.0)
    assert area_contains(area, far_north) is True


def test_unbounded_area_still_excludes_a_contact_outside_the_wedge() -> None:
    """The wedge is doing real work on an unbounded area -- it must not be
    lost along with the radius."""
    area = _area(radius_m=None, sector="N")
    far_south = GeoPosition(x=-50000.0, z=0.0, alt_m=0.0)
    assert area_contains(area, far_south) is False


def test_bounded_area_behaves_exactly_as_before() -> None:
    """Regression guard for the typed `scan-area`/`watch-area` console
    path, which keeps supplying a real, player-chosen radius."""
    area = _area(radius_m=1000.0, sector="N")
    inside = GeoPosition(x=500.0, z=0.0, alt_m=0.0)
    outside = GeoPosition(x=1500.0, z=0.0, alt_m=0.0)
    assert area_contains(area, inside) is True
    assert area_contains(area, outside) is False


def test_unbounded_area_finds_the_s300_mast_a_bounded_one_would_have_missed() -> None:
    """The real motivation, worked concretely (`todo/todo.md`, "Scan
    geometry: drop the invented radius"): an S-300 mast at 8000 m, well
    inside the wedge, is excluded by the old 3000 m radius but contained
    by an unbounded area."""
    mast = GeoPosition(x=8000.0, z=0.0, alt_m=0.0)
    old_invented_radius = _area(radius_m=3000.0, sector="N")
    unbounded = _area(radius_m=None, sector="N")
    assert area_contains(old_invented_radius, mast) is False
    assert area_contains(unbounded, mast) is True


def test_effective_attention_ignore_always_wins_over_area() -> None:
    area = _area(level="priority")
    position = GeoPosition(x=100.0, z=0.0, alt_m=0.0)
    level, area_id = effective_attention("ignore", position, [area])
    assert level == "ignore"
    assert area_id is None


def test_effective_attention_no_areas_returns_direct_mark() -> None:
    position = GeoPosition(x=100.0, z=0.0, alt_m=0.0)
    level, area_id = effective_attention("normal", position, [])
    assert level == "normal"
    assert area_id is None


def test_effective_attention_area_raises_a_normal_contact() -> None:
    area = _area(level="watch")
    position = GeoPosition(x=100.0, z=0.0, alt_m=0.0)
    level, area_id = effective_attention("normal", position, [area])
    assert level == "watch"
    assert area_id == "AREA_1"


def test_effective_attention_direct_mark_wins_on_tie_or_higher() -> None:
    area = _area(level="watch")
    position = GeoPosition(x=100.0, z=0.0, alt_m=0.0)
    level, area_id = effective_attention("priority", position, [area])
    assert level == "priority"
    assert area_id is None

    level, area_id = effective_attention("watch", position, [area])
    assert level == "watch"
    assert area_id is None


def test_effective_attention_position_outside_area_is_unaffected() -> None:
    area = _area(level="priority", radius_m=100.0)
    far_away = GeoPosition(x=5000.0, z=0.0, alt_m=0.0)
    level, area_id = effective_attention("normal", far_away, [area])
    assert level == "normal"
    assert area_id is None


def test_effective_attention_best_of_multiple_areas() -> None:
    weak = _area(area_id="AREA_WEAK", level="watch")
    strong = _area(area_id="AREA_STRONG", level="priority")
    position = GeoPosition(x=100.0, z=0.0, alt_m=0.0)
    level, area_id = effective_attention("normal", position, [weak, strong])
    assert level == "priority"
    assert area_id == "AREA_STRONG"


# -- RelativeSector wedge bounds (plan's "Sector bounds" table) -------------


def test_relative_sector_wedge_bounds_match_the_plan_table() -> None:
    # `plans/f10-command-vocabulary/plan.md`'s table, in relative bearing
    # degrees with 12 o'clock = 0: ahead 11->1 (center 0, half-width 30),
    # left 9->11 (center -60, half-width 30), right 1->3 (center +60,
    # half-width 30), full 9->3 (center 0, half-width 90).
    ownship = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    expected: dict[RelativeSector, tuple[float, float]] = {
        "ahead": (0.0, 30.0),
        "left": (-60.0, 30.0),
        "right": (60.0, 30.0),
        "full": (0.0, 90.0),
    }
    for relative, (expected_center, expected_half_width) in expected.items():
        area = _area(relative_sector=relative)
        projected = project_relative_area(area, ownship, heading_true_deg=0.0)
        assert projected.wedge_deg == (expected_center % 360.0, expected_half_width)


# -- project_relative_area ---------------------------------------------------


def test_project_relative_area_rotates_by_heading() -> None:
    ownship = GeoPosition(x=100.0, z=200.0, alt_m=50.0)
    area = _area(relative_sector="ahead")

    projected = project_relative_area(area, ownship, heading_true_deg=90.0)

    assert projected.center == ownship
    assert projected.wedge_deg == (90.0, 30.0)


def test_project_relative_area_wraps_across_360() -> None:
    ownship = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    area = _area(relative_sector="left")  # centered -60 relative

    projected = project_relative_area(area, ownship, heading_true_deg=30.0)

    # -60 + 30 = -30 -> wraps to 330.
    assert projected.wedge_deg == (330.0, 30.0)


def test_project_relative_area_returns_fixed_areas_unchanged() -> None:
    ownship = GeoPosition(x=999.0, z=999.0, alt_m=0.0)
    area = _area(sector="N")  # no relative_sector -- a fixed ground area

    projected = project_relative_area(area, ownship, heading_true_deg=45.0)

    assert projected is area


# -- area_wedge_deg precedence (plan D3) -------------------------------------


def test_area_wedge_deg_explicit_wedge_wins_over_sector() -> None:
    area = _area(sector="N", wedge_deg=(200.0, 15.0))
    assert area_wedge_deg(area) == (200.0, 15.0)


def test_area_wedge_deg_falls_back_to_sector_literal() -> None:
    area = _area(sector="SE")
    assert area_wedge_deg(area) == (135.0, 45.0)


def test_area_wedge_deg_is_none_with_no_angular_filter() -> None:
    area = _area()
    assert area_wedge_deg(area) is None


def test_area_wedge_deg_unprojected_relative_area_matches_full_circle() -> None:
    # An ownship-anchored area that has not yet been projected has
    # `relative_sector` set but no `wedge_deg` -- deliberately permissive
    # (matches everywhere) rather than empty, per `area_wedge_deg`'s own
    # docstring.
    area = _area(relative_sector="ahead")
    assert area_wedge_deg(area) is None
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    far_away = GeoPosition(x=-10000.0, z=0.0, alt_m=0.0)
    wide_area = _area(relative_sector="ahead", radius_m=20000.0, center=center)
    assert area_contains(wide_area, far_away) is True
