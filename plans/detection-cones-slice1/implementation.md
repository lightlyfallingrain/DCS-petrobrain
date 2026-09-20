### Implementation Summary

Slice 1 of the detection-cones milestone: a per-optic field-of-view gate and magnification
generalisation on `perception.visibility.check_visibility`, plus a new `perception.optics`
module naming the optics involved. Implemented in three passes within one session, each on
explicit coordinator/user direction:

1. Initial build per the plan as revised (`plans/detection-cones-slice1/plan.md`, commit
   632867e) — four optics (`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`, `SIGHT_WIDE_OPTIC`,
   `SIGHT_NARROW_OPTIC`), `Optic` with field-of-regard fields carried as inert data.
2. **Scope cut** (user, mid-session): the 9K113 sight (`SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`)
   deferred entirely; the four field-of-regard fields dropped from `Optic` since, with no
   sighted optic in the table, they would all be `None` and untested.
3. **Magnification/derating split** (user, mid-session): `BINOCULAR_RANGE_MULTIPLIER` (4.0) was
   never a real optical magnification — it is `HelperAI.lua`'s `extra_eyesight_ratio` wearing
   that label. Split into a realistic instrument (`magnification=8.0`, a Б-8/БПЦ5 8x30) times a
   named, unmeasured `handheld_effectiveness=0.5` derating factor, chosen so their product
   (`effective_magnification`) exactly reproduces 4.0 — behaviour-preserving by construction.

The final state below reflects pass 3, not the intermediate passes.

### Files Changed
- `body-layer/src/perception/optics.py` (new) — `Optic` dataclass (`name`, `magnification`,
  `fov_half_angle_deg: float | None`, `boresight_azimuth_deg: float = 0.0`,
  `handheld_effectiveness: float = 1.0`, plus an `effective_magnification` property),
  `within_optic_fov` (spherical-law-of-cosines circular FOV test, `None` = unrestricted), and
  two named optics: `UNAIDED_OPTIC` (M=1.0, no derating, no FOV restriction) and
  `BINOCULAR_OPTIC` (M=8.0 × 0.5 derating = effective 4.0, no FOV restriction — today's
  implicit default made explicit). Imports `BINOCULAR_RANGE_MULTIPLIER` from `visibility.py`
  (plan Decision 1: the constant's home stays `visibility.py`).
- `body-layer/src/perception/visibility.py` — `check_visibility` gains a keyword-only
  `optic: Optic | None = None` parameter (resolved to `BINOCULAR_OPTIC` inside the function
  body — see "Notable Discoveries" for why not a literal default), a new FOV gate after the
  cockpit-mask gate, and `optic.effective_magnification` threaded through the range-threshold
  formula and `_achieved_tier` (which gains its own `magnification: float =
  BINOCULAR_RANGE_MULTIPLIER` parameter) in place of the hardcoded constant reference. Module
  and gate docstrings updated (three gates → four; `BINOCULAR_RANGE_MULTIPLIER`'s own comment
  now explains it is the *effective* figure, with the derivation).
- `body-layer/tests/test_optics.py` (new) — `within_optic_fov` mechanism tests against small
  synthetic `Optic` instances, plus `UNAIDED_OPTIC`/`BINOCULAR_OPTIC` value/derating checks.
- `body-layer/tests/test_visibility.py` — new tests for the optic gate and magnification
  threading (see below).
- `body-layer/CLAUDE.md` — new `src/perception/optics.py` Structure entry; extended the
  existing `src/perception/visibility.py` entry to cover the optic parameter, FOV gate, and
  the magnification/derating split.

### Tests Added
- `test_default_optic_argument_matches_pre_slice1_behaviour` — the central regression guard:
  `check_visibility(...)` called with no `optic` argument, on hires/medres/out-of-range fixture
  cases, matches both the pre-slice-1 expected values and an explicit `optic=BINOCULAR_OPTIC`
  call exactly.
- `test_synthetic_narrow_fov_optic_rejects_candidate_outside_its_cone` /
  `test_synthetic_narrow_fov_optic_admits_candidate_inside_its_cone` — FOV gate wiring, using a
  synthetic `Optic` (neither shipped optic has a FOV restriction).
- `test_higher_magnification_optic_extends_the_range_threshold` — `BINOCULAR_OPTIC` admits a
  candidate at a range just beyond `UNAIDED_OPTIC`'s own `lowres` threshold but well inside its
  own, demonstrating `effective_magnification` reaching the range formula.
- `test_optics.py`: `test_none_fov_half_angle_always_passes`,
  `test_boundary_case_exactly_at_the_half_angle_passes`,
  `test_just_outside_the_half_angle_fails`, `test_off_boresight_azimuth_case`,
  `test_elevation_offset_alone_can_fail_the_gate`,
  `test_unaided_optic_has_no_fov_restriction`,
  `test_unaided_optic_derating_leaves_effective_magnification_unchanged`,
  `test_binocular_optic_effective_magnification_matches_the_calibrated_constant` — the last
  pinning that `BINOCULAR_OPTIC.effective_magnification == BINOCULAR_RANGE_MULTIPLIER` so the
  two can never silently drift apart.

### Checks
(body-layer/ only — no other subproject touched)
- ruff format --check: pass
- ruff check: pass
- mypy --strict (`cd body-layer && mypy src`): pass, 36 source files
- pytest -q: pass, 731 passed

### Notable Discoveries
- **A real circular import, not flagged by the plan.** The plan's Decision 1 says
  "`optics.py` imports the constant from `visibility.py`, not the reverse," but the
  Implementation Plan's own step 2 requires `visibility.py` to import `Optic`/`BINOCULAR_OPTIC`
  from `optics.py` for the parameter type and default — the reverse direction, on the same pair
  of modules. This is a genuine mutual dependency: `optics.py` needs `visibility.py`'s constant
  defined, and `visibility.py` needs `optics.py` fully loaded (the `Optic` class and the
  `BINOCULAR_OPTIC` instance). Traced through import order: whichever module is imported first
  triggers a full load of the other, which then needs the first one fully loaded while it is
  still mid-load — an `ImportError` regardless of which module a test imports first (so it would
  have surfaced nondeterministically depending on pytest's collection order, e.g. `test_optics.py`
  alphabetically before `test_visibility.py`). Resolved by keeping `Optic` as a
  `TYPE_CHECKING`-only import in `visibility.py` and doing the real `optics.py` import lazily
  inside `check_visibility`'s function body, with `optic: Optic | None = None` resolved to
  `BINOCULAR_OPTIC` at call time rather than as a literal default expression — behaviourally
  identical to `optic: Optic = BINOCULAR_OPTIC`, confirmed by the byte-identical-default
  regression test, but avoids the module-load-order trap entirely. Documented in both modules'
  docstrings so a future reader doesn't "simplify" it back into a literal default and reintroduce
  the cycle.
- No test-inventory mismatches found against the plan's own test list — this is a new module
  pair with no pre-existing tests to conflict with, and a `grep` across `tests/` for other
  `check_visibility`/`optics` references turned up nothing outside `test_visibility.py`/
  `test_optics.py` themselves.

---

## Follow-up pass (same session, 2026-09-20): derating dropped, multiplier raised to 8.0

The coordinator relayed a further, explicit user reversal of pass 3 above: **drop
`handheld_effectiveness` entirely.** Rationale (user's own words, preserved): a multiplier should
state the instrument honestly; the 0.5 derating factor "preserved the old 4.0's *behaviour* while
dressing it up as physics," which is the same mislabelling problem the split was meant to fix, one
level down. Decision: **take the range increase now, recalibrate afterwards.**
`BINOCULAR_OPTIC.magnification` is now plainly `8.0`; `BINOCULAR_RANGE_MULTIPLIER` is now `8.0`.

### Files Changed (this pass)
- `body-layer/src/perception/optics.py` — `handheld_effectiveness` field and
  `effective_magnification` property removed from `Optic` entirely (not kept as a no-op — it would
  only have returned `magnification` unchanged, which the task's own instructions called out as
  not earning its place). `BINOCULAR_OPTIC.magnification = BINOCULAR_RANGE_MULTIPLIER` (8.0)
  directly, no second factor. Module docstring gains a "No derating factor" section recording the
  reversal and its rationale, plus a "stale calibration" note.
- `body-layer/src/perception/visibility.py` — `BINOCULAR_RANGE_MULTIPLIER: Final[float] = 8.0`
  (was 4.0). `optic.effective_magnification` → `optic.magnification` in both the range-threshold
  formula and the `_achieved_tier` call. Extensive docstring updates: the constant's own comment
  records the 4.0→8.0 change and the reversed derating step; the module docstring's binocular
  premise section flags that the old "matches `extra_eyesight_ratio` (4.0)" coincidence no longer
  holds and that the 2026-09-17 screenshot calibration is now stale; the `LOWRES`/`MEDRES`/
  `HIRES_ANGULAR_RADIUS_RAD` block gets an explicit "STALE as of 2026-09-20" banner.
- `body-layer/tests/test_optics.py` — the two derating tests replaced with one:
  `test_binocular_optic_magnification_matches_the_range_multiplier`, pinning
  `BINOCULAR_OPTIC.magnification == BINOCULAR_RANGE_MULTIPLIER == 8.0`.
- `body-layer/tests/test_visibility.py` — every M=4.0-derived literal recomputed for M=8.0:
  the medres/hires/lowres boundary tests (new x values, comments show the arithmetic), the Ural
  truck gate test (**renamed** to `test_ural_truck_gate_is_now_bound_by_the_range_cap_again` —
  its premise flipped: at M=8.0 a Ural's uncapped lowres threshold, 16000 m, now exceeds
  `NAKED_EYE_RANGE_CAP_M`, so the cap binds again, the opposite of what the 2026-09-17-calibration
  test it replaced proved), and the magnification-comparison test (`BINOCULAR_OPTIC` vs.
  `UNAIDED_OPTIC`, tier expectations recomputed). The central regression test
  `test_default_optic_argument_matches_pre_slice1_behaviour` is **replaced** by
  `test_default_optic_is_binocular_at_the_new_8x_range_multiplier`, per the coordinator's explicit
  instruction not to weaken or silently delete it — the new test still pins "default optic is
  exactly `BINOCULAR_OPTIC`" (byte-identical explicit-vs-implicit calls) but pins the *new* range
  behaviour instead of the old one, with a worked before/after tier comparison in its own
  docstring (Infantry at 700 m: `lowres` under the old M=4.0, `medres` under the new M=8.0).
- `body-layer/tests/test_naked_eye_source.py` — two more fixture ranges recomputed (found by
  running the full suite, not named by the coordinator): `test_medres_range_candidate_stays_at_
  class_level` (a T-72B at the old test range now resolves to `hires`, not `medres` —moved the
  fixture range from 1500 m to 3000 m) and `test_no_visible_candidates_returns_empty` (a Ural
  truck at the old test range, 8500 m, is now inside the M=8.0-driven cap rather than gated out —
  moved to 10500 m, which clears the hard range cap regardless of magnification).
- `body-layer/tests/test_mock_flight_chain.py` — the full-chain fixture's object 102 (stationary
  infantry) now genuinely crosses from presence to class tier mid-flight, at frame 14 (t_sim=70.0,
  slant range ≈980.6 m against the new 1028.57 m medres threshold) — verified by actually running
  the harness (this file's own stated convention: "not guessed"), not derived from the formula on
  paper. This produces a real `CONTACT_CLASSIFICATION_CHANGED` event the fixture's assertions
  didn't previously expect. Updated: the module docstring's object-102 bullet (also notes the
  *pre-existing* "refining to medres by frame 16" text was already stale before this change — the
  real old-M=4.0 slant range at the fixture's last frame was ~689 m against a 514.29 m threshold,
  so it never actually reached medres under the old constant either), the events-list assertion
  (now 3 events, not 2), and the final `CONTACT_2` classification/level assertions (`OP_INFANTRY`/
  `class`, not `OP_GROUPSOMETHING`/`presence`).
- `body-layer/tests/test_vision_calibration.py` — **not edited to pass.** Four parametrized cases
  (`C-3990m`, `C-2990m`, `C-1990m`, `C-1500m`) now compute `hires` where the real, photographed
  screenshot ground truth says `medres` (`class_recognizable`) — this module's own docstring
  predicts exactly this failure mode for exactly this kind of edit: "the moment someone changes
  ... `BINOCULAR_RANGE_MULTIPLIER` ... this test fails and names the range that stopped matching
  what the screenshots show." Editing the assertion or the fixture would mean asserting the
  screenshots show something they do not, so these four cases are `xfail`ed instead (a new
  `_STALE_AT_8X_MULTIPLIER` frozenset, checked at the top of
  `test_computed_tier_matches_ground_truth` via `pytest.xfail(...)` with a dated reason) — the
  ground-truth data and the assertion logic are both untouched.
- `body-layer/CLAUDE.md` — `visibility.py`/`optics.py` Structure entries rewritten: no more
  `handheld_effectiveness`/`effective_magnification`, `BINOCULAR_RANGE_MULTIPLIER` is 8.0, and a
  pointer to `test_vision_calibration.py`'s `xfail`s so a future reader lands on the known
  calibration debt instead of rediscovering it independently.

### Checks (this pass)
- ruff format --check: pass
- ruff check: pass
- mypy --strict (`cd body-layer && mypy src`): pass, 36 source files
- pytest -q: pass, 726 passed, 4 xfailed (the vision-calibration ground-truth divergences above)

### Consequences flagged to the user (per explicit instruction)

**Every calibration figure recorded before this commit is now stale.** This includes: the three
angular-radius constants (`LOWRES`/`MEDRES`/`HIRES_ANGULAR_RADIUS_RAD`), every worked-example
range number in `visibility.py`'s own comments, and every threshold literal that was in the test
suite before this pass (all updated to the new arithmetic, not re-measured). None of this was
re-derived from real sortie/screenshot data at the new M=8.0 — only recomputed from the existing
formula. A fresh calibration ladder against the real 8.0 multiplier is genuinely owed.

**`clustering.py`'s acuity floor re-checked at M=8.0 and confirmed still non-binding** — the
concern the coordinator asked to be re-verified explicitly. `clustering.py`'s own docstring proves
floor (A) non-binding *algebraically*, generic in `M`: `visibility.py` admits a candidate exactly
when `theta_size * M >= LOWRES_ANGULAR_RADIUS_RAD`; combined with merge criterion (S),
`theta_sep * M >= 0.5*(theta_size_a + theta_size_b)*M >= LOWRES_ANGULAR_RADIUS_RAD` always holds
for anything detected. This proof does not depend on `M`'s specific value — it depends only on
`clustering.py` and `visibility.py` using the *same* `BINOCULAR_RANGE_MULTIPLIER` constant, which
they still do (`clustering.py` imports it directly; `visibility.py`'s live default path only ever
uses `BINOCULAR_OPTIC`, whose `magnification` is that same constant). Confirmed empirically too:
`test_clustering.py::test_floor_self_consistency_of_the_detection_floor_at_the_detection_limit`
(which derives its own boundary case from the live `BINOCULAR_RANGE_MULTIPLIER` value, so it is
self-consistent by construction regardless of magnitude) passed with no changes needed, alongside
every other `test_clustering.py` case. **No behaviour change outside this slice's intended scope
was found here.**

**A real behaviour flip found and flagged, not silently absorbed**: at M=8.0, `NAKED_EYE_RANGE_CAP_M`
(10000 m) now binds for every vehicle-sized object ≥3.75 m (`size_m / LOWRES_ANGULAR_RADIUS_RAD *
8.0 > 10000` whenever `size_m > 3.75`) — a Ural truck (6 m) and a T-72 (7 m) both now hit the flat
10000 m cap on their `lowres` tier rather than the size curve discriminating further out, exactly
reversing what the 2026-09-17 calibration pass achieved when it raised the cap from 5000 to 10000
specifically to hand the discriminating back to the size curve for medium/large vehicles. This is
a genuine, currently-live consequence of the M=8.0 change (not merely a stale comment) — surfaced
via the renamed Ural-truck test in `test_visibility.py` and the `test_no_visible_candidates_returns_
empty` fixture-range move in `test_naked_eye_source.py`, and called out here per the "I need to
know" instruction. Not fixed in this pass (`NAKED_EYE_RANGE_CAP_M` retuning is calibration work,
explicitly deferred by "recalibrate afterwards").

### Notable Discoveries (this pass)
- **The plan-vs-test-suite gap this time was in the direction the role's own process note warns
  about most**: the coordinator's message named exactly one test by name
  (`test_default_optic_argument_matches_pre_slice1_behaviour`) as certain to fail. Running the full
  suite (not just the named test) found five more files with real, non-cosmetic failures:
  `test_visibility.py` (5 more cases beyond the named one), `test_optics.py` (the derating tests,
  expected — removed along with the fields), `test_naked_eye_source.py` (2 cases),
  `test_mock_flight_chain.py` (1 case, the deepest of the six — a real new domain event surfacing
  through the full pipeline, not a boundary-literal edit), and `test_vision_calibration.py` (4
  cases, the one genuinely irreducible failure — real photographic ground truth, correctly left
  failing via `xfail` rather than "fixed"). Had I only touched the one named test, the suite would
  have been left red in five other files.
- `test_vision_calibration.py`'s own module docstring turned out to already document, in prose,
  exactly the failure this pass triggered — "the moment someone changes ... `BINOCULAR_RANGE_
  MULTIPLIER` ... this test fails and names the range" — written before this pass existed. Worth
  noting as a case where the codebase's own prior documentation correctly predicted a future
  regression's shape.
