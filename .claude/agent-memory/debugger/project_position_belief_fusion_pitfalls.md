---
name: position-belief-fusion-pitfalls
description: Two numerical pitfalls in belief/position_belief.py's 2x2 covariance fusion, found fixing the runaway-range defect
metadata:
  type: project
---

`belief/position_belief.py`'s `fold_position` (information-form 2x2 covariance fusion) has two
numerical traps beyond the runaway-mean defect itself (fixed in `plans/position-belief-runaway/`):

1. **Bearing separation alone cannot guard ill-conditioning.** Near-parallel look bearings are only
   dangerous when the looks *disagree*; a repeated look from the same bearing (residual zero) must
   still tighten the estimate via ordinary averaging. A bearing-only guard breaks that case (caught
   live by `tests/test_optic_policy.py`'s pre-existing calibration test). The right test is a
   residual/Mahalanobis sanity check on the *fused mean itself* against each input's own individual
   covariance (not the sum) — see `FUSION_SANITY_SIGMA` in `position_belief.py`.

2. **`Covariance2D`'s determinant floor was scaled for covariance determinants (~1e9), not
   information-matrix determinants — fixed 2026-09-25, see [[project_covariance2d_determinant_floor_scale]].**
   Originally flagged here as a real, pre-existing, deferred latent bug (out of the runaway-range
   fix's own scope); a review of that fix (`plans/position-belief-runaway/review.md`) established
   it was reachable at ordinary naked-eye ranges (beyond ~2.7km, not an exotic corner) and was
   corrupting the brand-new `FUSION_SANITY_SIGMA` guard's own correctness, so it became a required
   fix rather than a backlog item. `_MIN_DETERMINANT` (absolute) is now `_MIN_DETERMINANT_RATIO`
   (relative to each matrix's own `trace**2`) plus a tiny absolute backstop for the fully-degenerate
   `trace == 0` case — see the linked memory for the fix pattern (`determinant / trace^2` is
   scale-invariant under `.inverse()`), reusable anywhere else a 2x2 SPD matrix gets inverted at
   more than one scale.

**Also confirmed:** `association_over_time.passes_gate`'s existing 3-sigma spatial gate is *not*
broken — a single big near-parallel disagreement (the kind used for a clean unit-level repro) is
rejected by that gate before ever reaching `fold_position` in production. The real live-flight
mechanism was a *slow drift* — many small, individually gate-passing steps whose bias compounds —
which is what actually needed the new `clamp_to_detection_envelope` safety net (not just the
per-step ill-conditioning guard).
