"""Generate `body-layer/config/effectors-raw.toml` from ED's own Mi-24P
cockpit scripts -- `plans/effector-sequences/plan.md` Stage 0.

Reads `devices.lua`, `command_defs.lua` and `clickabledata.lua` from the
installed Mi-24P module's `Cockpit/Scripts` directory, resolves every
`elements[...]` entry's symbolic device/command references to integers,
and emits one TOML entry per clickable element (device, cmd, arg, label,
shape, crew). **Stdlib only. Parses the Lua as text; never executes it.**

**The exact forms below are confirmed against a live install, build
2.9.30.28738, 2026-10-23** -- see `aircraft-layer/research/
2026-10-23-mi24p-clickabledata-forms.md` for the full recon this parser
is built against. `clickable_defs.lua`'s 22 helper signatures are baked
into `_HELPER_SIGNATURES` below rather than parsed at runtime: their
bodies are mesh/sound triggers irrelevant to id resolution, and only the
*parameter order* (which this generator needs) is fixed, known Lua
source this tool's author has already read once.

**DCS-BIOS is never read by this tool** -- it is GPL-3.0 and this
project's registry must stay DCS-native (`plans/effector-sequences/
plan.md`, "Registry scope and source"). DCS-BIOS is read by hand, by a
human, when a curated entry's label is ambiguous -- never parsed here.

**Only runs on a machine with the Mi-24P module installed** (a Windows
box, same posture as every other "read the installed DCS tree" tool in
this project). Not runnable from this repo's own dev checkout or CI.

Usage:

    # report only -- parses, prints a summary, writes nothing
    python tools/generate_effector_registry.py --scripts-dir <path>

    # write config/effectors-raw.toml
    python tools/generate_effector_registry.py --scripts-dir <path> --write

    # on the DCS machine itself, with DCS_INSTALL_PATH set, no --scripts-dir needed
    python tools/generate_effector_registry.py --write

**Fails closed, at two levels.** A single `elements[...]` entry this
parser cannot make sense of (unrecognised helper, unresolved device/
command symbol, a reference that is neither a definition nor a
`.field = ...` patch) is "unhandled" -- reported, and the process exits 2
without writing anything, unless `--allow-unhandled` is passed (in which
case the registry is written with unhandled elements simply omitted).
A `command_defs.lua` structure this parser does not recognise at all --
most importantly, a loop over an empty command table that is not
*exactly* the one `device_commands` loop shape this file is known to use
-- is a different, harder failure: there is no partial registry to fall
back to, so it is always fatal (`CommandDefsParseError`), `--allow-
unhandled` or not.

The completeness count this prints (`elements[` heads == emitted +
unhandled + post-assignments) is the thing to check after every DCS
patch -- a silent drop would otherwise look identical to a clean run.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT_PATH = _BODY_LAYER_ROOT / "config" / "effectors-raw.toml"
_SCRIPTS_SUBPATH = Path("Mods") / "aircraft" / "Mi-24P" / "Cockpit" / "Scripts"

#: `clickable_defs.lua`'s 22 helper signatures, confirmed live 2026-10-23
#: (`aircraft-layer/research/2026-10-23-mi24p-clickabledata-forms.md`
#: Q3). Every one of them puts `device_` at positional index 1 and the
#: command(s) immediately after at index 2 (two indices, 2 and 3, for the
#: two helpers that take `command1_, command2_`); `arg_` (the cockpit
#: draw argument) always follows the command(s) directly, so its index
#: is `2 + n_commands` and is never stored separately below. The value
#: is `(n_commands, crew_idx)`; `crew_idx` is `None` for the two helpers
#: with no crew parameter at all (`default_square_button`, `stick_button`).
_HELPER_SIGNATURES: dict[str, tuple[int, int | None]] = {
    "default_button": (1, 5),
    "default_spring_button": (1, 7),
    "default_square_button": (1, None),
    "default_tumb_button": (1, 5),
    "default_position_tumb": (1, 7),
    "default_1_position_tumb": (1, 7),
    "default_2_position_tumb": (1, 5),
    "default_2_position_small_tumb": (1, 5),
    "default_2_position_flares_tumb": (1, 5),
    "default_3_position_tumb": (1, 9),
    "triple_switch": (1, 4),
    "multiposition_switch": (1, 10),
    "default_button_tumb": (2, 6),
    "springloaded_2_pos_tumb": (1, 5),
    "springloaded_3_pos_tumb": (2, 9),
    "default_animated_lever": (1, 6),
    "default_axis": (1, 11),
    "default_axis_limited": (1, 11),
    "default_CB_button": (1, 4),
    "default_blue_cover": (1, 5),
    "radio_wheel_1": (1, 7),
    "stick_button": (1, None),
}

_INT_RE = re.compile(r"^-?\d+$")

# -- devices.lua: `devices["NAME"] = counter()` (bracket-string form,
# confirmed 2026-10-23 -- the dotted `devices.NAME` form only ever
# appears as a *reference* inside clickabledata.lua, never as the
# devices.lua declaration itself).
_DEVICE_ASSIGN_RE = re.compile(r'devices\[\s*"(\w+)"\s*\]\s*=\s*([^\n;]+)')

# -- command_defs.lua: a column-0 `count = start_command` precedes every
# per-device table (49 of them, confirmed 2026-10-23 Q2) and resets that
# table's counter to 3001 for its first `= counter()` entry.
_RESET_MARKER_RE = re.compile(r"count\s*=\s*start_command\b")
_TABLE_HEADER_RE = re.compile(r"[\s;]*(\w+)\s*=\s*")
_BRACE_RE = re.compile(r"\s*\{")
_TABLE_ENTRY_RE = re.compile(r"(\w+)\s*=\s*(counter\(\)|-?\d+)\s*[;,]?")
_LOOP_RE = re.compile(
    r"[\s;]*for\s+(\w+)\s*=\s*(\d+)\s*,\s*(\d+)\s*do\s*"
    r'(\w+)\[\s*"([^"]*)"\s*\.\.\s*(\w+)\s*\]\s*=\s*counter\(\)\s*[;\s]*end'
)

# -- clickabledata.lua.
_ELEMENTS_REF_RE = re.compile(r"""elements\s*\[\s*(["'])(?P<name>.*?)\1\s*\]""")
_DEF_EQUALS_RE = re.compile(r"\s*=\s*")
_POST_ASSIGN_RE = re.compile(r"\s*\.(\w+)\s*=\s*")
_CALL_HEAD_RE = re.compile(r"(\w+)\s*\(")
_DEVICE_REF_RE = re.compile(r"^devices\.(\w+)$")
_DOTTED_REF_RE = re.compile(r"^(\w+)\.(\w+)$")
_ANY_DOTTED_REF_RE = re.compile(r"(\w+)\.(\w+)")
_LABEL_UNDERSCORE_RE = re.compile(r"""_\(\s*(["'])(.*?)\1\s*\)""", re.DOTALL)
_LABEL_PLAIN_RE = re.compile(r"""^(["'])(.*?)\1$""", re.DOTALL)
_RAW_HINT_RE = re.compile(r"""\bhint\s*=\s*_\(\s*(["'])(.*?)\1\s*\)""", re.DOTALL)
_RAW_DEVICE_RE = re.compile(r"\bdevice\s*=\s*devices\.(\w+)")
_RAW_ACTION_RE = re.compile(r"\baction\s*=\s*(\{[^{}]*\}|[^,\n]+)")
_RAW_ARG_RE = re.compile(r"\barg\s*=\s*(\{[^{}]*\}|-?\d+)")
_RAW_CREW_RE = re.compile(r"\bcrew_member_access\s*=\s*(\{[^{}]*\}|-?\d+)")
_BARE_TOML_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class CommandDefsParseError(Exception):
    """A `command_defs.lua` structure this generator does not recognise
    at all -- see the module docstring's "Fails closed, at two levels"."""


@dataclass(frozen=True)
class RawElement:
    name: str
    device_id: int
    device_symbol: str
    cmd_id: int
    cmd_symbol: str
    arg: int
    label: str
    shape: str
    crew: int
    crew_explicit: bool
    cmd2_id: int | None = None
    cmd2_symbol: str | None = None


@dataclass(frozen=True)
class UnhandledElement:
    name: str
    reason: str


def _strip_lua_comments(text: str) -> str:
    """Remove `-- line comments` and `--[[ block comments ]]`, respecting
    string literals (a `--` inside a quoted label is not a comment
    start). A `--[[ ... ]]--` banner's trailing `--` is picked up as an
    ordinary fresh line comment on the next pass, no special-casing
    needed. Keeps every newline so line counts are unaffected."""
    out: list[str] = []
    i = 0
    n = len(text)
    in_str: str | None = None
    while i < n:
        c = text[i]
        if in_str is not None:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in ('"', "'"):
            in_str = c
            out.append(c)
            i += 1
            continue
        if text[i : i + 4] == "--[[":
            end = text.find("]]", i + 4)
            i = n if end == -1 else end + 2
            continue
        if text[i : i + 2] == "--":
            nl = text.find("\n", i)
            if nl == -1:
                i = n
            else:
                out.append("\n")
                i = nl + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _extract_balanced(text: str, open_pos: int, open_ch: str, close_ch: str) -> str:
    """`text[open_pos] == open_ch`. Returns the text strictly between the
    opening bracket and its matching close, tracking string literals so a
    bracket character inside a quoted label never miscounts depth."""
    assert text[open_pos] == open_ch
    depth = 0
    i = open_pos
    in_str: str | None = None
    start_inner = open_pos + 1
    n = len(text)
    while i < n:
        c = text[i]
        if in_str is not None:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in ('"', "'"):
            in_str = c
            i += 1
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start_inner:i]
        i += 1
    raise ValueError(f"unbalanced {open_ch!r}/{close_ch!r} starting at {open_pos}")


def _split_top_level(text: str) -> list[str]:
    """Split `text` on top-level commas -- i.e. not inside `()`/`{}`/`[]`
    or a string literal. Used to break a helper call's argument list
    apart without being fooled by a nested call or a label containing a
    comma or a parenthesis (207 labels do, per the 2026-10-23 recon)."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_str: str | None = None
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if in_str is not None:
            current.append(c)
            if c == "\\" and i + 1 < n:
                current.append(text[i + 1])
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in ('"', "'"):
            in_str = c
            current.append(c)
            i += 1
            continue
        if c in "([{":
            depth += 1
            current.append(c)
            i += 1
            continue
        if c in ")]}":
            depth -= 1
            current.append(c)
            i += 1
            continue
        if c == "," and depth == 0:
            parts.append("".join(current))
            current = []
            i += 1
            continue
        current.append(c)
        i += 1
    if current or parts:
        parts.append("".join(current))
    return [p.strip() for p in parts if p.strip() != ""]


# --- devices.lua --------------------------------------------------------


def parse_devices(stripped_text: str) -> dict[str, int]:
    """`devices["NAME"] = counter()` is the only form seen live
    (2026-10-23); a literal int RHS is accepted too, defensively, and
    simply taken at face value without disturbing the running sequence."""
    devices: dict[str, int] = {}
    counter_next = 1
    for m in _DEVICE_ASSIGN_RE.finditer(stripped_text):
        name, rhs = m.group(1), m.group(2).strip()
        if _INT_RE.match(rhs):
            value = int(rhs)
            devices[name] = value
            counter_next = value + 1
        else:
            devices[name] = counter_next
            counter_next += 1
    return devices


def _parse_command_loop(
    stripped_text: str, pos: int, table_name: str
) -> dict[str, int]:
    m = _LOOP_RE.match(stripped_text, pos)
    if m is None:
        raise CommandDefsParseError(
            f"table `{table_name}` is assigned an empty `{{}}` but is not followed by "
            f'the expected `for VAR = start,end do {table_name}["prefix"..VAR] = '
            "counter() end` loop (fail-closed: any other loop over an empty command "
            "table is unhandled, not guessed at)"
        )
    loop_var, start_s, end_s, target_table, prefix, concat_var = m.groups()
    if target_table != table_name or concat_var != loop_var:
        raise CommandDefsParseError(
            f"table `{table_name}`'s loop assigns into `{target_table}[...{concat_var}]`, "
            f"expected `{table_name}[...{loop_var}]`"
        )
    start, end = int(start_s), int(end_s)
    result: dict[str, int] = {}
    next_id = 3001
    for i in range(start, end + 1):
        result[f"{prefix}{i}"] = next_id
        next_id += 1
    return result


def parse_command_defs(stripped_text: str) -> dict[str, dict[str, int]]:
    """Every `*_commands` table (49 of them, 2026-10-23 recon) is preceded
    by a `count = start_command` reset and is either a plain table
    constructor (`name = { field = counter(); ... }`) or, for
    `device_commands` alone, an empty `{}` followed by a `for` loop --
    see `_parse_command_loop`. `Keys = { PlaneGear = 68, ... }` (the
    global iCommand space, lines 11-623 of the real file) has no
    preceding reset marker and is never touched by this scan, which is
    exactly right: nothing in `clickabledata.lua` references `Keys`."""
    tables: dict[str, dict[str, int]] = {}
    for marker in _RESET_MARKER_RE.finditer(stripped_text):
        header_match = _TABLE_HEADER_RE.match(stripped_text, marker.end())
        if header_match is None:
            raise CommandDefsParseError(
                f"reset marker at offset {marker.start()} is not followed by "
                "`<table> = ...`"
            )
        table_name = header_match.group(1)
        brace_match = _BRACE_RE.match(stripped_text, header_match.end())
        if brace_match is None:
            raise CommandDefsParseError(
                f"table `{table_name}` after a reset marker is not assigned a "
                "`{...}` literal"
            )
        brace_pos = brace_match.end() - 1
        body = _extract_balanced(stripped_text, brace_pos, "{", "}")
        close_pos = brace_pos + len(body) + 2
        tables.setdefault(table_name, {})
        if body.strip() == "":
            tables[table_name].update(
                _parse_command_loop(stripped_text, close_pos, table_name)
            )
            continue
        next_id = 3001
        for entry in _TABLE_ENTRY_RE.finditer(body):
            name, rhs = entry.group(1), entry.group(2)
            if rhs == "counter()":
                tables[table_name][name] = next_id
                next_id += 1
            else:
                value = int(rhs)
                tables[table_name][name] = value
                next_id = value + 1
    return tables


# --- clickabledata.lua ---------------------------------------------------


def _extract_label(arg_text: str) -> str:
    m = _LABEL_UNDERSCORE_RE.search(arg_text)
    if m:
        return m.group(2)
    m = _LABEL_PLAIN_RE.match(arg_text)
    if m:
        return m.group(2)
    return ""


def _resolve_device(symbol: str, devices: dict[str, int]) -> tuple[int, str] | str:
    """Returns `(device_id, symbol)` on success, or an error-reason string."""
    if symbol not in devices:
        return f"unknown device symbol: devices.{symbol}"
    return devices[symbol], symbol


def _resolve_cmd(
    table: str, name: str, command_defs: dict[str, dict[str, int]]
) -> tuple[int, str] | str:
    if table not in command_defs:
        return f"unknown command table: {table}"
    if name not in command_defs[table]:
        return f"unknown command symbol: {table}.{name}"
    return command_defs[table][name], f"{table}.{name}"


def _parse_helper_call(
    name: str,
    helper: str,
    args: list[str],
    devices: dict[str, int],
    command_defs: dict[str, dict[str, int]],
) -> RawElement | UnhandledElement:
    sig = _HELPER_SIGNATURES.get(helper)
    if sig is None:
        return UnhandledElement(name, f"unrecognised helper call: {helper}")
    n_commands, crew_idx = sig
    arg_idx = 2 + n_commands
    if len(args) < arg_idx + 1:
        return UnhandledElement(
            name,
            f"{helper}(...) has {len(args)} argument(s), expected at least {arg_idx + 1}",
        )
    label = _extract_label(args[0])

    device_match = _DEVICE_REF_RE.match(args[1])
    if device_match is None:
        return UnhandledElement(
            name, f"expected devices.<symbol> as argument 2 to {helper}, got: {args[1]}"
        )
    device_resolved = _resolve_device(device_match.group(1), devices)
    if isinstance(device_resolved, str):
        return UnhandledElement(name, device_resolved)
    device_id, device_symbol = device_resolved

    cmd_ids: list[int] = []
    cmd_symbols: list[str] = []
    for i in range(n_commands):
        cmd_arg = args[2 + i]
        cmd_match = _DOTTED_REF_RE.match(cmd_arg)
        if cmd_match is None:
            return UnhandledElement(
                name,
                f"expected <table>.<symbol> as argument {3 + i} to {helper}, got: {cmd_arg}",
            )
        cmd_resolved = _resolve_cmd(
            cmd_match.group(1), cmd_match.group(2), command_defs
        )
        if isinstance(cmd_resolved, str):
            return UnhandledElement(name, cmd_resolved)
        resolved_id, resolved_symbol = cmd_resolved
        cmd_ids.append(resolved_id)
        cmd_symbols.append(resolved_symbol)

    arg_text = args[arg_idx].strip()
    if not _INT_RE.match(arg_text):
        return UnhandledElement(
            name,
            f"expected an integer draw argument as argument {arg_idx + 1} to {helper}, "
            f"got: {arg_text}",
        )
    arg = int(arg_text)

    if crew_idx is None or len(args) <= crew_idx:
        crew, crew_explicit = 0, False
    else:
        crew_text = args[crew_idx].strip()
        if crew_text in ("nil", ""):
            crew, crew_explicit = 0, False
        elif _INT_RE.match(crew_text):
            crew, crew_explicit = int(crew_text), True
        else:
            return UnhandledElement(
                name, f"could not parse crew_member_access expression: {crew_text}"
            )

    return RawElement(
        name=name,
        device_id=device_id,
        device_symbol=device_symbol,
        cmd_id=cmd_ids[0],
        cmd_symbol=cmd_symbols[0],
        arg=arg,
        label=label,
        shape=helper,
        crew=crew,
        crew_explicit=crew_explicit,
        cmd2_id=cmd_ids[1] if len(cmd_ids) > 1 else None,
        cmd2_symbol=cmd_symbols[1] if len(cmd_symbols) > 1 else None,
    )


def _distinct_dotted_refs(text: str) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    for m in _ANY_DOTTED_REF_RE.finditer(text):
        pair = (m.group(1), m.group(2))
        if pair not in seen:
            seen.append(pair)
    return seen


def _parse_raw_literal(
    name: str,
    body: str,
    devices: dict[str, int],
    command_defs: dict[str, dict[str, int]],
) -> RawElement | UnhandledElement:
    """The 13-element gap: a raw Lua table literal instead of a helper
    call, confirmed 2026-10-23 to use `device = devices.<symbol>` (not
    `cockpit_device_id`), `action = ...`/`action = {...}` for the
    command reference(s), `arg = ...`/`arg = {...}` for the draw
    argument(s), and `hint = _("...")` for the label -- the plan's
    original guessed field names (`cockpit_device_id`, `name`) were
    wrong and are not accepted here."""
    device_match = _RAW_DEVICE_RE.search(body)
    if device_match is None:
        return UnhandledElement(
            name, "raw table literal has no `device = devices.<symbol>` field"
        )
    device_resolved = _resolve_device(device_match.group(1), devices)
    if isinstance(device_resolved, str):
        return UnhandledElement(name, device_resolved)
    device_id, device_symbol = device_resolved

    action_match = _RAW_ACTION_RE.search(body)
    if action_match is None:
        return UnhandledElement(name, "raw table literal has no `action = ...` field")
    refs = _distinct_dotted_refs(action_match.group(1))
    if not refs:
        return UnhandledElement(
            name,
            f"`action` field has no <command_table>.<symbol> reference: {action_match.group(1)}",
        )
    cmd_ids: list[int] = []
    cmd_symbols: list[str] = []
    for table, cmd_name in refs[:2]:
        resolved = _resolve_cmd(table, cmd_name, command_defs)
        if isinstance(resolved, str):
            return UnhandledElement(name, resolved)
        resolved_id, resolved_symbol = resolved
        cmd_ids.append(resolved_id)
        cmd_symbols.append(resolved_symbol)

    arg_match = _RAW_ARG_RE.search(body)
    if arg_match is None:
        return UnhandledElement(name, "raw table literal has no `arg = ...` field")
    arg_text = arg_match.group(1)
    if arg_text.startswith("{"):
        numbers = re.findall(r"-?\d+", arg_text)
        if not numbers:
            return UnhandledElement(name, "raw table literal's `arg = {...}` is empty")
        arg = int(numbers[0])
    else:
        arg = int(arg_text)

    crew_match = _RAW_CREW_RE.search(body)
    if crew_match is None:
        crew, crew_explicit = 0, False
    else:
        numbers = re.findall(r"-?\d+", crew_match.group(1))
        crew, crew_explicit = (int(numbers[0]), True) if numbers else (0, False)

    hint_match = _RAW_HINT_RE.search(body)
    label = hint_match.group(2) if hint_match is not None else ""

    return RawElement(
        name=name,
        device_id=device_id,
        device_symbol=device_symbol,
        cmd_id=cmd_ids[0],
        cmd_symbol=cmd_symbols[0],
        arg=arg,
        label=label,
        shape="raw_table_literal",
        crew=crew,
        crew_explicit=crew_explicit,
        cmd2_id=cmd_ids[1] if len(cmd_ids) > 1 else None,
        cmd2_symbol=cmd_symbols[1] if len(cmd_symbols) > 1 else None,
    )


def _parse_element_at(
    stripped_text: str,
    name: str,
    rhs_start: int,
    devices: dict[str, int],
    command_defs: dict[str, dict[str, int]],
) -> RawElement | UnhandledElement:
    rest = stripped_text[rhs_start:]
    call_match = _CALL_HEAD_RE.match(rest)
    if call_match is not None:
        helper = call_match.group(1)
        open_paren = rhs_start + call_match.end() - 1
        try:
            args_text = _extract_balanced(stripped_text, open_paren, "(", ")")
        except ValueError:
            return UnhandledElement(name, "unbalanced parentheses in call")
        args = _split_top_level(args_text)
        return _parse_helper_call(name, helper, args, devices, command_defs)
    if rest[:1] == "{":
        try:
            body = _extract_balanced(stripped_text, rhs_start, "{", "}")
        except ValueError:
            return UnhandledElement(name, "unbalanced braces in table literal")
        return _parse_raw_literal(name, body, devices, command_defs)
    return UnhandledElement(
        name, "could not determine assignment form (neither a call nor a table literal)"
    )


def _read_simple_rhs(text: str, start: int) -> str:
    """The RHS of an `elements["X"].field = ...` post-assignment: a
    balanced `{...}` list, or otherwise everything up to the next
    top-level separator/newline."""
    if text[start : start + 1] == "{":
        body = _extract_balanced(text, start, "{", "}")
        return "{" + body + "}"
    end = start
    n = len(text)
    while end < n and text[end] not in ",;\n":
        end += 1
    return text[start:end]


def scan_clickabledata(
    text: str, devices: dict[str, int], command_defs: dict[str, dict[str, int]]
) -> tuple[int, dict[str, RawElement], list[UnhandledElement], int]:
    """Returns `(heads, handled, unhandled, n_post_assigns)`. Every
    `elements[...]` occurrence lands in exactly one of three buckets by
    construction (one regex pass, classified immediately): a definition
    (`elements["X"] = ...`), a field patch (`elements["X"].field = ...`,
    235 of them in the real file -- only `crew_member_access` patches are
    applied, every other field is counted and otherwise ignored, since
    none of `turn_box`/`sound`/`updatable`/`side`/`arg_value`/`arg_lim`/
    `animation_speed` is part of this registry's schema), or neither (an
    ambiguous reference, e.g. a read rather than an assignment --
    unhandled, same as a parse failure). So
    `heads == len(handled) + len(unhandled) + n_post_assigns` always
    holds; `main()` asserts it rather than trusting the construction."""
    stripped = _strip_lua_comments(text)
    heads = 0
    handled: dict[str, RawElement] = {}
    unhandled: list[UnhandledElement] = []
    post_assigns: list[tuple[str, str, str]] = []

    for ref in _ELEMENTS_REF_RE.finditer(stripped):
        heads += 1
        name = ref.group("name")
        post_match = _POST_ASSIGN_RE.match(stripped, ref.end())
        if post_match is not None:
            field = post_match.group(1)
            rhs_text = _read_simple_rhs(stripped, post_match.end())
            post_assigns.append((name, field, rhs_text))
            continue
        def_match = _DEF_EQUALS_RE.match(stripped, ref.end())
        if def_match is None:
            unhandled.append(
                UnhandledElement(
                    name,
                    'an `elements[...]` reference is neither `elements["X"] = ...` '
                    'nor `elements["X"].field = ...` -- possibly a read rather than '
                    "an assignment",
                )
            )
            continue
        result = _parse_element_at(
            stripped, name, def_match.end(), devices, command_defs
        )
        if isinstance(result, RawElement):
            handled[result.name] = result
        else:
            unhandled.append(result)

    for element_name, field, rhs_text in post_assigns:
        if field != "crew_member_access" or element_name not in handled:
            continue
        numbers = re.findall(r"-?\d+", rhs_text)
        if not numbers:
            continue
        handled[element_name] = replace(
            handled[element_name], crew=int(numbers[0]), crew_explicit=True
        )

    return heads, handled, unhandled, len(post_assigns)


# --- output ---------------------------------------------------------------


def _toml_key(name: str) -> str:
    if _BARE_TOML_KEY_RE.match(name):
        return name
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_toml(
    handled: dict[str, RawElement],
    dcs_build: str,
    heads: int,
    n_unhandled: int,
    n_post_assigns: int,
) -> str:
    lines = [
        "# GENERATED by body-layer/tools/generate_effector_registry.py. DO NOT HAND-EDIT.",
        "# Regenerate against the installed Mi-24P module (a Windows box with the",
        "# module installed -- this tool reads the live DCS tree and never runs from",
        "# this repo's own dev checkout or CI):",
        "#   python tools/generate_effector_registry.py --write",
        f"# Source DCS build: {dcs_build}",
        (
            f"# Elements: {len(handled)} handled, {n_unhandled} unhandled, "
            f"{n_post_assigns} field patches, {heads} elements[ heads total."
        ),
        "",
    ]
    for name in sorted(handled):
        el = handled[name]
        lines.append(f"[elements.{_toml_key(name)}]")
        lines.append(f"device = {el.device_id}          # devices.{el.device_symbol}")
        lines.append(f"cmd = {el.cmd_id}            # {el.cmd_symbol}")
        if el.cmd2_id is not None:
            lines.append(f"cmd2 = {el.cmd2_id}            # {el.cmd2_symbol}")
        lines.append(f"arg = {el.arg}")
        lines.append(f"label = {_toml_string(el.label)}")
        lines.append(f"shape = {_toml_string(el.shape)}")
        lines.append(f"crew = {el.crew}")
        lines.append(f"crew_explicit = {'true' if el.crew_explicit else 'false'}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --- CLI --------------------------------------------------------------------


def _resolve_scripts_dir(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    env = os.environ.get("DCS_INSTALL_PATH")
    if not env:
        return None
    return Path(env) / _SCRIPTS_SUBPATH


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scripts-dir",
        type=Path,
        default=None,
        help="Mi-24P Cockpit/Scripts directory; overrides DCS_INSTALL_PATH",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write config/effectors-raw.toml; without this, report only",
    )
    parser.add_argument(
        "--allow-unhandled",
        action="store_true",
        help="write the registry anyway, omitting unhandled elements",
    )
    parser.add_argument(
        "--dcs-build",
        default="unknown",
        help="recorded verbatim in the output file's header comment",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"override output path (default {_DEFAULT_OUT_PATH})",
    )
    args = parser.parse_args(argv)

    scripts_dir = _resolve_scripts_dir(args.scripts_dir)
    if scripts_dir is None:
        print(
            "Not on the DCS machine: no --scripts-dir given and DCS_INSTALL_PATH is "
            "not set. This tool reads the installed Mi-24P module directly and does "
            "not search for an install -- pass --scripts-dir, or set "
            "DCS_INSTALL_PATH and re-run.",
            file=sys.stderr,
        )
        return 2

    required = ("devices.lua", "command_defs.lua", "clickabledata.lua")
    missing = [f for f in required if not (scripts_dir / f).exists()]
    if missing:
        print(
            f"missing file(s) in {scripts_dir}: {', '.join(missing)}", file=sys.stderr
        )
        return 2

    devices_text = (scripts_dir / "devices.lua").read_text(encoding="utf-8")
    command_defs_text = (scripts_dir / "command_defs.lua").read_text(encoding="utf-8")
    clickable_text = (scripts_dir / "clickabledata.lua").read_text(encoding="utf-8")

    devices = parse_devices(_strip_lua_comments(devices_text))
    try:
        command_defs = parse_command_defs(_strip_lua_comments(command_defs_text))
    except CommandDefsParseError as exc:
        print(f"command_defs.lua: {exc}", file=sys.stderr)
        return 2

    heads, handled, unhandled, n_post_assigns = scan_clickabledata(
        clickable_text, devices, command_defs
    )
    assert heads == len(handled) + len(unhandled) + n_post_assigns, (
        heads,
        len(handled),
        len(unhandled),
        n_post_assigns,
    )

    print(
        f"{heads} elements[ heads: {len(handled)} emitted, {len(unhandled)} unhandled, "
        f"{n_post_assigns} field patches"
    )
    if unhandled:
        print("unhandled:")
        for u in unhandled:
            print(f"  {u.name}: {u.reason}")

    if unhandled and not args.allow_unhandled:
        print(
            f"{len(unhandled)} unhandled element(s) -- fix the parser, or pass "
            "--allow-unhandled to write the registry anyway (unhandled elements "
            "will be omitted, not guessed at)",
            file=sys.stderr,
        )
        return 2

    if not args.write:
        print("(report only -- pass --write to write the registry)")
        return 0

    out_path = args.out or _DEFAULT_OUT_PATH
    rendered = render_toml(
        handled, args.dcs_build, heads, len(unhandled), n_post_assigns
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    print(f"wrote {out_path} ({len(handled)} elements)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
