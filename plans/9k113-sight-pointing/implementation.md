### Implementation Summary

BL-B80 Stages 1–3 of `plans/9k113-sight-pointing/plan.md` (Stage 4 is the live sortie, not
implemented here). Coordinator amendments (2026-10-22) applied throughout: reactive-only
ShowMenu, `ai_believed_on` gating the OBSERV-falling-edge press, never-latch self-correction,
elevation rate split in Export.lua, placeholder detector timing (0.5 s / 2.5 s).

### Files Changed

- `aircraft-layer/dcs-export/Export.lua` — new per-frame sight owner: `DEV_I9K113`/`CMD_AI_AZ`/
  `CMD_AI_ELEV` constants, the `sight_target` inbound op (`handle_sight_target_command`), the
  rate limiter (`sight_rate_limit_step`, 20°/60/s az, 0.5/0.667 raw/s elev split per the
  coordinator amendment), the centre-target azimuth bias, the AI-on/off detector with
  `ai_believed_on` self-correction, OBSERV-falling-edge reset of all per-OBSERV state, and the
  mission-stop reset mirroring `pending_release_t`'s. `EXPORT_SCRIPT_VERSION` bumped to
  `"2026-10-22"`. Pruned a stale comment on `SIGHT_POS_EPSILON` that claimed BL-B80's deadband
  "is a body-layer concern, not this one" — it now lives in this file.
- `aircraft-layer/src/collector/server.py` — `EXPECTED_EXPORT_VERSION` bumped to match, paired
  commit per that file's own convention.
- `aircraft-layer/src/collector/command_sender.py` — `CommandSender.send_sight_target(az_cmd,
  elev_cmd)`, same shape/raise posture as `send_cockpit_switch`.
- `aircraft-layer/src/api/server.py` — `POST /command/sight_target`, reusing the existing
  `command_sender` instance. Adds the Security plan review's non-blocking recommendation: both
  values clamped to `_SIGHT_TARGET_CMD_BOUND = 1.5` (±90° equivalent in raw command units)
  alongside the finite-float check.
- `aircraft-layer/tests/test_sight_target.py` (new) — `CommandSender.send_sight_target` +
  `POST /command/sight_target` endpoint tests, mirroring `test_cockpit_switch.py`'s structure.
- `body-layer/src/belief/sight_effector.py` — `sight_azimuth_deg_to_raw` (azimuth's inverse);
  `sight_elevation_raw_to_deg`/`sight_elevation_deg_to_raw` (elevation's new derived conversion —
  see "Notable Discoveries" below for a correction made mid-implementation); `GYRO_ALIGNMENT_S`
  tunable (`tuning.real`, 10.0, `lo=5.0, hi=20.0, status="measured"`); `GuidanceUnitState.
  observ_observed_since_sim` (new field) and `in_gyro_alignment`; `refresh_readback` gained an
  optional `now_sim` parameter to stamp the rising/falling edge; `write_sight_target` (the
  once-per-poll aim-setter). Pruned the stale "no consumer reads `observ_observed`" docstring
  claim, since `logger.py`'s `home_phase` derivation now does.
- `body-layer/src/aircraft_client.py` — `AircraftLayerClient.write_sight_target(az_cmd, elev_cmd)`.
- `body-layer/src/belief/optic_policy.py` — `advance_sight_aim` gained optional `sight_az_raw`/
  `sight_elev_raw` parameters: each axis independently prefers the real readback (converted via
  `sight_effector`) over the pass-through model.
- `body-layer/src/logger.py` — `run_once`: (1) derives `OpticState.home_phase` from
  `self.guidance_unit_state.observ_observed` every poll (the carried-forward BL-B66 gap), one
  poll lagged since `refresh_cockpit_switch_readback` runs after `run_once` in the poll loop;
  (2) immediately after `decide_optic` returns, caps a sight-tier optic to `BINOCULAR_OPTIC`
  while `in_gyro_alignment`; (3) threads `sight_az_raw`/`sight_elev_raw` into `_apply_active_gaze`
  → `advance_sight_aim`. `_run_crew_text_poll_loop`: the `observ_transition` drain block no
  longer sets `home_phase` (only the cockpit write + hands-busy suppression); a new block sends
  `write_sight_target` every poll while `home_phase is SIGHTING`, idle included;
  `refresh_cockpit_switch_readback` now passes `runner.last_t_sim` to stamp the gyro-alignment
  window.
- `body-layer/src/sight_trace_writer.py` — elevation's `_row` branch now prefers the readback
  (via `sight_elevation_raw_to_deg`) the same way azimuth already did, once a raw sample exists.
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`) for the
  new `GYRO_ALIGNMENT_S` tunable.

### Tests Added

- `aircraft-layer/tests/test_sight_target.py` — `send_sight_target` datagram shape/failure;
  `/command/sight_target` valid/boundary/out-of-bounds/missing-field/non-finite/503/500 cases.
- `body-layer/tests/test_sight_effector.py` — `sight_azimuth_deg_to_raw` inverse;
  `sight_elevation_raw_to_deg`/`sight_elevation_deg_to_raw` at the two mechanical stops and the
  measured piecewise-gauge readback; `in_gyro_alignment` at the window's edges and with no
  rising edge recorded; `refresh_readback`'s new `now_sim` stamping (rising edge, no restamp
  while already on, clearing on falling edge, `None`-`now_sim` no-op, falling-then-rising reset);
  `write_sight_target` degree→raw conversion (including negative elevation) and raise-on-failure.
- `body-layer/tests/test_sight_trace_writer.py` — replaced the now-superseded
  `test_actual_elevation_is_always_model_source_never_readback` with
  `test_actual_elevation_prefers_readback_and_converts_to_degrees` +
  `test_actual_elevation_falls_back_to_model_when_no_readback` (see Notable Discoveries).

### Checks

**aircraft-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass (26 source files)
- pytest: pass (459 passed, including `test_dcs_export_lua_local_order.py` and
  `test_dcs_export_lua_syntax.py` against the modified `Export.lua`)

**body-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass (70 source files)
- pytest: pass (2417 passed, 4 xfailed) — one run hit an unrelated flaky failure
  (`test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop`, a `caplog`-based
  test touching no code this plan changed) that passed in isolation and on a clean re-run of the
  full suite; not attributable to this change.

### Notable Discoveries

- **The plan's elevation formula direction needed correcting during implementation**, caught by
  the first unit test written against it. The plan states one formula
  (`elevation_deg = arg_876 * 20.0`, both signs) for "the derived calibration" without
  distinguishing two different domains: the **readback argument** (`arg_876`, what
  `get_argument_value` returns) is linear in degrees with one constant (×20.0) for both signs —
  the piecewise 0.75 gauge factor on the *negative* side of the argument exactly cancels against
  the 20/15 degree-per-unit asymmetry, which is the elegant fact the plan is pointing at. But the
  **command value** sent via `SetCommand` (what `write_sight_target`/Export.lua's rate limiter
  actually write) needs the *piecewise* 20/15 split directly, with no cancellation, since there is
  no readback step on the way out. My first implementation applied the piecewise split to
  `sight_elevation_raw_to_deg` (the readback direction) by mistake, which a unit test asserting
  `sight_elevation_raw_to_deg(-0.75) == -15.0` immediately caught (it returned -11.25). Fixed:
  `sight_elevation_raw_to_deg` is now the single ×20.0 formula (readback domain);
  `sight_elevation_deg_to_raw` is the piecewise one (command domain) and is **not** a literal
  inverse of the former — both functions' docstrings now say so explicitly. Export.lua's own rate
  constants (`SIGHT_RATE_ELEV_UP/DOWN_RAW_PER_S`) were already correct (command domain), so only
  the body-layer readback conversion and its comment needed the fix.
- **Test-impact check (per role instructions):** grepped for every test touching `optic_policy`,
  `sight_effector`, `sight_trace_writer`, `advance_sight_aim`, `refresh_readback`,
  `observ_transition`, and `GuidanceUnitState` construction sites before starting. Two existing
  tests' assertions were **direct, foreseeable consequences of the plan's own explicit scope**
  (elevation gaining a readback conversion) and were updated rather than left contradicting new
  behaviour: `test_sight_trace_writer.py::test_actual_elevation_is_always_model_source_never_
  readback` (renamed/split into two tests covering readback-preferred and model-fallback) and
  one assertion inside `test_logger.py::test_slew_trace_is_written_from_the_real_poll_loop`
  (`actual_elevation_source != "readback"` → `== "readback"` with the correct degree value). No
  test named in the plan turned out to be missing or already-folded (the plan's own "Tests:"
  bullets per stage matched the actual suite).
- **`test_observ_off_command_stops_the_sight_through_the_real_poll_loop`** (test_logger.py) is a
  **self-contained reproduction** of the old `observ_transition == "off"` drain block — it
  constructs its own local `if console.observ_transition == "off": ...` snippet rather than
  calling `logger.py`'s real code, so it still passes unchanged, but its docstring's claim
  ("Reproduces the exact ... drain block logger.py's poll loop runs") is now stale: the real block
  no longer sets `home_phase` there. Left as-is (it tests no changed production path and
  rewriting it was outside this plan's stated scope), flagged here for whoever next touches that
  test.
- **`sight_elevation_deg_to_raw`/`sight_elevation_raw_to_deg` operate on two different domains**
  (command value vs. readback argument) that happen to share the same physical degree mapping only
  on the positive side — this is exactly the kind of cross-key/cross-domain coupling the
  Implementer role's standing guidance asks to flag even without a guard: nothing in the type
  system distinguishes "a command value" from "a readback argument" (both are bare `float`), so a
  future caller swapping one function for the other at a call site would silently produce a wrong
  but plausible-looking number. Not guarded in code; flagged here per that guidance.

### Review fixes

`plans/9k113-sight-pointing/review.md`'s five required fixes, all applied:

1. **`Export.lua:1215-1239` — `ai_off_since` unconditional reset.** Removed the unconditional
   "Reset either way" line; `ai_off_since` is now reset only inside the inner `if` block,
   immediately after a `ShowMenu` press actually fires. Verified the fix is load-bearing by
   manual trace (no automated test reaches this file): with the unconditional reset, `(t -
   ai_off_since)` could never exceed one frame's `dt`; with it removed, `ai_off_since` holds the
   original stuck-since timestamp until either the readback responds again (`else` branch,
   clearing it to `nil`) or a press fires and restarts the window — the "never latch off" property
   (re-press after `AI_OFF_REPRESS_INTERVAL_S` while still stuck) is preserved because a press
   without a confirming readback leaves `ai_off_since` reset to `t`, so the next timeout starts
   fresh rather than firing every frame.
2. **`body-layer/src/logger.py:782-800` — gated `sight_az_raw`/`sight_elev_raw`** at the
   `_apply_active_gaze` call site on `optic_decision.optic` (the post-cap value) being
   `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`; `None, None` otherwise. Added
   `test_run_once_caps_a_sight_tier_optic_during_gyro_alignment` (`test_logger.py`), which combines
   a non-sight optic (the gyro-alignment cap) with a stale `sight_az_raw`/`sight_elev_raw` already
   present in `guidance_unit_state` and asserts the gaze is not anchored to it — confirmed this
   assertion fails against the pre-fix code (reverted the gating change, reran the test in
   isolation: `runner.optic_state.actual_aim_azimuth_deg` was the readback's 68.18°, not the
   desired 12°; restored and reran clean, `src/logger.py` sha unchanged from the fixed version
   before/after the probe).
3. **Added the missing `run_once`-level integration test** the plan's Stage 1 test list specified
   — `test_run_once_caps_a_sight_tier_optic_during_gyro_alignment`, above. Monkeypatches
   `logger.decide_optic` to force a sight-tier decision regardless of input (isolating the cap's
   own logic from `decide`'s real dispatch, which has its own separate unit tests), drives one
   poll inside the 10 s gyro-alignment window (asserts the cap holds) and one poll after it ends
   (asserts the cap lifts and the optic becomes the sight-tier one `decide_optic` chose). Also
   doubles as fix 2's test, per the review's own observation that this is "the natural place to
   catch" it.
4. **`Export.lua:1076` — wrapped `sight_point_quiet`'s `GetDevice(DEV_I9K113)`** in `safe_call`,
   matching every other `GetDevice` call site's convention in this file.
5. **`test_logger.py` (`test_observ_off_command_stops_the_sight_through_the_real_poll_loop`) —
   corrected the stale docstring.** It no longer claims to reproduce the current `observ_
   transition == "off"` drain block (which no longer sets `home_phase`); it now states explicitly
   that it covers only the hands-busy-suppression/cockpit-write half, and that `home_phase` is
   set directly in the test as a starting state for `decide`'s dispatch, not through any
   reproduced drain logic.

**Optional items**: left all three as-is, per the review's own "not blocking" verdict on each
(the elevation-rate wrong-side-of-zero cosmetic case, the `NewType`-per-domain structural
suggestion, and `AC-B11.md`'s endpoint-count housekeeping note) — none were trivially safe to fold
in without their own small design decision, and the review did not ask for them.

**Checks after the fixes** (same commands as above): aircraft-layer — `ruff format --check`
(pass), `ruff check` (pass), `mypy --strict` (pass, 26 source files), `pytest` (459 passed,
including `test_dcs_export_lua_local_order.py`), `luac5.1 -p Export.lua` (pass), the `GETGLOBAL`
mechanical scan (clean — only stdlib/DCS globals). body-layer — `ruff format --check` (pass),
`ruff check` (pass), `mypy --strict` (pass, 70 source files), `pytest` (2418 passed, 4 xfailed —
one more passed than the pre-fix run, the new integration test; the previously-flaky
`test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop` did not recur).
