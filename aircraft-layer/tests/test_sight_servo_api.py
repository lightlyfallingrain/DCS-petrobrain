"""The 9K113 DCS-slave servo's status feed (`plans/9k113-sight-pointing/
plan.md`, BL-B80 v2): schema, cache, line routing, and the
`GET /sight_servo/latest` endpoint.

Mirrors `test_cockpit_switch.py`'s `TestCollectorRouting`/
`TestCockpitSwitchLatestEndpoint` structure -- same "not an error"
`None`-before-first-sample posture, same routing-ahead-of-telemetry
shape, with the wire key `"servo_mode"` and a read-only endpoint (no
write side; this is a status feed body-layer only ever reads)."""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import (
    PetrovichIndicationCache,
    PetrovichWheelCache,
    SightServoCache,
    TelemetryCache,
    WorldObjectsCache,
)
from collector.server import CollectorServer
from schema import SightServoParseError, SightServoState

_LINE = (
    '{"t":1.5,"servo_mode":"closed","setpoint_azimuth_deg":12.0,'
    '"setpoint_elevation_deg":-3.0,"mark_azimuth_deg":12.01,'
    '"mark_elevation_deg":-2.99,"error_azimuth_deg":-0.01,'
    '"error_elevation_deg":-0.01,"stalled":false,"stall_count":0,'
    '"field_target_azimuth_deg":12.0,"field_target_elevation_deg":-3.0,'
    '"mark_clipped":false}'
)


class TestSightServoState:
    def test_parses_a_line(self) -> None:
        sample = SightServoState.from_json_line(_LINE, received_wall_clock_s=99.0)
        assert sample.dcs_model_time_s == pytest.approx(1.5)
        assert sample.received_wall_clock_s == 99.0
        assert sample.mode == "closed"
        assert sample.setpoint_azimuth_deg == pytest.approx(12.0)
        assert sample.mark_azimuth_deg == pytest.approx(12.01)
        assert sample.error_azimuth_deg == pytest.approx(-0.01)
        assert sample.stalled is False
        assert sample.stall_count == 0

    def test_null_mark_and_error_fields_parse_as_none(self) -> None:
        # "homing" (v3 rename of "open"): the schema does not validate
        # the string, so this is a label change only, not a behavioural
        # fix -- `plans/9k113-sight-pointing/plan.md` v3's own Affected
        # Files note.
        line = (
            '{"t":1.5,"servo_mode":"homing","setpoint_azimuth_deg":12.0,'
            '"setpoint_elevation_deg":-3.0,"mark_azimuth_deg":null,'
            '"mark_elevation_deg":null,"error_azimuth_deg":null,'
            '"error_elevation_deg":null,"stalled":false,"stall_count":2,'
            '"field_target_azimuth_deg":null,"field_target_elevation_deg":null,'
            '"mark_clipped":true}'
        )
        sample = SightServoState.from_json_line(line, received_wall_clock_s=99.0)
        assert sample.mark_azimuth_deg is None
        assert sample.error_azimuth_deg is None
        assert sample.stall_count == 2
        assert sample.field_target_azimuth_deg is None
        assert sample.mark_clipped is True

    def test_missing_servo_mode_is_a_parse_error(self) -> None:
        with pytest.raises(SightServoParseError):
            SightServoState.from_json_line(
                '{"t":1.5,"stalled":false,"stall_count":0,"mark_clipped":false}',
                received_wall_clock_s=99.0,
            )

    def test_non_boolean_stalled_is_a_parse_error(self) -> None:
        with pytest.raises(SightServoParseError):
            SightServoState.from_json_line(
                '{"t":1.5,"servo_mode":"homing","stalled":"nope",'
                '"stall_count":0,"mark_clipped":false}',
                received_wall_clock_s=99.0,
            )

    def test_non_boolean_mark_clipped_is_a_parse_error(self) -> None:
        with pytest.raises(SightServoParseError):
            SightServoState.from_json_line(
                '{"t":1.5,"servo_mode":"closed","stalled":false,'
                '"stall_count":0,"mark_clipped":"nope"}',
                received_wall_clock_s=99.0,
            )

    def test_to_api_dict_carries_every_field(self) -> None:
        sample = SightServoState(
            dcs_model_time_s=1.5,
            received_wall_clock_s=99.0,
            mode="closed",
            setpoint_azimuth_deg=12.0,
            setpoint_elevation_deg=-3.0,
            mark_azimuth_deg=12.01,
            mark_elevation_deg=-2.99,
            error_azimuth_deg=-0.01,
            error_elevation_deg=-0.01,
            stalled=False,
            stall_count=0,
            field_target_azimuth_deg=12.0,
            field_target_elevation_deg=-3.0,
            mark_clipped=False,
        )
        assert sample.to_api_dict() == {
            "t": pytest.approx(1.5),
            "received_wall_clock_s": pytest.approx(99.0),
            "mode": "closed",
            "setpoint_azimuth_deg": pytest.approx(12.0),
            "setpoint_elevation_deg": pytest.approx(-3.0),
            "mark_azimuth_deg": pytest.approx(12.01),
            "mark_elevation_deg": pytest.approx(-2.99),
            "error_azimuth_deg": pytest.approx(-0.01),
            "error_elevation_deg": pytest.approx(-0.01),
            "stalled": False,
            "stall_count": 0,
            "field_target_azimuth_deg": pytest.approx(12.0),
            "field_target_elevation_deg": pytest.approx(-3.0),
            "mark_clipped": False,
        }


class TestSightServoCache:
    def test_empty_until_a_line_arrives(self) -> None:
        assert SightServoCache().latest() is None

    def test_keeps_only_the_latest(self) -> None:
        cache = SightServoCache()
        first = SightServoState.from_json_line(_LINE, received_wall_clock_s=1.0)
        second = SightServoState.from_json_line(_LINE, received_wall_clock_s=2.0)
        cache.push(first)
        cache.push(second)
        assert cache.latest() is second


class TestCollectorRouting:
    def _collector(self, sight_servo_cache: SightServoCache) -> CollectorServer:
        return CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            sight_servo_cache=sight_servo_cache,
        )

    def test_a_servo_mode_line_reaches_the_cache(self) -> None:
        cache = SightServoCache()
        self._collector(cache)._handle_line(_LINE)
        latest = cache.latest()
        assert latest is not None
        assert latest.mode == "closed"

    def test_a_servo_mode_line_is_never_parsed_as_telemetry(self) -> None:
        """It routes ahead of the telemetry fallthrough; reaching that
        would log every servo status update as a malformed sample."""
        telemetry = TelemetryCache()
        cache = SightServoCache()
        collector = CollectorServer(
            telemetry,
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            sight_servo_cache=cache,
        )
        collector._handle_line(_LINE)
        assert telemetry.latest() is None
        assert cache.latest() is not None

    def test_a_collector_with_no_sight_servo_cache_drops_the_line(self) -> None:
        """Correct behaviour rather than an error: nothing downstream is
        listening, and every pre-existing construction site passes no
        cache."""
        collector = CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
        )
        collector._handle_line(_LINE)  # must not raise

    def test_a_malformed_servo_mode_line_is_dropped_not_raised(self) -> None:
        cache = SightServoCache()
        self._collector(cache)._handle_line(
            '{"t":1.0,"servo_mode":123,"stalled":false,"stall_count":0}'
        )
        assert cache.latest() is None


class TestSightServoLatestEndpoint:
    @pytest.fixture
    def server(self) -> Iterator[tuple[str, SightServoCache]]:
        cache = SightServoCache()
        api = TelemetryAPIServer(
            TelemetryCache(), host="127.0.0.1", port=0, sight_servo_cache=cache
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
            f"{base_url}/sight_servo/latest", timeout=5
        ) as response:
            return json.loads(response.read())

    def test_null_before_the_first_line_arrives(
        self, server: tuple[str, SightServoCache]
    ) -> None:
        base_url, _ = server
        assert self._get(base_url) is None

    def test_serves_the_latest_sample(
        self, server: tuple[str, SightServoCache]
    ) -> None:
        base_url, cache = server
        cache.push(SightServoState.from_json_line(_LINE, received_wall_clock_s=99.0))
        payload = self._get(base_url)
        assert payload == {
            "t": pytest.approx(1.5),
            "received_wall_clock_s": pytest.approx(99.0),
            "mode": "closed",
            "setpoint_azimuth_deg": pytest.approx(12.0),
            "setpoint_elevation_deg": pytest.approx(-3.0),
            "mark_azimuth_deg": pytest.approx(12.01),
            "mark_elevation_deg": pytest.approx(-2.99),
            "error_azimuth_deg": pytest.approx(-0.01),
            "error_elevation_deg": pytest.approx(-0.01),
            "stalled": False,
            "stall_count": 0,
            "field_target_azimuth_deg": pytest.approx(12.0),
            "field_target_elevation_deg": pytest.approx(-3.0),
            "mark_clipped": False,
        }
