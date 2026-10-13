---
name: feedback-verify-held-field-choice-against-caller-not-sibling
description: when a hold branch copies a sibling function's field-construction pattern (e.g. bump as_of_sim, hold fused_at_sim), trace the one real caller's own arithmetic to confirm the choice serves that caller too -- don't accept "matches the sibling" as sufficient on its own.
metadata:
  type: feedback
---

`clamp_fold_displacement`'s NaN-safety fix (`2a9a676`, closing `plans/bounded-fold-displacement/
review.md`'s required fixes) copied `clamp_to_detection_envelope`'s hold-branch field set:
`as_of_sim=fused.as_of_sim` (bumped), `fused_at_sim=prior.fused_at_sim` (held). The two functions
have different signatures (`clamp_fold_displacement` has no `observer`/`growth_rate_mps`, so it
cannot inflate `covariance` the way its sibling does), so "matches the sibling" alone does not
establish the field choice is right *here* — it could easily have been right for the wrong reason.

Verified instead by tracing the one real caller (`Contact.record`, `contacts.py`): `max_displacement_m
= growth_rate_mps * max(0.0, percept.t_sim - prior_position.fused_at_sim)`, computed from
`fused_at_sim` on the *pre-fold* position. Holding `fused_at_sim` at the prior's value (not bumping
it) means a run of consecutive holds keeps `fused_at_sim` anchored at the last genuine fuse, so the
bound keeps widening poll over poll — the "Hold-recovery timing" invariant's whole point. Bumping
`fused_at_sim` on a hold (the wrong field, easy to reach for since `clamp_to_detection_envelope`
also bumps `as_of_sim` right next to it) would have frozen the bound at its first-hold value,
reintroducing the exact recovery-time defect `plans/position-belief-runaway/debug.md` fixed in this
function's sibling.

**How to apply:** when a fix's hold/guard branch is explicitly modeled on a sibling function
elsewhere in the same module, don't stop at "the field set matches." Find the one real caller that
consumes each held/bumped field downstream, and check the arithmetic that consumes it still behaves
correctly across a *run* of consecutive holds, not just one. A single-hold test can pass with the
wrong field bumped; only the caller's own accumulation exposes it.
