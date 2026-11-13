"""The closed `FINAL ...` grammar -- `plans/brain-tool-calls/plan.md`
Stage 0's measured form (`brain-layer/research/2026-11-12-tool-call-form.md`
conclusion 1: native `/api/chat` `tools` for the *call*, but every final
reply stays this one closed text line in `content`, in both forms). Moved
here from `tools/stage0_tool_call_probe.py`, which defined it first and
now imports it from here instead of carrying its own copy -- `ToolLoopDecider`
(`decider.py`) needs the identical parser the probe was measured against,
and the alternative (a second, hand-synced copy in `src/`) is exactly the
drift-by-duplication failure mode this project's own docstrings warn
against elsewhere (e.g. `belief.brain_reply`'s `OFFERED_CONFIRM_VOCABULARY`
comment on a mirrored constant's two unsafe drift directions).

**Pure parsing, no I/O, never raises.** Anything that is not cleanly one
of the four `FINAL ...` shapes is `ParsedLine(kind="malformed")` -- the
same "unparseable degrades, never invents" posture `decider.py`'s own
`_parse_discriminate_reply`/`_parse_classify_reply` already have."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_FINAL_COMMAND_RE = re.compile(
    r"^\s*FINAL\s+command\s+(\w+)\s+(\{.*\})\s*$", re.IGNORECASE | re.DOTALL
)
_FINAL_ANSWER_RE = re.compile(
    r"^\s*FINAL\s+answer\s+(\w+)\s+(\[.*\])\s*$", re.IGNORECASE | re.DOTALL
)
_FINAL_ASK_RE = re.compile(r"^\s*FINAL\s+ask\s+(\[.*\])\s*$", re.IGNORECASE | re.DOTALL)
_FINAL_UNABLE_RE = re.compile(r"^\s*FINAL\s+unable\s+(\w+)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedLine:
    """The parsed shape of one model reply line. `kind` is one of
    `"final_command"`, `"final_answer"`, `"final_ask"`, `"final_unable"`,
    `"malformed"` for anything `parse_final_text` itself produces. A bare
    tool call (Ollama's native `tool_calls`) is not this module's
    concern -- `decider.ToolLoopDecider` reads that straight off
    `ollama_client.ChatResult`, exactly as the Stage 0 probe's own
    `_interpret_native_result` already does.

    `tool`/`args` exist only for `tools/stage0_tool_call_probe.py`'s own
    *grammar*-form `"call"` kind (`CALL <tool> <json>>`, Stage 0's
    losing, now-measurement-only alternative) -- `parse_final_text` never
    sets either, and `final_to_dict` never reads them."""

    kind: str
    tool: str | None = None
    args: dict[str, Any] | None = None
    token: str | None = None
    slots: dict[str, Any] | None = None
    form: str | None = None
    refs: list[str] | None = None
    reason: str | None = None


def parse_final_text(text: str) -> ParsedLine:
    """The four `FINAL ...` shapes, exactly as measured in Stage 0 --
    used for a native reply's `content` (which must never itself contain
    a tool call; the model has the native `tools` field for that)."""
    stripped = text.strip()
    match = _FINAL_COMMAND_RE.match(stripped)
    if match:
        token, slots_json = match.groups()
        try:
            slots = json.loads(slots_json)
        except json.JSONDecodeError:
            return ParsedLine(kind="malformed")
        if not isinstance(slots, dict):
            return ParsedLine(kind="malformed")
        return ParsedLine(kind="final_command", token=token, slots=slots)
    match = _FINAL_ANSWER_RE.match(stripped)
    if match:
        form, refs_json = match.groups()
        try:
            refs_raw = json.loads(refs_json)
        except json.JSONDecodeError:
            return ParsedLine(kind="malformed")
        if not isinstance(refs_raw, list):
            return ParsedLine(kind="malformed")
        return ParsedLine(
            kind="final_answer", form=form, refs=[str(r) for r in refs_raw]
        )
    match = _FINAL_ASK_RE.match(stripped)
    if match:
        try:
            refs_raw = json.loads(match.group(1))
        except json.JSONDecodeError:
            return ParsedLine(kind="malformed")
        if not isinstance(refs_raw, list):
            return ParsedLine(kind="malformed")
        return ParsedLine(kind="final_ask", refs=[str(r) for r in refs_raw])
    match = _FINAL_UNABLE_RE.match(stripped)
    if match:
        return ParsedLine(kind="final_unable", reason=match.group(1))
    return ParsedLine(kind="malformed")


def final_to_dict(parsed: ParsedLine) -> dict[str, Any] | None:
    """`ParsedLine` -> the wire dict shape `belief.escalation.BrainReply`
    decodes (`kind` plus that kind's own fields) -- `None` for anything
    that is not one of the four final shapes (a `"malformed"` line, or a
    bare tool call, which this function is never called for)."""
    if parsed.kind == "final_command":
        slots = parsed.slots or {}
        return {
            "kind": "command",
            "token": parsed.token,
            "slots": slots,
            "target": slots.get("target"),
        }
    if parsed.kind == "final_answer":
        return {"kind": "answer", "form": parsed.form, "refs": parsed.refs or []}
    if parsed.kind == "final_ask":
        return {"kind": "ask", "refs": parsed.refs or []}
    if parsed.kind == "final_unable":
        return {"kind": "unable", "reason": parsed.reason}
    return None


__all__ = ["ParsedLine", "final_to_dict", "parse_final_text"]
