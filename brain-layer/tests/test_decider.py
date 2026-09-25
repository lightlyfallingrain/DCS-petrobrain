from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from decider import (
    OllamaDecider,
    StubDecider,
    _parse_classify_reply,
    _parse_discriminate_reply,
    _unquote,
    structural_unable_reason,
)


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


# --- _unquote ------------------------------------------------------------


def test_unquote_strips_a_matched_straight_quote_pair() -> None:
    assert _unquote('"village"') == "village"
    assert _unquote("'village'") == "village"


def test_unquote_strips_a_matched_typographic_quote_pair() -> None:
    # A model that has read prose produces these -- not just straight
    # ASCII quotes.
    assert _unquote("“village”") == "village"
    assert _unquote("‘village’") == "village"


def test_unquote_leaves_a_mid_string_quote_alone() -> None:
    # Only one *matched surrounding* pair is stripped -- evidence that
    # legitimately contains a quote keeps it.
    assert _unquote('the "big" one') == 'the "big" one'


def test_unquote_leaves_an_unbalanced_quote_alone() -> None:
    # Left for D10 to reject rather than silently repaired here --
    # repairing it would be this parser guessing at intent.
    assert _unquote('"unbalanced') == '"unbalanced'


def test_unquote_no_quotes_is_a_no_op() -> None:
    assert _unquote("near the village") == "near the village"


# --- _parse_discriminate_reply / _parse_classify_reply -----------------


def test_parse_discriminate_reply_pick_because() -> None:
    """`because` is unquoted by `decider._unquote`: the discriminate
    prompt renders the transcript as `Pilot said: "..."`, so the model
    mirrors that quoting and D10 (body-side) compares the evidence
    against a transcript that contains no quote characters at all."""
    result = _parse_discriminate_reply('PICK CONTACT_7 BECAUSE "near the village"')
    assert result == {
        "kind": "pick",
        "contact_id": "CONTACT_7",
        "because": "near the village",
    }


def test_parse_discriminate_reply_is_case_insensitive_on_keywords() -> None:
    result = _parse_discriminate_reply("pick CONTACT_7 because near the village")
    assert result == {
        "kind": "pick",
        "contact_id": "CONTACT_7",
        "because": "near the village",
    }


def test_parse_discriminate_reply_ask() -> None:
    assert _parse_discriminate_reply("ASK") == {"kind": "ask"}
    assert _parse_discriminate_reply("  ask  ") == {"kind": "ask"}


def test_parse_discriminate_reply_malformed_degrades_to_ask() -> None:
    """Unparseable model text never becomes a silent pick -- degrades to
    `ASK`, mirroring `StubDecider`'s own no-free-judgement posture. D10's
    own semantic checks (id offered, words actually discriminating) run
    body-side against whatever this function *does* manage to parse."""
    assert (
        _parse_discriminate_reply("I think it's the one by the village")["kind"]
        == "ask"
    )
    assert _parse_discriminate_reply("")["kind"] == "ask"


def test_parse_classify_reply_confirm() -> None:
    result = _parse_classify_reply("CONFIRM watch_nearest")
    assert result == {"kind": "confirm", "token": "watch_nearest"}


def test_parse_classify_reply_unable() -> None:
    assert _parse_classify_reply("UNABLE") == {
        "kind": "unable",
        "reason": "NO_SUCH_COMMAND",
    }


def test_parse_classify_reply_malformed_degrades_to_unable() -> None:
    assert _parse_classify_reply("I don't know what that means") == {
        "kind": "unable",
        "reason": "NO_SUCH_COMMAND",
    }


# --- OllamaDecider -------------------------------------------------------


@dataclass
class _FakeOllamaClient:
    """Records every `generate()` call and returns a scripted response --
    stands in for `ollama_client.OllamaClient` without a live Ollama
    daemon, per `brain-layer/CLAUDE.md`'s "Testing" section (every unit
    here is testable with no live Ollama process)."""

    scripted_response: str = "ASK"
    calls: list[dict[str, Any]] = field(default_factory=list)

    def generate(self, model: str, prompt: str, num_ctx: int, num_predict: int) -> str:
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            }
        )
        return self.scripted_response


def test_ollama_decider_no_match_is_structural_no_model_call() -> None:
    fake = _FakeOllamaClient()
    decider = OllamaDecider(model="test-model", ollama_client=fake)  # type: ignore[arg-type]
    result = decider.decide(_payload("set_attention", []))
    assert result == {"kind": "unable", "reason": "NO_MATCH"}
    assert fake.calls == []


def test_ollama_decider_no_such_command_calls_classify_prompt() -> None:
    fake = _FakeOllamaClient(scripted_response="CONFIRM watch_nearest")
    decider = OllamaDecider(model="test-model", ollama_client=fake)  # type: ignore[arg-type]
    payload = _payload(None, [])
    payload["transcript"] = "keep an eye on the nearest one"
    result = decider.decide(payload)
    assert result == {"kind": "confirm", "token": "watch_nearest"}
    assert len(fake.calls) == 1
    assert "keep an eye on the nearest one" in fake.calls[0]["prompt"]


def test_ollama_decider_candidates_present_calls_discriminate_prompt() -> None:
    fake = _FakeOllamaClient(scripted_response='PICK CONTACT_7 BECAUSE "near Gemerek"')
    decider = OllamaDecider(model="test-model", ollama_client=fake)  # type: ignore[arg-type]
    candidates = [
        {"id": "CONTACT_7", "why": "a T-72, near Gemerek"},
        {"id": "CONTACT_12", "why": "a T-72, on the road"},
    ]
    payload = _payload("set_attention", candidates)
    payload["transcript"] = "keep an eye on that tank near Gemerek"
    result = decider.decide(payload)
    # `because` is unquoted by `decider._unquote` -- see
    # `test_parse_discriminate_reply_pick_because`'s own docstring.
    assert result == {
        "kind": "pick",
        "contact_id": "CONTACT_7",
        "because": "near Gemerek",
    }
    assert len(fake.calls) == 1
    prompt = fake.calls[0]["prompt"]
    assert "CONTACT_7: a T-72, near Gemerek" in prompt
    assert "CONTACT_12: a T-72, on the road" in prompt


def test_ollama_decider_passes_num_ctx_and_num_predict_explicitly() -> None:
    fake = _FakeOllamaClient(scripted_response="ASK")
    decider = OllamaDecider(
        model="test-model",
        ollama_client=fake,
        num_ctx=999,
        num_predict=17,  # type: ignore[arg-type]
    )
    candidates = [{"id": "CONTACT_1", "why": "x"}, {"id": "CONTACT_2", "why": "y"}]
    decider.decide(_payload("set_attention", candidates))
    assert fake.calls[0]["num_ctx"] == 999
    assert fake.calls[0]["num_predict"] == 17
