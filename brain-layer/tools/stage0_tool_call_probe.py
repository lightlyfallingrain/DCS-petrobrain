"""Stage 0 probe for `plans/brain-tool-calls/plan.md` (BR-2): measures
which tool-call *form* a small local model handles better -- Ollama's
native `/api/chat` `tools`, or a closed one-line grammar in the style of
this subproject's own BR-1 `prompts.py` (`CALL <tool> <json-args>` /
`FINAL command|answer|ask|unable ...`). The plan's own D1 leaves the
choice to this measurement; nothing downstream depends on which form
wins.

**Not a test, and not runnable in an agent sandbox** (`plans/brain-tool-
calls/plan.md` Stage 0, citing BR-1.2: "Agent sandboxes have no route to
Ollama"). This is a CLI a human runs against a real `qwen3:4b-instruct-
2507-q4_K_M` on the user's own Mac, reads the printed summary table and
`--out` JSON from, and uses to fill in
`brain-layer/research/2026-11-12-tool-call-form.md`.

**The script itself plays "body".** For every tool call the model
makes, it looks up the fixture's own canned observation for that
`(tool, name)` pair (`stage0_cases.json`) and feeds it back as the next
round's input -- exactly the role `drain_brain` will play once BR-2
Stage 2 picks a form and builds the real tool loop. `BRAIN_MAX_TOOL_
ROUNDS` does not exist as a tunable yet (plan D9, body-side, not built
in this stage); `MAX_TOOL_ROUNDS` below is this probe's own stand-in for
that default, measured against on purpose so Stage 0's findings carry
over once the real constant ships.

**Why the system prompt is built once per form and never touched
inside the per-case, per-round loop** (plan R3): the plan's own finding
is that a byte-identical prompt *prefix* across calls is what lets
Ollama's inference engine reuse its KV cache -- `system_prompt` (tool
block or tools-API, command block, the closed FINAL grammar) is
identical for every round of every case run in a given form, and only
the per-case suffix (utterance, header) and the growing per-round steps
block are ever appended after it.

Usage (from `brain-layer`, matching `CLAUDE.md`'s `PYTHONPATH`
convention):

    PYTHONPATH=src .venv/bin/python tools/stage0_tool_call_probe.py \\
        --model qwen3:4b-instruct-2507-q4_K_M --form both \\
        --num-ctx 2048 4096 \\
        --cases tools/stage0_cases.json --out /tmp/stage0_results.json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from ollama_client import ChatResult, OllamaClient, OllamaRequestError

#: Stand-in for the body-side tunable `BRAIN_MAX_TOOL_ROUNDS` (plan D9,
#: default 4) -- not built yet; this probe measures against the stated
#: default so its findings transfer once the real constant exists.
MAX_TOOL_ROUNDS = 4

#: Generous relative to BR-1's own ~6-token closed-vocabulary replies
#: (`decider.DEFAULT_NUM_PREDICT`) -- a tool call's JSON arguments and a
#: `FINAL command <token> <json>` line both run longer than a bare
#: `PICK`/`ASK`, and a model that needs to think its way to a well-formed
#: line should not be cut off mid-line by too tight a cap, which this
#: probe would otherwise record as `well_formed=False` for the wrong
#: reason.
DEFAULT_NUM_PREDICT = 200


# --------------------------------------------------------------------------
# Fixture types (ParamSpec/ToolSpec mirror plan D2's shape; a brain-layer-
# local copy, not an import -- this subproject never imports body-layer,
# module independence, `brain-layer/CLAUDE.md`).
# --------------------------------------------------------------------------

ParamKind = Literal[
    "str", "int", "bool", "enum", "contact_ref", "place_ref", "memory_ref"
]


@dataclass(frozen=True)
class ParamSpec:
    name: str
    kind: ParamKind
    required: bool = False
    max_len: int = 40


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    params: tuple[ParamSpec, ...]


@dataclass(frozen=True)
class ObservationEntry:
    tool: str
    args_hint: dict[str, Any]
    observation: dict[str, Any]


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    utterance: str
    header: dict[str, Any]
    observations: tuple[ObservationEntry, ...]
    expected: dict[str, Any]


@dataclass(frozen=True)
class CaseFile:
    tools: tuple[ToolSpec, ...]
    commands: tuple[str, ...]
    cases: tuple[Case, ...]
    #: Optional one-line meaning per command token, rendered beside it.
    #: Added after the first Mac run: with bare tokens the model picked
    #: `watch_nearest {target}` for "keep an eye on the tank" (the slot
    #: belongs to `follow`). Stage 2's `BRAIN_COMMANDS` carries this as
    #: the slot schema + description, so the probe should too.
    command_notes: dict[str, str] = field(default_factory=dict)


def load_case_file(path: Path) -> CaseFile:
    data = json.loads(path.read_text())
    tools = tuple(
        ToolSpec(
            name=tool["name"],
            description=tool.get("description", ""),
            params=tuple(
                ParamSpec(
                    name=param["name"],
                    kind=param["kind"],
                    required=bool(param.get("required", False)),
                    max_len=int(param.get("max_len", 40)),
                )
                for param in tool.get("params", [])
            ),
        )
        for tool in data["tools"]
    )
    commands = tuple(data["commands"])
    command_notes = {str(k): str(v) for k, v in data.get("command_notes", {}).items()}
    cases = tuple(
        Case(
            id=case["id"],
            category=case.get("category", ""),
            utterance=case["utterance"],
            header=case.get("header", {}),
            observations=tuple(
                ObservationEntry(
                    tool=entry["tool"],
                    args_hint=entry.get("args_hint", {}),
                    observation=entry["observation"],
                )
                for entry in case.get("observations", [])
            ),
            expected=case["expected"],
        )
        for case in data["cases"]
    )
    return CaseFile(
        tools=tools, commands=commands, cases=cases, command_notes=command_notes
    )


# --------------------------------------------------------------------------
# Prompt rendering
# --------------------------------------------------------------------------

_KIND_TO_JSON_TYPE: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "bool": "boolean",
    "enum": "string",
    "contact_ref": "string",
    "place_ref": "string",
    "memory_ref": "string",
}


def render_tool_block(tools: tuple[ToolSpec, ...]) -> str:
    lines: list[str] = []
    for tool in tools:
        params = (
            ", ".join(
                f"{p.name}{'' if p.required else '?'}: {p.kind}" for p in tool.params
            )
            or "no arguments"
        )
        lines.append(f"- {tool.name}({params}) -- {tool.description}")
    return "\n".join(lines)


def render_command_block(
    commands: tuple[str, ...], notes: dict[str, str] | None = None
) -> str:
    notes = notes or {}
    if not notes:
        return ", ".join(commands)
    # Tokens with a note get a line each; the rest (the report_clock_*
    # family and the like) stay one comma-joined line so the block does
    # not grow past what a 4B model will read.
    noted = [f"- {token} -- {notes[token]}" for token in commands if token in notes]
    bare = [token for token in commands if token not in notes]
    lines = noted
    if bare:
        lines.append("- also, no target: " + ", ".join(bare))
    return "\n".join(lines)


def render_header_block(header: dict[str, Any]) -> str:
    lines: list[str] = []
    contacts = header.get("contacts") or []
    if contacts:
        lines.append("Offered contacts:")
        for contact in contacts:
            mention = " (just mentioned)" if contact.get("last_mentioned") else ""
            lines.append(
                f"  {contact['ref']}: {contact['class']}, {contact['certainty']}, "
                f"{contact['clock']}, {contact['range_text']}, {contact['landmark']}{mention}"
            )
    places = header.get("places") or []
    if places:
        lines.append("Offered places:")
        for place in places:
            lines.append(f"  {place['ref']}: {place['name']}")
    marks = header.get("marks") or []
    if marks:
        lines.append("Marks you know of:")
        for mark in marks:
            lines.append(f"  {mark['ref']}: {mark['label']}")
    if not lines:
        lines.append("(nothing offered yet this turn)")
    return "\n".join(lines)


def tool_to_json_schema(tool: ToolSpec) -> dict[str, Any]:
    """Ollama's native `/api/chat` `tools` entry shape (OpenAI-style
    function calling) for one `ToolSpec`."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in tool.params:
        properties[param.name] = {
            "type": _KIND_TO_JSON_TYPE[param.kind],
            "description": param.kind,
        }
        if param.required:
            required.append(param.name)
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


#: The FINAL grammar and the no-invention rule -- identical text in both
#: forms, since D5/D10 require the same closed final-reply vocabulary
#: however the tool call itself was expressed (plan D1: "Either way the
#: wire to body is the same structured JSON").
_FINAL_GRAMMAR_BLOCK = """When you have what you need, finish with ONE line, exactly one of:
FINAL command <token> {"target": "<ref>"}   -- do something, or point out one contact (use where_is_it for "where is X"); omit the slots object for commands without a target
FINAL answer <form> <json list of refs>      -- form is one of: our_position (no refs), memory (mark refs), contacts (contact refs, at most 3), nothing_seen (no refs)
FINAL ask <json list of refs>                -- two or more contacts fit and nothing the pilot said tells them apart
FINAL unable <reason>                        -- reason is one of: NO_PLACE (pilot named a place no tool knows), CANNOT_ANSWER (no tool covers the question, e.g. ammunition or fuel), FIXED_COMMAND_ONLY (weapons, sight or flying: the pilot must use the fixed phrase)

Rules:
- The header below lists only what has already been offered this turn. It is EMPTY at the start of most turns. An empty header never means "nothing out there": if the pilot asks about something the header does not contain, CALL a tool first. That is how you find out.
- Every ref you name must be one offered to you this turn, in the header or in a tool's observation. Never invent a ref, a position, a bearing or a range.
- Do not reply FINAL unable just because the header is empty. Reply FINAL unable only for the three reasons above.
- Never repeat a call that is already listed under "So far this turn": its observation is there, use it. If a place is offered, the next step is list_contacts with a filter naming it, or a FINAL.

Examples (header empty each time):
Pilot said: "Petrovich, where's the BMP?"          -> CALL find_contact {"text": "bmp"}
  ... observation says one match, CONTACT_3        -> FINAL command where_is_it {"target": "CONTACT_3"}
Pilot said: "Petrovich, anything near Soganli?"    -> CALL find_place {"text": "soganli"}
  ... observation offers PLACE_1                   -> CALL list_contacts {"filter": "near PLACE_1"}
  ... observation lists CONTACT_8                  -> FINAL answer contacts ["CONTACT_8"]
Pilot said: "Petrovich, arm the weapons."          -> FINAL unable FIXED_COMMAND_ONLY"""

_SYSTEM_PROMPT_HEAD = """You are Petrovich, the weapons officer in a Mi-24P attack helicopter, replying to your pilot who just spoke to you directly. You know only what the tools tell you this turn -- never invent a contact, a place, a position, a bearing, a range or a quantity that no tool gave you. Tools are how you look things up; use them before answering.

Reply with EXACTLY ONE line, nothing else, no explanation, no markdown, no thinking out loud."""


def build_system_prompt(
    tools: tuple[ToolSpec, ...],
    commands: tuple[str, ...],
    form: str,
    command_notes: dict[str, str] | None = None,
) -> str:
    """Byte-stable across every round and every case run in `form` --
    see the module docstring's note on why nothing case-specific is
    allowed in here."""
    command_block = f"\n\nCommands you may issue as a FINAL command, and no others:\n{render_command_block(commands, command_notes)}"
    if form == "grammar":
        call_block = (
            "\n\nTools you may call -- to use one, reply with ONE line of the form:\n"
            "CALL <tool_name> <json object of arguments>\n\n"
            f"{render_tool_block(tools)}"
        )
        return f"{_SYSTEM_PROMPT_HEAD}{call_block}{command_block}\n\n{_FINAL_GRAMMAR_BLOCK}"
    # native: tools are offered through the API's own `tools` field, not
    # restated in prose -- but the model still has to be told that a
    # tool call (not a FINAL line) is the way to look things up. The
    # examples' "CALL ..." lines then read as "call that tool".
    call_block = (
        "\n\nYou have tools (see the tools you were given). To look something up, call the tool"
        " -- do not write a CALL line in text. In the examples below, 'CALL x {...}' means"
        " 'call tool x with those arguments'."
    )
    return f"{_SYSTEM_PROMPT_HEAD}{call_block}{command_block}\n\n{_FINAL_GRAMMAR_BLOCK}"


def build_case_suffix(case: Case) -> str:
    """Also byte-stable across a case's own rounds -- only
    `build_steps_block`'s growing tail changes between rounds."""
    return f'\n\nPilot said: "{case.utterance}"\n\n{render_header_block(case.header)}'


@dataclass
class Step:
    tool: str
    args: dict[str, Any]
    observation: dict[str, Any]
    matched_canned: bool


def build_steps_block(steps: list[Step]) -> str:
    if not steps:
        return ""
    lines = ["", "So far this turn:"]
    for index, step in enumerate(steps, start=1):
        lines.append(f"{index}. CALL {step.tool} {json.dumps(step.args)}")
        lines.append(f"   OBSERVATION {json.dumps(step.observation)}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Grammar / native reply parsing
# --------------------------------------------------------------------------

_CALL_RE = re.compile(r"^\s*CALL\s+(\w+)\s+(\{.*\})\s*$", re.IGNORECASE | re.DOTALL)
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
    """The parsed shape of one model reply line, from either form.
    `kind` is one of `"call"`, `"final_command"`, `"final_answer"`,
    `"final_ask"`, `"final_unable"`, `"malformed"`."""

    kind: str
    tool: str | None = None
    args: dict[str, Any] | None = None
    token: str | None = None
    slots: dict[str, Any] | None = None
    form: str | None = None
    refs: list[str] | None = None
    reason: str | None = None


def _parse_final_text(text: str) -> ParsedLine:
    """The four `FINAL ...` shapes only -- used directly for a native
    reply's `content` (which must never itself contain a `CALL` line;
    the model has the native `tools` field for that) and as the second
    half of `parse_grammar_line`."""
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


def parse_grammar_line(raw: str) -> ParsedLine:
    """The grammar form's full vocabulary: `CALL ...` or one of the four
    `FINAL ...` shapes. Anything else is `"malformed"` -- never guessed
    at, matching `decider.py`'s own "unparseable degrades, never invents"
    posture."""
    stripped = raw.strip()
    match = _CALL_RE.match(stripped)
    if match:
        tool_name, args_json = match.groups()
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError:
            return ParsedLine(kind="malformed")
        if not isinstance(args, dict):
            return ParsedLine(kind="malformed")
        return ParsedLine(kind="call", tool=tool_name, args=args)
    return _parse_final_text(raw)


def _interpret_native_result(result: ChatResult) -> tuple[ParsedLine, bool, str]:
    """A native reply either carries one or more structured
    `tool_calls`, or a `FINAL ...` line in `content` -- never both, by
    the API's own contract. Only the *first* tool call is acted on;
    more than one is recorded as not well-formed (D3's "one round, one
    tool" rule has no native equivalent to appeal to)."""
    if result.tool_calls:
        call = result.tool_calls[0]
        well_formed = len(result.tool_calls) == 1
        raw = json.dumps(
            {
                "tool_calls": [
                    {"name": tc.name, "arguments": tc.arguments}
                    for tc in result.tool_calls
                ]
            }
        )
        return (
            ParsedLine(kind="call", tool=call.name, args=dict(call.arguments)),
            well_formed,
            raw,
        )
    parsed = _parse_final_text(result.content)
    return parsed, parsed.kind != "malformed", result.content


def find_observation(
    case: Case, tool: str, _args: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """This case's own canned observation for `tool`, matched by tool
    name alone. **`args` is deliberately not matched against** -- every
    case in `stage0_cases.json` calls a given tool at most once, so a
    small local model's own phrasing of its arguments (`"shilka"` vs
    `"the shilka"`) must not fail a case over a lookup miss that has
    nothing to do with the thing Stage 0 measures. `args_hint` on the
    fixture entry is for a human reading the results, not matched here."""
    for entry in case.observations:
        if entry.tool == tool:
            return entry.observation, True
    return {"error": "no canned observation for this call"}, False


def _final_from_parsed(parsed: ParsedLine) -> dict[str, Any] | None:
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


def _refs_match(final: dict[str, Any], expected: dict[str, Any]) -> bool:
    if "refs" not in expected:
        return True
    return sorted(final.get("refs") or []) == sorted(expected.get("refs") or [])


def _final_matches_expected(final: dict[str, Any], expected: dict[str, Any]) -> bool:
    if final.get("kind") != expected.get("kind"):
        return False
    kind = final["kind"]
    if kind == "command":
        if final.get("token") != expected.get("token"):
            return False
        return "target" not in expected or final.get("target") == expected.get("target")
    if kind == "answer":
        return final.get("form") == expected.get("form") and _refs_match(
            final, expected
        )
    if kind == "ask":
        return _refs_match(final, expected)
    if kind == "unable":
        return final.get("reason") == expected.get("reason")
    return False


# --------------------------------------------------------------------------
# The round loop
# --------------------------------------------------------------------------


@dataclass
class RoundRecord:
    round_index: int
    latency_s: float
    prompt_tokens: int
    eval_tokens: int
    kind: str  # "tool_call" | "final" | "malformed" | "round_cap_exceeded" | "transport_error"
    well_formed: bool
    step_matched_expected: bool | None
    raw: str


@dataclass
class CaseRunResult:
    case_id: str
    form: str
    num_ctx: int
    rounds: list[RoundRecord]
    final: dict[str, Any] | None
    final_correct: bool
    exceeded_rounds: bool
    error: str | None


def run_case_once(
    client: OllamaClient,
    model: str,
    num_ctx: int,
    num_predict: int,
    max_rounds: int,
    form: Literal["native", "grammar"],
    system_prompt: str,
    native_tool_schemas: list[dict[str, Any]],
    case: Case,
) -> CaseRunResult:
    """Drives one case through up to `max_rounds` tool-call rounds plus
    one final round, playing "body" for every tool call via
    `find_observation` -- the multi-round loop `drain_brain` will run
    for real once BR-2 Stage 2 ships (plan D1/D9)."""
    steps: list[Step] = []
    rounds: list[RoundRecord] = []
    suffix = build_case_suffix(case)
    expected_steps = case.expected.get("steps", [])

    for round_index in range(max_rounds + 1):
        steps_block = build_steps_block(steps)
        expected_tool = (
            expected_steps[len(steps)]["tool"]
            if len(steps) < len(expected_steps)
            else None
        )
        t0 = time.monotonic()
        try:
            if form == "native":
                messages: list[dict[str, Any]] = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": suffix + steps_block},
                ]
                chat_result = client.chat(
                    model=model,
                    messages=messages,
                    tools=native_tool_schemas,
                    num_ctx=num_ctx,
                    num_predict=num_predict,
                )
                latency = time.monotonic() - t0
                parsed, well_formed, raw_text = _interpret_native_result(chat_result)
                prompt_tokens = chat_result.usage.prompt_tokens
                eval_tokens = chat_result.usage.eval_tokens
            else:
                prompt = system_prompt + suffix + steps_block
                text, usage = client.generate_with_usage(
                    model=model, prompt=prompt, num_ctx=num_ctx, num_predict=num_predict
                )
                latency = time.monotonic() - t0
                parsed = parse_grammar_line(text)
                well_formed = parsed.kind != "malformed"
                raw_text = text
                prompt_tokens = usage.prompt_tokens
                eval_tokens = usage.eval_tokens
        except OllamaRequestError as exc:
            rounds.append(
                RoundRecord(
                    round_index=round_index,
                    latency_s=time.monotonic() - t0,
                    prompt_tokens=0,
                    eval_tokens=0,
                    kind="transport_error",
                    well_formed=False,
                    step_matched_expected=False,
                    raw=str(exc),
                )
            )
            return CaseRunResult(
                case_id=case.id,
                form=form,
                num_ctx=num_ctx,
                rounds=rounds,
                final=None,
                final_correct=False,
                exceeded_rounds=False,
                error=str(exc),
            )

        if parsed.kind == "call" and round_index >= max_rounds:
            # The round budget is spent and the model is still trying to
            # call a tool -- D3's degrade-on-exceeded-rounds case. The
            # call is recorded but never executed.
            rounds.append(
                RoundRecord(
                    round_index=round_index,
                    latency_s=latency,
                    prompt_tokens=prompt_tokens,
                    eval_tokens=eval_tokens,
                    kind="round_cap_exceeded",
                    well_formed=well_formed,
                    step_matched_expected=False,
                    raw=raw_text,
                )
            )
            return CaseRunResult(
                case_id=case.id,
                form=form,
                num_ctx=num_ctx,
                rounds=rounds,
                final=None,
                final_correct=False,
                exceeded_rounds=True,
                error=None,
            )

        if parsed.kind == "call":
            assert parsed.tool is not None
            assert parsed.args is not None
            observation, matched_canned = find_observation(
                case, parsed.tool, parsed.args
            )
            step_matched = expected_tool is not None and parsed.tool == expected_tool
            rounds.append(
                RoundRecord(
                    round_index=round_index,
                    latency_s=latency,
                    prompt_tokens=prompt_tokens,
                    eval_tokens=eval_tokens,
                    kind="tool_call",
                    well_formed=well_formed,
                    step_matched_expected=step_matched,
                    raw=raw_text,
                )
            )
            steps.append(
                Step(
                    tool=parsed.tool,
                    args=parsed.args,
                    observation=observation,
                    matched_canned=matched_canned,
                )
            )
            continue

        # A final reply (well-formed or not) always ends the turn.
        final_dict = _final_from_parsed(parsed) if well_formed else None
        final_correct = final_dict is not None and _final_matches_expected(
            final_dict, case.expected.get("final", {})
        )
        rounds.append(
            RoundRecord(
                round_index=round_index,
                latency_s=latency,
                prompt_tokens=prompt_tokens,
                eval_tokens=eval_tokens,
                kind="final" if well_formed else "malformed",
                well_formed=well_formed,
                step_matched_expected=None,
                raw=raw_text,
            )
        )
        return CaseRunResult(
            case_id=case.id,
            form=form,
            num_ctx=num_ctx,
            rounds=rounds,
            final=final_dict,
            final_correct=final_correct,
            exceeded_rounds=False,
            error=None,
        )

    # Unreachable in practice: the `round_index >= max_rounds` branch
    # above always returns on the last iteration. Kept for mypy's
    # exhaustiveness and as a safety net against a future off-by-one.
    return CaseRunResult(
        case_id=case.id,
        form=form,
        num_ctx=num_ctx,
        rounds=rounds,
        final=None,
        final_correct=False,
        exceeded_rounds=True,
        error=None,
    )


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def render_summary_table(
    results: list[CaseRunResult], forms: Sequence[str], num_ctxs: list[int]
) -> str:
    header = (
        "| form | num_ctx | correct/total | mean round latency (s) | max round latency (s) "
        "| max prompt tokens | cases needing >2 rounds |"
    )
    lines = [header, "|---|---|---|---|---|---|---|"]
    for form in forms:
        for num_ctx in num_ctxs:
            subset = [r for r in results if r.form == form and r.num_ctx == num_ctx]
            if not subset:
                continue
            correct = sum(1 for r in subset if r.final_correct)
            total = len(subset)
            latencies = [
                round_record.latency_s for r in subset for round_record in r.rounds
            ]
            mean_latency = statistics.mean(latencies) if latencies else 0.0
            max_latency = max(latencies) if latencies else 0.0
            max_prompt_tokens = max(
                (
                    round_record.prompt_tokens
                    for r in subset
                    for round_record in r.rounds
                ),
                default=0,
            )
            over_two_rounds = sum(
                1
                for r in subset
                if sum(
                    1 for round_record in r.rounds if round_record.kind == "tool_call"
                )
                > 2
            )
            lines.append(
                f"| {form} | {num_ctx} | {correct}/{total} | {mean_latency:.2f} | "
                f"{max_latency:.2f} | {max_prompt_tokens} | {over_two_rounds} |"
            )
    return "\n".join(lines)


def _result_to_dict(result: CaseRunResult) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "form": result.form,
        "num_ctx": result.num_ctx,
        "rounds": [asdict(round_record) for round_record in result.rounds],
        "final": result.final,
        "final_correct": result.final_correct,
        "exceeded_rounds": result.exceeded_rounds,
        "error": result.error,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3:4b-instruct-2507-q4_K_M")
    parser.add_argument("--num-ctx", type=int, nargs="+", default=[2048, 4096])
    parser.add_argument("--form", choices=["native", "grammar", "both"], default="both")
    parser.add_argument(
        "--cases", type=Path, default=Path(__file__).parent / "stage0_cases.json"
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--num-predict", type=int, default=DEFAULT_NUM_PREDICT)
    parser.add_argument("--max-rounds", type=int, default=MAX_TOOL_ROUNDS)
    args = parser.parse_args(argv)

    case_file = load_case_file(args.cases)
    client = OllamaClient(base_url=args.base_url, timeout_s=args.timeout_s)
    forms: list[Literal["native", "grammar"]] = (
        ["grammar", "native"] if args.form == "both" else [args.form]
    )
    num_ctxs: list[int] = list(args.num_ctx)

    all_results: list[CaseRunResult] = []
    for form in forms:
        system_prompt = build_system_prompt(
            case_file.tools, case_file.commands, form, case_file.command_notes
        )
        native_schemas = (
            [tool_to_json_schema(tool) for tool in case_file.tools]
            if form == "native"
            else []
        )
        for num_ctx in num_ctxs:
            for case in case_file.cases:
                result = run_case_once(
                    client=client,
                    model=args.model,
                    num_ctx=num_ctx,
                    num_predict=args.num_predict,
                    max_rounds=args.max_rounds,
                    form=form,
                    system_prompt=system_prompt,
                    native_tool_schemas=native_schemas,
                    case=case,
                )
                all_results.append(result)
                verdict = "OK" if result.final_correct else "MISS"
                print(
                    f"[{form} num_ctx={num_ctx}] {case.id}: {verdict} "
                    f"rounds={len(result.rounds)} final={result.final} error={result.error}"
                )

    print()
    print(render_summary_table(all_results, forms, num_ctxs))

    if args.out is not None:
        args.out.write_text(
            json.dumps([_result_to_dict(r) for r in all_results], indent=2)
        )
        print(f"\nwrote {len(all_results)} case results to {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
