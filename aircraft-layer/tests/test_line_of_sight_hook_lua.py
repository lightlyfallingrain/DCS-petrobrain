"""Static text checks against `dcs-export/petrobrain-line-of-sight-hook.
lua` -- `plans/dcs-driven-los/plan.md` (X-B29).

This project's aircraft-layer Hook scripts have no automated *behavioural*
test (`aircraft-layer/CLAUDE.md`'s own Testing section: "Export.lua, the
overlay Hook script/.dlg pair, and the live Export.lua<->collector<->API
path have no automated test" -- correctness there needs a real DCS
process). What *is* mechanically checkable without DCS is the text of the
one runtime-value splice this codebase has ever put into a `dostring_in`
code string (Security plan review, Finding 3/recommended, non-blocking):
`SET_LOOK_TEMPLATE` must carry exactly the `%d` conversions it is
documented to carry, and no other format specifier -- a future edit
adding a third substitution point (or changing either `%d` to `%s`) is
the change that would make the splice genuinely unsafe, and this is the
guard against it landing unnoticed.

Two `%d`, not one -- see the Lua file's own header for why this
deliberately differs from the Security review's literal "exactly one
%d" phrasing (one coalesced `dostring_in` call sets both `PB_LOOK_HOUR`
and `PB_LOOK_FOV_DEG`, required fix 2, rather than two separate calls)."""

from __future__ import annotations

import re
from pathlib import Path

_LUA_PATH = (
    Path(__file__).resolve().parent.parent
    / "dcs-export"
    / "petrobrain-line-of-sight-hook.lua"
)

#: Matches any `%` format directive Lua's `string.format` would consume --
#: `%%` (a literal percent) is excluded on purpose, since it is not a
#: substitution point.
_FORMAT_DIRECTIVE_RE = re.compile(r"%[^%]")


def _extract_template() -> str:
    text = _LUA_PATH.read_text(encoding="utf-8")
    match = re.search(r'local SET_LOOK_TEMPLATE = "((?:[^"\\]|\\.)*)"', text)
    assert match is not None, "SET_LOOK_TEMPLATE literal not found in the Lua file"
    return match.group(1)


def test_set_look_template_has_exactly_two_percent_d_and_nothing_else() -> None:
    template = _extract_template()
    directives = _FORMAT_DIRECTIVE_RE.findall(template)
    assert directives == ["%d", "%d"], (
        "SET_LOOK_TEMPLATE must carry exactly two '%d' conversions and no "
        f"other format specifier -- found {directives!r}. Adding a third "
        "substitution point (or changing a %d to %s/another specifier) is "
        "the change that would make this splice genuinely unsafe."
    )


def test_set_look_template_sets_both_expected_globals() -> None:
    template = _extract_template()
    assert "PB_LOOK_HOUR=%d" in template
    assert "PB_LOOK_FOV_DEG=%d" in template


def test_lua_file_contains_the_nan_and_infinity_guards() -> None:
    """Security plan review, required fix 1: the clamp must explicitly
    test for NaN (self-inequality) and +-infinity before any ordinary
    min/max comparison -- not rely on `math.min`/`math.max` alone."""
    text = _LUA_PATH.read_text(encoding="utf-8")
    assert "value ~= value" in text, "missing the NaN self-inequality guard"
    assert "math.huge" in text
    assert "-math.huge" in text


def test_lua_file_wraps_the_look_direction_apply_in_pcall() -> None:
    """Security plan review, required fix 1: no error path may leave a
    stale value silently in place -- the decode/clamp/format/dostring_in
    sequence for an inbound datagram is wrapped end to end."""
    text = _LUA_PATH.read_text(encoding="utf-8")
    assert "pcall(pollLookDirection)" in text


def test_lua_file_coalesces_to_one_setter_call_per_frame() -> None:
    """Security plan review, Finding 5/required fix 2: drain every queued
    datagram but apply only the last one, so a burst of duplicate/retried
    directives in one frame never triggers more than one `dostring_in`
    setter call."""
    text = _LUA_PATH.read_text(encoding="utf-8")
    assert "_applyLookDirection(latest)" in text
    # Only one call site invokes the setter -- i.e. it is not called once
    # per datagram inside the drain loop.
    assert text.count("_applyLookDirection(") == 2  # def + the one call site
