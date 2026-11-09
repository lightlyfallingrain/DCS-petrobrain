### Debug Report

### Observed Issue

Same-group re-sightings through the **same optic** (naked eye twice, or binoculars twice)
occasionally failed to fold into one contact: ~10% duplicate-contact rate with naked eye, ~5%
with binoculars, measured on 2026-11-09 (`plans/expected-area-check/plan.md`, "Same-optic fold
measurement 2026-11-09", on `feature/expected-area-check`). The suspected mechanism, per that
measurement: `association_over_time.passes_gate`'s innovation covariance `S =
belief.position_belief.correlated_innovation(...)` goes **indefinite** (negative determinant) on
same-optic gate evaluations, and `Covariance2D.inverse()`'s determinant floor then clamps the
invalid value to a tiny positive number regardless of sign, producing a Mahalanobis test that
rejects almost independently of the percept's actual offset.

### Hypothesis

`correlated_innovation` computes `S = (P_est + P_look) - (C + C^T)`, a *subtraction* of a
geometry-correlated cross-term `C` from a sum of two covariances. A sum of two valid covariances
is always positive semi-definite (PSD); a subtraction has no such guarantee. The function already
had a cap on `C`'s magnitude (`c_down`), but it only applied when `for_fusion=True` — i.e. only for
`fold_position`'s own call. Both gate call sites
(`association_over_time.passes_gate`/`contacts_plausibly_same`) called it with `for_fusion=False`
(the default) and so got the **raw, uncapped** `c_down`. When both looks share one optic and the
gate's hypothesis bearing sits close to the anchor's own bearing (`rho_eff` near 1 — exactly the
same-optic reacquisition case), the raw `c_down` can exceed the bound a valid correlation permits,
pushing `S`'s determinant negative.

### Evidence

**Reproduced directly** (standalone script against the committed code, same-optic `u_u`, 2 km
range, 4 s gap, zero-growth "installation" class, `n=300`, one noise draw per trial via
`perception.estimation.perturbed_bearing_range`'s own id/time-keyed draws): 3/300 trials produced
`S` with a large negative determinant (`-1.2e8` to `-6.8e8`), confirming the hypothesis's mechanism
exactly as the plan's own measurement described it — not an approximation, the real `S` the gate
actually computed.

**First fix attempt (naive, insufficient) — read, don't widen the floor.** Making the existing
`for_fusion` cap (`min(var_prior_along, var_look_along)`, each side's variance projected onto *its
own* bearing axis, independently) apply unconditionally reduced the repro's negative-determinant
count from 3/300 to 1/300, not 0/300. Inspecting the one remaining failure (trial 215) by hand: the
per-axis cap (109 036) was itself *larger* than the true PSD boundary (103 381) for that geometry —
it is necessary but not sufficient, because it ignores `P_est + P_look`'s own off-diagonal
structure, which the gate's hypothesis-vs-real-look bearing mismatch (the gate's `look_covariance`
is built at the percept's own real bearing but the correlation geometry is evaluated at the
*hypothesis* bearing — the two coincide for the fold, never for the gate) interacts with.

**Exact-cap fix, regression found and root-caused.** Replacing the per-axis cap outright with the
closed-form exact PSD boundary (`_max_c_down_for_psd`, derived below) fixed the repro to float-noise
level (`~1e-6` to `~1e-7`, consistent with landing exactly on `det(S)=0`) — but broke an unrelated,
previously-green test:
`test_stage0a_armour_growth_bounded_by_prior_inflation_and_reaches_naked_grade_by_sixth_fuse`
(`tests/test_position_belief.py`), a repeated same-bearing dwell/growth scenario through
`fold_position`. Isolated with a standalone script running the real `fold_position` against both
the true original (`main` checkout) and the exact-cap code side by side: original fuse 3 landed at
exactly the prior's own inflated radius (the `_is_valid_covariance` "hold" branch firing); the
exact-cap version landed 14% *above* it. Root cause: pushing `c_down` to the **exact** PSD boundary
drives `S` to near-singularity, and the Bar-Shalom-Campo fused-covariance formula
(`P_est - gain @ (P_est - C^T)`, `gain` through `S^-1`) is exactly the numerically fragile regime
`_is_valid_covariance`'s own docstring already names ("a near-singular `S^-1` amplified through `K`
can push the result negative") — the result can come out *larger*, not smaller, even though `S`
itself stays nominally valid, and `_is_valid_covariance`'s existing guard does not catch a result
that is merely too large (only outright negative trace/determinant).

### Fix Applied

`body-layer/src/belief/position_belief.py`, `correlated_innovation`:

1. **The cap now always applies** (for both the gate and the fold) — the `for_fusion` parameter is
   removed. The original "the gate never needs capping" theory was true for `S` being too *narrow*,
   false for `S` failing to be a valid covariance at all.
2. **Two caps, combined by `min`, not one:**
   - `per_axis_cap` — the original `min(var_prior_along, var_look_along)`, kept as-is. Already
     proven stable for every case this project has run `fold_position` through; removing it
     outright (replacing rather than supplementing) is what caused the dwell/growth regression
     above.
   - `psd_cap` — a new helper, `_max_c_down_for_psd(sum_covariance, k_xx, k_zz, k_xz)`: the exact,
     closed-form largest `c >= 0` for which `sum_covariance - c * K` stays PSD, where `K` is the
     fixed symmetric direction matrix `c_sym = c_down * K`. Since `sum_covariance` (a sum of two
     valid covariances) is always PSD and `det(K) <= 0` always (a 2D cross-product identity,
     provable from `K`'s own construction as two unit-vector outer products), `det(sum_covariance -
     c*K)` is a downward-opening (or linear, at `det(K)=0`) function of `c` with exactly one
     positive root; `trace(S) >= 0` is a second, independent cap. Full derivation in the function's
     own docstring.
   - `max_c_down = min(per_axis_cap, psd_cap)`: never looser than either cap alone. Stays on the
     per-axis cap everywhere that cap already sat inside the true PSD region (the fold's own
     established-stable cases); only tightens further, to the exact boundary, where the per-axis cap
     alone was insufficient (the gate's mismatched-hypothesis-bearing regime the original defect
     lives in).

No tuning constant was introduced — `_max_c_down_for_psd` is a closed-form geometric derivation, not
a magic number, so `body-layer/src/tuning.py` does not apply (per `CLAUDE.md`'s own scope for that
mechanism: behaviour-affecting *constants*, not formulas).

**Regression test added** (`tests/test_position_belief.py::
test_correlated_innovation_s_stays_psd_over_a_same_optic_ensemble`): sweeps both optics in the
ladder, four ranges, 60 resampled same-optic reacquisition trials each (240 calls total, unique
`observation_id`/time base per trial, the harness-resampling recipe), asserting `S`'s determinant
and trace stay non-negative (float tolerance `1e-3 * trace^2`, orders of magnitude tighter than the
bug's own `-1e7` to `-1e9` signature) on every call.

### Verification

- `ruff format --check`, `ruff check`, `mypy src` (strict): all clean.
- Full suite (`pytest tests -q`, 3043 tests + the new regression test): **3039 passed, 6 failed,
  4 xfailed** (unchanged failure count before/after adding the regression test). The 6 failures are
  **not accidental** — each was individually isolated (standalone script, same test code, `main`
  checkout's original `src` vs this fix's `src`, same salt/geometry) to confirm it is a genuine,
  measured consequence of this fix and not pre-existing flakiness:

  | test | before (measured) | after (measured) | why |
  |---|---|---|---|
  | `test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact` (`u_u`) | 100% (frozen-draw harness artifact, per `feedback_harness_resampling_fix_can_falsify_an_existing_guarantee`) | 87% (resampled harness, this task's own instructed fix to `_e3_fold_rate`) | Expected — matches the already-published 83–87% honest same-optic ceiling. Harness fix, not the production fix. |
  | `test_e1_same_optic_fold_rate_stays_at_or_below_the_clear_case_ceiling[False-optic0-5.0-3.5]` | 6.0% (ceiling 10%) | 12.0% (ceiling 10%) | Production fix alone (harness untouched for this test). The bug's floor-clamp pathology was spuriously *rejecting* some different-groups same-optic pairs that should have genuinely folded less; fixing it raises this one cell's fold rate past its 10% ceiling. |
  | `test_e1_cross_optic_memory_only_fold_rate_is_fenced[True-far_optic1-near_optic1-b_u-5.0-3.5]` | 88.3% (fence 95%) | 96.7% (fence 95%) | Same mechanism, cross-optic. |
  | `test_residual_fold_rate_for_far_binocular_near_unaided_is_small[4.5-3.0]` / `[5.0-3.5]` | 1–5% (fence 10%) | residual ≈ honest fold rate (≈87%, far above the 10% fence) | **The most consequential finding** — see below. |
  | `test_false_trigger_rate_for_long_gap_stationary_same_group_exceeds_the_gate` | 25–27% (documented floor `>= 0.15`) | 6.0% at the 2.0 km cell (below `0.15`) | Moved in the *good* direction; still reported, not edited, per the task's instruction. |

  **Per the task's explicit instruction, none of these six were edited.** All are pre-existing
  fences (`BL-B108`/`BL-B110`) outside this entry's scope; the fence values are the user's to
  revise.

  **Significant side-finding on `test_expected_area_trigger.py`'s "as-if gate" (`BL-B110`'s own
  test-only stand-in for a not-yet-built trigger).** That module's `_as_if_gate` deliberately
  overrides `correlation_optic_class` to the *tighter* of the two optics, to manufacture an
  intentionally stricter discriminator against genuinely different groups. Isolating the **honest**
  fold rate (the real `passes_gate`, not the as-if stand-in) for the far-binocular→near-unaided
  *different-groups* case showed it barely moved (81.3% → 88.7%, consistent with the other E1
  shifts above) — the collapse of the *residual* fence from ~1–5% to ~87% is not from the honest
  gate becoming far more lenient. It is because the as-if gate's own measured catch rate (~76–80%,
  what the 1–5% residual fence rested on) was **itself an artifact of the same indefinite-S bug**:
  pushing `correlation_optic_class` to the tighter optic (while leaving the magnitude at the real,
  looser optic's declared sigma) is exactly the geometry that drove `S` negative before this fix,
  and the floor-clamped, effectively-infinite Mahalanobis that produced was doing most of the
  as-if gate's "catching." With `S` now valid, the as-if gate's real, intended discriminating power
  for this direction is far weaker than the 1–5% residual implied. **Not fixed here** — this is a
  finding for whoever next touches `BL-B110`'s Stage 2 trigger design, not a regression in this
  entry's own scope.

- Negative-determinant repro: re-run after the fix, 0/300 trials with a determinant below float
  noise (`~1e-6`, down from `-1.2e8`/`-6.8e8`).
- `test_stage0a_armour_growth_bounded_by_prior_inflation_and_reaches_naked_grade_by_sixth_fuse`
  (the dwell/growth regression the exact-cap-alone attempt caused): passes, bit-for-bit identical
  per-fuse covariance to the original `main` checkout (verified by direct side-by-side script, not
  just the pytest pass/fail).
- New regression test
  (`test_correlated_innovation_s_stays_psd_over_a_same_optic_ensemble`): passes.
- Harness-resampling fix applied to `_e3_fold_rate` in `tests/test_relative_distance_sweep.py`
  (per-trial `observation_id`/`t_sim` base, `t0 = trial * 1e-3`), per the task's instruction —
  this is what moved the `u_u` "always folds" test's measured rate from the frozen-draw 100% to
  the honest 87%. **Correction, 2026-11-09 (review required fix):** this entry originally claimed
  the same fix was also applied to `_fuse_two_looks` at this point in the task. It was not — only
  `_e3_fold_rate` was touched here. `_fuse_two_looks` carried the same frozen-draw shape
  unaddressed until the Reviewer caught it (`plans/same-optic-gate-indefinite/review.md`'s
  Required Fix); see `implementation.md`'s own correction note for what that pass did.
- Re-measured `body-layer/tools/measure_same_group_fold.py --n 300` (copied onto this branch, full
  240-cell/72 000-trial sweep, 647.2 s). Aggregate rates are statistically consistent with the
  2026-11-09 baseline measured on the *unfixed* code (`u_u` ≈ 88–90%, `b_b` ≈ 92–95%, `u_b` ≈
  98–100%, `b_u` ≈ 97–99%, surface 100 m AGL ≈ 87–91%, surface 500 m AGL ≈ 90–97%) — the
  determinant bug was contributing roughly 1% of trials per cell (matching the earlier "accounts
  for roughly a third to half of one cell's own ~14% non-fold rate" finding, which was for one
  specific 2 km/4 s cell, not the aggregate), not the dominant driver of the ~85–94% ceiling. Full
  240-row table: `/private/tmp/claude-501/-Users-sg-Code-DCS-petrobrain/9af034a3-3761-4eb7-a81e-bb7415cff2d5/scratchpad/fold_table_n300.md`
  (scratchpad, not committed — regenerate with the command in the script's own module docstring).

### Files changed

- `body-layer/src/belief/position_belief.py` — the fix (`correlated_innovation`, new
  `_max_c_down_for_psd` helper, `for_fusion` parameter removed, one call site updated).
- `body-layer/tests/test_position_belief.py` — new regression test.
- `body-layer/tests/test_relative_distance_sweep.py` — harness-resampling fix to `_e3_fold_rate`,
  per the task's instruction. (`_fuse_two_looks` was **not** fixed in this pass — see the
  correction note above and in the "Verification" section.)
- `body-layer/tools/measure_same_group_fold.py` — copied from `feature/expected-area-check` so the
  re-measurement is reproducible on this branch.

### User direction 2026-11-09 (after the first pass)

Asked: the S-indefinite fix holds but moves the same-optic fold rate only ~1%; the residual
~10% is unexplained against a 3-sigma gate's ~1%. Recommended continuing on this branch before any
fence edit: check whether the gate's assumed correlation between two same-optic looks matches the
error the simulation actually draws (hypothesis: the gate subtracts a cross-term for an error the
two looks do not share, so S is too tight). User, verbatim:

> *"continue as recommended"*

The six moved fences stay unedited until the second pass; they come back to the user once.

### Second pass

**Method.** Built `body-layer/tools/measure_gate_calibration.py` (a measurement tool, not a
test, same posture as `measure_same_group_fold.py`): for a fixed same-optic, same-group geometry,
resample the noise ensemble and record both the gate's own modelled `S`
(`belief.position_belief.correlated_innovation`) and the empirical covariance of the actual
simulated innovation, then compare the Mahalanobis^2 calibration against chi-square(2) (a
correctly-sized 3-sigma gate should reject ~1.1% of same-group same-optic pairs).

**Finding 1 -- the leading hypothesis as literally stated is not what is happening.** Directly
measured the TRUE correlation between two same-optic looks' own stable (field-based) down-range
error at identical geometry: ~0.96, matching the model's `effective_down_correlation` exactly
once the independent `z_look` share is accounted for (which the model already excludes by
construction via `sigma_down_stable_m`). The field-based correlation model
(`perception.estimation.stable_range_correlation`/`_tiered_field`) is mathematically exact at
matched geometry, not an approximation error -- the simulation does *not* draw a different
correlation than `C` assumes, for the stable/field term.

**Finding 2 -- a real, confirmed defect: the gate has no ill-conditioning guard, and the first
pass's exact PSD cap lands `S` close enough to that boundary on same-optic short-gap trials that
`.inverse()`'s determinant floor fires on `~4-6%` of `passes_gate` evaluations.** Measured on
`u_u` 2km/4s-gap (n=2000): gate rejects 11.2% against chi2(2)'s ~1.1%; of the rejected trials,
`det(S)/trace(S)^2 < 1e-6` (near-singular) for 38%, producing Mahalanobis values in the
*billions* via the floor-clamped, essentially-arbitrary inverse. This is exactly the
`_is_valid_covariance`-class failure the first pass fixed for the **fold**; `passes_gate`/
`contacts_plausibly_same` have no equivalent check and feed a possibly near-singular `S` straight
into the Mahalanobis test.

**Fix applied (first half):** `_max_c_down_for_psd` now targets `det(S) == _MIN_S_DETERMINANT_
RATIO * trace(S)^2` (a new private numerical-stability margin, `1e-4`, framed like the existing
`_MIN_DETERMINANT_RATIO` -- not a tuning key, not a correlation/physics judgement) instead of
`det(S) == 0`, via the same quadratic solved against adjusted coefficients. Confirmed: post-fix,
0% of trials are near-singular (min ratio lands exactly at the margin), and the Mahalanobis
*magnitude* for those trials drops from billions to the tens of thousands.

**Correction, found re-measuring after the fix: this does NOT move the overall rejection rate.**
Still 11.2%, the identical 225/2000 trials rejected before and after. The margin fix removes the
catastrophic *magnitude* of the near-boundary outliers (real numerical-hygiene value, and it
protects the fold's own gain computation from the same fragile regime per `.claude/agent-memory/
debugger/feedback_exact_psd_cap_can_regress_a_different_caller.md`) but does not, by itself, fix
the fold-rate defect -- those trials were already going to clear the 3-sigma threshold at a
finite, merely-large Mahalanobis value. **Keep this fix for the numerical-hygiene reason; do not
credit it with a fold-rate improvement without a re-measured `measure_same_group_fold.py` table
showing one.**

**Finding 3 -- the orientation-mismatch theory (the natural next candidate once Finding 2 turned
out not to move the rate) is refuted.** `C`'s correlation kernel and axis unit vectors are built
from each look's own *reported* (perturbed) bearing/range, never the true one -- a plausible
source of shape mismatch, since the field correlation the kernel is modelling actually lives along
the *true* bearing axis. Tested directly with a ground-truth probe
(`correlated_innovation_true_axis`, test-only, can never ship -- no-omniscience is structural):
rebuild `C`'s kernel and axis from each look's true bearing/range instead, keep every declared
sigma unchanged, and re-measure the rejection rate. Result (n=1000, `u_u` 2km/4s): **15.3% under
the true-axis variant vs. 10.6% under production's reported-axis `S`** -- *worse*, not better; the
4.5km cell shows the same direction (17.1% vs 11.4%); `b_b` is roughly unchanged (3.9% vs 5.3%).
The true-axis variant does not recover anything close to chi2(2)'s 1.1%, so building `C`'s axis
off the reported bearing is **not** the cause of the residual mismatch. No fix follows from this
finding -- per the task's own instruction, a refuted hypothesis gets reported, not patched around.

**Net result of this pass: the near-singular mechanism (Finding 2) is fixed (numerical hygiene);
the well-conditioned residual over-rejection (~5-11% depending on cell, vs. chi2(2)'s 1.1%) has
two confirmed non-causes (Findings 1 and 3) and no identified cause.** The empirical covariance of
the real simulated innovation, used directly in place of the model `S`, reproduces chi2(2)'s
1.1% almost exactly in every cell measured -- so the test/threshold machinery is sound and the
mismatch is specifically in how `S`'s *shape* (not trace, which tracks the empirical covariance to
within ~5%) is built. The clearest numeric signature: the empirical down-axis variance is
consistently 70-76% of the model's `S_down` (model too wide on that axis alone, by the approximate
down/cross split), while the full 2x2 Mahalanobis test still over-rejects -- i.e. the mismatch is
not reducible to either axis's own variance in isolation; it is a genuine interaction the
approximate per-axis split (explicitly not exact when `S`'s off-diagonal term is non-zero, per
`measure_same_group_fold.py`'s own comment) cannot localise further. **Left open for whoever next
picks this up**, with the two ruled-out theories recorded above so they are not re-tried.

### Fix applied (second pass)

`body-layer/src/belief/position_belief.py`:

1. `_MIN_S_DETERMINANT_RATIO: Final[float] = 1e-4` (new private module constant, alongside
   `_MIN_DETERMINANT_RATIO`) -- a numerical-stability margin, not a tuning key (same reasoning the
   file already applies to `_MIN_DETERMINANT_RATIO`: this governs how far `S` is kept from its own
   inversion floor, not a correlation/perceptual judgement).
2. `_max_c_down_for_psd` now solves for `det(S) == _MIN_S_DETERMINANT_RATIO * trace(S)^2` instead
   of `det(S) == 0`, by substituting the margin's target into the existing quadratic
   (`det(S) = det_a - b*c + det_k*c^2`) and solving against adjusted coefficients `det_a' = det_a -
   margin*trace_a^2`, `b' = b - 2*margin*trace_a*trace_k`, `det_k' = det_k - margin*trace_k^2`
   (`det_k' <= 0` still holds, so the same root-finding code applies unchanged; at `margin = 0`
   this collapses to the original derivation exactly). Full derivation in the function's own
   docstring.

No other production code changed. `association_over_time.py`'s two call sites
(`passes_gate`/`contacts_plausibly_same`) are unchanged -- the fix lives entirely in
`correlated_innovation`'s own shared cap, so both the gate and the fold inherit it.

### Verification (second pass)

- `ruff format --check`, `ruff check`, `mypy src` (strict): all clean, including the new
  `tools/measure_gate_calibration.py` (ruff only -- `tools/` is outside `mypy src`'s scope per
  `CLAUDE.md`'s own Commands list, same as every other `tools/*.py` in this subproject).
- Full suite (`pytest tests -q`): **3039 passed, 6 failed, 4 xfailed** -- identical failure count,
  identical failing test names, and fold-rate numbers matching the first pass's own table to
  within noise (`u_u` always-folds: 87.00% vs. the first pass's 87%; cross-optic memory-only:
  96.67% vs. 96.7%; same-optic ceiling: unchanged cell). **No new failures, no regression** --
  confirms the margin fix does not move any fenced rate, consistent with the calibration
  measurement's own finding that it does not change the overall rejection count.
- `test_correlated_innovation_s_stays_psd_over_a_same_optic_ensemble` and
  `test_stage0a_armour_growth_bounded_by_prior_inflation_and_reaches_naked_grade_by_sixth_fuse`
  (the first pass's own regression tests): both still pass, run in isolation to confirm.
- Negative/near-singular-determinant repro, re-run against this fix
  (`tools/measure_gate_calibration.py --n 1000`, `u_u` 2km/4s cell): `det(S)/trace(S)^2` minimum is
  now exactly `1.000e-04` (the margin, working as designed) across every trial in every cell
  measured -- 0% near-singular, down from 4-6% before this fix.
- Re-measured `tools/measure_same_group_fold.py --n 80` (reduced from the task's requested
  `--n 300` to fit this pass's per-command foreground time budget; aggregate rates below are
  therefore slightly noisier than the first pass's `n=300` table but land within the same range):

  | optic pair | aggregate fold rate (n=80/cell) | first pass's `n=300` baseline |
  |---|---|---|
  | `u_u` | 90.5% | 88-90% |
  | `b_b` | 93.4% | 92-95% |
  | `u_b` | 98.9% | 98-100% |
  | `b_u` | 97.8% | 97-99% |
  | `u_u` surface | 89.4% | 87-91% / 90-97% |

  **Statistically consistent with the first pass's own baseline, no detectable movement** --
  confirms Finding 2's own conclusion that the near-singular fix is numerical hygiene, not a
  fold-rate change.

### Status of the six moved fences (table carried from the first pass)

**None of the six were edited.** Re-run against this fix's code (full `pytest tests -q` above):

| test | first pass (measured) | this pass (measured) | moved further? |
|---|---|---|---|
| `test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact` (`u_u`) | 87% | 87.00% | no |
| `test_e1_same_optic_fold_rate_stays_at_or_below_the_clear_case_ceiling[False-optic0-5.0-3.5]` | 6.0%/12.0% (ceiling 10%) | 12.00% | no |
| `test_e1_cross_optic_memory_only_fold_rate_is_fenced[True-far_optic1-near_optic1-b_u-5.0-3.5]` | 88.3%/96.7% (fence 95%) | 96.67% | no |
| `test_residual_fold_rate_for_far_binocular_near_unaided_is_small[4.5-3.0]` | 1-5%/~honest rate (fence 10%) | 72.00% | no |
| `test_residual_fold_rate_for_far_binocular_near_unaided_is_small[5.0-3.5]` | 1-5%/~honest rate (fence 10%) | 87.33% | no |
| `test_false_trigger_rate_for_long_gap_stationary_same_group_exceeds_the_gate` | 25-27%/6.0% (floor `>= 0.15`) | 6.00% | no |

**All six are exactly where the first pass left them.** This is expected, not a gap in this pass's
own fix -- Finding 2 (the only production defect this pass actually fixed) was confirmed not to
move the overall rejection rate, so no fence-relevant number should have moved either. The fences
remain the user's to revise; nothing here changes that.

### Files changed (second pass)

- `body-layer/src/belief/position_belief.py` -- `_MIN_S_DETERMINANT_RATIO`, `_max_c_down_for_psd`'s
  margin-aware cap derivation.
- `body-layer/tools/measure_gate_calibration.py` -- new measurement tool (not committed test code),
  documenting and reproducing every finding in this section; its own module docstring restates
  the three findings for a reader who finds the tool before this file.
- `plans/same-optic-gate-indefinite/debug.md` -- this section.

### Open item for whoever next touches this gate

The well-conditioned residual over-rejection (Finding 3's "left open") has no identified mechanism.
Two theories are now ruled out (the field correlation model itself, and the reported-vs-true-axis
mismatch). Candidates not yet tested: whether the approximate down/cross split is hiding a genuine
off-diagonal effect that a full-2x2, non-decomposed comparison would localise better; whether
`hypothesis_scale`'s rescaling of the percept's own sigma (`passes_gate`'s "Belief side" amendment)
interacts with the cap in a way that is not visible cell-by-cell; or whether the mismatch is a
property of the Random-Fourier-Feature field approximation's own higher moments (skew/kurtosis)
rather than its second moment (variance/correlation), which this pass never checked. Any of these
is Architect-level scoping, not a Debugger patch, per this role's own escalation rule and
`.claude/agent-memory/debugger/feedback_escalate_gate_policy_changes.md`'s precedent for this same
gate.

### User decision 2026-11-09: stop here

Offered (A) an architect pass on the residual S-shape mismatch, or (B) stop: merge the
conditioning fixes, reset the six moved fences to honestly measured values, file the residual.
User, verbatim:

> *"stop here. If this becomes a problem in missions, we'll investigate more, but not now."*

Residual filed as `[[BL-B113]]` (deferred). Next on this branch: fences reset to measured values
(with margin), then Reviewer → Security → Performance → DoD → merge.
