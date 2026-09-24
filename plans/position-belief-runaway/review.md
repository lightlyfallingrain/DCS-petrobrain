### Review Summary

Branch `fix/position-belief-runaway`, single commit `b5b79b8`, branched from `main` at `a04eec8`.

The debugger's correction of the orchestrator's own hypothesis holds up: I reverted the
worktree to pre-fix source (`a04eec8`, confirmed no `FUSION_SANITY_SIGMA` present), copied in
only the new `test_slow_directional_drift_never_reports_a_range_beyond_the_detection_cap` test,
and ran it against the unmodified pre-fix `fold_position`/`Contact` code — it fails
(`10000.714922534582 <= 10000.0`), confirming the slow-drift mechanism is the reachable live
path and the fix addresses it directly, not a neighbouring defect. `passes_gate`'s existing
3-sigma gate does reject the single-big-jump reproduction (`GATE_SIGMA_THRESHOLD = 3.0`,
`association_over_time.py:226`), consistent with the debug report.

Both fixes (`FUSION_SANITY_SIGMA` residual guard, `clamp_to_detection_envelope`) are correctly
scoped, correctly placed (envelope check is a caller concern, not baked into the pure fusion
primitive — matches the module's own stated `(estimate, estimate) -> estimate` contract), wired
at both `Contact.record`/`from_percept` call sites with no bypass, and use the calibrated
channel caps (`perception.visibility.NAKED_EYE_RANGE_CAP_M`,
`perception.association.RANGE_CAP_M`) rather than new constants. The `_identification_lead`
regex fix is correct and covered end-to-end. The cardinality reasoning is sound and the pinning
test is real (not vacuous — it exercises the actual gate-widening interaction path, not a
restated assumption).

However, empirical testing of the one item flagged as "found, not fixed, out of scope" —
`Covariance2D._MIN_DETERMINANT` — shows it is not the narrow, deferrable edge case the debug
report characterizes it as. It is reachable under ordinary flight conditions, it corrupts the
fused **mean** (not just the reported uncertainty), and it demonstrably makes the brand-new
`FUSION_SANITY_SIGMA` guard misfire. That is a required fix, not a backlog note — see below.

### Required Fixes

- **`Covariance2D._MIN_DETERMINANT` corrupts `fold_position`'s fused mean under ordinary
  naked-eye ranges, and can make the new `FUSION_SANITY_SIGMA` guard hold a legitimate fusion.**
  This is more severe and more reachable than the debug report states. Verified directly
  (scripts run against the fix branch's actual source, `body-layer/.venv/bin/python`):

  - `fold_position`'s `fused_covariance = info_sum.inverse()` inverts an *information* matrix
    every single time `prior is not None` — not just in some many-fold degenerate case. For two
    naked-eye looks of equal covariance, `det(info_sum) = 4 / det(cov)`; the floor
    (`1e-9`) is hit whenever `det(cov) > ~4e9`.
  - Production naked-eye uncertainty (`perception/estimation.py`'s `naked_eye_sigma_m`:
    `sigma_cross_m = radians(3.0) * range`, `sigma_down_m = 0.17 * range` — not a test-only
    value, this is what `naked_eye_source.py` actually populates `Percept.position_uncertainty`
    with) makes `det(cov) ∝ range^4`. Solving the threshold: **the floor is hit for any
    same-bearing repeated naked-eye look beyond ~2.7 km** — i.e. across roughly three quarters of
    the naked-eye envelope (`NAKED_EYE_RANGE_CAP_M` = 10 km), not an exotic corner. The exact
    sigma pair that exposed this in the debugger's own testing (`157.08, 510.0`) is not a
    contrived number — it is `naked_eye_sigma_m(3000.0)`, i.e. an ordinary 3 km look, and is the
    same pair `test_optic_policy.py::test_a_well_refined_contact_collapses_the_look_to_a_single_
    step` already folds ten times at.
  - The corruption is not confined to the reported uncertainty magnitude. Repeating an
    *identical* look (x=3000, z=0) five more times with this sigma pair — which must converge to
    and stay at `(3000, 0)`, only tightening — instead visibly wanders: `3000.0 → 1853.5 → 2125.3
    → 2293.7 → 2408.6 → 2492.0`, only slowly re-converging. The believed **position**, not just
    its confidence, is wrong for several consecutive folds under a completely ordinary
    re-observation sequence.
  - This directly threatens the new guard: a *legitimate* moderate near-parallel residual (100 m
    at 5° — the same case `test_fold_position_moderate_near_parallel_residual_still_fuses`
    exercises with the clean `(60, 800)` pair, and which correctly fuses there) **incorrectly
    holds the prior** when run with the floor-triggering `(157.08, 510.0)` pair instead — i.e. the
    new anti-runaway guard itself misfires on ordinary evidence, at ranges the fix's own test
    suite doesn't probe (the suite's own tests deliberately avoid this sigma pair for fusion
    tests, per the `test_fold_position_repeated_identical_look_still_tightens` docstring, but
    the pair it substitutes, `(60, 800)`, sits at `det(info_sum) = 1.7e-9` — under 2x above the
    floor, not a safe margin, and does not represent the sigma naked-eye percepts actually carry
    at any real range).
  - Note `_MIN_DETERMINANT` is pre-existing on `main` (unrelated commit history to this fix), but
    this fix is the first change whose own correctness is shown to depend on it — the new guard's
    mahalanobis tests are computed against covariances this floor can silently corrupt, and the
    corruption propagates forward (a corrupted `fused_covariance` becomes next fold's `prior.
    covariance`, feeding the *next* guard evaluation too). Given that, "pre-existing, unrelated,
    out of scope" does not hold for this PR specifically.
  - **Fix suggestion** (not prescriptive): the floor is calibrated for covariance-scale
    determinants (~1e9) and applied uniformly to both covariance-form and information-form
    inversions, which live at wildly different scales for realistic sigma values. A
    scale-relative floor (e.g. relative to the matrix's own trace or the product of its
    diagonal terms) rather than an absolute `1e-9`, or a floor specific to each call site's
    expected scale, would avoid firing on the ordinary case while still guarding the
    genuinely-near-singular one.

### Optional Refinements

- **A held look bumps `last_seen_sim` (and therefore `certainty_of`/`position_confidence`)
  exactly as an accepted one does** — `Contact.record` sets `self.last_seen_sim =
  percept.t_sim` unconditionally, regardless of whether `fold_position`/
  `clamp_to_detection_envelope` held the prior. So a contact whose position is genuinely frozen by
  either guard still reads as fresh/"observed" and high-confidence, rather than reflecting that
  its position hasn't actually moved. This is pre-existing field semantics (`last_seen_sim` was
  never separately tracked from a "did the position actually update" signal, even before this
  fix), and empirically the guards recover within tens of seconds under normal reacquisition
  (verified: a genuinely relocated target starts being believed again by ~t+20s at
  `GATE_GROWTH_RATE_MPS = 20`), so this is not "stuck forever" — but it does mean a stale-position
  hold is invisible to certainty/confidence for as long as it lasts. Worth a follow-up if a
  future sortie reports a confident-sounding callout for a position that hasn't visibly moved.

- `Contact` is never permanently stuck: confirmed both guards recover once elapsed-time inflation
  grows the covariance enough (`GATE_GROWTH_RATE_MPS`-driven), independent of anything fixed here.
  No action needed, noted for completeness since the task asked for this to be checked explicitly.

### Verification

- Reused the branch's own reported run: `ruff format`/`check` clean, `mypy --strict` clean (48
  files), `pytest -q` 1189 passed / 4 xfailed (12 new, no regressions) — not re-run, per the
  task's own note that this was already established.
- Independently re-ran, from this review: the crux "does the slow-drift test genuinely fail
  pre-fix" check (see Review Summary) — confirmed by direct execution against reverted source,
  not by inspection.
- Independently ran three throwaway scripts (not committed — scratch, per instructions) against
  the fix branch's actual installed source (`body-layer/.venv/bin/python`) to establish the
  `_MIN_DETERMINANT` finding above: a round-trip `inverse().inverse()` mismatch, a repeated-look
  mean-drift reproduction, and a guard-misfire reproduction on a legitimate 100 m residual. All
  three are directly reproducible, not inferred.
- Did not re-verify the `passes_gate` "rejects the 5°/large-residual case" claim by direct
  execution (only by reading `GATE_SIGMA_THRESHOLD = 3.0` and the formula) — low risk, the
  debugger's own report already states it was confirmed directly and the math is a simple
  threshold comparison.

### Verdict

NEEDS REVISION — one required fix (`_MIN_DETERMINANT`'s scale mismatch, which this PR's new
guard now depends on for correctness at ordinary naked-eye ranges). The core mechanism fix
(ill-conditioning guard + detection-envelope clamp + speech stutter fix) is otherwise sound,
correctly scoped, and well-tested; once the determinant floor is rescaled (or the guard's
mahalanobis computation is shown to be safe against it some other way), this should be a quick
re-review, not a redesign.

### Review Confidence

Full read of the diff and the debug report. Empirically verified (not just read) the three
claims most load-bearing for the verdict: the slow-drift reproduction against reverted pre-fix
source, the `passes_gate` numeric threshold, and the `_MIN_DETERMINANT` corruption's reach and
its interaction with the new guard. Did not re-run the full branch test suite (reused the
already-reported clean run per the task's instruction).

---

## 2026-09-25 re-review — required fix (`97d5c65`)

Re-review of the single commit responding to the required fix above. Read `97d5c65`'s diff
(`git diff c1cba89..97d5c65`) and the corresponding `plans/position-belief-runaway/debug.md`
addendum in full.

**Working-note on this review's own setup**: my assigned worktree is based on `main`
(`a04eec8`), which predates this whole branch, so `body-layer/src` on disk here is *not* the
fix — it is `main`'s pre-`b5b79b8` `position_belief.py` (confirmed: no `FUSION_SANITY_SIGMA`,
absolute `_MIN_DETERMINANT`, `git log -1` on the file shows `5676b09`, unrelated). A first probe
script that imported "the current code" via this worktree's own `PYTHONPATH` was silently
running pre-fix code for both "old" and "new" cases and produced a false match. Caught before
it reached this report by noticing `pytest`'s own `pythonpath` config (`body-layer/pyproject.toml`)
inserts `src` ahead of anything on `PYTHONPATH`, and by then noticing the two `git show` dumps
disagreed with what `grep` found on disk. Fixed by `git archive`-ing the branch tip (`97d5c65`)
and the pre-fix commit (`c1cba89`) into two clean scratch trees and running pytest/scripts with
those directories as `cwd`, so each tree's own `pyproject.toml` resolves `pythonpath` against
itself. All findings below are from those two clean trees, not this worktree's checkout.

### Findings, against the review's five numbered checks

1. **Invariance claim** — true, and true for the anisotropic, rotated case, not just the
   diagonal one. Derived analytically first (2x2 symmetric `M` with eigenvalues `a, b`:
   `det(M)=ab`, `trace(M)=a+b`; `M^-1` has eigenvalues `1/a, 1/b`, so
   `det(M^-1)/trace(M^-1)^2 = (1/(ab)) / ((a+b)^2/(ab)^2) = ab/(a+b)^2 = det(M)/trace(M)^2`
   exactly — trace and det are basis-independent, so this holds regardless of rotation), then
   confirmed numerically against `covariance_from_uncertainty(157.08, 510.0, bearing)` at five
   bearings (0°, 17°, 37°, 90°, 123.4°): `det/trace²` before and after `.inverse()` match to
   float precision at every bearing. The claim is correct as written, not just for the diagonal
   case the addendum's own worked example happened to check.
2. **Is `1e-9` the right ratio** — yes, with real margin, and the same-digits-as-before is
   coincidence, not carried-over laziness (the addendum's own math derives it from the same
   quantity, `ab/(a+b)^2`, at a value that happens to still read as `1e-9`). The floor permits a
   sigma-axis ratio down to `sqrt(1/1e-9) ≈ 31623:1` before firing. Checked real anisotropy this
   code produces: `naked_eye_sigma_m` pairs run `ratio ≈ 0.0056` (60,800) to `≈ 0.079` (157.08,
   510) — 7-8 orders of magnitude of margin. Pushed a deliberately extreme synthetic pair
   (`sigma_cross=1.0, sigma_down=5000.0`, a 5000:1 ratio, well beyond anything
   `covariance_from_uncertainty`'s real callers produce) and the ratio is still `~4e-8`, 40x
   above the floor. No cross-channel or elapsed-inflation path was found that could push a real
   ratio anywhere near `1e-9` — `inflated()` adds an *isotropic* term to both axes, which moves
   the ratio *toward* 1 (less anisotropic), never toward the floor.
3. **Does the floor still fire when it should** — yes. A genuinely singular matrix
   (`xx=100, zz=25, xz=50`, `det=0` exactly by construction) still floors to a finite inverse
   (`Covariance2D(1.6e6, 6.4e6, -3.2e6)`, no inf/NaN). The fully-degenerate `trace==0` case
   (`xx=zz=xz=0.0`) is caught by `_MIN_DETERMINANT_ABSOLUTE` and also returns finite (all-zero)
   output — the relative floor alone would divide by zero there, confirming the backstop is
   load-bearing and not decorative. Also ran the fix's own repeated-identical-look case out to 15
   folds (not just the 6 the regression test pins): the mean holds exactly at `x=3000.0` for
   every fold, and the covariance itself converges and stabilises after fold 6 (matches the
   `_apply_floor` systematic-bias floor) — no re-drift on repeated application.
4. **Trap 1** (`test_optic_policy.py::test_a_well_refined_contact_collapses_the_look_to_a_single_
   step`) — read the test body directly (`tests/test_optic_policy.py:602-670`). Confirmed its
   only assertion is `assert len(steps) == 1`; nothing in the test body or its fixture asserts or
   depends on any intermediate numeric value from the ten folds that precede it, and no other
   assertion elsewhere in that file reads a value calibrated against the corrupted intermediates.
   The debugger's account holds.
5. **The two new regression tests** — independently re-executed against a clean `git archive`
   of `c1cba89` (pre-fix) and confirmed both **fail** there
   (`test_..._is_exact_at_floor_triggering_sigma`: `1869.817...  == 3000.0 ± 1e-6` fails;
   `test_..._still_fuses_at_floor_triggering_sigma`: `(0.0, 3000.0) != (0.0, 3000.0)` fails, i.e.
   the guard holds the prior when it should fuse) — then re-executed against a clean `git
   archive` of `97d5c65` (post-fix) and confirmed both pass. This is the crux check the task
   asked for and it was run against real isolated trees, not inferred from the diff or reused
   from the debugger's own account (which the setup note above explains I could not simply
   trust without also independently getting a clean environment, after my first pass showed a
   false-positive from an environment mistake of my own).

**Optional item (`last_seen_sim`)** — the debug addendum's "Deliberately not fixed here (logged
as a decision, not an oversight)" section states plainly that this is a known, pre-existing,
bounded gap left out of this fix's scope, restates the review's own recovery-time finding
(~20s via `GATE_GROWTH_RATE_MPS`), and frames it as a follow-up rather than silence. That reads
as a recorded decision, not an oversight — no further action needed here.

**Full verification, independently re-run** (not reused from the debug report) against the
clean `97d5c65` tree: `ruff format --check src tests` — 103 files already formatted; `ruff check
src tests` — all checks passed; `mypy src` — success, no issues in 48 source files; `pytest
tests -q` — 1191 passed, 4 xfailed, matching the debug addendum's own count.

### Verdict

**APPROVED.** The required fix is satisfied: the invariance claim is correct and shown to hold
for the general (rotated, anisotropic) case, the chosen ratio carries real margin against every
real and a deliberately extreme synthetic anisotropy this code can produce, the floor still
catches genuine singularity, Trap 1 is confirmed a non-issue for the stated reason, and the two
regression tests are confirmed to fail pre-fix and pass post-fix by direct, isolated execution.
Nothing new surfaced. The branch as a whole (`b5b79b8` + `97d5c65`) is approved.

### Review Confidence

Full read of `97d5c65`'s diff and the debug addendum. Every one of the five numbered checks was
verified by direct execution against a clean, isolated snapshot of the relevant commit (`git
archive` into scratch directories), not by reading alone — including re-deriving and
numerically confirming the eigenvalue-ratio invariance claim for rotated matrices, which the
original debug addendum had only checked for one bearing.
