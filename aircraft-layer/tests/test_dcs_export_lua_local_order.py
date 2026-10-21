"""No `dcs-export/*.lua` file may read one of its own locals as a global.

**What happened, twice.** In Lua a `local` referenced *above* its
declaration is not an upvalue: it compiles as a global lookup, which is nil
at call time. The syntax is valid, so `luac -p` and
`test_dcs_export_lua_syntax.py` pass it.

- `push_ptt_state` once sat above `safe_call`; the trigger never published
  a line (see that function's comment in `Export.lua`).
- `push_slew_trace` (BL-B66 Stage 4b) sat above `safe_call` too. On the first
  sortie with `SLEW_DEBUG` on, 2026-10-21, every frame raised
  `attempt to call global 'safe_call' (a nil value)`, and the error aborted
  the rest of `LuaExportAfterNextFrame` -- all telemetry export with it.

**The check.** `luac5.1 -l -p` lists every `GETGLOBAL`. Any global it reads
whose name the same file also declares as a `local` is this bug: a
deliberate global would not share a name with a local. No allow-list, so
nothing has to be kept in sync when a file grows a new helper.

Skips without `luac5.1` -- only 5.1's bytecode listing is accepted, for the
reason `test_dcs_export_lua_syntax.py` gives for parse checks.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_EXPORT_DIR = Path(__file__).resolve().parent.parent / "dcs-export"
_LUA_FILES = sorted(_EXPORT_DIR.glob("*.lua"))

#: `local function name(` and `local name =` / `local a, b =` at any indent.
_LOCAL_DECL_RE = re.compile(
    r"^\s*local\s+(?:function\s+([A-Za-z_]\w*)|([A-Za-z_][\w\s,]*?)\s*(?:=|$))",
    re.MULTILINE,
)

#: `GETGLOBAL 	0 -1	; safe_call` in `luac -l` output.
_GETGLOBAL_RE = re.compile(r"\bGETGLOBAL\b.*;\s*([A-Za-z_]\w*)\s*$", re.MULTILINE)


def _declared_locals(source: str) -> set[str]:
    names: set[str] = set()
    for fn_name, var_list in _LOCAL_DECL_RE.findall(source):
        if fn_name:
            names.add(fn_name)
        else:
            names.update(n.strip() for n in var_list.split(",") if n.strip())
    return names


def test_local_declaration_parser_sees_both_forms() -> None:
    src = "local function safe_call(fn)\nend\nlocal a, b = 1, 2\n  local c\n"
    assert _declared_locals(src) == {"safe_call", "a", "b", "c"}


@pytest.mark.parametrize("path", _LUA_FILES, ids=lambda p: p.name)
def test_no_local_read_as_global(path: Path) -> None:
    luac = shutil.which("luac5.1")
    if luac is None:
        pytest.skip("luac5.1 not installed")
    listing = subprocess.run(
        [luac, "-l", "-p", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    leaked = set(_GETGLOBAL_RE.findall(listing)) & _declared_locals(
        path.read_text(encoding="utf-8")
    )
    assert not leaked, (
        f"{path.name} reads {sorted(leaked)} as global(s) but also declares "
        "them local -- a use above the declaration. Move the caller below it."
    )
