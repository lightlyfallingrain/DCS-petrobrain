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

---

## LV-1 (2026-11-23, continuing from LV-0, tip `6fa74373`)

Forward-flight law, no hand-back (`plans/flight-lift-vector/plan.md`, "The law, in words" B–I,
G's ordinary chain, H's anti-windup). Built directly on the feature branch worktree
(`impl/lv1`, tip `6fa74373`), no separate agent worktree was needed for this pass.

### Files Changed

- `aircraft-layer/dcs-export/Petrobrain/flight_profile.lua` — new LV-1 fields: the gain schedule
  (`schedule_gain_min`/`schedule_full_speed_kmh`), the trim loops (`c_theta`/`k_phi_trim`/
  `k_theta_trim`/`trim_hold_attitude_err_deg`/`phi_i_bound_deg`), the ordinary priority chain
  (`k_theta_speed_give`/`speed_give_capacity`/`k_phi_give`/`phi_ff_min_scale`/
  `k_collective_speed_give`), the lift-length feed-forward (`k_lift_ff`), the ball-centring pedal
  loop (`k_ball_pedal`/`rotor_dir`). Removed (dead, per the plan's "Removed and kept" table):
  `k_bank_increment`, `k_tilt_from_ax`, `k_tilt_from_az_saturated`, `tau_accel_filter_s`,
  `k_break_pedal_bias`. `k_collective`/`k_pedal_from_collective_rate`/`k_turn_coord_pedal` reused
  (same field, new role — see each one's own updated comment).
- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua` — the law itself: `law_phi_ff_deg`/
  `law_theta_ff_deg`/`law_lift_length_g` (new shared helpers, sections D/E); `law_init_at_take`
  rewritten (phi_i/theta_i/u_c_i seeded from the estimator's own measured acceleration, section I);
  `law_update` rewritten (C–H); `law_outputs` damps on Euler rates
  (`measured.theta_dot_deg_s`/`phi_dot_deg_s`, falling back to the body rate only while the
  estimator has not primed). The estimator's own output (`a_f`/`a_r`/`a_u`/the three Euler rates/
  `ball`) is merged onto `measured` in `run_active_frame`, gated on a new `fc_est.primed` flag
  (set once the acceleration ring itself has a real window — section A's "the law must not feed
  un-primed values" requirement); while not primed, `law_update` is skipped for that frame (shapers/
  integrators hold) and `law_outputs` still reacts to the current attitude against the frozen
  target, never a literally-frozen axis value. `check_unpark_preconditions` lost its IAS check
  (AGL only); `check_envelope` lost the low-IAS release (`ENV_IAS_MARGIN_KMH`/`ENV_HOLD_S`/
  `fc_env_low_ias_since_t` removed entirely); `fc_limits`/`FC_LIMIT_BOUNDS` lost `min_ias_kmh`;
  `build_take_seed`'s unpark clamp lost its speed floor (kept the ceiling).
- `aircraft-layer/tests/test_flight_control_law.py` — `_PROFILE` updated to LV-1's field set;
  every shared bank-lag toy-plant driver gained a real `measured.a_r = g*tan(bank)` feedback line
  (see Notable Discoveries); the altitude-channel overshoot test gained a real `measured.a_u` from
  the plant's own `w_mps` delta; `TestBreakPedalBiasUnwinds` removed outright (the mechanism it
  tested is gone, U5); `TestTurnCoordinationPedal`'s break-suppression test rewritten to assert
  the opposite (no suppression exists any more); `TestCollectiveHoldsAltitudeInABankedTurn` re-pins
  `state.phi_d` every loop iteration (see Notable Discoveries); two new test classes added
  (`TestAntiWindupPreventsTheRetestDivergence`, `TestTakeIsBumpless` — see Tests Added).
- `aircraft-layer/tests/test_flight_control_lua.py` — the `flight_profile` global stub updated to
  LV-1's field set; every `"min_ias_kmh":80.0,` wire literal removed; `TestUnparkTakeRefusals`'s
  low-IAS-refusal test rewritten to assert acceptance; `TestStage2VoiceTakePrecondition`'s
  too-slow test rewritten to assert acceptance; `TestEnvelopeRelease`'s sustained-low-IAS-release
  test rewritten to assert no release; `TestUnparkTakeSeedClampsToMode1Limits`'s speed-0 test
  rewritten to assert the exact (unclamped) value flies, not the old floor.
- `body-layer/src/belief/flight_control.py` — `MIN_IAS_KMH` removed; `take_controls` lost its
  `too_slow` parameter and `"TOO_SLOW"` branch; `clamp_speed`'s lower bound is `0.0`;
  `flight_control_limits()` no longer sends `min_ias_kmh`.
- `body-layer/src/belief/crew_console.py` — the `MIN_IAS_KMH` import and the now-dead `ias_kmh`
  field (and its only reader, the `too_slow` computation in `take_controls`) removed.
- `body-layer/src/belief/speech.py` — the `"TOO_SLOW"` template line removed.
- `body-layer/src/belief/flight_authority.py` — `decide_carried_value_speech`'s own docstring
  updated (no `min_ias_kmh` on the wire any more).
- `body-layer/src/body.py` — the `crew_console.ias_kmh = runner.last_ias_kmh` assignment and its
  comment removed; `Runner.last_ias_kmh`'s own docstring updated (the field stays — `belief.
  ai_pilot_wheel`'s IAS-ceiling recovery check still reads it).
- `body-layer/config/rules/README.md` — `flight.take_controls`'s row no longer lists `"TOO_SLOW"`.
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`);
  `MIN_IAS_KMH`'s entry is gone.
- `body-layer/tests/test_flight_control.py`, `test_flight_authority.py`,
  `test_rules_flight_actions.py` — `MIN_IAS_KMH` imports and every `too_slow=`/`ias_kmh=` fixture
  line tied to the removed floor/refusal rewritten or removed (see Tests Added for the new
  assertions each one now carries).
- `body-layer/ROADMAP/BL-16.md`, `body-layer/CLAUDE.md`, `aircraft-layer/CLAUDE.md` — status/
  docs updated (LV-0 reviewed, LV-1 built; the floor removal noted where each file's own earlier
  text described it).
- `docs/acceptance/2026-11-23-bl16-lv1-card.md` — new, the LV-1 card.

### Deviations from the plan

- **The law's own cadence stays per-frame; only the estimator's `LoGet*` reads are gated to
  `LAW_HZ` (unchanged from LV-0).** The plan's "Update rate, not every frame" asks for the full
  law (not only the estimator) to move to the scheduled/interleaved cadence from LV-1 on. Not
  built here: splitting `law_update`'s own state machine (bit-exact take, anti-windup, the
  take-seed subtleties) across interleaved execution phases is a materially larger, separately
  risky change, and the estimator's own `LAW_HZ` gating (LV-0) already removes the bulk of the
  per-frame `LoGet*` cost the user's own reasoning (performance headroom at ~140 Hz) was aimed at
  — `law_update` itself makes no `LoGet*` call at all. Flagged for the architect's own review,
  same posture as LV-0's own analogous deviation (which this one directly continues).
- **The ordinary priority chain (G) is a simplified single-shortfall model, not a fully sequenced
  speed→turn→height solve.** One scalar `shortfall` (how much of the nominal collective rate the
  RPM/stall/pedal-limit/anti-windup guards would not allow this frame) feeds both the pitch
  "speed gives" term and, once a `speed_give_capacity` threshold is crossed, the bank "turn gives"
  scale — height gives last, implicitly, because nothing forces it (the vertical integrator simply
  stops tracking once collective cannot rise further). This matches the user's own ordering
  (speed, then turn rate, then height) but is a first-cut approximation of the hand-off between
  the first two steps, not a measured one — same "first cut, the flights tune" posture every other
  gain in this law already carries.
- **`K_L`/`K_c`/`K_phi_trim`/`K_theta_trim`/`K_ball_pedal` are flat gains, not scheduled by speed**
  (`G(V)` itself — the one schedule the plan's own Tests section names explicitly — IS built, and
  multiplies the three shaper accel caps). The plan's prose names `K_L(V)`/`K_c(V)`/`K_beta(V)` as
  speed-scheduled; building a second per-gain schedule for each of five gains, untested until a
  future card, was judged to add profile surface without proportionate value at this stage — the
  one schedule that the Tests section explicitly requires is the one that is built.

### Tests Added

- `test_flight_control_law.py::TestAntiWindupPreventsTheRetestDivergence` — a take from a bad
  initial attitude (30° bank, 10° nose down, mid-turn: `r_deg_s = 8.0`) must converge, with the
  roll rate staying well below a real-divergence bound (100 deg/s, the retest's own crash reached
  536 deg/s) and bank/pitch never saturating toward ±90° — the main-loop task's own required
  anti-windup/divergence test, directly modelled on the LV-0 debug pass's retest crash
  (`debug-2026-11-23.md`, problem 3).
- `test_flight_control_law.py::TestTakeIsBumpless` — the take seeds the *target* (`phi_d`/
  `theta_d`/`u_c`) from the measured attitude/collective, not a zeroed integrator that would only
  coincidentally cancel out on the first frame.
- `test_flight_control_lua.py` — `TestUnparkTakeRefusals::test_accepted_below_80_kmh_no_hand_back`,
  `TestStage2VoiceTakePrecondition::test_a_voice_take_below_80_kmh_is_accepted_no_hand_back`,
  `TestEnvelopeRelease::test_sustained_low_ias_never_releases_no_hand_back`,
  `TestUnparkTakeSeedClampsToMode1Limits::test_speed_0_in_m2_then_unpark_flies_exactly_0_no_floor`
  — the no-hand-back/no-floor behaviour, at the whole-module level (wire-shaped `limits`, real
  `request_take`/`run_flight_control` dispatch), not only the pure-function toy plant.
- `test_flight_control.py::TestClampHelpers::test_clamp_speed_has_no_floor_only_a_ceiling`,
  `TestWireHelpers::test_flight_control_limits_carries_the_given_on_ground_threshold` (extended) —
  `clamp_speed` and the wire `limits` bundle, body-layer side.
- `test_flight_authority.py::test_a_carried_speed_of_0_is_flown_exactly_no_floor_no_announcement`,
  `test_only_altitude_is_carried_badly_now_speed_has_no_floor` — the carried-value speech no
  longer announces a speed clamp that no longer happens.
- `test_rules_flight_actions.py::test_you_have_controls_accepted_below_80_kmh_no_hand_back` — the
  rule-dispatch level.

### Checks

(both touched subprojects — `world-model/` untouched)

- `aircraft-layer`: `ruff format --check src tests` — pass (90 files); `ruff check src tests` —
  pass; `cd aircraft-layer && .venv/bin/mypy src` — pass (29 files, no issues); `pytest tests -q`
  (full suite) — pass, 1137 passed; `luac5.1 -p` on both touched Lua files — pass; the
  `luac5.1 -l -p` GETGLOBAL check on `flight_control.lua`/`flight_profile.lua` — clean (every
  global is stdlib, a genuine DCS API, or a legitimate cross-module global; `flight_profile.lua`
  reads no global at all).
- `body-layer`: `ruff format --check src tests` — pass (230 files); `ruff check src tests` — pass;
  `cd body-layer && .venv/bin/mypy src` — pass (93 files, no issues); `pytest tests -q -p xdist
  -n auto` (full suite) — pass, 2968 passed, 4 xfailed (one pre-existing `too_slow`-adjacent test,
  `TestDecideCarriedValueSpeech::test_both_parts_carried_badly_announce_both_in_one_call`, found
  broken by the floor removal via `fast-tests.sh body-layer` before the full run, and rewritten —
  see Notable Discoveries).

### Test-impact check (role instruction 1b)

The plan's own per-stage test list for LV-1 names no specific files (the plan's "Tests" section is
written for the whole feature). Checked beyond what LV-0's implementer already confirmed in scope
(`test_export_lua_constants_parity.py` out of scope, `test_dcs_export_lua_local_order.py`
auto-discovering): **`test_flight_authority.py`, `test_rules_flight_actions.py` and
`test_flight_control.py` were not named anywhere and turned out to need rewrites** — each held a
fixture or assertion built directly on the 80 km/h floor (`MIN_IAS_KMH`, `too_slow`, the
carried-value-speech clamp), which U8's "no floor" removes. `grep -rn "MIN_IAS_KMH\|too_slow\|
TOO_SLOW"` across both subprojects' `src/` and `tests/` after the Lua/Python removal is what found
all of them — the kind of miss the role's own instructions warn is silent (the suite still passes
once rewritten; nothing failed loudly until each fixture's own assumption was checked against the
new behaviour).

### Notable Discoveries

- **The toy-plant tests needed real acceleration feedback (`measured.a_r`/`a_u`), not the `law_*`
  functions' own nil-safe fallback to `0.0`, to converge at all.** LV-1's trim loops (`phi_i`/
  `theta_i`) integrate on *measured minus desired* acceleration, replacing the old law's
  turn-rate-based trim; a toy plant that never sets the measured-acceleration fields leaves that
  error permanently equal to the desired value (never shrinking as the plant's own attitude
  converges), so the trim loop either winds up on a real transient and never unwinds (the
  mid-break unpark scenario reached a standing +17° `phi_i` with 100 s to settle, at the original
  `phi_i_bound_deg = 60.0`) or, for the altitude/collective double-integrator plant, oscillates
  outright (`measured.w_mps` swung to ±30 m/s with no `a_u` feedback at all, independent of
  `k_lift_ff`, confirmed by setting it to `0.0` and seeing the oscillation persist). Fixed by
  giving each shared toy-plant driver the real feedback a production estimator would supply
  (`a_r = g·tan(bank)`, `a_u` from the plant's own `w_mps` backward difference) rather than treating
  the fallback as "good enough for a toy plant."
- **`phi_i_bound_deg` tightened from 60° to 8°, with the production default changed to match.**
  Measured directly: the mid-break-unpark scenario would not converge into the heading band at
  60°, 20°, 15° or 12° (residual heading error 11–25°), and did at 8° and below. This is also the
  more defensible design point independent of the measurement — `phi_i` is a secondary trim on top
  of the kinematic feed-forward `phi_ff` (which is unbounded, and alone carries a break's 60–80°
  bank), not meant to be a primary driver of a large bank itself.
- **The anti-windup freeze and the collective-rate guards (RPM floor/blade stall/pedal limit) must
  cap the *combined* feed-forward-plus-integrator rate, not the integrator's own rate alone** — a
  real bug found by `TestRotorEnvelopeGuards` going from "capped" to "uncapped" partway through
  this implementation. `u_c = u_c,ff(n_d) + u_c,i`, and `u_c,ff` is recomputed fresh every frame
  from the desired state (never itself rate-limited) — capping only `u_c,i`'s own nominal step let
  a jump in `n_d` (e.g. a big climb goal) walk straight through the RPM-floor guard via the
  feed-forward term instead. Fixed by computing the guards against the *candidate combined* rate
  (`u_c_candidate - state.u_c) / dt`) and backing `u_c_i` out of whatever capped value actually
  lands, every frame, rather than capping `c_dot` (the old, pre-feed-forward variable name) and
  adding the feed-forward on top uncapped.
- **`TestCollectiveHoldsAltitudeInABankedTurn`'s externally-fixed-bank fixture needed `state.phi_d`
  re-pinned every loop iteration, not just once at take.** `law_update` recomputes `phi_d` fresh
  every frame from `phi_ff + phi_i`; since this specific toy plant never commands a turn (it fixes
  `measured.bank_deg = 40.0` as an environmental condition, to isolate the altitude/collective-vs-
  pitch split from bank-tracking physics), `phi_ff ≈ phi_i ≈ 0` and `law_update`'s own next frame
  overwrites the test's one-time `state.phi_d = 40.0` override straight back to ~0 — tripping
  section H's "attitude not following" anti-windup gate (a genuine 40° mismatch) and freezing every
  trim integrator the test means to exercise. Re-pinning `phi_d` after every `law_update` call
  (not just once) keeps the gate satisfied for the duration the fixture's own premise requires.
- **One pre-existing test outside both files' own obvious scope broke silently**:
  `test_flight_authority.py::TestDecideCarriedValueSpeech::test_both_parts_carried_badly_announce_
  both_in_one_call` expected two carried-value announcements (speed *and* altitude) from an unpark
  at `ias_kmh=0.0`/`alt_m=0.0` — the speed half no longer fires (no floor to clamp up to), so the
  full-suite run (`pytest -p xdist -n auto`, this project's own DoD command) found exactly one
  failure where `fast-tests.sh`'s targeted selection also caught it, confirming the full run adds
  no further surprises for this change. Rewritten to assert the one remaining (altitude)
  announcement.
