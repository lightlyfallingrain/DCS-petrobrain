### Review Summary

Branch `fix/same-optic-gate-indefinite` at `5a896538e696660d5b5a4411e37882a60803c41c`, reviewed
against `main`. Two commits of substance: a production fix to
`belief/position_belief.correlated_innovation`'s cross-term cap (`for_fusion` removed, replaced by
`min(per_axis_cap, psd_cap)`, plus a numerical-stability margin `_MIN_S_DETERMINANT_RATIO`), and a
test-fence reset pass (no production code) per the user's explicit "stop here" decision recorded in
`debug.md`.

**The production fix itself is sound.** The PSD-boundary derivation in `_max_c_down_for_psd`'s
docstring checks out (sum of two valid covariances is PSD; `det(K) <= 0` from the cross-product
identity; the quadratic-with-margin substitution is algebraically correct and collapses to the
original at `margin = 0`). The fold path keeps `min(per_axis_cap, psd_cap)` rather than replacing
the proven-stable per-axis cap outright — exactly the fix for the regression the debug log reports
finding and root-causing (`test_stage0a_armour_growth_bounded_...`). `for_fusion` is cleanly removed
end-to-end (confirmed by grep: no stray `for_fusion=` kwarg anywhere, and `mypy --strict` is clean,
which would have caught one). No-omniscience is preserved — nothing in the fix reads
`Observation.derived_world_position` or any ground-truth field; the one test-only ground-truth probe
(`measure_gate_calibration.py`'s `correlated_innovation_true_axis`) lives in `tools/`, is explicitly
documented "test-only, can never ship," and is outside `mypy src`'s scope like every other
`tools/*.py`.

`_MIN_S_DETERMINANT_RATIO` is correctly scoped as a non-tunable numerical constant, not a
behaviour-affecting one: it governs how far a covariance is kept from its own inversion floor (same
role as the pre-existing `_MIN_DETERMINANT_RATIO` beside it), not a correlation/perceptual judgement
about what Petrovich believes. `body-layer/src/tuning.py` correctly does not apply, and the debug
log states this reasoning explicitly rather than leaving it implicit.

**Checks, run in this worktree (`/Users/sg/Code/DCS-petrobrain/body-layer/.venv`, no venv exists in
this worktree itself):**
- `ruff format --check`: 1 pre-existing unformatted file (`research/2026-10-05-security-audit.md`,
  untouched by this diff, confirmed via `git log`/`git diff main...tip`) — not this branch's doing.
- `ruff check src tests tools`: clean.
- `cd body-layer && .venv/bin/mypy src`: clean, 79 source files.
- `pytest tests -q`: **3045 passed, 4 xfailed, 0 failed** — matches `implementation.md`'s claimed
  count exactly.

**Documentation (ROADMAP entries, `BL-B113`, backlog) is accurate and consistent with the code and
with each other** — `BL-B108`/`BL-B110`'s added notes correctly scope what moved and why, `BL-B113`
is a properly-minted, honestly-stated deferred entry, and the "Superseded 2026-11-09" paragraphs in
`test_expected_area_trigger.py`'s module docstring follow the project's own "prune for tense, not
delete" convention — the original dated finding stays, the correction is appended underneath it.

### Required Fixes

- **`debug.md` and `implementation.md` both claim the harness-resampling fix (per-trial
  `observation_id`/`t_sim` base) was applied to `_fuse_two_looks`, but the actual diff only touches
  `_e3_fold_rate`.** Verified by diffing `main...5a896538e6` against `test_relative_distance_sweep.py`:
  the only hunks are the `_SAME_OPTIC_FOLD_CEILING` comment/value, the one `_CROSS_OPTIC_MEMORY_ONLY_FENCE`
  cell, and `_e3_fold_rate`/the renamed E3 test. `_fuse_two_looks` (line 586, outside every hunk) still
  uses the fixed `observation_id="first"/"second"`, `t_sim=0.0`/`6.0` across its caller's trial loop —
  the exact frozen-draw shape the debug log itself describes as the bug in `_e3_fold_rate` before the
  fix (the project's own agent memory,
  `feedback_harness_resampling_fix_can_falsify_an_existing_guarantee`, is literally about this class of
  defect). `test_no_omniscience_fused_sigma_never_beats_the_tighter_optics_own_sigma` and
  `test_no_omniscience_fused_mean_never_extrapolates_past_either_look` both call `_fuse_two_looks`
  inside a 10-trial loop and still carry this latent risk unaddressed.
  Two acceptable resolutions, either is fine: (a) correct the inaccurate claim in both docs to state
  only `_e3_fold_rate` was fixed and record `_fuse_two_looks` as a known-remaining instance of the
  same pattern (filed, not silently left undocumented), or (b) apply the same per-trial
  `observation_id`/`t_sim` fix to `_fuse_two_looks` for consistency, since it is the same pattern in
  the same file fixed two functions away. Given this project's weight on documentation accuracy
  ("verify state, not the account of it"; dated claims are the project's record), a false claim about
  what shipped is the thing to fix here, whichever of the two paths closes it.

### Optional Refinements

- `_CROSS_OPTIC_MEMORY_ONLY_FENCE[(5.0, 3.5, "b_u", True)] = 1.0` is a tautological assertion
  (`rate <= 1.0` can never fail, since `rate` is a fraction) — effectively dead test code. It is
  documented as a deliberate, explained choice (saturated, kept as a record, explicit instruction to
  tighten deliberately later rather than leave stale), which is enough to not block this, but a
  `pytest.mark.skip`/comment-only cell (dropping it from the asserted dict rather than keeping a
  no-op assertion) would make the "this cell currently asserts nothing" fact visible from the test
  list rather than only from a comment. (Optional.)
- The removal of the old `c_down = max(-max_c_down, min(max_c_down, c_down))` symmetric clamp in
  favour of `c_down = max(0.0, min(max_c_down, c_down))` (one-sided) is unflagged in both docs.
  Traced it myself: `effective_down_correlation` can only return a value in `[0, 1]` (both
  `rho_view`/`rho_near` are non-negative by construction — `view_range_correlation`/`optic_range_
  correlation` are both exponentials/ratios of non-negative quantities), so `c_down` was already
  non-negative in every real case and this is a behaviour-neutral simplification, not a silent
  widening. Worth a one-line docstring note for the next reader who has to re-derive this, but not a
  blocker. (Optional.)

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read. Read `debug.md`/`implementation.md` in full, the complete source diff
(`position_belief.py`), both test file diffs in full, the ROADMAP/backlog entries touched, and both
new `tools/` scripts' structure (not every line of their ~1300 combined lines, but their module
docstrings, CLI/argparse shape, and grep-checked for scratchpad paths and the test-only ground-truth
probe's containment). Ran `ruff format --check`, `ruff check`, `mypy --strict`, and the full
`pytest -q` suite myself in this worktree rather than trusting the reported numbers, and they match
exactly (3045 passed, 4 xfailed, 0 failed).
