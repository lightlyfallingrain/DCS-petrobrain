"""`body._resolve_command_reset` -- BL-16 sortie 2026-11-20 (`docs/
acceptance/2026-11-20-sortie-feedback.md`, `plans/flight-control/
debug.md`): body-layer's own process-start reset. User's own words:
*"if body layer resets, it could send a reset signal. that would then
reset the counters and reset state at aircraft layer too. then body and
collector would match"*, and on whether Petrovich lets go: *"yes let
go. A service reset is error situation, that should not happen."*

Exercises the composition only (holding/sending the reset, confirming
it, bounding the resend) -- `advance_flight_control_state`/`advance_
parked_flight_state`'s own `lua_reset_epoch` mirroring is tested in
`test_flight_control.py`/`test_ai_pilot_wheel.py`."""

from __future__ import annotations

import time
from dataclasses import replace

from aircraft_client import AircraftLayerError
from belief.ai_pilot_wheel import ParkedFlightState
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from belief.flight_control import FlightControlState
from body import (
    COMMAND_RESET_RESEND_INTERVAL_S,
    ConsolePerceptionRunner,
    _resolve_command_reset,
)


class _FakeAircraftClient:
    def __init__(self, *, raise_on_write: bool = False) -> None:
        self.reset_calls: list[int] = []
        self.raise_on_write = raise_on_write

    def write_reset(self, epoch: int) -> None:
        if self.raise_on_write:
            raise AircraftLayerError("simulated send failure")
        self.reset_calls.append(epoch)


def _runner(**fields: object) -> tuple[ConsolePerceptionRunner, _FakeAircraftClient]:
    client = _FakeAircraftClient(
        raise_on_write=bool(fields.pop("raise_on_write", False))
    )
    runner = ConsolePerceptionRunner(
        aircraft_client=client,  # type: ignore[arg-type]
        command_reset_epoch=42,
        **fields,  # type: ignore[arg-type]
    )
    return runner, client


def _console(lua_reset_epoch: int | None) -> CrewConsole:
    console = CrewConsole(store=ContactStore())
    console.flight_control_state = FlightControlState(lua_reset_epoch=lua_reset_epoch)
    return console


class TestResolveCommandReset:
    def test_sends_the_reset_when_neither_channel_has_confirmed(self) -> None:
        runner, client = _runner()
        console = _console(None)

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert client.reset_calls == [42]
        assert runner.command_reset_confirmed is False
        assert runner.command_reset_last_sent_wall is not None

    def test_confirms_once_both_channels_echo_the_epoch(self) -> None:
        runner, client = _runner(
            parked_flight_state=replace(ParkedFlightState(), lua_reset_epoch=42)
        )
        console = _console(42)

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert runner.command_reset_confirmed is True
        # Confirmed -- no send needed, even though nothing was sent yet
        # this process (`command_reset_last_sent_wall` still `None`).
        assert client.reset_calls == []

    def test_one_channel_confirmed_the_other_not_still_holds(self) -> None:
        """Both channels must echo the epoch -- one confirming alone is
        not enough, since the other channel's own seq-carrying sends
        (`_apply_ai_pilot_wheel_goal`/`_apply_flight_control`) are
        gated on the same single `command_reset_confirmed` flag."""
        runner, client = _runner(
            parked_flight_state=replace(ParkedFlightState(), lua_reset_epoch=42)
        )
        console = _console(None)  # mode 1 has not echoed it yet

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert runner.command_reset_confirmed is False
        assert client.reset_calls == [42]

    def test_a_different_epoch_does_not_confirm(self) -> None:
        """A stale echo from a previous process's own epoch (persisted
        in Lua across a mission restart, see `flight_control.lua`'s/
        `ai_pilot_wheel.lua`'s own `reset()`) must not be mistaken for
        this process's confirmation."""
        runner, client = _runner(
            parked_flight_state=replace(ParkedFlightState(), lua_reset_epoch=7)
        )
        console = _console(7)

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert runner.command_reset_confirmed is False
        assert client.reset_calls == [42]

    def test_already_confirmed_is_a_true_no_op(self) -> None:
        runner, client = _runner(command_reset_confirmed=True)
        console = _console(None)

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert client.reset_calls == []
        assert runner.command_reset_last_sent_wall is None

    def test_resend_is_bounded_by_the_interval(self) -> None:
        """A send within `COMMAND_RESET_RESEND_INTERVAL_S` of the last
        one does not resend -- the "bounded" half of "resends while
        unconfirmed, bounded"."""
        runner, client = _runner()
        console = _console(None)

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]
        assert client.reset_calls == [42]
        first_sent_wall = runner.command_reset_last_sent_wall
        assert first_sent_wall is not None

        # Immediately again, well within the resend interval.
        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]
        assert client.reset_calls == [42]
        assert runner.command_reset_last_sent_wall == first_sent_wall

        # Simulate the interval having elapsed.
        runner.command_reset_last_sent_wall = (
            time.monotonic() - COMMAND_RESET_RESEND_INTERVAL_S - 0.01
        )
        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]
        assert client.reset_calls == [42, 42]

    def test_a_failed_send_does_not_raise_and_still_sets_the_resend_clock(
        self,
    ) -> None:
        """If the aircraft layer is not up yet, this keeps waiting
        without crashing -- `AircraftLayerError` is caught, and the
        resend clock still advances so the next attempt is bounded the
        same way a successful send's would be."""
        runner, client = _runner(raise_on_write=True)
        console = _console(None)

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert runner.command_reset_confirmed is False
        assert runner.command_reset_last_sent_wall is not None
