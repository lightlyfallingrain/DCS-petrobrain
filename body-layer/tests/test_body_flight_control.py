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
from io import StringIO
from typing import Any

from aircraft_client import AircraftLayerError
from belief.crew_console import CrewConsole
from belief.flight_authority import PendingFlightReadback
from belief.flight_control import FlightControlGoalRequest
from body import _apply_flight_requests


class _FakeRunner:
    """Stands in for `ConsolePerceptionRunner` -- `_apply_flight_requests`
    only reads/writes `command_seq`, mission-wide per the plan's own
    "one body-layer counter" (section 5). BL-16 M3 (`plans/
    flight-lift-vector/plan.md`, section E) also reads `last_ownship_
    state` (via `_compose_and_relay_terrain`) -- `None` here (no
    telemetry simulated in this file) takes that function's own early
    return, so `_terrain_sent`/`_terrain_seq` are never touched."""

    def __init__(self, command_seq: int = 0) -> None:
        self.command_seq = command_seq
        self.last_ownship_state = None
        self._terrain_sent: dict[int, Any] = {}
        self._terrain_seq = 0


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
        """Debug-2026-11-23, problem 1 -- a release is now queued as
        its own `PendingTake` (`flight_pending_release`), the exact
        `take` twin, so `drain_flight_control` waits for Lua's own ack
        before ever speaking "You have controls." -- it is no longer
        spoken at dispatch time."""
        client = _FakeAircraftClient()
        runner = _FakeRunner()
        console = _console()
        console.flight_control_transition = "release"
        console.pending_release_says = "You have controls."

        _apply_flight_requests(runner, console, client, 1, 7.0)  # type: ignore[arg-type]

        assert console.flight_control_transition is None
        assert console.pending_release_says is None
        _epoch, seq, _until, kind, fields = client.flight_calls[0]
        assert seq == 1
        assert kind == "release"
        assert fields == {}
        # No `PendingTake` is queued on the *take* field for a release.
        assert console.flight_pending_take is None
        pending = console.flight_pending_release
        assert pending is not None
        assert pending.seq == 1
        assert pending.says == "You have controls."
        assert pending.sent_at_sim == 7.0

    def test_a_release_with_no_recorded_says_falls_back_to_the_default_line(
        self,
    ) -> None:
        client = _FakeAircraftClient()
        runner = _FakeRunner()
        console = _console()
        console.flight_control_transition = "release"

        _apply_flight_requests(runner, console, client, 1, 0.0)  # type: ignore[arg-type]

        pending = console.flight_pending_release
        assert pending is not None
        assert pending.says == "You have controls."

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

    def test_a_goal_request_s_staged_readback_is_queued_against_the_sent_seq(
        self,
    ) -> None:
        """BL-16 Stage 3b (`plans/flight-desired-state/plan.md`, section
        3a, U1) -- `handle_command` stages the rule's own readback text
        into `pending_flight_readback_lines` rather than printing it;
        this is the glue that pairs it with the exact `seq` just sent,
        so `drain_flight_control` can wait for that `seq`'s own ack
        before ever speaking it."""
        client = _FakeAircraftClient()
        runner = _FakeRunner()
        console = _console()
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=270.0
        )
        console.pending_flight_readback_lines = ["Heading 270."]

        _apply_flight_requests(runner, console, client, 1, 5.0)  # type: ignore[arg-type]

        assert console.pending_flight_readback_lines is None
        assert console.pending_flight_readbacks == [
            PendingFlightReadback(seq=1, lines=("Heading 270.",), sent_at_sim=5.0)
        ]

    def test_no_staged_readback_queues_nothing(self) -> None:
        """The ordinary case -- most `set` requests this function sends
        come from a dispatch that produced no readback to defer at all
        (there is none for a successful mode-1 command with empty
        `lines`, e.g. none shipped today, but this is the "nothing
        staged" no-op this function must still handle correctly)."""
        client = _FakeAircraftClient()
        runner = _FakeRunner()
        console = _console()
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=270.0
        )

        _apply_flight_requests(runner, console, client, 1, 0.0)  # type: ignore[arg-type]

        assert console.pending_flight_readbacks == []

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
        for epoch, _limits, _terrain in client.flight_lease_calls:
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

    def test_a_staged_readback_is_dropped_with_unable_not_ready_on_the_same_edge(
        self,
    ) -> None:
        """BL-16 Stage 3b -- the Co-moving row 11 mode flip above drops
        the queued transition unsent; a readback `handle_command` had
        already staged for that now-unsent request must not leak into a
        later, unrelated dispatch, so it speaks "Unable, not ready."
        right here instead."""
        client = _FakeAircraftClient()
        runner = _FakeRunner()
        console = _console(overlay=True)
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=10.0
        )
        console.pending_flight_readback_lines = ["Heading 010."]
        output = StringIO()
        console.output = output

        _apply_flight_requests(runner, console, client, 1, 0.0)  # type: ignore[arg-type]

        assert console.pending_flight_readback_lines is None
        assert console.pending_flight_readbacks == []
        assert output.getvalue().strip() == "Unable, not ready."

    def test_a_send_failure_does_not_raise(self) -> None:
        client = _FakeAircraftClient(raise_on_write=True)
        runner = _FakeRunner()
        console = _console()
        console.flight_control_transition = "take"

        _apply_flight_requests(runner, console, client, 1, 0.0)  # type: ignore[arg-type]  # must not raise

        assert console.flight_control_transition is None
