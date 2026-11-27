---
name: toy-plant-root-cause-vs-test-profile
description: a reviewer-flagged "test profile doesn't match shipped gains" gap can hide a second, different root cause once the honest number is measured -- don't assume closing the profile gap also closes the behavioural gap
metadata:
  type: feedback
---

On BL-16 LV-1 debug-2026-11-27 round 2 (`fix/bl16-flight-epoch-bound`, building on
`review-debug-1127.md`'s NEEDS REVISION), the reviewer's required fix was "the committed
altitude-hold test runs against a stale, pre-amendment toy-plant profile; against shipped gains the
loss is -19.3 m, not the test's claimed -9.3 m, outside the test's own -15 m bound."

**The naive read of that required fix is "loosen the bound to -22 and move on."** Printing the
vertical-channel internals every frame (`a_u_d`/`a_u`/`e_u`/`u_c`/`u_c_i`) during the shipped-gain
run showed `u_c` frozen at an exact, unmoving value for ~9 s while `e_u` grew unopposed — a
*different* mechanism from the one Round 1 had just fixed (the unbounded speed-give rate bias).
Confirmed by a diagnostic mutation (relax the suspected guard, not committed): the loss dropped from
-19.3 m to -3.3 m, isolating `collective_rate_cap_near_blade_stall = 0.0` (Decision 30's retreating-
blade-stall freeze) as the actual remaining cause, unrelated to the bug Round 1 fixed.

**How to apply:** when a review's "wrong test profile" finding produces a larger-than-claimed number,
don't just widen the bound — trace *why* the real number is what it is, with per-frame
instrumentation on the actual law internals (not just the plant's I/O), before deciding whether the
gap is a new bug, a pre-existing and already-accepted design tradeoff (here: the project's own plan
doc had already said this guard class is "not a defect to engineer away," for a sibling guard), or
something the user needs to decide. The three are not interchangeable, and only instrumenting the
internals (not just min/max altitude deviation) told them apart. See [[project_bl16_decel_round2_findings]]
if present, and `plans/flight-lift-vector/debug-2026-11-27.md`'s "Round 2" section for the full trace.
