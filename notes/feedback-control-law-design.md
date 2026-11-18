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
