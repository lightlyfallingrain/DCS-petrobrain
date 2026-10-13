---
name: project-as-of-sim-bump-on-every-hold
description: body-layer position_belief.py's "Hold-recovery timing" invariant requires PositionEstimate.as_of_sim to advance on every poll, hold included -- a new hold branch that returns an unmodified prior (bare identity) silently violates this even though nothing downstream currently reads as_of_sim.
metadata:
  type: project
---

`body-layer/src/belief/position_belief.py`'s module docstring states, in its own "Hold-recovery
timing" section (added after a real 2026-09-25 production regression where a *different*
`as_of_sim` mishandling made hold-recovery time scale as `1 / poll_interval_s`, ~47s becoming
~934s): `as_of_sim` is "bumped on every poll including a hold, since the belief is still the best
current answer even when unchanged." `clamp_to_detection_envelope`'s hold branch honours this —
it constructs a fresh `PositionEstimate` with `as_of_sim=fused.as_of_sim` even when it cannot
re-fuse.

A later guard added to the sibling `clamp_fold_displacement` (commit `3dfe922`, the NaN-safety
fix) returns bare `prior` on its hold path instead of a reconstructed estimate, so `as_of_sim`
stays stale. Probed directly: `prior.as_of_sim=0.0`, `fused.as_of_sim=1.0`, guard fires, result
carries `as_of_sim=0.0`. Not reachable today — `grep -rn "as_of_sim" src/` outside this one module
turns up no consumer — but it is the same invariant the project was already burned by once in this
exact file, now silently un-held by a guard whose own docstring justification ("this function has
no `observer`/`growth_rate_mps` to re-inflate `prior.covariance` with") only explains why it can't
touch `covariance`, not why it skips `as_of_sim`, which needs no growth rate at all (`fused.
as_of_sim` is already in scope as a parameter).

**How to apply:** whenever reviewing a new "hold the prior" branch anywhere in this module (or one
that reconstructs a `PositionEstimate`), check `as_of_sim` is bumped to the current poll's
timestamp even when nothing else about the estimate changes, and read the branch's own
justification for *what it does not do* (here: not re-inflating covariance) as scoped to exactly
that field, not a blanket excuse for leaving every field untouched. A hold that returns the input
object by bare identity is a tell: check whether it should instead construct a copy with just the
timestamp advanced.
