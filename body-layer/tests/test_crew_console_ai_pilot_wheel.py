"""`CrewConsole`'s BL-16 mode 2 Stage P2a/P2b dispatch (`plans/
flight-control/plan.md`, "Stage P2 ready to build").

`[[BL-17]]` Stage 2 moved "turn left/right NN" off this static dispatch
table onto a rule (`config/rules/flight.lua`'s `turn_heading_relative`)
-- see `TestIncrementAiHeading` below and `test_rules_flight_actions.py`.
**Stage 4 moved every other command this file used to test** (`level_
flight`/`turn_heading`/`set_speed`/`speed_step`/`set_altitude`/
`altitude_step`/`hold_altitude`/`level_off`, and HVRT translate/hold/
step) onto rules too -- their own differential pins now live in
`test_rules_flight_actions.py`, which dispatches through the real gate
and the real shipped `flight.lua`, not a static token. What remains
here is `TestIncrementAiHeading` (Stage 2's own extracted action,
unaffected by Stage 4) and `TestDrainAiPilotWheelSpeech` (the
"mode_blocked" readback, never a command token at all)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from belief.ai_pilot_wheel import AiPilotGoalRequest, ParkedFlightState
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole


def _console(**state_fields: object) -> CrewConsole:
    console = CrewConsole(store=ContactStore())
    console.parked_flight_state = replace(ParkedFlightState(), **state_fields)
    return console


class TestIncrementAiHeading:
    """`[[BL-17]]` Stage 2 moved "turn left/right NN" off a static
    `handle_command` token onto a rule (`config/rules/flight.lua`'s
    `turn_heading_relative`, dispatched through `enabled_rule_ids`/
    `_handle_rule`) calling `CrewConsole.increment_ai_heading` directly --
    `test_rules_flight_actions.py` differentially pins the *old*
    `_handle_turn_heading_relative` readback/transition against the new
    rule end to end; these three are the unit-level equivalent of the
    `TestTurnHeadingRelative` class this replaced, now exercising the
    extracted method rather than a dispatch token that no longer exists.
    `[[BL-17]]` Stage 3b (D16) retired this method's own `NOT_READY`
    branch -- the third test below now pins that calling it directly
    without a held heading is a precondition violation, not a degrade."""

    def test_turns_right_from_the_held_heading(self) -> None:
        console = _console(held_heading=10.0)
        result = console.increment_ai_heading(20)
        assert result == {"ok": True, "reason": None}
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="heading", heading_deg=30.0
        )

    def test_turns_left_from_the_held_heading(self) -> None:
        console = _console(held_heading=10.0)
        result = console.increment_ai_heading(-20)
        assert result == {"ok": True, "reason": None}
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="heading", heading_deg=350.0
        )

    def test_asserts_the_precondition_the_gate_now_owns(self) -> None:
        """`[[BL-17]]` Stage 3b (D16) supersedes the old `{"ok": False,
        "reason": "NOT_READY"}` case this test used to pin: the
        `current is None` check is gone from `increment_ai_heading`
        itself -- it is dead code once the `"flight_control_heading"`
        category gate owns that precondition for the whole category (the
        gate only ever reaches `PASS`, and thus calls this method at all,
        once `held_heading is not None`). Calling this method directly
        with no held heading, bypassing the gate the way this unit test
        always has, is now a precondition violation the method asserts
        rather than degrades -- the real "unable, not flying" case is
        `test_rules_flight_actions.py`'s own gate-level tests."""
        console = _console()
        with pytest.raises(AssertionError):
            console.increment_ai_heading(-20)


class TestDrainAiPilotWheelSpeech:
    """`"mode_blocked"`'s own spoken line -- edge-triggered, once per
    exhausted attempt."""

    def test_speaks_once_when_mode_blocked_first_appears(self) -> None:
        console = _console(lua_goal_progress="mode_blocked")
        lines = console.drain_ai_pilot_wheel_speech(now_sim=0.0)
        assert lines == ["Unable, not ready."]

    def test_does_not_repeat_while_still_blocked(self) -> None:
        console = _console(lua_goal_progress="mode_blocked")
        console.drain_ai_pilot_wheel_speech(now_sim=0.0)
        lines = console.drain_ai_pilot_wheel_speech(now_sim=0.2)
        assert lines == []

    def test_speaks_again_after_a_fresh_exhaustion(self) -> None:
        console = _console(lua_goal_progress="mode_blocked")
        console.drain_ai_pilot_wheel_speech(now_sim=0.0)
        console.parked_flight_state = replace(
            console.parked_flight_state, lua_goal_progress="pressing"
        )
        console.drain_ai_pilot_wheel_speech(now_sim=0.2)
        console.parked_flight_state = replace(
            console.parked_flight_state, lua_goal_progress="mode_blocked"
        )
        lines = console.drain_ai_pilot_wheel_speech(now_sim=0.4)
        assert lines == ["Unable, not ready."]

    def test_silent_outside_mode_blocked(self) -> None:
        console = _console(lua_goal_progress="pressing")
        lines = console.drain_ai_pilot_wheel_speech(now_sim=0.0)
        assert lines == []
