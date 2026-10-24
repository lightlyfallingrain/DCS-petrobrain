"""`Export.lua`'s `MAX_WATCHED_ARGS`/`MAX_WATCHED_ARG_NUMBER` and its
Python twins (`aircraft-layer/src/schema/watched_args.py`) must stay
equal -- the bound is stated once per side (no shared import across the
Lua/Python boundary, per the plan's "no test checks the version pair
today; the comment above it says 'update both', and that is the kind of
rule that drifts"). This greps the Lua source rather than running an
interpreter, so it needs none."""

from __future__ import annotations

import re
from pathlib import Path

from schema.watched_args import MAX_WATCHED_ARG_NUMBER, MAX_WATCHED_ARGS

_EXPORT_LUA = Path(__file__).resolve().parent.parent / "dcs-export" / "Export.lua"


def _lua_constant(name: str) -> int:
    text = _EXPORT_LUA.read_text(encoding="utf-8")
    match = re.search(rf"^local {name} = (\d+)\s*$", text, re.MULTILINE)
    assert match is not None, f"{name} not found in Export.lua"
    return int(match.group(1))


def test_max_watched_args_matches() -> None:
    assert _lua_constant("MAX_WATCHED_ARGS") == MAX_WATCHED_ARGS


def test_max_watched_arg_number_matches() -> None:
    assert _lua_constant("MAX_WATCHED_ARG_NUMBER") == MAX_WATCHED_ARG_NUMBER
