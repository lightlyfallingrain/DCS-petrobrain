### Implementation Summary

Per the user decision recorded in `debug.md`'s final section (2026-11-09, verbatim: *"stop here. If
this becomes a problem in missions, we'll investigate more, but not now."*), this pass resets the
six test fences that the S-conditioning fixes moved, to their honestly re-measured values. No
production code was touched — only `body-layer/tests/test_relative_distance_sweep.py`,
`body-layer/tests/test_expected_area_trigger.py`, and two `ROADMAP/` entries.

Every fence was re-measured on this branch's own committed code, at the test's own `n`, and
cross-checked for stability across 3-8 additional salts before being set. Where a test's own
docstring states a measured range, that range is what several additional salt runs produced, not
a single draw.

### Fence table (old → new)

| test | old assertion | re-measured on this branch | new assertion |
|---|---|---|---|
| `test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact` (renamed `..._folds_at_least_as_often_as_measured`) | `rate == 1.0` for both u_u and u_b | u_u: 87-90% (frozen-draw-harness artifact exposed by the resampled harness, matches `[[BL-B113]]`'s own same-optic finding); u_b: 98-100% | split into `_E3_FOLD_RATE_FLOOR`: u_u `>= 0.75`, u_b `>= 0.95` |
| `test_e1_same_optic_fold_rate_stays_at_or_below_the_clear_case_ceiling` (`_SAME_OPTIC_FOLD_CEILING`, shared across all 24 parametrized cells) | `0.10` | worst cell (`5.0/3.5 km, unaided, far_first=False`, this test's own salt): 12%; a wider resample of the same cell reached 16%; other cells 0-10% | `0.20` |
| `test_e1_cross_optic_memory_only_fold_rate_is_fenced[True-far_optic1-near_optic1-b_u-5.0-3.5]` (`_CROSS_OPTIC_MEMORY_ONLY_FENCE[(5.0, 3.5, "b_u", True)]`) | `0.95` | 90-98% across salts (this test's own salt: 96.67%) — essentially saturated | `1.0` (no further widening to catch; a future narrowing should tighten this deliberately) |
| `test_residual_fold_rate_for_far_binocular_near_unaided_is_small[4.5-3.0]` (renamed `..._matches_honest_rate`) | `residual <= 0.10` | 70-78% across salts | floor `>= 0.55` (`_FAR_BINOCULAR_NEAR_UNAIDED_RESIDUAL_FLOOR`) |
| `test_residual_fold_rate_for_far_binocular_near_unaided_is_small[5.0-3.5]` (same rename) | `residual <= 0.10` | 87-95% across salts | floor `>= 0.70` |
| `test_false_trigger_rate_for_long_gap_stationary_same_group_exceeds_the_gate` (renamed `..._stays_within_the_gate`) | `catch >= 0.15` (STOP finding) | 4.7-12.0% across salts and both ranges (this test's own salts: 6.0% at 2.0 km, 9.33% at 4.5 km) — the STOP finding's premise (the as-if gate's catch inflated by the indefinite-`S` bug) is gone | ceiling `<= 0.20` (`_LONG_GAP_STATIONARY_FALSE_TRIGGER_CEILING`) |

### Why the residual-fence and long-gap tests changed shape, not just value

Per the task's framing: for the two `test_residual_fold_rate_for_far_binocular_near_unaided_*`
cells and the long-gap false-trigger test, the premise behind the *old* fence is gone, not just
the number. `debug.md`'s "Significant side-finding" established that the as-if gate's own measured
catch rate (what both the 1-5% residual and the 25-27% STOP finding rested on) was itself an
artifact of the same indefinite-`S` bug the production fix on this branch resolved — pushing
`correlation_optic_class` to the tighter optic was exactly the geometry that drove `S` negative,
and the floor-clamped near-infinite Mahalanobis that produced was doing most of the "catching" (or,
for the long-gap case, most of the false-triggering). With `S` now a valid covariance, the as-if
gate's real discriminating power in both directions is far weaker than the old numbers implied.

So these three were converted from ceilings asserting the trigger *works* to floors/ceilings that
*record the current honest truth*, with docstrings pointing at `[[BL-B110]]` Stage 2: its trigger
design (not yet built) must be re-measured against these honest numbers, not the stale ones the
indefinite-`S` bug produced. The module docstring of `test_expected_area_trigger.py` keeps the
original dated finding (point 2) intact and adds a "Superseded 2026-11-09" paragraph underneath
it, per this project's "prune for tense, not length" convention — the original measurement is true
history, not a correction to delete.

### `_SAME_OPTIC_FOLD_CEILING` and the E3 u_u floor are a different kind of change

These two are not "the trigger's premise is gone" — they are ordinary, honestly-measured ceiling/
floor resets after the production fix moved the real rate: the gate-cap fix removed a spurious
over-rejection that was suppressing some genuine different-groups folds (raising
`_SAME_OPTIC_FOLD_CEILING`'s worst cell), and exposed that the E3 u_u "always folds" claim was a
frozen-draw-harness artifact rather than a real guarantee (the resampled harness's honest 87-90%
matches `[[BL-B113]]`'s own already-filed same-optic residual finding exactly). Both are reset to
measured values plus headroom, following this file's existing margin convention (binomial sampling
noise across a many-cell grid, or a flat +10-20 percentage points where the measured rate leaves
room for it).

### Files Changed

- `body-layer/tests/test_relative_distance_sweep.py` — `_SAME_OPTIC_FOLD_CEILING` 0.10 → 0.20 (plus
  comment rewrite); `_CROSS_OPTIC_MEMORY_ONLY_FENCE[(5.0, 3.5, "b_u", True)]` 0.95 → 1.0 (plus
  comment); `test_e3_same_and_unaided_then_binocular_always_folds_to_one_contact` renamed to
  `test_e3_same_and_unaided_then_binocular_folds_at_least_as_often_as_measured`, restructured
  around a new `_E3_FOLD_RATE_FLOOR` dict (u_u `>= 0.75`, u_b `>= 0.95`) instead of `== 1.0`.
- `body-layer/tests/test_expected_area_trigger.py` — module docstring's point 2 gets a
  "Superseded 2026-11-09" paragraph; `_FAR_BINOCULAR_NEAR_UNAIDED_RESIDUAL_FENCE` (a single 0.10
  ceiling) replaced by `_FAR_BINOCULAR_NEAR_UNAIDED_RESIDUAL_FLOOR` (per-cell floors, 0.55/0.70);
  `test_residual_fold_rate_for_far_binocular_near_unaided_is_small` renamed to
  `..._matches_honest_rate`; `test_false_trigger_rate_for_long_gap_stationary_same_group_exceeds_
  the_gate` renamed to `..._stays_within_the_gate`, its `>= 0.15` STOP assertion replaced by a new
  `_LONG_GAP_STATIONARY_FALSE_TRIGGER_CEILING = 0.20` ceiling.
- `body-layer/ROADMAP/BL-B108.md` — one-line note: same-optic/cross-optic fences re-measured with
  the resampled harness on this branch, with the moved values.
- `body-layer/ROADMAP/BL-B110.md` — one-line note: Decision 12's numbers and the as-if trigger's
  catch were artifacts of the indefinite-`S` bug; Stage 2 must be re-designed on honest numbers.
- `plans/same-optic-gate-indefinite/implementation.md` — this file.

No production code (`body-layer/src/`) was touched by this pass.

### Tests Added

None — this pass resets existing fences to measured values; it does not add new test coverage.
The renamed tests are the same six tests, continuing to exercise the same code paths.

### Checks

(body-layer only — the only subproject touched)

- `ruff format --check`: pass (193 files, after one auto-reformat of a multi-line assert in
  `test_relative_distance_sweep.py` that the formatter collapsed to one line).
- `ruff check`: pass — "All checks passed!".
- `mypy src` (strict): pass — "Success: no issues found in 79 source files" (unaffected; this pass
  touches only `tests/`).
- `pytest -q`: pass — 3045 passed, 4 xfailed (3039 passed + 6 previously-failing tests now passing
  against their re-measured fences, 0 failed). Full suite re-run from this worktree; see the run's
  own tail in the conversation for the exact count.

### Notable Discoveries

- **The two "premise gone" tests and the long-gap STOP finding share one root cause**, not three
  independent coincidences: `_as_if_gate`'s own measured discriminating power (both its catch rate
  for different groups and its false-trigger rate for the same group) was dominated by the same
  indefinite-`S` floor-clamp pathology the production fix resolved. This is worth remembering for
  whoever designs BL-B110 Stage 2's real trigger: re-derive its calibration from scratch against
  this branch's code, not by "un-inflating" the old numbers by some factor.
- **`_SAME_OPTIC_FOLD_CEILING` is a single constant shared across 24 parametrized cells**, so
  fixing the one failing cell required re-measuring the whole grid to find the true worst cell
  (16% on a wider salt resample, 12% on the test's own fixed salt) rather than assuming the one
  reported failure was the worst case the constant needs to cover.
- **No tuning-mechanism question arises here** — every changed value is a test fence/ceiling, not
  a behaviour-affecting production constant, so `body-layer/src/tuning.py` does not apply (same
  scope boundary `debug.md`'s own first-pass fix note already stated for the PSD-cap derivation).
