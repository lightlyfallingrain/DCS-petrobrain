### Implementation Summary

Built in three commits, matching the plan's own two-stage split (Stage 1 behaviour-preserving,
Stage 2 the behaviour change) plus a third commit for Stage 3's calibration validation. Stage 4
(trace/docs) folded into Stage 1 and this file, since `threshold_bound`'s `"group_resolution"`
value is mechanically part of the same `check_visibility` edit as the constant split — splitting
it into a separate commit would have meant re-touching the same lines twice for no seam benefit
(Stage 1 stayed behaviour-identical regardless, pinned by its own regression test).

### Files Changed

- `body-layer/src/perception/visibility.py` — adds `RESOLUTION_ANGULAR_RADIUS_RAD` (0.0013);
  `check_visibility`/`_achieved_tier` gain `group_salient: bool = False`; new private
  `_presence_angular_radius_rad` helper is the single place both the admission gate and
  `_achieved_tier`'s own `presence_threshold_m` read the effective radius from, so they can't drift
  apart. `threshold_bound` gains `"group_resolution"`.
- `body-layer/src/perception/clustering.py` — floor (A) now checks against
  `RESOLUTION_ANGULAR_RADIUS_RAD`, not `LOWRES_ANGULAR_RADIUS_RAD` (the plan's named Stage 1
  correctness fix). Docstring rewritten with a new "Group-detectability: the floor must use the
  loosest admission threshold" section.
- `body-layer/src/perception/detection_trace.py` — docstring only, documents the new
  `threshold_bound` value.
- `body-layer/src/perception/group_salience.py` — **new**. `group_salient_ids(candidates, observer,
  optic) -> frozenset[int]`, pure, no state, no clock, no `belief` import. Single-link union-find
  over `_cohesive` (reusing `clustering.angular_separation_rad`/`angular_size_rad`, not
  `clustering`'s own merge threshold), restricted to candidates that pass `_resolvable`
  (`RESOLUTION_ANGULAR_RADIUS_RAD` at the optic's `presence_range_mult`). `GROUP_MIN_MEMBERS = 3`,
  `GROUP_COHESION_GAP_UNIT_WIDTHS = 10.0`, both stated assumptions per the plan.
- `body-layer/src/perception/naked_eye_source.py` — `poll()` computes `salient_ids` once per poll,
  before the per-candidate `check_visibility` loop, over the un-gazed candidate pool; threads
  `group_salient=candidate.object_id in salient_ids` through. Module docstring gains point "1a".
- `body-layer/ROADMAP.md` — milestone entry.
- Tests: `body-layer/tests/test_group_salience.py` (new), edits to `test_visibility.py`,
  `test_clustering.py`, `test_vision_calibration.py`, `test_naked_eye_source.py` (see below).

### Tests Added

- `test_group_salient_default_is_behaviour_identical_to_before_the_parameter_existed` — Stage 1
  regression pin.
- `test_group_salient_admits_a_candidate_between_the_salience_and_resolution_thresholds` /
  `test_group_salient_candidate_beyond_the_resolution_threshold_is_still_rejected` — the presence
  threshold relaxes but doesn't disappear.
- `test_group_salient_trace_records_group_resolution_as_the_threshold_bound` /
  `test_ordinary_admission_trace_still_records_size_curve_not_group_resolution` — the new
  `threshold_bound` value.
- `test_group_admitted_pair_would_have_wrongly_merged_under_the_old_lowres_floor` (clustering) —
  reproduces the concrete floor (A) defect the plan's Risks section names, at the *resolution*
  detection limit, proving the fix in effect.
- `test_group_salience.py` (5 tests) — cohesion/mass predicate in isolation: a group of 3 forms, a
  pair doesn't, non-cohesive candidates don't group, an unresolvable candidate is excluded without
  blocking the rest, empty input.
- `test_vision_calibration.py` (6 tests) — the plan's named Stage 3 ground truth: 4 km/3 km group
  admission, the 5.44 km boundary (see Notable Discoveries), the infantry out-of-sample prediction,
  a lone-unit guard, MEDRES/HIRES unaffected at 500 m/250 m.
- `test_naked_eye_source.py` (2 tests) — the real `poll()` pipeline wiring, not `visibility.py`
  called directly: three group-mates beyond `LOWRES` get admitted together; the same lone candidate
  at the same range still doesn't.

### Checks

(body-layer/ only — no other subproject touched)
- ruff format --check: pass
- ruff check: pass
- mypy src (strict): pass, `cd body-layer && mypy src` — no issues in 40 source files
- pytest -q: pass, 861 passed, 4 xfailed (baseline was 842 passed, 4 xfailed; +19 new tests, 0
  regressions, xfailed count unchanged)

### Notable Discoveries

- **The 5.44 km rung, as the plan's own literal constant computes it, does not admit.** Plan's
  `RESOLUTION_ANGULAR_RADIUS_RAD = 0.0013` is `7 / 5440 = 0.0012868` rounded **up**. Rounding up
  *tightens* the threshold (bigger angular-radius requirement = shorter range), the opposite of
  `LOWRES_ANGULAR_RADIUS_RAD`'s own established precedent (`7 / 8890 * 4 = 0.00315` rounded *down*
  to 0.003, deliberately loosening so its own calibration point — the farthest photographed range —
  stayed admitted). The result: `7 / 0.0013 = 5384.6 m`, ~55 m (1%) short of the photographed
  5440 m rung. At exactly 5440 m a member's own `theta_size` (0.0012868) sits fractionally below
  `RESOLUTION_ANGULAR_RADIUS_RAD`, so it fails `_resolvable` outright — no group forms at all, and
  `check_visibility` rejects it even with `group_salient=True` forced.

  This is not something implementation introduced — the plan's own worked table already showed
  `"5385 m"` against a `"5.44 km"` rung, i.e. the discrepancy is visible in the plan text itself,
  but Stage 3's prose still calls the rung "admitted (marginal)" and lists it as ground truth to
  encode. Implemented per the plan's explicit constant (0.0013, Stage 1, not this stage's decision
  to relitigate); `test_group_admission_at_the_derived_resolution_boundary` documents exactly what
  the code does (admits at 5380 m, rejects at the photographed 5440 m) rather than back-fitting the
  test to a number the code doesn't produce. **Worth the user's attention**: either the constant
  should be tightened toward 0.00128 (admitting the exact photographed rung, matching the rounding
  direction `LOWRES` already established), or the plan's prose should say "5.44 km, right at the
  model's own conservative boundary" rather than "admitted."

- **The infantry prediction holds with real margin, unaffected by the above.** `1.8 / 0.0013 =
  1384.6 m`, 525 m (38%) short of the photographed 1.91 km "no infantry" rung — robust to the
  5.44 km rounding-direction question above, since it's a fresh prediction rather than a
  refitting of the same calibration point.

- **`GROUP_COHESION_GAP_UNIT_WIDTHS`'s cohesion test is range-invariant by construction.** Both
  sides of the cohesion inequality (`theta_sep` for a fixed linear spacing, and `mean_unit_rad`)
  scale as `1/range`, so whether a 200 m/12-unit line reads as cohesive doesn't depend on range at
  all — confirmed directly rather than assumed (see `group_salience.py`'s module docstring and the
  worked ratio in the plan: 2.6 unit widths measured vs. 10.0 threshold, ~4x slack, independent of
  range).

- **No existing test in the 842-test baseline exercised the new group-salience path** — the full
  842-test baseline count was unchanged in the diff between Stage 1 and Stage 2 (848 after Stage 1's
  own new tests, 853 after Stage 2's wiring landed with zero regressions to the 848), meaning no
  pre-existing fixture happened to contain 3+ resolvable, cohesive candidates beyond `LOWRES` — the
  new behaviour was genuinely inert until this plan's own new tests exercised it deliberately.
