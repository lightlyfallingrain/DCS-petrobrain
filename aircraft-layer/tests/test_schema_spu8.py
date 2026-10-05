"""The SPU-8 intercom panel: schema, cache, line routing, and the
`GET /spu8/state` endpoint (`plans/spu8-intercom/plan.md` Stage 1).

Mirrors `test_ptt.py`'s structure exactly -- same raw-plus-decided shape,
same "arg animates through intermediate values, threshold don't equate"
reasoning, applied to three args (377/664/457) instead of one (738).
"""

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
    Spu8Cache,
    Spu8GateState,
    TelemetryCache,
    WorldObjectsCache,
)
from collector.server import CollectorServer
from schema import Spu8ParseError, Spu8Sample


class TestSpu8Sample:
    def test_parses_a_line(self) -> None:
        sample = Spu8Sample.from_json_line(
            '{"t":11.423,"net1":1.000,"ics_power":1.000,"vol":0.750}',
            received_wall_clock_s=99.0,
        )
        assert sample.dcs_model_time_s == pytest.approx(11.423)
        assert sample.received_wall_clock_s == 99.0
        assert sample.net1 == pytest.approx(1.0)
        assert sample.ics_power == pytest.approx(1.0)
        assert sample.vol == pytest.approx(0.75)

    def test_gate_is_open_only_when_both_switches_are_on(self) -> None:
        both_on = Spu8Sample(1.0, 2.0, net1=1.0, ics_power=1.0, vol=1.0)
        net1_off = Spu8Sample(1.0, 2.0, net1=0.0, ics_power=1.0, vol=1.0)
        ics_off = Spu8Sample(1.0, 2.0, net1=1.0, ics_power=0.0, vol=1.0)
        both_off = Spu8Sample(1.0, 2.0, net1=0.0, ics_power=0.0, vol=1.0)

        assert both_on.gate_open is True
        assert net1_off.gate_open is False
        assert ics_off.gate_open is False
        assert both_off.gate_open is False

    def test_the_switches_threshold_at_half_not_equality(self) -> None:
        """377/664 animate through intermediate values (observed live:
        0.32, 0.64) for ~0.1s on a flip -- a reader must threshold, not
        test equality."""
        mid_transit = Spu8Sample(1.0, 2.0, net1=0.64, ics_power=1.0, vol=1.0)
        assert mid_transit.net1_on is True

        still_low = Spu8Sample(1.0, 2.0, net1=0.32, ics_power=1.0, vol=1.0)
        assert still_low.net1_on is False

    def test_a_missing_value_is_a_parse_error(self) -> None:
        with pytest.raises(Spu8ParseError):
            Spu8Sample.from_dict({"t": 1.0, "net1": 1.0}, received_wall_clock_s=2.0)

    def test_a_non_numeric_value_is_a_parse_error(self) -> None:
        with pytest.raises(Spu8ParseError):
            Spu8Sample.from_dict(
                {"t": 1.0, "net1": "on", "ics_power": 1.0, "vol": 1.0},
                received_wall_clock_s=2.0,
            )

    def test_a_boolean_is_not_a_number(self) -> None:
        with pytest.raises(Spu8ParseError):
            Spu8Sample.from_dict(
                {"t": 1.0, "net1": True, "ics_power": 1.0, "vol": 1.0},
                received_wall_clock_s=2.0,
            )

    def test_to_api_dict_carries_raw_and_decided_fields(self) -> None:
        sample = Spu8Sample(11.423, 99.0, net1=1.0, ics_power=0.0, vol=0.6)
        assert sample.to_api_dict() == {
            "t": pytest.approx(11.423),
            "received_wall_clock_s": pytest.approx(99.0),
            "net1": pytest.approx(1.0),
            "ics_power": pytest.approx(0.0),
            "vol": pytest.approx(0.6),
            "net1_on": True,
            "ics_power_on": False,
            "gate_open": False,
        }


class TestSpu8Cache:
    def test_empty_until_a_line_arrives(self) -> None:
        assert Spu8Cache().latest() is None

    def test_keeps_only_the_latest(self) -> None:
        cache = Spu8Cache()
        cache.push(Spu8Sample(1.0, 2.0, net1=1.0, ics_power=1.0, vol=1.0))
        cache.push(Spu8Sample(2.0, 3.0, net1=0.0, ics_power=1.0, vol=0.5))
        latest = cache.latest()
        assert latest is not None
        assert latest.net1 == 0.0

    def test_gate_state_is_fail_safe_closed_when_empty(self) -> None:
        """Plan Decision 3: an unknown SPU-8 state must not let anything
        through, in either direction."""
        assert Spu8Cache().gate_state() == Spu8GateState(gate_open=False, volume=1.0)

    def test_gate_state_reflects_the_latest_sample(self) -> None:
        cache = Spu8Cache()
        cache.push(Spu8Sample(1.0, 2.0, net1=1.0, ics_power=1.0, vol=0.3))
        assert cache.gate_state() == Spu8GateState(gate_open=True, volume=0.3)

        cache.push(Spu8Sample(2.0, 3.0, net1=0.0, ics_power=1.0, vol=0.3))
        assert cache.gate_state() == Spu8GateState(gate_open=False, volume=0.3)


class TestCollectorRouting:
    def _collector(self, spu8_cache: Spu8Cache) -> CollectorServer:
        return CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            spu8_cache=spu8_cache,
        )

    def test_a_net1_line_reaches_the_cache(self) -> None:
        cache = Spu8Cache()
        self._collector(cache)._handle_line(
            '{"t":1.0,"net1":1.0,"ics_power":1.0,"vol":0.8}'
        )
        latest = cache.latest()
        assert latest is not None
        assert latest.gate_open is True

    def test_a_net1_line_is_never_parsed_as_telemetry(self) -> None:
        """It routes ahead of the telemetry fallthrough; reaching that
        would log every SPU-8 change as a malformed sample."""
        telemetry = TelemetryCache()
        cache = Spu8Cache()
        collector = CollectorServer(
            telemetry,
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            spu8_cache=cache,
        )
        collector._handle_line('{"t":1.0,"net1":1.0,"ics_power":1.0,"vol":0.8}')
        assert telemetry.latest() is None
        assert cache.latest() is not None

    def test_a_collector_with_no_spu8_cache_drops_the_line(self) -> None:
        """Correct behaviour rather than an error: nothing downstream is
        listening, and every pre-existing construction site passes no
        cache."""
        collector = CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
        )
        collector._handle_line(  # must not raise
            '{"t":1.0,"net1":1.0,"ics_power":1.0,"vol":0.8}'
        )

    def test_a_malformed_net1_line_is_dropped_not_raised(self) -> None:
        cache = Spu8Cache()
        self._collector(cache)._handle_line(
            '{"t":1.0,"net1":"nope","ics_power":1.0,"vol":0.8}'
        )
        assert cache.latest() is None


class TestSpu8Endpoint:
    @pytest.fixture
    def server(self) -> Iterator[tuple[str, Spu8Cache]]:
        cache = Spu8Cache()
        api = TelemetryAPIServer(
            TelemetryCache(), host="127.0.0.1", port=0, spu8_cache=cache
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
        with urllib.request.urlopen(f"{base_url}/spu8/state", timeout=5) as response:
            return json.loads(response.read())

    def test_null_before_the_first_line_arrives(
        self, server: tuple[str, Spu8Cache]
    ) -> None:
        base_url, _ = server
        assert self._get(base_url) is None

    def test_serves_the_raw_values_and_decided_fields(
        self, server: tuple[str, Spu8Cache]
    ) -> None:
        base_url, cache = server
        cache.push(Spu8Sample(11.423, 99.0, net1=1.0, ics_power=0.0, vol=0.5))
        payload = self._get(base_url)
        assert payload == {
            "t": pytest.approx(11.423),
            "received_wall_clock_s": pytest.approx(99.0),
            "net1": pytest.approx(1.0),
            "ics_power": pytest.approx(0.0),
            "vol": pytest.approx(0.5),
            "net1_on": True,
            "ics_power_on": False,
            "gate_open": False,
        }
