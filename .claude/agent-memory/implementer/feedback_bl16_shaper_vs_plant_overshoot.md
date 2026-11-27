---
name: bl16-shaper-vs-plant-overshoot
description: BL-16 flight law -- "no overshoot" claims about a heading/rate shaper must say which model they're about (idealized r_ref/psi_ref vs the toy plant's own bank-lag), and an antipodal (180 deg) wrap test needs signed cumulative turn, not wrapped psi
metadata:
  type: feedback
---

When tuning `flight_control.lua`'s critically-damped (`zeta=1`) heading-rate shaper
(`a_ref = omega^2*err - 2*zeta*omega*r_ref`), "no overshoot" is true of the shaper's own internal
reference (`r_ref`/`psi_ref`) by construction, for ANY `omega`, independent of any rate/accel
ceiling -- confirmed numerically (pure Python simulation of the formula, no plant). It is NOT true
of the full closed-loop toy plant (`_BREAK_PLANT_DRIVER`-style, with a first-order bank lag on
`phi_d`) once the shaper is fast enough that the real bank can't reverse before the heading target
is crossed -- that overshoot grows with the shaper bandwidth and is a property of the plant's own
lag, not a defect in the shaper. Raising `break_omega_heading` LV-2 fix pass, 2026-11-27
(`plans/flight-lift-vector/implementation-lv2.md`, review-lv2.md required fix 1) from the shared
`omega_heading`=0.3 to a break-only 1.0 rad/s fixed the review's finding (cap never bound) but
introduced ~5-10 deg of real heading overshoot that the idealized math said would be zero.

**Why: a sweep (omega 0.3 to 1.2) showed overshoot scaling monotonically with omega in the real toy
plant while the idealized r_ref/psi_ref model stayed at exactly zero overshoot for every value
tested** -- so a report that says "no overshoot, confirmed" needs to say which model, or it is
misleading in exactly the direction that matters (a pilot will see the real, lagged response).

**How to apply**: when a plan or review says "keep zeta=1 so no overshoot," verify against BOTH the
idealized shaper state AND the closed-loop toy plant with lag before claiming either one holds; if
they disagree, report both numbers and flag the real-plant residual explicitly rather than letting
the idealized check stand in for the whole claim.

**Separate trap, same session**: measuring heading progress by tracking the wrapped `measured.
psi_deg` breaks for an exact-antipodal goal (a 180 deg break-away from any start heading) --
`law_wrap180(180)` deterministically resolves to -180, so the aircraft turns the "long way" through
359->270->181->180, and `psi - goal` reads the wraparound as a ~180 deg false "overshoot." Fix:
track the SIGNED cumulative turn (`sum(r*dt)`, never wrapped via `%360`) and compare its magnitude
against the target's magnitude instead.
