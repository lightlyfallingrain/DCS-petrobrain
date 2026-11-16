"""`body._apply_ai_pilot_wheel_goal` -- BL-16 mode 2 Stage P2a/P2b
(`plans/flight-control/plan.md`, "Stage P2 ready to build"): the glue
between `CrewConsole`'s one-shot transition fields and the goal-channel
wire write (`AircraftLayerClient.write_ai_pilot_goal`). The rotation
mechanism/actions themselves are `belief.ai_pilot_wheel`'s own tested
surface (`test_ai_pilot_wheel.py`); these tests exercise only the
composition `body.py` adds on top: applying a transition, running
`decide_ai_pilot_wheel`, and deciding whether/what to send."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from belief.ai_pilot_wheel import (
    AiPilotGoalRequest,
    AiPilotWheelGoal,
    ParkedFlightState,
)
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from body import ConsolePerceptionRunner, _apply_ai_pilot_wheel_goal


class _FakeAircraftClient:
    def __init__(self) -> None:
        self.ai_pilot_goal_calls: list[tuple[Any, ...]] = []

    def write_ai_pilot_goal(self, *args: Any) -> None:
        self.ai_pilot_goal_calls.append(args)


def _runner(
    **state_fields: object,
) -> tuple[ConsolePerceptionRunner, _FakeAircraftClient]:
    client = _FakeAircraftClient()
    runner = ConsolePerceptionRunner(
        aircraft_client=client,  # type: ignore[arg-type]
        last_t_sim=10.0,
        parked_flight_state=replace(
            ParkedFlightState(parked_active=True), **state_fields
        ),
    )
    return runner, client


class TestApplyAiPilotWheelGoal:
    def test_a_turn_heading_transition_is_applied_and_sent(self) -> None:
        runner, client = _runner()
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_goal_transition = AiPilotGoalRequest(
            param="heading", heading_deg=90.0
        )

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        goal = runner.parked_flight_state.goal
        assert goal is not None
        assert goal.active_param == "heading"
        assert goal.heading_target_deg == 90.0
        assert console.ai_pilot_goal_transition is None
        assert len(client.ai_pilot_goal_calls) == 1
        assert client.ai_pilot_goal_calls[0][:2] == (goal.goal_seq, "heading")

    def test_level_flight_queues_all_three_known_values(self) -> None:
        runner, client = _runner(
            held_heading=10.0, held_altitude=300.0, held_speed=150.0
        )
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_level_flight_transition = True

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        goal = runner.parked_flight_state.goal
        assert goal is not None
        assert goal.heading_target_deg == 10.0
        assert goal.altitude_target_m == 300.0
        assert goal.speed_target_kmh == 150.0
        assert console.ai_pilot_level_flight_transition is False
        # One promoted (active), the other two queued -- all three
        # requested in one poll (plan's own "interleaved" design).
        assert goal.active_param is not None
        assert len(goal.pending_order) == 2

    def test_hvrt_transition_sets_the_direction(self) -> None:
        runner, client = _runner()
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_hvrt_transition = "left"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        goal = runner.parked_flight_state.goal
        assert goal is not None
        assert goal.hvrt_direction == "left"
        assert console.ai_pilot_hvrt_transition is None

    def test_hold_clears_the_hvrt_direction(self) -> None:
        runner, client = _runner(
            goal=AiPilotWheelGoal(hvrt_direction="left", goal_seq=1)
        )
        runner.ai_pilot_goal_last_sent_seq = 1
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_hvrt_transition = "hold"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        goal = runner.parked_flight_state.goal
        assert goal is not None
        assert goal.hvrt_direction is None

    def test_a_settled_param_is_cleared_and_the_next_one_promoted(self) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0,
            speed_target_kmh=150.0,
            active_param="heading",
            active_since_sim=5.0,
            pending_order=("speed",),
            goal_seq=1,
        )
        runner, client = _runner(goal=goal, lua_goal_progress="settled")
        runner.ai_pilot_goal_last_sent_seq = 1
        console = CrewConsole(store=ContactStore())

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        new_goal = runner.parked_flight_state.goal
        assert new_goal is not None
        assert new_goal.heading_target_deg is None
        assert new_goal.active_param == "speed"
        assert len(client.ai_pilot_goal_calls) == 1  # the new promotion is sent

    def test_no_send_when_goal_seq_has_not_moved(self) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0, active_param="heading", goal_seq=3
        )
        runner, client = _runner(goal=goal)
        runner.ai_pilot_goal_last_sent_seq = 3
        console = CrewConsole(store=ContactStore())

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        assert client.ai_pilot_goal_calls == []

    def test_hvrt_step_always_sends_with_a_bumped_goal_seq(self) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0, active_param="heading", goal_seq=3
        )
        runner, client = _runner(goal=goal)
        runner.ai_pilot_goal_last_sent_seq = 3
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_hvrt_step_transition = "up"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        assert len(client.ai_pilot_goal_calls) == 1
        call = client.ai_pilot_goal_calls[0]
        assert call[0] == 4  # bumped from 3
        assert call[-1] == "up"
        assert console.ai_pilot_hvrt_step_transition is None
        assert runner.ai_pilot_goal_last_sent_seq == 4

    def test_unparking_drops_the_goal_and_the_send_cursor(self) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0, active_param="heading", goal_seq=3
        )
        runner, client = _runner(goal=goal, parked_active=False)
        runner.ai_pilot_goal_last_sent_seq = 3
        console = CrewConsole(store=ContactStore())

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        assert runner.parked_flight_state.goal is None
        assert runner.ai_pilot_goal_last_sent_seq is None
        assert client.ai_pilot_goal_calls == []

    def test_no_ownship_sample_yet_is_a_no_op(self) -> None:
        client = _FakeAircraftClient()
        runner = ConsolePerceptionRunner(
            aircraft_client=client,  # type: ignore[arg-type]
            last_t_sim=None,
            parked_flight_state=ParkedFlightState(parked_active=True),
        )
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_goal_transition = AiPilotGoalRequest(
            param="heading", heading_deg=90.0
        )

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        assert runner.parked_flight_state.goal is None
        assert client.ai_pilot_goal_calls == []
