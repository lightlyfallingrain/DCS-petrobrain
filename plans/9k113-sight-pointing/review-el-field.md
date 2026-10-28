### Review Summary

Reviewed `fix/9k113-el-field-measured` (tip `649cce716cd630500f2fd210e2e0836fb36694ef`, diff from
`3d1f905a9761e358a8e6d4e54910315c94803586`) against the 2026-10-28 sortie feedback (§2-4), the
plan's v3 "Elevation field measured in flight" entry, and `implementation.md`'s matching note.

Change: the symmetric `ASP17_FIELD_EL_HALF_DEG` placeholder (4.3°) is replaced with two measured
raw clip readings (`ASP17_MARK_EL_RAW_CLIP_UP = 1.0`, `ASP17_MARK_EL_RAW_CLIP_DOWN = 0.278`) and a
new boresight/scale (`MARK_BORESIGHT_EL = 0.83`, `MARK_DEG_PER_UNIT_EL = 1/0.030`), from which two
asymmetric degree bounds are derived. `sight_clip_to_field_body_deg` and `sight_mark_is_clipped`
both gained a signature split (`field_el_half_deg` → `field_el_up_deg`/`field_el_down_deg`), with
azimuth calling both with the same value on both sides.

**Projection correctness, verified by reading and by mutation:**
- `sight_clip_to_field_body_deg`: per-axis independent scale-min (az always symmetric; el selects
  `field_el_up_deg`/`field_el_down_deg` by the *sign* of `set_el_deg`, not magnitude) is the correct
  generalization of the existing ray-to-box clip. Confirmed inside-unchanged, both elevation sides,
  and the diagonal case (az wins over an out-of-bound el, and vice versa) both by reading and by the
  new tests (`test_setpoint_above_the_up_bound_lands_on_the_up_edge`,
  `..._below_the_down_bound...`, `..._inside_the_asymmetric_field_is_unchanged`,
  `test_diagonal_setpoint_below_the_down_bound_still_clips_azimuth_too`).
- `sight_mark_is_clipped`: sign-based branch on `body_deg`, each side checked against its own bound
  independently of the other. Confirmed by the new asymmetric tests and by mutation (below).
- **Every call site updated.** `grep`-equivalent check (read all four call sites in the diff):
  `push_slew_trace`'s log-time check (both branches), `run_sight_servo`'s `field_target` projection,
  and its own mark-validity gate — all four pass the new 5/6-argument shape correctly, azimuth
  passing its single half-angle twice. No stale 4-argument call left.
- **Raw-bound clip checks** (top 1.0, bottom 0.278, with margin): `ASP17_FIELD_EL_UP_DEG`/`_DOWN_DEG`
  are derived from the raw readings and the calibration rather than hand-duplicated, so a future
  recalibration moves both together — matches the plan's stated intent.
- **Mutation testing** (not just reading): three independent mutations applied to the production
  `Export.lua` and reverted —
  1. `sight_clip_to_field_body_deg`'s down branch pointed at `field_el_up_deg` instead of
     `field_el_down_deg` → 4 tests failed (3 unit, 1 end-to-end `TestRunSightServoFieldPark`).
  2. `sight_mark_is_clipped`'s down branch pointed at `field_up_deg` instead of `field_down_deg` →
     1 test failed (`test_asymmetric_up_bound_clips_independently_of_the_down_bound`).
  3. `ASP17_MARK_EL_RAW_CLIP_DOWN` changed from `0.278` to `0.400` → **no test failed.** The test
     harness carries its own hand-duplicated copy of the production constants (same pattern as
     `GIMBAL_*`/`MARK_BORESIGHT_AZ`/etc. already use, stated explicitly in the harness's own
     comment: "not extracted, same reasoning as every other constant in this preamble"). This is a
     pre-existing project convention, not a gap introduced by this diff — noted below as optional,
     not required.
- **`test_elevation_down_field_bound_is_unreachable_through_the_gimbal`**: verified independently by
  reading `run_sight_servo`'s setpoint clamp (`GIMBAL_EL_DOWN_DEG`/`GIMBAL_EL_UP_DEG`, lines
  ~1661-1663 of production `Export.lua`) — the setpoint is clamped to `[-15, 20]` *before*
  `sight_clip_to_field_body_deg` ever runs, so the measured down bound (~−17.9° inset) can never
  actually be reached by the setpoint path in production. The test's claim and the implementer's
  "Notable discovery" are both correct.

**Checks**: `luac5.1 -p Export.lua` pass. `ruff format --check`/`ruff check` on `aircraft-layer/`
clean except one pre-existing, unrelated finding in `research/2026-10-06-unit-id-join-reduce.py`
(confirmed via `git log` that this diff never touched that file — not introduced here).
`mypy --strict` on `src`: pass, 25 files (no `src/` file touched by this change at all). `pytest
aircraft-layer/tests -q`: 618 passed. `body-layer/` untouched by the diff — not re-run, matching the
diff's own stated scope (no wire-format change).

### Required Fixes

- **No `aircraft-layer/research/` entry records this DCS-internals finding.** The project's
  established pattern for a measured 9K113 fact (raw gauge calibration, clip behaviour) is a dated
  `aircraft-layer/research/<date>-...md` entry — see `2026-10-21-9k113-slew-readback-probe-findings.md`,
  `2026-10-17-9k113-effector-and-slew-probe-findings.md`, `2026-10-05-elevation-cost-probe-results.md`.
  This diff encodes a new DCS-internals fact as hard constants (`MARK_BORESIGHT_EL = 0.83`,
  `MARK_DEG_PER_UNIT_EL = 1/0.030`, the two raw clip values) sourced only from
  `docs/acceptance/2026-10-28-sortie-feedback.md` and the plan's own prose — no corresponding
  `research/` entry exists. CLAUDE.md's invariant ("no claim about DCS internals encoded as fact
  without a corresponding research/ entry") is written against `world-model/research/` but states
  the finding belongs in "whichever subproject's research/ directory" the finding is about; this is
  squarely aircraft-layer's own 9K113 recon, in the same vein as the three entries above. A short
  entry cross-referencing the sortie feedback's §2-4 measurements and this constant change would
  close it — this is a documentation gap, not a code defect, and is small to fix.

### Optional Refinements

- **The test harness's hand-duplicated elevation constants (`MARK_BORESIGHT_EL`, `MARK_DEG_PER_UNIT_EL`,
  the derived field bounds) are not extracted from production**, so a typo in the production raw
  clip values would not be caught by any test (confirmed by mutation: changing
  `ASP17_MARK_EL_RAW_CLIP_DOWN` to `0.400` left all 54 tests green). This is the same convention
  already used for every other constant in that test preamble (`GIMBAL_*`, `MARK_BORESIGHT_AZ`,
  etc.) and is not a regression introduced by this diff — flagged only because this is a fresh
  flight-measured value with more churn risk ahead (see the scale question below) than the
  long-settled azimuth constants it sits beside. Not blocking.

### Calibration-scale opinion (not applied — flagged for the user/Architect)

The implementer's own flagged inconsistency is real and, on reading the air-run log, I'd lean
toward **not** trusting `MARK_DEG_PER_UNIT_EL = 1/0.030` as-is, for a reason stronger than the
rate-derivation's internal consistency:

**The down-side figure it implies (~−18.4°) is physically impossible.** `GIMBAL_EL_DOWN_DEG =
-15.0` is the *sourced* periscope manual limit (`body-layer/research/2026-09-20-9k113-sight-optics-
from-manual.md`) — the real periscope cannot physically move past it, so no reading of the 555
mark gauge can correspond to a true angle beyond it. The 1/0.030 scale, applied to the measured raw
delta (0.83 − 0.278 = 0.552), produces exactly such an impossible angle. Something in the
derivation is therefore wrong — most plausibly the assumed 0.5°/s commanded rate (sourced from
`Devices_specs/9K113.lua`'s `v_axis_velocity = 10 deg/s` plus the probe's `0.05` command unit, but
that is the *commanded* rate, not a confirmed *delivered* one), not the raw clip readings themselves
(0.278/1.0 are direct telemetry, not derived).

The alternative the implementer names — scale ≈ 1/0.037, if the bottom stop is exactly the gimbal
−15° — has two things going for it the 1/0.030 figure doesn't: (1) it is physically consistent with
the sourced gimbal limit rather than contradicting it, and (2) it sits close to azimuth's own
measured 1/0.039, which is a reasonable prior if both mark gauges (565/566, 555/556) are the same
kind of linear linkage reading off the same kind of periscope mechanism. The rate-derivation's
internal agreement (travel-time estimate matching the scale-derived span almost exactly) is not
independent evidence for 1/0.030 — both numbers were computed from the same assumed 0.5°/s, so
they agree by construction, not by confirmation.

**Reading the log for which fits an abrupt stop vs. a soft clip**: the descent is a clean, steady
linear ramp (~−0.0140/s, `research/logs/2026-10-28/...hud_elevation_limits.log`, air run) that
decelerates over roughly 0.2 s into a hard, flat plateau at exactly 0.27842, holding flat for ~0.75 s
before the reversal check even begins. That shape is consistent with hitting a genuine stop (either
an optical-window saturation or a mechanical gimbal stop) — it does not, by itself, distinguish
between the two candidate causes; both would look the same in this telemetry.

**Operational consequence, if 1/0.030 is wrong**: `sight_mark_is_clipped`'s root-cause check is
self-consistent regardless of the scale (raw clip and its degree-derived threshold are built from
the same scale, so it still correctly detects true saturation) — this part is not at risk. What is
at risk is `sight_clip_to_field_body_deg`'s **up-side** inset bound (the only side reachable through
the gimbal clamp): if the true up-side optical limit is nearer 4.6° than 5.67°, the current inset
(5.17°, meant to sit safely *inside* true saturation per the user's own "keep it just within the HUD
limit... while still keeping the read back values" decision) could actually sit *past* it — defeating
the margin's purpose on the one side that matters operationally, which is exactly the mismatch
between simulated and real sight the whole feature exists to prevent.

**What I'd ship**: given the raw clip values are solid (direct telemetry) and only the *scale*
converting them to degrees is in question, and the down side is provably unreachable regardless, I
would not block this merge on it — the parking behaviour at the true clip is correct either way
(`sight_mark_is_clipped` is scale-consistent). But I would flag this loudly for a short, dedicated
calibration flight (a known pitch change at a fixed sight position, independent of commanded rate)
before trusting the up-side **degree** figure for anything beyond "same side as before." If forced
to pick a number today without that flight, I would lean toward the gimbal-consistent ~1/0.037
over the rate-derived 1/0.030, specifically because the latter implies an angle the aircraft cannot
physically reach.

### Verdict

APPROVED WITH MINOR FIXES

The one required fix (a `research/` entry) is a documentation gap, not a code defect, and does not
block the mechanism itself, which is correctly implemented and well-tested. The calibration-scale
question is flagged, not blocking, per the analysis above — the implementer already surfaced it
honestly rather than hiding it, and the parking logic is correct under either candidate scale.

### Review Confidence

Full read. Read the complete diff (Lua + tests + roadmap + implementation.md), the full sortie
feedback doc, the relevant plan sections, and the raw air-run log around both edges. Ran
`luac5.1 -p`, `ruff format --check`, `ruff check`, `mypy --strict`, and the full `pytest` suite
(618 passed). Verified projection correctness and call-site wiring by mutation (3 mutations applied
to production `Export.lua` and reverted), not reading alone.
