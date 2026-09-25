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
4. `CONFIRM <token>` -- `<token>` must be in `OFFERED_CONFIRM_VOCABULARY`
   (what the classify prompt actually offered the model, see that
   constant's own docstring) **and** in `dispatched_command_tokens`
   (`_validate_confirm`). **Revised 2026-09-25** (security deep analysis,
   `plans/brain-layer/security-review.md`'s Stage 2 section): this used
   to check only `dispatched_command_tokens` -- body's *entire*
   dispatchable set, ~30 tokens including slot-taking ones
   (`scan_bearing_deg`, `report_bearing_deg`, `follow`) the classify
   prompt never offers -- so a hallucinated `CONFIRM` naming one of those
   validated even though the model was never given it as an option. This
   is the same asymmetry `_validate_pick` never had: that check was
   always against the candidate list *this payload offered*, never
   "any contact that exists." The prior gap failed safe (an odd confirm
   prompt via `_describe_token_for_confirm`'s slots=None fallback, then a
   "say again" degrade in `handle_command` if the pilot affirmed --
   `crew_console.py`'s own documented behaviour) rather than
   misdispatching, so this is defense-in-depth consistency, not a fix for
   a live hole -- and that graceful degradation is untouched by this
   revision, only reached less often now that the validator itself
   catches more.
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

#: The classify prompt's own offered vocabulary
#: (`brain-layer/src/prompts.py`'s `CLASSIFY_COMMAND_VOCABULARY`, 7
#: no-slot tokens), duplicated here for the same module-independence
#: reason brain-layer duplicates body's `DISPATCHED_COMMAND_TOKENS` in
#: the first place -- this process never imports `brain-layer/` code, so
#: there is no import to share instead. This is what closes the CONFIRM
#: validator's asymmetry with `PICK`'s own candidate-membership check
#: (`_validate_pick` already only accepts an id *this payload offered*,
#: never "any contact that exists somewhere"): `_validate_confirm` used
#: to accept any of body's ~30 dispatchable tokens, including
#: slot-taking ones (`scan_bearing_deg`, `report_bearing_deg`, `follow`)
#: the classify prompt never shows the model at all.
#:
#: `PICK`'s offered set is genuine per-escalation data (a different
#: candidate list every call) and is correctly wired through the wire
#: payload itself (`parse.referenced_contact_candidates`). This
#: vocabulary is not: every classify call offers the identical, fixed
#: 7 tokens `prompts.py` declares as a module constant, so serialising it
#: onto every `EscalationPayload` would resend the same unchanging value
#: every time for no correctness benefit -- a duplicated constant, kept
#: manually in sync (there is no cross-import to enforce it, and no
#: assertion in either test suite compares the two literals against each
#: other, since module independence forbids the import that would let one
#: side check the other directly), is the proportionate fix at this
#: stage. If this ever drifts in practice, the failure direction is
#: known: a legitimate `CONFIRM` for a newly-added classify token would
#: be wrongly degraded to `ASK` here until this list catches up --
#: annoying, never unsafe, since a stricter validator only ever refuses,
#: it does not admit a token the model was never offered.
OFFERED_CONFIRM_VOCABULARY: frozenset[str] = frozenset(
    {
        "watch_nearest",
        "watch_nearest_air_defence",
        "report_all",
        "cancel_task",
        "cancel_scan",
        "cancel_watch",
        "stop_talking",
    }
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
    if (
        reply.token is None
        or reply.token not in OFFERED_CONFIRM_VOCABULARY
        or reply.token not in dispatched_command_tokens
    ):
        return _degrade(reply, parse)
    return reply


def _validate_unable(reply: BrainReply, parse: PartialParse) -> BrainReply:
    if reply.reason is None or reply.reason not in VALID_UNABLE_REASONS:
        return _degrade(reply, parse)
    return reply


__all__ = [
    "OFFERED_CONFIRM_VOCABULARY",
    "VALID_UNABLE_REASONS",
    "validate_brain_reply",
]
