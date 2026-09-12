"""Tests for `runtime.compile.compile_current_mission` --
`plans/mi6-runtime-compilation/plan.md`, Implementation Plan stage 3.

Mirrors `test_schema_understanding.py`'s pattern: build a
`MissionUnderstanding` by hand (no `.miz`/HTTP pipeline needed at this
layer), compile it, assert the compact shape -- including the
player-intent reconciliation rules that are this stage's actual
substantive work.
"""

from __future__ import annotations

import dataclasses

from miz.tree import RoutePoint
from runtime.compile import compile_current_mission
from schema.tags import Tagged
from schema.understanding import (
    SCHEMA_VERSION,
    ImportantLocation,
    MissionPhase,
    MissionUnderstanding,
    Ownship,
    PlayerAnswer,
    Threat,
)
from world_enrich.schema import EnrichedRoutePoint, WorldRef

_EMPTY_WORLD_REF = WorldRef(position={}, name_matches=())


def _route_point(x: float, y: float, point_type: str = "Turning Point") -> RoutePoint:
    return RoutePoint(
        x=x,
        y=y,
        alt=1000.0,
        alt_type="BARO",
        speed=60.0,
        type=point_type,
        action="Turning Point",
        eta=0.0,
        eta_locked=False,
        raw={},
    )


def _named_world_ref(name: str) -> WorldRef:
    return WorldRef(position={}, name_matches=({"name": name, "kind": "settlement"},))


def _base_understanding(
    *,
    ownship: Tagged[Ownship | None] | None = None,
    purpose: Tagged[str] | None = None,
    task: Tagged[str] | None = None,
    known_threats: tuple[Tagged[Threat], ...] = (),
    player_intent: tuple[Tagged[PlayerAnswer], ...] = (),
    route: tuple[EnrichedRoutePoint, ...] = (),
    mission_phases: tuple[Tagged[MissionPhase], ...] = (),
    important_locations: tuple[Tagged[ImportantLocation], ...] = (),
) -> MissionUnderstanding:
    if ownship is None:
        ownship = Tagged(
            value=Ownship(aircraft="Mi-24P", flight="Hip-1", role=None),
            epistemic_status="FACT",
            basis=("miz:unit.skill",),
        )
    return MissionUnderstanding(
        schema_version=SCHEMA_VERSION,
        theatre=Tagged(
            value="Caucasus", epistemic_status="FACT", basis=("miz:mission.theatre",)
        ),
        ownship=ownship,
        route=Tagged(value=route, epistemic_status="FACT", basis=("miz:group.route",)),
        mission_phases=mission_phases,
        important_locations=important_locations,
        purpose=purpose,
        task=task,
        known_threats=known_threats,
        player_intent=player_intent,
    )


def _player_answer(
    tagged_wrap: bool, question_id: str, question_kind: str, parsed: bool | str | int
) -> Tagged[PlayerAnswer]:
    answer = PlayerAnswer(
        question_id=question_id,
        question_text="text",
        question_kind=question_kind,  # type: ignore[arg-type]
        parsed=parsed,
    )
    return Tagged(value=answer, epistemic_status="FACT", basis=("player:console",))


def test_passthrough_fields_unchanged() -> None:
    phases = (
        Tagged(
            value=MissionPhase(name="DEPARTURE", waypoint_index=0),
            epistemic_status="FACT",
            basis=("x",),
        ),
    )
    understanding = _base_understanding(mission_phases=phases)

    compact = compile_current_mission(understanding)

    assert compact.schema_version == understanding.schema_version
    assert compact.theatre == understanding.theatre
    assert compact.phases == phases


def test_ownship_display_string_from_fact() -> None:
    understanding = _base_understanding()

    compact = compile_current_mission(understanding)

    assert compact.ownship.value == "Mi-24P (Hip-1)"
    assert compact.ownship.epistemic_status == "FACT"


def test_ownship_unknown_without_answer_is_empty_string() -> None:
    unknown_ownship: Tagged[Ownship | None] = Tagged(
        value=None, epistemic_status="UNKNOWN", basis=("found 0",)
    )
    understanding = _base_understanding(ownship=unknown_ownship)

    compact = compile_current_mission(understanding)

    assert compact.ownship.value == ""
    assert compact.ownship.epistemic_status == "UNKNOWN"


def test_ownship_reconciled_from_free_text_player_answer() -> None:
    unknown_ownship: Tagged[Ownship | None] = Tagged(
        value=None, epistemic_status="UNKNOWN", basis=("found 0",)
    )
    answer = _player_answer(True, "ownship", "free_text", "Mi-8 Hook-2")
    understanding = _base_understanding(
        ownship=unknown_ownship, player_intent=(answer,)
    )

    compact = compile_current_mission(understanding)

    assert compact.ownship.value == "Mi-8 Hook-2"
    assert compact.ownship.epistemic_status == "FACT"
    assert compact.ownship.basis == ("player:console",)


def test_purpose_filled_from_free_text_when_never_populated() -> None:
    answer = _player_answer(True, "purpose", "free_text", "Escort the convoy")
    understanding = _base_understanding(purpose=None, player_intent=(answer,))

    compact = compile_current_mission(understanding)

    assert compact.purpose is not None
    assert compact.purpose.value == "Escort the convoy"
    assert compact.purpose.epistemic_status == "FACT"
    assert compact.purpose.basis == ("player:console",)


def test_purpose_stays_none_when_never_populated_and_never_asked() -> None:
    understanding = _base_understanding(purpose=None, player_intent=())

    compact = compile_current_mission(understanding)

    assert compact.purpose.value is None
    assert compact.purpose.epistemic_status == "UNKNOWN"
    assert compact.purpose.basis == ()


def test_task_confirmed_raises_confidence_without_upgrading_epistemic_status() -> None:
    low_confidence_task = Tagged(
        value="Suppress the SAM site",
        epistemic_status="INFERENCE",
        basis=("model:qwen3",),
        confidence="low",
    )
    answer = _player_answer(True, "task", "bool", True)
    understanding = _base_understanding(
        task=low_confidence_task, player_intent=(answer,)
    )

    compact = compile_current_mission(understanding)

    assert compact.task is not None
    assert compact.task.value == "Suppress the SAM site"
    # Epistemic status must NOT be upgraded to FACT -- player confirmation
    # doesn't turn a model inference into ground truth. This is the test
    # that would catch an accidental "upgrade" to a more-certain status.
    assert compact.task.epistemic_status == "INFERENCE"
    assert compact.task.confidence == "high"
    assert compact.task.basis == ("model:qwen3", "player:console")


def test_purpose_rejected_clears_value_but_keeps_tagged_wrapper() -> None:
    low_confidence_purpose = Tagged(
        value="Recon the border",
        epistemic_status="INFERENCE",
        basis=("model:qwen3",),
        confidence="low",
    )
    answer = _player_answer(True, "purpose", "bool", False)
    understanding = _base_understanding(
        purpose=low_confidence_purpose, player_intent=(answer,)
    )

    compact = compile_current_mission(understanding)

    assert compact.purpose.value is None
    # Rejection doesn't change epistemic_status, mirroring confirmation's
    # own "don't upgrade" rule -- it's distinguished from "never had a
    # guess" by non-empty `basis` instead.
    assert compact.purpose.epistemic_status == "INFERENCE"
    assert compact.purpose.basis == ("model:qwen3", "player:rejected")
    assert compact.purpose.confidence is None


def test_purpose_untouched_when_no_matching_player_intent_entry() -> None:
    high_confidence_purpose = Tagged(
        value="Strike the airfield",
        epistemic_status="INFERENCE",
        basis=("model:qwen3",),
        confidence="high",
    )
    understanding = _base_understanding(
        purpose=high_confidence_purpose, player_intent=()
    )

    compact = compile_current_mission(understanding)

    assert compact.purpose == high_confidence_purpose


def test_threat_confirmed_kept_and_confidence_raised() -> None:
    threat = Tagged(
        value=Threat(kind="sam", description="near the ridge", area_ref=None),
        epistemic_status="INFERENCE",
        basis=("model:qwen3",),
        confidence="low",
    )
    answer = _player_answer(True, "threat_0", "bool", True)
    understanding = _base_understanding(
        known_threats=(threat,), player_intent=(answer,)
    )

    compact = compile_current_mission(understanding)

    assert len(compact.expected_threats) == 1
    assert compact.expected_threats[0].value == "sam: near the ridge"
    assert compact.expected_threats[0].confidence == "high"
    assert compact.expected_threats[0].basis == ("model:qwen3", "player:console")
    # The raw MissionUnderstanding.known_threats itself is untouched --
    # compaction only trims the compact projection.
    assert understanding.known_threats == (threat,)


def test_threat_rejected_dropped_from_compact_but_not_from_raw() -> None:
    threat = Tagged(
        value=Threat(kind="armor", description="in the valley", area_ref=None),
        epistemic_status="INFERENCE",
        basis=("model:qwen3",),
        confidence="low",
    )
    answer = _player_answer(True, "threat_0", "bool", False)
    understanding = _base_understanding(
        known_threats=(threat,), player_intent=(answer,)
    )

    compact = compile_current_mission(understanding)

    assert compact.expected_threats == ()
    assert understanding.known_threats == (threat,)


def test_threat_untouched_when_no_matching_player_intent_entry() -> None:
    threat = Tagged(
        value=Threat(kind="unknown", description="somewhere", area_ref=None),
        epistemic_status="INFERENCE",
        basis=("model:qwen3",),
        confidence=None,
    )
    understanding = _base_understanding(known_threats=(threat,), player_intent=())

    compact = compile_current_mission(understanding)

    assert len(compact.expected_threats) == 1
    assert compact.expected_threats[0].value == "unknown: somewhere"
    assert compact.expected_threats[0].confidence is None
    assert compact.expected_threats[0].basis == ("model:qwen3",)


def test_route_extracts_xy_and_place_name() -> None:
    route = (
        EnrichedRoutePoint(
            point=_route_point(1.0, 2.0), world_ref=_named_world_ref("Ridgeline")
        ),
        EnrichedRoutePoint(point=_route_point(3.0, 4.0), world_ref=_EMPTY_WORLD_REF),
    )
    understanding = _base_understanding(route=route)

    compact = compile_current_mission(understanding)

    assert len(compact.route) == 2
    assert compact.route[0].value.index == 0
    assert compact.route[0].value.x == 1.0
    assert compact.route[0].value.y == 2.0
    assert compact.route[0].value.place_name == "Ridgeline"
    assert compact.route[1].value.place_name is None
    assert compact.route[0].epistemic_status == "FACT"


def test_key_locations_keyed_by_id_with_place_name() -> None:
    location = Tagged(
        value=ImportantLocation(
            id="Zone-Circle",
            kind="trigger_zone",
            world_ref=_named_world_ref("Border Town"),
        ),
        epistemic_status="OBSERVATION",
        basis=("world_model:find_place_by_name",),
    )
    understanding = _base_understanding(important_locations=(location,))

    compact = compile_current_mission(understanding)

    assert len(compact.key_locations) == 1
    assert compact.key_locations[0].value.id == "Zone-Circle"
    assert compact.key_locations[0].value.kind == "trigger_zone"
    assert compact.key_locations[0].value.place_name == "Border Town"
    assert compact.key_locations[0].epistemic_status == "OBSERVATION"


def test_priorities_and_intended_plan_and_role_keying_are_absent() -> None:
    """No producer exists for `priorities`/`intended_plan` anywhere in the
    pipeline, and no semantic-role classifier exists for `key_locations`
    (keyed by `ImportantLocation.id` instead) -- MI-6 must not fabricate
    either rather than leave a documented gap."""
    understanding = _base_understanding()

    compact = compile_current_mission(understanding)

    field_names = {f.name for f in dataclasses.fields(compact)}
    assert "priorities" not in field_names
    assert "intended_plan" not in field_names
    for location in compact.key_locations:
        # `CompactLocation` has no role/relevance field at all.
        location_field_names = {f.name for f in dataclasses.fields(location.value)}
        assert location_field_names == {"id", "kind", "place_name"}
