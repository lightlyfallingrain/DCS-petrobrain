"""`CrewConsole`'s BL-16 mode 2 Stage P2a/P2b dispatch (`plans/
flight-control/plan.md`, "Stage P2 ready to build"): the FLT/HVR goal
vocabulary (`level_flight`/`turn_heading`/`turn_heading_relative`/
`set_speed`/`speed_step`/`set_altitude`/`altitude_step`/`hold_altitude`/
`level_off`) and HVRT translate (`hvrt_translate_*`/`hvrt_hold`/
`hvrt_step_*`). Each handler only ever sets a one-shot transition field
for `body.py`'s poll loop to apply (`ai_pilot_goal_transition`/
`ai_pilot_level_flight_transition`/`ai_pilot_hvrt_transition`/`ai_pilot_
hvrt_step_transition`) -- these tests check the readback and the
transition value, not the real wire effect (covered by `test_ai_pilot_
wheel.py`'s own actions/`test_ai_pilot_wheel_lua.py`'s Lua tests)."""

from __future__ import annotations

from dataclasses import replace

from belief.ai_pilot_wheel import AiPilotGoalRequest, ParkedFlightState
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole


def _console(**state_fields: object) -> CrewConsole:
    console = CrewConsole(store=ContactStore())
    console.parked_flight_state = replace(ParkedFlightState(), **state_fields)
    return console


class TestLevelFlight:
    def test_freezes_all_three_known_values(self) -> None:
        console = _console(held_heading=90.0, held_altitude=300.0, held_speed=150.0)
        lines = console.handle_command("level_flight", now_sim=0.0)
        assert lines == ["Level flight."]
        assert console.ai_pilot_level_flight_transition is True

    def test_unable_when_nothing_is_known_yet(self) -> None:
        console = _console()
        lines = console.handle_command("level_flight", now_sim=0.0)
        assert lines == ["Unable, not ready."]
        assert console.ai_pilot_level_flight_transition is False


class TestTurnHeading:
    def test_speaks_the_resolved_heading_digit_by_digit(self) -> None:
        console = _console()
        lines = console.handle_command(
            "turn_heading", now_sim=0.0, slots={"heading_deg": 315}
        )
        assert lines == ["Heading 3 1 5."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="heading", heading_deg=315.0
        )

    def test_negative_or_over_360_wraps(self) -> None:
        console = _console()
        lines = console.handle_command(
            "turn_heading", now_sim=0.0, slots={"heading_deg": 370}
        )
        assert lines == ["Heading 1 0."]

    def test_missing_slot_says_again(self) -> None:
        console = _console()
        lines = console.handle_command("turn_heading", now_sim=0.0, slots=None)
        assert lines == ["say again -- no heading heard"]
        assert console.ai_pilot_goal_transition is None


class TestTurnHeadingRelative:
    def test_turns_right_from_the_held_heading(self) -> None:
        console = _console(held_heading=10.0)
        lines = console.handle_command(
            "turn_heading_relative",
            now_sim=0.0,
            slots={"direction": "right", "degrees": 20},
        )
        assert lines == ["20 right."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="heading", heading_deg=30.0
        )

    def test_turns_left_from_the_held_heading(self) -> None:
        console = _console(held_heading=10.0)
        lines = console.handle_command(
            "turn_heading_relative",
            now_sim=0.0,
            slots={"direction": "left", "degrees": 20},
        )
        assert lines == ["20 left."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="heading", heading_deg=350.0
        )

    def test_unable_without_a_known_current_heading(self) -> None:
        console = _console()
        lines = console.handle_command(
            "turn_heading_relative",
            now_sim=0.0,
            slots={"direction": "left", "degrees": 20},
        )
        assert lines == ["Unable, not ready."]


class TestSetSpeed:
    def test_snaps_a_numeric_request_for_the_readback(self) -> None:
        console = _console()
        lines = console.handle_command(
            "set_speed", now_sim=0.0, slots={"speed_kmh": 140}
        )
        assert lines == ["Speed 1 5 0."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="speed", speed_kmh=140.0
        )

    def test_the_literal_max_speaks_max(self) -> None:
        console = _console()
        lines = console.handle_command(
            "set_speed", now_sim=0.0, slots={"speed_kmh": "max"}
        )
        assert lines == ["Speed max."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="speed", speed_kmh="max"
        )


class TestSpeedStep:
    def test_steps_up_from_the_held_speed(self) -> None:
        console = _console(held_speed=120.0)
        lines = console.handle_command(
            "speed_step", now_sim=0.0, slots={"direction": "up"}
        )
        assert lines == ["Speed 1 5 0."]

    def test_unable_without_a_known_held_speed(self) -> None:
        console = _console()
        lines = console.handle_command(
            "speed_step", now_sim=0.0, slots={"direction": "up"}
        )
        assert lines == ["Unable, not ready."]


class TestSetAltitude:
    def test_a_reachable_radar_request_is_honoured(self) -> None:
        console = _console(held_altitude_ref="B")
        lines = console.handle_command(
            "set_altitude",
            now_sim=0.0,
            slots={"altitude_m": 300, "reference": "radar"},
        )
        assert lines == ["300 meters."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="altitude", altitude_m=300.0, altitude_ref="radar"
        )

    def test_a_target_above_the_cap_speaks_barometric_not_radar(self) -> None:
        console = _console(held_altitude_ref="R")
        lines = console.handle_command(
            "set_altitude",
            now_sim=0.0,
            slots={"altitude_m": 900, "reference": "radar"},
        )
        assert lines == ["900 meters barometric."]

    def test_no_reference_spoken_keeps_the_current_one(self) -> None:
        console = _console(held_altitude_ref="R")
        lines = console.handle_command(
            "set_altitude", now_sim=0.0, slots={"altitude_m": 300}
        )
        assert lines == ["300 meters."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="altitude", altitude_m=300.0, altitude_ref="radar"
        )


class TestAltitudeStep:
    def test_climbs_from_the_held_altitude(self) -> None:
        console = _console(held_altitude=300.0, held_altitude_ref="B")
        lines = console.handle_command(
            "altitude_step",
            now_sim=0.0,
            slots={"direction": "climb", "amount_m": 50},
        )
        assert lines == ["350 meters barometric."]

    def test_descends_from_the_held_altitude(self) -> None:
        console = _console(held_altitude=300.0, held_altitude_ref="R")
        lines = console.handle_command(
            "altitude_step",
            now_sim=0.0,
            slots={"direction": "descend", "amount_m": 50},
        )
        assert lines == ["250 meters."]

    def test_unable_without_a_known_held_altitude(self) -> None:
        console = _console()
        lines = console.handle_command(
            "altitude_step",
            now_sim=0.0,
            slots={"direction": "climb", "amount_m": 50},
        )
        assert lines == ["Unable, not ready."]


class TestHoldAltitude:
    def test_freezes_at_the_held_value_and_reference(self) -> None:
        console = _console(held_altitude=300.0, held_altitude_ref="B")
        lines = console.handle_command("hold_altitude", now_sim=0.0)
        assert lines == ["Holding 300 meters."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="altitude", altitude_m=300.0, altitude_ref="barometric"
        )

    def test_unable_without_a_known_held_altitude(self) -> None:
        console = _console()
        lines = console.handle_command("hold_altitude", now_sim=0.0)
        assert lines == ["Unable, not ready."]


class TestLevelOff:
    def test_holds_the_current_heading(self) -> None:
        console = _console(held_heading=120.0)
        lines = console.handle_command("level_off", now_sim=0.0)
        assert lines == ["Heading 1 2 0."]
        assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
            param="heading", heading_deg=120.0
        )

    def test_unable_without_a_known_current_heading(self) -> None:
        console = _console()
        lines = console.handle_command("level_off", now_sim=0.0)
        assert lines == ["Unable, not ready."]


class TestHvrtTranslate:
    def test_dispatches_from_hover(self) -> None:
        console = _console(ai_mode="HVR")
        lines = console.handle_command("hvrt_translate_left", now_sim=0.0)
        assert lines == ["Left."]
        assert console.ai_pilot_hvrt_transition == "left"

    def test_dispatches_while_already_in_hvrt(self) -> None:
        console = _console(ai_mode="HVRT")
        lines = console.handle_command("hvrt_translate_forward", now_sim=0.0)
        assert lines == ["Forward."]
        assert console.ai_pilot_hvrt_transition == "forward"

    def test_unable_when_not_in_hover(self) -> None:
        console = _console(ai_mode="FLT")
        lines = console.handle_command("hvrt_translate_right", now_sim=0.0)
        assert lines == ["Unable, not ready."]
        assert console.ai_pilot_hvrt_transition is None

    def test_unable_before_any_mode_has_been_read(self) -> None:
        console = _console()
        lines = console.handle_command("hvrt_translate_back", now_sim=0.0)
        assert lines == ["Unable, not ready."]


class TestHvrtHold:
    def test_clears_the_translate(self) -> None:
        console = _console(ai_mode="HVRT")
        lines = console.handle_command("hvrt_hold", now_sim=0.0)
        assert lines == ["Holding."]
        assert console.ai_pilot_hvrt_transition == "hold"

    def test_unable_when_not_in_hover(self) -> None:
        console = _console(ai_mode="CBTM")
        lines = console.handle_command("hvrt_hold", now_sim=0.0)
        assert lines == ["Unable, not ready."]


class TestHvrtStep:
    def test_taps_up(self) -> None:
        console = _console(ai_mode="HVRT")
        lines = console.handle_command("hvrt_step_up", now_sim=0.0)
        assert lines == ["Up."]
        assert console.ai_pilot_hvrt_step_transition == "up"

    def test_taps_down(self) -> None:
        console = _console(ai_mode="HVR")
        lines = console.handle_command("hvrt_step_down", now_sim=0.0)
        assert lines == ["Down."]
        assert console.ai_pilot_hvrt_step_transition == "down"

    def test_unable_when_not_in_hover(self) -> None:
        console = _console(ai_mode="FLT")
        lines = console.handle_command("hvrt_step_up", now_sim=0.0)
        assert lines == ["Unable, not ready."]
        assert console.ai_pilot_hvrt_step_transition is None


class TestTransitionsResetEachDispatch:
    """The reset-at-top-of-`handle_command` convention every one-shot
    signal in this class follows (`observ_transition`'s own docstring) --
    a stale value from an earlier dispatch must not leak into an
    unrelated later command's evaluation."""

    def test_a_later_unrelated_command_clears_the_goal_transition(self) -> None:
        console = _console(held_heading=10.0)
        console.handle_command("turn_heading", now_sim=0.0, slots={"heading_deg": 90})
        assert console.ai_pilot_goal_transition is not None
        console.handle_command("radio_check", now_sim=0.1)
        assert console.ai_pilot_goal_transition is None

    def test_a_later_unrelated_command_clears_the_hvrt_transition(self) -> None:
        console = _console(ai_mode="HVRT")
        console.handle_command("hvrt_translate_left", now_sim=0.0)
        assert console.ai_pilot_hvrt_transition is not None
        console.handle_command("radio_check", now_sim=0.1)
        assert console.ai_pilot_hvrt_transition is None


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
