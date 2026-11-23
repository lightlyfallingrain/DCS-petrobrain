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
    COMMAND_RESET_CONFIRM_TIMEOUT_S,
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


def _console(
    lua_reset_epoch: int | None, *, lua_mode: str | None = None
) -> CrewConsole:
    console = CrewConsole(store=ContactStore())
    console.flight_control_state = FlightControlState(
        lua_reset_epoch=lua_reset_epoch, lua_mode=lua_mode
    )
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

    def test_already_confirmed_with_both_echoes_still_matching_is_a_true_no_op(
        self,
    ) -> None:
        """Debug-2026-11-23 -- confirmed and *still* echoed (the common
        case for the rest of a sortie) sends nothing, unlike a confirmed
        state whose echo has gone stale (see `TestCommandResetResync`
        below)."""
        runner, client = _runner(
            command_reset_confirmed=True,
            parked_flight_state=replace(ParkedFlightState(), lua_reset_epoch=42),
        )
        console = _console(42)

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert client.reset_calls == []
        assert runner.command_reset_last_sent_wall is None
        assert runner.command_reset_confirmed is True

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


class TestCommandResetResync:
    """Debug-2026-11-23 -- a DCS mission (re)start re-runs `Export.lua`'s
    module init code, re-nilling every seq-carrying channel's own
    echoed epoch; the previous one-shot latch (`if runner.command_
    reset_confirmed: return`) never noticed this and kept gating
    `_apply_flight_requests`/`_apply_ai_pilot_wheel_goal` open with a
    now-stale `runner.command_reset_epoch`, which `flight_desired.lua`
    then refused `r:epoch` on every send -- the sortie's "unable, not
    ready" on "you have controls" after a mission restart."""

    def test_a_confirmed_reset_whose_echo_goes_stale_is_resent_and_unconfirmed(
        self,
    ) -> None:
        """Confirmed, then one channel's echo reverts to `None` (the
        reload) -- resent, and `command_reset_confirmed` flips back to
        `False` rather than staying a stale `True`."""
        runner, client = _runner(
            command_reset_confirmed=True,
            parked_flight_state=replace(ParkedFlightState(), lua_reset_epoch=42),
        )
        console = _console(42)
        # Both channels confirmed once -- now the reload nils one of
        # them back out (`fc_reset_epoch` -> nil).
        console.flight_control_state = replace(
            console.flight_control_state, lua_reset_epoch=None
        )

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert runner.command_reset_confirmed is False
        assert client.reset_calls == [42]

    def test_a_confirmed_reset_whose_echo_changes_to_a_different_epoch_is_resent(
        self,
    ) -> None:
        """Same mismatch, but the echoed value is a different (non-null)
        epoch rather than `None` -- still a mismatch, same resend."""
        runner, client = _runner(
            command_reset_confirmed=True,
            parked_flight_state=replace(ParkedFlightState(), lua_reset_epoch=42),
        )
        console = _console(42)
        console.flight_control_state = replace(
            console.flight_control_state, lua_reset_epoch=7
        )

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert runner.command_reset_confirmed is False
        assert client.reset_calls == [42]

    def test_resync_restarts_the_unconfirmed_since_clock_rather_than_firing_the_warning_immediately(
        self,
    ) -> None:
        """A mismatch that reappears long after the original startup
        handshake confirmed must not fire the slow-confirm warning on
        its very next poll -- `command_reset_unconfirmed_since_wall` is
        reset to `None` on the un-confirming edge (this test's own
        assertion), so the timeout clock starts counting from *this*
        mismatch, same as a fresh process start would."""
        runner, client = _runner(
            command_reset_confirmed=True,
            parked_flight_state=replace(ParkedFlightState(), lua_reset_epoch=42),
            # Simulate a stale cursor left over from long before this
            # process's original (successful) handshake.
            command_reset_unconfirmed_since_wall=time.monotonic() - 10_000.0,
            command_reset_warned=True,
        )
        console = _console(42, lua_mode="off")
        console.flight_control_state = replace(
            console.flight_control_state, lua_reset_epoch=None
        )

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert runner.command_reset_confirmed is False
        assert runner.command_reset_warned is False
        assert console.command_reset_slow_pending is False
        # The clock restarted this call (aircraft layer already up, a
        # sample exists) rather than carrying the ancient cursor
        # forward.
        assert runner.command_reset_unconfirmed_since_wall is not None
        assert time.monotonic() - runner.command_reset_unconfirmed_since_wall < 1.0

    def test_resync_then_reconfirming_restores_confirmed_and_the_right_epoch(
        self,
    ) -> None:
        """Confirmed -> echo goes stale (unconfirmed, resent) -> Lua
        echoes the (unchanged) `command_reset_epoch` again -- confirms
        once more, with `runner.command_reset_epoch` itself never having
        changed, so the very next `_apply_flight_requests`/`_apply_ai_
        pilot_wheel_goal` send after this call carries the same, correct
        epoch Lua now actually holds."""
        runner, client = _runner(
            command_reset_confirmed=True,
            parked_flight_state=replace(ParkedFlightState(), lua_reset_epoch=42),
        )
        console = _console(42)
        console.flight_control_state = replace(
            console.flight_control_state, lua_reset_epoch=None
        )

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]
        assert runner.command_reset_confirmed is False

        # Lua re-echoes this process's own (unchanged) epoch, e.g. once
        # the resent reset lands.
        console.flight_control_state = replace(
            console.flight_control_state, lua_reset_epoch=42
        )
        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert runner.command_reset_confirmed is True
        assert runner.command_reset_epoch == 42


class TestResolveCommandResetFailLoud:
    """BL-16 fail-loud (2026-11-20, `docs/acceptance/
    2026-11-20-sortie-feedback.md`): the aircraft layer up, reset still
    unconfirmed after `COMMAND_RESET_CONFIRM_TIMEOUT_S` case -- a stale
    deployed `Export.lua`/`Petrobrain/*.lua` that never echoes the
    epoch."""

    def test_quiet_while_no_status_sample_has_ever_arrived(self) -> None:
        """Neither feed has a sample yet -- the aircraft layer simply is
        not up. Must never warn, however long this runs."""
        runner, client = _runner()
        console = _console(None)  # lua_mode also None -- no sample yet

        for _ in range(5):
            _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]
            runner.command_reset_last_sent_wall = (
                time.monotonic() - COMMAND_RESET_RESEND_INTERVAL_S - 0.01
            )

        assert runner.command_reset_unconfirmed_since_wall is None
        assert runner.command_reset_warned is False
        assert console.command_reset_slow_pending is False

    def test_warns_and_queues_one_spoken_line_after_the_timeout(self) -> None:
        """A sample has arrived (aircraft layer up) but the epoch has
        not echoed -- once `COMMAND_RESET_CONFIRM_TIMEOUT_S` has passed
        since that first sample, warn once and queue the spoken line."""
        runner, client = _runner()
        console = _console(None, lua_mode="off")  # a sample, just not the echo

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]
        assert runner.command_reset_unconfirmed_since_wall is not None
        assert runner.command_reset_warned is False
        assert console.command_reset_slow_pending is False

        # Simulate the timeout having elapsed since that first sample.
        runner.command_reset_unconfirmed_since_wall = (
            time.monotonic() - COMMAND_RESET_CONFIRM_TIMEOUT_S - 0.01
        )
        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert runner.command_reset_warned is True
        assert console.command_reset_slow_pending is True

    def test_warns_only_once(self) -> None:
        """Not re-queued on a later poll once already warned -- the
        spoken line is one-shot, same as `config_error_pending`."""
        runner, client = _runner()
        console = _console(None, lua_mode="off")
        runner.command_reset_unconfirmed_since_wall = (
            time.monotonic() - COMMAND_RESET_CONFIRM_TIMEOUT_S - 0.01
        )
        runner.command_reset_warned = True

        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        # Already warned -- draining the pending flag (as `CrewConsole.
        # drain_command_reset_slow` would, elsewhere) and calling again
        # must not re-set it.
        console.command_reset_slow_pending = False
        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]
        assert console.command_reset_slow_pending is False

    def test_confirming_clears_the_pending_line_unspoken(self) -> None:
        """A confirmation landing after the warning was queued but
        before `drain_command_reset_slow` ever ran cancels it -- the
        player is never told about an error that has since resolved."""
        runner, client = _runner()
        console = _console(None, lua_mode="off")
        runner.command_reset_unconfirmed_since_wall = (
            time.monotonic() - COMMAND_RESET_CONFIRM_TIMEOUT_S - 0.01
        )
        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]
        assert console.command_reset_slow_pending is True

        # Now both channels echo the epoch.
        runner.parked_flight_state = replace(
            runner.parked_flight_state, lua_reset_epoch=42
        )
        console.flight_control_state = replace(
            console.flight_control_state, lua_reset_epoch=42
        )
        _resolve_command_reset(runner, console, client)  # type: ignore[arg-type]

        assert runner.command_reset_confirmed is True
        assert console.command_reset_slow_pending is False
