---
name: project-nan-guard-must-cover-every-operand
description: a math.isfinite guard added to close a NaN finding must check every float that feeds the same arithmetic, not just the one named in the finding -- body-layer position_belief.py's clamp_fold_displacement guarded fused.x/fused.z but left max_displacement_m unguarded, reaching the identical NaN*0.0 corruption through scale instead of dx.
metadata:
  type: project
---

`clamp_fold_displacement` (`body-layer/src/belief/position_belief.py`) got an explicit
`math.isfinite` guard (commit `3dfe922`, closing `plans/bounded-fold-displacement/
security-review.md`'s finding) that checks `fused.x`/`fused.z` but not `max_displacement_m`, the
third float feeding the same `dx * scale` expression. Probed directly: `max_displacement_m=nan`
with a finite `fused`/`prior` still produces `x=nan` output — `displacement_m <= max_displacement_m`
is `False` for a NaN bound too, so `scale = max_displacement_m / displacement_m` inherits the NaN,
and `dx * scale == NaN`. Identical corruption, different operand. Low reachability today (the one
real caller resolves the bound from a table lookup that cannot currently produce NaN/inf), same
risk profile the security review already accepted for the original finding — but the fix's own
docstring claimed completeness ("by design, not by accident") without covering this case, and the
whole point of the round was to make the identity claim true rather than borrowed.

**How to apply:** when reviewing any guard added specifically to close a NaN/non-finite finding,
list every float operand that reaches the arithmetic the finding described, not just the one named
in the finding's own repro. Probe each one individually (`<value>=math.nan` with the others held
finite) rather than trusting the guard's own docstring to have enumerated them. This is the same
shape of check as `project_nan_comparison_incidental_guards.md` (security's memory, same module) —
that one is about guards that work by accident; this one is about guards that work by design but
only for a subset of the inputs that need them.

Related: `project_as_of_sim_bump_on_every_hold.md` — the same commit's hold branch also missed a
second, unrelated invariant (`as_of_sim` must advance on every poll including a hold) for a
different reason (the docstring's justification covered only `covariance`, not `as_of_sim`).
