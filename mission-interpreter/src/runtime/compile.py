"""`compile_current_mission`: the single pure, deterministic mapping from a
full `MissionUnderstanding` (MI-3/MI-4/MI-5's output) to the compact
`RuntimeMissionUnderstanding` -- `plans/mi6-runtime-compilation/plan.md`.

Mirrors `schema/build.py`'s shape/style exactly: one entry point, small
private helpers per field group. No model/LLM involved, no world-model
call -- everything here is table lookups, tuple filtering, and dataclass
reshaping over already-produced `Tagged` values.

**Player-intent reconciliation** is the actual substantive work of this
stage -- MI-5's `player_intent` tuple is otherwise never folded back into
the fields it answers (`console.run` only ever appends to it). Three
independently-testable rules, one per question-id pattern MI-5's
`questions.detect_questions` actually produces today:

- `question_id == "ownship"` -- only ever asked as `free_text` today
  (`_ownship_candidates` is always empty, see `questions.py`'s docstring),
  so the player's raw answer string becomes the compact `ownship` display
  identifier, tagged `FACT`, `basis=("player:console",)`.
- `question_id in ("purpose", "task")` -- two cases mirroring
  `_detect_purpose_or_task_question`: (a) the source field was `None`
  (always asked `free_text`) -> the answer *is* the compact value, `FACT`;
  if there is no answer either (no player_intent stage ran, or this
  question was never reached), the field stays unpopulated as
  `Tagged(value=None, epistemic_status="UNKNOWN", basis=())` -- "never had
  a guess". (b) the source field existed at `confidence == "low"` (always
  asked `bool`) -> `True` keeps the existing value but raises `confidence`
  to `"high"` and appends `"player:console"` to `basis` (`epistemic_status`
  is untouched -- player confirmation doesn't turn a model inference into
  ground truth); `False` clears the *value* to `None` but keeps the
  wrapping `Tagged` (`epistemic_status` unchanged from `source`, `basis`
  gains `"player:rejected"`, `confidence` reset to `None`) -- "the model
  guessed, and the player said it's wrong," a different fact from "never
  had a guess," distinguished by non-empty `basis` alone. Both cases
  return `Tagged[str | None]`, never a bare `None`, which is why
  `RuntimeMissionUnderstanding.purpose`/`.task` are typed `Tagged[str |
  None]` rather than `Tagged[str] | None`.
- `question_id.startswith("threat_")` -- the trailing integer indexes into
  `understanding.known_threats` (stable: nothing between question
  detection and this compilation mutates that tuple). `True` keeps the
  threat in `expected_threats`, raises `confidence` to `"high"`, adds
  `"player:console"` to `basis`. `False` drops it from the *compact*
  projection only -- the raw `MissionUnderstanding.known_threats` this
  reads from is never mutated, mirroring MI-1.5's "raw tree keeps
  everything, filtered tree doesn't" pattern applied to a different filter
  axis. **This index-based lookup silently breaks if a future stage
  inserted between MI-5 and MI-6 reorders/filters `known_threats`** --
  flagged in the plan's Risks & Unknowns, not addressed here.
"""

from __future__ import annotations

from runtime.compact import (
    CompactLocation,
    CompactRoutePoint,
    RuntimeMissionUnderstanding,
)
from schema.tags import Tagged
from schema.understanding import MissionUnderstanding, PlayerAnswer, Threat


def compile_current_mission(
    understanding: MissionUnderstanding,
) -> RuntimeMissionUnderstanding:
    ownship = _reconcile_ownship(understanding)
    purpose = _reconcile_purpose_or_task(understanding, field_name="purpose")
    task = _reconcile_purpose_or_task(understanding, field_name="task")
    expected_threats = _reconcile_threats(understanding)

    return RuntimeMissionUnderstanding(
        schema_version=understanding.schema_version,
        theatre=understanding.theatre,
        ownship=ownship,
        purpose=purpose,
        task=task,
        phases=understanding.mission_phases,
        route=_build_route(understanding),
        key_locations=_build_key_locations(understanding),
        expected_threats=expected_threats,
    )


def _find_answer(
    understanding: MissionUnderstanding, question_id: str
) -> PlayerAnswer | None:
    for tagged_answer in understanding.player_intent:
        if tagged_answer.value.question_id == question_id:
            return tagged_answer.value
    return None


def _reconcile_ownship(understanding: MissionUnderstanding) -> Tagged[str]:
    source = understanding.ownship
    display = (
        f"{source.value.aircraft} ({source.value.flight})"
        if source.value is not None
        else ""
    )
    passthrough = Tagged(
        value=display,
        epistemic_status=source.epistemic_status,
        basis=source.basis,
        confidence=source.confidence,
    )

    answer = _find_answer(understanding, "ownship")
    if answer is None or not isinstance(answer.parsed, str):
        return passthrough

    return Tagged(
        value=answer.parsed, epistemic_status="FACT", basis=("player:console",)
    )


def _reconcile_purpose_or_task(
    understanding: MissionUnderstanding, *, field_name: str
) -> Tagged[str | None]:
    source = understanding.purpose if field_name == "purpose" else understanding.task
    answer = _find_answer(understanding, field_name)

    if source is None:
        # Never populated by MI-4 -- `questions.py` always asks a
        # `free_text` question in this case. If the player answered, that
        # answer *is* the value; if not (no player_intent stage ran at
        # all, or this question was never reached), the field stays
        # unpopulated -- but as `Tagged(None, "UNKNOWN", basis=())`, not a
        # bare `None`, so this "never had a guess" case stays
        # distinguishable from the "guessed and rejected" case below
        # purely by `basis` (empty here, non-empty there).
        if answer is not None and isinstance(answer.parsed, str):
            return Tagged(
                value=answer.parsed, epistemic_status="FACT", basis=("player:console",)
            )
        return Tagged(value=None, epistemic_status="UNKNOWN", basis=())

    if (
        source.confidence != "low"
        or answer is None
        or not isinstance(answer.parsed, bool)
    ):
        return Tagged(
            value=source.value,
            epistemic_status=source.epistemic_status,
            basis=source.basis,
            confidence=source.confidence,
        )

    if answer.parsed:
        return Tagged(
            value=source.value,
            epistemic_status=source.epistemic_status,
            basis=(*source.basis, "player:console"),
            confidence="high",
        )

    # Rejected: the model's guess was wrong -- an active correction, not
    # an absence of one. `epistemic_status` is left unchanged from `source`
    # for the same reason confirmation above doesn't upgrade it: the
    # player's act doesn't change *how the model arrived* at its
    # now-retracted guess. `confidence` resets to `None` since it
    # described the model's certainty in a value that no longer stands.
    # `basis` gaining `"player:rejected"` (non-empty) is what distinguishes
    # this from the "never had a guess" `Tagged(None, "UNKNOWN", ())` case
    # above -- a future BL-7 dialogue layer can use that to e.g. never
    # resurface this specific debunked value.
    return Tagged(
        value=None,
        epistemic_status=source.epistemic_status,
        basis=(*source.basis, "player:rejected"),
    )


def _build_route(
    understanding: MissionUnderstanding,
) -> tuple[Tagged[CompactRoutePoint], ...]:
    source = understanding.route
    points: list[Tagged[CompactRoutePoint]] = []
    for index, enriched_point in enumerate(source.value):
        name_matches = enriched_point.world_ref.name_matches
        place_name = _first_place_name(name_matches)
        points.append(
            Tagged(
                value=CompactRoutePoint(
                    index=index,
                    x=enriched_point.point.x,
                    y=enriched_point.point.y,
                    place_name=place_name,
                ),
                epistemic_status=source.epistemic_status,
                basis=source.basis,
                confidence=source.confidence,
            )
        )
    return tuple(points)


def _build_key_locations(
    understanding: MissionUnderstanding,
) -> tuple[Tagged[CompactLocation], ...]:
    locations: list[Tagged[CompactLocation]] = []
    for tagged_location in understanding.important_locations:
        location = tagged_location.value
        place_name = _first_place_name(location.world_ref.name_matches)
        locations.append(
            Tagged(
                value=CompactLocation(
                    id=location.id, kind=location.kind, place_name=place_name
                ),
                epistemic_status=tagged_location.epistemic_status,
                basis=tagged_location.basis,
                confidence=tagged_location.confidence,
            )
        )
    return tuple(locations)


def _first_place_name(name_matches: tuple[dict[str, object], ...]) -> str | None:
    if not name_matches:
        return None
    name = name_matches[0].get("name")
    return name if isinstance(name, str) else None


def _format_threat(threat: Threat) -> str:
    return f"{threat.kind}: {threat.description}"


def _reconcile_threats(understanding: MissionUnderstanding) -> tuple[Tagged[str], ...]:
    threats: list[Tagged[str]] = []
    for index, tagged_threat in enumerate(understanding.known_threats):
        answer = _find_answer(understanding, f"threat_{index}")
        if answer is not None and isinstance(answer.parsed, bool):
            if not answer.parsed:
                continue
            threats.append(
                Tagged(
                    value=_format_threat(tagged_threat.value),
                    epistemic_status=tagged_threat.epistemic_status,
                    basis=(*tagged_threat.basis, "player:console"),
                    confidence="high",
                )
            )
            continue
        threats.append(
            Tagged(
                value=_format_threat(tagged_threat.value),
                epistemic_status=tagged_threat.epistemic_status,
                basis=tagged_threat.basis,
                confidence=tagged_threat.confidence,
            )
        )
    return tuple(threats)
