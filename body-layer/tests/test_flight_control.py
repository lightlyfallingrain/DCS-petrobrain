"""Tests for `belief.flight_control` -- BL-16 mode 1 (`plans/
flight-control/plan.md`, "Revised 2026-11-18", and `plans/
flight-desired-state/plan.md` Stage 3). `advance_flight_control_state`
is exercised against a real loopback `http.server` instance via a real
`AircraftLayerClient`, same posture as `test_ai_pilot_wheel.py`'s own
convention (the project's "no mocked `urllib`" rule) -- not a mocked
client double. `take_controls`/`release_controls`/the clamp helpers are
pure, so they are exercised directly, no server needed.

**BL-16 Stage 3** removed `FlightControlPhase`/`phase`/`take_seq`/
`pending_take_says`/`took_at_sim`/`unpark_take`/`wire_seq`/`held_*`/
`lua_take_seq`/`lua_last_cmd_seq` from `FlightControlState` entirely
(the mode authority and the voice-take confirm/timeout handshake moved
to `belief.flight_authority`'s `FlightAuthorityState`/`PendingTake`/
`resolve_pending_take`, tested in `test_flight_authority.py`) and
deleted `decide_flight_control` outright -- `TestDecideFlightControl`,
`TestDrainFlightControlSeedsTheBreakTarget` (the Decision-32 break-seed
logic, now owned by `Export.lua`'s own `build_take_seed`, carrying
`desired` verbatim into an unpark) and `TestDrainFlightControlSends
ReleaseOnAckTimeout` (the `flight_control_system_release_pending`
mechanism, superseded by `resolve_pending_take`'s own timeout handling)
are removed along with them."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from aircraft_client import AircraftLayerClient
from belief.flight_control import (
    FLOOR_AGL_M,
    MAX_IAS_KMH,
    FlightControlGoalRequest,
    FlightControlState,
    advance_flight_control_state,
    clamp_altitude,
    clamp_speed,
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
            import json

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
        "fc_take_origin": "voice",
        "fc_takeover_mode": "heading",
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
        "fc_slip_ball_pilot_raw": 0.125,
        "fc_slip_ball_operator_raw": -0.25,
        "fc_slip_ball_lo_api": None,
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
        assert state.lua_take_origin == "voice"
        assert state.lua_takeover_mode == "heading"
        assert state.measured_heading == pytest.approx(91.0)
        assert state.measured_altitude == pytest.approx(200.0)
        assert state.measured_speed == pytest.approx(150.0)
        assert state.lua_release_reason is None
        assert state.lua_refuse_cause is None
        assert state.in_band_heading is True
        assert state.in_band_altitude is False
        assert state.in_band_speed is None
        assert state.slip_ball_pilot_raw == pytest.approx(0.125)
        assert state.slip_ball_operator_raw == pytest.approx(-0.25)
        assert state.slip_ball_lo_api is None

    def test_a_null_sample_leaves_state_unchanged(self, server_with_null: str) -> None:
        client = AircraftLayerClient(base_url=server_with_null)
        previous = FlightControlState(lua_mode="active")
        state = advance_flight_control_state(previous, client)
        assert state is previous


class TestAdvanceFlightControlStateResetEpoch:
    """BL-16 sortie 2026-11-20 (`docs/acceptance/
    2026-11-20-sortie-feedback.md`) -- `lua_reset_epoch` mirrors
    `Export.lua`'s own `fc_reset_epoch` echo verbatim, same "mirror
    only" posture every other `lua_*` field already has."""

    def test_mirrors_the_echoed_epoch(self) -> None:
        body: dict[str, Any] = {
            "t": 1.0,
            "fc_mode": "off",
            "fc_reset_epoch": 1234,
            "fc_axes_pitch": False,
            "fc_axes_roll": False,
            "fc_axes_pedal": False,
            "fc_axes_collective": False,
        }
        for url in _server(body):
            client = AircraftLayerClient(base_url=url)
            state = advance_flight_control_state(FlightControlState(), client)
            assert state.lua_reset_epoch == 1234

    def test_absent_field_mirrors_as_none(self, server_with_sample: str) -> None:
        """`server_with_sample`'s own fixture body predates this field."""
        client = AircraftLayerClient(base_url=server_with_sample)
        state = advance_flight_control_state(FlightControlState(), client)
        assert state.lua_reset_epoch is None


class TestTakeControls:
    """BL-16 Stage 3 -- `take_controls` is now a pure request builder
    with no `FlightControlState` parameter at all (no more `phase` to
    transition); it returns only the `{"ok", "acted"|"reason"}` result."""

    def test_overlay_flying_is_a_silent_no_op(self) -> None:
        result = take_controls(
            overlay_flying=True,
            on_ground=False,
            attack_run_engaged=False,
        )
        assert result == {"ok": True, "acted": False}

    def test_on_ground_refuses(self) -> None:
        result = take_controls(
            overlay_flying=False,
            on_ground=True,
            attack_run_engaged=False,
        )
        assert result == {"ok": False, "reason": "ON_GROUND"}

    def test_attack_run_engaged_refuses(self) -> None:
        result = take_controls(
            overlay_flying=False,
            on_ground=False,
            attack_run_engaged=True,
        )
        assert result == {"ok": False, "reason": "ATTACK_RUN_ENGAGED"}

    def test_refusal_order_is_ground_then_attack_run(self) -> None:
        """Both refusals true at once -- `ON_GROUND` wins, pinning the
        plan's own check order."""
        result = take_controls(
            overlay_flying=False,
            on_ground=True,
            attack_run_engaged=True,
        )
        assert result == {"ok": False, "reason": "ON_GROUND"}

    def test_a_clean_take_succeeds(self) -> None:
        result = take_controls(
            overlay_flying=False,
            on_ground=False,
            attack_run_engaged=False,
        )
        assert result == {"ok": True, "acted": True}


class TestReleaseControls:
    """BL-16 Stage 3 -- `release_controls` takes `flying_axes` (the
    caller's own `flight_authority_state.fd_mode in ("taking", "m1")`)
    in place of the deleted `state.phase`/`state.lua_mode` check."""

    def test_overlay_flying_is_unable(self) -> None:
        result = release_controls(overlay_flying=True, flying_axes=False)
        assert result == {"ok": False, "reason": "AI_OVERLAY"}

    def test_flying_axes_acts(self) -> None:
        result = release_controls(overlay_flying=False, flying_axes=True)
        assert result == {"ok": True, "acted": True}

    def test_not_flying_axes_is_a_silent_no_op(self) -> None:
        result = release_controls(overlay_flying=False, flying_axes=False)
        assert result == {"ok": True, "acted": False}


class TestClampHelpers:
    def test_clamp_altitude_agl_has_no_floor_only_a_non_negative_bound(self) -> None:
        """BL-16 M3 (`plans/flight-lift-vector/plan.md`, section A): the
        AGL floor clamp is gone -- "allow player to command any
        altitude and then accept it." `FLOOR_AGL_M` is applied inside
        `Export.lua`'s law (against the goal, as `F_eff`), never here;
        this clamp now only rejects a negative height."""
        assert clamp_altitude(FLOOR_AGL_M - 10.0, "agl") == FLOOR_AGL_M - 10.0
        assert clamp_altitude(FLOOR_AGL_M + 10.0, "agl") == FLOOR_AGL_M + 10.0
        assert clamp_altitude(-5.0, "agl") == 0.0
        assert clamp_altitude(0.0, "agl") == 0.0

    def test_clamp_altitude_baro_passes_through_unclamped(self) -> None:
        assert clamp_altitude(0.0, "baro") == 0.0
        assert clamp_altitude(-50.0, "baro") == -50.0

    def test_clamp_speed_has_no_floor_only_a_ceiling(self) -> None:
        """BL-16 lift-vector law, Stage LV-1 (U8, "no floor"): the
        lower bound is gone entirely -- `clamp_speed` only ever ceils
        now."""
        assert clamp_speed(-10.0) == 0.0
        assert clamp_speed(0.0) == 0.0
        assert clamp_speed(MAX_IAS_KMH + 10.0) == MAX_IAS_KMH
        assert clamp_speed(150.0) == 150.0


class TestWireHelpers:
    def test_flight_control_limits_carries_the_given_on_ground_threshold(self) -> None:
        limits = flight_control_limits(12.5)
        assert limits["on_ground_agl_threshold_m"] == 12.5
        assert "min_ias_kmh" not in limits
        assert limits["max_ias_kmh"] == MAX_IAS_KMH

    def test_flight_control_limits_carries_m2s_shaper_limits_and_bands(self) -> None:
        """M2's own additions to the wire `limits` bundle -- the
        shaper's own rate limit (`max_turn_bank_deg`/`max_accel_mps2`)
        and A9's bands, all sent so `Export.lua`'s control law has one
        source of truth for behaviour. **`max_climb_vs_mps` removed
        (BL-16 M3, `plans/flight-lift-vector/plan.md`, section C)** --
        "no number limit, limit comes from available power"; a power
        governor inside `Export.lua`'s law replaces it."""
        limits = flight_control_limits(12.5)
        for key in (
            "max_turn_bank_deg",
            "max_accel_mps2",
            "speed_band_frac",
            "alt_band_frac",
            "alt_band_min_m",
            "turn_rate_band_frac",
            "heading_band_deg",
        ):
            assert key in limits
            assert isinstance(limits[key], float)
        assert "max_climb_vs_mps" not in limits

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

    def test_goal_request_fields_carries_the_break_rate_override(self) -> None:
        """Mode-1 batch, Decision 27 -- `turn_rate_deg_s` rides the wire
        only when a command actually set it (e.g. `axes_break_turn`),
        never for an ordinary heading command."""
        assert goal_request_fields(
            FlightControlGoalRequest(heading_deg=90.0, turn_rate_deg_s=-40.0)
        ) == {"heading_deg": 90.0, "turn_rate_deg_s": -40.0}
        assert "turn_rate_deg_s" not in goal_request_fields(
            FlightControlGoalRequest(heading_deg=90.0)
        )

    def test_flight_control_limits_has_no_max_bank_deg_and_carries_the_rotor_envelope(
        self,
    ) -> None:
        """F-M1 (mode-1 batch): "remove the 30 degree limit. Set no
        limit for now" -- `max_bank_deg` is removed from the wire
        entirely, not widened. Decisions 29-31 add the rotor-RPM floor,
        the retreating-blade-stall IAS, the break's own height-loss
        budget, and the VRS descent cap."""
        limits = flight_control_limits(12.5)
        assert "max_bank_deg" not in limits
        for key in (
            "rotor_rpm_floor_pct",
            "retreating_blade_stall_ias_kmh",
            "break_max_height_loss_m",
            "vrs_ias_threshold_kmh",
            "vrs_max_descent_mps",
        ):
            assert key in limits
            assert isinstance(limits[key], float)
