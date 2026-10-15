---
name: lua-dostring-in-snippet-must-be-self-contained
description: A Hook-local Lua function is invisible to a net.dostring_in("scripting", ...) snippet string -- helpers used inside it must be defined inside the snippet itself
metadata:
  type: feedback
---

When extending one of this project's mission-telemetry/F10-command Hook scripts
(`aircraft-layer/dcs-export/petrobrain-*-hook.lua`), any helper a `net.dostring_in("scripting",
CODE_STRING)` snippet needs must be defined **inside `CODE_STRING` itself**, never as a Lua
function in the Hook's own surrounding file.

**Why:** `CODE_STRING` executes in DCS's separate mission-scripting Lua state, which shares no
scope with the Hook's own state -- that is the whole reason the project calls across that boundary
with `net.dostring_in` rather than a plain function call in the first place
(`petrobrain-f10-commands-hook.lua`'s own header: snippets are "exactly two fixed literal
snippets, never built from runtime input," and self-contained for the same reason).

**What it looks like when got wrong:** writing `local function lifeFields(obj) ... end` as an
ordinary Hook-local function, then calling `lifeFields(unit)` from inside the `[[ ... ]]`
`VELOCITY_CODE` string. This compiles, and is **silently wrong at runtime** -- `lifeFields` is
`nil` inside the scripting state, so the call either errors inside the `pcall`-wrapped poll (caught
and logged as a generic "poll failed") or, if the call site isn't itself guarded, breaks the whole
snippet. There is no static check that would catch this; it only surfaces on a live DCS sortie,
and even then reads as "a weird poll failure" rather than "I called a function that doesn't
exist here."

**How to apply:** before writing or reviewing an edit to one of these Hook scripts, check whether
any new helper is referenced from inside a `[[ ... ]]` string that is later passed to
`net.dostring_in`. If so, move the helper's definition inside that string. Caught this on
`plans/emitter-visibility/plan.md` (`AC-B7`) by re-reading `petrobrain-f10-commands-hook.lua`'s own
header before deploying, not by any test -- there is no Lua test harness for these scripts in this
repo.
