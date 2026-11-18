"""Tests for `belief.flight_control` -- BL-16 mode 1 Stage M1 (`plans/
flight-control/plan.md`, "Revised 2026-11-18"). `advance_flight_control_
state` is exercised against a real loopback `http.server` instance via a
real `AircraftLayerClient`, same posture as `test_ai_pilot_wheel.py`'s
own convention (the project's "no mocked `urllib`" rule) -- not a mocked
client double. `take_controls`/`release_controls`/`decide_flight_
control`/the clamp helpers are pure, so they are exercised directly
against `FlightControlState` values, no server needed."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from aircraft_client import AircraftLayerClient
from belief.flight_control import (
    FLOOR_AGL_M,
    MAX_IAS_KMH,
    MIN_IAS_KMH,
    FlightControlGoalRequest,
    FlightControlState,
    advance_flight_control_state,
    clamp_altitude,
    clamp_speed,
    decide_flight_control,
    flight_control_limits,
    goal_request_fields,
    release_controls,
    take_controls,
)


def _make_handler(body: object) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/flight_control/latest":
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
        "fc_mode": "active",
        "fc_take_seq": 3,
        "fc_goal_seq": 1,
        "fc_take_origin": "voice",
        "fc_takeover_mode": "heading",
        "fc_goal_heading": 90.0,
        "fc_goal_altitude": None,
        "fc_goal_altitude_ref": None,
        "fc_goal_speed": None,
        "fc_measured_heading": 91.0,
        "fc_measured_altitude": 200.0,
        "fc_measured_speed": 150.0,
        "fc_release_reason": None,
        "fc_refuse_cause": None,
        "fc_in_band_heading": True,
        "fc_in_band_altitude": False,
        "fc_in_band_speed": None,
        "fc_axes_pitch": True,
        "fc_axes_roll": True,
        "fc_axes_pedal": True,
        "fc_axes_collective": False,
    }
    yield from _server(body)


@pytest.fixture
def server_with_null() -> Iterator[str]:
    yield from _server(None)


class TestAdvanceFlightControlState:
    def test_a_sample_is_parsed_into_the_mirrors(self, server_with_sample: str) -> None:
        client = AircraftLayerClient(base_url=server_with_sample)
        state = advance_flight_control_state(FlightControlState(), client)

        assert state.lua_mode == "active"
        assert state.lua_take_seq == 3
        assert state.lua_take_origin == "voice"
        assert state.lua_takeover_mode == "heading"
        assert state.held_heading == pytest.approx(90.0)
        assert state.held_altitude is None
        assert state.measured_heading == pytest.approx(91.0)
        assert state.measured_altitude == pytest.approx(200.0)
        assert state.measured_speed == pytest.approx(150.0)
        assert state.lua_release_reason is None
        assert state.lua_refuse_cause is None
        assert state.in_band_heading is True
        assert state.in_band_altitude is False
        assert state.in_band_speed is None

    def test_body_layer_own_fields_are_carried_through_unchanged(
        self, server_with_sample: str
    ) -> None:
        """`phase`/`take_seq`/`pending_take_says`/`took_at_sim`/
        `unpark_take`/`wire_seq` are body-layer's own authoritative
        fields -- the mirror refresh must never touch them."""
        client = AircraftLayerClient(base_url=server_with_sample)
        previous = FlightControlState(
            phase="TAKING",
            take_seq=7,
            pending_take_says="I have controls.",
            took_at_sim=12.0,
            unpark_take=True,
            wire_seq=4,
        )
        state = advance_flight_control_state(previous, client)

        assert state.phase == "TAKING"
        assert state.take_seq == 7
        assert state.pending_take_says == "I have controls."
        assert state.took_at_sim == 12.0
        assert state.unpark_take is True
        assert state.wire_seq == 4

    def test_a_null_sample_leaves_state_unchanged(self, server_with_null: str) -> None:
        client = AircraftLayerClient(base_url=server_with_null)
        previous = FlightControlState(phase="ACTIVE", take_seq=2)
        state = advance_flight_control_state(previous, client)
        assert state is previous


class TestTakeControls:
    def test_overlay_flying_is_a_silent_no_op(self) -> None:
        state, result = take_controls(
            FlightControlState(),
            0.0,
            overlay_flying=True,
            on_ground=False,
            too_slow=False,
            attack_run_engaged=False,
        )
        assert result == {"ok": True, "acted": False}
        assert state.phase == "PILOT"

    def test_on_ground_refuses(self) -> None:
        _, result = take_controls(
            FlightControlState(),
            0.0,
            overlay_flying=False,
            on_ground=True,
            too_slow=False,
            attack_run_engaged=False,
        )
        assert result == {"ok": False, "reason": "ON_GROUND"}

    def test_too_slow_refuses(self) -> None:
        _, result = take_controls(
            FlightControlState(),
            0.0,
            overlay_flying=False,
            on_ground=False,
            too_slow=True,
            attack_run_engaged=False,
        )
        assert result == {"ok": False, "reason": "TOO_SLOW"}

    def test_attack_run_engaged_refuses(self) -> None:
        _, result = take_controls(
            FlightControlState(),
            0.0,
            overlay_flying=False,
            on_ground=False,
            too_slow=False,
            attack_run_engaged=True,
        )
        assert result == {"ok": False, "reason": "ATTACK_RUN_ENGAGED"}

    def test_refusal_order_is_ground_then_speed_then_attack_run(self) -> None:
        """All three refusals true at once -- `ON_GROUND` wins, pinning
        the plan's own check order."""
        _, result = take_controls(
            FlightControlState(),
            0.0,
            overlay_flying=False,
            on_ground=True,
            too_slow=True,
            attack_run_engaged=True,
        )
        assert result == {"ok": False, "reason": "ON_GROUND"}

    def test_a_clean_take_bumps_take_seq_and_enters_taking(self) -> None:
        state, result = take_controls(
            FlightControlState(take_seq=5),
            42.0,
            overlay_flying=False,
            on_ground=False,
            too_slow=False,
            attack_run_engaged=False,
        )
        assert result == {"ok": True, "acted": True}
        assert state.phase == "TAKING"
        assert state.take_seq == 6
        assert state.took_at_sim == 42.0


class TestReleaseControls:
    def test_overlay_flying_is_unable(self) -> None:
        state, result = release_controls(FlightControlState(), overlay_flying=True)
        assert result == {"ok": False, "reason": "AI_OVERLAY"}
        assert state.phase == "PILOT"

    def test_releases_from_taking(self) -> None:
        state, result = release_controls(
            FlightControlState(phase="TAKING", pending_take_says="x", took_at_sim=1.0),
            overlay_flying=False,
        )
        assert result == {"ok": True, "acted": True}
        assert state.phase == "PILOT"
        assert state.pending_take_says is None
        assert state.took_at_sim is None

    def test_releases_from_active(self) -> None:
        state, result = release_controls(
            FlightControlState(phase="ACTIVE"), overlay_flying=False
        )
        assert result == {"ok": True, "acted": True}
        assert state.phase == "PILOT"

    def test_nobody_flying_is_a_silent_no_op(self) -> None:
        state, result = release_controls(FlightControlState(), overlay_flying=False)
        assert result == {"ok": True, "acted": False}
        assert state.phase == "PILOT"


class TestDecideFlightControl:
    def test_park_edge_while_active_moves_to_overlay_silently(self) -> None:
        state, decision = decide_flight_control(
            FlightControlState(phase="ACTIVE", take_seq=1),
            10.0,
            parked_active=True,
        )
        assert state.phase == "OVERLAY"
        assert state.unpark_take is True
        assert decision is None

    def test_park_edge_while_taking_moves_to_overlay_silently(self) -> None:
        state, decision = decide_flight_control(
            FlightControlState(phase="TAKING", took_at_sim=9.0),
            10.0,
            parked_active=True,
        )
        assert state.phase == "OVERLAY"
        assert state.took_at_sim is None
        assert decision is None

    def test_park_while_pilot_is_a_no_op_here(self) -> None:
        """Nothing to arm yet (he was not flying mode 1) -- `body.py`'s
        own 2026-11-17-handover `arm` send is a separate concern from
        this function (the plan's Co-moving row 8b)."""
        state, decision = decide_flight_control(
            FlightControlState(phase="PILOT"), 10.0, parked_active=True
        )
        assert state.phase == "PILOT"
        assert decision is None

    def test_unpark_confirmed_adopts_lua_take_seq_silently(self) -> None:
        state, decision = decide_flight_control(
            FlightControlState(
                phase="OVERLAY",
                take_seq=1,
                unpark_take=True,
                lua_mode="active",
                lua_take_origin="unpark",
                lua_take_seq=9,
            ),
            10.0,
            parked_active=False,
        )
        assert state.phase == "ACTIVE"
        assert state.take_seq == 9
        assert decision is None

    def test_unpark_refused_hands_back_with_an_urgent_line(self) -> None:
        state, decision = decide_flight_control(
            FlightControlState(
                phase="OVERLAY",
                unpark_take=True,
                lua_mode="off",
                lua_release_reason="refused",
                lua_refuse_cause="disabled",
            ),
            10.0,
            parked_active=False,
        )
        assert state.phase == "PILOT"
        assert state.unpark_take is False
        assert decision is not None
        assert decision.says == "You have controls!"
        assert decision.urgent is True

    def test_unpark_still_pending_is_a_no_op(self) -> None:
        """Lua has not reported an outcome for this unpark yet (neither
        `active`+`unpark` nor `off`+`refused`) -- nothing decided."""
        state, decision = decide_flight_control(
            FlightControlState(phase="OVERLAY", unpark_take=True, lua_mode="armed"),
            10.0,
            parked_active=False,
        )
        assert state.phase == "OVERLAY"
        assert decision is None

    def test_lua_self_release_while_active_speaks_urgently(self) -> None:
        for reason in ("envelope", "nan", "dead"):
            state, decision = decide_flight_control(
                FlightControlState(
                    phase="ACTIVE",
                    pending_take_says="stale",
                    lua_mode="off",
                    lua_release_reason=reason,
                ),
                10.0,
                parked_active=False,
            )
            assert state.phase == "PILOT", reason
            assert state.pending_take_says is None, reason
            assert decision is not None, reason
            assert decision.says == "You have controls!", reason
            assert decision.urgent is True, reason

    def test_says_spoken_exactly_once_for_the_matching_take_seq(self) -> None:
        state, decision = decide_flight_control(
            FlightControlState(
                phase="TAKING",
                take_seq=4,
                pending_take_says="I have controls.",
                took_at_sim=1.0,
                lua_mode="active",
                lua_take_seq=4,
            ),
            1.5,
            parked_active=False,
        )
        assert state.phase == "ACTIVE"
        assert state.pending_take_says is None
        assert state.took_at_sim is None
        assert decision is not None
        assert decision.says == "I have controls."
        assert decision.urgent is True

        # A second call against the now-`ACTIVE` state (as a later poll
        # would make) must not speak it again -- `pending_take_says` is
        # already cleared, so there is nothing left to say.
        _state2, decision2 = decide_flight_control(state, 2.0, parked_active=False)
        assert decision2 is None

    def test_says_not_spoken_for_a_mismatched_take_seq(self) -> None:
        """Lua confirms `active` for a *stale* take_seq (an earlier take
        this one superseded) -- must not speak the current pending
        `says` against the wrong confirmation."""
        state, decision = decide_flight_control(
            FlightControlState(
                phase="TAKING",
                take_seq=5,
                pending_take_says="I have controls.",
                took_at_sim=1.0,
                lua_mode="active",
                lua_take_seq=4,
            ),
            1.5,
            parked_active=False,
        )
        assert state.phase == "TAKING"
        assert decision is None

    def test_ack_timeout_speaks_unable_not_ready_non_urgently(self) -> None:
        state, decision = decide_flight_control(
            FlightControlState(
                phase="TAKING",
                take_seq=1,
                pending_take_says="I have controls.",
                took_at_sim=0.0,
            ),
            100.0,
            parked_active=False,
        )
        assert state.phase == "PILOT"
        assert state.pending_take_says is None
        assert decision is not None
        assert decision.says == "Unable, not ready."
        assert decision.urgent is False

    def test_taking_before_the_timeout_is_a_no_op(self) -> None:
        state, decision = decide_flight_control(
            FlightControlState(phase="TAKING", take_seq=1, took_at_sim=0.0),
            0.5,
            parked_active=False,
        )
        assert state.phase == "TAKING"
        assert decision is None

    def test_pilot_with_nothing_happening_is_a_no_op(self) -> None:
        state, decision = decide_flight_control(
            FlightControlState(), 10.0, parked_active=False
        )
        assert state.phase == "PILOT"
        assert decision is None


class TestClampHelpers:
    def test_clamp_altitude_agl_floors_at_floor_agl_m(self) -> None:
        assert clamp_altitude(FLOOR_AGL_M - 10.0, "agl") == FLOOR_AGL_M
        assert clamp_altitude(FLOOR_AGL_M + 10.0, "agl") == FLOOR_AGL_M + 10.0

    def test_clamp_altitude_baro_passes_through_unclamped(self) -> None:
        assert clamp_altitude(0.0, "baro") == 0.0
        assert clamp_altitude(-50.0, "baro") == -50.0

    def test_clamp_speed_floors_and_ceilings(self) -> None:
        assert clamp_speed(MIN_IAS_KMH - 10.0) == MIN_IAS_KMH
        assert clamp_speed(MAX_IAS_KMH + 10.0) == MAX_IAS_KMH
        assert clamp_speed(150.0) == 150.0


class TestWireHelpers:
    def test_flight_control_limits_carries_the_given_on_ground_threshold(self) -> None:
        limits = flight_control_limits(12.5)
        assert limits["on_ground_agl_threshold_m"] == 12.5
        assert limits["min_ias_kmh"] == MIN_IAS_KMH
        assert limits["max_ias_kmh"] == MAX_IAS_KMH

    def test_flight_control_limits_carries_m2s_shaper_limits_and_bands(self) -> None:
        """M2's own additions to the wire `limits` bundle -- the
        shaper's own rate limits (`max_turn_bank_deg`/`max_climb_vs_
        mps`/`max_accel_mps2`) and A9's bands, all sent so `Export.
        lua`'s control law has one source of truth for behaviour."""
        limits = flight_control_limits(12.5)
        for key in (
            "max_turn_bank_deg",
            "max_climb_vs_mps",
            "max_accel_mps2",
            "speed_band_frac",
            "alt_band_frac",
            "alt_band_min_m",
            "turn_rate_band_frac",
            "heading_band_deg",
        ):
            assert key in limits
            assert isinstance(limits[key], float)

    def test_goal_request_fields_omits_none_and_false_fields(self) -> None:
        assert goal_request_fields(FlightControlGoalRequest()) == {}
        assert goal_request_fields(FlightControlGoalRequest(heading_deg=90.0)) == {
            "heading_deg": 90.0
        }
        assert goal_request_fields(FlightControlGoalRequest(turn=0)) == {"turn": 0}
        assert goal_request_fields(FlightControlGoalRequest(level_off=True)) == {
            "level_off": True
        }
        assert goal_request_fields(
            FlightControlGoalRequest(altitude_m=200.0, altitude_ref="agl")
        ) == {"alt_m": 200.0, "alt_ref": "agl"}
        assert goal_request_fields(FlightControlGoalRequest(ias_kmh=150.0)) == {
            "ias_kmh": 150.0
        }
