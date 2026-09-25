"""D10's validator (`plans/brain-layer/plan.md`) -- the deterministic,
body-side, pure-function check every `belief.escalation.BrainReply`
passes before `belief.crew_console.CrewConsole` acts on it or speaks it.
No I/O: takes the escalated `belief.utterance.PartialParse` (for the
candidate list `find_contact` already assembled) and the original
transcript (for the `BECAUSE` verbatim-quote check), and returns either
`reply` unchanged or a degraded replacement -- **never raises**.

This is the safety net Measurements 3/4 (`plans/brain-layer/plan.md`)
exist to justify: a small model that silently picks on a genuinely
ambiguous reference is exactly the failure D10 is built to catch. The
plan's own worked example is this module's single required test: a wrong
`PICK CONTACT_7 BECAUSE "tank"` (both candidates are T-72s, so "tank"
does not discriminate) must be converted to `ASK`.

**D10, in full, and where each rule is implemented:**

1. The reply is one of the four allowed forms, or it is rejected. Already
   enforced upstream -- `belief.brain_client._reply_from_dict` never
   constructs a `BrainReply` whose `kind` is not one of `pick`/`ask`/
   `confirm`/`unable` (its own docstring: "a structural, type/shape parse
   of untrusted cross-process JSON"), and `BrainReply.kind`'s own type is
   the closed `Literal`. `validate_brain_reply` below dispatches
   exhaustively over those four, with nothing left to reject at this
   level.
2. `PICK <id>` -- `<id>` must be one of the candidate ids *this payload
   supplied*, not merely a contact that exists (`_validate_pick`).
3. `PICK ... BECAUSE <words>` -- `<words>` must appear literally
   (case-insensitively) in the transcript **and** in the chosen
   candidate's own `why` text, **and must not** appear in any other
   candidate's `why` text (`_validate_pick`). The why-field check is what
   "must not be equally true of another candidate" turns into as a pure
   substring test: `"tank"` names neither candidate's own `why` text at
   all (both say "T-72", not "tank"), so it fails to discriminate
   *and* fails to positively support the chosen one -- both readings
   converge on the same required outcome. `"near Gemerek"` does appear in
   one candidate's own `why` and not the other's, so it passes.
4. `CONFIRM <token>` -- `<token>` must be in `dispatched_command_tokens`
   (`_validate_confirm`).
5. `UNABLE <reason>` -- `<reason>` must be one of D11's three tokens
   (`_validate_unable`).
6. Any rejection degrades to `ASK` if the payload offered candidates,
   else to `UNABLE NO_MATCH` (`_degrade`) -- never silence, never a
   guess."""

from __future__ import annotations

from belief.escalation import BrainReply
from belief.utterance import PartialParse

#: D11's closed set of `UNABLE` reasons a *decider* may emit. Structural
#: reasons (`decider.structural_unable_reason`'s `NO_SUCH_COMMAND`/
#: `NO_MATCH`, `brain-layer/src/decider.py`) never reach a model call in
#: the first place, so in practice only `NO_LINE_OF_SIGHT` is a genuine
#: model judgement -- but this set is D11's own three-reason vocabulary,
#: not merely "whatever `decider.py` happens to emit today," so an
#: `UNABLE` naming any of the three validates regardless of which path
#: produced it.
VALID_UNABLE_REASONS: frozenset[str] = frozenset(
    {"NO_SUCH_COMMAND", "NO_MATCH", "NO_LINE_OF_SIGHT"}
)


def validate_brain_reply(
    reply: BrainReply,
    parse: PartialParse,
    transcript: str,
    dispatched_command_tokens: frozenset[str],
) -> BrainReply:
    """The one entry point `belief.crew_console.CrewConsole._handle_brain_
    reply` calls before dispatching a reply -- see module docstring for
    D10's rules and where each lives."""
    if reply.kind == "pick":
        return _validate_pick(reply, parse, transcript)
    if reply.kind == "confirm":
        return _validate_confirm(reply, parse, dispatched_command_tokens)
    if reply.kind == "unable":
        return _validate_unable(reply, parse)
    return reply  # "ask" -- always legal, nothing to validate


def _degrade(reply: BrainReply, parse: PartialParse) -> BrainReply:
    """D10 point 6."""
    if parse.referenced_contact_candidates:
        return BrainReply(
            utterance_id=reply.utterance_id, kind="ask", t_sim=reply.t_sim
        )
    return BrainReply(
        utterance_id=reply.utterance_id,
        kind="unable",
        t_sim=reply.t_sim,
        reason="NO_MATCH",
    )


def _validate_pick(
    reply: BrainReply, parse: PartialParse, transcript: str
) -> BrainReply:
    candidate_why: dict[str, str] = {
        candidate.id: candidate.why for candidate in parse.referenced_contact_candidates
    }
    if reply.contact_id is None or reply.contact_id not in candidate_why:
        return _degrade(reply, parse)

    because = reply.because
    if because is None or not because.strip():
        return _degrade(reply, parse)
    words = because.strip().lower()

    if words not in transcript.lower():
        return _degrade(reply, parse)

    chosen_why = candidate_why[reply.contact_id].lower()
    if words not in chosen_why:
        return _degrade(reply, parse)

    for other_id, other_why in candidate_why.items():
        if other_id == reply.contact_id:
            continue
        if words in other_why.lower():
            return _degrade(reply, parse)

    return reply


def _validate_confirm(
    reply: BrainReply, parse: PartialParse, dispatched_command_tokens: frozenset[str]
) -> BrainReply:
    if reply.token is None or reply.token not in dispatched_command_tokens:
        return _degrade(reply, parse)
    return reply


def _validate_unable(reply: BrainReply, parse: PartialParse) -> BrainReply:
    if reply.reason is None or reply.reason not in VALID_UNABLE_REASONS:
        return _degrade(reply, parse)
    return reply


__all__ = ["VALID_UNABLE_REASONS", "validate_brain_reply"]
