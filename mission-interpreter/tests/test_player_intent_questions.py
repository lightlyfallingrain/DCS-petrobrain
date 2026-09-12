"""Unit tests for `player_intent.questions.detect_questions` -- one case
per detector rule (`plans/mi5-player-questions/plan.md`, Implementation
Plan stage 2), plus a no-questions case on a fully-resolved,
high-confidence understanding.

Builds `MissionUnderstanding` instances directly rather than through the
full MI-1->MI-4 pipeline -- this stage is a pure function over the schema
shape, so it doesn't need `.miz`/world-model/Ollama fidelity (mirrors
`test_schema_understanding.py`'s bare-`EnrichedMission` edge-case
convention)."""

from __future__ import annotations

from player_intent.questions import detect_questions
from schema.tags import Tagged
from schema.understanding import MissionUnderstanding, Ownship, Threat

_RESOLVED_OWNSHIP: Tagged[Ownship | None] = Tagged(
    value=Ownship(aircraft="Mi-24P", flight="Visible Group", role=None),
    epistemic_status="FACT",
    basis=("miz:unit.skill",),
)
_EMPTY_ROUTE: Tagged[tuple[()]] = Tagged(
    value=(), epistemic_status="FACT", basis=("miz: group has no route",)
)
_THEATRE: Tagged[str] = Tagged(
    value="TestTheatre", epistemic_status="FACT", basis=("miz:mission.theatre",)
)


def _base_understanding(**overrides: object) -> MissionUnderstanding:
    fields: dict[str, object] = {
        "schema_version": 1,
        "theatre": _THEATRE,
        "ownship": _RESOLVED_OWNSHIP,
        "route": _EMPTY_ROUTE,
    }
    fields.update(overrides)
    return MissionUnderstanding(**fields)  # type: ignore[arg-type]


def test_unresolved_ownship_produces_a_question() -> None:
    unresolved_ownship: Tagged[Ownship | None] = Tagged(
        value=None,
        epistemic_status="UNKNOWN",
        basis=("found 2 Player/Client-skill units, expected exactly 1",),
    )
    understanding = _base_understanding(ownship=unresolved_ownship)

    questions = detect_questions(understanding)

    ownship_questions = [q for q in questions if q.id == "ownship"]
    assert len(ownship_questions) == 1
    question = ownship_questions[0]
    # `_build_ownship`'s UNKNOWN basis carries only a match count today, no
    # enumerable candidate ids/names -- falls back to free_text rather than
    # inventing choice options (see questions.py's docstring).
    assert question.kind == "free_text"
    assert question.options == ()
    assert question.text == "Which aircraft is yours?"


def test_low_confidence_purpose_produces_a_bool_question() -> None:
    purpose = Tagged(
        value="Interdict enemy armor column",
        epistemic_status="INFERENCE",
        basis=("synth:ollama",),
        confidence="low",
    )
    understanding = _base_understanding(purpose=purpose)

    questions = detect_questions(understanding)

    purpose_questions = [q for q in questions if q.id == "purpose"]
    assert len(purpose_questions) == 1
    question = purpose_questions[0]
    assert question.kind == "bool"
    assert "Interdict enemy armor column" in question.text


def test_low_confidence_task_produces_a_bool_question() -> None:
    task = Tagged(
        value="Escort the convoy",
        epistemic_status="INFERENCE",
        basis=("synth:ollama",),
        confidence="low",
    )
    understanding = _base_understanding(task=task)

    questions = detect_questions(understanding)

    task_questions = [q for q in questions if q.id == "task"]
    assert len(task_questions) == 1
    assert task_questions[0].kind == "bool"


def test_purpose_still_none_produces_a_free_text_question() -> None:
    understanding = _base_understanding(purpose=None)

    questions = detect_questions(understanding)

    purpose_questions = [q for q in questions if q.id == "purpose"]
    assert len(purpose_questions) == 1
    assert purpose_questions[0].kind == "free_text"


def test_task_still_none_produces_a_free_text_question() -> None:
    understanding = _base_understanding(task=None)

    questions = detect_questions(understanding)

    task_questions = [q for q in questions if q.id == "task"]
    assert len(task_questions) == 1
    assert task_questions[0].kind == "free_text"


def test_low_confidence_threat_produces_a_bool_question() -> None:
    threats = (
        Tagged(
            value=Threat(
                kind="armor", description="tanks near the FARP", area_ref=None
            ),
            epistemic_status="INFERENCE",
            basis=("synth:ollama",),
            confidence="low",
        ),
        Tagged(
            value=Threat(kind="sam", description="SA-6 battery", area_ref=None),
            epistemic_status="INFERENCE",
            basis=("synth:ollama",),
            confidence="high",
        ),
    )
    understanding = _base_understanding(known_threats=threats)

    questions = detect_questions(understanding)

    threat_questions = [q for q in questions if q.id.startswith("threat_")]
    assert len(threat_questions) == 1
    assert threat_questions[0].id == "threat_0"
    assert threat_questions[0].kind == "bool"
    assert "tanks near the FARP" in threat_questions[0].text


def test_medium_or_high_confidence_purpose_produces_no_question() -> None:
    purpose = Tagged(
        value="Interdict enemy armor column",
        epistemic_status="INFERENCE",
        basis=("synth:ollama",),
        confidence="high",
    )
    understanding = _base_understanding(purpose=purpose)

    questions = detect_questions(understanding)

    assert not any(q.id == "purpose" for q in questions)


def test_fully_resolved_high_confidence_understanding_produces_no_questions() -> None:
    purpose = Tagged(
        value="Interdict enemy armor column",
        epistemic_status="INFERENCE",
        basis=("synth:ollama",),
        confidence="high",
    )
    task = Tagged(
        value="Escort the convoy",
        epistemic_status="INFERENCE",
        basis=("synth:ollama",),
        confidence="high",
    )
    threats = (
        Tagged(
            value=Threat(kind="sam", description="SA-6 battery", area_ref=None),
            epistemic_status="INFERENCE",
            basis=("synth:ollama",),
            confidence="high",
        ),
    )
    understanding = _base_understanding(
        purpose=purpose, task=task, known_threats=threats
    )

    questions = detect_questions(understanding)

    assert questions == ()
