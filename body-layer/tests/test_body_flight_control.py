"""`body._apply_flight_requests` -- BL-16 mode 1, Stage 3 (`plans/
flight-desired-state/plan.md`, section 5): the glue between `CrewConsole`'s
one-shot transition fields and the one numbered `flight` channel
(`AircraftLayerClient.write_flight`), replacing `_apply_flight_control`/
`write_flight_control` entirely. `belief.flight_control`'s own pure
functions (`take_controls`/`release_controls`) are tested directly in
`test_flight_control.py`; these tests exercise only the composition
`body.py` adds on top: sending a pending transition/goal with a freshly
minted `seq`, queuing a `PendingTake` for a take, and the lease.

**Removed along with `_apply_flight_control`** (Stage 3's own
deletions): the `wire_seq`/`lua_last_cmd_seq` reconciliation (the
staleness floor is `flight_desired`'s own `fd_epoch`/`fd_last_seq` now),
`flight_control_system_release_pending` (superseded by `belief.
flight_authority.resolve_pending_take`'s own timeout handling), and the
"goal held during `TAKING`" logic (`Export.lua`'s own stamp-filtered
`build_take_seed` handles that now, per `test_flight_control_lua.py`)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from aircraft_client import AircraftLayerError
from belief.crew_console import CrewConsole
from belief.flight_control import FlightControlGoalRequest
from body import _apply_flight_requests


class _FakeRunner:
    """Stands in for `ConsolePerceptionRunner` -- `_apply_flight_requests`
    only reads/writes `command_seq`, mission-wide per the plan's own
    "one body-layer counter" (section 5)."""

    def __init__(self, command_seq: int = 0) -> None:
        self.command_seq = command_seq


class _FakeAircraftClient:
    def __init__(self, *, raise_on_write: bool = False) -> None:
        self.flight_calls: list[tuple[Any, ...]] = []
        self.flight_lease_calls: list[tuple[Any, ...]] = []
        self.raise_on_write = raise_on_write

    def write_flight(self, *args: Any) -> None:
        if self.raise_on_write:
            raise AircraftLayerError("simulated send failure")
        self.flight_calls.append(args)

    def write_flight_lease(self, *args: Any) -> None:
        if self.raise_on_write:
            raise AircraftLayerError("simulated send failure")
        self.flight_lease_calls.append(args)


def _console(*, overlay: bool = False) -> CrewConsole:
    """`overlay=True` sets `flight_authority_state.fd_mode = "m2"`."""
    console = CrewConsole(store=None)  # type: ignore[arg-type]
    if overlay:
        console.flight_authority_state = replace(
            console.flight_authority_state, fd_mode="m2"
        )
    return console


class TestApplyFlightRequests:
    def test_a_take_transition_is_sent_with_a_fresh_seq_and_cleared(self) -> None:
        client = _FakeAircraftClient()
        runner = _FakeRunner(command_seq=0)
        console = _console()
        console.flight_control_transition = "take"
        console.pending_take_says = "I have controls."

        _apply_flight_requests(runner, console, client, 1, 10.0)  # type: ignore[arg-type]

        assert console.flight_control_transition is None
        assert console.pending_take_says is None
        assert len(client.flight_calls) == 1
        epoch, seq, until, kind, fields = client.flight_calls[0]
        assert epoch == 1
        assert seq == 1
        assert until > 10.0
        assert kind == "take"
        assert fields == {}
        assert runner.command_seq == 1
        # The take is queued as a `PendingTake`, using the recorded
        # `says` text, ready for `drain_flight_control` to resolve
        # against `fd_acks` on a later poll.
        pending = console.flight_pending_take
        assert pending is not None
        assert pending.seq == 1
        assert pending.says == "I have controls."
        assert pending.sent_at_sim == 10.0

    def test_a_take_with_no_recorded_says_falls_back_to_the_default_line(
        self,
    ) -> None:
        client = _FakeAircraftClient()
        runner = _FakeRunner()
        console = _console()
        console.flight_control_transition = "take"

        _apply_flight_requests(runner, console, client, 1, 0.0)  # type: ignore[arg-type]

        pending = console.flight_pending_take
        assert pending is not None
        assert pending.says == "I have controls."

    def test_a_release_transition_is_sent_and_cleared(self) -> None:
        client = _FakeAircraftClient()
        runner = _FakeRunner()
        console = _console()
        console.flight_control_transition = "release"

        _apply_flight_requests(runner, console, client, 1, 0.0)  # type: ignore[arg-type]

        assert console.flight_control_transition is None
        _epoch, seq, _until, kind, fields = client.flight_calls[0]
        assert seq == 1
        assert kind == "release"
        assert fields == {}
        # No `PendingTake` is queued for a release.
        assert console.flight_pending_take is None

    def test_a_goal_request_is_sent_as_a_set_with_its_fields_and_cleared(
        self,
    ) -> None:
        client = _FakeAircraftClient()
        runner = _FakeRunner()
        console = _console()
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=270.0
        )

        _apply_flight_requests(runner, console, client, 1, 0.0)  # type: ignore[arg-type]

        assert console.flight_control_goal_transition is None
        _epoch, seq, _until, kind, fields = client.flight_calls[0]
        assert seq == 1
        assert kind == "set"
        assert fields == {"heading_deg": 270.0}

    def test_both_a_transition_and_a_goal_in_one_poll_bump_the_sequence_twice(
        self,
    ) -> None:
        client = _FakeAircraftClient()
        runner = _FakeRunner()
        console = _console()
        console.flight_control_transition = "take"
        console.flight_control_goal_transition = FlightControlGoalRequest(turn=1)

        _apply_flight_requests(runner, console, client, 1, 0.0)  # type: ignore[arg-type]

        assert len(client.flight_calls) == 2
        seqs = [call[1] for call in client.flight_calls]
        assert seqs == [1, 2]
        assert runner.command_seq == 2

    def test_the_lease_resends_every_poll_regardless_of_pending_requests(
        self,
    ) -> None:
        client = _FakeAircraftClient()
        runner = _FakeRunner()
        console = _console()

        _apply_flight_requests(runner, console, client, 7, 0.0)  # type: ignore[arg-type]
        _apply_flight_requests(runner, console, client, 7, 1.0)  # type: ignore[arg-type]

        assert len(client.flight_lease_calls) == 2
        for epoch, _limits in client.flight_lease_calls:
            assert epoch == 7

    def test_a_stale_transition_is_discarded_while_overlay_flying(self) -> None:
        """BL-16 mode 1's Co-moving row 11: an `axes_*` goal action
        spoken just before a park -- both one-shots must be discarded
        unsent, with no `seq` consumed, whenever `flight_mode() ==
        "overlay"` by the time this poll runs."""
        client = _FakeAircraftClient()
        runner = _FakeRunner()
        console = _console(overlay=True)
        console.flight_control_transition = "take"
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=10.0
        )

        _apply_flight_requests(runner, console, client, 1, 0.0)  # type: ignore[arg-type]

        assert console.flight_control_transition is None
        assert console.flight_control_goal_transition is None
        assert console.pending_take_says is None
        assert client.flight_calls == []
        assert runner.command_seq == 0

    def test_a_send_failure_does_not_raise(self) -> None:
        client = _FakeAircraftClient(raise_on_write=True)
        runner = _FakeRunner()
        console = _console()
        console.flight_control_transition = "take"

        _apply_flight_requests(runner, console, client, 1, 0.0)  # type: ignore[arg-type]  # must not raise

        assert console.flight_control_transition is None
