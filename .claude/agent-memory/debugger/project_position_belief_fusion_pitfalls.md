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

2. **`Covariance2D._MIN_DETERMINANT = 1e-9` is scaled for covariance determinants (~1e9), not
   information-matrix determinants.** Inverting a covariance twice (or summing two infos and
   inverting again) can legitimately produce a determinant as small as ~1e-10 — below the floor —
   silently corrupting the result (confirmed: `cov.inverse().inverse() != cov` for
   `sigma_cross_m=157.08, sigma_down_m=510.0`, the same pair `test_optic_policy.py` already uses,
   off by ~6.4x). This is a real, pre-existing, **unfixed** latent bug — not touched during the
   runaway-range fix (out of that defect's scope, no reported symptom tied to it, existing tests
   don't check exact numeric values there). Worth a dedicated debug/fix pass if a future symptom
   traces back to it — check the actual determinant magnitude before assuming a fusion result is
   trustworthy for any sigma pair much smaller than the naked-eye channel's own (60, 800).

**Also confirmed:** `association_over_time.passes_gate`'s existing 3-sigma spatial gate is *not*
broken — a single big near-parallel disagreement (the kind used for a clean unit-level repro) is
rejected by that gate before ever reaching `fold_position` in production. The real live-flight
mechanism was a *slow drift* — many small, individually gate-passing steps whose bias compounds —
which is what actually needed the new `clamp_to_detection_envelope` safety net (not just the
per-step ill-conditioning guard).
