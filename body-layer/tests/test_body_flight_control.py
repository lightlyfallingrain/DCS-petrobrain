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

from dataclasses import replace
from typing import Any

from aircraft_client import AircraftLayerError
from belief.crew_console import CrewConsole
from belief.flight_control import FlightControlGoalRequest, FlightControlState
from body import _apply_flight_control


class _FakeAircraftClient:
    def __init__(self, *, raise_on_write: bool = False) -> None:
        self.flight_control_calls: list[tuple[Any, ...]] = []
        self.flight_lease_calls: list[tuple[Any, ...]] = []
        self.raise_on_write = raise_on_write

    def write_flight_control(self, *args: Any) -> None:
        if self.raise_on_write:
            raise AircraftLayerError("simulated send failure")
        self.flight_control_calls.append(args)

    def write_flight_lease(self, *args: Any) -> None:
        if self.raise_on_write:
            raise AircraftLayerError("simulated send failure")
        self.flight_lease_calls.append(args)


def _console(state: FlightControlState, *, overlay: bool = False) -> CrewConsole:
    """`overlay=True` (BL-16 Stage 2) sets `flight_authority_state.
    fd_mode = "m2"` -- `_apply_flight_control`'s own stale-transition
    guard reads `CrewConsole.flight_mode()` now, not `state.phase`."""
    console = CrewConsole(store=None)  # type: ignore[arg-type]
    console.flight_control_state = state
    if overlay:
        console.flight_authority_state = replace(
            console.flight_authority_state, fd_mode="m2"
        )
    return console


class TestApplyFlightControl:
    def test_a_take_transition_is_sent_and_cleared(self) -> None:
        client = _FakeAircraftClient()
        console = _console(FlightControlState(wire_seq=0))
        console.flight_control_transition = "take"

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        assert console.flight_control_transition is None
        assert len(client.flight_control_calls) == 1
        seq, cmd, _limits, goal = client.flight_control_calls[0]
        assert seq == 1
        assert cmd == "take"
        assert goal is None
        assert console.flight_control_state.wire_seq == 1

    def test_a_take_transition_sets_take_seq_to_the_actual_sent_wire_seq(
        self,
    ) -> None:
        """2026-11-19 mode 1 handover feedback: `Export.lua` echoes back
        the **wire** seq of the `take` message as `fc_take_seq`
        (`fc_pending_take_seq = seq` in `flight_control.lua`'s own
        `cmd == "take"` handler), never `FlightControlState.take_seq`'s
        own independent per-take counter. `take_controls` bumps that
        counter locally (here, 5 -> 6) with no knowledge of the wire --
        `decide_flight_control`'s ack comparison (`lua_take_seq ==
        take_seq`) can only ever match by the two counters' sheer luck,
        which is exactly why the existing pure-function tests (built
        with both values set equal by hand) never saw this. `take_seq`
        must come out equal to the *sent* wire seq (3, from
        `wire_seq=2 + 1`), not the independently-bumped 6, or every
        voice take times out even though Lua goes active."""
        client = _FakeAircraftClient()
        console = _console(FlightControlState(phase="TAKING", take_seq=6, wire_seq=2))
        console.flight_control_transition = "take"

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        seq, cmd, _limits, _goal = client.flight_control_calls[0]
        assert seq == 3
        assert cmd == "take"
        assert console.flight_control_state.take_seq == 3

    def test_a_release_transition_is_sent_and_cleared(self) -> None:
        client = _FakeAircraftClient()
        console = _console(FlightControlState(wire_seq=5))
        console.flight_control_transition = "release"

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        assert console.flight_control_transition is None
        seq, cmd, _limits, _goal = client.flight_control_calls[0]
        assert seq == 6
        assert cmd == "release"

    def test_a_goal_request_is_sent_with_its_fields_and_cleared(self) -> None:
        client = _FakeAircraftClient()
        console = _console(FlightControlState(phase="ACTIVE", wire_seq=0))
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=270.0
        )

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

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
        console = _console(FlightControlState(phase="ACTIVE", wire_seq=0))
        console.flight_control_transition = "take"
        console.flight_control_goal_transition = FlightControlGoalRequest(turn=1)

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        assert len(client.flight_control_calls) == 2
        seqs = [call[0] for call in client.flight_control_calls]
        assert seqs == [1, 2]
        assert console.flight_control_state.wire_seq == 2

    def test_a_system_release_is_sent_alone_and_a_queued_take_is_deferred(
        self,
    ) -> None:
        """review-handover-ack.md Required Fix -- what actually goes on
        the wire for the interleaving `test_flight_control.py`'s
        `test_a_same_poll_take_does_not_clobber_the_queued_release`
        reproduces at the belief level: the ack-timeout's self-queued
        release (`flight_control_system_release_pending`) must reach
        Lua before the same-poll player `take` that followed it --
        and that `take` must not simply be dropped, only deferred to
        the next poll's own `_apply_flight_control` call, once Lua has
        had this release to act on."""
        client = _FakeAircraftClient()
        console = _console(FlightControlState(phase="TAKING", wire_seq=10))
        console.flight_control_transition = "take"
        console.flight_control_system_release_pending = True

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        assert len(client.flight_control_calls) == 1
        seq, cmd, _limits, goal = client.flight_control_calls[0]
        assert seq == 11
        assert cmd == "release"
        assert goal is None
        assert console.flight_control_state.wire_seq == 11
        assert console.flight_control_system_release_pending is False
        # the player's "take" is neither sent nor discarded this poll --
        # it is still here, to be sent on the very next poll.
        assert console.flight_control_transition == "take"

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        assert len(client.flight_control_calls) == 2
        seq, cmd, _limits, goal = client.flight_control_calls[1]
        assert seq == 12
        assert cmd == "take"
        assert goal is None
        assert console.flight_control_transition is None
        assert console.flight_control_state.wire_seq == 12

    def test_a_goal_during_taking_is_held_not_sent_and_not_cleared(self) -> None:
        """review-m2.md Required Fix 1: a goal commanded in the one-
        frame `TAKING` window (the absolute-set `axes_*` actions gate on
        `has_controls` alone, which is already true here) must not be
        sent while `fc_law` cannot yet exist on the Lua side -- `Export.
        lua`'s `apply_goal_fields` only applies a goal once `fc_law is
        not None`, so sending it now would be silently dropped there,
        with no retry. It is kept pending instead, to be retried once
        Lua confirms `ACTIVE`."""
        client = _FakeAircraftClient()
        console = _console(FlightControlState(phase="TAKING", wire_seq=3))
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=315.0
        )

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        assert client.flight_control_calls == []
        assert console.flight_control_goal_transition == FlightControlGoalRequest(
            heading_deg=315.0
        )
        assert console.flight_control_state.wire_seq == 3

    def test_a_held_goal_is_sent_once_phase_becomes_active(self) -> None:
        """The other half of Required Fix 1: once Lua confirms `active`
        (`phase` moves from `TAKING` to `ACTIVE`), a goal held through
        the taking window is sent on the very next poll -- not lost."""
        client = _FakeAircraftClient()
        console = _console(FlightControlState(phase="TAKING", wire_seq=3))
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=315.0
        )
        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]
        assert client.flight_control_calls == []

        console.flight_control_state = replace(
            console.flight_control_state, phase="ACTIVE"
        )
        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        assert console.flight_control_goal_transition is None
        assert len(client.flight_control_calls) == 1
        seq, cmd, _limits, goal = client.flight_control_calls[0]
        assert seq == 4
        assert cmd == "goal"
        assert goal == {"heading_deg": 315.0}
        assert console.flight_control_state.wire_seq == 4

    def test_a_goal_held_through_a_failed_take_is_dropped_not_sent(self) -> None:
        """If the take itself fails (ack timeout moves `phase` from
        `TAKING` to `PILOT` before this poll runs), there is no law --
        and will be no law for this `take_seq` -- to apply the held
        goal to. It is dropped, not sent to a now-irrelevant take."""
        client = _FakeAircraftClient()
        console = _console(FlightControlState(phase="PILOT", wire_seq=3))
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=315.0
        )

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        assert client.flight_control_calls == []
        assert console.flight_control_goal_transition is None
        assert console.flight_control_state.wire_seq == 3

    def test_the_lease_resends_every_poll_regardless_of_phase(self) -> None:
        """BL-16 Stage 2 (`plans/flight-desired-state/plan.md`,
        refinement 3): the lease is no longer conditioned on `phase`/
        `unpark_take` (both gone from this check) -- it is sent every
        poll this function runs, on its own channel, carrying the given
        epoch and the `limits` bundle."""
        client = _FakeAircraftClient()
        console = _console(FlightControlState(wire_seq=0))

        _apply_flight_control(console, client, 7)  # type: ignore[arg-type]
        _apply_flight_control(console, client, 7)  # type: ignore[arg-type]

        assert len(client.flight_lease_calls) == 2
        for epoch, _limits in client.flight_lease_calls:
            assert epoch == 7

    def test_row_11_other_direction_a_stale_transition_is_discarded_while_overlay(
        self,
    ) -> None:
        """BL-16 mode 1's Co-moving row 11, the direction that is
        specific to `_apply_flight_control` itself (the ai_pilot_*
        direction is `test_body_ai_pilot_wheel.py`'s own test): an
        `axes_*` goal action spoken just before a park. **BL-16 Stage
        2**: the guard reads `flight_mode() == "overlay"` now (`fd_mode`
        via `flight_authority_state`), not `state.phase == "OVERLAY"`
        -- both one-shots must still be discarded unsent, with no
        `wire_seq` bump, whenever the mirror says mode 2 is flying."""
        client = _FakeAircraftClient()
        console = _console(FlightControlState(wire_seq=3), overlay=True)
        console.flight_control_transition = "take"
        console.flight_control_goal_transition = FlightControlGoalRequest(
            heading_deg=10.0
        )

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        assert console.flight_control_transition is None
        assert console.flight_control_goal_transition is None
        assert client.flight_control_calls == []
        assert console.flight_control_state.wire_seq == 3

    def test_a_send_failure_does_not_raise(self) -> None:
        client = _FakeAircraftClient(raise_on_write=True)
        console = _console(FlightControlState(wire_seq=0))
        console.flight_control_transition = "take"

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]  # must not raise

        assert console.flight_control_transition is None

    def test_a_body_layer_restart_reconciles_wire_seq_above_lua_last_cmd_seq(
        self,
    ) -> None:
        """security-m1-m2.md Finding A: a fresh process has `wire_seq ==
        0` (the dataclass default), but Lua's own `fc_last_cmd_seq` --
        mirrored here as `lua_last_cmd_seq` -- never resets, so a restart
        while mode 1 was active mid-sortie leaves it well above 0 (47,
        here, standing in for "whatever this DCS session already
        accepted"). Without reconciliation the next send would be
        `seq=1`, which `seq <= fc_last_cmd_seq` rejects forever -- this
        asserts the actual send lands at `48`, strictly above Lua's own
        counter, so Lua accepts it."""
        client = _FakeAircraftClient()
        console = _console(FlightControlState(wire_seq=0, lua_last_cmd_seq=47))
        console.flight_control_transition = "take"

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        seq, cmd, _limits, _goal = client.flight_control_calls[0]
        assert seq == 48
        assert cmd == "take"
        assert console.flight_control_state.wire_seq == 48

    def test_reconciliation_never_lowers_wire_seq_below_its_own_history(
        self,
    ) -> None:
        """The mirror update that refreshes `lua_last_cmd_seq` each poll
        lags one poll behind whatever this process itself last sent
        (Lua processes the write before body-layer's own `GET /flight_
        control/latest` poll catches up to it) -- reconciliation must
        never *lower* `wire_seq`, or a genuine duplicate/stale resend
        within this same session would start being accepted again."""
        client = _FakeAircraftClient()
        console = _console(FlightControlState(wire_seq=10, lua_last_cmd_seq=3))
        console.flight_control_transition = "release"

        _apply_flight_control(console, client, 1)  # type: ignore[arg-type]

        seq, _cmd, _limits, _goal = client.flight_control_calls[0]
        assert seq == 11
        assert console.flight_control_state.wire_seq == 11
