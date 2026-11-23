### Implementation Summary

Stage **LV-0** of `plans/flight-lift-vector/plan.md` (BL-16 mode 1 lift-vector law, instruments and
shadow — **no behaviour change**), built on `impl/lv0` (tip `4ccd3227b618a93f7d906cac257066daac637d3c`
at start). Three pieces, each its own commit:

1. **`flight_profile.lua`** (new, loaded before `flight_control`): every loop gain/time-constant
   the five pure law functions (`law_apply_goal`/`law_init_at_take`/`law_update`/`law_outputs`/
   `law_turn_rate_at_bank`) read, moved verbatim from `flight_control.lua`'s own module locals into
   `PROFILES["Mi-24P"]`, plus the estimator's own new first-cut fields (`law_hz`, `velocity_source`,
   the running-average windows, the ball calibration). The four functions that actually read these
   gains gain `profile` as an explicit trailing parameter (`law_turn_rate_at_bank` and
   `law_stopping_height` do not — neither reads a moved constant; `GRAVITY_MPS2` stays a plain
   `flight_control.lua` local, a physical constant, not a tunable gain). **Confirmed bit-identical**:
   every one of the 39 pre-existing toy-plant scenarios in `test_flight_control_law.py` passes
   unmodified (same numeric assertions) once the harness threads a `_PROFILE` Lua table carrying the
   same values through every call site — this is the plan's own "a test asserts the law's outputs
   are bit-identical before and after the move," read as "the existing suite's own assertions did
   not have to change," rather than a new, separate diff-based test (a separate test would just
   re-derive the same numbers the existing suite already pins).

2. **The estimator** (new code inside `flight_control.lua`, living outside `fc_law`): fixed-size,
   preallocated ring buffers with incremental least-squares sums (add the newest sample, subtract
   whatever ages out — never a refit over the stored window, per `perf-plan-review.md`'s own "NOW"
   finding) back world-frame velocity (least-squares slope of `LoGetSelfData().Position`, or a
   running mean of `LoGetVectorVelocity` if `profile.velocity_source == "vector"`), acceleration
   (slope of velocity, then one more running-mean smoothing stage), ground speed, the Euler-rate
   kinematic transform from body rates, and a running-averaged slip ball. Runs every frame, in every
   mode, gated internally to `profile.law_hz` (first cut 30 Hz) on **DCS model time** (`t`, already
   threaded into `run_flight_control(t)` from `Export.lua`'s `LuaExportBeforeNextFrame` — no
   `Export.lua` timing change was needed). The due-check (`est_due`) runs *before* any `LoGet*` read,
   so an off-due frame (the large majority, at ~140 Hz DCS frames against a 30 Hz law rate) costs two
   comparisons and nothing else. The unselected velocity source and the logged-only channels
   (`LoGetAccelerationUnits`, AoA/AoSS) are read and computed **only while the per-frame trace flag
   is on** (perf-plan-review's other "NOW" finding). Nothing in `law_update` reads the estimator's
   output yet — this is the "shadow" half of LV-0.

3. **Status fields and the trace flag**: `push_flight_control_state` gains `fc_est_a_f`/`a_r`/`a_u`,
   `fc_est_v_g`/`v_g_f`, the three Euler rates, `fc_est_ball` and `fc_est_lambda` (a trivial, hard-
   coded first-cut 0..1 curve on ground speed — reported for the card even though nothing reads it;
   the real blend breakpoints are deliberately not added to the profile yet, per the plan's own
   "LV-1/LV-2/LV-3" staging). A new, separate flag file (`aircraft_layer_flight_debug.flag` →
   `aircraft_layer_flight_trace.log`), checked once at load via a bare `pcall` (not `core.lua`'s own
   `safe_call` global, which is not guaranteed to exist in every harness that loads this file whole
   — see Notable Discoveries).

### Files Changed

- `aircraft-layer/dcs-export/Petrobrain/flight_profile.lua` — **new**. `PROFILES["Mi-24P"]` table;
  see the old-name → new-field mapping below.
- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua` — the constant-move refactor (profile
  parameter threaded through the five pure functions and their six internal call sites); the
  estimator (ring buffers, least-squares helpers, Euler-rate transform, `est_reset`/`est_due`/
  `est_sample`, `read_estimator_raw`, the trace flag/logger); `on_stop` resets the estimator too
  (Co-moving Fields: "mission stop, reset(epoch)"); new `fc_est_*` status fields; `M.est_*` exports
  for the dedicated test file.
- `aircraft-layer/dcs-export/Export.lua` — `flight_profile` loaded via `load_module` right before
  `flight_control` (comment updated to explain the ordering).
- `aircraft-layer/src/schema/flight_control.py` — `FlightControlState` gains the ten `est_*`
  dataclass fields, `from_dict` parsing (`_optional_number`), `to_api_dict` entries, and a docstring
  paragraph.
- `aircraft-layer/tests/test_flight_control_law.py` — every `law_*` call site (81 of them) threaded
  with a new `PROFILE` Lua table mirroring `flight_profile.lua`'s values; `law_init_at_take` call
  sites that previously omitted `seed` now pass an explicit `nil` before `PROFILE` (positional-arg
  correctness — see Notable Discoveries).
- `aircraft-layer/tests/test_flight_control_lua.py` — a `flight_profile = { ACTIVE = {...} }` global
  stub added to `_PREAMBLE` (this harness exercises `run_active_frame`/`request_take` end to end, so
  it needs the cross-module global, unlike the toy-plant harness which calls the pure functions
  directly); new `TestEstimatorStatusFields` class (the estimator's fields are present and finite on
  the wire even while `fc_mode == "off"`, which the toy-plant harnesses cannot exercise).
- `aircraft-layer/tests/test_flight_control_estimator.py` — **new**. Ring-buffer least-squares math,
  the Euler-rate transform (including the plan's own 60°-bank worked example), reset/priming on a
  model-time gap, ground-speed/heading-frame rotation, velocity-source selection, the ball average.
- `aircraft-layer/tests/test_flight_control_api.py` — two new test methods (`est_*` fields optional/
  absent-as-None and parse-when-present) plus the existing `test_to_api_dict_carries_every_field`
  exact-dict-equality test extended with the ten new keys (unavoidable: a new wire field changes
  what that assertion must equal — the new keys were added, no existing assertion value changed).
- `docs/acceptance/2026-11-23-bl16-lv0-card.md` — **new**. The card named in the plan's Implementation
  Plan item 1.
- `plans/flight-lift-vector/implementation.md` — this file.

### Old constant → new `flight_profile.lua` field mapping

| old `flight_control.lua` local | new profile field |
|---|---|
| `LAW_ZETA` | `law_zeta` |
| `OMEGA_HEADING` / `OMEGA_ALT` / `OMEGA_SPEED` | `omega_heading` / `omega_alt` / `omega_speed` |
| `T_ROLL` | `t_roll` |
| `HEADING_ACCEL_CAP_DEG_S2` | `heading_accel_cap_deg_s2` |
| `K_HEADING_TRACK` | `k_heading_track` |
| `ALT_ACCEL_CAP_MPS2` / `SPEED_ACCEL_CAP_MPS2` | `alt_accel_cap_mps2` / `speed_accel_cap_mps2` |
| `K_VS_ERROR` / `K_ALT_ERROR` / `K_SPEED_ERROR` | `k_vs_error` / `k_alt_error` / `k_speed_error` |
| `K_COLLECTIVE` | `k_collective` |
| `K_TILT_FROM_AX` / `K_TILT_FROM_AZ_SATURATED` | `k_tilt_from_ax` / `k_tilt_from_az_saturated` |
| `THETA_MIN_DEG` / `THETA_MAX_DEG` | `theta_min_deg` / `theta_max_deg` |
| `K_BANK_INCREMENT` | `k_bank_increment` |
| `K_THETA` / `K_THETA_I` / `K_Q` / `K_PHI` / `K_PHI_I` / `K_P` | `k_theta` / `k_theta_i` / `k_q` / `k_phi` / `k_phi_i` / `k_p` |
| `K_PEDAL_FROM_COLLECTIVE_RATE` | `k_pedal_from_collective_rate` |
| `PEDAL_LIMIT_POSITIVE` / `PEDAL_LIMIT_NEGATIVE` | `pedal_limit_positive` / `pedal_limit_negative` |
| `PEDAL_NEAR_LIMIT_MARGIN` | `pedal_near_limit_margin` |
| `COLLECTIVE_RATE_CAP_NEAR_PEDAL_LIMIT` | `collective_rate_cap_near_pedal_limit` |
| `ROTOR_RPM_NEAR_FLOOR_MARGIN_PCT` | `rotor_rpm_near_floor_margin_pct` |
| `COLLECTIVE_RATE_CAP_NEAR_RPM_FLOOR` | `collective_rate_cap_near_rpm_floor` |
| `RETREATING_BLADE_STALL_MARGIN_KMH` | `retreating_blade_stall_margin_kmh` |
| `COLLECTIVE_RATE_CAP_NEAR_BLADE_STALL` | `collective_rate_cap_near_blade_stall` |
| `K_BREAK_PEDAL_BIAS` | `k_break_pedal_bias` |
| `K_TURN_COORD_PEDAL` | `k_turn_coord_pedal` |
| `TAU_ACCEL_FILTER_S` | `tau_accel_filter_s` |
| `TURN_SETTLE_DEG_S` | `turn_settle_deg_s` |
| *(stays local, not moved)* `GRAVITY_MPS2` | — (physics, not a tunable gain) |
| *(new, not previously a constant)* | `law_hz`, `velocity_source`, `w_v_s`, `w_a_s`, `w_a2_s`, `w_b`, `ball_centre`, `ball_usable_range` |

**Deliberately not added yet** (first needed by LV-1/LV-2/LV-3): the regime blend speeds (25/50 km/h),
the gain schedule `G(V)` breakpoints, the per-manoeuvre priority orders, `rotor_dir`. Adding these
now, unused, risked guessing ahead of what those stages actually need — the plan's own staging
language already defers them explicitly.

### Tests Added

- `test_flight_control_estimator.py` (17 tests): ring-buffer least-squares slope (including the
  regression case for the eviction-index bug found during this work), fewer-than-two-samples,
  running mean, window-eviction-actually-forgets-the-past; the Euler-rate transform at a steady 60°
  bank turn (the plan's own worked example — `q ≈ ψ̇·sin(φ)` in body rates, `theta_dot ≈ 0` in Euler
  rates), at level flight (body and Euler rates coincide), and near-vertical pitch (no NaN/inf);
  reset/priming on a `dt > DT_CAP` gap and on the first sample ever, `est_reset` clearing every
  field; northbound/eastbound ground-speed-vs-heading rotation, vertical acceleration reading ~zero
  in a level turn; `velocity_source == "vector"` actually averaging rather than differentiating;
  the ball running average and its fallback to `profile.ball_centre` when the reading is missing.
- `test_flight_control_lua.py::TestEstimatorStatusFields` (2 tests): every `fc_est_*` field present
  and finite while `fc_mode == "off"`; ground speed tracked on a northbound leg with no take ever
  requested (the estimator runs regardless of whether Petrovich is flying).
- `test_flight_control_api.py` (2 new tests + 1 extended): `est_*` fields optional/absent-as-None;
  `est_*` fields parse correctly when present; `test_to_api_dict_carries_every_field` extended with
  the ten new keys.
- `test_flight_control_law.py`: no new test cases — the existing 39, now threaded with `PROFILE`,
  **are** the bit-identical test (see Implementation Summary item 1).

### Checks

(aircraft-layer only — LV-0 touches no other subproject; `body-layer`/`world-model` untouched)

- `ruff format --check src tests`: **pass** (90 files already formatted)
- `ruff check src tests`: **pass** (all checks passed)
- `mypy src` (run from inside `aircraft-layer`): **pass** (29 source files, no issues)
- `pytest tests -q -p xdist -n auto` (full suite, not just the touched files): **pass**, 1133 passed
- `luac5.1 -p` on every file under `dcs-export/*.lua` and `dcs-export/Petrobrain/*.lua`: **pass**
- `luac5.1 -l -p` GETGLOBAL check on `flight_control.lua` and `flight_profile.lua`: every listed
  global is either Lua stdlib, a genuine DCS API, or a legitimate cross-module global
  (`flight_desired`/`ai_pilot_wheel`/`client`/`flight_profile`) — no name that is also one of the
  file's own locals read before its declaration.

### Test-impact check (role instruction 1b)

The plan's own test list for LV-0 named `test_flight_control_law.py`, `test_flight_control_lua.py`,
`test_export_lua_constants_parity.py`, `test_dcs_export_lua_local_order.py`. Checked against what
actually exists and was actually needed:

- **`test_export_lua_constants_parity.py`**: confirmed out of scope — it checks `MAX_WATCHED_ARGS`/
  `EXPORT_SCRIPT_VERSION`-class parity only, nothing LV-0 touches. Not edited, as the plan itself
  expected ("Replaced" vs "Reused" constant lists did not name this file either).
- **`test_dcs_export_lua_local_order.py`**: confirmed auto-discovering (`glob("**/*.lua")`) — covers
  `flight_profile.lua` with no edit, as the plan's own Affected Modules entry said.
- **Missing from the plan's own list, found necessary**: `test_flight_control_api.py` (the schema/
  API-level parse test for `FlightControlState`, which LV-0's own "status fields `fc_est_*`" bullet
  requires extending) and the new `test_flight_control_estimator.py` (the plan's Tests section
  implies estimator-level unit coverage — "focused unit tests" per this role's own directive — but
  did not name a file for it, since the plan's Tests section is written for the whole feature, not
  stage-by-stage). Neither omission was a defect in the plan — LV-0's own prose already anticipated
  the schema/status-field work, just without naming the test file.

### LV-0 deviations from the plan, if any

- **The law-rate scheduler/interleaving applies only to the estimator in LV-0, not to `law_update`
  itself.** The plan's "Update rate, not every frame" section describes the estimator *and the law*
  both moving to `profile.law_hz`, interleaved. LV-0's own Implementation Plan bullet, though, says
  only "Estimator (A) running every frame" for this stage — `law_update`'s own per-frame cadence,
  rate limit, and bit-exact-at-take guarantee are untouched here, since changing when/how often
  `law_update` runs would itself be a behaviour change, contradicting LV-0's own "no behaviour
  change" framing. The full law moving to the scheduled/interleaved cadence is read as LV-1's own
  job (the first stage that actually changes what the law does). Flagged explicitly per the
  directive's own instruction to say so if this reading is uncertain.
- **`lambda` uses hard-coded 25/50 km/h breakpoints** inside `est_sample` rather than reading them
  from the profile, since the profile deliberately does not carry the real blend breakpoints yet
  (see the mapping table above). This is a placeholder value, explicitly commented as such, not the
  real LV-3 schedule.
- **The ball estimator reads only the pilot seat's draw arg** (943), not "whichever seat is live" —
  the 2026-11-20 calibration flight already confirmed both seats read the same physical value, so a
  live-seat-tracking mechanism (which exists elsewhere in this module for a different purpose, the
  take-capture logic) would add complexity with no behavioural difference.
- **`LoGetAccelerationUnits`'s return shape is assumed to be an `{x,y,z}` table**, matching
  `LoGetAngularVelocity`/`LoGetVectorVelocity`'s own confirmed shape — `Sim_ControlAPI.md` documents
  neither args nor results for this call (confirmed by direct grep). This is logged-only (trace-
  gated, never closes a loop), so a wrong guess here shows up as an always-nil trace field, never a
  crash or a wrong control input.

### Notable Discoveries

- **An off-by-one bug in the ring buffer's own eviction-index arithmetic**, found by a manual smoke
  test before it reached the pytest suite: `oldest_idx` was computed as `((head - count - 1) % CAP)
  + 1`, one slot older than the actual oldest live sample (`((head - count) % CAP) + 1`). A
  perfectly linear test series (`v = 2t + 5`) returned slope `16.29` instead of `2.0` with the bug
  present — fixed and re-verified both by the manual smoke test and by
  `test_flight_control_estimator.py::TestRingLeastSquaresSlope`.
- **`core.lua`'s own `safe_call` global is not safe to call at `flight_control.lua`'s module-load
  time in every test harness.** `test_flight_control_law.py`'s toy-plant harness deliberately never
  mocks a single DCS/cross-module global (its own docstring: "never has to mock a single DCS
  global"), so a top-level `local FLIGHT_TRACE_ENABLED = safe_call(function() ... end) == true`
  statement crashed that harness with "attempt to call global 'safe_call' (a nil value)" — `safe_call`
  is only ever published as a global by a harness that specifically extracts it (`test_flight_control_
  lua.py` does; the toy-plant one does not, by design). Fixed by using a bare `pcall` instead — `pcall`
  is a Lua builtin, never missing, and the project's own `safe_call` is itself nothing more than
  `pcall` plus a 3-value-return convention this one-shot check does not need.
- **Comments pruned**: the 150-line "M2 control law constants" block comment (the big module-header-
  style comment introducing every moved gain) was replaced with a 6-line pointer to `flight_profile.lua`'s
  own header, which now carries the per-constant "owed by M0-E"/measurement context instead (one
  home for that information, not two). Three smaller "moved to flight_profile.lua" pointer comments
  replace the individual `ROTOR_RPM_NEAR_FLOOR_MARGIN_PCT`/`K_BREAK_PEDAL_BIAS`/`K_TURN_COORD_PEDAL`,
  `TAU_ACCEL_FILTER_S`, and `TURN_SETTLE_DEG_S` comment blocks in `flight_control.lua` (4 comment
  blocks pruned, all in that one file — the content moved, not duplicated, into `flight_profile.lua`'s
  own per-field comments). No comment was pruned without its content having a new home; this is a
  relocation, not a deletion of load-bearing "why."
- **The `FC_AXES_ENABLED`/`SEAT_ARGS`/`CMD`/`SIGN` tables were deliberately NOT moved to the profile**
  even though they are per-aircraft data in the same spirit as everything that did move — the plan's
  own "Removed and kept" table assigns them to `[[BL-18]]` ("owns the per-module arg/cmd map"), a
  different, not-yet-built mechanism, so moving them now would pre-empt that decision rather than
  follow it.
