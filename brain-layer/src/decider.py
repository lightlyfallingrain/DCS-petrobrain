"""The `Decider` protocol and Stage 1's model-free implementation
(`plans/brain-layer/plan.md` Stage 1) -- the thing that turns one
escalation payload into one reply from the closed vocabulary D5/D10/D11
define: `PICK <id> BECAUSE <words>`, `ASK`, `CONFIRM <token>`, or
`UNABLE <reason>`. Stage 1 never calls Ollama; `OllamaDecider` is Stage
2's addition behind this same protocol.

**Wire shape, not prose.** Unlike the plan's D5/D10 discussion of a model's
raw one-line text answer, `Decider.decide` returns an already-structured
dict (`{"kind": "pick"|"ask"|"confirm"|"unable", ...}`) -- the "one line
drawn from a closed vocabulary" constraint is about what a *model* is
allowed to produce internally (Stage 2's `OllamaDecider` prompt/parse
step, D10's validator), not about the wire format between this process and
body-layer. `StubDecider` is plain code with nothing to parse, so it
builds the structured reply directly; `server.py` serialises whatever a
`Decider` returns straight onto `GET /replies/poll`.

**`structural_unable_reason` is deliberately its own function, not a
branch inside `StubDecider`.** D11: two of the three `UNABLE` reasons are
"decided structurally by code rather than by any decider... [it] usually
can[, n]either needs asking" -- i.e. this is a fact read off the payload,
not a judgement call, so it belongs in a shared helper both `StubDecider`
today and `OllamaDecider` (Stage 2) can call *before* reaching for any
model-specific logic, rather than being reinvented per decider."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from final_reply import final_to_dict, parse_final_text
from ollama_client import OllamaClient, OllamaRequestError
from prompts import render_classify_prompt, render_discriminate_prompt
from tool_loop_prompts import (
    build_system_prompt,
    build_user_message,
    tool_to_json_schema,
)

#: D11's closed set, minus `NO_LINE_OF_SIGHT` -- that reason needs a real
#: world-model LOS call this module has no access to (the payload crossing
#: the wire is plain JSON, no world-model connection), so it is not
#: structurally derivable here. Nothing in Stage 1's scope emits a
#: place-directed command that would need it (see plan D11's own table).
_NO_SUCH_COMMAND = "NO_SUCH_COMMAND"
_NO_MATCH = "NO_MATCH"


def structural_unable_reason(payload: dict[str, Any]) -> str | None:
    """Whichever of D11's two structural `UNABLE` reasons `payload` already
    proves, or `None` when neither applies and genuine judgement (a real
    `PICK`/`ASK`/`CONFIRM` decision) remains.

    `payload["partial_parse"]` is `belief.utterance.PartialParse` carried
    across the wire (`belief.brain_client.BrainLayerClient`'s own
    serialisation) -- `matched_intent is None` means no verb in body's
    deterministic grammar matched at all (`NO_SUCH_COMMAND`);
    a matched intent with zero `referenced_contact_candidates` means the
    command needs a referent and none was found (`NO_MATCH`). One or more
    candidates is the genuine-judgement case (`ASK`/`PICK`), left to the
    caller."""
    parse = payload.get("partial_parse") or {}
    if parse.get("matched_intent") is None:
        return _NO_SUCH_COMMAND
    candidates = parse.get("referenced_contact_candidates") or []
    if not candidates:
        return _NO_MATCH
    return None


class Decider(Protocol):
    """One escalation payload in, one structured reply dict out. No I/O
    contract implied -- `StubDecider` does none; `OllamaDecider` (Stage 2)
    will call Ollama from inside this method."""

    def decide(self, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class StubDecider:
    """Stage 1's `Decider` -- deterministic, no model call at all. Exists
    to prove the async round trip (D2/D3/D4/D8) end to end with **zero
    model risk** (plan Stage 1): every hard part of the design is provable
    at the REPL with Ollama not running.

    `delay_s` is the configurable artificial delay the plan's Stage 1
    acceptance criteria are measured against (set to 8.0 to reproduce the
    plan's own worked scenario) -- stands in for real inference latency so
    `job.py`'s newest-wins/staleness machinery and `crew_console.py`'s
    stand-by/D4 revalidation logic are exercised without any model
    dependency.

    `reply`, when set, is returned verbatim regardless of `payload` -- test
    control, for forcing a specific `PICK`/`ASK`/`CONFIRM`/`UNABLE` case
    (the task's own requirement: "the stub must be able to emit UNABLE
    <reason> with the three closed reasons"). When unset, the stub falls
    back to `structural_unable_reason` and then, absent a structural
    reason, a bare `ASK` naming every candidate the payload itself
    offered -- there is no free judgement in a stub, and `ASK` is the
    honest answer to "which one" when nothing distinguishes them (the same
    degrade-rather-than-guess posture D10 requires of a real decider)."""

    delay_s: float = 0.0
    reply: dict[str, Any] | None = None

    def decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.delay_s > 0:
            time.sleep(self.delay_s)
        if self.reply is not None:
            return dict(self.reply)
        reason = structural_unable_reason(payload)
        if reason is not None:
            return {"kind": "unable", "reason": reason}
        return {"kind": "ask"}


#: `num_ctx`, set explicitly rather than inherited from Ollama's own 32k
#: default (D6: "the default costs 4.6GB of nothing" -- measured on this
#: machine 2026-09-25, dropping to `num_ctx=2048` takes the default
#: model's resident footprint from 7.5GB to 2.9GB). BR-1's own prompts
#: measure ~155 tokens; 2048 is comfortable headroom, not a tight fit.
DEFAULT_NUM_CTX = 2048

#: Generous above the ~6-token closed-vocabulary answer D6 measured, to
#: leave room for a `BECAUSE <words>` clause quoting several words of the
#: transcript -- still small enough that a runaway generation (the
#: fabricated-justification failure mode D6 also measured, "qwen3 told to
#: 'think step by step' produced 575 tokens") is capped well short of
#: that, not merely discouraged by the prompt's own wording.
DEFAULT_NUM_PREDICT = 40

#: `PICK <id> BECAUSE <words>` -- id is whatever token immediately follows
#: "PICK" (no internal whitespace, matching how `partial_parse`'s
#: candidate ids are always built body-side); `<words>` is everything
#: after "BECAUSE", trimmed. Case-insensitive on the two keywords only,
#: never on the id or the quoted words themselves.
_PICK_BECAUSE_RE = re.compile(
    r"^\s*PICK\s+(\S+)\s+BECAUSE\s+(.+?)\s*$", re.IGNORECASE | re.DOTALL
)
_ASK_RE = re.compile(r"^\s*ASK\s*$", re.IGNORECASE)
_CONFIRM_RE = re.compile(r"^\s*CONFIRM\s+(\S+)\s*$", re.IGNORECASE)
_UNABLE_RE = re.compile(r"^\s*UNABLE\s*$", re.IGNORECASE)

#: Quote characters the model wraps its `BECAUSE` evidence in, stripped by
#: `_unquote` below. Straight and typographic pairs both appear -- a model
#: that has read prose produces the latter.
_QUOTE_PAIRS: tuple[tuple[str, str], ...] = (
    ('"', '"'),
    ("'", "'"),
    ("“", "”"),
    ("‘", "’"),
)


def _unquote(words: str) -> str:
    """Strip one matched pair of surrounding quotes from a `PICK ...
    BECAUSE <words>` reply's evidence.

    **Not cosmetic -- without this, no `PICK` can ever pass D10's
    verbatim-quote check, whatever the model says.**
    `prompts.DISCRIMINATE_PROMPT` renders the transcript as `Pilot said:
    "..."`, so the model mirrors that quoting and answers `PICK CONTACT_7
    BECAUSE "near Gemerek"`. `belief.brain_reply`'s first rule then tests
    whether the evidence appears verbatim in the transcript -- and the
    transcript contains `near Gemerek`, never `"near Gemerek"`. The quote
    characters alone reject it, independently of whether the model chose
    a genuinely discriminating word (found live, reviewer session
    2026-09-25 -- reproduced directly against the installed code, not
    merely read).

    Deliberately strips only *one matched pair*, and only when the string
    both starts and ends with it: evidence that legitimately contains a
    quote mid-string is left alone, and an unbalanced quote is left for
    D10 to reject rather than silently repaired here -- repairing it
    would be this parser guessing at intent, which is exactly what the
    "structural parse only" rule forbids."""
    stripped = words.strip()
    for opening, closing in _QUOTE_PAIRS:
        if (
            len(stripped) >= 2
            and stripped.startswith(opening)
            and stripped.endswith(closing)
        ):
            return stripped[1:-1].strip()
    return stripped


def _parse_discriminate_reply(raw: str) -> dict[str, Any]:
    """Parses a model's raw text answer to `prompts.DISCRIMINATE_PROMPT`
    into a structured reply dict. **Never raises and never invents a
    pick** -- anything that is not cleanly `PICK <id> BECAUSE <words>` or
    `ASK` degrades to `{"kind": "ask"}`, the same "unparseable is not the
    same as wrong, but it is never acted on directly" posture D10's
    validator applies to a semantically-invalid reply (this function only
    handles *syntactic* parsing; D10's own membership/verbatim-quote
    checks run body-side, on the structured dict this function
    produces). `because` is passed through `_unquote` -- see that
    function's own docstring for why this is required, not optional."""
    pick_match = _PICK_BECAUSE_RE.match(raw)
    if pick_match is not None:
        contact_id, because = pick_match.groups()
        return {"kind": "pick", "contact_id": contact_id, "because": _unquote(because)}
    if _ASK_RE.match(raw) is not None:
        return {"kind": "ask"}
    return {"kind": "ask"}


def _parse_classify_reply(raw: str) -> dict[str, Any]:
    """Parses a model's raw text answer to `prompts.CLASSIFY_PROMPT` into
    a structured reply dict. Anything that is not cleanly
    `CONFIRM <command>` or `UNABLE` -- including outright unparseable
    text -- degrades to `{"kind": "unable", "reason": _NO_SUCH_COMMAND}`,
    the honest default for a call only ever reached because code already
    found no verb match (module docstring)."""
    confirm_match = _CONFIRM_RE.match(raw)
    if confirm_match is not None:
        return {"kind": "confirm", "token": confirm_match.group(1)}
    return {"kind": "unable", "reason": _NO_SUCH_COMMAND}


@dataclass
class OllamaDecider:
    """Stage 2's real `Decider` -- calls a local Ollama daemon through
    `ollama_client.OllamaClient`, using D5's two prompt shapes
    (`prompts.py`). Reuses `structural_unable_reason` exactly as
    `StubDecider` does (module docstring), so the two code-decidable
    `UNABLE` reasons never touch the model:

    - `NO_MATCH` (matched intent, zero candidates) -- returned directly,
      no model call. D11: "an empty candidate list *is* `NO_MATCH`... it
      needs no asking."
    - `NO_SUCH_COMMAND` (no matched intent at all) -- routed to the
      **classify** prompt. This is the one case `structural_unable_reason`
      surfaces without fully resolving: D11's scope also wants "plausibly
      a command the deterministic grammar missed" to become `CONFIRM
      <token>` rather than an automatic refusal, and only a model can make
      that call.
    - Neither reason (one or more candidates offered) -- routed to the
      **discriminate** prompt (`PICK <id> BECAUSE <words>` or `ASK`).

    `model`/`num_ctx`/`num_predict` are all plain fields, never hardcoded
    constants -- D6: "the model is expected to be swapped... no model
    name is compiled into any logic." `__main__.py`'s `--brain-model` is
    this field's one caller."""

    model: str
    ollama_client: OllamaClient = field(default_factory=OllamaClient)
    num_ctx: int = DEFAULT_NUM_CTX
    num_predict: int = DEFAULT_NUM_PREDICT

    def decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        reason = structural_unable_reason(payload)
        if reason == _NO_MATCH:
            return {"kind": "unable", "reason": reason}
        transcript = payload.get("transcript")
        transcript_text = transcript if isinstance(transcript, str) else ""
        if reason == _NO_SUCH_COMMAND:
            return self._classify(transcript_text)
        return self._discriminate(transcript_text, payload)

    def _classify(self, transcript: str) -> dict[str, Any]:
        raw = self.ollama_client.generate(
            model=self.model,
            prompt=render_classify_prompt(transcript),
            num_ctx=self.num_ctx,
            num_predict=self.num_predict,
        )
        return _parse_classify_reply(raw)

    def _discriminate(self, transcript: str, payload: dict[str, Any]) -> dict[str, Any]:
        parse = payload.get("partial_parse") or {}
        raw_candidates = parse.get("referenced_contact_candidates") or []
        candidates: list[tuple[str, str]] = [
            (str(candidate.get("id", "")), str(candidate.get("why", "")))
            for candidate in raw_candidates
            if isinstance(candidate, dict)
        ]
        raw = self.ollama_client.generate(
            model=self.model,
            prompt=render_discriminate_prompt(transcript, candidates),
            num_ctx=self.num_ctx,
            num_predict=self.num_predict,
        )
        return _parse_discriminate_reply(raw)


#: `brain-layer/research/2026-11-12-tool-call-form.md` conclusion 2/4 --
#: Stage 0's measured `num_ctx` (the largest prompt seen was 1801 tokens
#: at this value, with headroom) and round cap. `TOOL_LOOP_NUM_CTX`
#: deliberately does not reuse `DEFAULT_NUM_CTX` above (BR-1's own 2048,
#: measured against a ~155-token prompt) even though the numbers
#: coincide today -- the two are independent measurements against very
#: different prompt sizes, and a future change to one must not silently
#: move the other.
TOOL_LOOP_NUM_CTX = 2048

#: Conclusion 3 -- `BRAIN_MAX_TOOL_ROUNDS`' body-side default (plan D9).
#: brain-layer has no tuning loader (root `CLAUDE.md`'s "Outside
#: body-layer the loader does not exist yet"), so this stays a plain
#: literal; noted here as wanting the mechanism if this subproject ever
#: grows one.
TOOL_LOOP_MAX_ROUNDS = 4

#: Generous relative to a `FINAL ...` line's own length (~20-60 tokens
#: measured) -- large enough that a `BECAUSE`/slots clause is never cut
#: off mid-line, small enough that a runaway generation is still capped,
#: same reasoning as `DEFAULT_NUM_PREDICT` above but sized for this
#: prompt's longer closed vocabulary (four final forms, not one).
TOOL_LOOP_NUM_PREDICT = 120

#: Per-round network timeout for the tool loop's own `OllamaClient`
#: instance -- independent of `ollama_client.DEFAULT_TIMEOUT_S` (5.0s,
#: BR-1's own two-call-per-decide budget) because a tool-loop turn can
#: run up to `TOOL_LOOP_MAX_ROUNDS + 1` rounds, each needing to fit
#: inside `server.py`'s own `DEFAULT_DECIDE_TIMEOUT_S` (12.0s) -- a
#: single round, not the whole turn, is what `decide()` is called for
#: (D1: each round is its own `POST /escalate`), so this is sized the
#: same as a BR-1 round rather than the whole turn's budget. Plain
#: literal, same "no tuning loader here" note as the two constants
#: above.
TOOL_LOOP_TIMEOUT_S = 5.0


@dataclass
class ToolLoopDecider:
    """`plans/brain-tool-calls/plan.md` D1's `Decider` for `mode ==
    "addressed"` -- one `decide()` call is one round (D1: brain-layer is
    stateless across rounds; body-layer's `steps`/`round` carry the
    turn's own history on the wire, re-sent every POST). Builds the
    system prompt once per call from `payload["tools"]`/`["commands"]`
    (byte-stable within a turn, R3 -- `tools` never changes process-wide
    and `commands` is `()` throughout Stage 2) and the user message from
    `payload["transcript"]`/`["situational_header"]`/`["steps"]`, then
    calls Ollama's native `/api/chat` `tools` (Stage 0's measured
    winner -- `brain-layer/research/2026-11-12-tool-call-form.md`
    conclusion 1).

    Returns one of the wire shapes `belief.escalation.BrainReply`
    decodes: `{"kind": "tool_call", "tool": ..., "args": ...}` from a
    native `tool_calls` entry, or `final_reply.final_to_dict`'s dict
    from a `FINAL ...` line in `content`. **Never raises and never
    invents** -- a transport failure (`OllamaRequestError`, Ollama
    itself unreachable or wedged) degrades to `{"kind": "unable",
    "reason": "NO_BRAIN"}`, D4's own wording for exactly this case ("If
    brain-layer is up but Ollama is not, brain-layer replies `unable
    NO_BRAIN`" -- body's *own* `available()` check guards the other
    half, "brain-layer itself is down"), and a malformed/multi-tool-call
    reply degrades to `{"kind": "ask"}` so body's own D3 validator (which
    has the actual candidate set to render from) decides what "ask" ends
    up meaning rather than this decider guessing at refs it cannot see."""

    model: str
    ollama_client: OllamaClient = field(default_factory=OllamaClient)
    num_ctx: int = TOOL_LOOP_NUM_CTX
    num_predict: int = TOOL_LOOP_NUM_PREDICT

    def decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        tools_raw = payload.get("tools") or []
        commands_raw = payload.get("commands") or []
        tools = tuple(t for t in tools_raw if isinstance(t, dict))
        commands = tuple(c for c in commands_raw if isinstance(c, dict))
        transcript = payload.get("transcript")
        transcript_text = transcript if isinstance(transcript, str) else ""
        header = payload.get("situational_header")
        header_dict = header if isinstance(header, dict) else {}
        steps_raw = payload.get("steps") or []
        steps = tuple(s for s in steps_raw if isinstance(s, dict))

        system_prompt = build_system_prompt(tools, commands)
        user_message = build_user_message(transcript_text, header_dict, steps)
        native_tool_schemas = [tool_to_json_schema(tool) for tool in tools]

        try:
            result = self.ollama_client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                tools=native_tool_schemas,
                num_ctx=self.num_ctx,
                num_predict=self.num_predict,
            )
        except OllamaRequestError:
            return {"kind": "unable", "reason": "NO_BRAIN"}

        if result.tool_calls:
            if len(result.tool_calls) != 1:
                # D3's "one round, one tool" rule has no native-API
                # equivalent to appeal to -- more than one call in a
                # single reply is simply not well-formed. Degrading to
                # `ask` (not `tool_call`) means body's own validator
                # never sees an ambiguous multi-call reply at all.
                return {"kind": "ask"}
            call = result.tool_calls[0]
            return {
                "kind": "tool_call",
                "tool": call.name,
                "args": dict(call.arguments),
            }

        parsed = parse_final_text(result.content)
        final_dict = final_to_dict(parsed)
        if final_dict is None:
            return {"kind": "ask"}
        return final_dict
