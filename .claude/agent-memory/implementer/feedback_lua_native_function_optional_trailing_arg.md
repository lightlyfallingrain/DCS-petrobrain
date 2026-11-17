---
name: feedback-lua-native-function-optional-trailing-arg
description: a Lua call to a Python-backed native function does not pad omitted trailing arguments with nil the way a Lua-defined function's formal parameters do -- an "optional trailing parameter" wrapper must accept both len(args) shrinking and an explicit nil
metadata:
  type: feedback
---

When a Python function exposed to Lua (via lupa, `*lua_args: object`-style) needs an optional
trailing parameter — `effector.write(name, value, says)` where `says` may be omitted (`[[BL-17]]`
D20, `plans/speech-rules/plan.md` Stage 3d) — two call shapes both need to work and they are not
the same code path:

1. `effector.write("x", "on")` — Lua passes exactly 2 values; the Python wrapper's `*lua_args`
   tuple has length 2.
2. `effector.write("x", "on", nil)` — Lua passes exactly 3 values, the third a real `None` once
   lupa converts it.

**Lua only pads missing arguments with `nil` for a *Lua-defined* function's own formal
parameters** (`function f(a, b, c) ... end` called as `f(1, 2)` makes `c` a local `nil` inside the
function body). A Python callable registered as a global is seen from Lua as a native/vararg-style
function, and lupa passes through exactly the arguments present at the call site — nothing pads
it. So a wrapper that only checks `len(lua_args) == len(action.params)` rejects case 1 outright,
and a wrapper that only checks "is this value `None`" without first checking it was *supplied*
handles case 2 but not case 1.

**Fix, generalizable:** make the arity check a range (`required <= len(lua_args) <= len(params)`,
where `required` is the count of non-optional parameters), treat an explicit `None` on a
declared-optional parameter the same as a validated value (not a type-check failure), and after
the per-parameter zip loop, fill every parameter past `len(lua_args)` with `None` explicitly —
`zip` silently stops at the shorter sequence, so parameters beyond `len(lua_args)` are never
visited by the loop at all and must be filled separately.

**How to apply:** whenever a Lua-callable Python action/tool gains an optional trailing
parameter, write one test for "omitted from the call" and, if literal `nil` is plausible in real
rule-author usage, one for "passed explicitly as `nil`" too — they exercise genuinely different
code paths in the wrapper (an omitted arg never reaches the per-parameter loop; an explicit `nil`
does and must be special-cased there).
