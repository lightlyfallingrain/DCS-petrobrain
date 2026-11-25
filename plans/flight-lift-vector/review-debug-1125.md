### Review Summary

Reviewed `plans/flight-lift-vector/debug-2026-11-25.md` (both iterations) against
`f8a8f93a..99413458` on `feature/bl16-lift-vector-law` (detached checkout, HEAD was not an ancestor
of the target tip so `--ff-only` was not available; checked out `99413458` directly). Scope: the
speed-shaper braking-distance ceiling, the combined `theta_d` clamp, the rotor-RPM warning/ease, the
RPM gauge recalibration (arg × 110), and the second-iteration `c_theta`/`k_speed_error` raise.

Full read of the diff (`flight_control.lua`, `flight_profile.lua`, both test files), the debug
report, the relevant plan sections ("LV-1 amendment", sections B/C/D/F/G), and the fourth/fifth
re-fly feedback. Ran all mechanical checks and, per the "verify by mutation" doctrine, mutated the
two mechanisms this pass exists to ship (the `dv_ref` anti-windup ceiling, the combined `theta_d`
clamp) to see whether the committed suite would catch their removal.

**Mechanical checks — all pass:**
- `ruff format --check` / `ruff check` (`aircraft-layer/src aircraft-layer/tests`): clean.
- `cd aircraft-layer && mypy src`: clean (run from inside the subproject, per this file's own
  CWD-only warning).
- `luac5.1 -p` on `flight_control.lua` and `flight_profile.lua`: clean.
- Full `aircraft-layer` suite: **1177 passed** (matches the debug report's own count).

**Mutation results (the substantive finding):**
- Deleting the new `dv_ref` braking-distance ceiling entirely (`dv_ref_ceiling`/`dv_cap`, the anti-
  windup that the debug report says is what makes raising `omega_speed` 0.15→0.5 safe) — **all 124
  tests in the two Lua-toy-plant files still passed.**
- Deleting the new combined `theta_d` clamp (`law_clamp(next_state.theta_i + delta_theta_ff, ...)`,
  fix 3, the item this review was specifically asked to check) — **same result, all 124 passed.**
- Deleting the rotor-RPM warning ease block entirely — **this one is caught**
  (`TestRotorEnvelopeGuards::test_low_rotor_rpm_eases_a_rising_collective` fails as expected). So
  that mechanism is properly defended; the other two are not.

The reason: the shared `_PROFILE` fixture in both test files (`test_flight_control_law.py` line
105/113/116, mirrored in `test_flight_control_lua.py`) still carries the **pre-amendment** values
— `omega_speed = 0.15`, `k_speed_error = 0.2`, `c_theta = 0.5` — by deliberate design (kept as the
"pre-amendment baseline," `TestSpeedChannelIsBrisk`'s own docstring, "do not reinvent" notwithstanding).
The handful of tests that *do* override these locally (`TestSpeedChannelIsBrisk`,
`TestAmendmentProductionValuesTogether`) only ever set `c_theta = 0.85` — the **first** iteration's
value, itself now superseded by the shipped `0.90` — and never touch `omega_speed` or
`k_speed_error` at all. So no committed test runs with `omega_speed ≥ 0.5`, which is exactly the
regime where the braking-distance ceiling matters (below that, `a_ref_v` never saturates
`speed_accel_cap_mps2` long enough to need braking). The theta_d clamp is unreached for the
symmetric reason: nothing pushes `k_speed_error`/`c_theta` high enough in a committed scenario for
`theta_i + delta_theta_ff` to approach ±15°.

**This is not a new failure mode for this branch — it recurred.** `TestAmendmentProductionValuesTogether`'s
own docstring says it exists because `review-lv1-amendment.md`'s "required fix 1" caught the same
gap one iteration ago ("no existing test ran `c_theta=0.85`, `speed_accel_cap_mps2=1.9` and
`k_pedal_from_collective_rate=0.6` together"). That fix landed, then this pass moved the goalposts
(`c_theta` 0.85→0.90, new `omega_speed`/`k_speed_error` raises) without moving the test that was
built to catch exactly this.

### Required Fixes

- **Add at least one committed toy-plant test that runs the actual shipped `flight_profile.lua`
  values together** — `omega_speed = 0.5`, `k_speed_error = 0.30`, `c_theta = 0.90` — and asserts
  the no-windup property the debug report's own (uncommitted) sweep measured: bounded sign changes
  / overshoot on a 150→250 and 250→150 step, at the production `max_accel_mps2`/`speed_accel_cap_mps2`.
  Right now only a throwaway, non-repo harness ever exercised this; mutation-testing the committed
  suite proves it cannot catch a regression in the mechanism this whole debug pass exists to ship.
  The natural home is extending `TestAmendmentProductionValuesTogether` (or a sibling class) to the
  current numbers, the same way it was built to close the identical gap one iteration ago — and
  updating it each time a profile constant it's meant to guard changes, not just when a reviewer
  happens to mutation-test it.
- **Add a test that actually drives `theta_i + delta_theta_ff` past ±15° and asserts the combined
  clamp catches it**, and fix the stale comment in `TestAmendmentProductionValuesTogether`
  (`test_row4_like_climb_and_speed_change_is_stable`, around the `max_abs_theta_d < 30.0` assertion):
  it currently reads *"theta_min/max_deg is +-15, but theta_d's feed-forward is not itself clamped
  to that -- 30 deg is a generous 'did not diverge' bound, not a tuned limit"* — that sentence is
  now false; this diff adds exactly that clamp. The bound should be tightened to assert the real
  invariant (`<= 15.0 + epsilon`) rather than left loose and describing behaviour the code no longer
  has.

### Optional Refinements

- **No hysteresis on `rotor_rpm_warning_pct` (88.0).** The guard is a bare per-frame `<` comparison
  that directly caps `u_c_rate`; nothing debounces a reading oscillating near the threshold. Low
  risk — rotor RPM is a slowly-varying quantity and the clamp only ever caps a *rate*, never snaps a
  position — but the toy-plant verification in the debug report shows the real droop-and-recover
  shape crossing this exact band, and the committed tests only check exactly-at (88.0, no trip) and
  one point below (87.0, trips); nothing checks an oscillating sequence straddling the line. Worth
  watching for a pulsing collective near the threshold on the next live flight that reaches it, and
  adding hysteresis later only if that flight shows it (the debug report already marks the first-cut
  values "owed by the next flight").
- **The RPM-warning ease is unconditional and sits outside section G's priority-under-limits chain**
  entirely — defensible (a real audio cue would override a climb/height goal too; rotor/engine
  limits are the ultimate authority a real pilot would respect over altitude) and the toy-plant
  verification in the debug report does exercise a climbing case. But this priority relationship
  (RPM warning above every G-chain absorber, including height) isn't stated in the plan's "G.
  Priority under limits" section, and no scenario near the 40 m AGL floor with the warning actually
  engaged has been checked (live or toy-plant). Worth a line in the plan, and a card row pairing the
  RPM-warning engagement with low AGL once LV-2's floor scenarios are flown.
- The arg × 110 calibration was checked for consistency across every consumer: both `read_rotor_rpm_pct`
  and `read_engine_rpm_pct` apply it; the flight-trace fields (`eng_rpm_40/41/838/839`, `rot42/845`)
  intentionally log the **raw** args, not percentages, which is consistent with how the debug
  report itself derived the calibration (multiplying the raw trace values by 110 by hand) — no
  inconsistency found, noting only that this was explicitly checked.
- The `dv_ref` ceiling's sign handling was checked by reading (not just testing, given the gap
  above): `dv_ref_ceiling = sqrt(2·speed_accel_cap·|err_v|)` is always non-negative and the clamp is
  symmetric (`±dv_cap`), so it bounds the reference-acceleration magnitude correctly in both
  directions and recomputes every frame from the live `err_v` — a speed command changing mid-manoeuvre
  is handled by construction (no stored direction to go stale). This reasoning is sound but, per the
  required fix above, is not backed by a committed regression test at the production `omega_speed`.

### Verdict
APPROVED WITH MINOR FIXES

The behaviour itself (braking-distance ceiling, combined `theta_d` clamp, rotor-RPM warning, RPM
recalibration, second-iteration gain raise) is correctly scoped to the debug report's own hypotheses,
matches the plan's "LV-1 amendment" sections B/C, and all mechanical checks are green. The required
fixes are test-coverage gaps, not functional defects — and not hypothetical: mutation-testing proved
the committed suite cannot currently catch a regression in either of the two central mechanisms this
pass shipped. One of the two gaps (stale production values in the shared toy-plant fixtures) is a
recurrence of a gap `review-lv1-amendment.md` already caught and fixed once this branch. Given the
auto-advance loop, these should go back through Implementer → Reviewer before DoD rather than being
waived, since the whole point of the toy-plant harness is to make exactly this kind of regression
visible without a live flight.

### Review Confidence
Full read of the diff and the debug report; mechanical checks run directly (venv resolved from the
main checkout since this worktree has no `.venv` of its own — gitignored directories don't copy into
a worktree); the two central fix mechanisms verified by mutation, not just by reading.
