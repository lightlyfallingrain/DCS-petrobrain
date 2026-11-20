"""BL-16 (`plans/flight-desired-state/plan.md`, Stages 1-2): schema,
cache, line routing, and the `GET /flight_desired/latest` endpoint.
Mirrors `test_flight_control_api.py`'s own read-side structure."""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import (
    FlightDesiredCache,
    PetrovichIndicationCache,
    PetrovichWheelCache,
    TelemetryCache,
    WorldObjectsCache,
)
from collector.server import CollectorServer
from schema import FlightDesiredParseError, FlightDesiredState

_LINE = (
    '{"t":12.5,"fd_mode":"m1","fd_mode_cause":"take","fd_mode_n":3,'
    '"fd_has_m2":true,"fd_hdg_mode":"heading","fd_heading":90.0,'
    '"fd_hdg_ref":"true","fd_turn_dir":null,"fd_turn_rate":null,'
    '"fd_turn_style":"normal","fd_alt":300.0,"fd_alt_ref":"agl",'
    '"fd_ias":150.0,"fd_manoeuvre":"none","fd_manoeuvre_seq":0,'
    '"fd_stamp_hdg":1,"fd_stamp_alt":1,"fd_stamp_spd":1,'
    '"fd_hdg_true_deg":90.5,"fd_hdg_mag_deg":97.8,'
    '"fd_measured_agl":300.0,"fd_measured_msl":350.0,'
    '"fd_measured_ias":150.0,"fd_overlay_course":71.0,'
    '"fd_reset_epoch":42}'
)


class TestFlightDesiredState:
    def test_parses_a_line(self) -> None:
        sample = FlightDesiredState.from_json_line(_LINE, received_wall_clock_s=99.0)
        assert sample.dcs_model_time_s == pytest.approx(12.5)
        assert sample.fd_mode == "m1"
        assert sample.mode_cause == "take"
        assert sample.mode_n == 3
        assert sample.has_m2 is True
        assert sample.hdg_mode == "heading"
        assert sample.heading_deg == pytest.approx(90.0)
        assert sample.hdg_ref == "true"
        assert sample.alt_m == pytest.approx(300.0)
        assert sample.alt_ref == "agl"
        assert sample.ias_kmh == pytest.approx(150.0)
        assert sample.hdg_true_deg == pytest.approx(90.5)
        assert sample.hdg_mag_deg == pytest.approx(97.8)
        assert sample.overlay_course_deg == pytest.approx(71.0)
        assert sample.reset_epoch == 42

    def test_missing_t_is_a_parse_error(self) -> None:
        with pytest.raises(FlightDesiredParseError):
            FlightDesiredState.from_json_line(
                '{"fd_mode":"off"}', received_wall_clock_s=0.0
            )

    def test_missing_fd_mode_is_a_parse_error(self) -> None:
        with pytest.raises(FlightDesiredParseError):
            FlightDesiredState.from_json_line('{"t":1.0}', received_wall_clock_s=0.0)

    def test_missing_fd_has_m2_is_a_parse_error(self) -> None:
        with pytest.raises(FlightDesiredParseError):
            FlightDesiredState.from_json_line(
                '{"t":1.0,"fd_mode":"off"}', received_wall_clock_s=0.0
            )

    def test_absent_optional_fields_parse_as_none(self) -> None:
        line = '{"t":1.0,"fd_mode":"off","fd_has_m2":false}'
        sample = FlightDesiredState.from_json_line(line, received_wall_clock_s=0.0)
        assert sample.mode_cause is None
        assert sample.mode_n is None
        assert sample.hdg_mode is None
        assert sample.heading_deg is None
        assert sample.turn_dir is None
        assert sample.reset_epoch is None

    def test_to_api_dict_carries_every_field(self) -> None:
        sample = FlightDesiredState.from_json_line(_LINE, received_wall_clock_s=99.0)
        assert sample.to_api_dict() == {
            "t": pytest.approx(12.5),
            "received_wall_clock_s": pytest.approx(99.0),
            "fd_mode": "m1",
            "fd_mode_cause": "take",
            "fd_mode_n": 3,
            "fd_has_m2": True,
            "fd_hdg_mode": "heading",
            "fd_heading": pytest.approx(90.0),
            "fd_hdg_ref": "true",
            "fd_turn_dir": None,
            "fd_turn_rate": None,
            "fd_turn_style": "normal",
            "fd_alt": pytest.approx(300.0),
            "fd_alt_ref": "agl",
            "fd_ias": pytest.approx(150.0),
            "fd_manoeuvre": "none",
            "fd_manoeuvre_seq": 0,
            "fd_stamp_hdg": 1,
            "fd_stamp_alt": 1,
            "fd_stamp_spd": 1,
            "fd_hdg_true_deg": pytest.approx(90.5),
            "fd_hdg_mag_deg": pytest.approx(97.8),
            "fd_measured_agl": pytest.approx(300.0),
            "fd_measured_msl": pytest.approx(350.0),
            "fd_measured_ias": pytest.approx(150.0),
            "fd_overlay_course": pytest.approx(71.0),
            "fd_reset_epoch": 42,
            "fd_epoch": None,
            "fd_last_seq": None,
            "fd_acks": None,
        }


class TestFlightDesiredCache:
    def test_empty_until_a_line_arrives(self) -> None:
        assert FlightDesiredCache().latest() is None

    def test_keeps_only_the_latest(self) -> None:
        cache = FlightDesiredCache()
        first = FlightDesiredState.from_json_line(_LINE, received_wall_clock_s=1.0)
        second = FlightDesiredState.from_json_line(_LINE, received_wall_clock_s=2.0)
        cache.push(first)
        cache.push(second)
        assert cache.latest() is second


class TestCollectorRouting:
    def _collector(self, flight_desired_cache: FlightDesiredCache) -> CollectorServer:
        return CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            flight_desired_cache=flight_desired_cache,
        )

    def test_an_fd_line_reaches_the_cache(self) -> None:
        cache = FlightDesiredCache()
        self._collector(cache)._handle_line(_LINE)
        latest = cache.latest()
        assert latest is not None
        assert latest.fd_mode == "m1"

    def test_an_fd_line_is_never_parsed_as_telemetry(self) -> None:
        telemetry = TelemetryCache()
        cache = FlightDesiredCache()
        collector = CollectorServer(
            telemetry,
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            flight_desired_cache=cache,
        )
        collector._handle_line(_LINE)
        assert telemetry.latest() is None
        assert cache.latest() is not None

    def test_a_collector_with_no_flight_desired_cache_drops_the_line(self) -> None:
        collector = CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
        )
        collector._handle_line(_LINE)  # must not raise

    def test_a_malformed_fd_line_is_dropped_not_raised(self) -> None:
        cache = FlightDesiredCache()
        self._collector(cache)._handle_line('{"t":1.0,"fd_mode":3}')
        assert cache.latest() is None


class TestFlightDesiredLatestEndpoint:
    @pytest.fixture
    def server(self) -> Iterator[tuple[str, FlightDesiredCache]]:
        cache = FlightDesiredCache()
        api = TelemetryAPIServer(
            TelemetryCache(), host="127.0.0.1", port=0, flight_desired_cache=cache
        )
        api.open()
        thread = threading.Thread(target=api.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{api.port}", cache
        finally:
            api.close()
            thread.join(timeout=5)

    def _get(self, base_url: str) -> object:
        with urllib.request.urlopen(
            f"{base_url}/flight_desired/latest", timeout=5
        ) as response:
            return json.loads(response.read())

    def test_null_before_the_first_line_arrives(
        self, server: tuple[str, FlightDesiredCache]
    ) -> None:
        base_url, _ = server
        assert self._get(base_url) is None

    def test_serves_the_latest_sample(
        self, server: tuple[str, FlightDesiredCache]
    ) -> None:
        base_url, cache = server
        cache.push(FlightDesiredState.from_json_line(_LINE, received_wall_clock_s=99.0))
        payload = self._get(base_url)
        assert (
            payload
            == FlightDesiredState.from_json_line(
                _LINE, received_wall_clock_s=99.0
            ).to_api_dict()
        )
