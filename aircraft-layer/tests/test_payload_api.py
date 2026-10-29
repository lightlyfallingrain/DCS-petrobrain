"""The ownship loadout feed (`[[BL-B67]]`, `plans/bl-b67-atgm-run/plan.md`
Stage 4): schema, cache, line routing, and the `GET /payload/latest`
endpoint.

Mirrors `test_sight_servo_api.py`'s structure -- same "not an error"
`None`-before-first-sample posture, same routing-ahead-of-telemetry shape,
with the wire key `"stations"` and a read-only endpoint (no write side;
this is a status feed body-layer only ever reads)."""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import (
    PayloadCache,
    PetrovichIndicationCache,
    PetrovichWheelCache,
    TelemetryCache,
    WorldObjectsCache,
)
from collector.server import CollectorServer
from schema import PayloadParseError, PayloadSample, PayloadStation

_LINE = (
    '{"t":1.5,"current_station":1,"stations":['
    '{"index":1,"name":"9M114","count":4,"container":false},'
    '{"index":2,"name":"?","count":0,"container":true}]}'
)


class TestPayloadSample:
    def test_parses_a_line(self) -> None:
        sample = PayloadSample.from_json_line(_LINE, received_wall_clock_s=99.0)
        assert sample.dcs_model_time_s == pytest.approx(1.5)
        assert sample.received_wall_clock_s == 99.0
        assert sample.current_station == 1
        assert len(sample.stations) == 2
        assert sample.stations[0] == PayloadStation(
            index=1, name="9M114", count=4, container=False
        )
        assert sample.stations[1] == PayloadStation(
            index=2, name="?", count=0, container=True
        )

    def test_empty_stations_list_parses_cleanly(self) -> None:
        """An unloaded aircraft, or a Mi-24P on which `LoGetPayloadInfo`
        turns out to return no entries -- see the schema module's own
        docstring on why this must not be an error."""
        sample = PayloadSample.from_json_line(
            '{"t":1.0,"current_station":0,"stations":[]}',
            received_wall_clock_s=5.0,
        )
        assert sample.current_station == 0
        assert sample.stations == ()

    def test_missing_t_is_a_parse_error(self) -> None:
        with pytest.raises(PayloadParseError):
            PayloadSample.from_json_line(
                '{"current_station":0,"stations":[]}', received_wall_clock_s=1.0
            )

    def test_missing_current_station_is_a_parse_error(self) -> None:
        with pytest.raises(PayloadParseError):
            PayloadSample.from_json_line(
                '{"t":1.0,"stations":[]}', received_wall_clock_s=1.0
            )

    def test_non_array_stations_is_a_parse_error(self) -> None:
        with pytest.raises(PayloadParseError):
            PayloadSample.from_json_line(
                '{"t":1.0,"current_station":0,"stations":"nope"}',
                received_wall_clock_s=1.0,
            )

    def test_station_missing_count_is_a_parse_error(self) -> None:
        with pytest.raises(PayloadParseError):
            PayloadSample.from_json_line(
                '{"t":1.0,"current_station":0,"stations":'
                '[{"index":1,"name":"x","container":false}]}',
                received_wall_clock_s=1.0,
            )

    def test_station_non_string_name_is_a_parse_error(self) -> None:
        with pytest.raises(PayloadParseError):
            PayloadSample.from_json_line(
                '{"t":1.0,"current_station":0,"stations":'
                '[{"index":1,"name":7,"count":1,"container":false}]}',
                received_wall_clock_s=1.0,
            )

    def test_station_non_boolean_container_is_a_parse_error(self) -> None:
        with pytest.raises(PayloadParseError):
            PayloadSample.from_json_line(
                '{"t":1.0,"current_station":0,"stations":'
                '[{"index":1,"name":"x","count":1,"container":"nope"}]}',
                received_wall_clock_s=1.0,
            )

    def test_to_api_dict_carries_every_field(self) -> None:
        sample = PayloadSample.from_json_line(_LINE, received_wall_clock_s=99.0)
        assert sample.to_api_dict() == {
            "t": pytest.approx(1.5),
            "received_wall_clock_s": pytest.approx(99.0),
            "current_station": 1,
            "stations": [
                {"index": 1, "name": "9M114", "count": 4, "container": False},
                {"index": 2, "name": "?", "count": 0, "container": True},
            ],
        }


class TestPayloadCache:
    def test_empty_until_a_line_arrives(self) -> None:
        assert PayloadCache().latest() is None

    def test_keeps_only_the_latest(self) -> None:
        cache = PayloadCache()
        first = PayloadSample.from_json_line(_LINE, received_wall_clock_s=1.0)
        second = PayloadSample.from_json_line(_LINE, received_wall_clock_s=2.0)
        cache.push(first)
        cache.push(second)
        assert cache.latest() is second


class TestCollectorRouting:
    def _collector(self, payload_cache: PayloadCache) -> CollectorServer:
        return CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            payload_cache=payload_cache,
        )

    def test_a_stations_line_reaches_the_cache(self) -> None:
        cache = PayloadCache()
        self._collector(cache)._handle_line(_LINE)
        latest = cache.latest()
        assert latest is not None
        assert latest.current_station == 1

    def test_a_stations_line_is_never_parsed_as_telemetry(self) -> None:
        """It routes ahead of the telemetry fallthrough; reaching that
        would log every payload update as a malformed sample."""
        telemetry = TelemetryCache()
        cache = PayloadCache()
        collector = CollectorServer(
            telemetry,
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            payload_cache=cache,
        )
        collector._handle_line(_LINE)
        assert telemetry.latest() is None
        assert cache.latest() is not None

    def test_a_collector_with_no_payload_cache_drops_the_line(self) -> None:
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

    def test_a_malformed_stations_line_is_dropped_not_raised(self) -> None:
        cache = PayloadCache()
        self._collector(cache)._handle_line(
            '{"t":1.0,"current_station":0,"stations":"nope"}'
        )
        assert cache.latest() is None


class TestPayloadLatestEndpoint:
    @pytest.fixture
    def server(self) -> Iterator[tuple[str, PayloadCache]]:
        cache = PayloadCache()
        api = TelemetryAPIServer(
            TelemetryCache(), host="127.0.0.1", port=0, payload_cache=cache
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
            f"{base_url}/payload/latest", timeout=5
        ) as response:
            return json.loads(response.read())

    def test_null_before_the_first_line_arrives(
        self, server: tuple[str, PayloadCache]
    ) -> None:
        base_url, _ = server
        assert self._get(base_url) is None

    def test_serves_the_latest_sample(self, server: tuple[str, PayloadCache]) -> None:
        base_url, cache = server
        cache.push(PayloadSample.from_json_line(_LINE, received_wall_clock_s=99.0))
        payload = self._get(base_url)
        assert payload == {
            "t": pytest.approx(1.5),
            "received_wall_clock_s": pytest.approx(99.0),
            "current_station": 1,
            "stations": [
                {"index": 1, "name": "9M114", "count": 4, "container": False},
                {"index": 2, "name": "?", "count": 0, "container": True},
            ],
        }
