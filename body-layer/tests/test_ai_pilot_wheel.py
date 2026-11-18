"""Tests for `belief.ai_pilot_wheel` -- BL-16 mode 2 Stage P1 (`plans/
flight-control/plan.md`, "Revised 2026-11-15") and Stage P2a/P2b
("Revised 2026-11-16 -- Stage P2 ready to build"). `advance_parked_flight_
state` is exercised against a real loopback `http.server` instance via a
real `AircraftLayerClient`, same posture as `test_aircraft_client.py`'s
own convention (and the project's stated "no mocked `urllib`" rule) --
not a mocked client double. The Stage P2 goal-channel functions below
(`request_goal`/the three actions/`decide_ai_pilot_wheel`) are pure, so
they are exercised directly against `AiPilotWheelGoal`/`ParkedFlightState`
values, no server needed."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar

import pytest

from aircraft_client import AircraftLayerClient
from belief.ai_pilot_wheel import (
    AI_PILOT_GOAL_SLICE_S,
    AI_PILOT_RECOVER_AGL_DROP_M,
    AI_PILOT_RECOVER_IAS_CEILING_KMH,
    AI_PILOT_SPEED_MAX_SENTINEL_KMH,
    AiPilotGoalRequest,
    AiPilotWheelGoal,
    FlightSnapshot,
    ParkedFlightState,
    advance_parked_flight_state,
    altitude_ref_from_letter,
    capture_flight_snapshot,
    cbtm_apply_align,
    cbtm_apply_align_for_launch,
    clear_hvrt_direction,
    decide_ai_pilot_wheel,
    goal_param_for_wire,
    nearest_speed_step,
    payload_count_dropped,
    request_goal,
    resolve_altitude_reference,
    seat_change,
    seed_recovery_goal,
    set_hvrt_direction,
    set_parked_altitude,
    set_parked_heading,
    set_parked_speed,
    step_speed,
)


def _make_handler(body: object) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/ai_pilot_wheel/latest":
                self._respond(200, body)
            else:
                self._respond(404, {"error": "not found"})

        def _respond(self, status: int, payload_obj: object) -> None:
            payload = json.dumps(payload_obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return _Handler


def _server(body: object) -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(body))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


@pytest.fixture
def server_with_sample() -> Iterator[str]:
    body: dict[str, Any] = {
        "t": 123.5,
        "received_wall_clock_s": 1000.0,
        "apw_parked_active": True,
        "apw_mode_text": "FLT",
        "apw_course_text": "71",
        "apw_alt_text": "196",
        "apw_alt_add_text": "R",
        "apw_speed_text": "60",
        "apw_last_press": "altitude_nudge_up",
    }
    yield from _server(body)


@pytest.fixture
def server_with_null() -> Iterator[str]:
    yield from _server(None)


class TestAdvanceParkedFlightState:
    def test_a_sample_is_parsed_into_the_state(self, server_with_sample: str) -> None:
        client = AircraftLayerClient(base_url=server_with_sample)
        state = advance_parked_flight_state(ParkedFlightState(), client)

        assert state.parked_active is True
        assert state.ai_mode == "FLT"
        assert state.held_heading == pytest.approx(71.0)
        assert state.held_altitude == pytest.approx(196.0)
        assert state.held_altitude_ref == "R"
        assert state.held_speed == pytest.approx(60.0)
        assert state.last_press == "altitude_nudge_up"
        # `server_with_sample`'s own body predates the "Revised
        # 2026-11-16" diagnostic fields -- absent, not an error, same
        # "missing is None" posture every optional field here already has.
        assert state.raw_arg_852 is None
        assert state.raw_arg_952 is None
        assert state.takeover_stage is None
        assert state.correction_path is None
        assert state.lua_goal_progress is None
        assert state.lua_goal_seq is None

    def test_the_goal_progress_fields_are_parsed_through(self) -> None:
        body: dict[str, Any] = {
            "t": 123.5,
            "received_wall_clock_s": 1000.0,
            "apw_parked_active": True,
            "apw_goal_progress": "mode_blocked",
            "apw_goal_seq": 7,
        }
        httpd = HTTPServer(("127.0.0.1", 0), _make_handler(body))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            client = AircraftLayerClient(
                base_url=f"http://127.0.0.1:{httpd.server_port}"
            )
            state = advance_parked_flight_state(ParkedFlightState(), client)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

        assert state.lua_goal_progress == "mode_blocked"
        assert state.lua_goal_seq == 7

    def test_the_takeover_diagnostic_fields_are_parsed_through(self) -> None:
        body: dict[str, Any] = {
            "t": 123.5,
            "received_wall_clock_s": 1000.0,
            "apw_parked_active": True,
            "apw_mode_text": "FLT",
            "apw_course_text": "71",
            "apw_alt_text": "1080",
            "apw_alt_add_text": "B",
            "apw_speed_text": "60",
            "apw_last_press": "correction_hold_phase2",
            "apw_arg852": 0.97,
            "apw_arg952": 0.03,
            "apw_takeover_stage": "correcting_altitude",
            "apw_correction_path": "hold",
        }
        httpd = HTTPServer(("127.0.0.1", 0), _make_handler(body))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            client = AircraftLayerClient(
                base_url=f"http://127.0.0.1:{httpd.server_port}"
            )
            state = advance_parked_flight_state(ParkedFlightState(), client)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

        assert state.raw_arg_852 == pytest.approx(0.97)
        assert state.raw_arg_952 == pytest.approx(0.03)
        assert state.takeover_stage == "correcting_altitude"
        assert state.correction_path == "hold"

    def test_a_boolean_arg_value_is_never_treated_as_a_number(self) -> None:
        """`isinstance(True, int)` is true in Python -- `_as_optional_
        float` must exclude `bool` explicitly or a malformed `true`/
        `false` on the wire would silently read back as `1.0`/`0.0`."""
        body: dict[str, Any] = {
            "t": 1.0,
            "received_wall_clock_s": 2.0,
            "apw_parked_active": True,
            "apw_arg852": True,
        }
        httpd = HTTPServer(("127.0.0.1", 0), _make_handler(body))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            client = AircraftLayerClient(
                base_url=f"http://127.0.0.1:{httpd.server_port}"
            )
            state = advance_parked_flight_state(ParkedFlightState(), client)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

        assert state.raw_arg_852 is None

    def test_no_sample_yet_leaves_state_unchanged(self, server_with_null: str) -> None:
        client = AircraftLayerClient(base_url=server_with_null)
        previous = ParkedFlightState(parked_active=True, ai_mode="HVR")

        state = advance_parked_flight_state(previous, client)

        assert state is previous

    def test_unparked_and_empty_overlay_fields_round_trip_as_none(
        self,
    ) -> None:
        body: dict[str, Any] = {
            "t": 1.0,
            "received_wall_clock_s": 2.0,
            "apw_parked_active": False,
            "apw_mode_text": None,
            "apw_course_text": None,
            "apw_alt_text": None,
            "apw_alt_add_text": None,
            "apw_speed_text": None,
            "apw_last_press": None,
        }
        httpd = HTTPServer(("127.0.0.1", 0), _make_handler(body))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            client = AircraftLayerClient(
                base_url=f"http://127.0.0.1:{httpd.server_port}"
            )
            state = advance_parked_flight_state(ParkedFlightState(), client)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

        assert state.parked_active is False
        assert state.ai_mode is None
        assert state.held_heading is None
        assert state.held_altitude is None

    def test_a_non_numeric_overlay_field_parses_as_none_not_an_error(
        self,
    ) -> None:
        """`course_text`/`alt_text`/`speed_text` are `Export.lua`'s own
        passthrough of whatever the overlay currently shows -- a
        transiently non-numeric reading (a stale/partial frame) must
        degrade to `None`, never raise, same posture as every other
        belief-side parse in this layer."""
        body: dict[str, Any] = {
            "t": 1.0,
            "received_wall_clock_s": 2.0,
            "apw_parked_active": True,
            "apw_mode_text": "FLT",
            "apw_course_text": "not-a-number",
            "apw_alt_text": None,
            "apw_alt_add_text": None,
            "apw_speed_text": None,
            "apw_last_press": None,
        }
        httpd = HTTPServer(("127.0.0.1", 0), _make_handler(body))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            client = AircraftLayerClient(
                base_url=f"http://127.0.0.1:{httpd.server_port}"
            )
            state = advance_parked_flight_state(ParkedFlightState(), client)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

        assert state.held_heading is None

    def test_later_stage_fields_are_carried_through_unchanged(
        self, server_with_sample: str
    ) -> None:
        """P2-P4's own fields (`goal`/`align_phase`/`pre_align_snapshot`)
        have no writer yet this stage -- `advance_parked_flight_state`
        must not reset them to their declared defaults on every poll."""
        client = AircraftLayerClient(base_url=server_with_sample)
        previous = ParkedFlightState(align_phase="aligning", goal="placeholder")

        state = advance_parked_flight_state(previous, client)

        assert state.align_phase == "aligning"
        assert state.goal == "placeholder"


class TestRequestGoal:
    """`request_goal`'s own rotation rule (plan, "`AiPilotWheelGoal` --
    the new co-moving state, and the rotation rule")."""

    def test_a_first_target_queues_at_the_back(self) -> None:
        goal = request_goal(
            AiPilotWheelGoal(), "heading", 10.0, heading_target_deg=90.0
        )
        assert goal.heading_target_deg == 90.0
        assert goal.pending_order == ("heading",)
        assert goal.active_param is None
        assert goal.goal_seq == 0

    def test_a_second_target_queues_behind_the_first_fifo(self) -> None:
        goal = request_goal(
            AiPilotWheelGoal(), "heading", 10.0, heading_target_deg=90.0
        )
        goal = request_goal(goal, "speed", 10.0, speed_target_kmh=200.0)
        assert goal.pending_order == ("heading", "speed")

    def test_replacing_a_queued_targets_value_does_not_move_its_queue_position(
        self,
    ) -> None:
        goal = request_goal(
            AiPilotWheelGoal(), "heading", 10.0, heading_target_deg=90.0
        )
        goal = request_goal(goal, "speed", 10.0, speed_target_kmh=200.0)
        goal = request_goal(goal, "heading", 20.0, heading_target_deg=180.0)
        assert goal.heading_target_deg == 180.0
        assert goal.pending_order == ("heading", "speed")
        # Not sent immediately -- it is still waiting its turn, not active.
        assert goal.goal_seq == 0

    def test_replacing_the_active_parameters_value_preempts_immediately(
        self,
    ) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0, active_param="heading", active_since_sim=10.0
        )
        goal = request_goal(goal, "heading", 20.0, heading_target_deg=270.0)
        assert goal.heading_target_deg == 270.0
        assert goal.active_param == "heading"
        assert goal.goal_seq == 1

    def test_idempotent_requeue_is_a_no_op_on_the_queue(self) -> None:
        goal = AiPilotWheelGoal(pending_order=("heading",))
        # No target yet for `heading` despite it already being queued
        # (e.g. it was promoted then demoted without clearing the queue
        # entry -- defensive case, should never duplicate the entry).
        goal = request_goal(goal, "heading", 10.0, heading_target_deg=45.0)
        assert goal.pending_order == ("heading",)

    def test_a_new_goal_clears_an_outstanding_hvrt_translate(self) -> None:
        """Review fix (BL-16 Stage P2 arbitration, main loop's own rule):
        "speaking any new heading/altitude/speed goal clears an
        outstanding translate direction... then the goal proceeds
        normally" -- latest command wins, nothing lost."""
        goal = AiPilotWheelGoal(hvrt_direction="left", goal_seq=1)
        goal = request_goal(goal, "altitude", 10.0, altitude_target_m=300.0)
        assert goal.hvrt_direction is None
        assert goal.altitude_target_m == 300.0
        assert goal.pending_order == ("altitude",)

    def test_no_hvrt_direction_outstanding_is_unaffected(self) -> None:
        goal = request_goal(
            AiPilotWheelGoal(), "heading", 10.0, heading_target_deg=90.0
        )
        assert goal.hvrt_direction is None


class TestSetParkedHeading:
    def test_normalises_into_0_360(self) -> None:
        goal = set_parked_heading(AiPilotWheelGoal(), 1.0, 370.0)
        assert goal.heading_target_deg == pytest.approx(10.0)

    def test_negative_degrees_wrap_positive(self) -> None:
        goal = set_parked_heading(AiPilotWheelGoal(), 1.0, -10.0)
        assert goal.heading_target_deg == pytest.approx(350.0)


class TestNearestSpeedStep:
    def test_snaps_to_the_nearest_real_step(self) -> None:
        assert nearest_speed_step(140.0) == 150.0
        assert nearest_speed_step(100.0) == 120.0

    def test_at_or_above_the_top_step_snaps_to_the_max_sentinel(self) -> None:
        assert nearest_speed_step(250.0) == AI_PILOT_SPEED_MAX_SENTINEL_KMH
        assert nearest_speed_step(999.0) == AI_PILOT_SPEED_MAX_SENTINEL_KMH


class TestSetParkedSpeed:
    def test_snaps_a_numeric_request(self) -> None:
        goal, resolved = set_parked_speed(AiPilotWheelGoal(), 1.0, 140.0)
        assert resolved == 150.0
        assert goal.speed_target_kmh == 150.0

    def test_the_literal_max_resolves_to_the_sentinel(self) -> None:
        goal, resolved = set_parked_speed(AiPilotWheelGoal(), 1.0, "max")
        assert resolved == AI_PILOT_SPEED_MAX_SENTINEL_KMH
        assert goal.speed_target_kmh == AI_PILOT_SPEED_MAX_SENTINEL_KMH


class TestStepSpeed:
    def test_steps_up_one_rung(self) -> None:
        assert step_speed(120.0, "up") == 150.0

    def test_steps_down_one_rung(self) -> None:
        assert step_speed(150.0, "down") == 120.0

    def test_cannot_step_above_the_max_sentinel(self) -> None:
        assert step_speed(AI_PILOT_SPEED_MAX_SENTINEL_KMH, "up") == (
            AI_PILOT_SPEED_MAX_SENTINEL_KMH
        )

    def test_the_top_real_step_can_step_up_to_max(self) -> None:
        assert step_speed(250.0, "up") == AI_PILOT_SPEED_MAX_SENTINEL_KMH

    def test_cannot_step_below_zero(self) -> None:
        assert step_speed(0.0, "down") == 0.0

    def test_an_unknown_current_speed_is_never_treated_as_a_known_step(self) -> None:
        assert step_speed(None, "up") is None


class TestAltitudeRefFromLetter:
    def test_recognised_letters(self) -> None:
        assert altitude_ref_from_letter("R") == "radar"
        assert altitude_ref_from_letter("B") == "barometric"

    def test_unrecognised_or_missing_is_none(self) -> None:
        assert altitude_ref_from_letter(None) is None
        assert altitude_ref_from_letter("MAX") is None


class TestAiPilotGoalRequest:
    def test_constructs_with_a_single_meaningful_field(self) -> None:
        request = AiPilotGoalRequest(param="heading", heading_deg=90.0)
        assert request.param == "heading"
        assert request.heading_deg == 90.0
        assert request.altitude_m is None
        assert request.speed_kmh is None


class TestResolveAltitudeReference:
    """The 700 m radar cap (plan, "The 700 m radar cap -- the defined
    answer for a request above it")."""

    def test_at_or_above_the_cap_is_always_barometric(self) -> None:
        assert resolve_altitude_reference(900.0, "radar", "radar") == "barometric"
        assert resolve_altitude_reference(700.0, None, "radar") == "barometric"

    def test_below_the_cap_honours_an_explicit_request(self) -> None:
        assert resolve_altitude_reference(300.0, "radar", "barometric") == "radar"
        assert resolve_altitude_reference(300.0, "barometric", "radar") == "barometric"

    def test_below_the_cap_with_no_request_keeps_the_current_reference(self) -> None:
        assert resolve_altitude_reference(300.0, None, "radar") == "radar"
        assert resolve_altitude_reference(300.0, None, "barometric") == "barometric"

    def test_below_the_cap_with_nothing_known_defaults_to_barometric(self) -> None:
        assert resolve_altitude_reference(300.0, None, None) == "barometric"


class TestSetParkedAltitude:
    def test_returns_the_achieved_reference_for_the_readback(self) -> None:
        goal, achieved = set_parked_altitude(
            AiPilotWheelGoal(), 1.0, 900.0, "radar", "radar"
        )
        assert achieved == "barometric"
        assert goal.altitude_target_m == 900.0
        assert goal.altitude_target_ref == "barometric"

    def test_a_reachable_radar_request_is_honoured(self) -> None:
        goal, achieved = set_parked_altitude(
            AiPilotWheelGoal(), 1.0, 300.0, "radar", "barometric"
        )
        assert achieved == "radar"
        assert goal.altitude_target_ref == "radar"


class TestHvrtDirection:
    def test_set_then_clear(self) -> None:
        goal = set_hvrt_direction(AiPilotWheelGoal(), "left")
        assert goal.hvrt_direction == "left"
        goal = clear_hvrt_direction(goal)
        assert goal.hvrt_direction is None

    def test_redirecting_replaces_the_direction(self) -> None:
        goal = set_hvrt_direction(AiPilotWheelGoal(), "left")
        goal = set_hvrt_direction(goal, "right")
        assert goal.hvrt_direction == "right"

    def test_an_actual_change_bumps_goal_seq(self) -> None:
        """Review fix: a sticky field, not a one-shot trigger -- without
        the bump, `body.py`'s own "send on `goal_seq` change" posture
        would silently drop the command whenever the goal's `goal_seq`
        had not already moved for some other reason (e.g. "Hold" after a
        translate with nothing else outstanding)."""
        goal = set_hvrt_direction(AiPilotWheelGoal(goal_seq=5), "left")
        assert goal.goal_seq == 6
        goal = set_hvrt_direction(goal, "right")
        assert goal.goal_seq == 7
        goal = clear_hvrt_direction(goal)
        assert goal.goal_seq == 8

    def test_no_change_does_not_bump_goal_seq(self) -> None:
        goal = AiPilotWheelGoal(hvrt_direction="left", goal_seq=5)
        assert set_hvrt_direction(goal, "left").goal_seq == 5
        no_direction = AiPilotWheelGoal(goal_seq=5)
        assert clear_hvrt_direction(no_direction).goal_seq == 5


class TestGoalParamForWire:
    """Review fix (BL-16 Stage P2): the `param` value actually sent on
    the wire is `None` whenever an HVRT translate is outstanding, even
    if `active_param` is still set internally -- the single place the
    wire's own invariant (`param`/`hvrt_direction` never both meaningful
    on one message) is enforced."""

    def test_active_param_passes_through_with_no_hvrt_direction(self) -> None:
        goal = AiPilotWheelGoal(active_param="altitude", altitude_target_m=300.0)
        assert goal_param_for_wire(goal) == "altitude"

    def test_hvrt_direction_nulls_the_param_even_though_active_param_is_kept(
        self,
    ) -> None:
        goal = AiPilotWheelGoal(
            active_param="altitude",
            altitude_target_m=300.0,
            hvrt_direction="left",
        )
        assert goal_param_for_wire(goal) is None
        # The main loop's own rule: queued/active goals keep their
        # targets and queue positions -- only the wire's own `param`
        # field is nulled, never `active_param` itself.
        assert goal.active_param == "altitude"


class TestDecideAiPilotWheel:
    """The rotation mechanism (plan, "`AiPilotWheelGoal` -- the new
    co-moving state, and the rotation rule"): promote/demote/preempt
    sequences and the takeover-coexistence gate."""

    def test_no_goal_at_all_is_a_no_op(self) -> None:
        state = ParkedFlightState()
        assert decide_ai_pilot_wheel(state, 10.0) is state

    def test_promotes_the_front_of_the_queue_when_idle(self) -> None:
        goal = AiPilotWheelGoal(heading_target_deg=90.0, pending_order=("heading",))
        state = replace_goal(ParkedFlightState(), goal)
        result = decide_ai_pilot_wheel(state, 10.0)
        assert result.goal is not None
        assert result.goal.active_param == "heading"
        assert result.goal.active_since_sim == 10.0
        assert result.goal.pending_order == ()
        assert result.goal.goal_seq == 1

    def test_a_single_outstanding_goal_never_rotates(self) -> None:
        """No slice limit applies when nothing else is waiting (plan:
        "When only one parameter is outstanding, no slice limit
        applies")."""
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0,
            active_param="heading",
            active_since_sim=0.0,
            goal_seq=1,
        )
        state = replace_goal(ParkedFlightState(), goal)
        result = decide_ai_pilot_wheel(state, 0.0 + AI_PILOT_GOAL_SLICE_S + 100.0)
        assert result.goal is not None
        assert result.goal.active_param == "heading"
        assert result.goal.goal_seq == 1

    def test_rotates_to_the_next_parameter_after_the_slice_elapses(self) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0,
            speed_target_kmh=200.0,
            active_param="heading",
            active_since_sim=0.0,
            pending_order=("speed",),
            goal_seq=1,
        )
        state = replace_goal(ParkedFlightState(), goal)
        result = decide_ai_pilot_wheel(state, AI_PILOT_GOAL_SLICE_S)
        assert result.goal is not None
        assert result.goal.active_param == "speed"
        assert result.goal.pending_order == ("heading",)
        assert result.goal.active_since_sim == AI_PILOT_GOAL_SLICE_S
        assert result.goal.goal_seq == 2
        # Demoted, not dropped -- its own target is kept.
        assert result.goal.heading_target_deg == 90.0

    def test_does_not_rotate_before_the_slice_elapses(self) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0,
            speed_target_kmh=200.0,
            active_param="heading",
            active_since_sim=0.0,
            pending_order=("speed",),
            goal_seq=1,
        )
        state = replace_goal(ParkedFlightState(), goal)
        result = decide_ai_pilot_wheel(state, AI_PILOT_GOAL_SLICE_S - 0.1)
        assert result.goal is not None
        assert result.goal.active_param == "heading"
        assert result.goal.goal_seq == 1

    def test_never_promotes_while_a_takeover_correction_is_running(self) -> None:
        goal = AiPilotWheelGoal(heading_target_deg=90.0, pending_order=("heading",))
        state = replace(
            replace_goal(ParkedFlightState(), goal),
            takeover_stage="correcting_altitude",
        )
        result = decide_ai_pilot_wheel(state, 10.0)
        assert result.goal is not None
        assert result.goal.active_param is None
        assert result.goal.pending_order == ("heading",)

    def test_a_settled_parameter_clears_and_promotes_the_next_one(self) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0,
            speed_target_kmh=200.0,
            active_param="heading",
            active_since_sim=0.0,
            pending_order=("speed",),
            goal_seq=1,
        )
        state = replace_goal(ParkedFlightState(), goal)
        result = decide_ai_pilot_wheel(state, 1.0, settled_param="heading")
        assert result.goal is not None
        assert result.goal.heading_target_deg is None
        assert result.goal.active_param == "speed"
        assert result.goal.pending_order == ()
        assert result.goal.goal_seq == 2

    def test_a_settled_parameter_with_nothing_else_queued_goes_idle(self) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0,
            active_param="heading",
            active_since_sim=0.0,
            goal_seq=1,
        )
        state = replace_goal(ParkedFlightState(), goal)
        result = decide_ai_pilot_wheel(state, 1.0, settled_param="heading")
        assert result.goal is not None
        assert result.goal.active_param is None
        assert result.goal.heading_target_deg is None
        # No new message sent for going idle -- unchanged sequence.
        assert result.goal.goal_seq == 1

    def test_hvrt_timeout_clears_the_direction_even_during_a_takeover(self) -> None:
        """Lua's own safety-timeout release must be observed regardless
        of the takeover gate -- that gate only withholds *promotion*, not
        reconciling a field Lua has already let go of."""
        goal = AiPilotWheelGoal(hvrt_direction="left")
        state = replace(
            replace_goal(ParkedFlightState(), goal), takeover_stage="opening_menu"
        )
        result = decide_ai_pilot_wheel(state, 10.0, hvrt_released_timeout=True)
        assert result.goal is not None
        assert result.goal.hvrt_direction is None

    def test_an_outstanding_hvrt_translate_pauses_the_goal_channel(self) -> None:
        """Review fix, main loop's own arbitration rule: a goal active,
        then "left" -- the goal keeps its target and queue position
        (nothing promoted/demoted/settled) while the translate is held,
        even though the slice has long elapsed and Lua reports it
        settled."""
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0,
            active_param="heading",
            active_since_sim=0.0,
            goal_seq=1,
            hvrt_direction="left",
        )
        state = replace_goal(ParkedFlightState(), goal)
        result = decide_ai_pilot_wheel(
            state,
            AI_PILOT_GOAL_SLICE_S + 100.0,
            settled_param="heading",
        )
        assert result.goal is not None
        assert result.goal.active_param == "heading"
        assert result.goal.heading_target_deg == 90.0
        assert result.goal.goal_seq == 1

    def test_a_queued_second_goal_also_stays_queued_while_paused(self) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0,
            speed_target_kmh=200.0,
            active_param="heading",
            active_since_sim=0.0,
            pending_order=("speed",),
            goal_seq=1,
            hvrt_direction="left",
        )
        state = replace_goal(ParkedFlightState(), goal)
        result = decide_ai_pilot_wheel(state, AI_PILOT_GOAL_SLICE_S + 100.0)
        assert result.goal is not None
        assert result.goal.active_param == "heading"
        assert result.goal.pending_order == ("speed",)
        assert result.goal.goal_seq == 1

    def test_the_goal_channel_resumes_once_the_translate_clears(self) -> None:
        """ "Hold" (or the preempting-goal clear) must land before this
        call for rotation to resume the same poll -- `body.py`'s own
        call site applies the transition first, exactly as this test
        does by handing in a goal whose `hvrt_direction` is already
        `None`."""
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0,
            speed_target_kmh=200.0,
            active_param="heading",
            active_since_sim=0.0,
            pending_order=("speed",),
            goal_seq=2,
            hvrt_direction=None,
        )
        state = replace_goal(ParkedFlightState(), goal)
        result = decide_ai_pilot_wheel(state, AI_PILOT_GOAL_SLICE_S)
        assert result.goal is not None
        assert result.goal.active_param == "speed"
        assert result.goal.pending_order == ("heading",)
        assert result.goal.goal_seq == 3


def replace_goal(state: ParkedFlightState, goal: AiPilotWheelGoal) -> ParkedFlightState:
    """Small local helper -- `ParkedFlightState.goal` is replaced
    wholesale like every other field here, and every test above needs
    one starting from a bare `ParkedFlightState()`."""
    return replace(state, goal=goal)


def _advance_with(body: dict[str, Any], state: ParkedFlightState) -> ParkedFlightState:
    for base_url in _server(body):
        return advance_parked_flight_state(
            state, AircraftLayerClient(base_url=base_url)
        )
    raise AssertionError("unreachable")


class TestPlayerSeat:
    """Seat-change triggers (user, 2026-11-16): `apw_seat` mirrored into
    `player_seat`, and `seat_change` deciding what counts as a move."""

    _BASE: ClassVar[dict[str, Any]] = {
        "t": 1.0,
        "received_wall_clock_s": 1.0,
        "apw_parked_active": False,
    }

    def test_seat_is_mirrored(self) -> None:
        state = _advance_with(
            {**self._BASE, "apw_seat": "operator"}, ParkedFlightState()
        )
        assert state.player_seat == "operator"

    def test_an_unknown_seat_value_reads_none(self) -> None:
        state = _advance_with(
            {**self._BASE, "apw_seat": "gunner"}, ParkedFlightState(player_seat="pilot")
        )
        assert state.player_seat is None

    def test_an_older_export_without_the_field_keeps_the_seat(self) -> None:
        state = _advance_with(dict(self._BASE), ParkedFlightState(player_seat="pilot"))
        assert state.player_seat == "pilot"

    def test_a_move_between_known_seats_is_a_change(self) -> None:
        assert seat_change("pilot", "operator") == "operator"
        assert seat_change("operator", "pilot") == "pilot"

    def test_the_first_reading_of_a_mission_is_not_a_change(self) -> None:
        assert seat_change(None, "pilot") is None
        assert seat_change(None, "operator") is None

    def test_no_change_and_going_unknown_are_not_changes(self) -> None:
        assert seat_change("pilot", "pilot") is None
        assert seat_change("operator", None) is None


class TestPayloadCountDropped:
    """Stage P3+P4's launch-detection helper (plan, "Launch detection --
    implemented, reusing only the payload feed")."""

    def test_no_previous_reading_is_never_a_drop(self) -> None:
        assert payload_count_dropped(None, {1: 2}) is False

    def test_a_drop_on_one_station_is_detected(self) -> None:
        assert payload_count_dropped({1: 2}, {1: 1}) is True

    def test_a_rise_on_one_station_while_another_drops_is_still_a_drop(
        self,
    ) -> None:
        assert payload_count_dropped({1: 2, 2: 0}, {1: 2, 2: 1}) is False
        assert payload_count_dropped({1: 2, 2: 1}, {1: 1, 2: 2}) is True

    def test_a_new_station_with_no_previous_reading_is_not_a_drop(self) -> None:
        assert payload_count_dropped({1: 2}, {1: 2, 2: 0}) is False

    def test_no_change_is_not_a_drop(self) -> None:
        assert payload_count_dropped({1: 2}, {1: 2}) is False


class TestCaptureFlightSnapshot:
    """`cbtm_align_for_launch`'s own pre-align snapshot (plan,
    "`AlignPhase` and `FlightSnapshot`")."""

    def test_prefers_the_outstanding_goal_target_over_the_held_value(self) -> None:
        state = ParkedFlightState(
            held_heading=10.0,
            held_altitude=100.0,
            held_altitude_ref="B",
            held_speed=150.0,
        )
        goal = AiPilotWheelGoal(
            heading_target_deg=270.0,
            altitude_target_m=400.0,
            altitude_target_ref="radar",
            speed_target_kmh=200.0,
        )
        snapshot = capture_flight_snapshot(state, goal, agl_m=50.0)
        assert snapshot == FlightSnapshot(
            heading_deg=270.0,
            altitude_m=400.0,
            altitude_ref="radar",
            speed_kmh=200.0,
            agl_m=50.0,
        )

    def test_falls_back_to_held_values_with_no_outstanding_goal(self) -> None:
        state = ParkedFlightState(
            held_heading=10.0,
            held_altitude=100.0,
            held_altitude_ref="B",
            held_speed=150.0,
        )
        snapshot = capture_flight_snapshot(state, AiPilotWheelGoal(), agl_m=50.0)
        assert snapshot == FlightSnapshot(
            heading_deg=10.0,
            altitude_m=100.0,
            altitude_ref="barometric",
            speed_kmh=150.0,
            agl_m=50.0,
        )

    def test_none_when_a_parameter_has_neither_target_nor_held_value(self) -> None:
        state = ParkedFlightState(held_altitude=100.0, held_altitude_ref="B")
        assert capture_flight_snapshot(state, AiPilotWheelGoal(), agl_m=50.0) is None

    def test_none_when_agl_is_not_yet_known(self) -> None:
        state = ParkedFlightState(
            held_heading=10.0,
            held_altitude=100.0,
            held_altitude_ref="B",
            held_speed=150.0,
        )
        assert capture_flight_snapshot(state, AiPilotWheelGoal(), agl_m=None) is None


class TestCbtmApplyAlign:
    def test_align_always_restarts_plain_alignment(self) -> None:
        state = ParkedFlightState(
            align_phase="recovering",
            pre_align_snapshot=FlightSnapshot(1.0, 2.0, "radar", 3.0, 4.0),
        )
        result = cbtm_apply_align(state)
        assert result.align_phase == "aligning"
        assert result.pre_align_snapshot is None


class TestCbtmApplyAlignForLaunch:
    """Fix 1 (plan check, 2026-11-18): a second "align for launch" said
    mid-recovery keeps the first snapshot."""

    def test_captures_fresh_from_none(self) -> None:
        state = ParkedFlightState(
            held_heading=10.0,
            held_altitude=100.0,
            held_altitude_ref="B",
            held_speed=150.0,
        )
        result = cbtm_apply_align_for_launch(state, AiPilotWheelGoal(), agl_m=50.0)
        assert result.align_phase == "launch_aligned"
        assert result.pre_align_snapshot == FlightSnapshot(
            heading_deg=10.0,
            altitude_m=100.0,
            altitude_ref="barometric",
            speed_kmh=150.0,
            agl_m=50.0,
        )

    def test_a_second_call_mid_recovery_keeps_the_first_snapshot(self) -> None:
        original = FlightSnapshot(10.0, 100.0, "barometric", 150.0, 50.0)
        state = ParkedFlightState(
            align_phase="recovering",
            pre_align_snapshot=original,
            held_heading=999.0,
            held_altitude=5.0,
            held_altitude_ref="R",
            held_speed=999.0,
        )
        result = cbtm_apply_align_for_launch(state, AiPilotWheelGoal(), agl_m=5.0)
        assert result.align_phase == "launch_aligned"
        assert result.pre_align_snapshot == original

    def test_a_second_call_while_launch_aligned_also_keeps_the_snapshot(
        self,
    ) -> None:
        original = FlightSnapshot(10.0, 100.0, "barometric", 150.0, 50.0)
        state = ParkedFlightState(
            align_phase="launch_aligned", pre_align_snapshot=original
        )
        result = cbtm_apply_align_for_launch(state, AiPilotWheelGoal(), agl_m=999.0)
        assert result.pre_align_snapshot == original


class TestSeedRecoveryGoal:
    """Decision 26's own priority order."""

    def test_altitude_is_active_speed_is_queued(self) -> None:
        snapshot = FlightSnapshot(10.0, 300.0, "barometric", 200.0, 50.0)
        result = seed_recovery_goal(AiPilotWheelGoal(), snapshot, now_sim=5.0)
        assert result.active_param == "altitude"
        assert result.active_since_sim == 5.0
        assert result.altitude_target_m == 300.0
        assert result.altitude_target_ref == "barometric"
        assert result.pending_order == ("speed",)
        assert result.speed_target_kmh == 200.0

    def test_a_previously_active_heading_is_requeued_not_dropped(self) -> None:
        snapshot = FlightSnapshot(10.0, 300.0, "barometric", 200.0, 50.0)
        goal = AiPilotWheelGoal(
            heading_target_deg=270.0, active_param="heading", active_since_sim=1.0
        )
        result = seed_recovery_goal(goal, snapshot, now_sim=5.0)
        assert result.active_param == "altitude"
        assert result.pending_order == ("heading", "speed")
        assert result.heading_target_deg == 270.0


class TestDecideAiPilotWheelCbtm:
    """Stage P3+P4's own additions to `decide_ai_pilot_wheel` (plan,
    "`decide_ai_pilot_wheel` -- the align/break/recovery 'when'")."""

    def test_a_break_drops_the_active_heading_goal_and_clears_align_phase(
        self,
    ) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0, active_param="heading", active_since_sim=0.0
        )
        state = replace(
            replace_goal(ParkedFlightState(), goal),
            align_phase="aligning",
            cbtm_action_sent="break_left",
        )
        result = decide_ai_pilot_wheel(state, 1.0)
        assert result.align_phase == "none"
        assert result.pre_align_snapshot is None
        assert result.goal is not None
        assert result.goal.active_param is None
        assert result.goal.heading_target_deg is None

    def test_a_break_drops_a_queued_heading_goal(self) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0,
            speed_target_kmh=200.0,
            active_param="speed",
            active_since_sim=0.0,
            pending_order=("heading",),
        )
        state = replace(
            replace_goal(ParkedFlightState(), goal), cbtm_action_sent="break_away"
        )
        result = decide_ai_pilot_wheel(state, 1.0)
        assert result.goal is not None
        assert result.goal.heading_target_deg is None
        assert result.goal.pending_order == ()
        assert result.goal.active_param == "speed"

    def test_an_align_action_sent_does_not_trigger_the_break_logic(self) -> None:
        goal = AiPilotWheelGoal(
            heading_target_deg=90.0, active_param="heading", active_since_sim=0.0
        )
        state = replace(
            replace_goal(ParkedFlightState(), goal),
            align_phase="aligning",
            cbtm_action_sent="align",
        )
        result = decide_ai_pilot_wheel(state, 1.0)
        assert result.align_phase == "aligning"
        assert result.goal is not None
        assert result.goal.active_param == "heading"

    def test_recovery_fires_once_on_the_agl_relative_floor(self) -> None:
        snapshot = FlightSnapshot(10.0, 300.0, "barometric", 150.0, agl_m=100.0)
        state = ParkedFlightState(
            align_phase="launch_aligned", pre_align_snapshot=snapshot
        )
        result = decide_ai_pilot_wheel(
            state,
            5.0,
            agl_m=100.0 - AI_PILOT_RECOVER_AGL_DROP_M,
        )
        assert result.align_phase == "recovering"
        assert result.goal is not None
        assert result.goal.active_param == "altitude"
        assert result.goal.pending_order == ("speed",)

    def test_recovery_does_not_fire_before_the_floor_is_crossed(self) -> None:
        snapshot = FlightSnapshot(10.0, 300.0, "barometric", 150.0, agl_m=100.0)
        state = ParkedFlightState(
            align_phase="launch_aligned", pre_align_snapshot=snapshot
        )
        result = decide_ai_pilot_wheel(
            state,
            5.0,
            agl_m=100.0 - AI_PILOT_RECOVER_AGL_DROP_M + 1.0,
        )
        assert result.align_phase == "launch_aligned"

    def test_recovery_fires_on_the_ias_ceiling(self) -> None:
        snapshot = FlightSnapshot(10.0, 300.0, "barometric", 150.0, agl_m=500.0)
        state = ParkedFlightState(
            align_phase="launch_aligned", pre_align_snapshot=snapshot
        )
        result = decide_ai_pilot_wheel(
            state,
            5.0,
            agl_m=500.0,
            ias_kmh=AI_PILOT_RECOVER_IAS_CEILING_KMH,
        )
        assert result.align_phase == "recovering"

    def test_recovery_fires_once_on_a_payload_count_drop(self) -> None:
        snapshot = FlightSnapshot(10.0, 300.0, "barometric", 150.0, agl_m=500.0)
        state = ParkedFlightState(
            align_phase="launch_aligned", pre_align_snapshot=snapshot
        )
        result = decide_ai_pilot_wheel(
            state, 5.0, agl_m=500.0, payload_count_dropped=True
        )
        assert result.align_phase == "recovering"

    def test_two_triggers_crossing_at_once_still_fires_only_once(self) -> None:
        snapshot = FlightSnapshot(10.0, 300.0, "barometric", 150.0, agl_m=100.0)
        state = ParkedFlightState(
            align_phase="launch_aligned", pre_align_snapshot=snapshot
        )
        result = decide_ai_pilot_wheel(
            state,
            5.0,
            agl_m=100.0 - AI_PILOT_RECOVER_AGL_DROP_M,
            ias_kmh=AI_PILOT_RECOVER_IAS_CEILING_KMH,
            payload_count_dropped=True,
        )
        assert result.align_phase == "recovering"
        assert result.goal is not None
        assert result.goal.active_param == "altitude"

    def test_recovery_promotes_speed_on_settled_param_never_the_slice_timer(
        self,
    ) -> None:
        """Decision 26: recovery promotes strictly on `settled_param`,
        never the slice timer -- even well past `AI_PILOT_GOAL_SLICE_S`,
        altitude stays active until Lua reports it settled."""
        snapshot = FlightSnapshot(10.0, 300.0, "barometric", 150.0, agl_m=500.0)
        goal = AiPilotWheelGoal(
            altitude_target_m=300.0,
            altitude_target_ref="barometric",
            speed_target_kmh=150.0,
            active_param="altitude",
            active_since_sim=0.0,
            pending_order=("speed",),
        )
        state = replace(
            replace_goal(ParkedFlightState(), goal),
            align_phase="recovering",
            pre_align_snapshot=snapshot,
        )
        result = decide_ai_pilot_wheel(state, AI_PILOT_GOAL_SLICE_S + 100.0)
        assert result.goal is not None
        assert result.goal.active_param == "altitude"
        assert result.align_phase == "recovering"

        promoted = decide_ai_pilot_wheel(
            result, AI_PILOT_GOAL_SLICE_S + 100.0, settled_param="altitude"
        )
        assert promoted.goal is not None
        assert promoted.goal.active_param == "speed"
        assert promoted.align_phase == "recovering"

    def test_recovery_ends_once_both_parameters_have_cleared(self) -> None:
        snapshot = FlightSnapshot(10.0, 300.0, "barometric", 150.0, agl_m=500.0)
        goal = AiPilotWheelGoal(
            speed_target_kmh=150.0, active_param="speed", active_since_sim=0.0
        )
        state = replace(
            replace_goal(ParkedFlightState(), goal),
            align_phase="recovering",
            pre_align_snapshot=snapshot,
        )
        result = decide_ai_pilot_wheel(state, 10.0, settled_param="speed")
        assert result.align_phase == "none"
        assert result.pre_align_snapshot is None
        assert result.goal is not None
        assert result.goal.active_param is None

    def test_a_fresh_command_for_one_recovering_parameter_leaves_the_other_alone(
        self,
    ) -> None:
        """Q6/the plan's own Co-moving table row: a fresh voice command
        for one recovering parameter replaces that parameter's own
        target via the ordinary `request_goal` 'latest wins' path --
        the other keeps recovering untouched. Exercised at the
        `request_goal` level, which is what a fresh `set_parked_
        altitude` call during recovery actually goes through."""
        snapshot = FlightSnapshot(10.0, 300.0, "barometric", 150.0, agl_m=500.0)
        goal = seed_recovery_goal(AiPilotWheelGoal(), snapshot, now_sim=0.0)
        assert goal.active_param == "altitude"
        assert goal.pending_order == ("speed",)

        updated = request_goal(goal, "altitude", 1.0, altitude_target_m=200.0)
        assert updated.altitude_target_m == 200.0
        assert updated.active_param == "altitude"
        assert updated.speed_target_kmh == 150.0
        assert updated.pending_order == ("speed",)
