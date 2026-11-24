---
name: toy-plant-bound-tests-dont-prove-sign
description: A toy-plant stability/bound test can pass under a flipped feed-forward sign if a P-term dominates the loop — mutate with a large gain, not just a sign flip, to find the real failure mode.
metadata:
  type: project
---

On `feature/bl16-lift-vector-law`'s LV-1 amendment fix pass (review-lv1-amendment.md re-review,
2026-11-24), `TestAmendmentProductionValuesTogether`'s toy plant couples collective-rate torque
into a simulated slip ball and bounds `max_abs_ball`/`max_abs_pedal`. Mutation-testing with a
**small sign flip** on the production torque feed-forward term (`flight_control.lua`'s `d_t_y =
d_t_y + k_pedal_from_collective_rate * u_c_rate * rotor_dir`) did **not** fail the test — the
ball's own proportional feedback term (`k_ball_pedal_p * (ball - ball_centre)`) dominates the toy
plant's stability regardless of the feed-forward's sign; a wrong-signed feed-forward only shifts
the equilibrium the P-loop settles on (bounded, non-zero), it does not destabilize the loop.
Mutating with a **large, flipped gain** (`-20.0` in place of the production `0.6`) did fail it —
that is the actual failure mode this class of test can catch.

**Why:** a toy-plant test built to catch "does this configuration blow up" is not automatically a
test that proves a feed-forward term's sign — those are different claims, and a P-term elsewhere in
the same loop can mask a sign error entirely. Sign correctness has to be hand-verified against the
law's own other terms (as the base `review-lv1.md`/`review-lv1-amendment.md` passes did, "Sign
conventions hold"), not assumed because a bound test passes.

**How to apply:** when reviewing a toy-plant stability/bound test over a control law with more than
one feedback path, mutate with (a) a small sign flip and (b) a large gain/flip, separately, before
calling the test "verified" — (a) alone can give a false sense that sign correctness is covered
when it is not. State explicitly, in the review, which claim the test does and does not cover.
