"""Tests for `belief.attention` -- `AttentionArea`, `area_contains`,
`effective_attention` (`plans/bl4-attention-events/plan.md`)."""

from __future__ import annotations

from belief.attention import (
    Attention,
    AttentionArea,
    Sector,
    area_contains,
    effective_attention,
)
from perception.geometry import GeoPosition


def _area(
    *,
    area_id: str = "AREA_1",
    center: GeoPosition | None = None,
    radius_m: float = 1000.0,
    level: Attention = "watch",
    sector: Sector | None = None,
    source: str = "console",
) -> AttentionArea:
    return AttentionArea(
        id=area_id,
        center=center if center is not None else GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        radius_m=radius_m,
        level=level,
        source=source,
        sector=sector,
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
