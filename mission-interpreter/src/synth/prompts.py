"""Builds the Ollama request for MI-4's capable-model synthesis stage:
system + user messages, and the structured-output JSON schema
(`plans/mi4-capable-model-synthesis/plan.md`).

**Structural prevention of overclaiming**: `RESPONSE_SCHEMA`'s
`epistemic_status` enum is restricted to `["INFERENCE", "ASSUMPTION"]`
only -- `FACT`/`OBSERVATION`/`UNKNOWN` are not valid values the schema
itself will accept, so the model is structurally prevented from
self-tagging as `FACT`, not merely instructed not to (the same class of
hard-boundary-over-convention as PB-6's grounding check, per the plan's
Decision 3 cross-reference). `synth/synthesize.py` re-validates this as
defense in depth, since Ollama's structured-output enforcement is not
confirmed live against the installed daemon/model (see
`ollama_client.py`'s docstring).

**Never a raw coordinate, never a group name.** The only mission facts
that make it into `_build_user_text` are: already-established
`MissionUnderstanding` fields (theatre, ownship, route length -- all
FACT/OBSERVATION, never touching a hidden/lateActivation group), briefing
prose, and `EnrichedThreatSignal`s rendered through `_threat_signal_line`,
which reads only `WorldRef.position`'s nested place-name field / a
`name_matches` entry's `name` -- never `EnrichedThreatSignal`'s underlying
`x`/`z` (which don't even exist on that type -- see its docstring) and
never a `ThreatSignal`'s raw coordinate. `test_synth_synthesize.py`'s
coordinate-leak regression test is the concrete proof this holds.
"""

from __future__ import annotations

from typing import Any

from miz.tree import BriefingText
from schema.understanding import MissionUnderstanding
from world_enrich.schema import EnrichedThreatSignal, WorldRef

_EPISTEMIC_STATUS_ENUM = ["INFERENCE", "ASSUMPTION"]
_CONFIDENCE_ENUM = ["low", "medium", "high"]

_SYSTEM_PROMPT = (
    "You are assisting a DCS World Mi-24P Hind crew's pre-mission briefing "
    "analysis. You are given established mission facts (theatre, ownship, "
    "route) and a mission briefing, plus a coarse summary of possible "
    "threats reported or expected near named places. From this alone, "
    "infer the mission's overall purpose, ownship's specific task, and a "
    "list of known threats.\n\n"
    "You have no information beyond what is given to you. You must never "
    "claim direct knowledge or certainty: every value you produce must be "
    "tagged 'INFERENCE' (a reasoned conclusion drawn from the given facts) "
    "or 'ASSUMPTION' (a plausible guess not directly supported by the "
    "given facts). Also give each value a 'confidence' of 'low', 'medium', "
    "or 'high', and a short 'basis' string naming what you based it on."
)


def _tagged_text_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "value": {"type": "string"},
            "epistemic_status": {"type": "string", "enum": _EPISTEMIC_STATUS_ENUM},
            "basis": {"type": "string"},
            "confidence": {"type": "string", "enum": _CONFIDENCE_ENUM},
        },
        "required": ["value", "epistemic_status", "basis", "confidence"],
    }


def _threat_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "kind": {"type": "string"},
            "description": {"type": "string"},
            "epistemic_status": {"type": "string", "enum": _EPISTEMIC_STATUS_ENUM},
            "basis": {"type": "string"},
            "confidence": {"type": "string", "enum": _CONFIDENCE_ENUM},
        },
        "required": ["kind", "description", "epistemic_status", "basis", "confidence"],
    }


RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "purpose": _tagged_text_schema(),
        "task": _tagged_text_schema(),
        "known_threats": {"type": "array", "items": _threat_schema()},
    },
    "required": ["purpose", "task", "known_threats"],
}


def build_messages(
    understanding: MissionUnderstanding,
    briefing: BriefingText,
    threat_signals: tuple[EnrichedThreatSignal, ...],
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _build_user_text(understanding, briefing, threat_signals),
        },
    ]


def _build_user_text(
    understanding: MissionUnderstanding,
    briefing: BriefingText,
    threat_signals: tuple[EnrichedThreatSignal, ...],
) -> str:
    lines = [f"Theatre: {understanding.theatre.value}"]

    ownship = understanding.ownship.value
    if ownship is not None:
        lines.append(f"Ownship aircraft: {ownship.aircraft}, flight: {ownship.flight}")
    lines.append(f"Ownship route has {len(understanding.route.value)} waypoint(s).")

    for label, text in (
        ("Mission briefing", briefing.description_text),
        ("Blue task", briefing.description_blue_task),
        ("Sortie", briefing.sortie),
    ):
        if text:
            lines.append(f"{label}: {text}")

    if threat_signals:
        lines.append("Possible threats reported near named places:")
        lines.extend(f"- {_threat_signal_line(signal)}" for signal in threat_signals)
    else:
        lines.append("No threat signals reported.")

    return "\n".join(lines)


def _threat_signal_line(signal: EnrichedThreatSignal) -> str:
    place = _place_name(signal.world_ref)
    if place is not None:
        return f"{signal.kind} reported/expected near {place}"
    return f"{signal.kind} reported/expected in the area (no named place nearby)"


def _place_name(world_ref: WorldRef) -> str | None:
    """Reads only `WorldRef.position`'s nested place-name field / a
    `name_matches` entry's `name` -- never a raw `x`/`z` value. See this
    module's docstring for why that boundary matters here specifically."""
    if world_ref.name_matches:
        name = world_ref.name_matches[0].get("name")
        if isinstance(name, str) and name:
            return name
    position = world_ref.position
    nearest = position.get("nearest_settlement") if isinstance(position, dict) else None
    if isinstance(nearest, dict):
        name = nearest.get("name")
        if isinstance(name, str) and name:
            return name
    return None
