---
name: project_nan_infinity_int_conversion_at_lua_action_boundary
description: Same int(x)-on-NaN/Inf gap as [[project_nan_infinity_int_conversion_at_lan_boundary]], found a third time at a non-LAN boundary -- rules/engine.py's action-argument validator and its digits() Lua global, BL-17 Stages 0/1b/2.
metadata:
  type: project
---

Third instance of the `int(x)` on an `isinstance(x, int | float)`-checked value gap
([[project_nan_infinity_int_conversion_at_lan_boundary]] has the first two, both at the
aircraft-layer<->body-layer LAN-HTTP boundary). This one is **not** a LAN boundary at all — it's
the Lua->Python boundary `rules/engine.py` builds for `[[BL-17]]`'s rule engine
(`plans/speech-rules/plan.md`), found in that feature's Mode 2 deep analysis
(`plans/speech-rules/security-stage0-2.md`, Required Fix 1). Worth keeping as its own entry because
the *source* of the untrusted/accident-prone value generalizes past "wire boundary": any boundary
where a value this codebase did not fully construct itself gets `int()`-converted is the same risk,
whether that value arrived over HTTP/JSON or out of a sandboxed Lua VM.

**Two call sites, both in `body-layer/src/rules/engine.py`**:

- `_make_action_wrapper`'s `wrapper` (~line 192): validates `isinstance(value, bool) or not
  isinstance(value, (int, float))` before `int(value)`, same shape as the LAN-boundary cases —
  missing the `math.isfinite` guard for the `float` branch. A Lua rule reaching this needs only
  ordinary `/` division (`0/0` -> `nan`, `1/0` -> `inf`), no stdlib access, to trip it.
- The `digits` lambda in `_make_env_builder` (~line 257): `lambda n: CrewConsole._digit_readback(
  int(n))` — **zero** validation, not even the type check the row above has. Reachable even more
  easily: any `WordSetElement` slot value is a Lua string by construction (e.g. `s.direction`,
  `"left"`/`"right"`), so `digits(s.direction)` — an ordinary mistake, not an attack — hits
  `int("left")` -> `ValueError` directly.

**Why this matters more here than the two LAN-boundary instances**: a bare Python exception raised
inside a Python callable invoked *from* Lua (via lupa) propagates out of the Lua call **as
itself** — confirmed empirically against the real `lupa==2.8` package, mirroring this function's
shape — not as `lupa.lua54.LuaError`. Every layer of this engine's own error handling
(`sandbox.run_with_budget`'s `except lua54.LuaError`, `engine.run_rule`'s `except (RuleRuntimeError,
RuleBudgetExceeded)`) is written to catch Lua errors specifically, so this exception sails past
all of it. Two consequences, traced through `body.py`: on the crew-text REPL thread
(`_run_crew_text_repl`, the **main thread**, unconditional since `BL-B96`, no broad `except`) it
**crashes the whole process**; on the poll thread it is caught by that loop's own blanket
`except Exception` (survives), but bypasses the rule engine's own documented D6 rollback contract
entirely — the pilot gets silence instead of the designed "action file error" callout, and the
rest of that poll tick's own processing is abandoned too (the exception aborts mid-tick, not just
the command).

**Not reachable by anything shipped in Stages 0/1b/2** — the one rule (`turn_heading_relative`)
only ever passes a bounded, negated int (`1..359`/`-359..-1`) and never calls `digits`. Flagged and
required-fixed anyway because the surface (`_make_action_wrapper`, `digits`) is explicitly the
generic validator for *every* future rule-callable action (`[[BL-B95]]`'s own widening), and the
later BL-17 porting stages are what will actually exercise it.

**Check for this whenever reviewing a new Lua-callable surface in this codebase** (any future
action namespace, any new Lua global `engine.py`/a sibling module exposes), the same way
[[project_nan_infinity_int_conversion_at_lan_boundary]] says to check a new JSON wire field: an
`isinstance` type check alone is not sufficient before `int()`; also require `math.isfinite` for
the float branch, or catch `(ValueError, OverflowError, TypeError)` around the conversion and
degrade to the surface's own existing graceful-failure shape (`{"ok": False}` for an action,
`render_unable(None).text` for a `say`-bound value) rather than letting it raise.
