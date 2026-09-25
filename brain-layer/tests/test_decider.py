from __future__ import annotations

import time

from decider import StubDecider, structural_unable_reason


def _payload(matched_intent: str | None, candidates: list[dict[str, str]]) -> dict:
    return {
        "utterance_id": "U1",
        "partial_parse": {
            "matched_intent": matched_intent,
            "referenced_contact_candidates": candidates,
        },
    }


def test_structural_reason_no_such_command_when_no_verb_matched() -> None:
    assert structural_unable_reason(_payload(None, [])) == "NO_SUCH_COMMAND"


def test_structural_reason_no_match_when_verb_matched_but_no_candidates() -> None:
    assert structural_unable_reason(_payload("set_attention", [])) == "NO_MATCH"


def test_structural_reason_none_when_candidates_exist() -> None:
    candidates = [{"id": "CONTACT_1", "why": "a T-72"}]
    assert structural_unable_reason(_payload("set_attention", candidates)) is None


def test_stub_decider_no_delay_returns_immediately() -> None:
    decider = StubDecider(delay_s=0.0)
    start = time.monotonic()
    decider.decide(_payload(None, []))
    assert time.monotonic() - start < 0.1


def test_stub_decider_sleeps_for_configured_delay() -> None:
    decider = StubDecider(delay_s=0.05)
    start = time.monotonic()
    decider.decide(_payload(None, []))
    assert time.monotonic() - start >= 0.05


def test_stub_decider_structural_unable_no_such_command() -> None:
    decider = StubDecider()
    result = decider.decide(_payload(None, []))
    assert result == {"kind": "unable", "reason": "NO_SUCH_COMMAND"}


def test_stub_decider_structural_unable_no_match() -> None:
    decider = StubDecider()
    result = decider.decide(_payload("set_attention", []))
    assert result == {"kind": "unable", "reason": "NO_MATCH"}


def test_stub_decider_falls_back_to_ask_when_candidates_exist() -> None:
    decider = StubDecider()
    candidates = [{"id": "CONTACT_1", "why": "x"}, {"id": "CONTACT_2", "why": "y"}]
    result = decider.decide(_payload("set_attention", candidates))
    assert result == {"kind": "ask"}


def test_stub_decider_reply_override_wins_regardless_of_payload() -> None:
    forced = {"kind": "pick", "contact_id": "CONTACT_7", "because": "village"}
    decider = StubDecider(reply=forced)
    result = decider.decide(_payload(None, []))
    assert result == forced
    # Returned copy, not the same object -- a caller mutating the result
    # must not corrupt the stub's own configured reply for the next call.
    assert result is not forced
