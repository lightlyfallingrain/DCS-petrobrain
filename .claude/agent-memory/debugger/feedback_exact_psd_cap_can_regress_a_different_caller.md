---
name: exact-psd-cap-can-regress-a-different-caller
description: fixing an indefinite-covariance bug by capping a cross-term at the exact PSD boundary can regress an unrelated caller that feeds the result into a matrix inverse (Kalman-style gain) -- combine the exact cap with the existing heuristic cap via min(), don't replace it
metadata:
  type: feedback
---

**When a covariance cross-term's cap is replaced with the exact closed-form PSD boundary (not
widened, the exact boundary), check every caller that uses the result's *inverse* in a gain
computation, not just the caller the bug was reported against.** A cap that only needs to prevent
`det(S) < 0` for a Mahalanobis *test* (gate) can be mathematically correct and still regress a
*fusion* caller (Bar-Shalom-Campo update, `gain = (P_est - C) @ S^-1`) that is numerically fragile
near `det(S) == 0`, even though the fused result stays nominally valid (positive trace/det) — the
fused covariance can come out *larger* than a naive "hold the prior" fallback, which a determinant/
trace guard never catches because it only rejects outright-negative results.

**Why, concretely (`plans/same-optic-gate-indefinite/debug.md`, body-layer, `BL-B108`):**
`correlated_innovation`'s `S = (P_est + P_look) - (C + C^T)` had a cross-term cap
(`min(var_prior_along, var_look_along)`, a per-axis heuristic) that only applied for the fold
(`for_fusion=True`), never the gate — the gate's uncapped `S` could go genuinely indefinite
(negative determinant, not just small), the measured bug. Replacing the per-axis cap outright with
the exact PSD boundary fixed the gate but broke an unrelated, previously-green repeated-fuse test
(`test_stage0a_armour_growth_bounded_by_prior_inflation_and_reaches_naked_grade_by_sixth_fuse`): the
fold's own fused covariance grew 14% past the prior's own inflated value at one fuse step, because
pushing `c_down` to exactly where `det(S)=0` drives `S^-1` toward its own singularity, and the gain
formula amplifies that into a worse (not better) fused result.

**How to apply:**
- Derive the exact cap when the bug needs it (don't settle for widening an existing floor — that
  was explicitly out of scope here too), but **combine it with the existing heuristic cap via
  `min()`, keep both**, rather than replacing the heuristic. The heuristic, however approximate,
  was already proven stable for the caller(s) it was tuned for; the exact cap only needs to bind
  where the heuristic alone was insufficient.
- To isolate whether a changed test result is caused by your production fix or by a test-harness
  change made in the same pass: run the *exact same* test helper function against both the
  unmodified upstream `src` and your modified `src` side by side (careful with `sys.path` ordering —
  a namespace-package directory without `__init__.py` does **not** shadow a regular package found
  later on `sys.path`; copy the whole package tree, including `__init__.py`, to get a real override).
- See also [[noise-field-sweeps-need-an-ensemble]] and
  [[harness-resampling-fix-can-falsify-an-existing-guarantee]] — the broader family of "a fence
  measured under one artifact can move, in either direction, once the artifact is fixed" lessons
  this one belongs to. This one's new angle: the artifact was in *production* code, not the test
  harness, and it moved a test-only diagnostic stand-in (`test_expected_area_trigger.py`'s
  `_as_if_gate`) that was unknowingly relying on the same bug for its own discriminating power.
