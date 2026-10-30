---
name: lua51-60-upvalue-ceiling
description: Lua 5.1 caps each closure at 60 upvalues (outer locals it references) -- a large per-frame Export.lua function can already be at the limit, so "just add one more if-check" fails luac5.1 -p outright rather than misbehaving at runtime.
metadata:
  type: reference
---

Discovered live, 2026-10-30, while adding the `SIGHT_HANDS_OFF` hands-off switch
(`plans/9k113-hands-off-switch/implementation.md`, `aircraft-layer/dcs-export/Export.lua`).
`run_sight_servo` (the 9K113 sight servo's per-frame function) already references ~55-60 outer
`local`s/constants (every `sight_*` module-level variable plus every `GIMBAL_*`/`ASP17_FIELD_*`/
`MARK_*`/`KP`/`FF_GAIN`/etc. constant it reads). Adding one more reference inside it -- even a
single `if SIGHT_HANDS_OFF then return end` at the top -- pushed it to 61 and `luac5.1 -p` failed
with `function at line 1581 has more than 60 upvalues`.

**This is a hard Lua 5.1 VM limit (`LUAI_MAXUPVALUES = 60`), not a style warning.** The syntax
check (`luac5.1 -p`) catches it immediately and loudly -- it does not compile at all, so there is
no risk of silently shipping an over-budget closure. But it means the usual fix for "this function
needs to also check flag X" -- add a line referencing X inside it -- is unavailable once a
function is already near the ceiling, and large per-frame dispatcher functions in this codebase
(anything resembling `run_sight_servo`, built up over several plan iterations) are exactly the
shape that gets there.

**How to apply:** before adding a new upvalue reference to a large, long-lived Export.lua
function, check `luac5.1 -p` after the edit, not just before. If it fails with this message, the
fix is to factor the new check into a small *separate* function (few upvalues of its own) that
wraps the call to the large one -- e.g. `sight_servo_tick(t)` here: a 3-upvalue wrapper
(`SIGHT_HANDS_OFF`, `sight_mode`, `run_sight_servo`) that the caller (`LuaExportAfterNextFrame`)
calls instead of the large function directly, and which decides whether to call through at all.
This also keeps the large function's own extraction boundary in test files
(`_extract_lua_function`-style helpers) unaffected, since nothing inside its body changed.

See also [[extract-lua-function-comment-false-positive]] for a second, unrelated discovery made
while debugging this same change.
