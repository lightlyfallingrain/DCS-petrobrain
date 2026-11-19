### Debug Report

### Observed Issue

2026-11-19 sortie, mode 1 (unparked, raw axes), flown on `main` at `bba8d03b`
(`docs/acceptance/2026-11-19-mode1-handover-feedback.md`):

> "you have controls" -> "unable, not ready" but Petrovich does take controls
>
> "turn right 2 0" -> "unable, not flying" though controls are written and I cannot control
>
> "I have controls" -> no effect since state says I already have controls, though I don't

So a voice "take" always times out even though `Export.lua` actually goes `active`, and once that
happens belief and the aircraft permanently disagree about who flies, with no recovery.

### Hypothesis

One root cause with two consequences, confirmed in the sortie feedback's own diagnosis and
verified against the real wire path here (`body-layer/src/body.py`'s `_apply_flight_control`,
not just the pure-function tests that had hidden it):

1. **The take ack can never match.** `Export.lua`'s `flight_control.lua` (`cmd == "take"`
   handler) records `fc_pending_take_seq = seq` -- the **wire** message's own `seq` field -- and
   later echoes it back as `fc_take_seq` once the take lands. `belief.flight_control.
   decide_flight_control`'s `TAKING` branch compared that against `FlightControlState.take_seq`,
   a *different*, independently-bumped counter (`take_controls`'s own `take_seq + 1`, decided
   before `_apply_flight_control` has even picked a wire `seq` to send with). The two numbers
   have no relationship to each other, so the `TAKING -> ACTIVE` branch can only ever fire by
   coincidence and `HANDOVER_ACK_TIMEOUT_S` (2 s) always wins: "Unable, not ready."
2. **The ack timeout only changes belief, not the aircraft.** `TAKING -> PILOT` on timeout sent
   no `release` to `Export.lua`, which by then has usually already gone `active` (the take simply
   arrived late) and keeps flying the axes regardless. From then on every `flight_control*` rule
   answers "Unable, not flying" (belief thinks nobody is in `TAKING`/`ACTIVE`), and "I have
   controls" from `PILOT` was a silent no-op (`release_controls` only acted from `TAKING`/
   `ACTIVE`) -- the one recovery phrase Decision 13 says must always act did nothing.

### Evidence

- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua`, `cmd == "take"` handler:
  `fc_pending_take_seq = seq` (the wire seq), and the `taking` branch of `run_flight_control`:
  `fc_take_seq = fc_pending_take_seq`. Confirms `fc_take_seq` is the take message's own wire seq,
  nothing else.
- `body-layer/src/belief/flight_control.py`, `take_controls`: `take_seq=state.take_seq + 1` --
  a local counter with no knowledge of what wire `seq` `_apply_flight_control` will later use.
  `decide_flight_control`'s `TAKING` branch (pre-fix): `state.lua_take_seq == state.take_seq`.
- Wrote a failing test against the *real* wire path (`body-layer/tests/
  test_body_flight_control.py::TestApplyFlightControl::
  test_a_take_transition_sets_take_seq_to_the_actual_sent_wire_seq`) with `take_seq=6` (the local
  counter) and `wire_seq=2` (so the actual send is `seq=3`): before the fix, `flight_control_state.
  take_seq` stayed `6`, never `3` -- reproducing the mismatch the existing pure-function tests
  could not see, since those build `take_seq`/`lua_take_seq` equal by hand.
- Every existing `test_flight_control.py` test for `decide_flight_control`'s `TAKING` branch
  constructs `FlightControlState(take_seq=N, lua_take_seq=N)` directly, confirming the diagnosis's
  own observation that the tests hid the bug by construction.

### Fix Applied

- **(a)** `body.py`'s `_apply_flight_control`, in the branch that actually sends a pending
  `flight_control_transition`: when the transition being sent is `"take"`, `take_seq` is now
  overwritten with the same `next_seq` the message is sent with (`replace(state, wire_seq=next_seq,
  take_seq=next_seq)`), at the one place that knows what seq is really going on the wire.
  `decide_flight_control`'s own comparison (`lua_take_seq == take_seq`) is unchanged -- it now
  compares against the right value by construction instead of by luck. The unpark-take path
  (`decide_flight_control`'s `OVERLAY -> ACTIVE` branch, which *adopts* `state.lua_take_seq`
  wholesale into `take_seq` once Lua confirms) was already correct on its own terms and is
  untouched -- it never compared against a body-layer-side counter in the first place, only ever
  echoed Lua's own number back.
- **(b)** `belief/crew_console.py`'s `CrewConsole.drain_flight_control`: when `decide_flight_
  control` makes the `TAKING -> PILOT` transition (the only transition it makes into `PILOT` from
  `TAKING`, i.e. the ack timeout), `self.flight_control_transition` is now set to `"release"` --
  picked up and sent by `_apply_flight_control` on the very next poll, so Lua is told to stop
  flying the axes whenever belief gives up on a take.
- **(c)** `belief/flight_control.py`'s `release_controls`: now also acts (`acted=True`, phase ->
  `PILOT`) when `state.lua_mode in ("active", "taking")`, even while belief's own `phase` is
  already `PILOT` -- the ack-timeout window (before fix b's own release has reached Lua) or any
  other poll where belief and Lua disagree. `CrewConsole.release_controls`'s existing wrapper
  (`if result.get("acted"): self.flight_control_transition = "release"`) needed no change -- it
  already queues the wire send whenever the pure function reports `acted`. The rule
  (`config/rules/flight.lua`'s `i_have_controls` handler: `if r.acted then say("You have
  controls.")`) already speaks "You have controls." on `acted=True` with no change needed, which
  answers the brief's open question: yes, it speaks, since the player's stick really was being
  ignored.

No new tunables -- `HANDOVER_ACK_TIMEOUT_S` and the rest of the constants in `flight_control.py`
are unchanged. Mode 2 (`ai_pilot_wheel`) code is untouched.

### Verification

- The failing test (`test_a_take_transition_sets_take_seq_to_the_actual_sent_wire_seq`) now
  passes.
- New tests added and passing:
  - `belief/flight_control.py::release_controls` -- `TestReleaseControls.
    test_lua_still_active_while_belief_says_pilot_still_acts`,
    `test_lua_still_taking_while_belief_says_pilot_still_acts`,
    `test_lua_off_while_belief_says_pilot_is_still_a_silent_no_op` (fix c, plus the
    no-regression case).
  - `CrewConsole.drain_flight_control` -- new `TestDrainFlightControlSendsReleaseOnAckTimeout`
    class: ack timeout queues a release; a successful take queues none; an ordinary quiet poll
    queues none (fix b, plus two no-regression cases).
- `body-layer/tests/test_flight_control.py`, `test_body_flight_control.py`,
  `test_rules_flight_actions.py`: 129 passed.
- Full body-layer suite (`pytest tests -q -m "not slow" -p xdist -n auto`): 3667 passed, 4 xfailed
  (pre-existing, unrelated).
- `ruff format --check`: 227 files already formatted. `ruff check`: all checks passed (after
  renaming two unused unpacked `state` locals in the new tests to `_state`).
- `mypy --strict` (run from `body-layer/`): Success, no issues found in 92 source files.
- Mode 2 (`ai_pilot_wheel.py`, `ai_pilot_wheel.lua`) left untouched, per the brief -- a separate
  mode 2 "unable, not flying" defect is being investigated by the main loop.

---

### Debug Report (second bug, same branch)

### Observed Issue

`docs/acceptance/2026-11-19-mode1-handover-feedback.md`, "Common root cause, both modes": the
Windows collector console logged `dropping malformed ai-pilot-wheel line` and `dropping malformed
flight-control line` while telemetry was live, and `GET /ai_pilot_wheel/latest` /
`GET /flight_control/latest` both returned `null`. This is the actual root cause behind both modes'
"unable, not flying" symptoms described above -- the take-ack seq fix above addressed a real but
secondary defect; the lines carrying the fix's own evidence were never reaching body-layer at all.

### Hypothesis

`aircraft-layer/dcs-export/Petrobrain/core.lua`'s `fmt_num_or_null` formats every number with
`%.5f`, with no distinction between a measurement and an integer-typed wire field. For a sequence
counter this produces e.g. `"-1.00000"`, which `json.loads` parses as a Python `float`; every
schema field declared strictly `int` (`fc_take_seq`/`fc_goal_seq`/`fc_last_cmd_seq` in
`src/schema/flight_control.py`, `apw_goal_seq`/`apw_cbtm_seq` in `src/schema/ai_pilot_wheel.py`)
then raises and the collector drops the whole line. `fc_last_cmd_seq` is never `null` (an always-set
`-1` sentinel before any command), so every flight-control line has been dropped since the module
that introduced it (`307d6a81`, 2026-11-18); the AI-wheel line drops only once a goal/combat-trim
command has ever been accepted this session (`apw_goal_seq`/`apw_cbtm_seq` start `nil`/`null`).

### Evidence

- `core.lua:108` (pre-fix): `local function fmt_num_or_null(v) ... return string.format("%.5f", v)
  end` -- no int/float distinction.
- `src/schema/flight_control.py`'s `_optional_int` (`"must be a whole number or null"`) and
  `src/schema/ai_pilot_wheel.py`'s matching checks on `apw_goal_seq`/`apw_cbtm_seq`: both reject
  any `float`, including an integer-valued one like `3.0`.
- Reproduced directly: `AiPilotWheelState.from_dict({'t':1.0,'apw_parked_active':True,
  'apw_goal_seq':3.0}, received_wall_clock_s=0.0)` raises `AiPilotWheelParseError`.
- `grep -n fmt_num_or_null aircraft-layer/dcs-export/Petrobrain/*.lua` -- swept every call site
  against every schema's int-strict fields (`isinstance(..., int)`/`_optional_int`/"whole number"
  across `src/schema/*.py`): only `fc_take_seq`/`fc_goal_seq`/`fc_last_cmd_seq` (`flight_control.
  lua`) and `apw_goal_seq`/`apw_cbtm_seq` (`ai_pilot_wheel.lua`) are both (a) formatted by
  `fmt_num_or_null` and (b) parsed strictly as `int`. `sight.lua`'s `fmt_num_or_null` fields and
  `ai_pilot_wheel.lua`'s `apw_arg852`/`apw_arg952`/`apw_cam_fwd_m` all parse as `float | int`-tolerant
  `_optional_number`, so no defect there. `world_objects.py`'s `category`/`subcategory` (also
  `_optional_int`) are formatted by `telemetry.lua`'s `encode_scalar`, which uses Lua's own
  `tostring` (`%.14g`-equivalent, prints an integer-valued double without a decimal point) --
  unaffected. `mission_start.py`'s strict-int `sequence`/`atmosphere_type` are sent by
  `petrobrain-mission-start-hook.lua` via a real `JSON:encode` library (Hook-state script, not
  `Export.lua`/`core.lua`) -- also unaffected. `line_of_sight.py`'s `_parse_int` fields come from a
  pipe-delimited payload string built by a separate Hook script, never `fmt_num_or_null` -- also
  unaffected.
- Checked `fmt_num_or_null` for the non-finite case too (not previously guarded): `nan`/`inf`/`-inf`
  are not valid JSON tokens, so a non-finite float on any `fmt_num_or_null`-formatted field (e.g. a
  measurement after a DCS API returns something degenerate) would already have produced an
  unparseable line, same failure mode, never previously tested.

### Fix Applied

- `core.lua`: added `is_finite_number(v)` (false for non-number, NaN, or either infinity) and a new
  `fmt_int_or_null(v)` (`"null"` for non-finite, else `%d` on a `math.floor`ed value), exported as
  `_G.fmt_int_or_null` the same way `fmt_num_or_null` already is. `fmt_num_or_null` itself now also
  routes through `is_finite_number`, so a non-finite measurement emits `null` instead of `nan`/`inf`
  text.
- `flight_control.lua`: `fc_take_seq`/`fc_goal_seq`/`fc_last_cmd_seq` now use `fmt_int_or_null`
  instead of `fmt_num_or_null`. Every other `fmt_num_or_null` call in this file (the heading/
  altitude/speed goal and measured fields) is unchanged -- those schema fields are float-tolerant.
- `ai_pilot_wheel.lua`: `apw_goal_seq`/`apw_cbtm_seq` now use `fmt_int_or_null`. `apw_arg852`/
  `apw_arg952`/`apw_cam_fwd_m` are unchanged (float-tolerant schema fields).
- `sight.lua`, `telemetry.lua`, `petrobrain-mission-start-hook.lua`, `petrobrain-line-of-sight-hook.
  lua`: no change -- swept and confirmed unaffected (see Evidence).
- No schema change -- the Python side keeps demanding a real `int` for these fields; the fix is on
  the Lua side that was emitting the wrong wire type, per this project's "code owns truth" posture
  (a schema that silently accepted a float here would hide the next version of this same bug).

### Verification

- New `aircraft-layer/tests/test_core_lua.py`: `fmt_num_or_null`/`fmt_int_or_null` run against a
  real Lua interpreter (`luajit` on this machine; `lua5.1` not installed locally, `_EXEC_TOOLS`
  falls back through `luajit`/`lua5.5`/`lua5.1`/`lua`) -- ordinary values, `nil`, non-number, NaN
  (`0/0`), `+inf`/`-inf` (`math.huge`/`-math.huge`). 14 passed.
- `aircraft-layer/tests/test_flight_control_lua.py`: added `fmt_int_or_null`/`is_finite_number` to
  the extracted `_CORE_HELPERS` set (full-module-execution harness, already in use); new
  `TestSeqFieldsSurviveTheRealSchema` runs the real `push_flight_control_state` (not a hand-built
  JSON string) through the real `schema.flight_control.FlightControlState.from_dict` -- default
  state (`last_cmd_seq == -1`, parses as `int`) and after a real take+goal (`take_seq`/`goal_seq`/
  `last_cmd_seq` all `int`). Updated the pre-existing `fc_last_cmd_seq` wire-format assertions from
  `"47.00000"`/`"48.00000"` to `"47"`/`"48"` (the format changed; the counter value did not). 30
  passed (28 pre-existing + 2 new, all updated assertions green).
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py`: added the same two helpers to
  `_run_push_ai_pilot_wheel_state`'s extraction list; new `TestSeqFieldsSurviveTheRealSchema` runs
  the real `push_ai_pilot_wheel_state` through `schema.ai_pilot_wheel.AiPilotWheelState.from_dict` --
  default (`goal_seq`/`cbtm_seq == 0`) and after setting both nonzero (`3`/`7`), both parsing as
  `int`. 89 passed (87 pre-existing + 2 new).
- A weaker test built from a hand-written `%.5f`-style JSON string was deliberately not used
  anywhere -- every new assertion here parses the real line a real Lua interpreter actually
  produced, which is what would have caught this the first time.
- `luac5.1 -p` on `core.lua`/`flight_control.lua`/`ai_pilot_wheel.lua`: all pass.
- `luac5.1 -l -p` GETGLOBAL sweep on all three touched files: `fmt_int_or_null` reads as a bare
  global in `flight_control.lua`/`ai_pilot_wheel.lua`, same as `fmt_num_or_null` already does
  (intentional cross-module access, `core.lua`'s own header comment); no name collides with a local
  declared in the same file.
- `ruff format`/`ruff check` (`aircraft-layer/src aircraft-layer/tests`): one file reformatted
  (new/edited test assertions' line wrapping), all checks pass after.
- `mypy --strict` (run from `aircraft-layer/`): Success, no issues found in 28 source files.
- Full `pytest aircraft-layer/tests -q`: 997 passed (18 of them new -- 14 in `test_core_lua.py`, 2
  each in `test_flight_control_lua.py`/`test_ai_pilot_wheel_lua.py` -- the other 979 pre-existing,
  no regressions). No skips: a real Lua interpreter (`luajit`) was available on this machine.
- `body-layer/` untouched -- this defect and fix are entirely within `aircraft-layer/`.
