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
