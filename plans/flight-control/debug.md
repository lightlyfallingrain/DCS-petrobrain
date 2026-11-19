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

### Debug Report (third bug, mode 2 -- heading goal stuck after a break)

### Observed Issue

2026-11-20 sortie, mode 2 (AI-pilot wheel overlay), flown on `main` at `98174b54`
(`docs/acceptance/2026-11-20-sortie-feedback.md`):

> Mode 2: break left -> ok > break right -> ok > turn heading 060 -> acknowledged, but nothing
> happens. Not in CPG. No flicker.

A later live sample (`GET /ai_pilot_wheel/latest`, after the user also manually switched the
overlay to FLT and spoke "turn left 15") showed `"apw_cbtm_status": "done"`, `"apw_cbtm_seq": 2`
(both breaks completed cleanly) and `"apw_goal_progress": "idle"`, `"apw_goal_seq": 0` -- Lua had
never received a single `ai_pilot_goal` message with a heading this whole mission, in either
overlay mode. "No flicker" (no `AI_WHEEL_LEFT` mode-cycle tap at all) was the tell: `Export.lua`'s
own `ai_pilot_goal_tick` never even starts trying, which only happens while `ai_pilot_goal.param`
is still `nil` -- i.e. body-layer never sent a heading goal, on either channel's own sequence
space. This ruled out every Lua-side hypothesis (mode-cycle bound, CPG-view hold, a stuck
`ai_pilot_cbtm.action`, a stuck `hvrt_direction`) and a cross-channel `goal_seq`/`cbtm_seq`
dedupe collision (`Export.lua`'s `handle_ai_pilot_goal_command` checks each sequence space only
against itself, confirmed by reading it in full) -- the defect is entirely upstream, in
body-layer's own pure decision function, before anything is ever written to the wire.

### Hypothesis

`belief/ai_pilot_wheel.py`'s `decide_ai_pilot_wheel` ("F-P7 -- a break always wins") drops a
`heading` goal whenever `state.cbtm_action_sent` names a break. `cbtm_action_sent` is set once,
by `body._apply_ai_pilot_wheel_goal`, when a break is spoken, and is **never cleared** except on
unpark (`body.py`'s own unparked branch). So F-P7 fired on *every* poll for the rest of the
activation, not only while the break's press was actually open -- any heading goal spoken any
time after any break, for the rest of that parked activation, was silently stripped from `goal`
before `decide_ai_pilot_wheel`'s own promotion step (the one place that bumps `goal_seq`) ever
saw it. `goal_seq` therefore never moved, `body.py`'s "send on `goal_seq` change" guard
(`final_goal.goal_seq != runner.ai_pilot_goal_last_sent_seq`) never fired, and no
`POST /command/ai_pilot_goal` carrying a heading was ever sent -- matching `apw_goal_seq: 0`
exactly. The function's own docstring even predicted the opposite of what actually happens: "This
runs on every poll `cbtm_action_sent` names a break, not only the one it was first sent on --
harmless once there is nothing left to drop or clear" -- false the moment a *new* heading goal
arrives after the break, which a break-then-level-off-then-new-heading flight profile does on
every sortie.

### Evidence

- Read `ai_pilot_wheel.py`'s `decide_ai_pilot_wheel` (old F-P7 block, then at line ~1037) and
  `request_goal`: a brand-new goal (no prior target) is only *queued* into `pending_order`,
  `goal_seq` is **not** bumped there -- it is bumped only by the promotion step at
  `goal.active_param is None` -> `pending_order` pop (line ~1113-1120) or by the slice-timer
  rotation. F-P7 ran *before* that promotion step and removed `"heading"` from `pending_order`
  outright, so the promotion/seq-bump code path was never reached for a heading goal spoken after
  a break.
- Read `body.py`'s `_apply_ai_pilot_wheel_goal`: `cbtm_action_sent` is carried through unchanged
  (`cbtm_action_sent=(cbtm_transition if cbtm_transition is not None else
  runner.parked_flight_state.cbtm_action_sent)`) and cleared only in the `not parked_active`
  branch -- confirmed by grep (`cbtm_action_sent` appears nowhere else as a write target in
  `body-layer/src/`).
- Read `Export.lua`'s `handle_ai_pilot_goal_command` in full: `goal_seq` is compared only against
  its own prior value (for `hvrt_step`'s one-shot dedup) and `cbtm_seq` only against its own --
  no shared/cross-channel sequence check exists on the Lua side. Ruled out the coordinator's
  "shared counter" hypothesis directly from the code, before building anything for it.
- Reproduced with a unit test against `decide_ai_pilot_wheel` directly
  (`body-layer/tests/test_ai_pilot_wheel.py::TestDecideAiPilotWheelCbtm::
  test_a_heading_goal_after_the_break_has_finished_is_not_dropped`): a queued heading goal with
  `cbtm_action_sent="break_right"`, `lua_cbtm_status="done"` (the break has already finished) is
  silently dropped on the old code (`heading_target_deg` ends `None`, `goal_seq` stays `0`) and
  correctly promoted on the fixed code (`heading_target_deg == 60.0`, `active_param == "heading"`,
  `goal_seq == 1`). Confirmed failing on the pre-fix function by temporarily stashing the source
  change only and re-running that one test (`AssertionError: assert None == 60.0`), then restoring
  the fix.

### Fix Applied

`body-layer/src/belief/ai_pilot_wheel.py`, `decide_ai_pilot_wheel`'s F-P7 block: added
`and state.lua_cbtm_status != "done"` to the break-wins condition (was: `state.cbtm_action_sent
in ("break_left", "break_right", "break_away")` alone). `lua_cbtm_status` is already a read-only
mirror of `Export.lua`'s own `apw_cbtm_status` (`"idle"`/`"running"`/`"done"`) -- no new field, no
wire change. `!= "done"` rather than `== "running"` deliberately also covers the one poll a break
is freshly sent on: `_apply_ai_pilot_wheel_goal` sets `cbtm_action_sent` and calls `decide_ai_
pilot_wheel` in the same poll, before the just-sent command has reached `Export.lua`, so `lua_
cbtm_status` that poll is still whatever it mirrored *before* this break (`None` the first break
this activation) -- `== "running"` would have missed that same-poll drop and broken the existing
`test_body_ai_pilot_wheel.py::TestCbtmTransitions::
test_break_left_is_recorded_and_ends_an_outstanding_alignment` (confirmed: it failed with that
narrower condition, passes with `!= "done"`). `cbtm_action_sent` itself is left untouched (still
carried through to unpark, still read by the mode-1 unpark-take's `cbtm_break_target_heading_deg`
seed) -- only the F-P7 drop's own duration is bounded, which is the minimal change the confirmed
root cause needs. Docstring updated to describe the real condition and name the bug.

Two existing unit tests (`test_a_break_drops_the_active_heading_goal_and_clears_align_phase`,
`test_a_break_drops_a_queued_heading_goal`) were updated to set `lua_cbtm_status="running"`,
since they exercise the "break in progress" case the old unconditional code never distinguished
from "break long done." Two new tests added: the "done -> not dropped" regression above, and
`test_a_freshly_sent_break_drops_heading_before_lua_has_echoed` (the same-poll case with `lua_
cbtm_status=None`, the condition the narrower `== "running"` fix would have broken).

**On the coordinator's shared-counter/reset-signal line of investigation**: stopped and did not
build it. The root cause confirmed above is not a seq/dedupe collision between channels -- `Export.
lua` never cross-checks `goal_seq` against `cbtm_seq` (read in full, see Evidence), and the live
sample's `apw_goal_seq: 0` is fully explained by body-layer never sending the message at all, not
by Lua rejecting or deduping one it received. No `flight_control.lua`/`flight_control.py` lines
were touched, and no mission-restart/reset mechanism was built, per the instruction to stop and
report rather than build a shared counter if the root cause turned out to be something else.

### Verification

- `body-layer/tests/test_ai_pilot_wheel.py` + `test_body_ai_pilot_wheel.py`: 124 passed (4 new/
  changed in the first file; the previously-failing `TestCbtmTransitions::
  test_break_left_is_recorded_and_ends_an_outstanding_alignment` in the second file now passes).
- `ruff format --check body-layer/src body-layer/tests`: 227 files already formatted.
- `ruff check body-layer/src body-layer/tests`: all checks pass.
- `cd body-layer && .venv/bin/mypy src`: Success, no issues found in 92 source files.
- Full `pytest body-layer -q` (no filter), two runs: the first, against the overly-narrow
  `== "running"` condition, surfaced the one regression above
  (`TestCbtmTransitions::test_break_left_is_recorded_and_ends_an_outstanding_alignment`, 1 failed,
  3696 passed, 4 xfailed) -- exactly how it was caught. After correcting to `!= "done"`, a second
  full run is clean: **3698 passed, 4 xfailed, 0 failed** (289.55s).
- No Lua files touched by this fix -- `luac5.1 -p`/GETGLOBAL checks not applicable.
- `aircraft-layer/` untouched -- this defect and fix are entirely within `body-layer/`.
