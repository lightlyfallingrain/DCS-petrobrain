### Review Summary

Reviewed commit `ba4e40f` ("Cones 2A: per-tier optic multipliers, distinctiveness, and the
clamp") on `feature/cones-2a-tiers-distinctiveness` against the 2A sections of
`plans/detection-cones-slice2/plan.md`, `plans/detection-cones-slice2/implementation.md`, and
`body-layer/research/2026-09-21-slice2-model-decisions.md`.

Every claim in the commit message and `implementation.md` was checked against the actual diff,
not taken on trust, per the priorities given:

1. **Fixture rewrites.** Re-derived by hand every re-derived boundary called out in
   `implementation.md`: infantry 1.8 m / LOWRES 0.003 = 600 m presence (exact match to the
   decisions doc's naked-eye observation); the detection-trace 250 m case (presence 600, class
   clamps to 600, type 64.29 → `medres`, matching the updated assertion); the two xfailed
   calibration rows (`8/0.003*2.42 = 6453.33 m` < 6580/8890; `8/0.028*3.00 = 857.14 m` < 1000 m,
   `8/0.014*3.50 = 2000 m` also short of 1000 m so the row resolves `medres`); and the new
   `test_binocular_presence_threshold_for_a_7m_object` boundary (`7/0.003*2.42 = 5646.67 m`).
   All check out arithmetically — these are genuinely derived, not back-fit from observed test
   output.
2. **The two new xfails in `test_vision_calibration.py`.** Confirmed both are caused exactly as
   claimed (per-tier multipliers below the old flat 4.0 at the two ground-truth points those
   constants were themselves derived against), derivations are correct, and nothing else in that
   file was weakened — every other row (`C-5040m` down to `C-503m`, plus the two `medres` rows)
   still passes, verified by running the suite.
3. **The clamp reproduces the measurements.** `class = min(presence, ...)`, `type = min(class,
   ...)` — nested `min()` calls make `type <= class <= presence` a mathematical certainty for any
   real-valued multipliers/distinctiveness, not merely for the shipped table. The property test
   (`test_tier_thresholds_never_invert`) checks it across every named profile × both shipped
   optics; hand-checked it additionally against the unshipped 9K113 narrow figures (5.81/13.75/15.00,
   distinctiveness 5.0) — still holds. Infantry's clamp collapses class onto presence at every
   optic exactly as claimed (naked: 600≈600; binocular: min(1452, 2250)=1452; narrow:
   min(3486, 8839)=3486) — the *structural* collapse (ratio 1.00) reproduces; the absolute figures
   differ from the decisions doc's directly-measured presence values (2.0 km/4.5 km vs. computed
   1452 m/3486 m), which is the already-documented "known unmodelled residual," not a defect here.
4. **Clustering floor fix.** `_separable`/`cluster_candidates` now take `presence_range_mult`
   instead of importing `BINOCULAR_RANGE_MULTIPLIER`; `naked_eye_source.py` threads
   `UNAIDED_OPTIC.presence_range_mult` through, unchanged behaviour for the only optic actually in
   use. `test_floor_would_have_broken_under_the_old_hardcoded_constant` directly demonstrates the
   defect (floor fails at the old hardcoded 4.0 for a pair admitted under 5.81) and the fix (holds
   under the real multiplier, and `cluster_candidates` still resolves them as separate clusters).
5. **Distinctiveness values.** Infantry 5.0 and S-300 2.6 are both derived (not invented) and the
   derivation is in the code, not only the research doc — `object_model.py`'s comments state the
   arithmetic (128 m vs 600 m needing ~4.7x; `4500/1714 = 2.6`) inline at the constant/field
   declaration, satisfying the "estimate flags must reach the code" standard from prior review
   findings.
6. **Scope.** No `gaze.py`, `ScanPlan`, or scan-loop code exists on this branch. `LOWRES_
   ANGULAR_RADIUS_RAD`/`MEDRES_ANGULAR_RADIUS_RAD`/`HIRES_ANGULAR_RADIUS_RAD`/`NAKED_EYE_RANGE_
   CAP_M` constant *values* are unchanged (only their consumers changed). `belief/decay.py` has no
   diff in this commit. `grep` over `body-layer/src/perception/` found no `belief` import. Aspect
   (`apparent_extent_m`) still only feeds `recognition_extent_m` (class/type), never
   `presence_size_m` — unchanged from before this slice.
   `BINOCULAR_RANGE_MULTIPLIER` and `Optic.magnification` are both fully deleted; every remaining
   grep hit is historical prose in docstrings/comments/test-derivation comments, not a live
   reference. The `optics.py → visibility.py` circular import is genuinely gone — `optics.py`'s
   diff removes its only import from `visibility.py`, and `visibility.py` now imports `Optic`/
   `UNAIDED_OPTIC`/`within_optic_fov` as an ordinary top-level import (the `TYPE_CHECKING` block is
   deleted).

Verification commands re-run directly from `body-layer/.venv`:
- `ruff format --check src tests` — pass (81 files already formatted)
- `ruff check src tests` — pass
- `python -m mypy src` — pass, no issues in 38 source files
- `python -m pytest tests -q` — **778 passed, 4 xfailed**, exactly as claimed

`git status` is clean for everything touched by this commit (the three untracked files in the
repo root are unrelated `world-model/` build artifacts, not part of this branch's work). No
debug prints, `TODO`/`FIXME`/`pdb`/`breakpoint` found anywhere in the diff.

One deviation from the plan is called out explicitly in the commit message and `implementation.md`
rather than hidden: plan step 6 said vehicle calibration rows must not move; the per-tier
multipliers alone (independent of distinctiveness) do move some, because `BINOCULAR_OPTIC`'s new
presence/type multipliers are individually lower than the old flat 4.0 those specific
angular-radius constants were derived against. This is a correct, unavoidable consequence of
moving to three independently-measured multipliers, is `xfail`ed with a full derivation (not
silently re-fit), and is reported as a "Notable Discovery" rather than worked around.

### Required Fixes

None.

### Optional Refinements

- `test_calibration_cluster_merge_undercount.py` now passes `BINOCULAR_OPTIC.presence_range_mult`
  explicitly, not `UNAIDED_OPTIC` (what production code actually calls `cluster_candidates` with
  today), because the fixture's own 9 km scenario predates optic multipliers and is only
  physically reachable under binocular-level range. This is documented in the module docstring and
  is a reasonable call, but it means this one fixture no longer tests the code path
  `naked_eye_source.py` actually exercises. Worth a follow-up note (or a second, `UNAIDED_OPTIC`-
  parameterised case) in whichever slice next touches this fixture, so the gap doesn't go
  unnoticed once an optic-selection mechanism lands in 2B. (Optional — no defect today, and the
  gap is already surfaced in the docstring.)
- The unshipped 9K113 narrow-sight numbers (5.81/13.75/15.00, referenced in `clustering.py`'s
  docstring and its regression test) live only in prose/tests, not as an importable constant —
  consistent with the deliberate scope cut, but if a future slice re-derives these from the
  decisions doc independently, a small risk exists of the two copies drifting. Not worth guarding
  against now given the explicit scope note in `optics.py`'s docstring.

### Verdict
APPROVED

### Review Confidence
Full read — read the 2A sections of the plan, `implementation.md`, and the decisions doc in full;
read the actual diff for every changed source file (`optics.py`, `object_model.py`,
`visibility.py`, `clustering.py`, `naked_eye_source.py`) and the key test additions
(`test_tier_thresholds_never_invert`, `test_infantry_class_clamps_to_presence_at_every_optic`,
`test_floor_would_have_broken_under_the_old_hardcoded_constant`, the two xfail blocks in
`test_vision_calibration.py`, the new `test_object_model.py` distinctiveness tests); hand-verified
the arithmetic behind every re-derived fixture value named in the priorities rather than trusting
the stated derivation; re-ran the full body-layer format/lint/type/test sequence myself from its
own venv and got the exact claimed result (778 passed, 4 xfailed).

---

## 2A.5: intake cap counts groups, not objects (review, 2026-09-21)

Commits reviewed: `1d501c0`, `43c67aa`, `b973784`, `02d2abd`, scoped to the plan's 2A.5 sections
("2A.5 sits where it does..." and hard part 6a) and `implementation.md`'s 2A.5 log.

### Review Summary

`poll()` now clusters every gate-surviving candidate before the simultaneous-detection cap runs,
and the cap operates on clusters (`NAKED_EYE_MAX_NEW_GROUPS_PER_POLL`, value unchanged at 3).
Traced the acquisition-state split by hand against both `_acquire_on_change` and
`_acquire_every_poll`: `steady_ids | admitted_ids` correctly excludes a capped-out cluster's
not-yet-seen members from `_previously_visible_ids`, and every cluster returned from either
acquisition method is proven 1:1 with `_build_observations`' output (`_build_observation` always
emits exactly one `Observation` per cluster entry, so the `zip(to_emit, observations)` trace-sink
loop in `poll()` cannot desync) — no path exists for an object to be marked acquired without its
observation actually being emitted, or vice versa. Hand-derived the expected counts (3, then 2,
then 0) for the rewritten pinned test and they match the code exactly. No-omniscience-leak check
holds structurally: `visible` (what gets clustered) is built strictly from candidates that already
individually cleared `check_visibility`, and `DetectionTraceCollector.record()` is called by
`check_visibility` itself per-candidate before any clustering runs — the test's
`GateOutcome.ADMITTED` assertion is therefore checking the real gate, not something clustering
later asserts about itself. Only one other pinned test's *comment* (not assertions) was touched,
exactly as claimed. Re-ran the full body-layer verification sequence myself from its own venv:
`ruff format --check`, `ruff check`, `mypy src`, `pytest -q` all pass, 780 passed / 4 xfailed,
matching `implementation.md` exactly. Scope holds — no gaze/`ScanPlan`/dwell code, no touches to
`visibility.py`/`optics.py`/`object_model.py`/`decay.py`, no `perception → belief` import.

### Required Fixes

- **Stale reference to the renamed constant left in a live test file.** `body-layer/tests/
  test_detection_trace.py:259`, in `test_admitted_but_throttled_candidate_stays_unannotated`,
  still reads `# NAKED_EYE_MAX_NEW_PER_POLL is 3 -- four simultaneous admissions means...`. This
  file wasn't touched by any of the four 2A.5 commits, so the rename in `naked_eye_source.py`
  didn't propagate to it. The test's behavior is unaffected (each of its four candidates is its
  own separable group, so per-object and per-group throttling agree here too), but the task's own
  scope item 6 explicitly calls for "no stale references to the old constant name anywhere," and a
  grep confirms this is the one place in `body-layer/src`/`body-layer/tests` that was missed.
  Trivial one-line comment fix.

### Optional Refinements

- **Plan step 6d's cost-verification note is missing from `implementation.md`.** The plan
  explicitly asks for "one line" confirming the clustering pair-loop stays cheap now that it runs
  over all gate-surviving candidates rather than the pre-cap subset. `implementation.md`'s 2A.5
  section documents the reordering, the tests, and the checks, but doesn't carry this line. I
  verified it myself: `cluster_candidates` is O(n²) over `visible`, and `visible` is exactly the
  set of candidates that individually passed `check_visibility` — the same population the plan's
  own trace measured at ~3.7 admissions/poll on average, so this is not a new unbounded quantity,
  just a reordering of when the same small population gets clustered. Not a functional risk, but
  worth adding the one-line confirmation to the log so the plan's own explicit ask isn't silently
  dropped. (Optional — verified independently, no defect found.)

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read — read the plan's 2A.5-relevant sections (slicing table, hard part 6a, implementation
steps 6a-6d) and `implementation.md`'s 2A.5 log in full; read the complete diff for all four
commits (`naked_eye_source.py`'s reorder and both acquisition methods, `detection_trace.py`,
`body-layer/CLAUDE.md`, the full test diff); hand-traced the acquisition-state split and the
rewritten pinned test's expected counts against the code rather than trusting the stated
derivation; grepped the full repo for the old constant name to check the "no stale references"
scope item; re-ran the full body-layer format/lint/type/test sequence myself from its own venv
(`body-layer/.venv`) and got the exact claimed result (780 passed, 4 xfailed).

## 2B: gaze as a filter (review, 2026-09-21)

Implementation commits: `5728841` (2B), `e520e8b` (plan correction on the `FULL_GAZE`/`None`
default, filed after the implementer caught the plan's own internal contradiction). Reviewed in an
isolated worktree per `AGENTS.md` "Where work happens" (rule 1); verification was run against
`e520e8b` in a separate temporary worktree since the branch was already checked out at
`/Users/sg/Code/DCS-petrobrain`.

### Review Summary

2B does exactly what its own acceptance gate demands and does it by construction, not by fixture
luck. The one interesting event in this slice is that the implementer caught a real error in the
plan itself — Hard Part 3 asserted `FULL_GAZE` (±90°) as the 2B default and called it a no-op,
but the cockpit mask's measured rear cutoff is ±130° (`cockpit_mask.py`, `rear_cutoff_deg=130.0`),
so a `FULL_GAZE` default would have silently narrowed live detection through the 90°–130° band —
the exact regression 2B exists to rule out. The implementer used `gaze=None` instead, and filed
`e520e8b` to correct the plan text rather than quietly building around the contradiction. Traced
this independently (`FULL_GAZE`'s definition in `gaze.py`, `cockpit_mask.py`'s `rear_cutoff_deg`,
`e520e8b`'s diff) — the deviation is correct, complete, and every default path (`check_visibility`'s
`gaze` parameter, `NakedEyePerceptionSource.gaze` field, `logger._active_gaze`'s no-pending-task
case) resolves to `None`, never to a narrowing value.

- **Behaviour-preservation (priority 1)**: confirmed structurally. `check_visibility(gaze=None)`
  skips the gaze gate entirely (`visibility.py`: `if gaze is not None and not within_gaze(...)`).
  `NakedEyePerceptionSource.gaze` defaults to `None`. `logger._active_gaze` returns `None` when no
  `scan_area` task is pending — there is no code path that manufactures a non-`None` gaze without an
  explicit F10 scan command. `test_default_gaze_is_none_and_does_not_narrow_the_cockpit_envelope`
  and `test_default_gaze_is_none_and_does_not_filter` pin this at both the `check_visibility` and
  `NakedEyePerceptionSource` layers with a candidate placed specifically in the 90°–130° band that a
  `FULL_GAZE` default would have wrongly rejected.
- **Vocabulary move (priority 2)**: `RelativeSector`/`RELATIVE_SECTORS`/the wedge table moved to
  `perception/gaze.py` verbatim; `belief/attention.py` re-imports `RelativeSector` (needed by three
  other importers) but does not re-export `RELATIVE_SECTORS` — grepped the full repo at the reviewed
  commit and nothing outside `gaze.py` itself ever imported `RELATIVE_SECTORS` from `belief.attention`,
  so this is dead-name removal, not a break. `angular_delta_deg` in `perception/geometry.py` is
  character-for-character the same formula as the deleted `belief.attention._angular_delta_deg`
  (`abs((a - b + 180.0) % 360.0 - 180.0)`), and both modules now import the one copy. `belief.attention.
  area_contains`'s own logic is otherwise untouched — confirmed by diff, not just by the module
  docstring's own claim. `perception` still does not import `belief` anywhere in this diff.
- **Gaze-first ordering (priority 3)**: `GateOutcome.GAZE` is a new enum member, evaluated and
  recorded before `COCKPIT_MASK`; `test_gaze_gate_runs_before_the_cockpit_mask` proves the ordering
  directly (a candidate that fails both records `GAZE`, not `COCKPIT_MASK`), not merely the pass/fail
  outcome. The trace's cost — losing the cockpit-mask rejection rate once a real gaze restriction is
  active — is documented in `GateOutcome.GAZE`'s own docstring exactly as the plan's hard part 3
  requires, and is inert under 2B's own default (`gaze=None` never fires `GAZE`), so nothing about
  today's trace output actually changes yet.
- **`Optic.peripheral` and the bypass rule (priority 4)**: `gaze_for` is a four-line pure function;
  tested in both directions in `test_gaze.py`
  (`test_gaze_for_bypasses_the_gate_for_a_peripheral_stimulus_under_unaided_optic`,
  `test_gaze_for_does_not_bypass_under_binocular_optic`, plus a third test against a synthetic
  non-peripheral `Optic` proving the rule reads `optic.peripheral` and not a hardcoded identity check
  against `BINOCULAR_OPTIC`). `test_gaze_for_returns_gaze_unchanged_for_a_non_stimulus_candidate` and
  `test_gaze_for_returns_none_when_no_gaze_is_active` confirm the rule is a true no-op against an
  empty `stimulus_ids` set (the only state that exists today, since no capture channel is wired). The
  bypass invariant — clears the gaze gate only, never cockpit mask/range/LOS — is separately pinned
  in `visibility.py`'s own test suite (`test_bypassed_gaze_still_respects_the_cockpit_mask`).
- **`Optic.boresight_azimuth_deg` removal (priority 5)**: became a required parameter on
  `within_optic_fov`; every existing call site (production and test) was updated to pass `0.0`
  explicitly where no gaze is active, reproducing the old pinned default exactly — confirmed no
  caller silently lost the boresight value. `check_visibility` now derives the boresight from
  `gaze.center_azimuth_deg` when a gaze is active, so the FOV cone genuinely follows the head rather
  than staying pinned forward; `test_optic_fov_boresight_follows_the_active_gaze` demonstrates both
  the admitted-with-gaze and rejected-without-gaze cases for the same off-axis candidate.
- **Angular-formula test coverage**: `test_within_gaze_at_a_non_axis_aligned_angle` (37°/42°) and
  `test_within_gaze_wraps_across_the_180_seam` (170° center, tested at −170° and 35°) both exercise
  genuinely non-axis-aligned angles and a wraparound case, per this review's own instruction and the
  plan's "milestone's own standing constraint" note (a prior bug in this codebase hid behind an
  axis-aligned-only suite). `test_gaze_gate_rejects_outside_wedge_and_admits_inside_it` uses a −60°
  gaze center at the `check_visibility` integration layer too, not just the unit layer.
- **Scope (priority 6)**: diffed the full file list touched between the 2A.5 merge point and this
  slice's tip — exactly the 13 files the plan's own "Affected Modules" 2B list names (`gaze.py`,
  `geometry.py`, `optics.py`, `visibility.py`, `detection_trace.py`, `naked_eye_source.py`,
  `belief/attention.py`, `logger.py`, and their six test files). No `ScanPlan`, `gaze_at`,
  `FOCUS_DWELL_S`, or `SCAN_CYCLE_PERIOD_S` anywhere in source (grepped). `clustering.py`,
  `object_model.py`, `decay.py`, `association.py`, `belief/contacts.py` untouched, as the plan
  requires.
- **The "zero existing expectations changed" claim**: verified against the diff, not merely trusted.
  Every change to an existing test file is either a pure addition (new test functions) or a
  mechanical call-site update forced by a signature change (`within_optic_fov` gaining a required
  `boresight_azimuth_deg` parameter) — same assertions, same expected values, just the new parameter
  threaded through. No existing assertion value moved. 810 passed / 4 xfailed reproduced exactly by
  re-running the suite myself (see Review Confidence).

The one thing worth naming without it being a fix: `Optic.peripheral` defaults to `True` on the
dataclass itself (rather than being a required field), so three synthetic `Optic(...)` instances in
`test_visibility.py` construct without ever setting it. This is the same "make the new field
inert-by-default so unrelated fixtures don't need touching" pattern the plan itself uses everywhere
else in this slice (`gaze=None`, `peripheral_stimulus_ids=frozenset()`), and the implementer's own
"Notable Discoveries" note calls it out explicitly as a deliberate, minimal-footprint choice rather
than an oversight. Confirmed correct: nothing turns on the FOV-gate tests' optics having peripheral
vision.

### Required Fixes

None.

### Optional Refinements

- **`test_optics.py`'s three test-site `_optic()` helper doesn't exercise `peripheral=False`
  through the FOV-gate tests** — every `within_optic_fov` test in that file uses the default
  `peripheral=True`, since `peripheral` has no bearing on `within_optic_fov`'s own geometry. Not a
  gap in this slice (the field is orthogonal to FOV geometry and is tested where it matters, in
  `test_gaze.py`/`test_optics.py`'s two dedicated `peripheral` tests) — noted only so a future reader
  doesn't mistake the absence for an oversight. (Optional — no defect, documentation note only.)
- **`logger._active_gaze`'s "most recently created wins" tie-break** iterates `reversed(tasks.tasks)`
  and returns on the first match, which assumes `TaskStore.tasks` is insertion-ordered. That
  assumption is correct today (confirmed by reading `belief/tasks.py`) and is exercised by
  `test_active_gaze_picks_the_most_recently_created_pending_task`, but the function's own docstring
  could say one sentence about relying on insertion order rather than a `created_sim` comparison, so
  a future change to `TaskStore`'s internal ordering doesn't silently break this in a way the test
  suite might not catch if a test ever inserts tasks with `created_sim` out of insertion order.
  (Optional — a documentation clarity note, not a correctness gap in the current implementation.)

### Verdict
APPROVED

### Review Confidence
Full read — read the plan's 2B section in full (module/hard-part list, hard parts 1/2a/3/4/5,
Implementation Plan steps 6-10) and `e520e8b`'s diff to `plan.md`; read every changed source file's
diff in full (`gaze.py` new module including its docstring, `geometry.py`, `optics.py`,
`visibility.py`, `detection_trace.py`, `naked_eye_source.py`, `belief/attention.py`, `logger.py`);
read every changed/added test file in full (`test_gaze.py`, `test_optics.py`, `test_visibility.py`,
`test_naked_eye_source.py`, `test_logger.py`); hand-verified `angular_delta_deg`'s formula is
identical to the deleted `belief.attention._angular_delta_deg` rather than trusting the docstring's
claim; grepped the full repo for `RELATIVE_SECTORS` and `within_optic_fov` call sites to confirm no
import broke and no caller lost the boresight value; grepped for 2C/2D-only names (`ScanPlan`,
`gaze_at`, `FOCUS_DWELL_S`, `SCAN_CYCLE_PERIOD_S`) to confirm scope; re-ran the full body-layer
format/lint/type/test sequence myself, in a separate temporary worktree checked out at `e520e8b`
(the branch tip was already checked out in the main working directory), using a fresh venv with
`ruff`/`mypy`/`pytest` installed, and got the exact claimed result (`ruff format --check`: pass,
`ruff check`: pass, `mypy src`: pass/39 files, `pytest -q`: 810 passed, 4 xfailed).
