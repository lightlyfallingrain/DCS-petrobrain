"""Generate `body-layer/config/effectors-raw.toml` from ED's own Mi-24P
cockpit scripts -- `plans/effector-sequences/plan.md` Stage 0.

Reads `devices.lua`, `command_defs.lua` and `clickabledata.lua` from the
installed Mi-24P module's `Cockpit/Scripts` directory, resolves every
`elements[...]` entry's symbolic device/command references to integers,
and emits one TOML entry per clickable element (`device`/`device_name`,
`cmds`/`cmd_names`, `args`, optional `arg_values`, optional `helper_args`,
`values` (settable-value ranges, 2026-10-23 follow-up -- see the "value
ranges" section below), `label`, `shape`, `seat`/`seat_explicit` -- lists
everywhere, so a consumer never branches on a helper-call vs.
raw-table-literal element). **Stdlib only. Parses
the Lua as text; never executes it.**

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
unhandled` or not. A repeated `devices["X"]` or `*_commands` table name
is the same kind of always-fatal failure (`DuplicateNameError`) -- a
repeat would otherwise silently restart a counter and reassign an id
with no error at all.

The completeness count this prints (`elements[` heads == emitted +
unhandled + post-assignments) is the thing to check after every DCS
patch -- a silent drop would otherwise look identical to a clean run.
Top-level statements that are neither (the file's own preamble, in the
real file) are counted separately as "statements ignored" and never
count toward or against that completeness check.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

_BODY_LAYER_ROOT = Path(__file__).resolve().parent.parent
#: R13 (Stage 2, 2026-10-23): one raw dump per aircraft directory name
#: (`effector_registry.aircraft_dir_name`) -- this tool still only reads
#: the Mi-24P scripts tree (`_SCRIPTS_SUBPATH` below, unchanged), so its
#: own default output names that one aircraft explicitly rather than
#: generalising the input side too.
_DEFAULT_OUT_PATH = _BODY_LAYER_ROOT / "config" / "effectors-raw" / "mi-24p.toml"
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
_ELEMENTS_HEAD_RE = re.compile(r"elements\s*\[")
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
_RAW_ARG_VALUE_RE = re.compile(r"\barg_value\s*=\s*(\{[^{}]*\}|-?\d+(?:\.\d+)?)")
_RAW_CREW_RE = re.compile(r"\bcrew_member_access\s*=\s*(\{[^{}]*\}|-?\d+)")
_BARE_TOML_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_VERSION_RE = re.compile(r'"version"\s*:\s*"([^"]+)"')

#: `crew_member_access`'s only three forms seen live (Q6, 2026-10-23) --
#: `plans/effector-sequences/plan.md` Stage 0's `{0}`/`{1}`/`{0, 1}` ->
#: `"pilot"`/`"operator"`/`"both"` mapping. A set outside this table is
#: unhandled rather than guessed at.
_SEAT_BY_NUMBERS: dict[frozenset[int], str] = {
    frozenset({0}): "pilot",
    frozenset({1}): "operator",
    frozenset({0, 1}): "both",
}

# --- value ranges (2026-10-23 follow-up) -------------------------------
#
# What each control can be *set to* -- `aircraft-layer/research/
# 2026-10-23-mi24p-clickable-value-ranges.md` is the source of truth this
# section is built against. A `ValueRange` is computed once per entry of
# `RawElement.args` (helper-call elements always have exactly one; a
# raw-table-literal element has one per action, parallel to its own
# `args`/`cmds`) -- never collapsed across actions, since the 13
# raw-literal elements genuinely have a different kind per action (the
# recon's Catch 3).
#
# **Deliberate simplification, stated so it is not mistaken for an
# oversight**: for the handful of helpers whose Lua signature *can* carry
# a custom `arg_lim_`/`arg_value_`/`val1_..val3_` (`default_spring_button`,
# `default_position_tumb`, `default_1_position_tumb`,
# `springloaded_3_pos_tumb`, `radio_wheel_1`), this generator still reads
# that parameter positionally off the real call (never hard-codes the
# default) -- the recon's own "Real calls" section is what tells us *no
# shipped call actually overrides it*, not a reason to stop checking a
# future one. `default_3_position_tumb`'s `arg_limit_`/`inversed_` and
# `multiposition_switch`'s `count_`/`delta_`/`min_`/`inversed_` are parsed
# the same way, and `multiposition_switch`'s `count_` has no default at
# all -- every real call passes a different one (11/4/5/9 steps), so it
# is never optional. `default_animated_lever` is the one deliberate
# exception: its `arg_lim_` parameter is parsed off the call but never
# applied to the output, because DCS's own `arg_lim__` typo (confirmed
# live) makes it dead code in the real helper too -- applying it here
# would disagree with what the switch actually does.
#
# **Amended after the first real Windows run (DCS 2.9.30.28738,
# 2026-10-23 follow-up)**: a positional parameter read this way is often
# a constant-arithmetic expression, not a bare literal -- `1/9`, `1/20`,
# `-2/3`, `0.2 * 5 / 6` all appear on real calls (`_lua_scalar` evaluates
# these via `_lua_arithmetic`/`_eval_constant_arithmetic` rather than
# leaving them `_UNRESOLVED`; the research note's earlier "every real
# call uses d = 0.1" for `multiposition_switch` was wrong and has been
# corrected there). `radio_wheel_1` is TUMB/relative, not LEV/continuous
# -- it is emitted as a stepped discrete range with `relative=True`, not
# a continuous axis. Every computed numeric field is rounded
# (`_round_value`) before being stored, since float division on a
# fraction like the ones above produces noise
# (`0.30000000000000004`) that would otherwise be re-emitted verbatim.


class ValueKind:
    DISCRETE = "discrete"
    CONTINUOUS = "continuous"
    UNKNOWN = "unknown"
    #: A raw-table-literal action whose `class` entry is the bare `0`
    #: (`class_type.NULL`) -- a placeholder action ED's own source
    #: assigns no behaviour to, confirmed live on `ILS-ADJUST-HANDLE-PTR`/
    #: `BRAKE-LEVEL-OP-PTR` (2026-10-23 follow-up). Distinct from
    #: `"unknown"`: there is nothing unrecognised here, the control
    #: simply has no settable value for this action.
    NONE = "none"


@dataclass(frozen=True)
class ValueRange:
    """One `args[i]`'s settable-value description. `kind` decides which
    other fields are meaningful: `"discrete"` uses `values` (sorted,
    never empty), `momentary` (BTN/spring-back vs. a latching TUMB), and
    `relative` (a wheel/knob whose step is added to the *current*
    position on each click, e.g. `radio_wheel_1`, rather than a position
    the control is set to directly); `"continuous"` uses `min`/`max`/
    optional `gain`; `"none"` uses no other field (a NULL-class
    placeholder action); `"unknown"` uses only `reason` -- fail-closed,
    per the module docstring's "Fails closed, at two levels," rather
    than a guessed default."""

    kind: str
    values: tuple[float, ...] | None = None
    min: float | None = None
    max: float | None = None
    gain: float | None = None
    momentary: bool = False
    relative: bool = False
    reason: str | None = None


#: Every `ValueRange` numeric field is rounded to this many decimal
#: places before it is stored -- Lua/Python float arithmetic on a
#: fraction like `1/3` or `0.2 * 5 / 6` produces noise
#: (`0.30000000000000004`) that is otherwise computed once here and then
#: re-emitted verbatim by every downstream reader (the TOML dump, the
#: rendered switch reference) forever.
_VALUE_ROUND_NDIGITS: Final = 6


def _round_value(x: float) -> float:
    return round(x, _VALUE_ROUND_NDIGITS)


def _discrete(
    values: list[float], *, momentary: bool, relative: bool = False
) -> ValueRange:
    return ValueRange(
        kind=ValueKind.DISCRETE,
        values=tuple(sorted({_round_value(v) for v in values})),
        momentary=momentary,
        relative=relative,
    )


def _continuous(lo: float, hi: float, *, gain: float | None = None) -> ValueRange:
    return ValueRange(
        kind=ValueKind.CONTINUOUS,
        min=_round_value(lo),
        max=_round_value(hi),
        gain=(_round_value(gain) if gain is not None else None),
    )


def _unknown_value(reason: str) -> ValueRange:
    return ValueRange(kind=ValueKind.UNKNOWN, reason=reason)


def _none_value() -> ValueRange:
    return ValueRange(kind=ValueKind.NONE)


#: A scalar Lua literal, parsed off a trailing helper parameter that
#: affects a *value* (never the ones that only affect animation/sound/
#: seat, which this section never looks at). Three outcomes, each
#: distinct: a number (use it; a constant-arithmetic expression like
#: `1/9` or `0.2 * 5 / 6` is evaluated via `_lua_arithmetic`, confirmed
#: live 2026-10-23 -- the real module's own `delta_`/`gain_` arguments
#: use these, not bare literals, on roughly half the helper calls that
#: pass one at all), `None` for `nil`/an absent trailing argument (use
#: the helper's own documented default), or the `_UNRESOLVED` sentinel
#: for anything that is not pure numeric-literal arithmetic (a bare
#: identifier such as `anim_speed_default`, a call, a table this parser
#: does not expect here) -- the caller must treat that sentinel as
#: "unknown," never substitute the default silently, which is exactly
#: what "never guessed" means here.
class _Unresolved:
    """Marker type for `_lua_scalar`/`_lua_bool`/`_lua_pair`: the text is
    a Lua expression this generator does not evaluate (a bare
    identifier, an arithmetic expression, a table shape it does not
    expect), distinct from both a parsed value and `nil`/absent. A
    dedicated class, not a bare `object()` sentinel, so `isinstance`
    narrows the return type at every call site -- a plain identity
    sentinel left `mypy --strict` unable to narrow `float | None |
    object` at all, since `object` already contains every other arm of
    that union."""


_UNRESOLVED: Final = _Unresolved()
_SCALAR_LITERAL_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
_BOOL_LITERAL_RE = re.compile(r"^(true|false)$")
_PAIR_LITERAL_RE = re.compile(r"^\{\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\}$")


#: `ast.BinOp.op` node types this generator evaluates -- `+`/`-`/`*`/`/`
#: only, matching Lua's own arithmetic operators on numbers (division is
#: always float, in both languages, so `/` needs no special-casing).
_ARITHMETIC_BINOPS: Final = (ast.Add, ast.Sub, ast.Mult, ast.Div)


def _eval_constant_arithmetic(node: ast.expr) -> float | None:
    """Evaluate `node` if -- recursively -- it is built only from numeric
    literals, unary minus, and `+ - * /` (parentheses are not a node at
    all; `ast.parse` already resolves them into nesting) -- `None` for
    anything else (a `Name`, a `Call`, a string, a comparison, ...), so a
    real identifier such as `anim_speed_default` in `anim_speed_default
    / 5` stays unresolved rather than silently evaluating to some wrong
    substitute. Never uses `eval` -- this is a small hand-written
    whitelist walk over the parsed tree, nothing else is interpreted."""
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        operand = _eval_constant_arithmetic(node.operand)
        return None if operand is None else -operand
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ARITHMETIC_BINOPS):
        left = _eval_constant_arithmetic(node.left)
        right = _eval_constant_arithmetic(node.right)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right  # the only remaining member of _ARITHMETIC_BINOPS: Div
    return None


def _lua_arithmetic(text: str) -> float | None:
    """`text` evaluated as constant-literal arithmetic, or `None` if it
    is not parseable Python expression syntax, not whitelisted by
    `_eval_constant_arithmetic`, or divides by zero -- every failure
    mode collapses to the same `None`, which `_lua_scalar` turns into
    `_UNRESOLVED` rather than a guess."""
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return None
    try:
        return _eval_constant_arithmetic(tree.body)
    except ZeroDivisionError:
        return None


def _lua_scalar(text: str) -> float | None | _Unresolved:
    text = text.strip()
    if text in ("", "nil"):
        return None
    if _SCALAR_LITERAL_RE.match(text):
        return float(text)
    value = _lua_arithmetic(text)
    if value is not None:
        return value
    return _UNRESOLVED


def _lua_bool(text: str) -> bool | None | _Unresolved:
    text = text.strip()
    if text in ("", "nil"):
        return None
    if _BOOL_LITERAL_RE.match(text):
        return text == "true"
    return _UNRESOLVED


def _lua_pair(text: str) -> tuple[float, float] | None | _Unresolved:
    text = text.strip()
    if text in ("", "nil"):
        return None
    m = _PAIR_LITERAL_RE.match(text)
    if m is not None:
        return float(m.group(1)), float(m.group(2))
    return _UNRESOLVED


def _trailing_param(args: list[str], index: int) -> str:
    """`args[index]` if present, else `"nil"` -- a trailing optional
    parameter the Lua call simply omits is indistinguishable from an
    explicit `nil` (both mean "use the default"), so callers never need
    to special-case a short argument list."""
    return args[index] if index < len(args) else "nil"


def _value_range_for_helper(helper: str, args: list[str], arg_idx: int) -> ValueRange:
    """One `ValueRange` for a helper-call element's single `args[0]`
    (every helper-call element has exactly one draw argument, however
    many commands it maps to -- see the module docstring). `args` is the
    full call argument list (`args[0]` is the hint); `arg_idx` is the
    draw-argument's own index in it, same convention as `_parse_helper_call`."""

    def p(offset: int) -> str:
        return _trailing_param(args, arg_idx + offset)

    if helper in (
        "default_button",
        "default_square_button",
        "default_tumb_button",
        "stick_button",
    ):
        return _discrete([0.0, 1.0], momentary=True)

    if helper in (
        "default_2_position_tumb",
        "default_2_position_small_tumb",
        "default_2_position_flares_tumb",
        "default_CB_button",
        "default_blue_cover",
        "default_animated_lever",
    ):
        # `default_animated_lever`'s own `arg_lim_` is deliberately never
        # read here -- see the section docstring above.
        return _discrete([0.0, 1.0], momentary=False)

    if helper in (
        "default_spring_button",
        "default_position_tumb",
        "default_1_position_tumb",
    ):
        lim_offset = {
            "default_spring_button": 2,
            "default_position_tumb": 2,
            "default_1_position_tumb": 3,
        }[helper]
        lim = _lua_pair(p(lim_offset))
        if isinstance(lim, _Unresolved):
            return _unknown_value(f"{helper}'s arg_lim_ is not a literal pair")
        if lim is not None:
            lo, hi = lim
        elif helper == "default_1_position_tumb":
            # This helper's own documented default is `arg_lim_ or {0,
            # arg_val_}` -- distinct from the other two in this group,
            # whose default is the fixed `{0,1}` (research note row 36).
            # `arg_val_` sits one offset before `arg_lim_` (`p(2)`).
            arg_val = _lua_scalar(p(2))
            if isinstance(arg_val, _Unresolved):
                return _unknown_value(
                    "default_1_position_tumb's arg_val_ is not a literal number"
                )
            lo, hi = 0.0, (arg_val if arg_val is not None else 1.0)
        else:
            lo, hi = 0.0, 1.0
        return _discrete([lo, hi], momentary=(helper == "default_spring_button"))

    if helper == "default_3_position_tumb":
        lim = _lua_pair(p(5))
        if isinstance(lim, _Unresolved):
            return _unknown_value(
                "default_3_position_tumb's arg_limit_ is not a literal pair"
            )
        lo, hi = lim if lim is not None else (-1.0, 1.0)
        return _discrete([lo, 0.0, hi], momentary=False)

    if helper == "triple_switch":
        # No parameter affects this one -- the whole element's values
        # are fixed by the helper body itself (confirmed Q-table: every
        # real call is `(hint, dev, cmd, arg[, crew])`).
        return _discrete([0.0, 0.1, 0.2, 0.3], momentary=False)

    if helper == "multiposition_switch":
        count = _lua_scalar(p(1))
        if isinstance(count, _Unresolved) or count is None:
            return _unknown_value(
                "multiposition_switch's count_ is required and must be a literal number"
            )
        delta = _lua_scalar(p(2))
        if isinstance(delta, _Unresolved):
            return _unknown_value(
                "multiposition_switch's delta_ is not a literal number"
            )
        inversed = _lua_bool(p(3))
        if isinstance(inversed, _Unresolved):
            return _unknown_value(
                "multiposition_switch's inversed_ is not a literal boolean"
            )
        min_ = _lua_scalar(p(4))
        if isinstance(min_, _Unresolved):
            return _unknown_value("multiposition_switch's min_ is not a literal number")
        d = delta if delta is not None else 0.5
        if inversed:
            d = -d
        m = min_ if min_ is not None else 0.0
        n = int(count)
        if n < 1:
            return _unknown_value(
                f"multiposition_switch's count_ must be >= 1, got {n}"
            )
        return _discrete([m + k * d for k in range(n)], momentary=False)

    if helper == "springloaded_3_pos_tumb":
        v1 = _lua_scalar(p(2))
        v2 = _lua_scalar(p(3))
        v3 = _lua_scalar(p(4))
        if (
            isinstance(v1, _Unresolved)
            or isinstance(v2, _Unresolved)
            or isinstance(v3, _Unresolved)
        ):
            return _unknown_value(
                "springloaded_3_pos_tumb's val1_/val2_/val3_ is not a literal number"
            )
        values = [
            v1 if v1 is not None else -1.0,
            v2 if v2 is not None else 0.0,
            v3 if v3 is not None else 1.0,
        ]
        return _discrete(values, momentary=True)

    if helper == "default_axis":
        gain = _lua_scalar(p(2))
        if isinstance(gain, _Unresolved):
            return _unknown_value("default_axis's gain_ is not a literal number")
        return _continuous(0.0, 1.0, gain=(gain if gain is not None else 0.1))

    if helper == "default_axis_limited":
        gain = _lua_scalar(p(2))
        if isinstance(gain, _Unresolved):
            return _unknown_value(
                "default_axis_limited's gain_ is not a literal number"
            )
        lim = _lua_pair(p(5))
        if isinstance(lim, _Unresolved):
            return _unknown_value(
                "default_axis_limited's arg_lim_ is not a literal pair"
            )
        lo, hi = lim if lim is not None else (0.0, 1.0)
        return _continuous(lo, hi, gain=(gain if gain is not None else 0.1))

    if helper == "radio_wheel_1":
        # TUMB, relative=true, not LEV/continuous (research note row for
        # `radio_wheel_1`) -- each click adds `arg_value_`'s magnitude to
        # the *current* position rather than setting an absolute one, so
        # this is emitted as a stepped discrete range with `relative`
        # set, not a continuous axis.
        step = _lua_pair(p(1))
        if isinstance(step, _Unresolved):
            return _unknown_value("radio_wheel_1's arg_value_ is not a literal pair")
        lim = _lua_pair(p(2))
        if isinstance(lim, _Unresolved):
            return _unknown_value("radio_wheel_1's arg_lim_ is not a literal pair")
        lo, hi = lim if lim is not None else (0.0, 1.0)
        step_size = abs(step[1]) if step is not None else 0.1
        if step_size <= 0:
            return _unknown_value("radio_wheel_1's arg_value_ step must be nonzero")
        n_steps = round((hi - lo) / step_size)
        if n_steps < 0:
            return _unknown_value(
                "radio_wheel_1's arg_lim_ span is inconsistent with its step"
            )
        values = [lo + k * step_size for k in range(int(n_steps) + 1)]
        return _discrete(values, momentary=False, relative=True)

    if helper in ("default_button_tumb", "springloaded_2_pos_tumb"):
        # Neither is ever called in the real module (confirmed live) and
        # each combines two genuinely different per-action kinds (a
        # momentary push and a latching position) into one shared `arg`
        # -- there is no single-element answer to give without a real
        # call to check it against, so this is left unknown rather than
        # guessed.
        return _unknown_value(
            f"{helper} combines heterogeneous action kinds; never called"
        )

    return _unknown_value(f"no value-range rule for helper {helper!r}")


#: `class_type`'s own enum (`clickable_defs.lua:14`, confirmed live
#: 2026-10-23) -- used only to resolve a bare-integer `class` entry
#: (`BRAKE-LEVEL-OP-PTR`'s third action, `class = {TUMB, LEV, 0}`); every
#: other entry seen live is the dotted `class_type.X` form.
_CLASS_TYPE_BY_NUMBER: dict[int, str] = {
    0: "NULL",
    1: "BTN",
    2: "TUMB",
    3: "SNGBTN",
    4: "LEV",
    5: "MOVABLE_LEV",
    6: "MULTY_TUMB",
    7: "BTN_FIX",
    8: "TUMB_4SIDE",
}

_RAW_CLASS_RE = re.compile(r"\bclass\s*=\s*(\{[^{}]*\}|class_type\.\w+|-?\d+)")
_RAW_GAIN_RE = re.compile(r"\bgain\s*=\s*(\{[^{}]*\}|-?\d+(?:\.\d+)?)")
#: `arg_lim`'s braces can nest one level (`{{0.0,1.0},{0.0,0.5}}`, one
#: pair per action) -- unlike `class`/`gain`/`action`/`arg`, a flat
#: `\{[^{}]*\}` regex cannot capture that, so only the field's *start* is
#: matched here and the value itself is read with `_extract_balanced`
#: (`_find_arg_lim_field`).
_RAW_ARG_LIM_START_RE = re.compile(r"\barg_lim\s*=\s*\{")


def _find_arg_lim_field(body: str) -> str | None:
    """The raw literal's own `arg_lim = {...}` field, braces included, or
    `None` if the field is absent -- `_parse_pair_list` expects the outer
    braces to still be there, the same contract `_RAW_CLASS_RE`/
    `_RAW_GAIN_RE`'s matches already have."""
    m = _RAW_ARG_LIM_START_RE.search(body)
    if m is None:
        return None
    open_pos = m.end() - 1
    inner = _extract_balanced(body, open_pos, "{", "}")
    return "{" + inner + "}"


def _parse_class_list(text: str) -> list[str] | None:
    """Every entry of a raw literal's `class` field, in order -- a scalar
    (`class_type.BTN`) is one-element. `None` if any entry is neither a
    `class_type.<NAME>` reference nor a bare integer this table knows."""
    text = text.strip()
    if text.startswith("{"):
        parts = [p.strip() for p in text[1:-1].split(",")]
    else:
        parts = [text]
    result: list[str] = []
    for part in parts:
        m = re.match(r"^class_type\.(\w+)$", part)
        if m is not None:
            result.append(m.group(1))
            continue
        if _INT_RE.match(part):
            name = _CLASS_TYPE_BY_NUMBER.get(int(part))
            if name is None:
                return None
            result.append(name)
            continue
        return None
    return result


def _parse_pair_list(text: str) -> list[tuple[float, float]] | None:
    """A raw literal's `arg_lim`/`gain`-shaped field: either one flat pair
    (`{0.0, 1.0}`, a single action) or a list of pairs
    (`{{0.0,1.0},{0.0,0.5}}`, one per action). `None` on any other shape."""
    text = text.strip()
    if not text.startswith("{") or not text.endswith("}"):
        return None
    inner = text[1:-1]
    parts = _split_top_level(inner)
    if not parts:
        return None
    if all(p.startswith("{") for p in parts):
        pairs: list[tuple[float, float]] = []
        for p in parts:
            m = _PAIR_LITERAL_RE.match(p)
            if m is None:
                return None
            pairs.append((float(m.group(1)), float(m.group(2))))
        return pairs
    if len(parts) == 2 and all(_SCALAR_LITERAL_RE.match(p) for p in parts):
        return [(float(parts[0]), float(parts[1]))]
    return None


def _parse_gain_list(text: str) -> list[float] | None:
    text = text.strip()
    if text.startswith("{"):
        parts = _split_top_level(text[1:-1])
    else:
        parts = [text]
    values: list[float] = []
    for p in parts:
        if not _SCALAR_LITERAL_RE.match(p.strip()):
            return None
        values.append(float(p.strip()))
    return values


def _value_ranges_for_raw_literal(body: str, n_actions: int) -> list[ValueRange]:
    """One `ValueRange` per action of a raw-table-literal element,
    parallel to its own `args`/`cmds` -- the 13 raw-literal elements
    genuinely mix kinds within one element (the recon's Catch 3), so
    these are never collapsed to one shared answer the way a helper-call
    element's single `args[0]` is."""
    class_match = _RAW_CLASS_RE.search(body)
    classes = _parse_class_list(class_match.group(1)) if class_match else None
    if classes is None or len(classes) != n_actions:
        reason = (
            "raw table literal has no parseable `class` field"
            if class_match is None or classes is None
            else f"`class` has {len(classes)} entries, expected {n_actions}"
        )
        return [_unknown_value(reason) for _ in range(n_actions)]

    lim_field = _find_arg_lim_field(body)
    lims = _parse_pair_list(lim_field) if lim_field is not None else None
    if lims is None or len(lims) != n_actions:
        reason = (
            "raw table literal has no parseable `arg_lim` field"
            if lim_field is None or lims is None
            else f"`arg_lim` has {len(lims)} entries, expected {n_actions}"
        )
        return [_unknown_value(reason) for _ in range(n_actions)]

    gain_match = _RAW_GAIN_RE.search(body)
    gains = _parse_gain_list(gain_match.group(1)) if gain_match else None

    result: list[ValueRange] = []
    for i, (kind, (lo, hi)) in enumerate(zip(classes, lims)):
        if kind == "BTN":
            result.append(_discrete([lo, hi], momentary=True))
        elif kind == "TUMB":
            result.append(_discrete([lo, hi], momentary=False))
        elif kind in ("LEV", "MOVABLE_LEV"):
            gain = gains[i] if gains is not None and i < len(gains) else None
            result.append(_continuous(lo, hi, gain=gain))
        elif kind == "NULL":
            # A placeholder action (`ILS-ADJUST-HANDLE-PTR`'s third/
            # fourth actions, `BRAKE-LEVEL-OP-PTR`'s third) -- its own
            # `arg_lim` pair is present but unused, since the action has
            # no behaviour at all. Not "unknown": there is nothing here
            # this generator failed to recognise.
            result.append(_none_value())
        else:
            result.append(_unknown_value(f"unhandled raw-literal class {kind!r}"))
    return result


class CommandDefsParseError(Exception):
    """A `command_defs.lua` structure this generator does not recognise
    at all -- see the module docstring's "Fails closed, at two levels"."""


class DuplicateNameError(Exception):
    """A name `devices.lua`/`command_defs.lua` declare must be unique --
    a `devices["X"]` name or a `*_commands` table name (reset by a second
    `count = start_command`) -- appears a second time. Always fatal, same
    posture as `CommandDefsParseError`: a repeat silently restarts a
    counter and reassigns an id with no error, no "unhandled" entry, and
    no effect on the `elements[`-heads completeness count, which only
    watches `clickabledata.lua` and never this file's own internal
    consistency -- so it is checked explicitly rather than trusted to
    surface some other way (found by mutation review, 2026-10-23)."""


@dataclass(frozen=True)
class RawElement:
    """`plan.md` Stage 0's output schema: lists everywhere (`cmds`,
    `cmd_names`, `args`, plus `arg_values` when present) so a consumer
    never branches between a helper-call element and a raw-table-literal
    one. `seat` is always one of `"pilot"`/`"operator"`/`"both"` --
    never the plan's original literal `"default"` -- with
    `seat_explicit` carrying whether `crew_member_access` was actually
    present in the source (see this tool's module docstring / the
    Implementer's report for why)."""

    name: str
    device_id: int
    device_symbol: str
    cmd_ids: list[int]
    cmd_symbols: list[str]
    args: list[int]
    label: str
    shape: str
    seat: str
    seat_explicit: bool
    arg_values: list[float] | None = None
    #: Verbatim source text of every positional call argument after the
    #: draw argument (`helper_args` in `plan.md`'s Output section) --
    #: `animation_speed_`/`arg_val_`/`turn_box_`/crew-class trailing
    #: parameters this generator does not otherwise resolve. `None` for
    #: a raw-table-literal element (it has no positional call at all) or
    #: a helper call with nothing after the draw argument.
    helper_args: tuple[str, ...] | None = None
    #: One `ValueRange` per entry of `args` -- see the "value ranges"
    #: section above for what "per entry" means for a helper call (always
    #: one) vs. a raw-table-literal element (one per action).
    value_ranges: tuple[ValueRange, ...] = ()


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
    simply taken at face value without disturbing the running sequence.
    A repeated device name is a `DuplicateNameError`, never a silent
    reassignment."""
    devices: dict[str, int] = {}
    counter_next = 1
    for m in _DEVICE_ASSIGN_RE.finditer(stripped_text):
        name, rhs = m.group(1), m.group(2).strip()
        if name in devices:
            raise DuplicateNameError(f'device "{name}" is declared more than once')
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
    exactly right: nothing in `clickabledata.lua` references `Keys`. A
    table name reset a second time is a `DuplicateNameError`, never a
    silent restart of its counter."""
    tables: dict[str, dict[str, int]] = {}
    for marker in _RESET_MARKER_RE.finditer(stripped_text):
        header_match = _TABLE_HEADER_RE.match(stripped_text, marker.end())
        if header_match is None:
            raise CommandDefsParseError(
                f"reset marker at offset {marker.start()} is not followed by "
                "`<table> = ...`"
            )
        table_name = header_match.group(1)
        if table_name in tables:
            raise DuplicateNameError(
                f'table "{table_name}" is reset by a second '
                "`count = start_command` / table header"
            )
        brace_match = _BRACE_RE.match(stripped_text, header_match.end())
        if brace_match is None:
            raise CommandDefsParseError(
                f"table `{table_name}` after a reset marker is not assigned a "
                "`{...}` literal"
            )
        brace_pos = brace_match.end() - 1
        body = _extract_balanced(stripped_text, brace_pos, "{", "}")
        close_pos = brace_pos + len(body) + 2
        tables[table_name] = {}
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


def _seat_for(numbers: list[int]) -> str | None:
    return _SEAT_BY_NUMBERS.get(frozenset(numbers))


def _parse_int_list(text: str) -> list[int]:
    """`arg = {738, 738}` or `arg = 738` -- a braced list keeps every
    number in order, including duplicates (the PTT shape's two
    identical `738`s)."""
    text = text.strip()
    if text.startswith("{"):
        return [int(n) for n in _NUMBER_RE.findall(text)]
    return [int(text)]


def _parse_float_list(text: str) -> list[float]:
    text = text.strip()
    if text.startswith("{"):
        return [float(n) for n in _NUMBER_RE.findall(text)]
    return [float(text)]


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
        seat, seat_explicit = "pilot", False
    else:
        crew_text = args[crew_idx].strip()
        if crew_text in ("nil", ""):
            seat, seat_explicit = "pilot", False
        elif _INT_RE.match(crew_text):
            resolved_seat = _seat_for([int(crew_text)])
            if resolved_seat is None:
                return UnhandledElement(
                    name,
                    f"unrecognised crew_member_access value: {crew_text}",
                )
            seat, seat_explicit = resolved_seat, True
        else:
            return UnhandledElement(
                name, f"could not parse crew_member_access expression: {crew_text}"
            )

    helper_args = tuple(args[arg_idx + 1 :]) or None
    value_range = _value_range_for_helper(helper, args, arg_idx)

    return RawElement(
        name=name,
        device_id=device_id,
        device_symbol=device_symbol,
        cmd_ids=cmd_ids,
        cmd_symbols=cmd_symbols,
        args=[arg],
        label=label,
        shape=helper,
        seat=seat,
        seat_explicit=seat_explicit,
        helper_args=helper_args,
        value_ranges=(value_range,),
    )


def _ordered_dotted_refs(text: str) -> list[tuple[str, str]]:
    """Every `<table>.<symbol>` reference in `text`, in order, **including
    duplicates** -- `STICK-PTT-PTR`'s `action = {spu8_commands.X,
    spu8_commands.X}` (the same command twice, once per LMB/RMB) must
    produce two list entries matching its two-element `arg`/`arg_value`
    lists, not collapse to one."""
    return [(m.group(1), m.group(2)) for m in _ANY_DOTTED_REF_RE.finditer(text)]


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
    refs = _ordered_dotted_refs(action_match.group(1))
    if not refs:
        return UnhandledElement(
            name,
            f"`action` field has no <command_table>.<symbol> reference: {action_match.group(1)}",
        )
    cmd_ids: list[int] = []
    cmd_symbols: list[str] = []
    for table, cmd_name in refs:
        resolved = _resolve_cmd(table, cmd_name, command_defs)
        if isinstance(resolved, str):
            return UnhandledElement(name, resolved)
        resolved_id, resolved_symbol = resolved
        cmd_ids.append(resolved_id)
        cmd_symbols.append(resolved_symbol)

    arg_match = _RAW_ARG_RE.search(body)
    if arg_match is None:
        return UnhandledElement(name, "raw table literal has no `arg = ...` field")
    args = _parse_int_list(arg_match.group(1))
    if not args:
        return UnhandledElement(name, "raw table literal's `arg = {...}` is empty")

    arg_value_match = _RAW_ARG_VALUE_RE.search(body)
    arg_values = (
        _parse_float_list(arg_value_match.group(1))
        if arg_value_match is not None
        else None
    )

    crew_match = _RAW_CREW_RE.search(body)
    if crew_match is None:
        seat, seat_explicit = "pilot", False
    else:
        numbers = _parse_int_list(crew_match.group(1))
        resolved_seat = _seat_for(numbers)
        if resolved_seat is None:
            return UnhandledElement(
                name, f"unrecognised crew_member_access value(s): {numbers}"
            )
        seat, seat_explicit = resolved_seat, True

    hint_match = _RAW_HINT_RE.search(body)
    label = hint_match.group(2) if hint_match is not None else ""

    value_ranges = tuple(_value_ranges_for_raw_literal(body, len(args)))

    return RawElement(
        name=name,
        device_id=device_id,
        device_symbol=device_symbol,
        cmd_ids=cmd_ids,
        cmd_symbols=cmd_symbols,
        args=args,
        arg_values=arg_values,
        label=label,
        shape="raw_table_literal",
        seat=seat,
        seat_explicit=seat_explicit,
        value_ranges=value_ranges,
    )


def _line_end(text: str, pos: int) -> int:
    nl = text.find("\n", pos)
    return len(text) if nl == -1 else nl


def _line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _parse_element_at(
    stripped_text: str,
    name: str,
    rhs_start: int,
    devices: dict[str, int],
    command_defs: dict[str, dict[str, int]],
) -> tuple[RawElement | UnhandledElement, int]:
    """Returns the parsed element (or an `UnhandledElement`) alongside the
    offset immediately after the value it consumed -- the closing `)`/`}`
    on success, or the end of `rhs_start`'s own line on failure (every
    call/literal form this parser recognises, or fails to recognise
    outright, fits on one line per the 2026-10-23 recon). Callers use
    this span to blank out the statement for "statements ignored"
    accounting (`scan_clickabledata`)."""
    rest = stripped_text[rhs_start:]
    call_match = _CALL_HEAD_RE.match(rest)
    if call_match is not None:
        helper = call_match.group(1)
        open_paren = rhs_start + call_match.end() - 1
        try:
            args_text = _extract_balanced(stripped_text, open_paren, "(", ")")
        except ValueError:
            return (
                UnhandledElement(name, "unbalanced parentheses in call"),
                _line_end(stripped_text, rhs_start),
            )
        close_pos = open_paren + len(args_text) + 2
        args = _split_top_level(args_text)
        return (
            _parse_helper_call(name, helper, args, devices, command_defs),
            close_pos,
        )
    if rest[:1] == "{":
        try:
            body = _extract_balanced(stripped_text, rhs_start, "{", "}")
        except ValueError:
            return (
                UnhandledElement(name, "unbalanced braces in table literal"),
                _line_end(stripped_text, rhs_start),
            )
        close_pos = rhs_start + len(body) + 2
        return (
            _parse_raw_literal(name, body, devices, command_defs),
            close_pos,
        )
    return (
        UnhandledElement(
            name,
            "could not determine assignment form (neither a call nor a table literal)",
        ),
        _line_end(stripped_text, rhs_start),
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


def _find_ignored_statements(
    stripped: str, consumed_spans: list[tuple[int, int]]
) -> list[tuple[int, str]]:
    """`plan.md` point 6's "statements ignored": blank out every matched
    `elements[...]` head's own span, then any remaining non-blank line is
    a top-level statement this scanner does not treat as part of the
    clickable-element surface at all -- the file's own preamble
    (`dofile`/`local`/plain-assignment lines, and `elements = {}` itself)
    in the real file, confirmed by the 2026-10-23 recon's Q4 to be
    everything before the first `elements[...]` assignment there. Never
    fatal, never part of the `heads == handled + unhandled + patches`
    completeness arithmetic -- counted and reported separately."""
    chars = list(stripped)
    for start, end in consumed_spans:
        for i in range(start, min(end, len(chars))):
            if chars[i] != "\n":
                chars[i] = " "
    blanked = "".join(chars)
    ignored: list[tuple[int, str]] = []
    for line_no, line in enumerate(blanked.split("\n"), start=1):
        if line.strip():
            ignored.append((line_no, line.strip()))
    return ignored


def scan_clickabledata(
    text: str, devices: dict[str, int], command_defs: dict[str, dict[str, int]]
) -> tuple[
    int, dict[str, RawElement], list[UnhandledElement], int, list[tuple[int, str]]
]:
    """Returns `(heads, handled, unhandled, n_post_assigns, ignored)`.
    Every `elements[` head -- any key form, not only a quoted string
    literal -- lands in exactly one of three buckets by construction
    (one pass, classified immediately): a definition
    (`elements["X"] = ...`), a field patch (`elements["X"].field = ...`,
    235 of them in the real file -- only `crew_member_access` patches are
    applied, every other field is counted and otherwise ignored, since
    none of `turn_box`/`sound`/`updatable`/`side`/`arg_value`/`arg_lim`/
    `animation_speed` is part of this registry's schema), or neither (an
    ambiguous reference, e.g. a read rather than an assignment, **or a
    dynamic/computed key such as `elements[key..i]`** -- unhandled in
    both cases, surfaced rather than silently skipped, since the quoted-
    literal regex alone would never even see a non-literal key). So
    `heads == len(handled) + len(unhandled) + n_post_assigns` always
    holds; `main()` asserts it rather than trusting the construction.
    `ignored` is `_find_ignored_statements`'s result -- see its own
    docstring; it plays no part in the completeness arithmetic above."""
    stripped = _strip_lua_comments(text)
    heads = 0
    handled: dict[str, RawElement] = {}
    unhandled: list[UnhandledElement] = []
    post_assigns: list[tuple[str, str, str]] = []
    consumed_spans: list[tuple[int, int]] = []

    for head in _ELEMENTS_HEAD_RE.finditer(stripped):
        ref = _ELEMENTS_REF_RE.match(stripped, head.start())
        if ref is None:
            heads += 1
            bracket_pos = head.end() - 1
            try:
                key_text = _extract_balanced(stripped, bracket_pos, "[", "]")
            except ValueError:
                key_text = "?"
            unhandled.append(
                UnhandledElement(
                    f"<dynamic key at line {_line_no(stripped, head.start())}>",
                    "elements[...] key is not a literal string (dynamic/computed "
                    f"key: {key_text!r}) -- unhandled",
                )
            )
            consumed_spans.append((head.start(), _line_end(stripped, head.start())))
            continue

        heads += 1
        name = ref.group("name")
        post_match = _POST_ASSIGN_RE.match(stripped, ref.end())
        if post_match is not None:
            field = post_match.group(1)
            rhs_start = post_match.end()
            rhs_text = _read_simple_rhs(stripped, rhs_start)
            post_assigns.append((name, field, rhs_text))
            consumed_spans.append((ref.start(), rhs_start + len(rhs_text)))
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
            consumed_spans.append((ref.start(), _line_end(stripped, ref.start())))
            continue
        result, consumed_end = _parse_element_at(
            stripped, name, def_match.end(), devices, command_defs
        )
        consumed_spans.append((ref.start(), consumed_end))
        if isinstance(result, RawElement):
            handled[result.name] = result
        else:
            unhandled.append(result)

    for element_name, field, rhs_text in post_assigns:
        if element_name not in handled:
            continue
        if field == "crew_member_access":
            numbers = [int(n) for n in _NUMBER_RE.findall(rhs_text)]
            if not numbers:
                continue
            resolved_seat = _seat_for(numbers)
            if resolved_seat is None:
                unhandled.append(
                    UnhandledElement(
                        element_name,
                        f"unrecognised crew_member_access value(s) in a post-assignment "
                        f"patch: {numbers}",
                    )
                )
                del handled[element_name]
                continue
            handled[element_name] = replace(
                handled[element_name], seat=resolved_seat, seat_explicit=True
            )
        elif field == "arg_lim":
            # The two ASP-17 sight-mode switches (`SIGHT-MAN-AUTO-PTR`/
            # `SIGHT-SYNC-UNSYNC-PTR`) are patched to 0.0/0.5 after their
            # `default_2_position_tumb` call already set 0/1 (recon's
            # "Post-assignment patches that change values") -- applied
            # here, after the helper-based value range, so the patch
            # always wins. `None`/empty means the patch's own RHS is not
            # a shape this generator parses; the helper's own range is
            # then left standing rather than silently discarded.
            current = handled[element_name]
            if len(current.value_ranges) != 1:
                continue
            old = current.value_ranges[0]
            if old.kind != ValueKind.DISCRETE:
                continue
            pairs = _parse_pair_list(rhs_text)
            if not pairs:
                continue
            lo, hi = pairs[0]
            handled[element_name] = replace(
                current,
                value_ranges=(
                    ValueRange(
                        kind=ValueKind.DISCRETE,
                        values=tuple(sorted({lo, hi})),
                        momentary=old.momentary,
                    ),
                ),
            )

    ignored = _find_ignored_statements(stripped, consumed_spans)
    return heads, handled, unhandled, len(post_assigns), ignored


# --- output ---------------------------------------------------------------


#: TOML basic-string short escapes (TOML spec: `\b \t \n \f \r \" \\`).
#: Every other control codepoint below U+0020, plus DEL (U+007F), has no
#: short form and must go out as `\uXXXX` -- `BL-B91`: `label`/`name` are
#: ED-sourced free text, unlike every numeric field here, which is regex-
#: constrained to `-?\d+` before it ever reaches this renderer, so this is
#: the one place a stray control character could otherwise produce a raw
#: literal newline (or other C0 byte) inside a TOML basic string, which
#: `tomllib` refuses to parse (fails closed, but on the *next* run that
#: reads the file back -- better to never emit it).
_TOML_SHORT_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def _toml_escape(value: str) -> str:
    out: list[str] = []
    for ch in value:
        short = _TOML_SHORT_ESCAPES.get(ch)
        if short is not None:
            out.append(short)
        elif ch < "\x20" or ch == "\x7f":
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def _toml_key(name: str) -> str:
    if _BARE_TOML_KEY_RE.match(name):
        return name
    return f'"{_toml_escape(name)}"'


def _toml_string(value: str) -> str:
    return f'"{_toml_escape(value)}"'


def _toml_int_array(values: list[int]) -> str:
    return "[" + ", ".join(str(v) for v in values) + "]"


def _toml_float_array(values: list[float]) -> str:
    return "[" + ", ".join(str(v) for v in values) + "]"


def _toml_str_array(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(v) for v in values) + "]"


def _toml_value_range(vr: ValueRange) -> str:
    """One `ValueRange` as a TOML inline table -- `kind` decides which
    other keys are present, mirroring the dataclass's own "which fields
    are meaningful" rule (its own docstring)."""
    parts = [f"kind = {_toml_string(vr.kind)}"]
    if vr.kind == ValueKind.DISCRETE:
        assert vr.values is not None
        parts.append(f"values = {_toml_float_array(list(vr.values))}")
        parts.append(f"momentary = {'true' if vr.momentary else 'false'}")
        if vr.relative:
            parts.append("relative = true")
    elif vr.kind == ValueKind.CONTINUOUS:
        assert vr.min is not None and vr.max is not None
        parts.append(f"min = {vr.min}")
        parts.append(f"max = {vr.max}")
        if vr.gain is not None:
            parts.append(f"gain = {vr.gain}")
    elif vr.kind == ValueKind.NONE:
        pass  # no other field is meaningful for a NULL-class placeholder
    else:
        assert vr.reason is not None
        parts.append(f"reason = {_toml_string(vr.reason)}")
    return "{ " + ", ".join(parts) + " }"


def _toml_value_ranges_array(value_ranges: tuple[ValueRange, ...]) -> str:
    return "[" + ", ".join(_toml_value_range(vr) for vr in value_ranges) + "]"


def sha256_hexdigest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_toml(
    handled: dict[str, RawElement],
    dcs_build: str,
    sha256_by_file: dict[str, str],
    heads: int,
    n_unhandled: int,
    n_post_assigns: int,
    n_ignored: int,
) -> str:
    source_subpath = "/".join(_SCRIPTS_SUBPATH.parts)
    inputs = ", ".join(f"{name} {digest}" for name, digest in sha256_by_file.items())
    n_unknown_value_ranges = len(_unknown_value_ranges(handled))
    lines = [
        "# GENERATED by body-layer/tools/generate_effector_registry.py. DO NOT HAND-EDIT.",
        "# Regenerate against the installed Mi-24P module (a Windows box with the",
        "# module installed -- this tool reads the live DCS tree and never runs from",
        "# this repo's own dev checkout or CI):",
        "#   python tools/generate_effector_registry.py --write",
        f"# Source: {source_subpath}, DCS {dcs_build}",
        f"# Inputs (sha256): {inputs}",
        (
            f"# Elements: {len(handled)} emitted, {n_unhandled} unhandled, "
            f"{n_post_assigns} field patches, {heads} elements[ heads total. "
            f"Statements ignored: {n_ignored} (see the run report). "
            f"Value ranges unknown: {n_unknown_value_ranges} (see the run report)."
        ),
        "# Regenerate after any DCS update: device and command numbers are positional.",
        "",
    ]
    for name in sorted(handled):
        el = handled[name]
        lines.append(f"[elements.{_toml_key(name)}]")
        lines.append(f"device = {el.device_id}")
        lines.append(f"device_name = {_toml_string(el.device_symbol)}")
        lines.append(f"cmds = {_toml_int_array(el.cmd_ids)}")
        lines.append(f"cmd_names = {_toml_str_array(el.cmd_symbols)}")
        lines.append(f"args = {_toml_int_array(el.args)}")
        if el.arg_values is not None:
            lines.append(f"arg_values = {_toml_float_array(el.arg_values)}")
        if el.helper_args is not None:
            lines.append(f"helper_args = {_toml_str_array(list(el.helper_args))}")
        if el.value_ranges:
            lines.append(f"values = {_toml_value_ranges_array(el.value_ranges)}")
        lines.append(f"label = {_toml_string(el.label)}")
        lines.append(f"shape = {_toml_string(el.shape)}")
        lines.append(f"seat = {_toml_string(el.seat)}")
        lines.append(f"seat_explicit = {'true' if el.seat_explicit else 'false'}")
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


def _read_dcs_build_from_autoupdate_cfg(install_path: Path) -> str | None:
    """`$DCS_INSTALL_PATH/autoupdate.cfg` -- that exact file, no walking
    up -- carries a `"version": "..."` field (confirmed live, 2026-10-23
    recon header). Returns `None` on anything unreadable or unparsable;
    the caller turns that into the same "pass --dcs-build" refusal as a
    wholly absent `DCS_INSTALL_PATH`."""
    try:
        text = (install_path / "autoupdate.cfg").read_text(encoding="utf-8")
    except OSError:
        return None
    m = _VERSION_RE.search(text)
    return m.group(1) if m else None


def _unknown_value_ranges(
    handled: dict[str, RawElement],
) -> list[tuple[str, int, str]]:
    """Every `(element name, action index, reason)` whose `ValueRange`
    is `"unknown"` across every handled element -- parse-level success
    (the element itself is `handled`, not `unhandled`) says nothing about
    whether its *value range* was determined, and that gap was
    previously silent: a reader had to grep the rendered TOML by hand to
    find out how many controls this run could not place a settable value
    on. Deliberately not fatal (see the module docstring's "Fails
    closed, at two levels" -- a value-range unknown already fails closed
    at the `ValueRange` level, so refusing to write the whole registry
    over it would be a second, redundant refusal) -- loud instead:
    `main` prints every one and a count in the summary line."""
    found: list[tuple[str, int, str]] = []
    for name in sorted(handled):
        for i, vr in enumerate(handled[name].value_ranges):
            if vr.kind == ValueKind.UNKNOWN:
                assert vr.reason is not None
                found.append((name, i, vr.reason))
    return found


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
        default=None,
        help=(
            "recorded verbatim in the output file's header comment; if omitted and "
            "--write is passed, read from $DCS_INSTALL_PATH/autoupdate.cfg"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"override output path (default {_DEFAULT_OUT_PATH})",
    )
    args = parser.parse_args(argv)

    scripts_dir = _resolve_scripts_dir(args.scripts_dir)
    if scripts_dir is None:
        print(
            "DCS_INSTALL_PATH is not set -- not on the DCS machine; pass "
            "--scripts-dir to point elsewhere.",
            file=sys.stderr,
        )
        return 1

    required = ("devices.lua", "command_defs.lua", "clickabledata.lua")
    missing = [f for f in required if not (scripts_dir / f).exists()]
    if missing:
        print(
            f"missing file(s) in {scripts_dir}: {', '.join(missing)}", file=sys.stderr
        )
        return 1

    devices_text = (scripts_dir / "devices.lua").read_text(encoding="utf-8")
    command_defs_text = (scripts_dir / "command_defs.lua").read_text(encoding="utf-8")
    clickable_text = (scripts_dir / "clickabledata.lua").read_text(encoding="utf-8")

    try:
        devices = parse_devices(_strip_lua_comments(devices_text))
    except DuplicateNameError as exc:
        print(f"devices.lua: {exc}", file=sys.stderr)
        return 2
    try:
        command_defs = parse_command_defs(_strip_lua_comments(command_defs_text))
    except (CommandDefsParseError, DuplicateNameError) as exc:
        print(f"command_defs.lua: {exc}", file=sys.stderr)
        return 2

    heads, handled, unhandled, n_post_assigns, ignored = scan_clickabledata(
        clickable_text, devices, command_defs
    )
    assert heads == len(handled) + len(unhandled) + n_post_assigns, (
        heads,
        len(handled),
        len(unhandled),
        n_post_assigns,
    )

    unknown_value_ranges = _unknown_value_ranges(handled)
    print(
        f"{heads} elements[ heads: {len(handled)} emitted, {len(unhandled)} unhandled, "
        f"{n_post_assigns} field patches, {len(ignored)} statements ignored, "
        f"{len(unknown_value_ranges)} value range(s) unknown"
    )
    if unhandled:
        print("unhandled:")
        for u in unhandled:
            print(f"  {u.name}: {u.reason}")
    if unknown_value_ranges:
        print("value range unknown (element emitted, but with no settable-value data):")
        for name, action_idx, reason in unknown_value_ranges:
            print(f"  {name} (action {action_idx}): {reason}")
    if ignored:
        print("statements ignored (neither an elements[...] definition nor a patch):")
        for line_no, snippet in ignored:
            print(f"  line {line_no}: {snippet}")

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

    dcs_build = args.dcs_build
    if dcs_build is None:
        install_env = os.environ.get("DCS_INSTALL_PATH")
        if not install_env:
            print(
                "DCS_INSTALL_PATH is not set and no --dcs-build was given -- "
                "pass --dcs-build.",
                file=sys.stderr,
            )
            return 1
        dcs_build = _read_dcs_build_from_autoupdate_cfg(Path(install_env))
        if dcs_build is None:
            print(
                f'could not read a "version" field from '
                f"{install_env}/autoupdate.cfg -- pass --dcs-build.",
                file=sys.stderr,
            )
            return 1

    out_path = args.output or _DEFAULT_OUT_PATH
    sha256_by_file = {f: sha256_hexdigest(scripts_dir / f) for f in required}
    rendered = render_toml(
        handled,
        dcs_build,
        sha256_by_file,
        heads,
        len(unhandled),
        n_post_assigns,
        len(ignored),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    print(f"wrote {out_path} ({len(handled)} elements)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
