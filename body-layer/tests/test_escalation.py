"""Tests for `belief.escalation` -- `plans/bl5a-text-mode-crew-interaction/
plan.md` Stage 3's `handle_player_utterance` (the one body->brain entry
point) and the `NullBrainClient`/`DebugPrintBrainClient` stand-ins."""

from __future__ import annotations

import io
import sqlite3

from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext
from belief.escalation import (
    DebugPrintBrainClient,
    EscalationPayload,
    NullBrainClient,
    handle_player_utterance,
)
from belief.utterance import PartialParse, PlayerUtterance
from perception.source import OwnshipState


class _CapturingBrainClient:
    """A fake `BrainClient` that records the payload it was handed, so
    tests can assert on `handle_player_utterance`'s construction without
    depending on either real stand-in's side effects."""

    def __init__(self) -> None:
        self.payloads: list[EscalationPayload] = []

    def handle(self, payload: EscalationPayload) -> None:
        self.payloads.append(payload)

    def awaiting_reply_id(self) -> str | None:
        return None


def _utterance(transcript: str = "should we go north?") -> PlayerUtterance:
    parse = PartialParse(
        matched_intent=None,
        confidence=0.0,
        disposition="escalated",
        reason_escalated="unmatched",
    )
    return PlayerUtterance(
        id="UTTERANCE_1",
        t_sim=42.0,
        transcript=transcript,
        transcript_confidence=1.0,
        source="debug_console",
        parse=parse,
    )


def test_handle_player_utterance_builds_the_expected_payload() -> None:
    store = ContactStore()
    brain_client = _CapturingBrainClient()
    utterance = _utterance()

    handle_player_utterance(store, utterance, brain_client)

    assert len(brain_client.payloads) == 1
    payload = brain_client.payloads[0]
    assert payload.utterance_id == "UTTERANCE_1"
    assert payload.transcript == "should we go north?"
    assert payload.transcript_confidence == 1.0
    assert payload.t_sim == 42.0
    assert payload.partial_parse is utterance.parse
    assert payload.awaiting_reply_to is None


def test_situational_header_omits_our_position_without_enrichment() -> None:
    store = ContactStore()
    brain_client = _CapturingBrainClient()

    handle_player_utterance(store, _utterance(), brain_client)

    header = brain_client.payloads[0].situational_header
    assert header["contact_counts"] == 0
    assert header["estimated_units"] == 0
    assert "our_position" not in header


def test_situational_header_includes_our_position_with_enrichment() -> None:
    store = ContactStore()
    brain_client = _CapturingBrainClient()
    enrichment = EnrichmentContext(
        conn=sqlite3.connect(":memory:"),
        theatre="Syria",
        ownship=OwnshipState(
            t_sim=0.0, x=111.0, z=222.0, alt_m=500.0, heading_true_deg=0.0
        ),
    )

    handle_player_utterance(store, _utterance(), brain_client, enrichment)

    header = brain_client.payloads[0].situational_header
    assert header["our_position"] == {"x": 111.0, "z": 222.0}
    assert header["estimated_units"] == 0


def test_null_brain_client_produces_no_output_and_no_reply() -> None:
    client = NullBrainClient()
    store = ContactStore()
    handle_player_utterance(store, _utterance(), client)  # must not raise
    assert client.awaiting_reply_id() is None


def test_debug_print_brain_client_prints_to_its_stream() -> None:
    stream = io.StringIO()
    client = DebugPrintBrainClient(stream=stream)
    store = ContactStore()

    handle_player_utterance(store, _utterance("keep an eye on that shilka"), client)

    output = stream.getvalue()
    assert "[escalated - no brain yet]" in output
    assert "keep an eye on that shilka" in output
    assert client.awaiting_reply_id() is None
