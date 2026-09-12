"""`detect_questions`: MI-5's deterministic ambiguity detector
(`plans/mi5-player-questions/plan.md`, Implementation Plan stage 2).

Grounded in what MI-3/MI-4 actually produce today
(`Tagged.epistemic_status == "UNKNOWN"`, `Tagged.confidence == "low"`,
`purpose`/`task` left `None`) -- not the concept doc's three worked
examples, which depend on schema fields (`task.type`, `protected_element`,
a masking-terrain marker) that don't exist yet on `MissionUnderstanding`
(see the plan's Decision 1, resolved).

Pure function: reads `understanding` only, no model, no world-model call,
no I/O -- the cheapest stage of this plan to test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from schema.understanding import MissionUnderstanding


@dataclass(frozen=True, slots=True)
class Question:
    """One detected ambiguity to surface to the player. `options` is only
    populated for `kind="choice"` (1-based index answers are matched
    against it by `console.py`)."""

    id: str
    text: str
    kind: Literal["free_text", "bool", "choice"]
    options: tuple[str, ...] = field(default=())


def detect_questions(understanding: MissionUnderstanding) -> tuple[Question, ...]:
    questions: list[Question] = []

    ownship_question = _detect_ownship_question(understanding)
    if ownship_question is not None:
        questions.append(ownship_question)

    questions.extend(
        _detect_purpose_or_task_question(understanding, field_name="purpose")
    )
    questions.extend(_detect_purpose_or_task_question(understanding, field_name="task"))

    for index, threat in enumerate(understanding.known_threats):
        if threat.confidence == "low":
            questions.append(
                Question(
                    id=f"threat_{index}",
                    text=(
                        "Petrovich isn't sure about this: "
                        f"'{threat.value.description}'. Is that a real threat?"
                    ),
                    kind="bool",
                )
            )

    return tuple(questions)


def _detect_ownship_question(understanding: MissionUnderstanding) -> Question | None:
    if understanding.ownship.epistemic_status != "UNKNOWN":
        return None

    candidates = _ownship_candidates(understanding)
    if candidates:
        return Question(
            id="ownship",
            text="Which aircraft is yours?",
            kind="choice",
            options=candidates,
        )
    # `_build_ownship`'s UNKNOWN basis today is only a match count (e.g.
    # "found 2 Player/Client-skill units, expected exactly 1") -- no
    # enumerable candidate ids/names to build real `choice` options from.
    # Fall back to free_text for this one question only, per the plan's
    # Decision 3 / Implementation Plan stage 2 note, rather than inventing
    # unit data that isn't there. See the plan's stage 5 refinement note:
    # revisiting this requires `_build_ownship` itself to start recording
    # candidate ids/names.
    return Question(id="ownship", text="Which aircraft is yours?", kind="free_text")


def _ownship_candidates(understanding: MissionUnderstanding) -> tuple[str, ...]:
    """Placeholder extraction point for enumerable ownship candidates, once
    `_build_ownship` records them on `basis` -- always empty today (see
    `_detect_ownship_question`'s docstring)."""
    return ()


def _detect_purpose_or_task_question(
    understanding: MissionUnderstanding, *, field_name: Literal["purpose", "task"]
) -> tuple[Question, ...]:
    tagged = understanding.purpose if field_name == "purpose" else understanding.task

    if tagged is None:
        prompt_text = (
            "What is the mission's overall purpose?"
            if field_name == "purpose"
            else "What is ownship's task on this mission?"
        )
        return (Question(id=field_name, text=prompt_text, kind="free_text"),)

    if tagged.confidence == "low":
        label = "purpose" if field_name == "purpose" else "task"
        return (
            Question(
                id=field_name,
                text=(
                    f"Petrovich's best guess at the mission {label} is: "
                    f"'{tagged.value}'. Is that right?"
                ),
                kind="bool",
            ),
        )

    return ()
