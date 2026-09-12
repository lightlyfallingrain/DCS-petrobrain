"""Tests for `schema.tags.Tagged` -- prove the mechanism (construction,
`asdict()` -> `json.dumps` -> `json.loads` round-trip) before anything is
built on top of it."""

from __future__ import annotations

import json
from dataclasses import asdict

from schema.tags import Tagged


def test_tagged_int_round_trips_through_json() -> None:
    tagged = Tagged(value=42, epistemic_status="FACT", basis=("miz:mission.theatre",))

    payload = json.loads(json.dumps(asdict(tagged)))

    assert payload == {
        "value": 42,
        "epistemic_status": "FACT",
        "basis": ["miz:mission.theatre"],
        "confidence": None,
    }


def test_tagged_str_round_trips_through_json() -> None:
    tagged: Tagged[str] = Tagged(value="Syria", epistemic_status="OBSERVATION")

    payload = json.loads(json.dumps(asdict(tagged)))

    assert payload == {
        "value": "Syria",
        "epistemic_status": "OBSERVATION",
        "basis": [],
        "confidence": None,
    }


def test_tagged_basis_defaults_to_empty_tuple() -> None:
    tagged: Tagged[int] = Tagged(value=1, epistemic_status="UNKNOWN")

    assert tagged.basis == ()


def test_tagged_confidence_defaults_to_none() -> None:
    tagged: Tagged[int] = Tagged(value=1, epistemic_status="FACT")

    assert tagged.confidence is None


def test_tagged_confidence_round_trips_through_json() -> None:
    tagged: Tagged[str] = Tagged(
        value="engage the convoy",
        epistemic_status="INFERENCE",
        basis=("synth:ollama:qwen3:14b",),
        confidence="medium",
    )

    payload = json.loads(json.dumps(asdict(tagged)))

    assert payload == {
        "value": "engage the convoy",
        "epistemic_status": "INFERENCE",
        "basis": ["synth:ollama:qwen3:14b"],
        "confidence": "medium",
    }
