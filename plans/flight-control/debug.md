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

---

### Debug Report (BL-16 sortie 2026-11-20, mode 1)

### Observed Issue

`docs/acceptance/2026-11-20-sortie-feedback.md`, flown on `main` at `98174b54` (after the
handover-ack/wire-format fix above). Two defects, user's own words:

> Mode 1 control handover. Petrovich increased left pedal quite a lot -> left yaw -> bank right to
> compensate -> ends up maintaining heading with right bank (5 deg this time) and unnecessary and
> unwanted left yaw.
> Second control transfer ended up in 10 deg right bank and "unable, not ready" nut still taking
> controls.

Speech log (`body-layer/logs/speech-20261120-010040.jsonl`): take at `now_sim=26.01`, "I have
controls" (release) at `now_sim=56.201`, take at `now_sim=78.223`. Expected (`docs/acceptance/...`,
"Explore" section, now unambiguous): a take adds no pedal of its own, wings level/ball centred
while holding heading; a take never answers "unable, not ready" while Petrovich in fact holds the
controls.

### Defect A — pedal drift at take, and a break's pedal bias never unwinding

**Hypothesis.** Two independent mechanisms in `Petrobrain/flight_control.lua`'s `law_update`
(Step 5, the pedal channel):

1. `d_t_y = K_PEDAL_FROM_COLLECTIVE_RATE * c_dot` fed the pedal from the collective-coupling
   rate `c_dot` unconditionally, even though `FC_AXES_ENABLED.collective = false` means the
   collective axis is never actually written to the aircraft (`write_outputs` skips a disabled
   axis). `u_c`/`c_dot` are an internal-only bookkeeping value in that case, driven by the
   altitude-hold shaper's own tracking error (`a_z_d`), which has no real coupling back from a
   collective that never moves the real aircraft -- so any sustained, never-resolving
   real/internal altitude mismatch (plausible at any ordinary handover) keeps `c_dot` non-zero
   indefinitely, and the pedal **ramps** rather than settling.
2. `K_BREAK_PEDAL_BIAS` was integrated into `t_y` for the duration of a break's rate override and
   never reversed once the break settled (the existing "settling clears it" block cleared
   `rate_override_deg_s`/`break_entry_h_m` but never touched `t_y`), leaving a standing pedal
   offset from any earlier break.

**Evidence.**
- Built the full-module Lua harness by hand (the same technique `test_flight_control_lua.py`
  uses) and ran it against the *unfixed* module: a take with collective disabled, then 20 s of
  `run_flight_control` with the real/measured altitude held a constant 5 m away from the stopping
  height captured at take (a plausible handover transient, nothing else touching the aircraft) --
  `written[2003]` (the pedal command) went from `-0.001` (wobble only) at take to `-0.101` after
  20 s, confirmed still growing, not settling.
- Built a second harness for the break case: a break's rate override held for ~2.5 s saturates the
  pedal at `PEDAL_LIMIT_POSITIVE` (0.2/s bias vs. a 0.5 limit); once the break settles (~9 s, this
  scenario), `t_y` stayed at `0.5` under the unfixed code -- never unwound.
- Both reproduced independently of each other (toggling `measured.collective_enabled`/the break
  goal in isolation).

**Fix Applied** (`Petrobrain/flight_control.lua`):
- `read_measured()` now reports `collective_enabled = FC_AXES_ENABLED.collective` on the
  `measured` table it returns -- the law's five pure functions never read a module-level local
  directly (module docstring), so this is how the config fact reaches `law_update` without
  breaking that contract.
- `law_update`'s pedal step now gates the collective-coupling feedforward on
  `measured.collective_enabled`; `0.0` while disabled, unchanged while enabled (a negative-control
  test confirms the term still works once collective is eventually enabled).
- The break's own pedal bias is now tallied separately (`break_pedal_bias_accum`, reset to `0.0`
  at `law_init_at_take` and at the start of each new break in `law_apply_goal`) as the **actually
  applied** per-frame delta to `t_y` (`next_state.t_y - t_y_before_break_step`), not the nominal
  `break_bias * dt` -- the first version of this fix tracked the nominal amount and overshot the
  unwind badly once the pedal had saturated mid-break (confirmed with the toy-plant harness: a
  15 s break ends at `t_y = 0.5` nominal-accumulated `0.6`+, and subtracting that overshoots to
  `-1.0` instead of returning to the pre-break value). Tracking the actually-applied delta instead
  means subtracting it exactly reverses the break's own contribution, including under saturation,
  as long as nothing else touches `t_y` in between (true here). The "settling clears it" block now
  also unwinds `t_y` by this accumulator and resets it to `0.0`.
- Scoped explicitly in comments: the break-bias unwind undoes *all* `t_y` change since the break
  began, which is exactly correct only while the collective-coupling term is zero (today's
  default) -- a future flight with collective enabled would need Flight M-A's own judgement call
  on how to apportion a saturated, shared clamp between the two terms.

**Verification.**
- New toy-plant tests (`aircraft-layer/tests/test_flight_control_law.py`,
  `TestPedalDoesNotDriftWithCollectiveDisabled`/`TestBreakPedalBiasUnwinds`): both fail on the
  pre-fix code (reproducing `-0.1`/`0.5` respectively) and pass after; a negative-control test
  confirms the gate is keyed on `collective_enabled`, not on the altitude error being absent.
  `_measured()`'s helper gained a `collective_enabled` field (default `True`, so every
  pre-existing collective-channel scenario keeps exercising the feedforward it always implicitly
  assumed).
- `pytest aircraft-layer/tests/test_flight_control_law.py aircraft-layer/tests/test_flight_control_lua.py -q`:
  60 passed (3 new: 2 toy-plant + 1 negative control), no regressions.
- Full `pytest aircraft-layer/tests -q`: 1002 passed.
- `ruff format --check`/`ruff check` (`aircraft-layer/src aircraft-layer/tests`): clean.
- `mypy` (run from `aircraft-layer/`, `src` and the two touched test files): Success.
- `luac5.1 -p` on `flight_control.lua`: passes. GETGLOBAL sweep: every name is a genuine DCS API,
  Lua stdlib, or an already-intentional cross-module helper (`debug_log`/`fmt_*_or_null`/
  `safe_call`/`json_escape_string`/`extract_json_*_field`) -- no new stray global.

### Defect B — a re-take while Lua is already flying never acks

**Hypothesis.** `handle_flight_control_command` bumps `fc_last_cmd_seq = seq` unconditionally,
*before* the `cmd == "take"` branch's own idempotent-no-op check (`if fc_mode == "active" or
fc_mode == "taking" then return end`). So a `take` message that arrives while Lua is already
`"active"`/`"taking"` for any reason — a prior take whose matching `release` never reached or
took effect at Lua (lost send, a reordered or dropped datagram, or simply a belief/aircraft
disagreement about who flies, which is exactly the state yesterday's ack-timeout fix (2026-11-19
report, above) accepts as reachable — "belief can land on `PILOT` with Lua still flying") —
advances `fc_last_cmd_seq` as a side effect but leaves `fc_take_seq`/`fc_pending_take_seq`
pointing at the *original* take. `body.py`'s `_apply_flight_control` sets
`FlightControlState.take_seq` to the wire seq of *this* send (fix (a), 2026-11-19), so
`decide_flight_control`'s ack match (`lua_take_seq == take_seq`) can never succeed for this take —
guaranteed, not merely slow — and after `HANDOVER_ACK_TIMEOUT_S` belief gives up: "Unable, not
ready," while Lua is still genuinely flying mode 1 the whole time. This matches both halves of the
report exactly (the spoken refusal, and Petrovich still holding the controls), and does not
depend on network timing.

I traced the alternative "it's just a slow ack" explanation first and ruled it out: `Export.lua`'s
own capture (`resolve_capture_values`) resolves within one physics frame whenever either seat
reads live (via `update_live_seat_tracking`, which runs every frame regardless of mode) or falls
back to the last-steady/magnitude-compare paths, none of which can block for anywhere near 2 s —
confirmed by reading every branch of `resolve_capture_values`, which returns a value immediately
in every reachable case (a `nil` capture only follows a genuine `NaN`/failed DCS read, not a
timing race). Given the 22 s gap between this sortie's release (`t=56.2`) and the second take
(`t=78.2`), a UDP-reordering race between those two specific messages (the only other candidate,
and the one `_apply_flight_control`'s own docstring already defends against for same-poll
sends) is not plausible either. What *is* plausible without further data (no
`--belief-truth-log` was captured for this sortie) is that the first release's own send failed or
was dropped somewhere between body-layer and `Export.lua` (every write on this channel is
best-effort/log-and-continue, consistent with every other command channel in this codebase, and
not itself a defect to retry) — but regardless of *why* Lua was still flying, the sequence-echo
bug above is what turns that into a permanent, unrecoverable belief/aircraft disagreement rather
than a one-poll hiccup, and is what I fixed.

**Evidence.** Reproduced directly against the real Lua interpreter (full-module harness): `take`
(`seq=1`) → `active`, `fc_take_seq=1`, `fc_last_cmd_seq=1`. A second `take` (`seq=2`) sent while
still `active`: under the unfixed code, `fc_last_cmd_seq` advances to `2` but `fc_take_seq` stays
`1` — the exact, permanent mismatch `decide_flight_control`'s `TAKING` branch can never clear.

**Fix Applied** (`Petrobrain/flight_control.lua`, `handle_flight_control_command`'s `cmd ==
"take"` branch): a repeat take remains a no-op for the aircraft (no re-capture, no `fc_law`
reset — Petrovich keeps flying exactly as before), but now re-syncs the take bookkeeping to the
new message's own seq: `fc_take_seq = seq` while already `"active"` (nothing else will ever set
it again for this session), `fc_pending_take_seq = seq` while still `"taking"` (so the forthcoming
`"taking" -> "active"` transition in `run_flight_control` reports the *new* seq, the one belief is
actually waiting on, not the stale original). No change to body-layer — `FlightControlState.
take_seq`/`decide_flight_control`'s comparison were already correct; the defect was entirely in
what Lua echoed back.

**Verification.**
- New tests (`aircraft-layer/tests/test_flight_control_lua.py`,
  `TestRepeatedTakeWhileAlreadyFlyingStillAcks`): a repeat take while `"active"` and one while
  still `"taking"` each fail on the pre-fix code (`fc_take_seq` stuck at `1` where `2` is expected)
  and pass after.
- `pytest aircraft-layer/tests/test_flight_control_lua.py -q`: 32 passed (2 new), no regressions.
- Full `pytest aircraft-layer/tests -q`: 1002 passed.
- `ruff format --check`/`ruff check`, `mypy` (from `aircraft-layer/`), `luac5.1 -p`, and the
  GETGLOBAL sweep: all clean, same results reported under Defect A above (one combined pass over
  both fixes, same files).
- `body-layer/` untouched — this defect's fix is entirely within `Export.lua`'s own
  `flight_control.lua` module; body-layer's sequencing was already correct.
