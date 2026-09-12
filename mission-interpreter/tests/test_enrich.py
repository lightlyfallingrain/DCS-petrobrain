"""Tests for `world_enrich.enrich.enrich_mission`.

Exercised against a fake `WorldModelClient`-shaped recording double (not a
real HTTP server -- no need for wire-format fidelity at this layer, that's
`test_world_model_client.py`'s job), fed the committed synthetic `.miz`
fixture run through MI-1 (`miz.reader.read_miz`) + MI-1.5
(`filter.crew_available.filter_crew_available`) to get a real
`CrewAvailableMission`.

The axis-mapping test below is this milestone's single most important
check: `miz.tree.RoutePoint.y` is DCS's `z` axis, not a literal `z` field
(see `enrich.py`'s module docstring). The synthetic fixture's visible
group's route waypoint has `x=10, y=20` -- visibly distinct values, so a
swap bug (`z=point.x` instead of `z=point.y`) would produce a detectably
wrong call, not pass by coincidence the way a symmetric `x == y` fixture
would.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fixtures.synthetic_mission import VISIBLE_GROUP_NAME, write_synthetic_miz

from filter.crew_available import filter_crew_available
from filter.threat_signals import ThreatSignal
from miz.reader import read_miz
from world_enrich.enrich import enrich_mission, enrich_threat_signals


class FakeWorldModelClient:
    """Records every call it receives and answers with canned, obviously
    fake data -- just enough shape for `enrich_mission` to build a
    `WorldRef` from, not a real world-model response."""

    def __init__(self) -> None:
        self.describe_position_calls: list[tuple[float, float]] = []
        self.find_place_by_name_calls: list[str] = []

    def get_describe_position(self, x: float, z: float) -> dict[str, Any]:
        self.describe_position_calls.append((x, z))
        return {"x": x, "z": z, "nearest_settlement": None}

    def get_find_place_by_name(
        self, text: str, kinds: list[str] | None = None
    ) -> list[dict[str, Any]]:
        self.find_place_by_name_calls.append(text)
        return [{"name": text, "kind": "settlement", "x": 0.0, "z": 0.0}]


def _crew_available(tmp_path: Path) -> Any:
    raw = read_miz(write_synthetic_miz(tmp_path / "synthetic.miz"))
    return filter_crew_available(raw)


def test_route_waypoint_maps_y_to_z_not_x(tmp_path: Path) -> None:
    """The synthetic fixture's visible group route waypoint is `x=10,
    y=20` -- the call reaching world-model must be `x=10, z=20`, never
    `x=20, z=10` (a swapped axis) or `x=10, z=10`/`x=20, z=20` (a dropped
    `y`)."""
    mission = _crew_available(tmp_path)
    client = FakeWorldModelClient()

    enrich_mission(mission, client)

    assert (10.0, 20.0) in client.describe_position_calls
    assert (20.0, 10.0) not in client.describe_position_calls


def test_visible_group_route_point_gets_world_ref(tmp_path: Path) -> None:
    mission = _crew_available(tmp_path)
    client = FakeWorldModelClient()

    enriched = mission
    result = enrich_mission(enriched, client)

    visible = next(
        group
        for coalition in result.coalitions
        for country in coalition.countries
        for group in country.groups
        if group.group.name == VISIBLE_GROUP_NAME
    )
    assert visible.route is not None
    # Fixture route: TakeOffGround (10, 20) -> Turning Point (15, 25) ->
    # Land (30, 40) -- see MI-3's synthetic_mission.py update.
    assert len(visible.route) == 3
    assert visible.route[0].world_ref.position == {
        "x": 10.0,
        "z": 20.0,
        "nearest_settlement": None,
    }
    assert visible.route[1].world_ref.position == {
        "x": 15.0,
        "z": 25.0,
        "nearest_settlement": None,
    }
    assert visible.route[2].world_ref.position == {
        "x": 30.0,
        "z": 40.0,
        "nearest_settlement": None,
    }


def test_visible_group_representative_position_uses_first_unit(
    tmp_path: Path,
) -> None:
    mission = _crew_available(tmp_path)
    client = FakeWorldModelClient()

    result = enrich_mission(mission, client)

    visible = next(
        group
        for coalition in result.coalitions
        for country in coalition.countries
        for group in country.groups
        if group.group.name == VISIBLE_GROUP_NAME
    )
    assert visible.world_ref is not None
    # Unit1's x=10, y=20 in the fixture -- same mapping rule as route points.
    assert visible.world_ref.position == {
        "x": 10.0,
        "z": 20.0,
        "nearest_settlement": None,
    }


def test_named_group_gets_name_matches(tmp_path: Path) -> None:
    mission = _crew_available(tmp_path)
    client = FakeWorldModelClient()

    enrich_mission(mission, client)

    assert VISIBLE_GROUP_NAME in client.find_place_by_name_calls


def test_trigger_zone_circle_uses_own_x_y(tmp_path: Path) -> None:
    mission = _crew_available(tmp_path)
    client = FakeWorldModelClient()

    result = enrich_mission(mission, client)

    circle = next(z for z in result.trigger_zones if z.zone.name == "Zone-Circle")
    # Fixture: Zone-Circle has x=100, y=200.
    assert circle.world_ref.position == {
        "x": 100.0,
        "z": 200.0,
        "nearest_settlement": None,
    }


def test_trigger_zone_polygon_uses_vertex_centroid(tmp_path: Path) -> None:
    mission = _crew_available(tmp_path)
    client = FakeWorldModelClient()

    result = enrich_mission(mission, client)

    polygon = next(z for z in result.trigger_zones if z.zone.name == "Zone-Poly")
    # Fixture: Zone-Poly vertices are (1, 2) and (3, 4) -- centroid (2, 3),
    # not the zone's own x=300/y=400 (not meaningful for a polygon).
    assert polygon.world_ref.position == {
        "x": 2.0,
        "z": 3.0,
        "nearest_settlement": None,
    }


def test_named_trigger_zones_get_name_matches(tmp_path: Path) -> None:
    mission = _crew_available(tmp_path)
    client = FakeWorldModelClient()

    enrich_mission(mission, client)

    assert "Zone-Circle" in client.find_place_by_name_calls
    assert "Zone-Poly" in client.find_place_by_name_calls


def test_briefing_and_kneeboard_images_pass_through_unchanged(
    tmp_path: Path,
) -> None:
    mission = _crew_available(tmp_path)
    client = FakeWorldModelClient()

    result = enrich_mission(mission, client)

    assert result.briefing == mission.briefing
    assert result.kneeboard_images == mission.kneeboard_images


def test_call_count_is_bounded_and_deterministic(tmp_path: Path) -> None:
    """One `describe_position` call per route waypoint + one per group
    representative position + one per trigger zone; one
    `find_place_by_name` call per non-empty named group/zone."""
    mission = _crew_available(tmp_path)
    client = FakeWorldModelClient()

    enrich_mission(mission, client)

    # Hidden groups are already dropped by filter_crew_available, so only
    # the visible group remains: 1 representative position + 3 route
    # waypoints (TakeOffGround/Turning Point/Land) = 4 calls, plus 2 trigger
    # zones (circle + polygon) = 2 more calls.
    assert len(client.describe_position_calls) == 6
    # Named entities: the visible group + 2 trigger zones = 3 calls.
    assert len(client.find_place_by_name_calls) == 3


def test_enrich_threat_signals_resolves_each_to_a_world_ref() -> None:
    signals = (
        ThreatSignal(kind="armor", x=100.0, z=200.0),
        ThreatSignal(kind="sam", x=5.0, z=6.0),
    )
    client = FakeWorldModelClient()

    result = enrich_threat_signals(signals, client)

    assert len(result) == 2
    assert result[0].kind == "armor"
    assert result[0].world_ref.position == {
        "x": 100.0,
        "z": 200.0,
        "nearest_settlement": None,
    }
    assert result[1].kind == "sam"
    assert result[1].world_ref.position == {
        "x": 5.0,
        "z": 6.0,
        "nearest_settlement": None,
    }
    assert (100.0, 200.0) in client.describe_position_calls
    assert (5.0, 6.0) in client.describe_position_calls


def test_enrich_threat_signals_never_calls_find_place_by_name() -> None:
    """A threat signal has no name to resolve -- see
    `filter.threat_signals`'s docstring on never surfacing a group name."""
    signals = (ThreatSignal(kind="armor", x=1.0, z=2.0),)
    client = FakeWorldModelClient()

    enrich_threat_signals(signals, client)

    assert client.find_place_by_name_calls == []


def test_enrich_threat_signals_of_empty_tuple_is_empty() -> None:
    client = FakeWorldModelClient()

    assert enrich_threat_signals((), client) == ()
