"""`synthesize_mission_understanding`: MI-4's entry point -- calls the
Ollama client with the prompt built by `prompts.py`, and parses the
response into `purpose`/`task`/`known_threats` `Tagged` values on a new
`MissionUnderstanding` (`plans/mi4-capable-model-synthesis/plan.md`).

**Defense in depth beyond the JSON schema constraint**: `prompts.py`'s
`RESPONSE_SCHEMA` already restricts `epistemic_status`/`confidence` to
valid enum values at the request level, but Ollama's structured-output
enforcement for the specific installed daemon/model isn't confirmed live
(see `ollama_client.py`'s docstring) -- so every parsed value is
re-validated here regardless, and a model that ignores the constraint
(e.g. emits `"FACT"`) raises `OllamaOutputError` rather than being
silently accepted or upgraded.

**Graceful degradation, not a hard failure**: on `OllamaOutputError` (bad
or schema-violating model output), this returns `understanding`
unchanged -- `purpose`/`task`/`known_threats` stay at MI-3's `None`/`()`
defaults for this pass, rather than failing the whole synthesis run over
one bad response. This is a real, stated tradeoff (see the plan's Risks
section): a MI-4 run can end up indistinguishable from "MI-4 never ran"
for whichever field failed, with only a log line as a signal. Whether that
needs a more visible signal (or a retry-with-stricter-instruction path) is
left to be revisited once a live run against the real sample mission shows
how often it actually happens (plan stage 6/7).

`OllamaUnavailableError` (the daemon itself unreachable) is deliberately
**not** caught here -- that is an environment problem the caller should
see and handle explicitly, not something this stage silently degrades on.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from miz.tree import BriefingText
from schema.tags import Confidence, EpistemicStatus, Tagged
from schema.understanding import MissionUnderstanding, Threat
from synth.ollama_client import OllamaClient, OllamaOutputError
from synth.prompts import RESPONSE_SCHEMA, build_messages
from world_enrich.schema import EnrichedThreatSignal

logger = logging.getLogger(__name__)

_VALID_EPISTEMIC_STATUS = ("INFERENCE", "ASSUMPTION")
_VALID_CONFIDENCE = ("low", "medium", "high")


def synthesize_mission_understanding(
    understanding: MissionUnderstanding,
    briefing: BriefingText,
    threat_signals: tuple[EnrichedThreatSignal, ...],
    client: OllamaClient,
) -> MissionUnderstanding:
    messages = build_messages(understanding, briefing, threat_signals)
    try:
        response = client.chat_json(messages, RESPONSE_SCHEMA)
        purpose, task, known_threats = _parse_response(response)
    except OllamaOutputError:
        logger.warning(
            "MI-4 synthesis produced unusable output; leaving purpose/task/"
            "known_threats unpopulated for this pass",
            exc_info=True,
        )
        return understanding

    return dataclasses.replace(
        understanding, purpose=purpose, task=task, known_threats=known_threats
    )


def _parse_response(
    response: dict[str, Any],
) -> tuple[Tagged[str], Tagged[str], tuple[Tagged[Threat], ...]]:
    purpose = _parse_tagged_text(response.get("purpose"), field_name="purpose")
    task = _parse_tagged_text(response.get("task"), field_name="task")

    raw_threats = response.get("known_threats")
    if not isinstance(raw_threats, list):
        raise OllamaOutputError("expected 'known_threats' to be a list")
    known_threats = tuple(_parse_tagged_threat(item) for item in raw_threats)

    return purpose, task, known_threats


def _parse_tagged_text(raw: Any, *, field_name: str) -> Tagged[str]:
    if not isinstance(raw, dict):
        raise OllamaOutputError(f"expected '{field_name}' to be a JSON object")
    value = raw.get("value")
    if not isinstance(value, str):
        raise OllamaOutputError(f"expected '{field_name}.value' to be a string")
    return Tagged(
        value=value,
        epistemic_status=_validated_epistemic_status(raw.get("epistemic_status")),
        basis=_validated_basis(raw.get("basis")),
        confidence=_validated_confidence(raw.get("confidence")),
    )


def _parse_tagged_threat(raw: Any) -> Tagged[Threat]:
    if not isinstance(raw, dict):
        raise OllamaOutputError(
            "expected each 'known_threats' entry to be a JSON object"
        )
    kind = raw.get("kind")
    description = raw.get("description")
    if not isinstance(kind, str) or not isinstance(description, str):
        raise OllamaOutputError(
            "expected each 'known_threats' entry to have string 'kind'/'description'"
        )
    threat = Threat(kind=kind, description=description, area_ref=None)
    return Tagged(
        value=threat,
        epistemic_status=_validated_epistemic_status(raw.get("epistemic_status")),
        basis=_validated_basis(raw.get("basis")),
        confidence=_validated_confidence(raw.get("confidence")),
    )


def _validated_epistemic_status(raw: Any) -> EpistemicStatus:
    """Rejects anything outside `{"INFERENCE", "ASSUMPTION"}` -- most
    importantly `"FACT"`, which the model must never be able to claim (see
    this module's docstring). This check exists independently of
    `prompts.RESPONSE_SCHEMA`'s enum restriction, not merely in case that
    schema constraint is bypassed."""
    if raw == "INFERENCE":
        return "INFERENCE"
    if raw == "ASSUMPTION":
        return "ASSUMPTION"
    raise OllamaOutputError(
        f"model produced epistemic_status={raw!r}; only "
        f"{_VALID_EPISTEMIC_STATUS} are allowed for synthesized values"
    )


def _validated_confidence(raw: Any) -> Confidence:
    if raw == "low":
        return "low"
    if raw == "medium":
        return "medium"
    if raw == "high":
        return "high"
    raise OllamaOutputError(
        f"model produced confidence={raw!r}; only {_VALID_CONFIDENCE} are allowed"
    )


def _validated_basis(raw: Any) -> tuple[str, ...]:
    if isinstance(raw, str) and raw:
        return (raw,)
    raise OllamaOutputError("expected 'basis' to be a non-empty string")
