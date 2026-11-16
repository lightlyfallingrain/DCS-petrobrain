"""Tests for `belief.ai_pilot_wheel` -- BL-16 mode 2 Stage P1 (`plans/
flight-control/plan.md`, "Revised 2026-11-15"). `advance_parked_flight_
state` is exercised against a real loopback `http.server` instance via a
real `AircraftLayerClient`, same posture as `test_aircraft_client.py`'s
own convention (and the project's stated "no mocked `urllib`" rule) --
not a mocked client double."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar

import pytest

from aircraft_client import AircraftLayerClient
from belief.ai_pilot_wheel import (
    ParkedFlightState,
    advance_parked_flight_state,
    seat_change,
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
