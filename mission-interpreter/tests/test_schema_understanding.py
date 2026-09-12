"""Tests for `schema.build.build_mission_understanding`.

The happy path runs the full MI-1 -> MI-1.5 -> MI-2 pipeline against the
committed synthetic `.miz` fixture (real `Unit.skill`/`RoutePoint.type`
values, a real `FakeWorldModelClient`-driven `EnrichedMission`). The
zero-/multi-`Player`-unit ownship edge cases build an `EnrichedMission`
directly in test code -- bypassing the zip/HTTP pipeline entirely -- which
mirrors `test_enrich.py`'s `FakeWorldModelClient` precedent of not needing
wire-format fidelity at this layer.

`test_no_tagged_value_is_ever_inference_or_assumption` is the central
invariant this stage exists to prove, mirroring `test_filter.py`'s role for
MI-1.5's author-only-knowledge invariant.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fixtures.synthetic_mission import write_synthetic_miz

from filter.crew_available import filter_crew_available
from miz.reader import read_miz
from miz.tree import BriefingText, Group, Unit
from schema.build import build_mission_understanding
from schema.tags import Tagged
from schema.understanding import MissionUnderstanding
from world_enrich.enrich import enrich_mission
from world_enrich.schema import (
    EnrichedCoalition,
    EnrichedCountry,
    EnrichedGroup,
    EnrichedMission,
    WorldRef,
)


class _FakeWorldModelClient:
    """Same shape as `test_enrich.py`'s double -- answers every lookup with
    canned, obviously fake data, non-empty for named entities."""

    def get_describe_position(self, x: float, z: float) -> dict[str, Any]:
        return {"x": x, "z": z, "nearest_settlement": None}

    def get_find_place_by_name(
        self, text: str, kinds: list[str] | None = None
    ) -> list[dict[str, Any]]:
        return [{"name": text, "kind": "settlement", "x": 0.0, "z": 0.0}]


def _happy_path_enriched(tmp_path: Path) -> EnrichedMission:
    raw = read_miz(write_synthetic_miz(tmp_path / "synthetic.miz"))
    crew_available = filter_crew_available(raw)
    return enrich_mission(crew_available, _FakeWorldModelClient())


def _bare_unit(unit_id: int, skill: str) -> Unit:
    return Unit(
        unit_id=unit_id,
        name=f"Unit{unit_id}",
        type="Mi-24P",
        x=0.0,
        y=0.0,
        skill=skill,
        raw={},
    )


def _bare_group(group_id: int, name: str, skills: list[str]) -> EnrichedGroup:
    group = Group(
        group_id=group_id,
        name=name,
        category="helicopter",
        hidden=False,
        hidden_on_planner=False,
        hidden_on_mfd=False,
        late_activation=False,
        route=None,
        units=tuple(
            _bare_unit(1000 * group_id + i, skill) for i, skill in enumerate(skills)
        ),
        raw={},
    )
    world_ref = WorldRef(position={"x": 0.0, "z": 0.0}, name_matches=())
    return EnrichedGroup(group=group, world_ref=world_ref, route=None)


_EMPTY_BRIEFING = BriefingText(
    description_text=None,
    description_blue_task=None,
    description_red_task=None,
    description_neutrals_task=None,
    sortie=None,
)


def _enriched_mission_with_ownship_groups(
    groups: list[EnrichedGroup],
) -> EnrichedMission:
    country = EnrichedCountry(name="USA", country_id=1, groups=tuple(groups))
    coalition = EnrichedCoalition(side="blue", countries=(country,))
    return EnrichedMission(
        theatre="TestTheatre",
        coalitions=(coalition,),
        trigger_zones=(),
        briefing=_EMPTY_BRIEFING,
        kneeboard_images=(),
    )


def _iter_tagged(value: Any) -> list[Tagged[Any]]:
    """Recursively collect every `Tagged` instance reachable from `value`
    (a `MissionUnderstanding`, or any dataclass/tuple nested inside one)."""
    found: list[Tagged[Any]] = []
    if isinstance(value, Tagged):
        found.append(value)
        found.extend(_iter_tagged(value.value))
    elif is_dataclass(value) and not isinstance(value, type):
        for field_name in value.__dataclass_fields__:
            found.extend(_iter_tagged(getattr(value, field_name)))
    elif isinstance(value, (tuple, list)):
        for item in value:
            found.extend(_iter_tagged(item))
    return found


def test_happy_path_populates_expected_fields(tmp_path: Path) -> None:
    enriched = _happy_path_enriched(tmp_path)

    understanding = build_mission_understanding(enriched)

    assert understanding.schema_version == 1
    assert understanding.theatre.value == "TestTheatre"
    assert understanding.theatre.epistemic_status == "FACT"

    assert understanding.ownship.epistemic_status == "FACT"
    ownship = understanding.ownship.value
    assert ownship is not None
    assert ownship.aircraft == "Mi-24P"
    assert ownship.flight == "Visible Group"
    assert ownship.role is None

    assert understanding.route.epistemic_status == "FACT"
    assert len(understanding.route.value) == 3

    phase_names = [p.value.name for p in understanding.mission_phases]
    assert phase_names == ["DEPARTURE", "RETURN"]
    assert understanding.mission_phases[0].value.waypoint_index == 0
    assert understanding.mission_phases[1].value.waypoint_index == 2
    for phase in understanding.mission_phases:
        assert phase.epistemic_status == "FACT"

    location_ids = {loc.value.id for loc in understanding.important_locations}
    assert location_ids == {"Visible Group", "Zone-Circle", "Zone-Poly"}
    for location in understanding.important_locations:
        assert location.epistemic_status == "OBSERVATION"

    assert understanding.purpose is None
    assert understanding.task is None
    assert understanding.known_threats == ()
    assert understanding.player_intent is None


def test_zero_player_units_resolves_ownship_and_route_to_unknown() -> None:
    groups = [_bare_group(1, "Group A", ["Average", "High"])]
    enriched = _enriched_mission_with_ownship_groups(groups)

    understanding = build_mission_understanding(enriched)

    assert understanding.ownship.value is None
    assert understanding.ownship.epistemic_status == "UNKNOWN"
    assert understanding.route.value == ()
    assert understanding.route.epistemic_status == "UNKNOWN"
    assert understanding.mission_phases == ()


def test_two_player_units_resolves_ownship_and_route_to_unknown() -> None:
    groups = [
        _bare_group(1, "Group A", ["Player"]),
        _bare_group(2, "Group B", ["Player"]),
    ]
    enriched = _enriched_mission_with_ownship_groups(groups)

    understanding = build_mission_understanding(enriched)

    assert understanding.ownship.value is None
    assert understanding.ownship.epistemic_status == "UNKNOWN"
    assert "found 2" in understanding.ownship.basis[0]
    assert understanding.route.value == ()
    assert understanding.route.epistemic_status == "UNKNOWN"
    assert understanding.mission_phases == ()


def test_important_locations_only_from_named_matches_not_route_waypoints(
    tmp_path: Path,
) -> None:
    """`important_locations` must come from `EnrichedGroup`/
    `EnrichedTriggerZone` whose `world_ref.name_matches` is non-empty, never
    from route waypoints (the pipeline has no per-waypoint name resolution
    at all -- see the plan's scope-narrowing note)."""
    enriched = _happy_path_enriched(tmp_path)

    understanding = build_mission_understanding(enriched)

    for location in understanding.important_locations:
        assert location.value.kind in ("unit_group", "trigger_zone")
    # Exactly the named group + 2 named trigger zones -- no waypoint-derived
    # entries snuck in.
    assert len(understanding.important_locations) == 3


def test_no_tagged_value_is_ever_inference_or_assumption(tmp_path: Path) -> None:
    """The central invariant this stage exists to prove: MI-3 never
    produces INFERENCE/ASSUMPTION -- only FACT/OBSERVATION/UNKNOWN."""
    enriched = _happy_path_enriched(tmp_path)

    understanding = build_mission_understanding(enriched)

    tagged_values = _iter_tagged(understanding)
    assert tagged_values, "expected at least one Tagged value to check"
    for tagged in tagged_values:
        assert tagged.epistemic_status not in ("INFERENCE", "ASSUMPTION")


def test_mission_understanding_round_trips_through_json(tmp_path: Path) -> None:
    enriched = _happy_path_enriched(tmp_path)

    understanding = build_mission_understanding(enriched)

    payload = json.loads(json.dumps(asdict(understanding)))

    assert payload["schema_version"] == 1
    assert payload["theatre"]["value"] == "TestTheatre"
    assert isinstance(payload["mission_phases"], list)
    assert isinstance(payload["important_locations"], list)


def test_mission_understanding_is_a_dataclass() -> None:
    assert is_dataclass(MissionUnderstanding)
