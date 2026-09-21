### Review Summary

Reviewed `feature/group-detectability` against `plans/group-detectability/plan.md` and
`plans/group-detectability/implementation.md` (5 commits: plan, Stage 1 split, Stage 2 wiring,
Stage 3 calibration validation, Stage 4 roadmap/docs, plus a constant correction). Full read of
`visibility.py`, `clustering.py`, `group_salience.py`, `naked_eye_source.py`,
`detection_trace.py`, and the corresponding test diffs.

**Priority 1 — clustering floor.** Verified. The floor (A) now checks
`theta_sep * M >= RESOLUTION_ANGULAR_RADIUS_RAD` instead of `LOWRES_ANGULAR_RADIUS_RAD`, both in
the docstring's restated proof and in `_separable`. Empirically confirmed the fix is load-bearing,
not cosmetic: reverting `clustering.py`'s import to alias `RESOLUTION_ANGULAR_RADIUS_RAD` back to
`LOWRES_ANGULAR_RADIUS_RAD` makes
`test_group_admitted_pair_would_have_wrongly_merged_under_the_old_lowres_floor` fail exactly as
predicted (two genuinely separable group-admitted candidates collapse into one cluster). Restored
after the check; `git status` confirms no residual diff. The proof's premises (both admission
paths, `theta_size * M >= RESOLUTION_ANGULAR_RADIUS_RAD` either way) are now stated in the
docstring rather than assumed. This is the third documented visit to this floor and the module
docstring says so explicitly — agreed with the plan's own framing that it carries more weight than
its form admits; worth a standing test (already present) rather than a one-off fix each time a new
admission path is added.

**Priority 2 — infantry prediction, computed independently.** `1.8 / 0.00128 = 1406.25 m`,
below the 1.91 km "no infantry" rung, confirmed by hand and matching
`test_infantry_group_admitted_ceiling_predicts_the_1_91km_rejection`'s own assertion
(`pytest.approx(1406.25, abs=0.1)`). This is a real out-of-sample prediction — the 1.91 km rung was
never used to fit either constant — and it holds with 525 m (38%) of margin, independent of the
5.44 km rounding-direction question below. This is the strongest evidence in the diff that the
resolution/salience split is a real distinction and not just a curve fit.

**Priority 3 — the constant correction.** Verified. `RESOLUTION_ANGULAR_RADIUS_RAD` is `0.00128`
in the shipped code (`7 / 0.00128 = 5468.75 m`), not the plan's `0.0013`. The reasoning holds: the
plan's figure was `7/5440` rounded up, which tightens the threshold and leaves the 5.44 km rung
(the constant's own calibration point) 55 m outside it — the opposite of `LOWRES`'s established
rounding-down convention, which keeps its own calibration point inside. All three affected tests
now assert the corrected property rather than documenting the old behaviour:
`test_group_admission_at_the_derived_resolution_boundary` (vision_calibration) admits exactly at
5440 m and rejects at 5600 m against the 5468.75 m boundary;
`test_group_salient_admits_a_candidate_between_the_salience_and_resolution_thresholds` and
`test_group_salient_candidate_beyond_the_resolution_threshold_is_still_rejected` (test_visibility)
both use 5384/5470 m against the 5468.75 m boundary and document in their own docstrings what the
number was before the fix. None of the three silently kept asserting the wrong-way behaviour.

**Priority 4 — purity and layer boundary.** `group_salience.py` has no state, no clock, and no
`belief` import (`grep -n "import belief\|from belief" src/perception/*.py` — empty). It reads
positions/sizes only and returns a `frozenset[int]`. `check_visibility` stays per-candidate — the
set-ness (`group_salient_ids`) is resolved once per poll in `naked_eye_source.poll`, before the
per-candidate loop, exactly mirroring the existing `gaze_for` precedent one line above the same
call site. Confirmed the diff moves nothing of that shape into `check_visibility` itself; it only
gained a boolean.

**Priority 5 — stated assumptions.** `GROUP_MIN_MEMBERS = 3` and
`GROUP_COHESION_GAP_UNIT_WIDTHS = 10.0` are both explicitly labelled "stated assumption" in their
own docstrings in `group_salience.py`, not presented as derived. Pattern/count exclusion is
likewise argued in the module and plan docstrings on the n=1-dataset grounds stated in the brief.

**Priority 6 — LOWRES/MEDRES/HIRES untouched.** Confirmed by diff: the hunk touching
`visibility.py`'s constant block only adds `RESOLUTION_ANGULAR_RADIUS_RAD` after
`HIRES_ANGULAR_RADIUS_RAD`; `LOWRES_ANGULAR_RADIUS_RAD = 0.003`,
`MEDRES_ANGULAR_RADIUS_RAD = 0.014`, `HIRES_ANGULAR_RADIUS_RAD = 0.028` are untouched by any hunk.
`test_group_salience_does_not_affect_medres_or_hires_thresholds` pins 500 m/250 m explicitly.

**Test-impact list accuracy.** The plan's Affected Modules/Files list names exactly the files
touched (`visibility.py`, `group_salience.py` new, `clustering.py`, `naked_eye_source.py`,
`detection_trace.py` docstring-only, `ROADMAP.md`, and edits to
`test_visibility.py`/`test_clustering.py`/`test_vision_calibration.py`/`test_naked_eye_source.py`
plus a new `test_group_salience.py`) — matches the actual diff with no surprises. Nothing in
`belief/`, `optics.py`, `object_model.py`, or `callout-scheduling` was touched, matching the plan's
explicit "Not touched" list.

**Checks (body-layer/ only):**
- `ruff format --check src tests` — pass (85 files already formatted)
- `ruff check src tests` — pass
- `cd body-layer && mypy src` — pass, no issues in 40 source files
- `pytest tests -q` (with both `PYTHONPATH` entries) — 861 passed, 4 xfailed, matching the
  implementer's reported baseline delta (+19 tests, 0 regressions)
- `git status --porcelain` — clean

### Required Fixes

- **`body-layer/ROADMAP.md`'s milestone entry is now stale against the shipped code.** It was
  written in Stage 4 (`c6407ae`), before the constant-correction commit (`b863119`) landed, and was
  never updated afterward. It currently states `RESOLUTION_ANGULAR_RADIUS_RAD` is `0.0013` (three
  places), reproduces the infantry ceiling as `1385 m` (the old, wrong figure — the corrected
  constant gives `1406.25 m`), and says the 5.44 km rounding discrepancy was "left as-is" / "not
  this stage's decision" — which is no longer true, it *was* fixed in this same feature, one commit
  later. A reader of this milestone entry (which is this subproject's stated source of truth for
  milestone status, per `body-layer/CLAUDE.md`) would conclude the wrong constant shipped and that
  a known discrepancy is still open, when neither is the case. This is a documentation-accuracy
  defect in the same class the plan's own Risks section is careful about elsewhere, and it should
  be fixed before merge — update the three `0.0013`/`1385 m` figures to `0.00128`/`1406.25 m` and
  replace the "left as-is, not this stage's decision" paragraph with a short note that the
  discrepancy was caught and fixed in this same feature (pointing at `implementation.md`'s
  "Notable Discoveries" section, which already has the correct account).

### Optional Refinements

- **Plan arithmetic slip, not load-bearing (the "one plan defect per slice" pattern).** The plan's
  "Where the set-ness lives" section says "7 m at 500 m is 0.014 rad, ~6× the salience threshold"
  — `0.014 / LOWRES_ANGULAR_RADIUS_RAD (0.003) ≈ 4.7×`, not 6×. Doesn't change the section's
  conclusion (the group term is inert at short range regardless of whether the margin is 4.7× or
  6×, since either way every member individually clears salience), and nothing in the shipped code
  depends on the exact multiple — flagging only because the brief asked to look, and because
  historically each slice has carried exactly one such slip. No code or test change needed.
- **Counting/individuation over-claim on newly-admitted distant groups** is explicitly named as an
  accepted, undone risk in both the plan and the ROADMAP entry (twelve angularly-separable dots
  each reporting as `OP_1UNIT` where the pilot says "cannot tell how many") — correctly scoped out
  of this plan rather than silently left. No action needed here; noting it only so it isn't lost
  before the next sortie.

### Verdict

APPROVED WITH MINOR FIXES

The code, tests, and invariants are sound — the three named priorities (clustering floor, infantry
prediction, constant correction) all independently verify, purity and the assumption-labelling are
clean, and LOWRES/MEDRES/HIRES are untouched. The one required fix is documentation-only
(`ROADMAP.md` trailing the code by one commit) and does not need another Implementer pass through
the code itself — a direct doc edit is enough before merge.

### Review Confidence

Full read. All six priority items and the test-impact-list/plan-defect checks were verified
directly (diff read, independent arithmetic, and one empirical revert-and-rerun of the clustering
floor fix), not taken on the implementer's word; the full body-layer verification sequence was
re-run from this worktree rather than trusted from the implementation notes.
