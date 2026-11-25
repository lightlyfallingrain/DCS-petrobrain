---
name: shaper-amplitude-saturation-windup
description: Raising a critically-damped 2nd-order reference generator's bandwidth without an anti-windup ceiling reintroduces overshoot once its own acceleration saturates the cap
metadata:
  type: feedback
---

BL-16 LV-1's speed shaper (`flight_control.lua` step 1, speed) is a textbook critically-damped
second-order reference generator (`a_ref = omega^2*err - 2*zeta*omega*rate`, then integrated twice,
with amplitude caps at each stage). This family is provably overshoot-free **only while
unsaturated**. The moment `omega` is raised enough that the unsaturated demand exceeds the
amplitude cap for an extended stretch, the system winds up (the integrated "rate" state grows past
what the critically-damped feedback — sized for the unsaturated case — can brake back to zero in
time) and overshoots/hunts. This is NOT specific to this shaper; it is a known defect class in any
rate/acceleration-limited reference generator (motion-control literature calls the fix "trapezoidal
velocity profile" / "S-curve with braking-distance governor").

**The fix that actually works, confirmed by toy-plant sweep**: add a continuous ceiling on the
integrated rate state, `rate_cap = min(existing_rate_limit, sqrt(2*accel_cap*|remaining_error|))`.
This never lets the rate exceed what the accel cap could brake to zero by the time the error
reaches zero — a continuous function of distance remaining, so there's no discrete mode switch to
chatter across (a literal bang-bang/trapezoidal switch between "accelerate at cap" and "the
critically-damped formula" DID chatter badly in testing — don't do that).

**Why:** this project's root `CLAUDE.md` keeps `omega_heading`/`omega_alt`/`omega_speed` as three
near-identical shaper instances (B, "kept" across LV-1 amendments). Any future pass that raises one
of their bandwidths without this same ceiling will likely hit the identical windup — check for an
amplitude-saturation ceiling before raising any of these, not just this one.

**How to apply:** when a bug report says "shaper/reference too slow" and the obvious fix is "raise
the bandwidth," always toy-plant-sweep the bandwidth first — the windup only shows up once the
unsaturated peak exceeds the cap, which a slow sweep from the current (safe) value will reveal as a
sudden jump in oscillation count, not a gradual one.

See [[shaper-anti-windup-bl16]] (if filed) / `plans/flight-lift-vector/debug-2026-11-25.md` for the
worked numbers.
