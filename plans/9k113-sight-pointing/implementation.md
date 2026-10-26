# BL-B80 v2 — implementation record

## Status 2026-10-22: Stages 1–4 (with 3b) built, unreviewed; Stage 0 pending

Built against `plan.md` v2 (tip `1c433fc6`). The implementing agent's session was **terminated
early by an automated content check** before it committed anything or wrote this file; its
uncommitted work was preserved by the main loop as one WIP commit, **`e16e31e2`**, then the branch
was merged with `main` (`90cf2ec0`). Checks on the WIP, run by the main loop:

| subproject | ruff | mypy --strict | pytest |
|---|---|---|---|
| aircraft-layer | clean | clean (27 files) | 527 passed |
| body-layer | clean | clean (71 files) | 2431 passed, 4 xfailed |

Lua: `luac5.1 -p` clean on every `dcs-export/*.lua`.

**Deviations from the plan and the project rules, all caused by the early stop:**

- **One commit for all stages**, not one per stage; the removal-only Stage 1 commit does not exist
  as a separate commit.
- **Mechanism and calibration share that commit** (`SEEN_AIM_HEIGHT_OFFSET_M` = 1.2 m, pilot's
  2026-10-22 answer *"let's assume on ground"*, lands with the seen-aim mechanism).
- **Stage 0 (calibration probe, Flight A)** was not built by the implementer; the main loop built it
  afterwards: `aircraft-layer/dcs-export/Export.probe-9k113-calibration.lua` (from run 11's probe;
  luajit mock-run clean) and its card `docs/acceptance/2026-10-22-bl-b80-v2-flight-a.md`.
- No per-stage notes from the implementer; what was built has to be read from the diff.

Present in the WIP (by search, to be confirmed by review): `belief/sight_head.py` (+ tests),
`attack_run.seen_world_direction`, `select_sight_goal`, `SEEN_AIM_HOLD_S`, `SEEN_AIM_HEIGHT_OFFSET_M`,
the F2/F3 fences and the F4 differential no-leak test (`tests/test_logger.py`), lamps 898/960/962 on
the cockpit-switch feed, the `sight_servo` schema/cache/endpoint (+ API and luajit tests),
`SERVO_WOBBLE` in `Export.lua`, `t_sim` validation, the `body-layer/CLAUDE.md` invariant edit, and
regenerated `config/defaults.toml`. `ShowMenu`/`ai_believed_on` are gone; `GYRO_ALIGNMENT_S` survives
only in a docstring.

### Review fixes (v2 review, 2026-10-22)

The three required fixes in `review.md`'s v2 section, one commit each (`28d45a09`, `ebd48c41`,
`fdfe3948`). body-layer only; aircraft-layer untouched.

**1 — `defaults.toml` first sentence.** `tools/generate_defaults.py`: `_SENTENCE_SPLIT` no longer
splits on a period inside a double-quoted span (an even number of `"` must follow it), and
`_first_sentence` no longer strips `` ` ``/`*` off both ends. Markup the split consumed after the
period (`.**`, `` .` ``) is either dropped together with its opening, when it wrapped the whole
sentence, or put back after the period. The regeneration repaired **9** rendered entries: the two in
the review, plus 7 already on the branch that had lost a leading backtick (5:
`ATTACK_RUN_ELEVATION_GATE_DEG`, `ATTACK_RUN_LINED_UP_AZIMUTH_DEG`, `BUILT_UP_VILLAGE_MAX_AREA_M2`,
`ATTACK_TARGET_LOS_MAX_AGE_S`, `FIRING_MAX_AGE_S`) or a closing one (2: `IDENTITY_HALF_LIFE_S`'s
`*is*`, `MEDRES_ANGULAR_RADIUS_RAD`'s `` `LOWRES_ANGULAR_RADIUS_RAD` ``). No sentence boundary moved
in any other entry (diffed the whole rendered file). Both new `#:` comments now open with a
pilot-facing sentence (what it does, which way is dangerous, what the default is in the world);
the pilot's verbatim quote moved to the second sentence. New
`tests/test_generate_defaults_first_sentence.py` (7 tests); 4 of them fail against the
pre-fix generator (quoted period, closing backtick, opening backtick, mid-sentence bold), restored
by `shasum`. The quote rule is only sound when quotes are balanced, so one test holds every
declaration's comment block to an even `"` count, and checks it scanned as many blocks as
`collect_declarations()` found.

**2 — F4 widened.** `_f4_scenario` now runs four polls through `_f4_poll`, which calls the crew-text
loop's own belief-to-speech sinks in that loop's order (`run_once`, attack-run transition + `drain_
attack_run`, the real `logger._mission_memory_step`, `drain_events`, `drain_pending_positional_
replies`), with `select_target armor` after poll 1 and `mark_target` + `engage` after poll 2 (the
seen poll). It is driven inline rather than through the threaded `_run_crew_text_poll_loop`
because a differential test needs both runs to see the same polls, and that loop rebuilds
`runner.sources`. It compares `ContactStore` positions, `MissionMemory` entries, every utterance,
and every `TOOL_SET` result (all 17, keyed by name and asserted equal to `TOOL_SET`'s own names so
a new tool cannot escape). Each comparison also asserts it is non-empty. `Entry.t_wall` is pinned,
because it is the one field two runs differ in whatever the seen aim does. The world-model
connection is an empty built store (`open_for_build`), so the enrichment-taking tools can run.
**Red runs** (mutations in `logger.py`, restored by `shasum`): seen aim written into the
looked-at contact's position → positions, memory, utterances, tools all fail; seen aim shifting a
commanded mark's `t_sim` → memory and tools fail; seen aim setting the contact's attention to
`ignore` → tools fail. A first draft of that last mutation set `priority` and stayed green. That
was the mutation's mistake, not the test's: `select_target` had already made the contact
`priority`.

**3 — wiring tests.** `test_run_once_perceives_through_the_world_stabilised_head_not_the_desired_aim`
(Stage 3): desired 50° right throughout; actual aim 0 → 20 → 10° over three 1 s polls, the last
after a 30° turn. `test_run_once_seen_look_moves_the_next_goal_onto_the_true_direction` (Stage 3b):
poll 2's goal is the true direction (0°, `atan(1.2/1000)`), not belief's (12°, −3°), and the
contact's position is unchanged. **Red runs**, each restored by `shasum`: Stage 3, perception fed
`optic_decision.look_azimuth_deg` instead of the head → the new Stage 3 test fails; the not-free cap
removed → the existing `test_run_once_caps_a_sight_tier_optic_until_the_head_is_free` fails (the
review's suggested mutation). Stage 3b, `look_contact=None` passed to `advance_sight_head` → fails;
the `last_sight_look_sim` stamp removed → fails; `select_sight_goal`'s `seen` row disabled (goal
always from belief, the plan's own mutation) → the new 3b test and F4's
`test_the_heads_own_aim_source_differs` fail, while F4's four identity tests stay green, as they
should.

**Checks (body-layer)**: `ruff format --check` pass, `ruff check` pass (`src tests tools`), `mypy
src` pass (71 files), `pytest` 2443 passed, 4 xfailed.

**Open, not fixed:** the plan's F4 spec says *"a target inside the sight FOV under both aims"*. The
scenario uses a canned `FakeSource`, so perception does not depend on the aim at all. It proves the
seen value does not reach the sinks downstream of perception. It does not prove that a changed aim
cannot change what a real `NakedEyePerceptionSource` admits. The plan allows that difference (*"it
can change how many looks he gets"*).

---

## v1 (superseded — position-command model)

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

### Exponent-float fix (2026-10-22)

**The bug.** `CommandSender.send_sight_target`/`send_cockpit_switch` built their datagram with
`json.dumps`, which emits exponent notation for small magnitudes
(`json.dumps({"az_cmd": 0.00001})` → `'{"az_cmd": 1e-05}'`). `Export.lua`'s
`extract_json_number_field` (line ~959) matched `"field"%s*:%s*(-?%d+%.?%d*)` — plain decimal
digits only — and silently stopped at the `e`: `"1e-05"` parsed as `1` (a 60°-equivalent sight
command from a near-zero intent), `"-3.3e-07"` as `-3.3`. Any `|value| < 1e-4` was affected, a
magnitude body-layer float arithmetic near sight centre readily produces. `cockpit_switch`'s
`value` field shares the same extractor, so it carried the same latent defect.

**Files changed:**

- `aircraft-layer/src/collector/command_sender.py` — new module-level `_format_fixed_point(value)`
  helper: renders a float as fixed-point decimal (9 decimal places, trailing zeros trimmed, at
  least one digit kept after the point so e.g. `0.0`/`-0.0` stay valid JSON numbers), never
  exponent notation. `send_sight_target`'s `az_cmd`/`elev_cmd` and `send_cockpit_switch`'s `value`
  now hand-build their JSON object string using this helper for the float field(s) instead of
  `json.dumps` — `device`/`cmd` stay plain Python ints spliced directly, since they were never the
  affected fields. One helper, reused by both ops, per the fix's own instruction not to hand-roll
  JSON beyond what's needed.
- `aircraft-layer/dcs-export/Export.lua` — `extract_json_number_field`'s pattern gained an
  optional exponent (`[eE]?[%-%+]?%d*`), and the function now rejects a non-finite `tonumber`
  result (NaN, or `math.huge`/`-math.huge` from a huge exponent overflowing, e.g. `"1e999"`)
  before returning — moved into the shared extractor itself rather than left to each caller, so
  "accept exponents, then check finite/range" holds regardless of which op calls it. Comment above
  the function rewritten to state what actually happened (the old comment's "digits-only, so
  non-finite is unreachable" claim was the bug's own premise). Added `SIGHT_TARGET_CMD_BOUND =
  1.5` (mirrors `api.server`'s `_SIGHT_TARGET_CMD_BOUND`) and a range check inside
  `handle_sight_target_command`, since a finite-but-huge exponent value (e.g. `"1e10"`) would
  otherwise pass the extractor's new finite check and still be a nonsense command —
  `cockpit_switch`'s own existing NaN/huge re-check in `handle_cockpit_switch_command` was left
  as-is (now genuinely redundant rather than falsely claimed redundant, see the memory file below);
  no range check was added there since that op's whole point (BL-B66, user direction 2026-10-21)
  is accepting any value for any switch.
  `EXPORT_SCRIPT_VERSION` bumped to `"2026-10-22b"`.
- `aircraft-layer/src/collector/server.py` — `EXPECTED_EXPORT_VERSION` bumped to match, same
  paired-commit convention as every other wire-format version bump in this file.
- `aircraft-layer/tests/test_exponent_float_fix.py` (new) — `TestSenderNeverEmitsExponentNotation`
  covers `_format_fixed_point` directly (1e-05, -3.3e-07, 0.0, -0.0, 0.25, -0.5) plus both
  `CommandSender` methods' actual datagram bytes; `TestExportLuaExtractorAcceptsExponentAndRejectsNonFinite`
  extracts the live `extract_json_number_field` source out of `Export.lua` (balanced
  `function`/`if`/`end` counting, so it is the real currently-deployed function, not a hand-copied
  duplicate that could drift) and runs it against a real Lua interpreter (`luajit` preferred,
  falling back to `lua5.5`/`lua5.1`/`lua`, skipping cleanly with none installed) for `1e-05`,
  `-3.3e-07`, `0.25`, `-0.5`, and `1e999` (overflow → `inf` → must come back `nil`).
  **Counterfactual run**: reverted the extractor to its old digits-only pattern and re-ran this
  Lua-side test class — it failed exactly as expected (`"1e-05"` → `1`, `"1e999"` → `1` instead of
  `nil`), then the revert was undone and `shasum` on both touched files confirmed an exact restore
  before continuing.
- `.claude/agent-memory/security/project_export_lua_json_extractor_cannot_yield_nonfinite.md` —
  rewritten. Its premise (the digits-only regex makes non-finite values unreachable, so a missing
  re-check is not a gap) was the bug's own blind spot: the regex doesn't reject exponent notation,
  it truncates it into a different, in-range-looking number that no `nil`/non-finite check could
  ever catch. The corrected entry states what the fix actually does and draws the generalizable
  lesson (verify a "this input can't happen" claim by constructing the adversarial input, not by
  re-reading the regex's intended character class).

**Checks**: aircraft-layer — `ruff format --check` (pass), `ruff check` (pass, after `--fix` for
two `UP012` unnecessary-`encoding`-argument lints on the new `.encode()` calls), `mypy --strict`
(pass, 26 source files), `pytest` (469 passed — the 10 new tests on top of the previous 459, same
count as before this fix), `test_dcs_export_lua_local_order.py` run by name (32 passed, confirming
the new Lua code introduces no local-read-as-global defect). body-layer untouched by this fix, so
its checks were not re-run.

### Stage 6 (v3 — the real sight never leaves the ASP-17 field, 2026-10-26)

Merged `9dfc3d2f` (plan's v3 section) and implemented it exactly as planned — the root-cause fix
(`setpoint_inside_field`'s wrong-magnitude gate replaced by `sight_mark_is_clipped` against the
mark's own raw reading), the always-closed loop on `field_target` (`sight_clip_to_field_body_deg`,
the setpoint radially projected onto the inset ASP-17 field), part 3's feed-forward switch to
`field_target`'s own finite difference while sliding, the merged `homing` mode (renamed from
`open`, its meaning changed), and the shared stall detector covering both `closed` and `homing`.
Open loop (`sight_estimate_body_*_deg`, `OPEN_LOOP_SAT_DEG`, `OPEN_LOOP_DEADZONE_DEG`) removed
entirely, not kept as a fallback, per the plan's own instruction.

**Files changed:**

- `aircraft-layer/dcs-export/Export.lua` —
  - New constants: `ASP17_FIELD_AZ_HALF_DEG`/`ASP17_FIELD_EL_HALF_DEG` (4.3, az measured/el
    placeholder) and `ASP17_FIELD_MARGIN_DEG` (0.5, guess), replacing the now-unused
    `FIELD_MARGIN_DEG` (see Notable Discoveries); `HOMING_SAT_DEG` (6.0) replaces
    `OPEN_LOOP_SAT_DEG`/`OPEN_LOOP_DEADZONE_DEG`, which are deleted along with the open-loop
    branch they served.
  - New pure functions `sight_clip_to_field_body_deg` (the plan's own ray-to-box clip, verbatim)
    and `sight_mark_is_clipped` (root-cause check), placed above `run_sight_servo`.
  - `run_sight_servo` rewritten: `field_target_body_az/el_deg` computed every frame
    (`sight_clip_to_field_body_deg` called with the **margin-reduced** half-angles
    `ASP17_FIELD_*_HALF_DEG - ASP17_FIELD_MARGIN_DEG`, not the raw field half-angle — see Notable
    Discoveries for why that call shape, not the raw one, is what the plan's own property-test
    wording requires); feed-forward uses `field_target`'s own per-frame finite difference whenever
    `scale < 1.0`, the raw goal rate otherwise; `closed`/`homing` split on
    `sight_mark_is_clipped`, both sharing one error/command formula (`closed` unsaturated beyond
    the write clamp, `homing` capped at `HOMING_SAT_DEG`); stall detection unified across both
    modes, gated on having a numeric mark to measure motion from.
  - `push_sight_servo_state` gains `field_target_azimuth_deg`/`field_target_elevation_deg`/
    `mark_clipped`.
  - `push_slew_trace` (the per-**frame** debug log, `--slew-trace`'s sibling) gains
    `mark_az_raw`/`mark_el_raw` (raw 566/555) and a computed `mark_clipped` flag — the user's own
    ANSWERED decision (*"Elevation - measure in flight"*): this is what a calibration flight reads
    to find 555's real clip edges, independent of the `ASP17_FIELD_EL_HALF_DEG` placeholder.
    **Moved the whole function below `sight_mark_is_clipped`/the new constants**, since it now
    reads them — see Notable Discoveries, this was a real local-read-as-global bug caught before
    it shipped, not a style choice.
  - `LuaExportStop` and every other state-reset site (OBSERV off, caged, hold) updated for the new
    fields (`sight_field_target_body_az/el_deg`, `sight_mark_clipped`,
    `sight_prev_field_target_body_az/el_deg`) and the removed ones
    (`sight_estimate_body_az/el_deg`).
- `aircraft-layer/src/schema/sight_servo.py` — `SightServoState` gains
  `field_target_azimuth_deg`/`field_target_elevation_deg: float | None` and `mark_clipped: bool`
  (required, same posture as `stalled`); docstring's mode list updated (`"open"` → `"homing"`).
- `aircraft-layer/tests/test_sight_servo_lua.py` — `TestSightClipToFieldBodyDeg` (incl. a property
  test over 11 setpoint samples pinning the margin-inset bound), `TestSightMarkIsClipped`, and
  `TestRunSightServoFieldPark` (7 end-to-end tests against the real `run_sight_servo`, via a new
  `_run_field_park_sequence` mock-run harness extending `_run_servo_off_sequence`'s pattern with a
  `GetDevice` mock covering 898/566/555 and mocked `LoGetSelfData`/`LoGetADIPitchBankYaw` at level
  flight). Covers every test the plan names: convergence against the reverted-field-target
  mutation, the root-cause regression (mark at clip edge, field_target inset → `homing` not
  `closed`), one-frame recovery to `closed`, the feed-forward finite-difference fix and its named
  mutation (raw-rate reversion), `homing` feeding the stall detector, continuous (non-latching)
  edge tracking, and the stall detector staying silent while the mark cleanly tracks a sliding
  target.
- `aircraft-layer/tests/test_sight_servo_api.py` — `_LINE` and the dict-literal tests extended
  with the two new fields (an unplanned but necessary ripple from making `mark_clipped` a
  *required* field — see Notable Discoveries); the one `"open"`-as-example-value test relabelled
  `"homing"` per the plan's own instruction.
- `body-layer/CLAUDE.md` — the `--slew-trace` clause gained one sentence: the new
  `field_target_*`/`mark_clipped` fields exist on `GET /sight_servo/latest` as of this stage, but
  `sight_trace_writer.py` does not read them yet (deliberately out of this stage's scope — see
  below).
- `notes/the-9k113-sight-bl-b64.md` — new bullet, occurrence 5 of the recurring
  field-of-regard-enforcement defect (the plan's own text, lightly adapted).

**Checks**: aircraft-layer — `ruff format --check` (pass, after `ruff format` auto-reformatted the
new test file once), `ruff check` (pass, after fixing one `UP032` format-call and one `RUF007`
zip-over-pairwise finding by hand), `mypy --strict` on `src` (pass, 25 source files) and on the
two touched test files directly (pass, strict), `pytest tests -q` (607 passed, up from 553 — 46 in
`test_sight_servo_lua.py`'s new classes, plus the `test_sight_servo_api.py` additions),
`luac5.1 -p` (pass) and the `GETGLOBAL` own-helper check (clean) on `Export.lua`,
`test_dcs_export_lua_local_order.py` (41 passed, parametrized over every `dcs-export/*.lua` file —
this is the test that would have caught the `push_slew_trace` ordering bug below had it shipped).
body-layer had no source change (CLAUDE.md only), so its checks were not re-run; confirmed by
`git status --porcelain` showing only the one doc file under `body-layer/`.

**No new behaviour-affecting constant went through `tuning.py`**: `ASP17_FIELD_AZ_HALF_DEG`,
`ASP17_FIELD_EL_HALF_DEG`, `ASP17_FIELD_MARGIN_DEG`, and `HOMING_SAT_DEG` are Lua-only, same
posture the plan states for every other constant in this file ("no tuning mechanism outside
body-layer") — flagged per that rule's own instruction to note it rather than improvise a second
loader.

**Notable Discoveries:**

- **`FIELD_MARGIN_DEG` became dead code, not merely superseded, once `setpoint_inside_field` was
  removed.** The plan's own text ("`FIELD_MARGIN_DEG`/`GIMBAL_*` stay exactly as they are — still
  correctly used elsewhere") is accurate for `GIMBAL_*` (the gimbal clamp, step 2, is genuinely
  unchanged) but not for `FIELD_MARGIN_DEG` itself: a `grep` of the pre-fix file shows its only use
  was inside the very check being replaced, and no other call site reads it. Removed it rather
  than leave an unused constant with a comment claiming it is still load-bearing; said so here
  rather than silently reinterpreting the plan.
- **`sight_clip_to_field_body_deg` must be called with the margin-reduced half-angle
  (`ASP17_FIELD_*_HALF_DEG - ASP17_FIELD_MARGIN_DEG`), not the raw field half-angle**, even though
  the plan's own Lua snippet for the function takes `field_az_half_deg`/`field_el_half_deg` as
  bare parameters with no margin baked in. The plan's property-test wording settles this: it
  requires `field_target` to never exceed `ASP17_FIELD_AZ_HALF_DEG - ASP17_FIELD_MARGIN_DEG` on
  either axis, which is only true if the *caller* passes the margin-reduced value as the clip
  bound. One consequence worth flagging rather than silently accepting: since
  `sight_mark_is_clipped`'s own clip threshold is computed as the exact same value
  (`field_half_deg - margin_deg`), a mark that has fully converged onto a fully-saturated
  `field_target` sits exactly *at* the mark's own clip threshold, not safely inside it — the
  boundary-churn risk the plan's own "Risks & Unknowns" section already names and defers to a
  flight-tuned margin, not a defect introduced here.
- **`push_slew_trace` had to move**, not just gain two fields. It is defined early in `Export.lua`
  (originally directly after `safe_call`), far above where `sight_mark_is_clipped` and the
  `ASP17_FIELD_*`/`MARK_*` constants are declared. Referencing them from the original location
  would have reproduced the exact "local read as global" bug `test_dcs_export_lua_local_order.py`
  exists to catch (and that this same function caused once before, 2026-10-21, per its own
  comment) — caught by running that test, not by inspection, before it was ever committed. Moved
  the whole function to just after `sight_mark_is_clipped`, well before its one call site.
- **Making `mark_clipped` a required field (mirroring `stalled`) rippled further than the plan's
  one-line note ("the one test using `'open'` ... is relabelled") implied.** Every existing
  `test_sight_servo_api.py` test built around the module-level `_LINE` fixture or a literal
  `SightServoState(...)`/expected-dict construction needed the two new fields added, or parsing
  failed with a `SightServoParseError` the plan's own file list did not anticipate. Flagging this
  as the "test-impact list is a hypothesis" case the role's own process asks for: the plan named
  one test, the actual diff touched five.
- **Stage 6 deliberately stops short of wiring `field_target_*`/`mark_clipped` into
  `sight_trace_writer.py`'s own columns**, even though the plan's "Affected Modules/Files" section
  (written for v3 as a whole) names that file. The Implementation Plan's own Stage 6 bullet is
  explicit that this stage is aircraft-layer-only and needs no body-layer check re-run — a
  body-layer source change would contradict that. Resolved by writing the `body-layer/CLAUDE.md`
  clause to describe what is actually true after this stage (the fields exist on the API, the
  trace writer does not yet read them) rather than what the broader v3 section's prose implied.
  Said here explicitly since it is a real scope narrowing, not an oversight.
