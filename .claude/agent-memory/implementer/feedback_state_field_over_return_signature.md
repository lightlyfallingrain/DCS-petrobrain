---
name: state-field-over-return-signature
description: when a pure engine needs to report a new per-call output, add a field to its existing replace()-only state dataclass rather than widening the function's return type
metadata:
  type: feedback
---

When a pure, frequently-called function (`advance()`-style, called once per poll from dozens of
test sites) needs to start reporting a new piece of per-call output -- e.g. "which lines did this
call decide to speak" -- prefer adding a field to its existing `replace()`-only state dataclass
(reset to the call's own fresh value every call, e.g. `()` when nothing happened) over changing the
function's return type to a tuple.

**Why:** `belief.effector_engine.advance()` (`[[BL-B119]]`) needed to report completed-row speech
lines. Changing `advance(...) -> EffectorRunState` to `-> tuple[EffectorRunState, tuple[str, ...]]`
would have broken ~40 `state = advance(...)` call sites across `test_effector_engine.py` alone --
an "existing tests must be rewritten" situation the project's own escalation rules flag. Instead,
adding `spoken: tuple[str, ...] = ()` to `EffectorRunState` kept every existing test passing
unchanged (they just never read the new field), and the engine stayed pure (no I/O, still only
returns state). The plan itself explicitly invited this ("a `spoken: tuple[str, ...]` on
`EffectorRunState`, or a returned value" -- either was acceptable) and separately said "if you add
a field, mission reset (D11) must clear it like the others" -- which this project's `reset_for_new_
mission` pattern (`self.__init__(...)` re-run with a `field(default_factory=...)` default) already
covers for free, with zero extra reset code, as long as the field has a plain default like every
other field on that dataclass.

**How to apply:** before widening a pure function's return signature, check how many existing call
sites assign its current return value directly (`grep -c` the function name in the test file). If
it's more than a handful, and the state object is already a `replace()`-only dataclass with "one
construction site" discipline, a new transient-output field on that dataclass is almost always
cheaper and less risky than a tuple return -- and it composes with any existing mission-reset
mechanism automatically.
