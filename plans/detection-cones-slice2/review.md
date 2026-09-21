### Review Summary

Reviewed commits `665821f` (production), `bfb57c4` (tests), `9b819ba` (implementer memory) on
`feature/cones-2c-scan-loop` (base `19180a0`, 2A/2A.5/2B already merged) against the 2C sections of
`plans/detection-cones-slice2/plan.md` and the implementer's memory note
(`.claude/agent-memory/implementer/project_cones_2c_scan_loop.md` — no `implementation.md` entry
exists for 2C; see Required Fixes).

Full verification run from this worktree (detached at `9b819ba`, using the main checkout's
`body-layer/.venv` interpreter):

```
ruff format --check src tests   -> 83 files already formatted
ruff check src tests            -> All checks passed!
mypy src                        -> Success: no issues found in 39 source files
pytest tests -q                 -> 830 passed, 4 xfailed
```

Matches the implementer's reported 810→830/4 xfailed delta exactly.

**1. Purity/determinism (priority 3).** `gaze_at(t_sim, plan)` in `perception/gaze.py` is a pure
function — table lookup + modulo, no mutation, no wall clock. `ScanPlan` is a frozen dataclass with
a `__post_init__` invariant (`commanded_sector is None` iff `command_t_sim is None`).
`NakedEyePerceptionSource.poll()` recomputes `gaze = gaze_at(now_sim, self.scan_plan)` fresh every
call, never caches it. The only mutable state added is the two acquisition dicts
(`_previously_seen_at`/`_acquired_at`), which are documented and tested as a pure function of the
*frame sequence* (`test_replaying_the_same_stream_twice_yields_identical_observations` replays two
independently-constructed sources over the same frame list and asserts byte-identical output,
including which specific `t_sim`s admit the contact — not just a matching count). Confirmed by
inspection: no wall-clock read (`time.time()`) anywhere in `gaze.py` or the new
`naked_eye_source.py` code, `t_wall` is excluded from the determinism comparison with a comment
explaining why. `perception → belief` import direction check: `grep` found no `belief` import
anywhere under `src/perception/`; `belief/decay.py` and `belief/attention.py` both import from
`perception.gaze`, the allowed direction.

**2. The two `OBSERVED_WINDOW_S` decay bounds (priority 4).** The derivation
(`SCAN_CYCLE_PERIOD_S - FOCUS_DWELL_S = 14 < OBSERVED_WINDOW_S = 16 < POSITION_HALF_LIFE_S = 30`) is
recorded in both `perception/gaze.py`'s module docstring and `belief/decay.py`'s own comments next
to the constant — a later reader hits it in the file that uses it, not only in the plan.
`decay.py` additionally enforces both bounds as module-level `assert` statements that fire at
import time. The corresponding pytest tests (`test_observed_window_clears_the_worst_case_flank_gap`,
`test_observed_window_does_not_collapse_the_tracked_band`) compute the identical predicate the
module-level asserts already enforce — they can only ever pass or crash the whole suite at
collection (the module-level assert fires first), so they don't add independent failure-catching
power beyond the asserts. This isn't wrong — the plan explicitly asks for "two assertion tests" and
these do pin the current values as documentation — but it's worth naming: the real protection is the
module-level `assert`, not the pytest wrapper. Flagged as optional, not required.

**3. The plan-defect resolution — commanded-sector sub-cycling (priority 2).** Judged sound. The
plan's Implementation Plan step 12 literally names only the free-scan table, but hard part 1
("a commanded scan is a function of sim time relative to the command time") and the user's own
quoted words in hard part 2a ("within a sector it is itself a smaller cone moving in a scan
pattern") point at exactly this generalisation, and the literal-narrow reading would leave
`ScanPlan.command_t_sim` unused for a commanded sector — dead data hard part 2a explicitly says
should be load-bearing. Checked for downstream breakage: no code outside `gaze.py`/tests reads
`Gaze.label` (`grep` confirms), so the relabelling from sector names (`"left"`) to o'clock names
(`"11_oclock"`) touches nothing else. Crew speech callouts (`crew_console.py`'s
`_RELATIVE_SCAN_TOKENS`/readback phrasing) say "scanning left arc," which remains true under
sub-cycling and doesn't imply static coverage — no false claim introduced. `ahead` degenerates to a
static single-leg cone by construction (`len(legs) == 1`), which is exactly why 2B's existing
"commanded ahead is static" tests (`test_emission_pipeline.py`, `test_mock_flight_chain.py`) still
hold unmodified in behaviour, only in field name. Four dedicated tests in `test_gaze.py` cover the
free-scan table walk, `ahead`'s degenerate static case, `left`/`right`'s own 3-leg cycling, `full`
matching the free-scan table verbatim, and the command-relative-not-absolute-time property. This
reads as the correct call, not merely a defensible one, and it was flagged prominently rather than
slipped through — exactly per the pattern the last three slices set.

**4. Time-based acquisition / eviction (priority 5).** `_live_ids`/`_prune_stale` correctly key
eviction on `SCAN_CYCLE_PERIOD_S` (imported from `perception.gaze`, not re-declared). Traced both
`_acquire_on_change` and `_acquire_every_poll` by hand: neither leaks unbounded dict growth (pruned
every poll), the on_change "capped-out cluster is retried, not lost" property from 2A.5 is
preserved (unrefreshed timestamps age out and re-enter `known_ids` as false only after eviction, at
which point the cluster is eligible again), and `_acquire_every_poll`'s "known but not currently
visible stays acquired but doesn't emit" behavior is correct because emission is gated by
`clusters` (built from `visible`, i.e. this poll's gate survivors) intersected with `acquired_ids`,
not by `acquired_ids` alone.

**5. Moved test expectations (priority 1).** Spot-checked several independently rather than trusting
the commit message/memory note:
- `_CAP_TEST_CROSS_OFFSETS_M`'s 0.85× rescale: the docstring states concrete margins (max 12.77° of
  15° half-width; worst pairwise separation 0.30° vs. the old 0.37°) computed against
  `perception.clustering`'s real functions, not eyeballed. Consistent with the stated 0.85× factor
  applied to `(0.0, 40.0, 65.0, 85.0, 105.0)` → `(0.0, 34.0, 55.0, 72.25→72, 89.25→89)` — matches.
- The `COCKPIT_MASK` → `GAZE` trace-outcome move (`test_gate_rejected_candidates_are_never_
  annotated`): correct — max gaze-cone reach from boresight is 90° (leg centre) + 15° (half-width) =
  105°, well short of the ±130° cockpit envelope, so an astern (180°) candidate is rejected by GAZE
  under any `ScanPlan` before it can reach COCKPIT_MASK. The companion test exercising the mask
  directly (`gaze=None` via `check_visibility`) is untouched, so mask coverage isn't lost, only
  relocated.
- The two debounce "leave and re-enter" tests widened past 16 s: checked
  `test_candidate_leaving_and_re_entering_the_visible_set_re_emits`'s new gap (0.0 → 16.1 → 16.3) —
  16.1 > `SCAN_CYCLE_PERIOD_S` clears eviction, and 16.1 % 16.0 = 0.1 keeps poll 3 in the same
  free-scan "12 o'clock" leg as poll 1, so the gaze gate is provably not the reason re-emission
  happens — the test still exercises the debounce/eviction logic it was written for, not a
  gaze-gate accident.
- `_replay_with_trace_sink`'s persistent `ScanPlan(commanded_sector="right", command_t_sim=96.0)`:
  verified object 102's claimed ~97.1° azimuth sits inside the "3 o'clock" leg's [4,6)s window at
  the fixture's actual sim-time span with 7.1° of margin — not axis-aligned to the leg's own centre
  (90°), which is a genuine non-trivial check of the wedge boundary, not a trivial dead-centre case.
- The subject-drift check the priorities called for: none of the moved tests changed what they were
  actually testing. The `on_change`/`every_poll` acquisition tests still exercise acquisition logic
  at their new sim times; the tier-threshold tests (`test_hires_range_candidate_...`,
  `test_medres_range_candidate_...`, etc.) only had their poll `now_sim` shifted from `100.0` to
  `0.0` with geometry otherwise untouched, still landing in the "12 o'clock" leg by construction
  (dead-ahead candidates), so they still test the visibility-tier logic they were written for.

**6. Angular-formula coverage.** `_gaze_for_clock_hour`'s own formula is simple modular arithmetic
over 8 fixed multiples of 30°, adequately covered by the parametrized table-walk test including the
wrap boundary (`t_sim=16.0` → back to `12_oclock`). The underlying angular primitive it depends on
(`within_gaze`) already carries non-axis-aligned and 180°-seam-wrapping tests from 2B
(`test_within_gaze_at_a_non_axis_aligned_angle`, `test_within_gaze_wraps_across_the_180_seam`),
unchanged by this slice. No new angular formula was introduced that lacks a non-axis-aligned test.

**7. Scope (priority 6).** `git diff 19180a0 9b819ba --stat` touches exactly `perception/gaze.py`,
`perception/naked_eye_source.py`, `belief/decay.py`, `logger.py`, their tests, and agent-memory —
matches the plan's 2C file list precisely. `optics.py`, `object_model.py`, `visibility.py`,
`clustering.py`, `association.py`, `belief/contacts.py` are all untouched, confirming 2A/2A.5/2B's
constants and mechanisms are undisturbed. No 2D code (no dwell state, no `BINOCULAR_OPTIC` caller)
exists on this branch.

### Required Fixes

- **Stale field names in `naked_eye_source.py`'s own module docstring.** Point 5 of the module
  docstring (lines documenting the group-intake cap) still says `_previously_visible_ids` (twice)
  and `_acquired_ids` — the exact fields this same commit renamed to `_previously_seen_at` and
  `_acquired_at` in point 4a, a few paragraphs above. A future reader searching the source for
  `_previously_visible_ids` after reading point 5 will not find it. Trivial to fix (find/replace
  within the docstring), but it's a real leftover from an incomplete rename inside the commit that
  did the renaming, not a pre-existing issue being carried forward.
- **No `implementation.md` entry for 2C.** 2A, 2A.5, and 2B each have their own dated section in
  `plans/detection-cones-slice2/implementation.md`; 2C does not — only the agent-memory note
  (`project_cones_2c_scan_loop.md`) records the work, including the plan-defect finding (the
  commanded-sector sub-cycling generalisation) that this review confirms as a genuine, well-reasoned
  design call. The implementer's own memory index (`feedback_implementation_log_append.md`) states
  multi-stage plans share one `implementation.md` and it should be appended to, not skipped. Since
  `implementation.md` — not agent-memory, which is implementer-role-scoped and not part of the
  project's own review trail — is this project's durable, plan-scoped record, the 2C design call and
  its justification should be appended there before DoD, mirroring the format the three prior
  sections already established.

### Optional Refinements

- `test_decay.py`'s two `OBSERVED_WINDOW_S` bound tests (`test_observed_window_clears_the_worst_
  case_flank_gap`, `test_observed_window_does_not_collapse_the_tracked_band`) recompute the exact
  predicate `belief/decay.py`'s own module-level `assert` statements already enforce at import time.
  A future value violating either bound would crash the whole suite at collection before either test
  could report a distinct failure. Harmless and matches the plan's literal request for "two
  assertion tests," but the real protection is the module-level `assert`, not these — worth knowing
  if either test is ever "strengthened" under the impression it's the only thing enforcing the bound.

### Verdict

APPROVED WITH MINOR FIXES

Both required fixes are small, low-risk, non-behavioural (a docstring correction and a
documentation-log append) and do not warrant a return trip through Implementer→Reviewer — they can
be applied directly before DoD. No correctness, invariant, determinism, or scope issue was found in
the production code or its tests.

### Review Confidence

Full read. All three commits' diffs were read in full (not sampled), the full body-layer
format/lint/type/test sequence was run and its output confirmed against the implementer's reported
numbers, purity/determinism and the belief→perception import direction were checked by direct
inspection and `grep` rather than assumed from the docstrings, and the specific numeric claims in
the "moved expectations" commit message (rescale factors, azimuth margins, the trace-outcome move)
were independently re-derived rather than trusted at face value.
