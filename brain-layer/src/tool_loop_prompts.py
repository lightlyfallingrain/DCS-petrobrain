"""The `ToolLoopDecider` prompt (`decider.py`) -- `plans/brain-tool-calls/
plan.md` D1/Stage 2, built from `brain-layer/research/2026-11-12-tool-call-
form.md`'s own measured prompt rather than written fresh: that note's
"Design inputs for Stage 2" says plainly that its own prompt text, the
command notes, and the three worked examples are "the starting point for
`ToolLoopDecider`'s prompt." This module is that starting point, adapted
from the wire shapes body-layer actually sends (`belief.tool_api.
BRAIN_TOOL_SPECS`'s `{name, params: [{name, kind, required, choices, lo,
hi, max_len}]}`) rather than the probe's own local fixture dataclasses.

**Byte-stable prefix (R3).** `build_system_prompt` depends only on
`tools`/`commands`, both fixed for the whole process (`tools` is always
`belief.tool_api.BRAIN_TOOL_SPECS`; `commands` is `()` until Stage 3) --
so it is computed once by the caller and reused across every round of
every turn, exactly as the research note measured. Only `build_user_
message`'s own steps block grows between rounds."""

from __future__ import annotations

import json
from typing import Any

_KIND_TO_JSON_TYPE: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "bool": "boolean",
    "enum": "string",
    "contact_ref": "string",
    "place_ref": "string",
    "memory_ref": "string",
}

#: Same closed grammar the Stage 0 probe measured (`tools/stage0_tool_
#: call_probe.py`'s `_FINAL_GRAMMAR_BLOCK`), word for word except for the
#: `command` line's slot-schema wording -- Stage 2 has no commands to
#: offer yet (`commands` is always `()`), so that sentence is rendered
#: conditionally by `_command_block` below rather than hard-coded here.
_FINAL_GRAMMAR_BLOCK = """When you have what you need, finish with ONE line, exactly one of:
FINAL answer <form> <json list of refs>      -- form is one of: our_position (no refs), memory (mark refs), contacts (contact refs, at most 3), nothing_seen (no refs)
FINAL ask <json list of refs>                -- two or more candidates fit and nothing the pilot said tells them apart
FINAL unable <reason>                        -- reason is one of: NO_PLACE (pilot named a place no tool knows), CANNOT_ANSWER (no tool covers the question), FIXED_COMMAND_ONLY (the pilot wants an action, not an answer)

Rules:
- The header below lists only what has already been offered this turn. It is EMPTY at the start of most turns. An empty header never means "nothing out there": if the pilot asks about something the header does not contain, call a tool first. That is how you find out.
- Every ref you name must be one offered to you this turn, in the header or in a tool's observation. Never invent a ref, a position, a bearing or a range.
- Do not reply FINAL unable just because the header is empty. Reply FINAL unable only for the three reasons above.
- Never repeat a call already listed under "So far this turn": its observation is there, use it."""

_SYSTEM_PROMPT_HEAD = """You are Petrovich, the weapons officer in a Mi-24P attack helicopter, replying to your pilot who just spoke to you directly. You know only what the tools tell you this turn -- never invent a contact, a place, a position, a bearing, a range or a quantity that no tool gave you. Tools are how you look things up; use them before answering.

Reply with EXACTLY ONE line, nothing else, no explanation, no markdown, no thinking out loud. To look something up, call one of your tools -- do not write it out as text."""


def tool_to_json_schema(tool: dict[str, Any]) -> dict[str, Any]:
    """One `belief.tool_api.BRAIN_TOOL_SPECS` entry -> Ollama's native
    `/api/chat` `tools` entry shape (OpenAI-style function calling)."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in tool.get("params", []):
        prop: dict[str, Any] = {"type": _KIND_TO_JSON_TYPE.get(param["kind"], "string")}
        choices = param.get("choices")
        if choices:
            prop["enum"] = list(choices)
        properties[param["name"]] = prop
        if param.get("required"):
            required.append(param["name"])
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", tool["name"]),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def _command_block(commands: tuple[dict[str, Any], ...]) -> str:
    if not commands:
        return (
            "\n\nYou have no commands yet -- answer with FINAL answer/ask/unable only."
        )
    lines = [f"- {command['token']}" for command in commands]
    return (
        "\n\nCommands you may issue as a FINAL command, and no others:\n"
        + "\n".join(lines)
    )


def build_system_prompt(
    tools: tuple[dict[str, Any], ...], commands: tuple[dict[str, Any], ...]
) -> str:
    """Byte-stable across every round of every turn (R3) -- nothing
    turn-specific belongs in here; see module docstring."""
    return f"{_SYSTEM_PROMPT_HEAD}{_command_block(commands)}\n\n{_FINAL_GRAMMAR_BLOCK}"


def _render_header(header: dict[str, Any]) -> str:
    """Plain, since Stage 2's own header carries only `contact_counts`/
    `estimated_units`/`our_position` (`belief.escalation.
    _situational_header`) -- none of it is an offered ref the model may
    name (D2: the model discovers handles only through tool calls), so
    this is one line of scene-setting prose, not an offered-ref list."""
    counts = header.get("contact_counts")
    units = header.get("estimated_units")
    return (
        f"(Situation: {counts} contact(s), at least {units} unit(s) believed present.)"
    )


def _render_steps(steps: tuple[dict[str, Any], ...]) -> str:
    if not steps:
        return ""
    lines = ["", "So far this turn:"]
    for index, step in enumerate(steps, start=1):
        lines.append(f"{index}. CALL {step['tool']} {json.dumps(step['args'])}")
        lines.append(f"   OBSERVATION {json.dumps(step['observation'])}")
    return "\n".join(lines)


def build_user_message(
    transcript: str, header: dict[str, Any], steps: tuple[dict[str, Any], ...]
) -> str:
    """The per-round user message: the transcript and header are
    byte-stable across a turn's own rounds; only the steps block grows."""
    return (
        f'Pilot said: "{transcript}"\n\n{_render_header(header)}{_render_steps(steps)}'
    )


__all__ = [
    "build_system_prompt",
    "build_user_message",
    "tool_to_json_schema",
]
