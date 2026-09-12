"""Serialization round-trip test for `runtime.compact.RuntimeMissionUnderstanding`
-- `plans/mi6-runtime-compilation/plan.md`, Implementation Plan stage 3.

Matches every prior stage's convention (`test_schema_understanding.py`,
etc.): `dataclasses.asdict()` -> `json.dumps` must round-trip cleanly with
no custom `to_dict` needed.
"""

from __future__ import annotations

import dataclasses
import json

from runtime.compact import (
    CompactLocation,
    CompactRoutePoint,
    RuntimeMissionUnderstanding,
)
from schema.tags import Tagged
from schema.understanding import MissionPhase


def _full_compact() -> RuntimeMissionUnderstanding:
    return RuntimeMissionUnderstanding(
        schema_version=1,
        theatre=Tagged(
            value="Caucasus", epistemic_status="FACT", basis=("miz:mission.theatre",)
        ),
        ownship=Tagged(
            value="Mi-24P (Hip-1)", epistemic_status="FACT", basis=("miz:unit.skill",)
        ),
        purpose=Tagged(
            value="Escort the convoy",
            epistemic_status="INFERENCE",
            basis=("model:qwen3", "player:console"),
            confidence="high",
        ),
        task=Tagged(value=None, epistemic_status="UNKNOWN", basis=()),
        phases=(
            Tagged(
                value=MissionPhase(name="DEPARTURE", waypoint_index=0),
                epistemic_status="FACT",
                basis=("x",),
            ),
        ),
        route=(
            Tagged(
                value=CompactRoutePoint(index=0, x=1.0, y=2.0, place_name="Ridgeline"),
                epistemic_status="FACT",
                basis=("miz:group.route",),
            ),
        ),
        key_locations=(
            Tagged(
                value=CompactLocation(
                    id="Zone-Circle", kind="trigger_zone", place_name="Border Town"
                ),
                epistemic_status="OBSERVATION",
                basis=("world_model:find_place_by_name",),
            ),
        ),
        expected_threats=(
            Tagged(
                value="sam: near the ridge",
                epistemic_status="INFERENCE",
                basis=("model:qwen3", "player:console"),
                confidence="high",
            ),
        ),
    )


def test_asdict_json_round_trip() -> None:
    compact = _full_compact()

    as_dict = dataclasses.asdict(compact)
    serialized = json.dumps(as_dict)
    round_tripped = json.loads(serialized)

    assert round_tripped["schema_version"] == 1
    assert round_tripped["theatre"]["value"] == "Caucasus"
    assert round_tripped["ownship"]["value"] == "Mi-24P (Hip-1)"
    assert round_tripped["purpose"]["confidence"] == "high"
    assert round_tripped["task"]["value"] is None
    assert round_tripped["task"]["epistemic_status"] == "UNKNOWN"
    assert round_tripped["phases"][0]["value"]["name"] == "DEPARTURE"
    assert round_tripped["route"][0]["value"]["place_name"] == "Ridgeline"
    assert round_tripped["key_locations"][0]["value"]["id"] == "Zone-Circle"
    assert round_tripped["expected_threats"][0]["value"] == "sam: near the ridge"


def test_absent_optional_field_values_serialize_as_null() -> None:
    never_asked = Tagged(value=None, epistemic_status="UNKNOWN", basis=())
    compact = dataclasses.replace(
        _full_compact(), purpose=never_asked, task=never_asked
    )

    as_dict = dataclasses.asdict(compact)
    serialized = json.dumps(as_dict)
    round_tripped = json.loads(serialized)

    assert round_tripped["purpose"]["value"] is None
    assert round_tripped["task"]["value"] is None
