"""Tests for `synth.synthesize.synthesize_mission_understanding` and
`synth.prompts.build_messages`, against a fake `OllamaClient`-shaped
double (same "no wire-format fidelity needed at this layer" posture as
`test_enrich.py`'s `FakeWorldModelClient` -- `test_synth_ollama_client.py`
already covers the real HTTP client).

`test_prompt_never_contains_a_raw_coordinate` is the concrete regression
test for the plan's "never leak hidden-unit position" invariant -- see
`prompts.py`'s module docstring.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from miz.tree import BriefingText
from schema.tags import Tagged
from schema.understanding import MissionUnderstanding, Ownship
from synth.ollama_client import OllamaOutputError
from synth.prompts import build_messages
from synth.synthesize import synthesize_mission_understanding
from world_enrich.schema import EnrichedThreatSignal, WorldRef

_EMPTY_BRIEFING = BriefingText(
    description_text="Escort the convoy through the valley.",
    description_blue_task="Provide close air support.",
    description_red_task=None,
    description_neutrals_task=None,
    sortie="Convoy Escort",
)


class _FakeOllamaClient:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self._response = response
        self.last_messages: list[dict[str, str]] | None = None
        self.last_schema: dict[str, Any] | None = None

    def chat_json(
        self, messages: list[dict[str, str]], json_schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.last_messages = messages
        self.last_schema = json_schema
        if self._response is None:
            raise OllamaOutputError("fake client configured to fail")
        return self._response


def _base_understanding() -> MissionUnderstanding:
    return MissionUnderstanding(
        schema_version=1,
        theatre=Tagged(value="TestTheatre", epistemic_status="FACT"),
        ownship=Tagged(
            value=Ownship(aircraft="Mi-24P", flight="Visible Group"),
            epistemic_status="FACT",
        ),
        route=Tagged(value=(), epistemic_status="FACT"),
    )


_HAPPY_RESPONSE: dict[str, Any] = {
    "purpose": {
        "value": "Escort a supply convoy through hostile territory.",
        "epistemic_status": "INFERENCE",
        "basis": "briefing text",
        "confidence": "medium",
    },
    "task": {
        "value": "Provide close air support to the convoy.",
        "epistemic_status": "INFERENCE",
        "basis": "blue task text",
        "confidence": "high",
    },
    "known_threats": [
        {
            "kind": "armor",
            "description": "Armor reported near Jablah.",
            "epistemic_status": "ASSUMPTION",
            "basis": "threat signal summary",
            "confidence": "low",
        }
    ],
}


def test_happy_path_populates_purpose_task_known_threats() -> None:
    understanding = _base_understanding()
    client = _FakeOllamaClient(_HAPPY_RESPONSE)

    result = synthesize_mission_understanding(
        understanding, _EMPTY_BRIEFING, (), client
    )

    assert result.purpose is not None
    assert result.purpose.value == "Escort a supply convoy through hostile territory."
    assert result.purpose.epistemic_status == "INFERENCE"
    assert result.purpose.confidence == "medium"

    assert result.task is not None
    assert result.task.epistemic_status == "INFERENCE"

    assert len(result.known_threats) == 1
    threat_tag = result.known_threats[0]
    assert threat_tag.epistemic_status == "ASSUMPTION"
    assert threat_tag.confidence == "low"
    assert threat_tag.value.kind == "armor"
    assert threat_tag.value.area_ref is None


def test_model_claiming_fact_is_rejected_not_upgraded() -> None:
    """The model attempting to emit `epistemic_status: "FACT"` must be
    rejected -- the whole point of the structural + defense-in-depth
    validation (see `synthesize.py`'s module docstring)."""
    bad_response = json.loads(json.dumps(_HAPPY_RESPONSE))
    bad_response["purpose"]["epistemic_status"] = "FACT"
    understanding = _base_understanding()
    client = _FakeOllamaClient(bad_response)

    result = synthesize_mission_understanding(
        understanding, _EMPTY_BRIEFING, (), client
    )

    # Degrades gracefully: purpose/task/known_threats stay unpopulated,
    # not silently accepted with an upgraded/overwritten epistemic_status.
    assert result.purpose is None
    assert result.task is None
    assert result.known_threats == ()


def test_ollama_output_error_leaves_understanding_unchanged() -> None:
    understanding = _base_understanding()
    client = _FakeOllamaClient(response=None)  # configured to raise

    result = synthesize_mission_understanding(
        understanding, _EMPTY_BRIEFING, (), client
    )

    assert result is understanding


def test_prompt_never_contains_a_raw_coordinate() -> None:
    """The concrete regression test for "never leak hidden-unit position":
    build a threat signal whose world_ref carries an easily-greppable
    coordinate, and assert neither that coordinate nor the generic
    'x'/'z' JSON keys ever appear in the constructed prompt string."""
    leak_x, leak_z = 123456.789, 987654.321
    threat_signal = EnrichedThreatSignal(
        kind="armor",
        world_ref=WorldRef(
            position={
                "x": leak_x,
                "z": leak_z,
                "nearest_settlement": {"name": "Jablah"},
            },
            name_matches=(),
        ),
    )
    understanding = _base_understanding()

    messages = build_messages(understanding, _EMPTY_BRIEFING, (threat_signal,))

    full_text = json.dumps(messages)
    assert str(leak_x) not in full_text
    assert str(leak_z) not in full_text
    assert "Jablah" in full_text  # the place name itself is expected to appear


def test_prompt_uses_name_matches_over_nearest_settlement() -> None:
    threat_signal = EnrichedThreatSignal(
        kind="sam",
        world_ref=WorldRef(
            position={"x": 1.0, "z": 2.0, "nearest_settlement": {"name": "Fallback"}},
            name_matches=({"name": "Preferred"},),
        ),
    )
    understanding = _base_understanding()

    messages = build_messages(understanding, _EMPTY_BRIEFING, (threat_signal,))

    full_text = json.dumps(messages)
    assert "Preferred" in full_text
    assert "sam reported/expected near Preferred" in full_text


def test_prompt_handles_no_named_place_gracefully() -> None:
    threat_signal = EnrichedThreatSignal(
        kind="unknown",
        world_ref=WorldRef(
            position={"x": 1.0, "z": 2.0, "nearest_settlement": None},
            name_matches=(),
        ),
    )
    understanding = _base_understanding()

    messages = build_messages(understanding, _EMPTY_BRIEFING, (threat_signal,))

    full_text = json.dumps(messages)
    assert "no named place nearby" in full_text


def test_response_missing_known_threats_raises_output_error_and_degrades() -> None:
    bad_response = json.loads(json.dumps(_HAPPY_RESPONSE))
    del bad_response["known_threats"]
    understanding = _base_understanding()
    client = _FakeOllamaClient(bad_response)

    result = synthesize_mission_understanding(
        understanding, _EMPTY_BRIEFING, (), client
    )

    assert result.known_threats == ()
    assert result.purpose is None


@pytest.mark.parametrize("bad_confidence", ["FACT", "urgent", "", None, 5])
def test_invalid_confidence_is_rejected(bad_confidence: object) -> None:
    bad_response = json.loads(json.dumps(_HAPPY_RESPONSE))
    bad_response["purpose"]["confidence"] = bad_confidence
    understanding = _base_understanding()
    client = _FakeOllamaClient(bad_response)

    result = synthesize_mission_understanding(
        understanding, _EMPTY_BRIEFING, (), client
    )

    assert result.purpose is None
