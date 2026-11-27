# BL-16 lift-vector law, Stage LV-3 (low speed and hover) — Implementation Summary

Built per `plans/flight-lift-vector/plan.md` "LV-3 amendment (2026-11-27)" through the end
(including the "Corrected 2026-11-28" notes under sections C and E, and the "Answered 2026-11-28"
U12–U17 block), `alignment.md`'s "Plan check — LV-3 amendment (2026-11-28)" (both findings already
applied at the read tip, `63a3218d`), and `explore-notes.md`'s "LV-3 explore" / "LV-3 diagram review
corrections" sections. No contradiction the corrections did not already settle was found.

## Files Changed

- `aircraft-layer/dcs-export/Petrobrain/flight_profile.lua` — U13: `pedal_limit_positive` 0.5 → 1.0
  (full axis range, replacing the software half-travel cap). New LV-3 tuning block: `lambda_hover_kmh`
  (25.0), `lambda_forward_kmh` (80.0), `k_yaw_damp`, `yaw_damp_max`, `yaw_damp_v_floor_mps`,
  `k_yaw_rate_i`, `hover_omega_heading`, `hover_yaw_rate_max_deg_s`, `k_drift_hold`,
  `speed_band_min_mps`, `hover_pedal_band`, `hover_pedal_band_forward`, `goal_jerk_hover_mps3`,
  `goal_jerk_edge_mps3` — all first-cut per the plan's own table, Lua-edited data (no `tuning.py`
  equivalent in aircraft-layer).
- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua`:
  - New pure helper `law_lambda(v_g_mps, profile)` (section A) — non-finite/missing input returns
    1.0 (the forward law). Exported as `M.law_lambda` for the toy-plant suite.
  - `law_init_at_take`: hover take rule (F, U15) — at `lambda <= 0` a banked take holds heading, not
    the bank; `V_m`-seeded `v_ref`/default `speed_goal_mps` (B); lambda-weighted ball P term (D);
    yaw-damper value backed out of `t_y`'s seed (D, bit-exact); new fields `yaw_damp_pedal`,
    `pedal_hover_ref` (= `command.pedals`), `heading_change_active` (= `false`), `a_f_goal_s`/
    `a_u_goal_s` (= `0.0`).
  - `law_update`: `lambda`/`v_m` derived once at the top; held-bank end at `lambda <= 0` (F);
    heading-shaper `omega`/`rate_limit` blend with lambda for the ordinary case, and the break's own
    `rate_limit` blends the same way (C); unexplained-yaw computation and the all-speed yaw-damper
    overlay (D); low-speed goal slew on `a_f_goal_s`/`a_u_goal_s` (G), feeding `a_f_d`/`a_u_d`;
    drift-hold blend on `a_r_d` (B); U14 collective speed-give nudge fades with lambda; `t_y`
    integrator's ball share is lambda-weighted, hover yaw-rate integral added (D); `pedal_hover_ref`/
    `heading_change_active` updated each step (E); `in_band_speed` uses `v_m` plus
    `speed_band_min_mps` floor (B, finding 7).
  - `law_outputs`: lambda-weighted ball P term; hover pedal band applied to the pedal sum only when
    `state.heading_change_active` (E, corrected).
  - `est_reset`: `est.lambda = nil` (was `0.0`, which read as "hover" on every reset).
  - `est_sample`: `est.lambda = law_lambda(est.v_g, profile)`, replacing the old hard-coded 25/50
    placeholder curve.
  - `run_active_frame`: merges `measured.lambda`/`v_g`/`v_g_f`/`v_g_r` from the estimator when
    primed; added a third write-back branch (held bank ending at hover writes the settled heading
    back to `flight_desired`, same pattern as the turn/break settle write-backs).
  - New getters `M.get_lambda` (mirrors `fc_est.lambda`) and `M.get_take_speed_kmh` (computes `V_m`
    from live `LoGetIndicatedAirSpeed` and `fc_est`), for `flight_desired.lua`'s own reseed.
- `aircraft-layer/dcs-export/Petrobrain/flight_desired.lua`:
  - `reseed_from_measured`: mirrors the hover take-rule override (via `flight_control.get_lambda`)
    and seeds `desired.ias_kmh` from `flight_control.get_take_speed_kmh` (falling back to IAS as
    before when the getter is unavailable).
  - `write_internal`: the heading branch now also clears `desired.bank_hold_deg` (finding 6).
- `aircraft-layer/tests/test_flight_control_law.py` — new LV-3 test classes (below); the shared
  hand-maintained `_PROFILE` fixture gained the new LV-3 fields, with `lambda_hover_kmh = 0.0` /
  `lambda_forward_kmh = 1.0` (forces lambda = 1 for every non-LV-3 test's realistic speed, so every
  pre-existing scenario stays on the pure forward law) and `speed_band_min_mps = 0.0` (preserves the
  pre-LV-3 `in_band_speed` formula bit-for-bit).
- `aircraft-layer/tests/test_flight_control_estimator.py` — added `lambda_hover_kmh`/
  `lambda_forward_kmh` to the shared `_PROFILE` and to one inline ad-hoc profile table
  (`TestVelocitySourceSelection`'s own `vector_profile`), both now required by `est_sample`.
- `aircraft-layer/tests/test_flight_control_lua.py`:
  - `flight_profile.ACTIVE` fixture updated to mirror the shipped profile: `pedal_limit_positive`
    1.0, plus every new LV-3 field.
  - `LoGetSelfData()` mock now returns a `Position` that advances by `ias_mps` along `heading_rad`
    for real elapsed sim time (`_mock_t`) — see "Notable Discoveries" below.
  - `_run`'s script assembly wraps `flight_control.run_flight_control` once to set `_mock_t` before
    delegating to the real function, so every existing driver's own `run_flight_control(t)` call
    keeps the mock's elapsed-time tracking correct with no per-test changes.

## Tests Added

All in `aircraft-layer/tests/test_flight_control_law.py` unless noted:

- `TestLv3LambdaHelper` — `law_lambda`'s breakpoints/linearity (shipped profile via `dofile`) and
  non-finite/missing-input fallback to 1.0.
- `TestLv3RunawayToyPlant` — the plan's own "toy plant first" step. A new point-mass plant: world-
  frame ground velocity (no wind), bank → lateral acceleration rotated into world frame by the
  *current* nose heading (not the track angle), with the nose's own yaw dynamics (pedal command,
  weathervane restoring torque, plant-side rate damping) kept separate — the mechanism the plan's
  trace reading describes ("slides right, nose stays put"). `test_plant_gate_lv2_law_reproduces_the_
  runaway` is the pass gate: decelerating 108→60 km/h on heading hold with `k_yaw_damp = 0` and
  lambda forced to 1 reproduces sideslip > 30° with the ball inside ±0.05.
  `test_shipped_damper_reduces_the_runaway` confirms the shipped profile cuts the same scenario's
  peak sideslip to well under half, ball still small.
  `test_damper_sign_right_pedal_when_nose_lags_the_bank_implied_turn` — damper sign check.
- `TestLv3AboveBlendTopUnchanged` — `k_yaw_damp = 0` reproduces `TestLV2BreakShaperBandwidth`'s own
  pinned 120 km/h ordinary-turn figures exactly (lambda = 1 above 80 km/h by construction).
- `TestLv3HoverPedalBand` — holding heading at hover with a sustained yaw disturbance moves the
  pedal more than `hover_pedal_band` from its take value, unclamped; a commanded 45° heading change
  at hover never leaves `pedal_hover_ref ± hover_pedal_band`.
- `TestLv3TakeRuleAtHover` — a banked take at `lambda = 0` holds heading, not the bank; the same bank
  at `lambda = 1` still holds the bank (regression).
- `TestLv3HeldBankEndsAtHover` — a held bank ends once lambda reaches 0, heading holds, no snap.
- `TestLv3LowSpeedGoalSlew` — at lambda = 1 the goal slew is a no-op; at lambda = 0 the first frame's
  `a_f_goal_s` never exceeds `goal_jerk_hover_mps3 * dt`.
- `TestLv3SpeedBandFloor` — a "speed 0" goal at ground speed 0.5 m/s is in band (the floor makes this
  possible; the old bare fractional band could not).

## Checks

**aircraft-layer/** (the only touched subproject; body-layer untouched per the plan):

- `ruff format --check src tests`: pass (one new test file needed `ruff format`, applied, re-checked
  pass)
- `ruff check src tests`: pass
- `mypy src` (from inside `aircraft-layer/`): pass, no issues in 29 source files
- `luac5.1 -p` on every touched Lua file (`flight_control.lua`, `flight_profile.lua`,
  `flight_desired.lua`): pass
- `luac5.1 -l -p` upvalue audit on `flight_control.lua`: `law_update` 8 upvalues (of 60), `law_
  init_at_take` 5, `law_outputs` 1, `run_active_frame` 38, `run_flight_control` 38 — every function
  this stage touched stayed well clear of the ceiling. Module-level local count: 124 of 200 (see
  "Notable Discoveries" — one more than the plan's own "no new module-level local" statement
  anticipated).
- `pytest tests -q -n auto -p no:cacheprovider`: **1254 passed**, full suite (not just the touched
  files), run twice (once mid-work, once at the end) to confirm no regressions survived the mock-
  harness fix below.
- **Fix pass (review-lv3.md, 2026-11-28) re-run**: same full-suite command, **1265 passed** (the 11
  new tests from "Fix pass" below, zero regressions). `ruff format --check`/`ruff check src tests`/
  `mypy src` (0 issues, 29 files)/`luac5.1 -p` on all three touched Lua files all re-run clean.

Toy-plant numbers (own measured figures, from `TestLv3RunawayToyPlant`, 700 steps of 0.05 s = 35 s,
decelerating 108 → 60 km/h on heading hold, no wind):

| | sideslip peak | ball peak | min ground speed |
|---|---|---|---|
| LV-2 gate (`k_yaw_damp = 0`, lambda forced 1) | 31.2° | 0.044 | 57.9 km/h |
| LV-3 shipped (`k_yaw_damp = 0.03`, real lambda blend) | 17.8° | 0.023 | 59.7 km/h |

Hover heading change (45°, lambda = 0): the `TestLv3HoverPedalBand` scenario settles within the
pedal band throughout and the heading-tracking shaper's own idealised peak rate (independent of this
toy plant's bank-lag) is ~8°/s per the shipped `hover_yaw_rate_max_deg_s`, consistent with the plan's
own "within 2° in ~9.7 s" figure (not independently re-derived here — the toy-plant assertion is on
the band and the slew, not a re-measurement of the shaper's own idealised step response, which the
plan's own "What reading the code and the trace turned up" section 3 already computed analytically).

## Notable Discoveries

1. **The plan's own illustrative "<10°" LV-3 sideslip figure is not what this toy plant produces.**
   My plant's own weathervane/pedal-yaw/ball gains are a first cut, picked only to clear the stage-1
   pass gate (sideslip > 30° with the ball inside ±0.05 under the pre-LV-3 law); with those same
   gains the shipped damper cuts peak sideslip to 17.8°, a clear, substantial improvement (<60% of
   the LV-2 figure) but not under 10°. I tuned the gains to demonstrate the *mechanism* (unexplained-
   yaw damping measurably suppresses the sideslip the ball cannot see), not to hit the plan's
   illustrative number — a different, more aggressive weathervane/pedal-authority balance in the
   plant could get closer to 10°, but doing so risks curve-fitting the plant to a number rather than
   reproducing the mechanism honestly. Flagging this rather than quietly asserting `< 10.0` in the
   test.
2. **`test_flight_control_lua.py`'s entire mock harness never modelled `LoGetSelfData().Position`
   at all** (its `LoGetSelfData` returned only `{ Heading = heading_rad }`). Because `est.v_g`/
   `v_g_f`/`v_g_r` (and therefore `lambda`) are derived from `Position` when `velocity_source =
   "position"` (this harness's own default), every one of that file's ~60 tests was silently
   running the law at `lambda = 0` (hover) once LV-3's regime blend existed — regardless of the
   mocked `ias_mps`, which was never consulted for anything ground-speed-related before. Four tests
   failed outright on this (tight numeric assertions written against the pure forward law); the rest
   likely tolerated the wrong regime by coincidence of their own assertion looseness, which is the
   more concerning half of this finding — a silent regime mismatch that a tighter test elsewhere
   could have missed entirely. Fixed by making the mock's `Position` advance by `ias_mps` along
   `heading_rad` for real elaped sim time (one `LoGetSelfData` change plus a one-time wrap of
   `flight_control.run_flight_control` in `_run`'s own script assembly, so no individual driver
   needed editing). This is a correction to the test harness's own fidelity, not a change to any
   test's asserted behaviour.
3. **`law_lambda` is a new module-level `local function`**, which the plan's own "Lua budget" note
   says LV-3 should not need ("LV-3 adds no module-level local beyond the two getters on `M`" — the
   getters are `M.get_lambda`/`M.get_take_speed_kmh`, table fields, not locals). `flight_control.lua`
   now has 124 of 200 top-level locals (was 122) — comfortably inside the budget, but a one-local
   deviation from that specific sentence. I kept it as a shared top-level function (used by
   `est_sample` and the toy-plant suite's own `M.law_lambda` export) rather than duplicating the
   breakpoint-interpolation logic inline in two places.
4. **Relationship/coupling not independently guarded**: `lambda_hover_kmh` must stay strictly below
   `lambda_forward_kmh` for `law_lambda`'s own span to be positive — guarded defensively (`span <=
   0.0` returns 1.0, same "degenerate data → forward" posture as every other division guard in this
   module) but not asserted anywhere as an invariant on the profile table itself. Worth noting for
   whoever next edits those two fields.
5. **Fixed in the review-lv3.md pass**: the heading-shaper's `turn_mode` branch (a commanded
   continuous "turn left/right") was not lambda-blended, only the ordinary heading-tracking branch
   and the break's own rate limit were — see "Fix pass (review-lv3.md)" below.
6. **U13's absolute pedal range is now the only bound on `t_y`'s integrator** — the near-right-stop
   collective-rate guard (`pedal_near_limit_margin`/`collective_rate_cap_near_pedal_limit`) is
   unchanged in code, now measured against the real stop (1.0) rather than the old 0.5, exactly as
   the plan's U13 answer specifies; no other call site reads `pedal_limit_positive`/`pedal_limit_
   negative` (grepped, two sites in `law_update`, matching the plan's own enumeration).

## Fix pass (review-lv3.md, 2026-11-28)

Four required fixes; `turn_mode` (the review's one Optional Refinement) treated as a fifth
required fix per the main loop's own direction, since the review's own probe found it reaching the
pedal-commanding yaw loop at hover.

**Required fix 1 — `flight_desired.lua`'s two LV-3 changes were completely untested.**
`test_flight_desired_lua.py`'s `flight_control` mock stub had no `get_lambda`/`get_take_speed_kmh`
entries, so `reseed_from_measured`'s hover take-rule mirror and its `V_m` speed seed were dead code
to this test file. Fixed: added both getters to the stub (`fc_lambda`/`fc_take_speed_kmh` backing
globals, `nil` default) and two tests —
`test_off_to_m1_at_hover_holds_heading_not_bank` (a banked take at `lambda = 0` reseeds to heading,
not bank) and `test_off_to_m1_at_a_blended_speed_seeds_from_v_m_not_bare_ias` (a `V_m` reading that
disagrees with bare IAS lands in `fd_ias`). Confirmed red without the stub fix (both new tests fail
against the un-fixed mock): `test_off_to_m1_at_hover_holds_heading_not_bank` reads `"bank"` instead
of `"heading"`; `test_off_to_m1_at_a_blended_speed_seeds_from_v_m_not_bare_ias` reads `200.0`
(bare IAS) instead of `55.0` (`V_m`).

**Required fix 2 — the held-bank-end write-back and `write_internal`'s `bank_hold_deg` clear had no
test against real code.** `test_flight_control_lua.py`'s own hand-written `flight_desired` mock
(a second, drifting copy of `flight_desired.lua`'s logic, per the review) had no `bank_hold_deg`
field in its `desired` table at all and did not clear one in its `write_internal`. Fixed: added the
field and the clear to the mock (mirroring the real module's finding-6 fix verbatim), and added
`TestLv3HeldBankEndWriteBack.test_held_bank_end_clears_bank_hold_in_flight_desired`, which drives
the real `flight_control.lua` orchestration end to end (`request_take`/`run_flight_control`, a
banked take decelerated to hover) and asserts the mock's `bank_hold_deg` is cleared and `hdg_mode`
becomes `"heading"` — not `law_update` in isolation (`TestLv3HeldBankEndsAtHover`, which only ever
reaches the law's own internal state, as the review noted). Confirmed red without the mock fix
(`bank_hold_deg` stays at its stale sentinel `99` instead of clearing to `nil`).

**Required fix 3 — no closed-loop test for the drift-hold mechanism.** Added
`TestLv3DriftHoldToyPlant.test_crosswind_drift_damps_toward_zero_heading_held_by_pedal`: the plan's
own named scenario ("speed 0 in a 5 m/s crosswind"), using the same world-frame point-mass/yaw toy
plant as `TestLv3RunawayToyPlant`, started with a 5 m/s sideways ground-velocity offset standing in
for the crosswind. Measured: final ground speed 0.041 m/s (plan: "under 1 m/s"), max heading
deviation 0.042° (heading held by the pedal/yaw loop, not the bank), max bank 5.79° (bank actively
carried the drift hold, not a no-op). Confirmed red with `k_drift_hold` zeroed in the shipped
profile (final ground speed stays at 5.0 m/s, the uncorrected crosswind) and restored afterwards.

**Required fix 4 (main loop direction) — the `turn_mode` gap.** A continuous "turn left/right"
command's own rate ceiling (`turn_goal_deg_s`, from `law_turn_rate_at_bank(max_turn_bank_deg, v_t)`,
speed-inverse and ~102°/s at 2 m/s per the review's own probe) was not blended with lambda the way
every other heading-type command's rate/accel caps are (C). Fixed in `flight_control.lua`'s
`law_update`, `turn_mode` branch: the commanded rate is now clamped to
`lambda * |turn_goal_deg_s| + (1 - lambda) * hover_yaw_rate_max_deg_s` before the existing
roll-in-limited ramp runs — a no-op at `lambda = 1` (`rate_cap = |turn_goal_deg_s|` exactly, so the
branch stays bit-exact with LV-2 above `lambda_forward_kmh`). Added
`TestLv3TurnModeLambdaBlend` (hover: settles at ≤ `hover_yaw_rate_max_deg_s`, confirming the raw
figure really does exceed 50°/s first; mid-blend at `lambda = 0.5`: settles within 0.5°/s of the
linear blend; above 80 km/h: settles bit-exact with the raw commanded rate, < 1e-6 difference).
Confirmed red on the two blend-sensitive cases with the fix reverted (hover case settled at 40.0°/s,
not ≤ 8.5°/s; mid-blend case settled 3.0°/s off the expected blended cap) and restored afterwards.

**Required fix 4 (the plan's own Tests-list disclosure) — honest accounting of what this and the
original LV-3 pass built, against the plan's own Tests section.** The original `implementation-
lv3.md` "Checks" section read as if the plan's Tests list was fully satisfied; it was not. Full
accounting, by plan Tests-list item:

| plan Tests-list item | status |
|---|---|
| `λ` helper (breakpoints, non-finite → 1.0) | built (`TestLv3LambdaHelper`) |
| Runaway reproduced, then fixed | built (`TestLv3RunawayToyPlant`) |
| Damper sign | built (`TestLv3RunawayToyPlant`) |
| Above 80 km/h, unchanged | built (`TestLv3AboveBlendTopUnchanged`) |
| **Stop 150 → 0** | **deferred to the LV-3 card, row 3** — needs vertical-dynamics toy-plant machinery (a stop-through-hover power curve) the current plant does not model at all (horizontal-only, by the module docstring above `_LV3_RUNAWAY_DRIVER`); building it is a materially bigger effort than this fix pass's scope |
| **Accelerate 0 → 150** | **deferred to the LV-3 card, row 7** — same vertical-dynamics gap as "Stop 150 → 0" |
| Hover heading change 45° and 90°, both ways | built this pass — the pre-existing suite only had 45°/one direction (`TestLv3HoverPedalBand.test_a_commanded_heading_change_at_hover_stays_inside_the_band`); added `test_a_90_degree_heading_change_at_hover_stays_inside_the_band` (parametrized ±90°) |
| Band does not cut the lead | built this pass (`TestLv3HoverPedalBand.test_collective_lead_moves_the_pedal_past_the_static_band`) |
| Speed 0 in a 5 m/s crosswind | built this pass (required fix 3, above) |
| **Ground effect and transitional lift** | **deferred to the LV-3 card, row 6** — no model exists anywhere in the law (per the plan: left to the vertical-loop integrator and telemetry feedback with no ground-effect/power-curve term to test against); the current toy plant has neither |
| Take at 20 km/h (interpolated λ, bit-exact, `speed_goal_mps = V_m`) | built this pass — the pre-existing suite only covered the λ=0/λ=1 boundaries (`TestLv3TakeRuleAtHover`); added `test_take_at_an_interpolated_lambda_is_bit_exact_and_seeds_v_m` (λ = 0.5) |
| Held bank slowing through 25 km/h, write-back check | built this pass (required fix 2, above) — the law-internal half (`TestLv3HeldBankEndsAtHover`) already existed; the write-back half is new |
| Low-speed slew | built (`TestLv3LowSpeedGoalSlew`) |
| Harness hygiene | built (the existing extraction-tuple/parity tests, unaffected by this pass) |

So three plan Tests-list items remain genuinely unbuilt after this pass — "Stop 150 → 0",
"Accelerate 0 → 150", and "Ground effect and transitional lift" — all three needing
vertical-dynamics toy-plant machinery (a stop-through-hover power curve, ground-effect/
transitional-lift terms) this file's horizontal-only plant has never modelled. Deferred to the
LV-3 live card's rows 3, 7 and 6 respectively, in writing, per the review's own required split —
not silently absent.

**Not addressed (review's own text, left as the review's judgment)**: the review's Optional
Refinements on the toy plant's sideslip figure and the interpolation test (the latter is now built
above, as part of required fix 4's Tests-list item) are otherwise unchanged from the original
pass's own Notable Discoveries.
