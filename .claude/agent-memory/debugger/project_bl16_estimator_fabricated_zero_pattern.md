---
name: bl16-estimator-fabricated-zero-pattern
description: BL-16 LV-0 estimator bug class -- a ring/getter returning "no info yet" must never be read as "the value is 0", or it reads as a real discontinuity to whatever differentiates it next
metadata:
  type: project
---

Debug pass 2026-11-23 (`plans/flight-lift-vector/debug-2026-11-23.md`) found the same root pattern
three times in one estimator (`flight_control.lua`'s `est_sample`): a degenerate/unknown read
(`est_ring_slope`'s own `count<2`/`denom==0` guard returning `0.0`, or `LoGetSelfData` failing and
falling back to `pos_n/u/e = 0.0`) was treated downstream as a genuine measured value, and whatever
differentiated it next (the acceleration ring) read the jump from "real" to "fabricated 0" as a huge
transient -- 350-700 m/s^2 at mission start, 300-550 m/s^2 mid-flight from a duplicate-timestamp
degeneracy, and -13,000,000 m/s^2 once the aircraft was actually destroyed and `LoGetSelfData`
started failing against ~115s of real position history.

**The fix shape, reusable for the next getter-fails-sometimes case**: add an explicit "is this
frame's reading trustworthy" signal (`est_ring_primed`, `raw.pos_valid`) and, when it is false, hold
the estimator's own output at its last known value rather than overwrite it with the getter's
"safe" default. A held value, fed into the next derivative, reads as "nothing changed" (correct);
a fabricated zero reads as "it dropped to 0 instantly" (a spike).

**One failed first attempt worth remembering**: gating on "has the ring's window fully spanned
`window_s`" (not just `count>=2`) seemed like the stricter, more correct check, but it made the
mission-start warm-up *worse* -- holding at 0 for several more samples then snapping to the full
real value in one step, instead of the existing least-squares fit's gradual convergence from
`count==2` onward. Caught by a test that asserted the opposite before trusting the "stricter is
better" instinct. See [[bl16-mission1-handover-ack-pattern]] for the companion, non-estimator defect
found the same pass.
