### Implementation Summary

`BL-B64` Stages 1 and 1b, plus direction §14 (`UNAIDED_OPTIC` FOV), implemented on
`worktree-agent-9k113-impl` (branched from `feature/9k113-sight` at
`08c512fe69d33472de67789679c03948be93753a`). Scope held to exactly the four items in
the task brief: the two sight optics as table entries (nothing selects them), the
per-optic position-sigma mechanism (`BL-B55`, folded in), the desired/actual aim field
split (§15a), and `UNAIDED_OPTIC.fov_half_angle_deg: None -> 90.0`. No cone, no
optic-aware range cap, no selection/`optic_policy` resting-phase change, no slew
controller — all deliberately out of scope per the brief.

### Files Changed

- `src/perception/optics.py` — `Optic` gains three field-of-regard fields
  (`regard_azimuth_half_deg`, `regard_elevation_up_deg`, `regard_elevation_down_deg`,
  all `float | None = None`, unread by anything yet). Added `SIGHT_WIDE_OPTIC`
  (3.55/7.00/6.50, FOV half-angle 5.75°, regard ±60°/+20°/−15°) and `SIGHT_NARROW_OPTIC`
  (5.81/13.75/15.00, FOV half-angle 3.0°, same regard). `UNAIDED_OPTIC.fov_half_angle_deg`
  changed `None -> 90.0`. Rewrote the module's stale "scope cut" paragraph and
  `within_optic_fov`'s docstring (the `is None` branch is now unreachable from this
  table but kept, with a comment, for a future peripheral-awareness pseudo-optic).
- `src/perception/estimation.py` — `naked_eye_sigma_m` renamed to `look_sigma_m`,
  gained a mandatory `optic: Optic` parameter. Added two tunable down-range scale
  constants (`SIGHT_WIDE_RANGE_SIGMA_SCALE` 0.5, `SIGHT_NARROW_RANGE_SIGMA_SCALE` 0.3,
  both `status="judgement"`) and two derived (non-tunable) cross-range scale dicts
  keyed by `optic.name`, computed from the FOV ratio against `BINOCULAR_OPTIC`. Both
  dicts default unmatched optics (`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`) to `1.0` —
  behaviour-preserving for every optic that existed before this entry.
- `src/perception/naked_eye_source.py` — threaded `self.optic` into the one
  `look_sigma_m` call site in `_build_observation`. That call already runs once per
  cluster, so "a group is ranged once with a shared draw" (direction §11) is a
  structural consequence of this one parameter, not a separate mechanism.
- `src/belief/optic_policy.py` — `OpticState` gains `actual_aim_azimuth_deg`/
  `actual_aim_elevation_deg` (both `float | None = None`). Added `advance_sight_aim(
  actual_az, actual_el, desired_az, desired_el, *, dt_s)`, whose body is `return
  (desired_az, desired_el)` — the perception-stage pass-through; `dt_s` is accepted and
  unused, reserved for `[[BL-B66]]`'s controller. Fixed the two branches of `decide()`
  that construct a fresh `OpticState(...)` (entering `SEARCHING`, entering `GLASSING`)
  to carry the two new fields forward explicitly — they are not part of `decide`'s own
  phase bookkeeping, so a phase transition must not reset them.
- `src/logger.py` — `_apply_active_gaze` is the one conversion point (plan §15a) where
  `OpticDecision`'s desired aim becomes the `ScanPlan`/`Gaze` perception treats as fact.
  It now takes `optic_state: OpticState | None` and `dt_s: float`, calls
  `advance_sight_aim` there, builds the `ScanPlan` from the *actual* result, and returns
  the updated `OpticState` (or `None` if nothing changed) for the caller to persist.
  When no look is commanded, actual aim is cleared to `None` too, mirroring
  `OpticState.look_azimuth_deg`'s own contract. `run_once` computes `dt_s` from the
  previous poll's `last_t_sim` and persists the returned state back onto
  `self.optic_state`.
- `src/perception/visibility.py`, `src/perception/detection_trace.py` — updated two
  comments that asserted `UNAIDED_OPTIC`'s FOV gate is a documented no-op; both are now
  live as of the `None -> 90.0` change. Also fixed `NAKED_EYE_RANGE_CAP_M`'s
  independently-stale docstring (claimed a 7 m vehicle reaches 9333 m from a threshold
  value that no longer exists; corrected to 2333 m from the current
  `LOWRES_ANGULAR_RADIUS_RAD = 0.003`) — touched while reading this file for the §14
  comment fix, as the brief invited.
- `src/belief/groups.py`, `src/belief/association_over_time.py` — updated two
  docstrings that claimed "the 9K113 does not exist in this code" / that
  `perception.estimation` is optic-blind. Both are now literally false; reworded to
  say the sight optics exist but nothing selects them, and binoculars remain
  deliberately unfixed (no sourced figure to assign them).
- `config/defaults.toml` — regenerated via `tools/generate_defaults.py --write` for
  the two new tunables above. Read the rendered output; both entries render cleanly
  with their own description, status and range.
- `tests/test_optics.py`, `tests/test_estimation.py`, `tests/test_optic_policy.py`,
  `tests/test_logger.py`, `tests/test_position_belief.py` — see below.

### Tests Added

- `test_unaided_optic_field_of_view_still_admits_anything_within_90_degrees` — an
  ordinary off-boresight candidate is unaffected by the `None -> 90.0` change.
- `test_unaided_optic_field_of_view_now_rejects_past_90_degrees_true_separation` — the
  one real behaviour change: a candidate whose true (azimuth+elevation) separation
  from the boresight exceeds 90° is now rejected, where `None` admitted it
  unconditionally. Moved from the now-false `TestBoresightElevation.test_the_unaided_
  eye_ignores_the_boresight_entirely` (see Notable Discoveries).
- `test_binocular_optic_gets_the_same_sigma_as_the_naked_eye` — pins that `BL-B55`'s
  fix is scoped to the two sight optics only; binoculars must produce the exact
  naked-eye sigma until a sourced figure exists for them.
- `test_sight_optics_get_a_smaller_down_range_sigma_than_the_naked_eye` — narrow <
  wide < naked eye, and pins both against the named tunable constants directly.
- `test_sight_cross_range_sigma_is_derived_from_the_fov_ratio` — narrow < binocular <
  wide, following from each optic's own sourced `fov_half_angle_deg`.
- `TestAdvanceSightAim` (3 tests) — the pass-through body, including the
  no-prior-actual case (first poll of a look), and that `dt_s` is accepted but inert.
- `TestOpticStateActualAimCarriesForward` (2 tests) — entering `GLASSING` and entering
  `SEARCHING` both preserve a pre-existing actual aim rather than resetting it to
  `None`, the correctness property the effector stage's controller will depend on.
- `test_apply_active_gaze_builds_the_scan_plan_from_actual_aim`,
  `test_apply_active_gaze_returns_the_updated_optic_state_with_actual_aim_set`,
  `test_apply_active_gaze_clears_actual_aim_when_no_look_is_commanded`,
  `test_apply_active_gaze_returns_none_when_optic_state_was_never_given` — the
  conversion point's four observable behaviours: builds from actual, persists actual
  onto the returned state, clears actual when nothing is commanded, and stays a true
  no-op (`None`) for every caller that passes no `optic_state` at all.

### Checks

(body-layer/ only — the only subproject touched)

- `ruff format --check .`: fails only on the pre-existing out-of-scope
  `research/2026-10-05-security-audit.md`, as the task brief predicted.
- `ruff check .`: pass
- `mypy src`: pass (0 errors, 59 source files)
- `pytest -q`: **1883 passed, 4 xfailed** (baseline 1870 passed, 4 xfailed). Counted
  precisely, not estimated: `git diff` shows 15 new `def test_` lines and 2 removed
  (one rename, one genuine removal — `test_the_unaided_eye_ignores_the_boresight_
  entirely`, which asserted something no longer true), net +13 — matching
  1883 - 1870 = 13 exactly.
- xfailed count unchanged (4 -> 4), as expected: nothing in this stage touches the
  mechanisms those four xfails cover.

### Notable Discoveries

- **The `None`-fov asymmetry the architect's plan predicted was real and already had
  a victim.** `test_optics.py`'s `TestBoresightElevation.test_the_unaided_eye_
  ignores_the_boresight_entirely` asserted `within_optic_fov(UNAIDED_OPTIC,
  boresight_azimuth_deg=0.0, azimuth_deg=80.0, elevation_deg=-40.0,
  boresight_elevation_deg=30.0)` is `True` — true separation for that pair is ~102°,
  past the new 90° half-angle, so the test now correctly asserts `False`. Moved to
  `test_optics.py` next to its companion case rather than left in place asserting
  something false, per the task's instruction to explain rather than quietly adjust.
  No other test in the full suite depended on the `None` behaviour — the rest of the
  suite's gaze/visibility fixtures stay well inside 90° true separation by
  construction, which is itself worth recording: a 90° *azimuth-only* bound
  (`FULL_GAZE`) was already in force everywhere upstream, so almost nothing in this
  codebase exercises geometry anywhere near the true-separation boundary.
- **`look_sigma_m`'s per-optic dicts needed a `BINOCULAR_OPTIC` reference, and that
  reference is read live off the optic object, not duplicated as a literal.** The
  cross-range scale is `optic.fov_half_angle_deg / BINOCULAR_OPTIC.fov_half_angle_deg`
  computed once at import time into `_SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC` — this
  means if `BINOCULAR_OPTIC.fov_half_angle_deg` or either sight optic's FOV is ever
  retuned, the sight's cross-range scale moves with it automatically rather than
  silently drifting out of sync with a hand-copied number.
- **`UNAIDED_OPTIC`'s own `fov_half_angle_deg` must never feed the sigma-scale
  formula**, even though it is now a real number. It represents a peripheral-vision
  envelope (direction §14), not pointing precision, so using it as the ratio's
  denominator or numerator would silently claim the naked eye's bearing precision
  changed when nothing about the crewman's pointing ability did. Both scale dicts are
  keyed by `optic.name` with a `1.0` default specifically so `UNAIDED_OPTIC` never
  needs to appear in either dict at all.
- **`decide()`'s two "fresh `OpticState(...)`" branches were a real, if currently
  harmless, trap.** Because `advance_sight_aim`'s body is `return desired`
  unconditionally this stage, the missing carry-forward on `actual_aim_*` would not
  have caused a visible defect today — the value gets overwritten with `desired`
  immediately after `decide()` returns, every poll. It would have become a real bug
  silently the day `[[BL-B66]]` replaces the body with a real controller that needs
  the *previous* poll's actual aim to converge from. Found by reading every
  `OpticState` construction site instead of trusting that `replace()`-style
  construction was used throughout (it mostly is, but not in the two branches that
  start a fresh `SEARCHING`/`GLASSING` phase) — exactly the "enumerate the containing
  unit" lesson from this role's own memory.
