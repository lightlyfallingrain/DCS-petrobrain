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


def test_confirm_token_actually_offered_by_classify_prompt_passes_unchanged() -> None:
    """Security review, `plans/brain-layer/security-review.md`'s Stage 2
    section: `_validate_confirm` must accept a token the classify prompt
    genuinely offers, not just one that happens to be in body's full
    dispatchable set. `dispatched_command_tokens` here is body's real,
    wide token set (not the narrow `_TOKENS` fixture above) so this
    exercises both membership checks, not just the offered-vocabulary
    one."""
    parse = _parse([])
    reply = BrainReply(utterance_id="U1", kind="confirm", token="watch_nearest")
    dispatched_command_tokens = frozenset(
        {"watch_nearest", "scan_bearing_deg", "report_bearing_deg", "follow"}
    )
    result = validate_brain_reply(
        reply, parse, "watch the closest one", dispatched_command_tokens
    )
    assert result == reply


def test_confirm_of_a_real_but_unoffered_dispatch_token_is_rejected() -> None:
    """The asymmetry this stage's fix closes: `scan_bearing_deg` is a
    real, dispatchable command (`crew_console.DISPATCHED_COMMAND_TOKENS`)
    but is never in `prompts.CLASSIFY_COMMAND_VOCABULARY` -- the classify
    prompt never offers it, because it takes a slot (a bearing in
    degrees) the model was never asked to extract. A `CONFIRM` naming it
    must degrade even though `scan_bearing_deg` is, on its own, a
    perfectly legal token elsewhere in the system."""
    parse = _parse([("CONTACT_1", "a T-72")])
    reply = BrainReply(utterance_id="U1", kind="confirm", token="scan_bearing_deg")
    dispatched_command_tokens = frozenset(
        {"watch_nearest", "scan_bearing_deg", "report_bearing_deg", "follow"}
    )
    result = validate_brain_reply(
        reply, parse, "scan bearing three one seven", dispatched_command_tokens
    )
    assert result.kind == "ask"


def test_confirm_of_a_hallucinated_unoffered_token_degrades_to_a_safe_confirm_prompt() -> (
    None
):
    """Confirms the existing safe-degradation path this stage must not
    weaken (task brief): even a `CONFIRM` naming a real, slot-taking
    dispatch token that was never offered degrades to `ASK` here rather
    than reaching `crew_console._handle_brain_confirm` at all -- the
    validator is the gate, and `_describe_token_for_confirm`'s
    slots=None graceful fallback / `handle_command`'s "say again" degrade
    (`crew_console.py`) are never even exercised for a reply this
    module already rejected. This is D10 point 6 (`_degrade`) applying
    to the newly-tightened CONFIRM check exactly as it already does to
    every other rejection reason."""
    parse = _parse([("CONTACT_1", "a T-72")])
    reply = BrainReply(utterance_id="U1", kind="confirm", token="follow")
    dispatched_command_tokens = frozenset(
        {"watch_nearest", "scan_bearing_deg", "report_bearing_deg", "follow"}
    )
    result = validate_brain_reply(
        reply, parse, "follow that one", dispatched_command_tokens
    )
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
