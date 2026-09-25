---
name: position-belief-runaway-required-fix-reviewed-approved
description: Re-review outcome for fix/position-belief-runaway's required fix (97d5c65), scale-relative Covariance2D determinant floor.
metadata:
  type: project
---

`fix/position-belief-runaway` was NEEDS-REVISION at `c1cba89` on one item:
`Covariance2D._MIN_DETERMINANT = 1e-9`, an absolute floor applied to both covariance-scale and
information-scale matrix inversions, reachable beyond ~2.7km of naked-eye range and corrupting
`fold_position`'s fused mean (a repeated identical 3km look wandered instead of holding).

The fix (`97d5c65`) replaced it with a scale-relative floor:
`max(_MIN_DETERMINANT_RATIO * trace**2, _MIN_DETERMINANT_ABSOLUTE)`, argued from
`det/trace^2 == ab/(a+b)^2` (a matrix's own eigenvalue ratio) being exactly invariant under
`.inverse()`.

**Re-review (2026-09-25) verified, by direct execution against isolated `git archive` snapshots
of both the pre-fix (`c1cba89`) and post-fix (`97d5c65`) commits** (not the reviewer's own
worktree — see [[feedback_worktree_main_based_pytest_pythonpath_trap]] for why that mattered
here specifically):

- The invariance claim, analytically (2x2 eigenvalue algebra) and numerically at 5 different
  bearings on the actual anisotropic naked-eye covariance — holds exactly, not just for the
  diagonal case.
- The chosen ratio (`1e-9`) has 7-8 orders of magnitude of margin against every real
  `naked_eye_sigma_m` anisotropy, and ~40x margin against a deliberately extreme synthetic 5000:1
  sigma ratio no real caller produces.
- The floor still catches genuine singularity (det=0 constructed matrix) and the fully-degenerate
  trace=0 case (caught by the separate absolute backstop) — both still finite, no inf/NaN.
- `test_optic_policy.py`'s Trap 1 test really does only assert `len(steps) == 1`, confirmed by
  reading the test body directly — no numeric intermediate dependency.
- Both new regression tests independently confirmed to fail against a clean pre-fix tree and
  pass against a clean post-fix tree.
- Full `ruff format/check` + `mypy --strict` + `pytest` re-run clean (1191/4 xfailed), matching
  the debug addendum.

The optional `Contact.last_seen_sim` bump-even-when-held item was left as a logged, explicit
decision (not silently dropped) in `plans/position-belief-runaway/debug.md`'s addendum — no
further action needed.

**Verdict: APPROVED**, branch as a whole. Full addendum:
`plans/position-belief-runaway/review.md` (2026-09-25 section).
