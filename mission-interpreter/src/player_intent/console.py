"""`PlayerIntentConsole`: MI-5's typed console loop
(`plans/mi5-player-questions/plan.md`, Implementation Plan stage 3).

Mirrors `body-layer/src/belief/crew_console.py`'s shape (typed line in,
structured field out, an input/output `TextIO` pair for testability) --
a pattern to copy, not a shared import: root `CLAUDE.md`'s module-
independence rule makes body-layer<->world-model the sole in-process
cross-subproject exception, so this is its own small dataclass + function.

**Re-prompt once, then give up (Decision 3, resolved).** A `"bool"`/
`"choice"` question that fails to parse gets one re-prompt. If the second
attempt also fails, the raw line is recorded as-is with `question_kind`
still reflecting what was actually asked (not silently promoted to look
like a real typed answer) -- so a consumer reading `PlayerAnswer` can tell
"this is a real `bool`" from "this is unparsed text left over from a
failed `bool` question." `"free_text"` questions never fail to parse
(any line, including blank, is accepted verbatim).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TextIO

from player_intent.questions import Question, detect_questions
from schema.tags import Tagged
from schema.understanding import MissionUnderstanding, PlayerAnswer

_BOOL_TRUE = ("y", "yes", "true", "1")
_BOOL_FALSE = ("n", "no", "false", "0")

_RETRY_PROMPT = "Sorry, I didn't understand that. Please try again."
_MAX_ATTEMPTS = 2


@dataclass(frozen=True, slots=True)
class PlayerIntentConsole:
    """One console session over an input/output `TextIO` pair -- `input_`
    is read one line at a time (`readline`), `output` receives every
    prompt (`write`), mirroring `crew_console.py`'s `TextIO`-pair
    convention for `io.StringIO`-based testing without real stdin/stdout."""

    input_: TextIO
    output: TextIO

    def run(self, understanding: MissionUnderstanding) -> MissionUnderstanding:
        questions = detect_questions(understanding)
        answers: list[Tagged[PlayerAnswer]] = []
        for question in questions:
            answers.append(self._ask(question))
        return dataclasses.replace(understanding, player_intent=tuple(answers))

    def _ask(self, question: Question) -> Tagged[PlayerAnswer]:
        line = ""
        parsed: bool | str | int | None = None
        for attempt in range(_MAX_ATTEMPTS):
            if attempt > 0:
                self.output.write(_RETRY_PROMPT + "\n")
            self._print_prompt(question)
            line = self._read_line()
            parsed = _parse(question, line)
            if parsed is not None:
                break

        if parsed is None:
            # Gave up after `_MAX_ATTEMPTS` (2) attempts -- record the raw
            # line as unparsed free_text while preserving the original
            # question_kind, per this module's docstring.
            answer = PlayerAnswer(
                question_id=question.id,
                question_text=question.text,
                question_kind=question.kind,
                parsed=line,
            )
        else:
            answer = PlayerAnswer(
                question_id=question.id,
                question_text=question.text,
                question_kind=question.kind,
                parsed=parsed,
            )

        return Tagged(value=answer, epistemic_status="FACT", basis=("player:console",))

    def _print_prompt(self, question: Question) -> None:
        self.output.write(question.text + "\n")
        if question.kind == "choice":
            for index, option in enumerate(question.options, start=1):
                self.output.write(f"  {index}) {option}\n")

    def _read_line(self) -> str:
        line = self.input_.readline()
        return line.rstrip("\n")


def _parse(question: Question, line: str) -> bool | str | int | None:
    """Returns the typed value, or `None` on parse failure (`"free_text"`
    never fails)."""
    if question.kind == "free_text":
        return line
    if question.kind == "bool":
        return _parse_bool(line)
    return _parse_choice(question, line)


def _parse_bool(line: str) -> bool | None:
    normalized = line.strip().lower()
    if normalized in _BOOL_TRUE:
        return True
    if normalized in _BOOL_FALSE:
        return False
    return None


def _parse_choice(question: Question, line: str) -> str | None:
    normalized = line.strip()
    if normalized.isdigit():
        index = int(normalized)
        if 1 <= index <= len(question.options):
            return question.options[index - 1]
        return None
    lowered = normalized.lower()
    for option in question.options:
        if option.lower() == lowered:
            return option
    return None
