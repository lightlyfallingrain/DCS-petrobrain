# Feedback control law design

- **A stopping-distance/stopping-height formula needs the channel's actual deceleration
  capability as its divisor, not the channel's velocity ceiling.** `law_init_at_take`'s altitude
  takeover goal used `h + w*|w|/(2*A_v)` with `A_v` wrongly bound to `max_climb_vs_mps` (the
  vertical-speed *ceiling*, 5.0) instead of `ALT_ACCEL_CAP_MPS2` (the channel's actual
  *deceleration* capability, 1.0). The wrong divisor under-stated the stopping distance, so the
  computed goal asked for more deceleration than the channel could deliver, and a toy-plant test
  run against the real accel-capped shaper overshot the wrong goal by several metres before
  settling — the exact "reversal" defect the formula exists to prevent, caught only by actually
  running the shaper against a toy plant rather than checking the formula by eye. General shape:
  a `v^2 / (2a)` stopping formula's `a` is always "how fast can this channel actually stop,"
  never "how fast is this channel allowed to go" — the two constants often sit right next to each
  other in a limits table and are easy to swap without either one looking obviously wrong (BL-16
  mode 1, Stage M2, `plans/flight-control/implementation.md`).

- **A fixed-gain critically-damped shaper (`a_ref = omega^2*err - 2*zeta*omega*v`) cannot
  generally guarantee zero overshoot against a velocity-dependent target, even with the right
  divisor.** The stopping-height goal itself scales with `v^2` (the square of the rate at
  takeover), but the one `omega` that exactly cancels overshoot for a *given* initial velocity
  scales with `1/v` — so a single fixed `omega` cannot zero the overshoot across every rate the
  aircraft might be moving at when the takeover happens. This is not a bug to fix by picking a
  "correct" gain; it is a property of using one fixed natural frequency against a family of
  initial conditions whose required frequency varies. The practical response is to pick the gain
  for acceptable overshoot across the real operating range (and accept "overshoot stays inside
  the band" as the pass criterion, not "never reverses"), or move to a velocity-scaled gain/target
  if a tighter guarantee is actually needed — a design change, not a tuning pass (BL-16 mode 1,
  Stage M2, `plans/flight-control/implementation.md`, `review-m2.md`'s own counterfactual).

- **Raising a rate ceiling does not raise the rate a critically-damped shaper actually reaches,
  once the ceiling already exceeds the shaper's own natural peak.** The heading-mode branch's
  achieved turn rate for a step heading error `E` peaks at roughly `E*omega/e` (its own
  `omega = OMEGA_HEADING`, an unmeasured placeholder), independent of how high the commanded rate
  ceiling is set above that peak — the mode-1 break batch raised `turn_rate_deg_s` to 40°/s
  expecting steeper banks and got the shaper's own lower natural peak instead, landing bank well
  below the plan's worked figures (measured ~43°/~54° vs. a predicted ~71°/~76° at 150/220 km/h).
  The ceiling only matters once the shaper's gain is high enough to actually reach it; tuning the
  ceiling and tuning the gain are two different knobs, and this project's break mechanism had only
  ever exercised the first one (BL-16 mode-1 batch, `plans/flight-control/plan.md` Decision 27,
  `implementation.md` Departure 3, `review-mode1-batch.md`).

- **Removing an output clamp (a bank limit) also removes the free anti-windup that clamp was
  incidentally providing.** `phi_i`'s integrator had no dedicated anti-windup of its own — it
  stayed bounded only because `max_bank_deg`'s clamp kept `phi_d` (and so the error driving the
  integrator) from growing unbounded. Deleting the bank clamp for an unrelated reason (F-M1: "no
  standing bank limit in mode 1") exposed integrator windup that had been dormant the whole time,
  not introduced by the deletion — a reminder that removing a limit written for one purpose can
  quietly remove a side-effect the system was depending on for another (BL-16 mode-1 batch,
  `plan.md`'s own Risks, `implementation.md` Departure 3).
