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

from collections.abc import Mapping
from typing import TYPE_CHECKING

from belief.escalation import BrainReply
from belief.tool_api import BRAIN_TOOLS_BY_NAME, BrainTool, ParamSpec
from belief.utterance import PartialParse

if TYPE_CHECKING:
    from belief.crew_console import BrainTurn

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
#: stage. **Drift is unsafe in one of its two directions, and the
#: earlier wording here claimed otherwise** (found by the review of
#: `d51a25b`, 2026-09-25):
#:
#: - *Brain widens, body lags* -- a token added to
#:   `CLASSIFY_COMMAND_VOCABULARY` but not here. Fails safe: a legitimate
#:   `CONFIRM` is degraded to `ASK` until this list catches up. Annoying,
#:   never unsafe, because a stricter validator only refuses.
#: - *Brain narrows, body lags* -- a token **removed** from
#:   `CLASSIFY_COMMAND_VOCABULARY` but still listed here. This is the
#:   unsafe one, and it is the likely shape: retiring a token from what
#:   the model is *offered* does not retire the command itself, so it
#:   stays in `dispatched_command_tokens` and `_validate_confirm`'s
#:   and-of-both-checks still passes it. That reopens exactly the
#:   asymmetry this constant was added to close, scoped to the removed
#:   token.
#:
#: So the sync is not left to this comment:
#: `brain-layer/tests/test_prompts.py::test_offered_confirm_vocabulary_matches_body_layers_mirror`
#: compares the two literals by reading body-layer's source as text
#: (module independence forbids the import; reading a file is not one).
#: **If you edit either list, edit both** -- that test is what will tell
#: you, and it is the only thing that will.
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


def _evidence_passes(
    because: str | None, transcript: str, chosen_text: str, other_texts: list[str]
) -> bool:
    """D10 rule 3's substring evidence test, factored out so BR-2's
    ambiguity-evidence rule (D3) can reuse it against a differently-shaped
    candidate set (handle -> short text, from a tool observation) instead
    of only `ReferenceCandidate.why` -- `plans/brain-tool-calls/plan.md`'s
    own words, "those words must pass `_validate_pick`'s existing evidence
    test." `because` must be non-empty, appear in the transcript, appear
    in the chosen candidate's own text, and appear in **no** other
    candidate's text -- the same four checks `_validate_pick` always ran,
    now shared rather than duplicated."""
    if because is None or not because.strip():
        return False
    words = because.strip().lower()
    if words not in transcript.lower():
        return False
    if words not in chosen_text.lower():
        return False
    for other_text in other_texts:
        if words in other_text.lower():
            return False
    return True


def _validate_pick(
    reply: BrainReply, parse: PartialParse, transcript: str
) -> BrainReply:
    candidate_why: dict[str, str] = {
        candidate.id: candidate.why for candidate in parse.referenced_contact_candidates
    }
    if reply.contact_id is None or reply.contact_id not in candidate_why:
        return _degrade(reply, parse)
    chosen_why = candidate_why[reply.contact_id]
    other_whys = [why for cid, why in candidate_why.items() if cid != reply.contact_id]
    if not _evidence_passes(reply.because, transcript, chosen_why, other_whys):
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


#: `plans/brain-tool-calls/plan.md` D7's `unable` reasons for a tool-loop
#: *final* reply -- a distinct, smaller set from `VALID_UNABLE_REASONS`
#: above (D11's three BR-1-decider reasons; `NO_MATCH`/`NO_SUCH_COMMAND`/
#: `NO_LINE_OF_SIGHT` are never produced by `ToolLoopDecider`).
#: **`NO_BRAIN` is included even though D4's own table first speaks it
#: client-side** (the instant `BrainClient.available()` is false, before
#: any escalation is posted, for a *down* brain-layer process): D4 also
#: names the other half -- "If brain-layer is up but Ollama is not,
#: brain-layer replies `unable NO_BRAIN`" -- and that reply crosses the
#: wire as an ordinary `ToolLoopDecider` reason (`decider.py`'s own
#: `OllamaRequestError` branch), not a model judgement, so it belongs in
#: this validated set rather than being rejected as unrecognised.
VALID_TURN_UNABLE_REASONS: frozenset[str] = frozenset(
    {"NO_ANSWER", "NO_PLACE", "CANNOT_ANSWER", "FIXED_COMMAND_ONLY", "NO_BRAIN"}
)

#: D7's closed answer-form set.
ANSWER_FORMS: frozenset[str] = frozenset(
    {"our_position", "memory", "contacts", "nothing_seen"}
)

#: D7's own cap on how many contacts one `answer(contacts, refs)` may name
#: -- "For telling targets apart," not for enumerating every contact
#: offered this turn (that is what `list_contacts`/`find_contact`'s own
#: `ToolObservation` already did, inside the turn, never spoken verbatim).
ANSWER_CONTACTS_MAX_REFS = 3


def _canonical_args(args: Mapping[str, object]) -> tuple[tuple[str, object], ...]:
    return tuple(sorted(args.items(), key=lambda item: item[0]))


def validate_tool_call(
    tool_name: str, args: Mapping[str, object], turn: BrainTurn
) -> dict[str, object] | str:
    """D3's tool-call validator: name must be a `belief.tool_api.
    BRAIN_TOOLS` entry, unknown args are rejected, every argument is
    checked against its own `ParamSpec` (type/enum/range/length, and --
    for a `*_ref` kind -- offered-this-turn membership against
    `turn.offered`), and a `(tool, args)` pair already present in
    `turn.steps` this turn is rejected outright (the research note's
    design input: Stage 0 run 2 burned its whole round budget on one
    model repeating an identical `find_place` call with the observation
    sitting right there).

    Returns the validated args dict on success, or a short string naming
    *why* it failed on rejection -- `belief.crew_console`'s caller turns
    that string into the `invalid: <why>` observation D3 calls for, so
    the string's own wording is the model's one chance to recover inside
    the round budget (the research note's "the invalid-call observation
    must name the fix")."""
    tool: BrainTool | None = BRAIN_TOOLS_BY_NAME.get(tool_name)
    if tool is None:
        return f"no such tool {tool_name!r}"
    allowed_names = {param.name for param in tool.params}
    unknown = sorted(set(args) - allowed_names)
    if unknown:
        return f"{tool_name} has no parameter(s) {', '.join(unknown)}"
    validated: dict[str, object] = {}
    for param in tool.params:
        if param.name not in args:
            if param.required:
                return f"{tool_name} requires {param.name}"
            continue
        error = _check_param(param, args[param.name], turn)
        if error is not None:
            return f"{tool_name}.{param.name} {error}"
        validated[param.name] = args[param.name]
    canonical = (tool_name, _canonical_args(validated))
    for step in turn.steps:
        if (step.tool, _canonical_args(step.args)) == canonical:
            return (
                f"already called {tool_name} with these args, see the observation above"
            )
    return validated


def _check_param(param: ParamSpec, value: object, turn: BrainTurn) -> str | None:
    """One `ParamSpec`'s own check -- `None` on success, else the
    rejection reason's tail (the caller prefixes `"<tool>.<param> "`)."""
    if param.kind == "str":
        if not isinstance(value, str):
            return "must be text"
        if len(value) > param.max_len:
            return f"must be at most {param.max_len} characters"
        return None
    if param.kind == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            return "must be a whole number"
        if param.lo is not None and value < param.lo:
            return f"must be at least {param.lo}"
        if param.hi is not None and value > param.hi:
            return f"must be at most {param.hi}"
        return None
    if param.kind == "bool":
        if not isinstance(value, bool):
            return "must be true or false"
        return None
    if param.kind == "enum":
        if value not in param.choices:
            return f"must be one of {', '.join(param.choices)}"
        return None
    # contact_ref / place_ref / memory_ref
    if not isinstance(value, str):
        return "must be a handle"
    if param.allow_ownship and value == "ownship":
        return None
    if value not in turn.offered:
        return "was not offered this turn"
    return None


def _most_recent_candidate_set(
    turn: BrainTurn,
) -> tuple[tuple[str, str], ...] | None:
    return turn.candidate_sets[-1] if turn.candidate_sets else None


def _candidate_set_for_ref(
    turn: BrainTurn, ref: str
) -> tuple[tuple[str, str], ...] | None:
    """The most recent `turn.candidate_sets` entry containing `ref`, if
    any -- D3's ambiguity-evidence rule only applies when the picked ref
    actually came from a multi-candidate `find_*` result this turn, never
    to a ref the brain picked some other way (e.g. `describe_contact`'s
    single handle)."""
    for candidate_set in reversed(turn.candidate_sets):
        if any(candidate_id == ref for candidate_id, _ in candidate_set):
            return candidate_set
    return None


def _turn_degrade(turn: BrainTurn) -> BrainReply:
    """BR-2's own `_degrade` (D3 rule 6, same shape as the BR-1 one
    above): any rejection becomes `ask` over the most recent candidate
    set this turn actually offered, else `unable CANNOT_ANSWER` -- never
    silence, never a guess."""
    candidate_set = _most_recent_candidate_set(turn)
    if candidate_set:
        return BrainReply(
            utterance_id="", kind="ask", refs=tuple(c for c, _ in candidate_set)
        )
    return BrainReply(utterance_id="", kind="unable", reason="CANNOT_ANSWER")


def validate_turn_final(
    reply: BrainReply, turn: BrainTurn, transcript: str
) -> BrainReply:
    """D3's validator for a tool-loop turn's *final* reply (`answer`/
    `command`/`ask`/`unable`) -- the counterpart to `validate_tool_call`
    above for a round that does not call a tool. Preserves `reply`'s own
    `utterance_id`/`t_sim` on every degrade, unlike `_turn_degrade`'s bare
    constructor (which `belief.crew_console` never sees directly)."""
    if reply.kind == "unable":
        if reply.reason not in VALID_TURN_UNABLE_REASONS:
            return _carry_ids(reply, _turn_degrade(turn))
        return reply
    if reply.kind == "ask":
        return reply
    if reply.kind == "answer":
        return _validate_turn_answer(reply, turn, transcript)
    if reply.kind == "command":
        return _validate_turn_command(reply, turn, transcript)
    # Anything else reaching here (a stray `tool_call`/`pick`/`confirm`
    # the caller did not already special-case) is not a legal final.
    return _carry_ids(reply, _turn_degrade(turn))


def _carry_ids(reply: BrainReply, degraded: BrainReply) -> BrainReply:
    return BrainReply(
        utterance_id=reply.utterance_id,
        kind=degraded.kind,
        t_sim=reply.t_sim,
        refs=degraded.refs,
        reason=degraded.reason,
    )


def _validate_turn_answer(
    reply: BrainReply, turn: BrainTurn, transcript: str
) -> BrainReply:
    form = reply.form
    refs = reply.refs or ()
    if form not in ANSWER_FORMS:
        return _carry_ids(reply, _turn_degrade(turn))
    if form in ("our_position", "nothing_seen"):
        return reply
    if not refs or any(ref not in turn.offered for ref in refs):
        return _carry_ids(reply, _turn_degrade(turn))
    if form == "contacts":
        if len(refs) > ANSWER_CONTACTS_MAX_REFS:
            return _carry_ids(reply, _turn_degrade(turn))
        if len(refs) == 1:
            candidate_set = _candidate_set_for_ref(turn, refs[0])
            if candidate_set is not None and len(candidate_set) >= 2:
                texts = dict(candidate_set)
                chosen_text = texts[refs[0]]
                other_texts = [text for cid, text in texts.items() if cid != refs[0]]
                if not _evidence_passes(
                    reply.because, transcript, chosen_text, other_texts
                ):
                    return BrainReply(
                        utterance_id=reply.utterance_id,
                        kind="ask",
                        t_sim=reply.t_sim,
                        refs=tuple(texts),
                    )
    return reply


def _validate_turn_command(
    reply: BrainReply, turn: BrainTurn, transcript: str
) -> BrainReply:
    """**Stage 3 hook, not a dispatcher** -- `belief.tool_api.
    BRAIN_COMMANDS` does not exist yet (plan Stage 3), so there is no
    allowlist a `command` final could be checked against. Structural
    shape is validated anyway (a `target` must be offered, same rule as
    every other `*_ref`) so a malformed command degrades exactly like a
    malformed answer rather than being dispatched on trust once Stage 3
    does add the allowlist -- but every *legal-shaped* command final
    still degrades to `unable CANNOT_ANSWER` here, deliberately, because
    nothing downstream of this function can act on it yet. Chosen over
    `FIXED_COMMAND_ONLY` (the plan's other suggested wording): that
    reason means "this specific command is excluded by policy" (U2), and
    a command final in Stage 2 is excluded by *construction*, not by
    policy -- using `FIXED_COMMAND_ONLY` here would make Stage 3's own
    U2 degrade indistinguishable from "not built yet" once it ships."""
    if reply.target is not None and reply.target not in turn.offered:
        return _carry_ids(reply, _turn_degrade(turn))
    del transcript  # no evidence check possible with no command allowlist yet
    return BrainReply(
        utterance_id=reply.utterance_id,
        kind="unable",
        t_sim=reply.t_sim,
        reason="CANNOT_ANSWER",
    )


__all__ = [
    "ANSWER_CONTACTS_MAX_REFS",
    "ANSWER_FORMS",
    "OFFERED_CONFIRM_VOCABULARY",
    "VALID_TURN_UNABLE_REASONS",
    "VALID_UNABLE_REASONS",
    "validate_brain_reply",
    "validate_tool_call",
    "validate_turn_final",
]
