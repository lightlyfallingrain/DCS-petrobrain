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

### Rework, 2026-11-20 -- "latest wins" during a still-running break

**The fix above still violated the user's own rule.** `!= "done"` bounded the drop to the break's
own running window, but a heading commanded *during* a still-open break was still dropped --
exactly what the user ruled out, verbatim, on being told that: *"Why? If player commands anything
during a break, act on it. Latest player command always wins."* (`docs/acceptance/
2026-11-20-sortie-feedback.md`, "Mode 2 root cause and the 'latest wins' direction"). Reconciled
with F-P7's original answer (2026-11-18, "a break supersedes any **outstanding** heading goal, i.e.
one set before it"): a heading commanded *before* the break stays superseded; one commanded *during
or after* it is flown at once, ending whatever remains of the break on the Lua side.

**Root cause of the status-gated version's own failure**: `Export.lua`'s own
`lua_cbtm_status`/running-done readback times *when the break's press happened to release*, not
*when the player spoke relative to it* -- the two coincide only when nothing is commanded until
after the break finishes, which is precisely the case the direction above rules out. Fixing this by
tightening the status window further (e.g. some other Lua-reported sub-state) would still be timing
against the wrong clock; the right clock is command order.

**Fix applied, body-layer (`body-layer/src/belief/ai_pilot_wheel.py`, `body-layer/src/body.py`)**:
replaced the `lua_cbtm_status != "done"` gate with a body-side command-order comparison.

- `ParkedFlightState` gains `command_order_seq: int` (a monotonic counter) and `cbtm_action_order:
  int | None` (the order stamp taken when `cbtm_action_sent` was last set to a break kind).
  `AiPilotWheelGoal` gains `heading_requested_order: int | None`, stamped by `set_parked_heading`
  (now taking an explicit `order: int` parameter) on every call -- the only path that ever writes
  `heading_target_deg`.
- `body._apply_ai_pilot_wheel_goal` holds a local `order_seq` (read from `state.command_order_seq`),
  bumped once per heading request (`level_flight`'s own heading freeze, or an ordinary
  `turn_heading`/goal-transition heading request) or break send, in the order this function
  processes them each poll, and writes the final value back at the end. `advance_parked_flight_
  state` carries both new fields through unchanged each poll (same posture as every other
  later-stage field) -- missing this would have silently reset them to their defaults every poll,
  since that function reconstructs `ParkedFlightState` from scratch rather than `replace()`-ing it.
- `decide_ai_pilot_wheel`'s F-P7 block: align-phase clearing (Q1, "no restore after a break") is now
  unconditional on `cbtm_action_sent in CBTM_BREAK_ACTIONS` alone -- it never actually depended on
  heading ordering (a fresh `cbtm_apply_align`/`_align_for_launch` call always overwrites `cbtm_
  action_sent` away from a break name in the same poll it runs, so `align_phase` can never be
  non-`"none"` while `cbtm_action_sent` still names a stale break). The heading drop itself now
  fires only when `goal.heading_requested_order` is `None` (never requested this activation, the
  conservative default) or strictly less than `state.cbtm_action_order` -- "requested before this
  break," not "while Lua still reports it running."
- `CBTM_BREAK_ACTIONS` is the new module-level constant (`("break_left", "break_right",
  "break_away")`) both call sites share, replacing the inline tuple literal.

**Fix applied, aircraft-layer (`aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`,
`handle_ai_pilot_goal_command`)**: the body-side fix alone is not sufficient -- `ai_pilot_goal_tick`/
`ai_pilot_goal_tick_hvrt` both pause (no-op) while `ai_pilot_cbtm.action ~= nil`, so a goal message
sent while a break's own CBTM episode is still open would sit acknowledged and never pressed, the
same symptom moved one layer down. Added an `elseif` branch beside the existing "a new `cbtm_action`
message starts a fresh run" check: when a goal message (`param ~= nil`) arrives and does **not**
itself start a new CBTM run, and `ai_pilot_cbtm.action ~= nil`, it releases any open timed press
(the same release the existing `cbtm_action`-starting branch already performs) and calls
`ai_pilot_cbtm_finish()` -- the same "this run is over" reset a break that ran to completion
already uses, so `apw_cbtm_status` reports `"done"`. No new wire field or status value: body-layer's
own F-P7 no longer reads `lua_cbtm_status` to decide anything (command order alone decides it now),
so inventing a distinct "superseded" status would have no reader.

**Evidence**:
- Read `ai_pilot_goal_tick`/`ai_pilot_goal_tick_hvrt` in full: both pause unconditionally while
  `ai_pilot_cbtm.action ~= nil`, confirming the Lua-side fix is necessary even once body-layer stops
  dropping the goal.
- `luac5.1 -l -p` GETGLOBAL check before/after the Lua edit: identical global list (`diff` empty) --
  no new unresolved global introduced.
- Reproduced both directions against `decide_ai_pilot_wheel` directly
  (`test_ai_pilot_wheel.py::TestDecideAiPilotWheelCbtm::
  test_a_heading_goal_commanded_during_a_still_running_break_is_not_dropped`,
  `test_a_break_drops_a_heading_requested_before_it_and_clears_align_phase`) and end to end through
  `_apply_ai_pilot_wheel_goal` (`test_body_ai_pilot_wheel.py::
  TestLatestCommandAlwaysWinsAgainstABreak`, both directions). Confirmed each test fails for the
  stated reason on the pre-rework code (temporarily reverted `heading_predates_break`'s computation
  to a bare `True` for the body-side cases, and removed the Lua `elseif` branch for the Lua cases;
  both restored byte-for-byte afterward, verified by `shasum` before/after).
- Reproduced the Lua-side fix with a real Lua interpreter (`lua5.5`, no `lua5.1` on this machine --
  `luac5.1`, the syntax/bytecode checker, is a separate binary and was available):
  `aircraft-layer/tests/test_ai_pilot_wheel_lua.py::TestHandleAiPilotGoalCommand::
  test_a_goal_arriving_mid_break_ends_the_cbtm_episode_and_the_tick_then_runs` (the open press
  releases, the episode finishes, and a tick run immediately afterward opens a fresh heading hold --
  proving the pause actually lifted, not just that the fields changed) and `test_a_goal_arriving_
  mid_break_away_cancels_the_pending_second_press` (the gap-until-second-press state clears with no
  press to release).

**Verification**:
- `body-layer/tests/test_ai_pilot_wheel.py` + `test_body_ai_pilot_wheel.py`: 128 passed (two
  existing `TestDecideAiPilotWheelCbtm` tests renamed and given explicit order fields; one test
  retired as redundant with the order-based design and replaced by two new ones covering "never
  requested this activation" and "align clears with no heading outstanding"; two new end-to-end
  tests in a new `TestLatestCommandAlwaysWinsAgainstABreak` class in `test_body_ai_pilot_wheel.py`;
  one new `TestSetParkedHeading` test for the `order` stamp itself).
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py`: 91 passed (two new tests in
  `TestHandleAiPilotGoalCommand`; `ai_pilot_cbtm_finish` added to `_run_goal_integration`'s extracted
  function list, since `handle_ai_pilot_goal_command` now calls it directly).
- `ruff format --check`/`ruff check` body-layer `src`/`tests`: clean. `cd body-layer &&
  .venv/bin/mypy src`: Success, no issues found in 92 source files.
- `ruff format --check`/`ruff check` aircraft-layer `src`/`tests`: clean. `cd aircraft-layer &&
  .venv/bin/mypy src`: Success, no issues found in 28 source files (test files are not
  `mypy --strict`-checked in this subproject, per its own `CLAUDE.md` "Commands").
- `luac5.1 -p` on `ai_pilot_wheel.lua` and `Export.lua`: both pass.
- Full-suite runs deferred to Reviewer/DoD per this project's "fast set while working, full suite
  once at DoD" policy (root `CLAUDE.md`, "Verification") -- not re-run a third time here.

### Debug Report (BL-16 sortie 2026-11-20 -- "Desired value must be exact; flying may be imprecise")

### Observed Issue

`docs/acceptance/2026-11-20-sortie-feedback.md`, last section, user's own words:

> desired values: I've said that a certain band is acceptable, holding a value need not be exact.
> However, the value *set* as desired must still be what player commanded. Actual flight is then
> allowed to deviate from it a bit, but the desired value must be correct.
>
> Now oberver "altitude 100 radar" -> alt set to 116 R. should set to 100. This was mode 2, but
> just as well the desired value must be correctly set in mode 1. Flying itself is allowed to be a
> bit imprecice.

Expected: the overlay's own *set* value (mode 2) or the stored goal (mode 1) lands on exactly what
was commanded (or the nearest value the wheel can represent, if coarser); only the *flown* value
may lag behind it.

### Hypothesis

Mode 2's goal convergence and mode 1's goal storage are two different mechanisms, so each needed
its own check:

- **Mode 2** (`aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`): `ai_pilot_goal_tick_
  altitude`/`ai_pilot_goal_tick_heading` stop pressing the AI-pilot-wheel hold the instant the
  overlay's own readback (`alt_text`/`course_text`) is within `AI_PILOT_ALT_TOLERANCE_M` (20 m) /
  `AI_PILOT_HEADING_TOLERANCE_DEG` (5°) of the commanded target -- the same band the user had
  described as acceptable for *holding* a value once flown, reused as the stop condition for
  *setting* it. "Altitude 100 radar" landing at 116 (16 m error, inside the 20 m band) is exactly
  this: the goal tick saw "close enough" and released the hold with the overlay still 16 m wrong.
- **Mode 1** (`aircraft-layer/dcs-export/Petrobrain/flight_control.lua`,
  `body-layer/src/belief/flight_control.py`): no equivalent mechanism was known to exist --
  `law_apply_goal` stores `goal.heading_deg`/`goal.alt_m`/`goal.ias_kmh` directly with no
  tolerance check at all, so the working hypothesis was "mode 1 has no bug here," to be confirmed
  by reading the whole path rather than assumed.

### Evidence

- Read `ai_pilot_wheel.lua`'s `ai_pilot_correction_direction`/`ai_pilot_goal_heading_direction`
  (the two pure "which way to press, or stop" decisions): both return `nil` (stop) once
  `|held - target| <= tolerance`, and the altitude goal tick (`ai_pilot_goal_tick_altitude`, line
  ~936 pre-fix) called the former with no override, so it shared the takeover-correction loop's
  20 m band. The heading goal tick (`ai_pilot_goal_tick_heading`) has always had its own 5°
  constant with no other caller, confirming it is purely a goal-exactness setting, not a shared
  flown-value one.
- `aircraft-layer/research/2026-11-14-mi24p-ai-pilot-wheel-layout.md` section 5 (the pilot's own
  operating-model writeup): FLT/HVR altitude and heading are changed **only** by a long hold
  ("altitude climbs/descends while held; release at target", "heading CCW/CW while held") -- no
  short-tap option exists for either in FLT/HVR (only HVRT's own `+2m`/`-2m` inner buttons do, a
  different mode). So "finish with short taps" (the user's own suggested anti-oscillation
  strategy) is not an available lever here; the only lever is when the existing hold-and-poll
  releases.
- `aircraft-layer/research/2026-10-31-mi24p-park-controls-ai-pilot.md` ("Nudge step sizes"):
  `$S/HelperAI/HelperAI.lua`'s own constants (`course_change_low_speed = 10`,
  `alt_change_low_speed = 15`, ramping to `course_change_high_speed = 40`/`alt_change_high_speed =
  50` only after holding past `course_alt_change_transition_time = 2` seconds). At the 5 Hz poll
  rate (`EXPORT_INTERVAL_S = 0.2 s`, `Export.lua`) this bounds one poll's worth of movement during
  an ordinary (sub-2 s) correction to roughly 2-3 units -- a tight stop tolerance will only ever
  overshoot by about that much, and the goal tick's own existing "switch direction immediately
  without waiting for a release" behaviour (already in `ai_pilot_goal_tick_heading`'s/`_altitude`'s
  code, confirmed by reading it) self-corrects any overshoot on the very next tick. Units
  (deg/s vs m/s) are the research note's own unverified guess, flagged there as "measure before
  relying on it" -- not re-verified live here, but the bound holds regardless of the exact units
  since it only needs "small relative to a tight tolerance," which 2-3 vs. a target band of
  0.5 satisfies either way.
- Every overlay altitude/heading reading in both research notes' screenshots (`196 R`, `948 B`,
  `71`, `60`, `150`) is a bare integer, no decimal point -- the basis for treating "exact" as
  "equal to the nearest whole unit" (tolerance 0.5) rather than true floating-point equality.
  **Not independently re-verified live** for this fix -- flagged in the new constants' own
  comments, since no screenshot was taken specifically looking for a fractional reading.
- Read mode 1 end to end for the same question: `body-layer/src/belief/crew_console.py`'s
  `axes_set_heading`/`axes_set_altitude`/`axes_set_speed`/`axes_step_altitude`/`axes_step_speed`
  pass the commanded value through `clamp_altitude`/`clamp_speed` only (the documented AGL floor
  and the documented IAS ceiling/floor -- no rounding, no band-snapping) before building
  `FlightControlGoalRequest`; `flight_control.lua`'s `apply_goal_fields` parses the wire JSON with
  `extract_json_number_field` (exact `tonumber`, no rounding) straight into `fc_goal_heading_deg`/
  `fc_goal_alt_m`/`fc_goal_ias_kmh` and into `law_apply_goal`, which assigns `next_state.heading_
  goal_deg = goal.heading_deg` / `next_state.alt_goal_m = goal.alt_m` / `next_state.speed_goal_mps
  = goal.ias_kmh / 3.6` verbatim (the last is an exact unit conversion, not a rounding); the wire
  echo (`fc_goal_heading`/`fc_goal_altitude`/`fc_goal_speed`) reads the same locals straight back.
  `round(clamped)` appears once, in `axes_set_altitude`/`axes_step_altitude`'s own **returned**
  dict (the spoken-readback value), never in the `FlightControlGoalRequest` sent on the wire. No
  deviation found anywhere in this path -- hypothesis confirmed as "no bug."

### Fix Applied

**Mode 2 only** (`aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`):

- `ai_pilot_correction_direction(held_m, target_m, tolerance_m)` gained a third, optional
  parameter (defaults to `AI_PILOT_ALT_TOLERANCE_M` when omitted, so every takeover-correction call
  site -- `ai_pilot_begin_hold_phase`'s two directions, `ai_pilot_decide_correction`, `ai_pilot_
  check_hold_convergence`, the quick-path second-pulse re-check -- is unchanged and keeps the 20 m
  "flown value matches the handover snapshot" band).
- A new constant, `AI_PILOT_GOAL_ALT_EXACT_TOLERANCE_M = 0.5`, is passed explicitly at the one
  call site that is the altitude **goal**'s own stop condition (`ai_pilot_goal_tick_altitude`).
- `AI_PILOT_HEADING_TOLERANCE_DEG` (the heading goal's only caller) is tightened in place from
  `5.0` to `0.5` -- no parameterization needed since, unlike altitude, heading has no second,
  wider-banded caller to preserve.
- Both new/changed constants are declared with no `tuning.py` equivalent (aircraft-layer has no
  tuning-loader mechanism; root `CLAUDE.md`, "Outside body-layer the loader does not exist") and
  documented as such.

**Mode 1**: no code change. Confirmed exact end to end (see Evidence); the user's rule was already
satisfied there.

**Body-layer** (`body-layer/src/belief/ai_pilot_wheel.py`): `AI_PILOT_ALTITUDE_TOLERANCE_M`'s and
`AI_PILOT_HEADING_TOLERANCE_DEG`'s docstrings corrected -- both are declared tunables with **no
code consumer anywhere in `body-layer/src/`** (confirmed by grep before editing), so their default
values (20.0/5.0) are unchanged, but the docstrings previously claimed (heading) or implied
(altitude) that Stage P2's goal tick would use them; that was never wired up, and is now actively
false for altitude (the goal tick uses its own, different, Lua-only constant) and stale for
heading (the Lua side's own identically-named constant just changed value while this one did not).
Regenerated `body-layer/config/defaults.toml` via `tools/generate_defaults.py --write` since the
rendered first-sentence description changed for both keys.

### Verification

- New/changed tests in `aircraft-layer/tests/test_ai_pilot_wheel_lua.py`:
  - `TestAiPilotCorrectionDirection.test_explicit_tolerance_overrides_the_default_band` -- the new
    third parameter.
  - `TestAiPilotGoalHeadingDirection`: `test_within_tolerance_needs_no_correction` tightened to
    0.3°; new `test_outside_the_tightened_tolerance_still_corrects` covers the old 5° band's own
    2° example, which now must still correct.
  - `TestAiPilotGoalTick.test_heading_goal_holds_then_settles`: extended with a 1°-short reading
    (89 vs. target 90) that must keep pressing before the exact 90 settles -- fails on the
    pre-fix 5° band (would have settled at 89), passes after.
  - `TestAiPilotGoalTick.test_altitude_goal_does_not_settle_short_of_the_exact_target` (new) --
    reproduces the exact sortie numbers (150 -> 116 -> 100 against a target of 100): fails on the
    pre-fix code (116 settles, 16 m inside the old 20 m band) and passes after. Verified the failure
    is the stated one by running it against the pre-fix source before applying the Lua change.
  - Both new constants added to the three `_*_CONSTANTS` extraction tuples the harness uses
    (`_AI_PILOT_WHEEL_CONSTANTS`/`_AI_PILOT_WHEEL_INTEGRATION_CONSTANTS`/`_GOAL_INTEGRATION_
    CONSTANTS`) -- missing this is a silent-fallback-to-default-tolerance failure mode, caught by
    first running the new altitude regression test before adding
    `AI_PILOT_GOAL_ALT_EXACT_TOLERANCE_M` to `_GOAL_INTEGRATION_CONSTANTS` and observing it fail
    for exactly that reason (`hold_cmd_116` read `nil`, i.e. the 20 m default had silently applied).
- `pytest aircraft-layer/tests/test_ai_pilot_wheel_lua.py -q`: 94 passed (was 91; +3 new tests,
  2 existing tests' fixture values changed to match the tightened bands).
- `pytest aircraft-layer/tests -q` (full subproject suite): 1007 passed, no regressions.
- `ruff format --check`/`ruff check` (`aircraft-layer/src aircraft-layer/tests`): clean.
- `cd aircraft-layer && .venv/bin/mypy src`: Success, no issues found in 28 source files.
- `luac5.1 -p` on `ai_pilot_wheel.lua`: passes. GETGLOBAL sweep: unchanged from before this fix
  (`client`, `debug_log`, `extract_json_number_field`, `extract_json_string_field`,
  `fmt_int_or_null`, `fmt_num_or_null`, `GetDevice`, `json_escape_string`, four `LoGet*` DCS APIs,
  `safe_call`, Lua stdlib (`math`/`string`/`tonumber`/`tostring`/`type`), `WHEEL_CENTER_BUTTON`,
  `WHEEL_MENU_BUTTON`) -- no new stray global; both new locals (`AI_PILOT_GOAL_ALT_EXACT_
  TOLERANCE_M`, and the tightened `AI_PILOT_HEADING_TOLERANCE_DEG`) are declared before use.
- `pytest body-layer/tests/test_ai_pilot_wheel.py body-layer/tests/test_body_ai_pilot_wheel.py
  body-layer/tests/test_crew_console_ai_pilot_wheel.py body-layer/tests/test_flight_control.py
  body-layer/tests/test_body_flight_control.py -q`: 194 passed.
- `pytest body-layer/tests/test_tuning_defaults_toml.py -q`: 1 passed (the regenerated
  `defaults.toml` matches the declarations).
- `ruff format --check`/`ruff check` (`body-layer/src body-layer/tests`): clean.
- `cd body-layer && .venv/bin/mypy src`: Success, no issues found in 92 source files.
- Full `pytest body-layer/tests -q` (no `-x`, after fixing the issue below): 3702 passed,
  4 xfailed, no regressions.
- The first full-suite run caught a real omission: `tests/test_tuning_comment_renders.py`
  (`X-T26`'s guard against a cross-key constraint stated after a `#:` block's first sentence,
  which the generator never renders) failed because `AI_PILOT_HEADING_TOLERANCE_DEG`'s docstring
  named `AI_PILOT_ALTITUDE_TOLERANCE_M` only in its second sentence. Not a real coupling between
  the two tunables (neither constrains the other's value) -- reworded to drop the cross-reference
  by name rather than add it to the first sentence; `test_tuning_comment_renders.py` and
  `test_tuning_defaults_toml.py` pass after. This is the exact trap root `CLAUDE.md`'s own
  "Behaviour-affecting constants are tunable" section warns about, caught mechanically rather than
  by a reader.

### Debug Report (BL-16 sortie 2026-11-20, mode 2 → mode 1 handover crash)

### Observed Issue

Flown on `main` @ `a8b21de0` (collective still disabled, `FC_AXES_ENABLED.collective = false`).
User, verbatim (`docs/acceptance/2026-11-20-sortie-feedback.md`):

> In mode 2 I commanded from speed 0 to 200, AI accelerated.
> I changed to mode 1 -> controls fixed at what they were, no corrective movement -> crash as bank
> kept increasing.
> On change to mode 1, mode 1 must keep flying the set targets from mode 2 (heading, speed, alt).

The speech log (`body-layer/logs/speech-20261120-015236.jsonl`) shows the run ending right after a
`"break away"` (`cbtm_break_away`, `now_sim=910.694`) followed ~11 sim seconds later by `"speed two
zero zero"` (`now_sim=921.663`) -- the log then stops, no further utterance recognised, consistent
with a crash shortly after. No `"i_have_controls"`/`"you_have_controls"` entry appears after that
point: the handover was the physical **unpark** (`ap_parked` falling edge via DCS's own Request
Control key), not a voice take -- so this is squarely `run_flight_control`'s unpark-take branch,
not the voice-take path.

### Hypothesis

`law_init_at_take`'s heading-vs-turn-mode pick (Decision 1 REVISED/24: `|bank| < takeover_level_
bank_deg` -> heading mode, else turn mode holding `measured.r_deg_s`) is the right call for a
**voice** take, where a bank past the threshold really does mean the pilot just rolled into one on
the raw stick. It is the wrong call for an **unpark** take: the player broke away (`cbtm_break_
away`), was almost certainly still banked/turning from that break when they commanded speed and
then unparked, and the captured bank/rate at that instant is a transient left over from mode 2's
own manoeuvre, not a deliberate "hold this turn" from the player taking raw controls. `law_init_at_
take` had no way to tell the two cases apart, and once in turn mode, nothing in `law_update` ever
drives `turn_goal_deg_s` back toward zero on its own -- the aircraft holds (and, as the mode-2 speed
command's effect on true airspeed continued, the kinematic bank `phi_kinematic = atan(V_t*r/g)`
that same held rate needs grows with it) a sustained, uncommanded turn with nothing the pilot did
visibly correcting it: "controls fixed, no corrective movement" from the cockpit, "bank kept
increasing" as speed under momentum/trim kept climbing into that formula. Mode 2's own standing AI-
wheel targets (the dial the AI was actually flying to/from) were available the whole time and were
simply never consulted.

### Evidence

- Read `plans/flight-control/plan.md` Decision 24 ("Petrovich has the controls is one state across
  park and unpark... `law_init_at_take`'s own 'At take' section") and confirmed `law_init_at_take`
  (`aircraft-layer/dcs-export/Petrobrain/flight_control.lua`) seeds every goal from `measured`/
  `command` alone -- no seam exists for mode 2's own set state at all, for either take origin.
- Read `body-layer/src/belief/flight_control.py`'s `decide_flight_control`: body-layer only mirrors
  Lua's own outcome on an unpark (silent `OVERLAY` -> `ACTIVE` once Lua reports `active`/`unpark`) --
  it never sends a seed, confirming Decision 23's "no LAN message ever carries a raw axis value" (or
  any axis-adjacent value) extends in practice to this handover too; any fix has to live in Lua,
  reading mode 2's own state locally.
- Read `body-layer/src/belief/ai_pilot_wheel.py`'s `ParkedFlightState.held_heading`/`held_altitude`/
  `held_altitude_ref`/`held_speed` -- confirmed these are parsed from the exact same overlay text
  (`apw_course_text`/`apw_alt_text`/`apw_alt_add_text`/`apw_speed_text`) that `Export.lua`'s own
  `Petrobrain/ai_pilot_wheel.lua` already parses and holds in module-level locals
  (`ai_pilot_course_text`/`ai_pilot_alt_text`/`ai_pilot_alt_add_text`/`ai_pilot_speed_text`) --
  the same data is already live, in-process, on the Lua side; no new wire message is needed.
- Confirmed `flight_control.lua` already depends read-only on `ai_pilot_wheel.is_parked`/`stick_
  park_raw` (Decision 25's cross-module seam) -- adding `held_targets()` to that same read-only
  surface is the existing pattern, not a new one.
- Reproduced the mechanism in the toy-plant harness (`aircraft-layer/tests/
  test_flight_control_law.py::TestUnparkTakeSeedFromMode2SetTargets::
  test_without_a_seed_a_mid_break_unpark_never_levels_or_converges`): `law_init_at_take` called with
  a captured 25 deg bank and a residual 6 deg/s rate (no seed) picks `turn_mode = true`; run through
  2000 steps of the bank-lag+heading-integration toy plant, `in_band_heading` stays `false` for the
  whole run (structurally -- `law_update` forces it `false` whenever `turn_mode` is set) and the
  bank never settles back toward level (`> 5 deg` at the end) -- confirmed this is the pre-fix
  behaviour by running it against the unmodified function signature first.
- Reproduced the fix the same way (`test_with_a_held_heading_the_unpark_rolls_level_and_converges`):
  the identical captured state, but with `seed = { heading_deg = 0.0 }`, picks heading mode
  immediately and the toy plant's bank converges back under 5 deg within the same 2000 steps.
- Reproduced end to end through the real `run_flight_control` driver (`aircraft-layer/tests/
  test_flight_control_lua.py::TestUnparkTakeSeedsFromMode2SetTargets`): an unpark with a held
  heading 78 deg away from the measured one never reaches `fc_in_band_heading: true` (converging to
  the *held* value, not the measured one), while a **voice** take with the identical held value and
  measured heading reaches `fc_in_band_heading: true` immediately -- confirming the seed is wired
  into the unpark-take path only, never the voice-take path, as Decision 24's own voice-take
  heuristic still requires.

### Fix Applied

**Seeding route chosen**: an in-process Lua read, not a new wire message. `ai_pilot_wheel.lua`
gains one new read-only export, `held_targets()` (mirroring `is_parked`/`player_seat`/`stick_park_
raw`'s existing shape), returning `{heading_deg, alt_m, alt_ref, speed_kmh}` parsed off the same
locals `update_ai_pilot_wheel_overlay` already populates every poll (`ai_pilot_course_text`/`ai_
pilot_alt_text`/`ai_pilot_alt_add_text`/`ai_pilot_speed_text`, via the existing `ai_pilot_parse_
altitude_text` helper for the altitude field) -- no second parse site. This is the simplest correct
route because the data already lives in the same Lua process Decision 25's seam already crosses
read-only; sending it over the wire from body-layer would mean body-layer re-deriving (or body-layer
sending back) exactly what Lua already has locally, for no benefit, and would need a new message
shape body-layer has no reason to otherwise send (Decision 23's own "never a raw axis value" is
about axis values specifically, but routing *any* of this through body-layer when Lua already holds
it would be the same kind of indirection the project's "do not reinvent the wheel" seam table argues
against -- this is a same-process read, not a new cross-process one).

`law_init_at_take(measured, limits, command, seed)` gains a fourth, optional parameter. Every
existing call site (the toy-plant suite, the voice-take path) passes nothing, so `seed = seed or {}`
reproduces the exact prior behaviour unchanged. For each field independently (Decision 24's own
"fall back to current measured state when not known"):
- `seed.heading_deg` present (a `number`) -> heading mode is forced **unconditionally** (never turn
  mode, regardless of bank at capture) and `heading_goal_deg` is that value. Absent/non-numeric ->
  the original bank-at-capture heuristic, unchanged.
- `seed.alt_m` present -> `alt_goal_m` is that value, with `seed.alt_ref == "B"` mapping to `"baro"`
  (anything else, including `nil`, to `"agl"` -- the module's existing ref vocabulary). Absent ->
  the original stopping-height formula, unchanged.
- `seed.speed_kmh` present -> `speed_goal_mps = seed.speed_kmh / 3.6`. Absent -> the original
  `measured.ias_mps`, unchanged (this is also the reason speed almost never visibly differs in
  practice: the fallback is already "whatever speed was captured", and the seed only matters when
  mode 2's own dial disagrees with the instantaneous reading, e.g. mid-ramp).

`run_active_frame`'s `just_took` branch builds the seed **only when `fc_take_origin == "unpark"`**
(never for a voice take) and only when `ai_pilot_wheel` loaded at all, via `safe_call(ai_pilot_
wheel.held_targets)` -- a failed call or missing module yields `seed = nil`, falling back to the
pre-existing behaviour exactly as if this fix did not exist (same "unknown is never a licence to
assume" posture the module docstring already states for `is_parked`).

Files touched:
- `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua` -- new `held_targets()` + `M.held_
  targets` export; module-header depends-on comment in `flight_control.lua` updated to name it.
- `aircraft-layer/dcs-export/Petrobrain/flight_control.lua` -- `law_init_at_take`'s new `seed`
  parameter and per-field fallback logic; the unpark-take call site in `run_active_frame` builds the
  seed from `ai_pilot_wheel.held_targets()`.
- `aircraft-layer/tests/test_flight_control_law.py` -- new `TestUnparkTakeSeedFromMode2SetTargets`
  (seed-field mapping, all-nil-seed-matches-no-seed, and the two toy-plant convergence tests above).
- `aircraft-layer/tests/test_flight_control_lua.py` -- `ai_pilot_wheel` mock table gains `held_
  targets`; new `TestUnparkTakeSeedsFromMode2SetTargets` (unpark adopts the held heading, voice take
  ignores it).

No conflict with any recorded decision: Decision 24's voice-take heuristic is untouched (the seed
only ever applies to `fc_take_origin == "unpark"`), Decision 23's wire invariant is untouched (no
new message, no axis value), and Decision 25's read-only cross-module seam is extended by one
function in the same shape as the three it already has.

### Verification

- `aircraft-layer/tests/test_flight_control_law.py` + `test_flight_control_lua.py`: 66 passed (32 +
  34, both files run together above). Full `aircraft-layer/tests`: 1010 passed.
- `ruff format --check`/`ruff check` aircraft-layer `src`/`tests`: clean (one file, `test_flight_
  control_law.py`, needed a `ruff format` pass after the new tests were added -- reformatted, then
  reverified clean).
- `cd aircraft-layer && .venv/bin/mypy src`: Success, no issues found in 28 source files.
- `luac5.5 -p` on both touched Lua files: both pass (no `lua5.1`/`luac5.1` on this machine; `lua5.5`
  is the closest available and this project's `luac5.1`-specific note is about catching syntax DCS
  would reject, which neither file's edit introduces -- both are ordinary local-function/table-field
  additions, no new syntax construct).
- GETGLOBAL-equivalent check (`luajit -bl <file> | grep GGET`, luajit's own bytecode name for the
  same instruction class `luac5.1 -l` calls `GETGLOBAL`) on both touched files: every name listed is
  a genuine Lua stdlib function, a real DCS API, or this project's own established cross-module/
  `core.lua` global (`ai_pilot_wheel`, `client`, `debug_log`, the `extract_json_*`/`fmt_*_or_null`/
  `json_escape_string` helpers) -- no unresolved reference to either file's own newly added local
  function (`held_targets`, or `law_init_at_take`'s new local variables), confirming the local-
  before-use ordering is correct in both files.
- body-layer is untouched by this fix (the task was scoped to the unpark-take path and goal seeding,
  both of which turned out to live entirely in Lua) -- not re-run here.
