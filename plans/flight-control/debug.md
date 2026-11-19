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
