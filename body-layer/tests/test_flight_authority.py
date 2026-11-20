"""Tests for `belief.flight_authority` -- BL-16 (`plans/
flight-desired-state/plan.md`, Stages 1-2). `advance_flight_authority`
is exercised against a real loopback `http.server` instance via a real
`AircraftLayerClient`, same posture as `test_flight_control.py`'s own
convention (the project's "no mocked `urllib`" rule). `decide_flight_
speech` is pure, so it is exercised directly against `FlightAuthority
State` values, no server needed."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from aircraft_client import AircraftLayerClient
from belief.flight_authority import (
    FlightAuthorityState,
    advance_flight_authority,
    decide_flight_speech,
)


class _Handler(BaseHTTPRequestHandler):
    sample: dict[str, Any] | None = None

    def do_GET(self) -> None:
        body = json.dumps(self.sample).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def server_with_sample() -> Iterator[str]:
    _Handler.sample = {
        "t": 12.5,
        "fd_mode": "m1",
        "fd_mode_cause": "take",
        "fd_mode_n": 3,
        "fd_has_m2": True,
        "fd_hdg_mode": "heading",
        "fd_heading": 90.0,
        "fd_hdg_ref": "true",
        "fd_turn_dir": None,
        "fd_turn_rate": None,
        "fd_turn_style": "normal",
        "fd_alt": 300.0,
        "fd_alt_ref": "agl",
        "fd_ias": 150.0,
        "fd_manoeuvre": "none",
        "fd_manoeuvre_seq": 0,
        "fd_stamp_hdg": 1,
        "fd_stamp_alt": 1,
        "fd_stamp_spd": 1,
        "fd_hdg_true_deg": 90.5,
        "fd_hdg_mag_deg": 97.8,
        "fd_measured_agl": 300.0,
        "fd_measured_msl": 350.0,
        "fd_measured_ias": 150.0,
        "fd_overlay_course": 71.0,
        "fd_reset_epoch": 42,
    }
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


@pytest.fixture
def server_with_null() -> Iterator[str]:
    _Handler.sample = None
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


class TestAdvanceFlightAuthority:
    def test_a_sample_is_parsed_into_the_mirror(self, server_with_sample: str) -> None:
        client = AircraftLayerClient(base_url=server_with_sample)
        state = advance_flight_authority(FlightAuthorityState(), client)
        assert state.fd_mode == "m1"
        assert state.mode_cause == "take"
        assert state.mode_n == 3
        assert state.has_m2 is True
        assert state.hdg_mode == "heading"
        assert state.heading_deg == pytest.approx(90.0)
        assert state.hdg_ref == "true"
        assert state.alt_m == pytest.approx(300.0)
        assert state.alt_ref == "agl"
        assert state.ias_kmh == pytest.approx(150.0)
        assert state.hdg_true_deg == pytest.approx(90.5)
        assert state.hdg_mag_deg == pytest.approx(97.8)
        assert state.overlay_course_deg == pytest.approx(71.0)
        assert state.reset_epoch == 42

    def test_a_null_sample_leaves_state_unchanged(self, server_with_null: str) -> None:
        client = AircraftLayerClient(base_url=server_with_null)
        original = FlightAuthorityState(fd_mode="m2", mode_n=7)
        state = advance_flight_authority(original, client)
        assert state == original


class TestDecideFlightSpeech:
    def test_no_mode_n_on_either_side_is_a_no_op(self) -> None:
        assert (
            decide_flight_speech(FlightAuthorityState(), FlightAuthorityState()) is None
        )

    def test_an_unchanged_mode_n_is_a_no_op(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=1)
        new = FlightAuthorityState(fd_mode="m1", mode_n=1)
        assert decide_flight_speech(prev, new) is None

    def test_a_take_edge_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="off", mode_n=1)
        new = FlightAuthorityState(fd_mode="m1", mode_n=2, mode_cause="take")
        assert decide_flight_speech(prev, new) is None

    def test_a_park_edge_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=2)
        new = FlightAuthorityState(fd_mode="m2", mode_n=3, mode_cause="park")
        assert decide_flight_speech(prev, new) is None

    def test_a_successful_unpark_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="m2", mode_n=3)
        new = FlightAuthorityState(fd_mode="m1", mode_n=4, mode_cause="unpark")
        assert decide_flight_speech(prev, new) is None

    def test_a_player_release_into_off_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=2)
        new = FlightAuthorityState(fd_mode="off", mode_n=3, mode_cause="release")
        assert decide_flight_speech(prev, new) is None

    def test_a_mission_stop_into_off_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="m2", mode_n=3)
        new = FlightAuthorityState(fd_mode="off", mode_n=4, mode_cause="stop")
        assert decide_flight_speech(prev, new) is None

    def test_a_body_layer_reset_into_off_is_silent(self) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=2)
        new = FlightAuthorityState(fd_mode="off", mode_n=3, mode_cause="reset")
        assert decide_flight_speech(prev, new) is None

    @pytest.mark.parametrize(
        "cause", ["unpark_refused", "unpark_unarmed", "envelope", "nan", "dead"]
    )
    def test_a_forced_handover_into_off_is_urgent(self, cause: str) -> None:
        prev = FlightAuthorityState(fd_mode="m1", mode_n=2)
        new = FlightAuthorityState(fd_mode="off", mode_n=3, mode_cause=cause)
        decision = decide_flight_speech(prev, new)
        assert decision is not None
        assert decision.says == "You have controls!"
        assert decision.urgent is True
