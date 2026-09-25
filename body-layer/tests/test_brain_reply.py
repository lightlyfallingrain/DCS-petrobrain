"""Tests for `belief.brain_reply.validate_brain_reply` -- D10
(`plans/brain-layer/plan.md`). The required test here is
`test_wrong_pick_because_tank_degrades_to_ask`: the plan's own worked
example, a wrong `PICK CONTACT_7 BECAUSE "tank"` converted to `ASK`
because "tank" is equally (un)true of every candidate -- "the safety
net's only proof"."""

from __future__ import annotations

from belief.brain_reply import validate_brain_reply
from belief.escalation import BrainReply
from belief.utterance import PartialParse, ReferenceCandidate

_TOKENS: frozenset[str] = frozenset({"watch_nearest", "cancel_task", "report_all"})


def _parse(candidates: list[tuple[str, str]]) -> PartialParse:
    return PartialParse(
        matched_intent="set_attention",
        confidence=0.5,
        disposition="escalated",
        reason_escalated="ambiguous_reference",
        attention_level="watch",
        referenced_contact_candidates=tuple(
            ReferenceCandidate(id=cid, why=why) for cid, why in candidates
        ),
    )


_TWO_T72_CANDIDATES = [
    ("CONTACT_7", "a T-72, 2.1 km, near Gemerek village"),
    ("CONTACT_12", "a T-72, 3.4 km, on the road"),
]


def test_wrong_pick_because_tank_degrades_to_ask() -> None:
    """The plan's required test, verbatim: both candidates are T-72s, so
    "tank" -- present in the pilot's own words but naming neither
    candidate's own `why` text specifically -- must not be accepted as a
    discriminator. Converted to `ASK`, not silently acted on."""
    parse = _parse(_TWO_T72_CANDIDATES)
    reply = BrainReply(
        utterance_id="U1",
        kind="pick",
        t_sim=100.0,
        contact_id="CONTACT_7",
        because="tank",
    )
    result = validate_brain_reply(reply, parse, "keep an eye on that tank", _TOKENS)
    assert result.kind == "ask"
    assert result.utterance_id == "U1"
    assert result.t_sim == 100.0


def test_pick_because_a_genuine_discriminator_passes_unchanged() -> None:
    """Measurement 4's other half: "near Gemerek" names `CONTACT_7`'s own
    `why` text and not `CONTACT_12`'s -- a real discriminator, and the
    reply passes through unchanged."""
    parse = _parse(_TWO_T72_CANDIDATES)
    reply = BrainReply(
        utterance_id="U1",
        kind="pick",
        t_sim=100.0,
        contact_id="CONTACT_7",
        because="near Gemerek",
    )
    result = validate_brain_reply(
        reply, parse, "keep an eye on the one near Gemerek", _TOKENS
    )
    assert result == reply


def test_pick_id_not_among_offered_candidates_degrades() -> None:
    """D10 point 2: the id must be one of the candidates *this payload
    offered*, not merely a contact that exists elsewhere."""
    parse = _parse(_TWO_T72_CANDIDATES)
    reply = BrainReply(
        utterance_id="U1",
        kind="pick",
        t_sim=100.0,
        contact_id="CONTACT_99",
        because="near Gemerek",
    )
    result = validate_brain_reply(reply, parse, "keep an eye on that tank", _TOKENS)
    assert result.kind == "ask"


def test_pick_because_not_in_transcript_degrades() -> None:
    """A quote the model fabricated -- never actually said -- must not be
    trusted even if it happens to match a candidate's own `why` text."""
    parse = _parse(_TWO_T72_CANDIDATES)
    reply = BrainReply(
        utterance_id="U1",
        kind="pick",
        t_sim=100.0,
        contact_id="CONTACT_7",
        because="near Gemerek",
    )
    result = validate_brain_reply(reply, parse, "keep an eye on that tank", _TOKENS)
    assert result.kind == "ask"


def test_pick_with_no_candidates_offered_degrades_to_unable_no_match() -> None:
    """D10 point 6's second branch: no candidates were ever offered, so
    the degrade target is `UNABLE NO_MATCH`, not `ASK` (asking "which
    one" with nothing to offer would be its own kind of dishonest)."""
    parse = _parse([])
    reply = BrainReply(
        utterance_id="U1", kind="pick", t_sim=100.0, contact_id="CONTACT_1"
    )
    result = validate_brain_reply(reply, parse, "watch it", _TOKENS)
    assert result.kind == "unable"
    assert result.reason == "NO_MATCH"


def test_confirm_token_in_vocabulary_passes_unchanged() -> None:
    parse = _parse([])
    reply = BrainReply(utterance_id="U1", kind="confirm", token="watch_nearest")
    result = validate_brain_reply(reply, parse, "watch the closest one", _TOKENS)
    assert result == reply


def test_confirm_token_not_in_vocabulary_degrades() -> None:
    parse = _parse([("CONTACT_1", "a T-72")])
    reply = BrainReply(utterance_id="U1", kind="confirm", token="launch_the_nukes")
    result = validate_brain_reply(reply, parse, "do the thing", _TOKENS)
    assert result.kind == "ask"


def test_unable_with_a_valid_reason_passes_unchanged() -> None:
    parse = _parse([])
    reply = BrainReply(utterance_id="U1", kind="unable", reason="NO_SUCH_COMMAND")
    result = validate_brain_reply(reply, parse, "do a thing", _TOKENS)
    assert result == reply


def test_unable_with_an_unrecognised_reason_degrades() -> None:
    parse = _parse([("CONTACT_1", "a T-72")])
    reply = BrainReply(utterance_id="U1", kind="unable", reason="I_JUST_DONT_WANT_TO")
    result = validate_brain_reply(reply, parse, "watch that tank", _TOKENS)
    assert result.kind == "ask"


def test_pick_because_survives_the_exact_quoting_a_real_model_produces() -> None:
    """The composition regression test neither this file nor
    `brain-layer/tests/test_decider.py` had on its own (found by the
    Stage 2 review, `plans/brain-layer/review.md`): each side only ever
    fed `validate_brain_reply` hand-typed, already-unquoted evidence, and
    `decider.py`'s own tests asserted the *quoted* output as correct --
    so nobody ever checked what a real model's natural completion habit
    (mirroring this prompt's own `Pilot said: "..."` rendering) does to
    this validator.

    `because` here is exactly `decider._unquote`'s fixed output for the
    model's real reply `PICK CONTACT_7 BECAUSE "near Gemerek"` --
    unquoted *before* it ever reaches this module, per D10's own module
    docstring ("the wire format between this process and body-layer" is
    already-structured JSON, not free model text). Before that upstream
    fix, this exact `because` value arrived as `'"near Gemerek"'` and
    degraded a genuinely correct `PICK` to a spurious `ASK`, since the
    quote characters are not a substring of the transcript."""
    parse = _parse(_TWO_T72_CANDIDATES)
    reply = BrainReply(
        utterance_id="U1",
        kind="pick",
        t_sim=100.0,
        contact_id="CONTACT_7",
        because="near Gemerek",
    )
    result = validate_brain_reply(
        reply, parse, "keep an eye on the tank near Gemerek", _TOKENS
    )
    assert result == reply


def test_ask_always_passes_unchanged() -> None:
    parse = _parse(_TWO_T72_CANDIDATES)
    reply = BrainReply(utterance_id="U1", kind="ask", t_sim=100.0)
    result = validate_brain_reply(reply, parse, "keep an eye on that tank", _TOKENS)
    assert result == reply
