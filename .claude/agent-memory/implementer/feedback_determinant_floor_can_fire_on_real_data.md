---
name: determinant-floor-can-fire-on-real-data
description: belief.position_belief.Covariance2D.inverse()'s determinant floor, documented as never firing on real data, fires on ~7% of same-optic (u_u) gate evaluations -- when a floor/clamp comment makes an "never happens" claim, measure it before trusting it, especially for a correlated/subtracted covariance that can go indefinite.
metadata:
  type: feedback
---

**A comment asserting a numerical floor "never fires on real data" is a claim, not a fact — when
the matrix it guards is built by subtraction (not just addition), measure whether it fires before
trusting the comment.** `belief.position_belief.Covariance2D.inverse()` floors `S`'s determinant
at `max(1e-9 * trace(S)**2, 1e-300)`; the comment says this floor sits "orders of magnitude above
this floor, so it never fires on real data." Measured (`BL-B110`, 2026-11-09, "measure first" same-
optic fold task): on a same-optic (`u_u`), zero-growth, 2 km/4 s-gap cell, `n=300`, the real
(pre-floor) determinant of `belief.association_over_time.passes_gate`'s own `S =
correlated_innovation(...)` is **negative** (not merely small — the matrix is not positive
semi-definite at all) on **7.0%** of trials, 1.7% for `b_b`, 0% for cross-optic (`u_b`/`b_u`).

**Why it happens, and why it is same-optic-specific.** `correlated_innovation` computes
`S = P_est + P_look - (C + C^T)`, a *subtraction* of a correlation cross-term from a sum of two
covariances — unlike an ordinary sum, a subtraction has no structural guarantee of staying
positive-definite. The cross-term `C` is largest in magnitude exactly when both looks share one
optic (the correlation kernel assumes more shared stable error the more alike the two looks are),
so same-optic pairs are where `C` is most likely to overshoot `P_est + P_look` and flip the
determinant negative. Cross-optic pairs, where `C` is naturally smaller, never hit it in the cells
checked.

**What a negative-determinant floor-clamp actually does, and why it is worse than a merely-tiny
determinant.** The floor exists to stop division by exactly zero on a "genuinely degenerate"
matrix (one axis's variance at zero) — it was not designed for, and does not detect, the case
where the *unclamped* value is large and negative. `max(negative_large, floor)` picks the floor
every time, same as `max(tiny_positive, floor)` would, but the resulting "inverse" is not a valid
precision matrix for an indefinite input — in the measured cells its diagonal terms blew up to
`S.zz/floor`/`S.xx/floor` (tens of thousands against a trace of ~30 000 m²), producing Mahalanobis
values of `1e7`–`1e9` against a `9.0` threshold. The practical effect: on the trials where this
fires, the gate rejects *regardless of the actual offset size* — split by determinant sign on one
cell, positive-determinant trials folded 90.7% of the time, negative-determinant trials folded only
19.0%.

**How to apply:**
- When a floor/clamp guards a matrix built by *subtracting* a cross-term (not just summing
  variances), do not trust a "never fires" comment — compute the real, unclamped determinant
  across an ensemble and check its sign distribution, especially in the regime the cross-term is
  largest (here: same-optic pairs, where the correlation assumption is strongest).
- `max(value, floor)` conflates two different failure modes — "value is a tiny positive number"
  (the floor's intended case) and "value is large and negative" (an invalid matrix) — and produces
  a *different* kind of wrong answer for each (a loose-but-sane test vs. a pathologically strict
  one). If you are adding or reviewing a determinant/variance floor, consider whether the two cases
  need to be distinguished rather than collapsed into one `max()`.
- This was found by instrumenting individual non-fold trials with a throwaway probe script (not a
  formal proof), reading the actual intermediate numbers rather than reasoning about the formula
  from its docstring — the standard "reproduce the fix sketch, not just the defect" pattern
  ([[reproduce-the-fix-sketch-not-just-the-defect]]), applied to a measurement task rather than a
  fix.
- Related: [[noise-field-sweeps-need-an-ensemble]] (the broader "measure the ensemble, don't trust
  one draw or one comment" lesson this is a specific instance of),
  [[harness-resampling-fix-can-falsify-an-existing-guarantee]] (the same `BL-B110` thread, one step
  earlier).
