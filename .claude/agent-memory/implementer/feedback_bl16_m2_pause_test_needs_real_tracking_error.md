---
name: bl16_m2_pause_test_needs_a_real_tracking_error
description: a toy-plant counterfactual for "pause freezes the shaper" is a no-op unless there is a live tracking error at the moment of the pause
metadata:
  type: feedback
---

For BL-16's flight-control law (`aircraft-layer/dcs-export/Petrobrain/flight_control.lua`), at
`law_init_at_take` every reference starts exactly equal to its measured value (heading, altitude,
speed goals = captured state, zero error by construction, Decision 24's "bit-exact at take"). If a
mutation test calls `law_update` with a non-zero `dt` during what should be a frozen pause frame,
but the mock plant is otherwise static and no goal has been commanded since take, **every
integrator's derivative is mathematically zero** — an un-frozen `law_update` produces byte-identical
output to a correctly-frozen rewrite. The mutation is numerically a no-op in that exact scenario, so
a value-equality assertion added to catch it would pass under both the fixed code and the bug.

**Fix:** inject a goal command (e.g. a heading target that disagrees with the measured heading)
between the take and the "paused" frame under test, so there is a live tracking error for an
un-frozen law to move against. Confirmed empirically with `luajit`: with the goal mismatch, the
reviewer's exact mutation (`law_update(fc_law, 0.5, ...)` in the pause branch) moves the roll
command by ~0.57 (`0.199` → `0.771`), while the correctly-frozen code only wobbles by ±0.001. See
[[flight_control_lua_wobble_test_tolerance]] for the comparison tolerance this also needs.

This was found while fixing `review-m2.md`'s Required Fix 2 (BL-16 M2, `feature/bl16-raw-axes`,
`m2-fix`): the review's own counterfactual passed on the *old* assertion
(`written[2001] ~= nil`), but a naive strengthened assertion using the original driver (no goal
command, same static inputs as take) would also have passed under the bug — always counterfactual-
check a new assertion against the exact mutation it's meant to catch, not just against the fixed
code.
