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

import time
from dataclasses import dataclass
from typing import Any, Protocol

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
