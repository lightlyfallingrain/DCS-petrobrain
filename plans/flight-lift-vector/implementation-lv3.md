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
5. **The heading-shaper's `turn_mode` branch (a commanded continuous "turn left/right") is not
   lambda-blended**, only the ordinary heading-tracking branch and the break's own rate limit are,
   per the plan's literal text ("the heading shaper's bandwidth, rate cap... blend with lambda" is
   stated once, in context of the ordinary/break cases; `turn_mode` is not mentioned either in C or
   in any diagram). Left unmodified — a continuous-turn command at hover is an edge case the plan
   does not discuss, and no test exercises it at low lambda.
6. **U13's absolute pedal range is now the only bound on `t_y`'s integrator** — the near-right-stop
   collective-rate guard (`pedal_near_limit_margin`/`collective_rate_cap_near_pedal_limit`) is
   unchanged in code, now measured against the real stop (1.0) rather than the old 0.5, exactly as
   the plan's U13 answer specifies; no other call site reads `pedal_limit_positive`/`pedal_limit_
   negative` (grepped, two sites in `law_update`, matching the plan's own enumeration).
