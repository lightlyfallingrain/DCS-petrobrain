---
name: numerical-fix-can-leave-rejection-rate-unchanged
description: fixing a near-singular/floor-clamped covariance's magnitude does not necessarily fix the defect that near-singularity was blamed for -- measure the rejection COUNT before and after, not just whether the magnitude stopped exploding
metadata:
  type: feedback
---

When a gate/test statistic explodes to an absurd magnitude (billions) because its own covariance
`S` sits near `det(S)==0` and a determinant floor clamps the inverse, the natural read is "this
near-singularity is causing the over-rejection." **Check this by counting, not by inspecting
magnitude.** On `plans/same-optic-gate-indefinite/debug.md`'s second pass
(`belief/position_belief.py`'s `correlated_innovation`): adding a safety margin to
`_max_c_down_for_psd` so `S` never gets closer than `_MIN_S_DETERMINANT_RATIO * trace(S)^2` to
singular eliminated every near-singular trial (0% afterward, from ~4-6%) and dropped the
Mahalanobis magnitude from billions to tens of thousands — but **the overall rejection count was
bit-for-bit identical before and after** (same 225/2000 trials in a measured cell). Those trials
were already going to clear the rejection threshold at a finite, merely-large value; the
catastrophic magnitude was cosmetic on top of an already-real rejection, not its cause.

**How to apply:** after any fix to a numerically-fragile covariance/precision computation, compare
the *count* of affected outcomes (gate accepts/rejects, test passes/fails) before and after, not
just whether the pathological magnitude disappeared. The fix can be entirely correct and worth
keeping (this one protects a *different* caller's gain computation from the same fragile regime,
per [[exact-psd-cap-can-regress-a-different-caller]]) while still not explaining the behavioural
symptom that motivated looking at it in the first place.

**Companion lesson, same pass:** before crediting a numerical-stability fix with a behavioural
improvement, re-run the actual rate-measuring tool (not just the calibration diagnostic) and
compare its aggregate numbers to the pre-fix baseline. Here, re-running
`measure_same_group_fold.py` after the fix showed fold rates statistically unchanged from the
pre-fix table — confirming the "doesn't move the rate" finding independently of the Mahalanobis
count comparison above.

**Also confirmed in the same pass, worth recording since it is counter-intuitive:** when a
cross-term `C`'s direction is built from a *reported* (noisy) bearing rather than the *true*
bearing the underlying correlated field actually lives along, this is not automatically the
source of a shape mismatch between the model covariance and the empirical one. A direct
ground-truth probe (rebuild `C`'s axis from true geometry, keep every declared sigma unchanged,
re-measure) made the rejection rate *worse*, not better, on two of three cells tested. Don't
assume an axis-alignment theory without measuring it against a ground-truth variant — the
declared/reported-quantity version can already be the better-calibrated one.
