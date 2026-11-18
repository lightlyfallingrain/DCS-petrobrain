"""`body._apply_flight_control` -- BL-16 mode 1 Stage M1 (`plans/
flight-control/plan.md`, "Revised 2026-11-18"): the glue between
`CrewConsole`'s one-shot transition fields and the wire write
(`AircraftLayerClient.write_flight_control`). `belief.flight_control`'s
own pure functions (`take_controls`/`release_controls`/`decide_flight_
control`) are tested directly in `test_flight_control.py`; these tests
exercise only the composition `body.py` adds on top: sending a pending
transition/goal, bumping `wire_seq`, and the arm lease -- the same split
`test_body_ai_pilot_wheel.py` already draws for mode 2's sibling
function."""

from __future__ import annotations

from typing import Any

from aircraft_client import AircraftLayerError
from belief.crew_console import CrewConsole
from belief.flight_control import FlightControlGoalRequest, FlightControlState
from body import _apply_flight_control


class _FakeAircraftClient:
    def __init__(self, *, raise_on_write: bool = False) -> None:
        self.flight_control_calls: list[tuple[Any, ...]] = []
        self.raise_on_write = raise_on_write

    def write_flight_control(self, *args: Any) -> None:
        if self.raise_on_write:
            raise AircraftLayerError("simulated send failure")
        self.flight_control_calls.append(args)


def _console(state: FlightControlState) -> CrewConsole:
    console = CrewConsole(store=None)  # type: ignore[arg-type]
    console.flight_control_state = state
    return console


class TestApplyFlightControl:
    def test_a_take_transition_is_sent_and_cleared(self) -> None:
        client = _FakeAircraftClient()
        console = _console(FlightControlState(wire_seq=0))
        console.flight_control_transition = "take"

        _apply_flight_control(console, client)  # type: ignore[arg-type]

        assert console.flight_control_transition is None
        assert len(client.flight_control_calls) == 1
        seq, cmd, _limits, goal = client.flight_control_calls[0]
        assert seq == 1
        assert cmd == "take"
        assert goal is None
        assert console.flight_control_state.wire_seq == 1

    def test_a_release_transition_is_sent_and_cleared(self) -> None:
        client = _FakeAircraftClient()
        console = _console(FlightControlState(wire_seq=5))
        console.flight_control_transition = "release"

        _apply_flight_control(console, client)  # type: ignore[arg-type]

        assert console.flight_control_transition is None
        seq, cmd, _limits, _goal = client.flight_control_calls[0]
        assert seq == 6
        assert cmd == "release"

    def test_a_goal_request_is_sent_with_its_fields_and_cleared(self) -> None:
        client = _FakeAircraftClient()
        console = _console(FlightControlState(wire_seq=0))
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=270.0
        )

        _apply_flight_control(console, client)  # type: ignore[arg-type]

        assert console.flight_control_goal_transition is None
        seq, cmd, _limits, goal = client.flight_control_calls[0]
        assert seq == 1
        assert cmd == "goal"
        assert goal == {"heading_deg": 270.0}
        assert console.flight_control_state.wire_seq == 1

    def test_both_a_transition_and_a_goal_in_one_poll_bump_the_sequence_twice(
        self,
    ) -> None:
        client = _FakeAircraftClient()
        console = _console(FlightControlState(wire_seq=0))
        console.flight_control_transition = "take"
        console.flight_control_goal_transition = FlightControlGoalRequest(turn=1)

        _apply_flight_control(console, client)  # type: ignore[arg-type]

        assert len(client.flight_control_calls) == 2
        seqs = [call[0] for call in client.flight_control_calls]
        assert seqs == [1, 2]
        assert console.flight_control_state.wire_seq == 2

    def test_the_arm_lease_resends_every_poll_while_overlay_and_unpark_take(
        self,
    ) -> None:
        client = _FakeAircraftClient()
        console = _console(
            FlightControlState(phase="OVERLAY", unpark_take=True, wire_seq=0)
        )

        _apply_flight_control(console, client)  # type: ignore[arg-type]
        _apply_flight_control(console, client)  # type: ignore[arg-type]

        assert len(client.flight_control_calls) == 2
        for seq, cmd, _limits, goal in client.flight_control_calls:
            assert cmd == "arm"
            assert goal is None
        assert console.flight_control_state.wire_seq == 2

    def test_no_arm_is_sent_while_overlay_without_unpark_take(self) -> None:
        client = _FakeAircraftClient()
        console = _console(FlightControlState(phase="OVERLAY", unpark_take=False))

        _apply_flight_control(console, client)  # type: ignore[arg-type]

        assert client.flight_control_calls == []

    def test_row_11_other_direction_a_stale_transition_is_discarded_while_overlay(
        self,
    ) -> None:
        """BL-16 mode 1's Co-moving row 11, the direction that is
        specific to `_apply_flight_control` itself (the ai_pilot_*
        direction is `test_body_ai_pilot_wheel.py`'s own test): an
        `axes_*` goal action spoken just before a park races `decide_
        flight_control`'s park-edge transition to `OVERLAY`. Both
        one-shots must be discarded unsent, with no `wire_seq` bump --
        sending a stale axes request to Lua while he now flies through
        the overlay would be meaningless at best."""
        client = _FakeAircraftClient()
        console = _console(FlightControlState(phase="OVERLAY", wire_seq=3))
        console.flight_control_transition = "take"
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=10.0
        )

        _apply_flight_control(console, client)  # type: ignore[arg-type]

        assert console.flight_control_transition is None
        assert console.flight_control_goal_transition is None
        assert client.flight_control_calls == []
        assert console.flight_control_state.wire_seq == 3

    def test_a_send_failure_does_not_raise(self) -> None:
        client = _FakeAircraftClient(raise_on_write=True)
        console = _console(FlightControlState(wire_seq=0))
        console.flight_control_transition = "take"

        _apply_flight_control(console, client)  # type: ignore[arg-type]  # must not raise

        assert console.flight_control_transition is None
