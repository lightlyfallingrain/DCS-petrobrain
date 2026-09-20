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
