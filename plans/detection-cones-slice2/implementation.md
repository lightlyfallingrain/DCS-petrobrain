### Implementation Summary

Implemented sub-slice **2A only** of the detection-cones slice 2 plan: per-optic per-tier
multipliers, per-op_class/per-type distinctiveness, the class-range clamp, and the
`clustering.py` acuity-floor fix. 2B/2C/2D (gaze, `ScanPlan`, scan-loop state,
`naked_eye_source.py` acquisition-set changes) were explicitly not touched, per scope.

### Files Changed

- `body-layer/src/perception/optics.py` — `Optic` loses `magnification`, gains
  `presence_range_mult`/`class_range_mult`/`type_range_mult`. `UNAIDED_OPTIC` = 1.0/1.0/1.0.
  `BINOCULAR_OPTIC` = 2.42/3.50/3.00 (BTR-60-derived, decisions doc). No longer imports from
  `visibility.py` (deleting `BINOCULAR_RANGE_MULTIPLIER` dissolved the circular import). 9K113
  wide/narrow multipliers (3.55/7.00/6.50, 5.81/13.75/15.00) are **not** added as named `Optic`
  instances — documented in the module docstring and referenced only where the clustering-floor
  derivation needs the narrow sight's 5.81, per the plan's explicit scope cut.
- `body-layer/src/perception/object_model.py` — `ObjectTypeProfile` gains
  `distinctiveness: float | None = None`. New `_OP_CLASS_DISTINCTIVENESS = {"OP_INFANTRY": 5.0}`,
  `_DEFAULT_DISTINCTIVENESS = 1.0`, and `distinctiveness_of(profile)` (per-type exception, else
  per-class default, else 1.0/"ordinary"). Both S-300 radar rows get `distinctiveness=2.6`
  (per-type exception, since `OP_LRSAM` also covers non-radar launchers).
- `body-layer/src/perception/visibility.py` — `_achieved_tier` now takes `optic: Optic` and
  `distinctiveness: float` instead of a flat `magnification`. Three thresholds, each chained
  through `min()` against the tier above it: `presence = size/LOWRES*presence_mult`,
  `class = min(presence, extent/MEDRES*class_mult*distinctiveness)`,
  `type = min(class, extent/HIRES*type_mult)`. The chained `min()`s make `type <= class <=
  presence` a structural guarantee, not a separately-checked clamp (plan step 4). The admission
  gate now uses `optic.presence_range_mult` (was `optic.magnification`). `BINOCULAR_RANGE_
  MULTIPLIER` deleted; `optics.py` imports collapsed to an ordinary top-level import (circular
  import gone).
- `body-layer/src/perception/clustering.py` — `cluster_candidates`/`_separable` take a new
  required `presence_range_mult: float` parameter, threaded into floor (A) instead of the
  hardcoded `BINOCULAR_RANGE_MULTIPLIER`. This is the fix for the latent defect the plan's "hard
  part 4" identifies: the old self-consistency proof for (A) only held while the active optic's
  presence multiplier was ≤ 4.0, and 9K113 narrow's 5.81 (not wired in this slice, but real)
  would have broken it.
- `body-layer/src/perception/naked_eye_source.py` — passes `UNAIDED_OPTIC.presence_range_mult`
  into `cluster_candidates` (the only optic `check_visibility` is called with today — no
  optic-selection mechanism exists until 2B).

### Tests Added

- `test_optics.py::test_binocular_optic_has_the_btr_60_derived_per_tier_multipliers` — pins the
  three BINOCULAR_OPTIC values.
- `test_object_model.py::test_ordinary_class_defaults_to_1` /
  `test_infantry_class_default_is_5` / `test_s300_radar_rows_carry_a_per_type_exception_not_the_
  class_default` / `test_per_type_exception_overrides_the_class_default` — `distinctiveness_of`'s
  resolution order (per-type exception, per-class default, global default).
- `test_visibility.py::test_tier_thresholds_never_invert` — property test, `type <= class <=
  presence` across every named profile in `object_model`'s two keyword tables × both shipped
  optics (plan step 4's mandated invariant test).
- `test_visibility.py::test_infantry_class_clamps_to_presence_at_every_optic` — the model's main
  evidence for decision 3: infantry's class threshold saturates to its own presence threshold at
  every optic (a range just inside presence still resolves `medres`, never `lowres`).
- `test_clustering.py::test_floor_would_have_broken_under_the_old_hardcoded_constant` — proves
  the clustering-floor defect directly: a pair admitted at the 9K113 narrow sight's real
  `presence_range_mult` (5.81) satisfies (A) when checked against that same multiplier, but fails
  (A) when checked against the old hardcoded `BINOCULAR_RANGE_MULTIPLIER` (4.0) — the exact
  mismatch the parameterisation fixes. Also confirms `cluster_candidates`, correctly
  parameterised, still resolves the pair as separate clusters.
- `test_visibility.py::test_binocular_presence_threshold_for_a_7m_object` — the new, correctly
  derived binocular presence threshold (5646.67 m for a 7 m object), replacing the ground-truth
  claim the xfail below documents as broken.

### Fixture/expected-value changes, with derivation

All derived from the model's own formulas (recomputed by hand and verified by running the
suite), not back-fit from observed output:

- **Infantry can no longer produce a presence-only (`lowres`) observation at any optic** (its
  `distinctiveness=5.0` saturates class to presence by design — this is decision 3's point).
  Every test that relied on an Infantry candidate landing in a genuine lowres-only band was
  switched to a non-distinctive object (Ural truck or T-72B, `distinctiveness=1.0`) at a
  re-derived boundary range:
  - `test_visibility.py`: `test_infantry_just_inside/outside_lowres_tier_range_*` →
    `test_armored_vehicle_just_inside/outside_lowres_tier_range_*` (T-72B, 500–2333.33 m band).
  - `test_visibility.py::test_default_optic_is_naked_eye`'s `downgraded_tier_candidate` → T-72B
    at 2000 m (presence 2333.33 m, class 500 m) instead of Infantry at 300 m.
  - `test_naked_eye_source.py::test_lowres_range_candidate_reaches_presence_level` → Ural truck
    at 1000 m (class 428.57 m, presence 2000 m) instead of Infantry at 400 m.
  - `test_detection_trace.py::test_admission_records_achieved_tier` — Infantry at 250 m now
    resolves `medres` (class threshold 600 m, clamped to presence), not `lowres`; expected value
    updated in place (this test isn't about the tier value specifically, just the trace
    mechanism, so the object wasn't swapped).
  - `test_visibility.py::test_higher_magnification_optic_extends_the_range_threshold` — Infantry
    at 610 m under `BINOCULAR_OPTIC` now resolves `medres` (class clamps to presence, 1452 m),
    not `lowres`.
- **`test_vision_calibration.py`** — this suite is CONTAMINATED (detection-aid dots) per its own
  docstring; 2A moved two real, known quantities:
  - `test_computed_tier_matches_ground_truth`/`test_gate_admits_every_photographed_range` needed
    `optic=BINOCULAR_OPTIC` passed explicitly (the function's new default is `UNAIDED_OPTIC`, a
    much tighter gate, since the old default resolved to the flat `BINOCULAR_RANGE_MULTIPLIER`).
  - Two genuine regressions, both `pytest.xfail`ed (not silently re-fit, not deleted) with
    `_KNOWN_TIER_REGRESSIONS`/`_KNOWN_GATE_REGRESSIONS`: `C-8890m`/`C-6580m` (gate) — an 8 m
    object's binocular presence threshold is now `8/0.003*2.42 = 6453.33 m`, below both real
    photographed ranges, because `BINOCULAR_OPTIC.presence_range_mult` (2.42, BTR-60-derived) is
    lower than the old flat 4.0 that `LOWRES_ANGULAR_RADIUS_RAD` was itself derived against at
    this exact 8.89 km ground-truth point. `C-1000m` (tier) — same mechanism for
    `type_range_mult` (3.00 < 4.0): the row now resolves `medres` instead of the photographed
    `type_recognizable`. Every other row (`C-5040m` down to `C-503m`) still matches.
  - `test_visibility.py::test_armored_vehicle_is_visible_at_the_farthest_photographed_range` —
    same underlying regression, `xfail`ed with a full derivation in the reason string; a new
    passing test (`test_binocular_presence_threshold_for_a_7m_object`) pins the actual new
    threshold instead.
- **`test_calibration_cluster_merge_undercount.py`** — all four `cluster_candidates(...)` calls
  needed the new required `presence_range_mult` argument. Passed `BINOCULAR_OPTIC.presence_
  range_mult` (2.42), not `UNAIDED_OPTIC`'s 1.0: this fixture's own 9 km detection range is only
  physically plausible under an optic with binoculars' reach (a 7 m object's `UNAIDED_OPTIC`
  presence threshold is 2333 m — `check_visibility`'s real gate would never admit this candidate
  in the first place under naked eye). Using `UNAIDED_OPTIC` here made floor (A) bind at naked
  eye's own coarser resolution and merge the fixture's "resolves individually at 9 km" headline
  case — documented in the module's own docstring, not silently switched without explanation.

### Checks

(body-layer/ only — no other subproject touched)

- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (strict): pass, no issues in 38 source files
- `pytest -q`: pass — 778 passed, 4 xfailed (baseline was 774 passing; net +4 xfail are the
  documented, real known regressions above, not silently swallowed failures)

### Notable Discoveries

- **The plan's "vehicle rows must not move" framing (step 6) was too narrow.** It reads as being
  about decision 3 (distinctiveness) only — but decision 1 (per-tier multipliers) *by itself*
  moves ordinary-vehicle calibration rows too, because `BINOCULAR_OPTIC`'s new presence/type
  multipliers (2.42/3.00) are lower than the old flat 4.0 the `LOWRES`/`HIRES_ANGULAR_RADIUS_RAD`
  constants were themselves derived against at specific ground-truth points (8.89 km/6.58 km for
  presence, 1000 m for type). This is a real, unavoidable consequence of moving from one flat
  multiplier to three independently-measured ones — the decisions doc's own "known unmodelled
  residual" note covers it in spirit, but the plan's step 6 statement should be read as "the
  *distinctiveness clamp* doesn't move vehicle rows," not "vehicle rows are immune to 2A."
  Reported here rather than silently worked around; all three known-broken rows are `xfail`ed
  with full derivations, not hidden.
- **The clustering-floor test fixture (`test_calibration_cluster_merge_undercount.py`) implicitly
  assumed binocular-level detection range all along.** Its own 9 km scenario is not reachable
  under `UNAIDED_OPTIC`'s real presence threshold (2333 m for a 7 m object) — the fixture
  predates optic multipliers entirely and was written when the default was `BINOCULAR_OPTIC` at a
  flat 4.0. Passing the plan-literal "active optic" (`UNAIDED_OPTIC`, since that's what
  `naked_eye_source.py` actually uses today) breaks the fixture's own headline claim for a
  physically real reason (naked eye can't resolve 18.7 m spacing at 9 km — the floor fix doing
  exactly its job). Kept the fixture's original premise by passing `BINOCULAR_OPTIC.presence_
  range_mult` explicitly instead, documented in the module docstring rather than silently chosen.
- **Distinctiveness (decision 3) turned out to interact with far more of the existing test suite
  than the plan's own "Infantry" framing suggested.** Every existing test that placed an Infantry
  candidate in what used to be a presence-only band broke, because infantry's
  `distinctiveness=5.0` structurally eliminates that band at every optic (class always saturates
  to presence). This is correct/intended per decision 3, but the blast radius was wider than a
  quick read of the plan implies — five separate test functions across three files needed a
  different (non-distinctive) test object, not just a value tweak.
