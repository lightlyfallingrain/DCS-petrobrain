---
name: lua-extract-function-for-loop-depth
description: aircraft-layer's _extract_lua_function test helper (test_sight_servo_lua.py pattern) only counts function/if/end as block openers, not for/while -- miscounts and truncates extraction of any Lua function containing a for or while loop
metadata:
  type: feedback
---

`aircraft-layer/tests/test_sight_servo_lua.py`'s `_extract_lua_function` helper (sliced
`local function NAME(...) ... end` out of `Export.lua` for execution against a real Lua
interpreter) tracks block depth with `re.compile(r"\b(function|if|end)\b")`. It never needed
`for`/`while` because none of that file's own extracted functions (`sight_world_to_body`,
`run_sight_servo`, etc.) contain a `for` loop.

**Why: `for ... do ... end` and `while ... do ... end` are both closed by `end` in Lua, so leaving
them out of the opener set underflows the depth counter** — extraction stops at the loop's own
closing `end`, silently truncating the function and producing a syntactically broken standalone
script (`'end' expected ... near '<eof>'` from the interpreter, not from the extractor itself,
which makes the failure confusing to diagnose from the error message alone).

**How to apply:** before reusing this extraction technique (it is duplicated per test module by
convention, not imported) on a new `Export.lua` function, check whether that function's body
contains a `for`/`while` loop. If it does, widen the token regex to
`r"\b(function|if|for|while|end)\b"` in your own copy of the helper — do not assume the existing
copies in other test files already handle this; as of 2026-10-29 `test_sight_servo_lua.py`'s copy
is still the narrow version and would hit the same bug if any of its own extracted functions later
grows a loop. `repeat ... until` blocks are not in this file's style and are not handled by either
version.

Found implementing `BL-B67` Stage 4 (`push_payload_state`, which iterates `payload.Stations` with
a `for` loop) in `plans/bl-b67-atgm-run/plan.md`.
