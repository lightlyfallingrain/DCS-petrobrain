"""Every `dcs-export/*.lua` file must be loadable Lua 5.1 -- the guard
that was missing on 2026-10-17, when three Hook scripts failed to load in
DCS and Petrovich detected nothing at all for a whole sortie.

**What happened.** This repo's documentation convention links an ID as an
Obsidian wiki link, `[[BL-B73]]` (`docs/DOC_CONVENTIONS.md`). That form
reached the *header block comments* of three Hook scripts, which are
written as Lua long comments -- `--[[ ... ]]`. Lua 5.1 does not nest long
brackets: the wiki link's `]]` closes the comment early and its `[[`
then raises `nesting of [[...]] is deprecated`. DCS logged exactly that
for `petrobrain-firing-events-hook.lua`, `petrobrain-line-of-sight-hook.
lua` and `petrobrain-mission-telemetry-hook.lua`, and loaded none of
them.

The blindness followed from the second one. With the LOS Hook dead,
`GET /line_of_sight/latest` served nothing, every candidate reached
`perception.visibility`'s gate 4 with `live_los_clear=None`, and that
gate is fail-closed by design (`plans/bl11-stage4-fail-closed/plan.md`):
no verdict is treated as blocked. 23744 traced candidates, 0 admitted.

**Why the existing Lua tests did not catch it.** They are static *text*
checks (`test_line_of_sight_hook_lua.py`'s own docstring explains why
behavioural testing needs a real DCS process). Reading a file as text
cannot notice that it is not valid Lua. Nothing here ever parsed these
files, so a syntax error was invisible to every check this repo runs --
which is the whole gap this module closes.

**Two checks, deliberately:**

1. `test_no_nested_long_bracket_in_block_comment` is pure Python and
   always runs. It names the exact failure above, so a reintroduced wiki
   link fails with a message that says what to write instead.
2. `test_loads_as_lua` is the general one -- it catches *any* syntax
   error, not only this family -- but it needs a Lua 5.1 interpreter and
   skips without one. `luajit` is Lua 5.1-compatible and reproduced DCS's
   failure byte for byte; plain `lua` on a dev machine is usually 5.4,
   which accepts constructs 5.1 rejects, so it is not accepted as a
   substitute. Check 1 is what holds on a machine with neither.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_EXPORT_DIR = Path(__file__).resolve().parent.parent / "dcs-export"

_LUA_FILES = sorted(_EXPORT_DIR.glob("*.lua"))

#: Opens a Lua long comment. Long brackets with levels (`--[==[`) are not
#: matched: nesting is legal with a different level, and no file here uses
#: one. If that changes, this check gets more precise, not less -- it would
#: stop looking inside the level-bracketed comment rather than mis-flag it.
_BLOCK_COMMENT_OPEN = "--[["

#: The Obsidian wiki-link form this repo writes IDs in. Inside a long
#: comment it is a syntax error; in a `--` line comment it is harmless but
#: still banned here, because a later reflow of line comments into a block
#: comment would silently reintroduce the fault.
#:
#: **The `.` in the character class is load-bearing** (Reviewer, 2026-10-17).
#: `docs/DOC_CONVENTIONS.md` documents a dotted stage-link form -- a parent
#: milestone links down as `[[AA-1.1]]` -- and `\w` does not include `.`, so
#: the first version of this pattern matched `[[BL-B73]]` and missed
#: `[[AA-1.1]]`. A dotted ID pasted into a Hook header would have
#: reproduced the 2026-10-17 blackout past a guard written to prevent
#: exactly it.
#:
#: Still anchored on a leading letter, so a genuine Lua long-bracket string
#: literal is not matched: `local NULL_CODE = [[return "x"]]` in
#: `petrobrain-elevation-cost-probe-hook.lua` is legal Lua and must stay
#: legal here.
_WIKI_LINK_RE = re.compile(r"\[\[[A-Za-z][\w.-]*\]\]")


#: Parse-only invocations, in preference order, as (tool, argv-tail). Each
#: must parse the file named by `PB_LUA_CHECK_PATH` *without running it* and
#: exit nonzero on a syntax error.
#:
#: `luac5.1 -p` comes first because it is the check
#: `aircraft-layer/CLAUDE.md`'s Commands section already documents for these
#: files, and the one installed where they are deployed -- this test is that
#: documented command moved somewhere it runs on its own, not a second way of
#: doing the same thing. It is absent on the Mac dev machine, which is
#: exactly why the documented form never ran and the 2026-10-17 breakage
#: shipped. `luajit` and `lua5.1` are the fallbacks; both implement 5.1's
#: long-bracket rule, and `luajit` is what reproduced DCS's failure locally.
#:
#: A newer `luac`/`lua` is deliberately NOT accepted: 5.2+ parses constructs
#: DCS's embedded 5.1 rejects, so it would pass the very file that breaks in
#: flight.
_PARSE_ONLY_TOOLS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("luac5.1", ("-p",)),
    ("luajit", ("-bl",)),
    ("lua5.1", ()),
)


def _parse_command(path: Path) -> list[str] | None:
    """A parse-only command line for `path`, or `None` when no Lua 5.1
    tool is installed."""
    for tool, flags in _PARSE_ONLY_TOOLS:
        found = shutil.which(tool)
        if found is None:
            continue
        if tool == "lua5.1":
            # No parse-only flag on the interpreter itself -- `loadfile`
            # is the equivalent, and the path travels by environment
            # variable so nothing is spliced into the chunk.
            return [
                found,
                "-e",
                (
                    'local chunk, err = loadfile(os.getenv("PB_LUA_CHECK_PATH")); '
                    "if not chunk then io.stderr:write(err); os.exit(1) end"
                ),
            ]
        # `luac5.1 -p` and `luajit -bl` both take the file as an argument
        # and neither executes it.
        return [found, *flags, str(path)]
    return None


def test_export_dir_has_lua_files() -> None:
    """Guard against this whole module silently passing because the glob
    stopped matching -- a renamed or moved `dcs-export/` would otherwise
    turn both tests below into no-ops."""
    assert _LUA_FILES, f"no .lua files found under {_EXPORT_DIR}"


@pytest.mark.parametrize("path", _LUA_FILES, ids=lambda p: p.name)
def test_no_nested_long_bracket_in_block_comment(path: Path) -> None:
    """No `[[...]]` wiki link anywhere in a Lua file (see module
    docstring). Checked over the whole file rather than only inside
    comments: the form has no legitimate use in these scripts, and a
    whole-file rule cannot be defeated by a later edit moving the link."""
    source = path.read_text(encoding="utf-8")
    offenders = [
        (source[: match.start()].count("\n") + 1, match.group())
        for match in _WIKI_LINK_RE.finditer(source)
    ]
    assert not offenders, (
        f"{path.name}: Obsidian wiki link(s) in a Lua file "
        f"{offenders} -- Lua 5.1 does not nest long brackets, so this "
        f"breaks the whole script when it sits inside a "
        f"`{_BLOCK_COMMENT_OPEN}` header comment (2026-10-17 incident: "
        f"three Hooks failed to load and Petrovich saw nothing). "
        f"Write the ID in backticks instead, e.g. `BL-B73`."
    )


@pytest.mark.parametrize("path", _LUA_FILES, ids=lambda p: p.name)
def test_loads_as_lua(path: Path) -> None:
    """The file parses as Lua 5.1. Skipped where no 5.1 tool is installed
    -- the wikilink check above is the floor.

    **Parse, never execute.** These scripts call into DCS APIs (`lfs`,
    `socket`, `LoGetSelfData`) that do not exist here, so running one
    fails for reasons that have nothing to do with its syntax. The first
    version of this test named the file as a positional argument to the
    *interpreter*, which runs it, and duly reported 26 "syntax errors"
    that were all missing-DCS-API runtime errors. Every entry in
    `_PARSE_ONLY_TOOLS` is parse-only by construction."""
    command = _parse_command(path)
    if command is None:
        tools = ", ".join(tool for tool, _ in _PARSE_ONLY_TOOLS)
        pytest.skip(f"no Lua 5.1 tool on PATH (tried: {tools})")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PB_LUA_CHECK_PATH": str(path)},
    )
    assert result.returncode == 0, f"{path.name} is not valid Lua 5.1:\n{result.stderr}"
