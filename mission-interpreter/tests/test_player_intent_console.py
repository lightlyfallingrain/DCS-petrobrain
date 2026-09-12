"""Tests for `player_intent.console.PlayerIntentConsole` -- driven against
in-memory `io.StringIO` pairs, mirroring `body-layer/tests`' fixture-only,
no-live-dependency convention (`plans/mi5-player-questions/plan.md`,
Implementation Plan stage 3). Covers the bool/choice/free_text parse paths
and the re-prompt-once-then-give-up path for both `bool` and `choice`."""

from __future__ import annotations

import io

from player_intent.console import PlayerIntentConsole, _parse
from player_intent.questions import Question
from schema.tags import Tagged
from schema.understanding import MissionUnderstanding, Ownship

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
_RESOLVED_PURPOSE: Tagged[str] = Tagged(
    value="Interdict enemy armor column",
    epistemic_status="INFERENCE",
    basis=("synth:ollama",),
    confidence="high",
)
_RESOLVED_TASK: Tagged[str] = Tagged(
    value="Escort the convoy",
    epistemic_status="INFERENCE",
    basis=("synth:ollama",),
    confidence="high",
)


def _base_understanding(**overrides: object) -> MissionUnderstanding:
    # purpose/task default to resolved, high-confidence values so a test
    # exercising one detector rule doesn't accidentally also trip the
    # "purpose/task is None" free_text rule for the field it isn't testing.
    fields: dict[str, object] = {
        "schema_version": 1,
        "theatre": _THEATRE,
        "ownship": _RESOLVED_OWNSHIP,
        "route": _EMPTY_ROUTE,
        "purpose": _RESOLVED_PURPOSE,
        "task": _RESOLVED_TASK,
    }
    fields.update(overrides)
    return MissionUnderstanding(**fields)  # type: ignore[arg-type]


def _run(understanding: MissionUnderstanding, input_text: str) -> MissionUnderstanding:
    console = PlayerIntentConsole(input_=io.StringIO(input_text), output=io.StringIO())
    return console.run(understanding)


def test_no_questions_leaves_player_intent_empty() -> None:
    understanding = _base_understanding()

    result = _run(understanding, "")

    assert result.player_intent == ()


def test_free_text_question_accepts_any_line_including_blank() -> None:
    understanding = _base_understanding(purpose=None)

    result = _run(understanding, "\n")

    assert len(result.player_intent) == 1
    tagged = result.player_intent[0]
    assert tagged.epistemic_status == "FACT"
    assert tagged.basis == ("player:console",)
    assert tagged.value.question_id == "purpose"
    assert tagged.value.question_kind == "free_text"
    assert tagged.value.parsed == ""


def test_free_text_question_accepts_verbatim_text() -> None:
    understanding = _base_understanding(purpose=None)

    result = _run(understanding, "Escort the convoy to the FARP.\n")

    tagged = result.player_intent[0]
    assert tagged.value.parsed == "Escort the convoy to the FARP."


def test_bool_question_parses_yes_variants() -> None:
    purpose = Tagged(
        value="Interdict armor",
        epistemic_status="INFERENCE",
        basis=("synth:ollama",),
        confidence="low",
    )
    understanding = _base_understanding(purpose=purpose)

    result = _run(understanding, "YES\n")

    tagged = result.player_intent[0]
    assert tagged.value.question_kind == "bool"
    assert tagged.value.parsed is True


def test_bool_question_parses_no_variants() -> None:
    purpose = Tagged(
        value="Interdict armor",
        epistemic_status="INFERENCE",
        basis=("synth:ollama",),
        confidence="low",
    )
    understanding = _base_understanding(purpose=purpose)

    result = _run(understanding, "0\n")

    tagged = result.player_intent[0]
    assert tagged.value.parsed is False


def test_bool_question_reprompts_once_then_gives_up_as_free_text() -> None:
    purpose = Tagged(
        value="Interdict armor",
        epistemic_status="INFERENCE",
        basis=("synth:ollama",),
        confidence="low",
    )
    understanding = _base_understanding(purpose=purpose)

    result = _run(understanding, "maybe\nunclear\n")

    tagged = result.player_intent[0]
    # question_kind still reflects what was actually asked (bool) even
    # though the give-up value is the raw unparsed string.
    assert tagged.value.question_kind == "bool"
    assert tagged.value.parsed == "unclear"


def test_bool_question_succeeds_on_second_attempt() -> None:
    purpose = Tagged(
        value="Interdict armor",
        epistemic_status="INFERENCE",
        basis=("synth:ollama",),
        confidence="low",
    )
    understanding = _base_understanding(purpose=purpose)

    result = _run(understanding, "maybe\nyes\n")

    tagged = result.player_intent[0]
    assert tagged.value.question_kind == "bool"
    assert tagged.value.parsed is True


def test_choice_question_parses_1_based_index() -> None:
    # Today's ownship question falls back to free_text (no enumerable
    # candidates in basis -- see test_player_intent_questions.py), so
    # exercise the choice-parsing path directly with a hand-built
    # Question instead of driving it through detect_questions.
    question = Question(
        id="ownship", text="Which aircraft is yours?", kind="choice", options=("A", "B")
    )
    assert _parse(question, "2") == "B"
    assert _parse(question, "b") == "B"
    assert _parse(question, "nonsense") is None


def test_choice_question_reprompts_once_then_gives_up_as_free_text() -> None:
    question = Question(
        id="ownship", text="Which aircraft is yours?", kind="choice", options=("A", "B")
    )
    console = PlayerIntentConsole(
        input_=io.StringIO("nonsense\nstill-nonsense\n"), output=io.StringIO()
    )
    answer = console._ask(question)

    assert answer.epistemic_status == "FACT"
    assert answer.basis == ("player:console",)
    assert answer.value.question_kind == "choice"
    assert answer.value.parsed == "still-nonsense"


def test_multiple_questions_are_asked_in_order() -> None:
    purpose = Tagged(
        value="Interdict armor",
        epistemic_status="INFERENCE",
        basis=("synth:ollama",),
        confidence="low",
    )
    understanding = _base_understanding(purpose=purpose, task=None)

    result = _run(understanding, "yes\nEscort the convoy\n")

    assert len(result.player_intent) == 2
    ids = [tagged.value.question_id for tagged in result.player_intent]
    assert ids == ["purpose", "task"]
    assert result.player_intent[0].value.parsed is True
    assert result.player_intent[1].value.parsed == "Escort the convoy"
