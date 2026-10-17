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
_WIKI_LINK_RE = re.compile(r"\[\[[A-Za-z][\w-]*\]\]")


def _lua51() -> str | None:
    """A Lua 5.1-compatible interpreter, or `None`. `luajit` implements
    5.1's syntax (including its long-bracket rule) and is what reproduced
    the DCS failure locally; `lua5.1` is the obvious alternative where it
    is packaged separately."""
    for name in ("luajit", "lua5.1"):
        found = shutil.which(name)
        if found is not None:
            return found
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
    """The file parses as Lua 5.1. Skipped where no 5.1-compatible
    interpreter is installed -- the check above is the floor."""
    interpreter = _lua51()
    if interpreter is None:
        pytest.skip("no Lua 5.1-compatible interpreter (luajit / lua5.1) on PATH")
    # `loadfile` parses without executing -- these scripts call into DCS
    # APIs (`lfs`, `socket`, `LoGetSelfData`) that do not exist here, so
    # running them is not an option. The whole check must stay inside
    # `-e`: naming the file as a positional argument makes the
    # interpreter *run* it, which is how the first version of this test
    # reported 26 "syntax errors" that were all missing-DCS-API runtime
    # errors. The path travels by environment variable rather than being
    # spliced into the chunk, so no path can quote its way out of it.
    result = subprocess.run(
        [
            interpreter,
            "-e",
            (
                'local chunk, err = loadfile(os.getenv("PB_LUA_CHECK_PATH")); '
                "if not chunk then io.stderr:write(err); os.exit(1) end"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PB_LUA_CHECK_PATH": str(path)},
    )
    assert result.returncode == 0, f"{path.name} is not valid Lua 5.1:\n{result.stderr}"
