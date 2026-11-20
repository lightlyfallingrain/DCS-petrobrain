"""`body._apply_ai_pilot_wheel_goal` -- BL-16 mode 2 Stage P2a/P2b/P3+P4
(`plans/flight-control/plan.md`, "Stage P2 ready to build", "Revised
2026-11-18 -- Stages P3+P4 ready to build"): the glue between
`CrewConsole`'s one-shot transition fields and the goal-channel/CBTM
wire writes (`AircraftLayerClient.write_ai_pilot_goal`). The rotation
mechanism/actions themselves are `belief.ai_pilot_wheel`'s own tested
surface (`test_ai_pilot_wheel.py`); these tests exercise only the
composition `body.py` adds on top: applying a transition, running
`decide_ai_pilot_wheel`, and deciding whether/what to send.

**Review fix (`plans/flight-control/review-p3p4.md` Required Fix 1):**
the Stage P3+P4 classes below (`TestCbtmTransitions`,
`TestFlightCommandEndsAlignment`, `TestLevelFlightAbortRecovery`,
`TestRecoveryTriggerWiring`) cover the composition the pure-function
tests in `test_ai_pilot_wheel.py` cannot reach: a CBTM one-shot
transition actually landing on `align_phase`/`cbtm_action_sent` and a
correctly-bumped `cbtm_seq` wire send, F-P6's "any voice command ends
alignment" branch, the F-P8/Q0 `level_flight` abort, and `agl_m`/
`ias_kmh`/`payload_count_dropped` actually reaching `decide_ai_pilot_
wheel` from `runner`'s own live state rather than a test passing them
in directly.

**Every CBTM-transition call below also sends an ordinary goal
message** -- a pre-existing behaviour this round found, not introduced
by it (`_apply_ai_pilot_wheel_goal` always writes `goal=goal` back onto
`runner.parked_flight_state` before computing `final_goal`, so a fresh,
all-`None` `AiPilotWheelGoal()` differs from `runner.ai_pilot_goal_
last_sent_seq`'s initial `None` and is sent once, harmlessly, on the
first poll of any activation with no goal yet). Tests below that care
only about the CBTM send filter `client.ai_pilot_goal_calls` down to
the one entry whose `cbtm_action` (index 8) is not `None`, rather than
asserting a single-call count that this pre-existing behaviour would
break."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from belief.ai_pilot_wheel import (
    AiPilotGoalRequest,
    AiPilotWheelGoal,
    FlightSnapshot,
    ParkedFlightState,
)
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from belief.flight_authority import PendingFlightReadback
from body import ConsolePerceptionRunner, _apply_ai_pilot_wheel_goal
from perception.source import OwnshipState


class _FakeAircraftClient:
    def __init__(self) -> None:
        self.ai_pilot_goal_calls: list[tuple[Any, ...]] = []
        self.flight_calls: list[tuple[Any, ...]] = []

    def write_ai_pilot_goal(self, *args: Any) -> None:
        self.ai_pilot_goal_calls.append(args)

    def write_flight(self, *args: Any) -> None:
        """BL-16 Stage 3's own dual-write (`plans/flight-desired-state/
        plan.md`, "Every mode-2 voice goal also writes a set") -- a
        `set` request alongside the `ai_pilot_goal` send above, recorded
        but not otherwise asserted on by most tests in this file."""
        self.flight_calls.append(args)


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

    def test_the_dual_write_s_staged_readback_is_queued_against_its_seq(
        self,
    ) -> None:
        """BL-16 Stage 3b (section 3a, U1) -- the ordinary mode-2 voice
        goal's own readback (staged by `handle_command`) is paired with
        the exact `seq` the dual-write onto the numbered `flight`
        channel just sent, so it waits for that `seq`'s own `fd_acks`
        entry rather than speaking immediately."""
        runner, client = _runner()
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_goal_transition = AiPilotGoalRequest(
            param="heading", heading_deg=90.0
        )
        console.pending_flight_readback_lines = ["Heading 090."]

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        assert console.pending_flight_readback_lines is None
        assert len(client.flight_calls) == 1
        dual_write_seq = client.flight_calls[0][1]
        assert console.pending_flight_readbacks == [
            PendingFlightReadback(
                seq=dual_write_seq,
                lines=("Heading 090.",),
                sent_at_sim=runner.last_t_sim,
            )
        ]

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

    def test_unparking_also_clears_a_captured_break_entry_heading(self) -> None:
        """Mode-1 batch, Decision 32 -- a stale break entry heading
        from a previous session must not survive into a later unpark,
        the same leak class `cbtm_action_sent` itself already guards
        against."""
        runner, client = _runner(
            cbtm_action_sent="break_left",
            cbtm_break_entry_heading_deg=123.0,
            parked_active=False,
        )
        console = CrewConsole(store=ContactStore())

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        assert runner.parked_flight_state.cbtm_action_sent is None
        assert runner.parked_flight_state.cbtm_break_entry_heading_deg is None

    def test_unparking_clears_every_stranded_ai_pilot_one_shot(self) -> None:
        """BL-16 mode 1's Co-moving row 11 fix (`plans/flight-control/
        plan.md`, "Revised 2026-11-18"): previously the three `ai_
        pilot_*` one-shot transition fields persisted while unparked
        (this function returned before ever reaching their clear) --
        harmless while `CrewState.has_controls == parked_active` (the
        gate refused every flight action while unparked, so nothing
        could ever set one), but a latent leak once mode 1 widens `has_
        controls`: an overlay command spoken just before an unpark is
        now a realistic way to strand one, to fire on the next park.
        All three must be `None`/`False` after this call, not just the
        `goal`/`ai_pilot_goal_last_sent_seq` the pre-existing test above
        already covers."""
        runner, client = _runner(parked_active=False)
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_goal_transition = AiPilotGoalRequest(
            param="heading", heading_deg=90.0
        )
        console.ai_pilot_level_flight_transition = True
        console.ai_pilot_hvrt_transition = "left"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        assert console.ai_pilot_goal_transition is None
        assert console.ai_pilot_level_flight_transition is False
        assert console.ai_pilot_hvrt_transition is None
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


class TestHvrtArbitration:
    """Review fix (BL-16 Stage P2): the goal channel vs. HVRT translate
    arbitration end to end through `_apply_ai_pilot_wheel_goal` -- the
    required test sequence named in the review-fix round."""

    def test_a_goal_active_then_left_stops_the_goal_and_runs_the_translate(
        self,
    ) -> None:
        goal = AiPilotWheelGoal(
            altitude_target_m=300.0,
            altitude_target_ref="barometric",
            active_param="altitude",
            active_since_sim=0.0,
            goal_seq=1,
        )
        runner, client = _runner(goal=goal)
        runner.ai_pilot_goal_last_sent_seq = 1
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_hvrt_transition = "left"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        new_goal = runner.parked_flight_state.goal
        assert new_goal is not None
        # The goal keeps its target and queue position -- paused, not
        # dropped (the main loop's own "nothing lost" rule).
        assert new_goal.active_param == "altitude"
        assert new_goal.altitude_target_m == 300.0
        assert new_goal.hvrt_direction == "left"
        assert len(client.ai_pilot_goal_calls) == 1
        sent = client.ai_pilot_goal_calls[0]
        # (goal_seq, param, heading, altitude, altitude_ref, speed, hvrt_direction)
        assert sent[1] is None  # `param` nulled on the wire -- the goal presses stop
        assert sent[6] == "left"  # the translate runs

    def test_hold_resumes_the_goal(self) -> None:
        goal = AiPilotWheelGoal(
            altitude_target_m=300.0,
            altitude_target_ref="barometric",
            active_param="altitude",
            active_since_sim=0.0,
            goal_seq=2,
            hvrt_direction="left",
        )
        runner, client = _runner(goal=goal)
        runner.ai_pilot_goal_last_sent_seq = 2
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_hvrt_transition = "hold"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        new_goal = runner.parked_flight_state.goal
        assert new_goal is not None
        assert new_goal.hvrt_direction is None
        assert new_goal.active_param == "altitude"
        assert len(client.ai_pilot_goal_calls) == 1
        sent = client.ai_pilot_goal_calls[0]
        assert sent[1] == "altitude"  # the goal resumes on the wire
        assert sent[6] is None

    def test_a_translate_active_then_a_new_altitude_goal_releases_it(self) -> None:
        goal = AiPilotWheelGoal(hvrt_direction="left", goal_seq=1)
        runner, client = _runner(goal=goal)
        runner.ai_pilot_goal_last_sent_seq = 1
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_goal_transition = AiPilotGoalRequest(
            param="altitude", altitude_m=300.0, altitude_ref="barometric"
        )

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        new_goal = runner.parked_flight_state.goal
        assert new_goal is not None
        assert new_goal.hvrt_direction is None
        assert new_goal.active_param == "altitude"
        assert len(client.ai_pilot_goal_calls) == 1
        sent = client.ai_pilot_goal_calls[0]
        assert sent[1] == "altitude"  # the goal runs
        assert sent[6] is None  # the translate is released on the wire


def _cbtm_send(client: _FakeAircraftClient) -> tuple[Any, ...]:
    """The one CBTM-carrying wire send among `client.ai_pilot_goal_
    calls` (`cbtm_action`, index 8, not `None`) -- see this module's own
    docstring for why a plain ordinary-goal send is also present and
    must not be mistaken for it."""
    cbtm_calls = [
        call
        for call in client.ai_pilot_goal_calls
        if len(call) > 8 and call[8] is not None
    ]
    assert len(cbtm_calls) == 1
    return cbtm_calls[0]


class TestCbtmTransitions:
    """Review fix (`plans/flight-control/review-p3p4.md` Required Fix 1):
    each of the four `cbtm_*` one-shot transitions actually reaching
    `align_phase`/`cbtm_action_sent` and a correctly-bumped `cbtm_seq`
    wire send, through `_apply_ai_pilot_wheel_goal` itself -- not just
    the underlying `belief.ai_pilot_wheel.cbtm_apply_align`/`cbtm_apply_
    align_for_launch` pure functions (`test_ai_pilot_wheel.py`'s own
    surface)."""

    def test_align_starts_a_plain_alignment_and_sends_cbtm_seq_1(self) -> None:
        runner, client = _runner()
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_cbtm_transition = "align"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        state = runner.parked_flight_state
        assert state.align_phase == "aligning"
        assert state.cbtm_action_sent == "align"
        assert console.ai_pilot_cbtm_transition is None
        assert runner.ai_pilot_cbtm_last_sent_seq == 1
        sent = _cbtm_send(client)
        assert sent[8] == "align"
        assert sent[9] == 1

    def test_align_for_launch_captures_a_snapshot_and_sends_cbtm_seq_1(self) -> None:
        runner, client = _runner(
            held_heading=90.0,
            held_altitude=300.0,
            held_altitude_ref="B",
            held_speed=150.0,
        )
        runner.last_ownship_state = OwnshipState(
            t_sim=10.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0, alt_agl_m=300.0
        )
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_cbtm_transition = "align_for_launch"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        state = runner.parked_flight_state
        assert state.align_phase == "launch_aligned"
        assert state.pre_align_snapshot == FlightSnapshot(
            heading_deg=90.0,
            altitude_m=300.0,
            altitude_ref="barometric",
            speed_kmh=150.0,
            agl_m=300.0,
        )
        assert state.cbtm_action_sent == "align_for_launch"
        sent = _cbtm_send(client)
        assert sent[8] == "align_for_launch"
        assert sent[9] == 1

    def test_break_left_is_recorded_and_ends_an_outstanding_alignment(self) -> None:
        """The break transition itself carries no `align_phase`
        mutation of its own to apply -- F-P7's own heading-drop/align-
        clear logic lives in `decide_ai_pilot_wheel`, keyed off `cbtm_
        action_sent`. But `_apply_ai_pilot_wheel_goal` runs `decide_ai_
        pilot_wheel` every call, in the same poll as this transition is
        applied, so the end-to-end effect through this one function is
        still `align_phase` dropping to `"none"` here -- the pure-
        function split is `test_ai_pilot_wheel.py`'s own `TestDecide
        AiPilotWheelCbtm`'s concern, not asserted a second time here."""
        runner, client = _runner(align_phase="aligning")
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_cbtm_transition = "break_left"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        state = runner.parked_flight_state
        assert state.align_phase == "none"
        assert state.pre_align_snapshot is None
        assert state.cbtm_action_sent == "break_left"
        sent = _cbtm_send(client)
        assert sent[8] == "break_left"
        assert sent[9] == 1

    def test_break_away_is_recorded_and_sent(self) -> None:
        runner, client = _runner()
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_cbtm_transition = "break_away"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        state = runner.parked_flight_state
        assert state.cbtm_action_sent == "break_away"
        sent = _cbtm_send(client)
        assert sent[8] == "break_away"
        assert sent[9] == 1

    def test_break_left_captures_the_held_heading_at_the_press(self) -> None:
        """Mode-1 batch, Decision 32 -- the held heading right at this
        instant (before anything else this poll can move it) is
        captured onto `cbtm_break_entry_heading_deg`, for a later
        unpark-take to seed its own heading goal from."""
        runner, client = _runner(held_heading=123.0)
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_cbtm_transition = "break_left"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        assert runner.parked_flight_state.cbtm_break_entry_heading_deg == 123.0

    def test_align_does_not_capture_an_entry_heading(self) -> None:
        """Only the three break kinds capture one -- `align`/`align_
        for_launch` leave it untouched (`None` here since nothing has
        set it yet)."""
        runner, client = _runner(held_heading=123.0)
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_cbtm_transition = "align"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        assert runner.parked_flight_state.cbtm_break_entry_heading_deg is None

    def test_a_second_cbtm_transition_bumps_its_own_seq_space_again(self) -> None:
        """`cbtm_seq` is its own distinct sequence space, never `goal_
        seq` -- a second CBTM trigger bumps from the last *CBTM* seq
        sent, independent of whatever `goal_seq` is doing."""
        runner, client = _runner()
        runner.ai_pilot_cbtm_last_sent_seq = 5
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_cbtm_transition = "break_right"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        assert runner.ai_pilot_cbtm_last_sent_seq == 6
        sent = _cbtm_send(client)
        assert sent[8] == "break_right"
        assert sent[9] == 6


class TestLatestCommandAlwaysWinsAgainstABreak:
    """2026-11-20 rework (`docs/acceptance/2026-11-20-sortie-feedback.md`,
    "Mode 2 root cause and the 'latest wins' direction"): the two
    end-to-end cases through `_apply_ai_pilot_wheel_goal` itself, each
    simulating a prior poll's own break/heading via `_runner`'s state
    fields rather than two real calls (the same pattern `test_a_second_
    cbtm_transition_bumps_its_own_seq_space_again` above already uses
    for "something already happened on an earlier poll")."""

    def test_a_heading_commanded_after_an_already_running_break_is_sent(self) -> None:
        """A break was sent on an earlier poll (`cbtm_action_order=1`,
        still `lua_cbtm_status="running"` -- it has not finished) and
        now the player commands a heading. The goal must be sent on the
        wire this poll, not dropped -- the user's own rule, "latest
        player command always wins," applies even while the break is
        still running."""
        runner, client = _runner(
            cbtm_action_sent="break_left",
            cbtm_action_order=1,
            command_order_seq=1,
            lua_cbtm_status="running",
        )
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_goal_transition = AiPilotGoalRequest(
            param="heading", heading_deg=250.0
        )

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        state = runner.parked_flight_state
        assert state.goal is not None
        assert state.goal.heading_target_deg == 250.0
        assert state.goal.active_param == "heading"
        assert runner.ai_pilot_goal_last_sent_seq is not None
        sent = client.ai_pilot_goal_calls[-1]
        assert sent[1] == "heading"
        assert sent[2] == 250.0

    def test_a_break_drops_a_heading_commanded_on_an_earlier_poll(self) -> None:
        """A heading was commanded on an earlier poll
        (`heading_requested_order=1`) and now the player commands a
        break. The outstanding heading must be dropped -- F-P7's
        original rule, unchanged by the rework: a break supersedes any
        heading goal commanded *before* it."""
        goal = AiPilotWheelGoal(
            heading_target_deg=250.0,
            active_param="heading",
            active_since_sim=5.0,
            heading_requested_order=1,
        )
        runner, client = _runner(goal=goal, command_order_seq=1)
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_cbtm_transition = "break_right"

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        state = runner.parked_flight_state
        assert state.goal is not None
        assert state.goal.heading_target_deg is None
        assert state.goal.active_param is None
        assert state.cbtm_action_sent == "break_right"


class TestFlightCommandEndsAlignment:
    """F-P6 (`plans/flight-control/plan.md`, "Stage P3+P4 ready to
    build"): a fresh voice heading/altitude/speed command always ends
    whichever `align_phase` is running (`"aligning"`/`"launch_aligned"`,
    never `"recovering"` -- that case is `TestApplyAiPilotWheelGoal`'s
    own "latest wins" path, unaffected by this branch) and is always
    flown, never queued behind it."""

    def test_a_heading_command_during_aligning_ends_it_and_still_flies(self) -> None:
        runner, client = _runner(align_phase="aligning")
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_goal_transition = AiPilotGoalRequest(
            param="heading", heading_deg=270.0
        )

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        state = runner.parked_flight_state
        assert state.align_phase == "none"
        assert state.pre_align_snapshot is None
        goal = state.goal
        assert goal is not None
        assert goal.heading_target_deg == 270.0
        assert goal.active_param == "heading"
        assert any(
            call[1] == "heading" and call[2] == 270.0
            for call in client.ai_pilot_goal_calls
        )

    def test_an_altitude_command_during_launch_aligned_ends_it_and_keeps_the_snapshot_cleared(
        self,
    ) -> None:
        """While `"launch_aligned"` with a captured snapshot, a fresh
        altitude command still ends the alignment and drops the
        snapshot outright -- the command is flown normally, not
        absorbed into recovery (that only happens via `level_flight`'s
        own `"recovering"` path, `TestLevelFlightAbortRecovery` below)."""
        snapshot = FlightSnapshot(
            heading_deg=90.0,
            altitude_m=300.0,
            altitude_ref="barometric",
            speed_kmh=150.0,
            agl_m=300.0,
        )
        runner, client = _runner(
            align_phase="launch_aligned", pre_align_snapshot=snapshot
        )
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_goal_transition = AiPilotGoalRequest(
            param="altitude", altitude_m=500.0, altitude_ref="barometric"
        )

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        state = runner.parked_flight_state
        assert state.align_phase == "none"
        assert state.pre_align_snapshot is None
        goal = state.goal
        assert goal is not None
        assert goal.altitude_target_m == 500.0
        assert goal.active_param == "altitude"

    def test_a_speed_command_during_recovering_does_not_end_recovery(self) -> None:
        """F-P6 deliberately excludes `"recovering"` -- a fresh command
        for one of its own two recovering parameters just replaces that
        parameter's target via the ordinary "latest wins" path (Q6),
        and `align_phase` stays `"recovering"`."""
        snapshot = FlightSnapshot(
            heading_deg=90.0,
            altitude_m=300.0,
            altitude_ref="barometric",
            speed_kmh=150.0,
            agl_m=300.0,
        )
        runner, client = _runner(align_phase="recovering", pre_align_snapshot=snapshot)
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_goal_transition = AiPilotGoalRequest(
            param="speed", speed_kmh=200.0
        )

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        state = runner.parked_flight_state
        assert state.align_phase == "recovering"
        assert state.pre_align_snapshot == snapshot


class TestLevelFlightAbortRecovery:
    """F-P8/Q0 (`plans/flight-control/plan.md`, "Follow-up on the goal
    check's own open assumptions"): "level off"/"level flight" spoken
    while `"launch_aligned"` with a captured snapshot enters
    `"recovering"` and seeds the recovery queue from the snapshot
    (`seed_recovery_goal`), heading frozen at its current *held* value
    -- never the snapshot's own heading, matching the reviewed "keep
    aligned heading" reading (Fix 2) extended to this abort path."""

    def test_launch_aligned_abort_enters_recovering_seeded_from_the_snapshot(
        self,
    ) -> None:
        snapshot = FlightSnapshot(
            heading_deg=90.0,
            altitude_m=300.0,
            altitude_ref="barometric",
            speed_kmh=150.0,
            agl_m=1000.0,
        )
        runner, client = _runner(
            align_phase="launch_aligned",
            pre_align_snapshot=snapshot,
            held_heading=200.0,
            held_altitude=900.0,
            held_speed=400.0,
        )
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_level_flight_transition = True

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        state = runner.parked_flight_state
        assert state.align_phase == "recovering"
        assert state.pre_align_snapshot == snapshot  # kept, for the end condition
        assert console.ai_pilot_level_flight_transition is False
        goal = state.goal
        assert goal is not None
        # Heading frozen at the *current held* value, not the snapshot's.
        assert goal.heading_target_deg == 200.0
        # Altitude/speed jump straight to the snapshot's own targets.
        assert goal.altitude_target_m == 300.0
        assert goal.altitude_target_ref == "barometric"
        assert goal.speed_target_kmh == 150.0
        assert goal.active_param == "altitude"
        assert "speed" in goal.pending_order

    def test_aligning_abort_simply_ends_with_nothing_to_recover(self) -> None:
        """Q1's "nothing to recover from" reasoning: while `"aligning"`
        (no snapshot ever captured), `level_flight`'s abort just falls
        back to `"none"` and the ordinary freeze-at-held-values applies,
        same as the pre-existing non-CBTM `level_flight` behaviour."""
        runner, client = _runner(
            align_phase="aligning",
            held_heading=200.0,
            held_altitude=900.0,
            held_speed=150.0,
        )
        console = CrewConsole(store=ContactStore())
        console.ai_pilot_level_flight_transition = True

        _apply_ai_pilot_wheel_goal(runner, console, client)  # type: ignore[arg-type]

        state = runner.parked_flight_state
        assert state.align_phase == "none"
        assert state.pre_align_snapshot is None
        goal = state.goal
        assert goal is not None
        assert goal.heading_target_deg == 200.0
        assert goal.altitude_target_m == 900.0
        assert goal.speed_target_kmh == 150.0


class TestRecoveryTriggerWiring:
    """Required Fix 1's fourth bullet: `decide_ai_pilot_wheel`'s three
    recovery triggers (payload drop, the AGL-relative floor, the IAS
    ceiling) are actually fed from `runner`'s own live state by `_apply_
    ai_pilot_wheel_goal` -- `agl_m` from `runner.last_ownship_state.alt_
    agl_m`, `ias_kmh` from `runner.last_ias_kmh`, and `payload_count_
    dropped` from comparing the caller-supplied `previous_payload_
    counts` against `runner.parked_flight_state.payload_station_counts_
    last_seen` -- not just `test_ai_pilot_wheel.py`'s own direct-argument
    unit tests of the pure function."""

    _SNAPSHOT = FlightSnapshot(
        heading_deg=90.0,
        altitude_m=300.0,
        altitude_ref="barometric",
        speed_kmh=150.0,
        agl_m=1000.0,
    )

    def test_a_payload_drop_computed_from_the_previous_poll_triggers_recovery(
        self,
    ) -> None:
        runner, client = _runner(
            align_phase="launch_aligned",
            pre_align_snapshot=self._SNAPSHOT,
            payload_station_counts_last_seen={0: 1},
        )

        _apply_ai_pilot_wheel_goal(
            runner,
            CrewConsole(store=ContactStore()),
            client,
            previous_payload_counts={0: 2},
        )

        assert runner.parked_flight_state.align_phase == "recovering"

    def test_no_drop_when_nothing_decreased_leaves_launch_aligned(self) -> None:
        runner, client = _runner(
            align_phase="launch_aligned",
            pre_align_snapshot=self._SNAPSHOT,
            payload_station_counts_last_seen={0: 1},
        )

        _apply_ai_pilot_wheel_goal(
            runner,
            CrewConsole(store=ContactStore()),
            client,
            previous_payload_counts={0: 1},
        )

        assert runner.parked_flight_state.align_phase == "launch_aligned"

    def test_agl_from_last_ownship_state_crossing_the_floor_triggers_recovery(
        self,
    ) -> None:
        runner, client = _runner(
            align_phase="launch_aligned", pre_align_snapshot=self._SNAPSHOT
        )
        runner.last_ownship_state = OwnshipState(
            t_sim=10.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0, alt_agl_m=950.0
        )

        _apply_ai_pilot_wheel_goal(runner, CrewConsole(store=ContactStore()), client)

        assert runner.parked_flight_state.align_phase == "recovering"

    def test_agl_from_last_ownship_state_still_above_the_floor_does_not_trigger(
        self,
    ) -> None:
        runner, client = _runner(
            align_phase="launch_aligned", pre_align_snapshot=self._SNAPSHOT
        )
        runner.last_ownship_state = OwnshipState(
            t_sim=10.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0, alt_agl_m=990.0
        )

        _apply_ai_pilot_wheel_goal(runner, CrewConsole(store=ContactStore()), client)

        assert runner.parked_flight_state.align_phase == "launch_aligned"

    def test_ias_from_last_ias_kmh_crossing_the_ceiling_triggers_recovery(self) -> None:
        runner, client = _runner(
            align_phase="launch_aligned", pre_align_snapshot=self._SNAPSHOT
        )
        runner.last_ias_kmh = 320.0

        _apply_ai_pilot_wheel_goal(runner, CrewConsole(store=ContactStore()), client)

        assert runner.parked_flight_state.align_phase == "recovering"

    def test_ias_from_last_ias_kmh_below_the_ceiling_does_not_trigger(self) -> None:
        runner, client = _runner(
            align_phase="launch_aligned", pre_align_snapshot=self._SNAPSHOT
        )
        runner.last_ias_kmh = 150.0

        _apply_ai_pilot_wheel_goal(runner, CrewConsole(store=ContactStore()), client)

        assert runner.parked_flight_state.align_phase == "launch_aligned"
