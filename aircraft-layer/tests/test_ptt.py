"""The push-to-talk feed: schema, cache, line routing, and the endpoint.

Arg 738 is a two-stage trigger -- 1.0 radio, 0.5 intercom, 0.0 released --
and this layer's job is to carry the number, not to decide what it means.
The one piece of interpretation that lives here is the pair of predicates,
and the interesting one is `intercom`: it is deliberately *not* DCS-SRS's
`raw >= 0.1`, which would treat a radio transmission as speech aimed at
the crew.
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
    PttCache,
    TelemetryCache,
    WorldObjectsCache,
)
from collector.server import CollectorServer
from schema import PttParseError, PttSample


class TestPttSample:
    def test_parses_a_line(self) -> None:
        sample = PttSample.from_json_line(
            '{"t":11.423,"ptt":0.500}', received_wall_clock_s=99.0
        )
        assert sample.dcs_model_time_s == pytest.approx(11.423)
        assert sample.received_wall_clock_s == 99.0
        assert sample.raw == pytest.approx(0.5)

    def test_the_intercom_stop_is_the_half_press(self) -> None:
        assert PttSample(1.0, 2.0, 0.5).intercom is True
        assert PttSample(1.0, 2.0, 0.0).intercom is False

    def test_a_full_press_is_the_radio_and_not_the_intercom(self) -> None:
        """The distinction the whole gate rests on: SRS gates on `>= 0.1`
        and would call this speech aimed at the crew. It is the player
        talking to someone else."""
        full = PttSample(1.0, 2.0, 1.0)
        assert full.radio is True
        assert full.intercom is False

    def test_a_released_trigger_is_neither(self) -> None:
        released = PttSample(1.0, 2.0, 0.0)
        assert released.radio is False
        assert released.intercom is False

    def test_the_stops_have_tolerance(self) -> None:
        """The argument is graduated and reported to three decimals; there
        is no guarantee a stop reads as exactly its declared value."""
        assert PttSample(1.0, 2.0, 0.497).intercom is True
        assert PttSample(1.0, 2.0, 0.981).radio is True

    def test_a_missing_value_is_a_parse_error(self) -> None:
        with pytest.raises(PttParseError):
            PttSample.from_dict({"t": 1.0}, received_wall_clock_s=2.0)

    def test_a_non_numeric_value_is_a_parse_error(self) -> None:
        with pytest.raises(PttParseError):
            PttSample.from_dict({"t": 1.0, "ptt": "0.5"}, received_wall_clock_s=2.0)

    def test_a_boolean_is_not_a_number(self) -> None:
        """`True` is an `int` in Python and would otherwise parse as 1.0 --
        a released trigger reported as a full press."""
        with pytest.raises(PttParseError):
            PttSample.from_dict({"t": 1.0, "ptt": True}, received_wall_clock_s=2.0)


class TestPttCache:
    def test_empty_until_the_trigger_moves(self) -> None:
        assert PttCache().latest() is None

    def test_keeps_only_the_latest(self) -> None:
        """The trigger is a state, not an event stream -- history is
        exactly what nobody wants here."""
        cache = PttCache()
        cache.push(PttSample(1.0, 2.0, 0.5))
        cache.push(PttSample(2.0, 3.0, 0.0))
        latest = cache.latest()
        assert latest is not None
        assert latest.raw == 0.0


class TestCollectorRouting:
    def _collector(self, ptt_cache: PttCache) -> CollectorServer:
        return CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            ptt_cache=ptt_cache,
        )

    def test_a_ptt_line_reaches_the_cache(self) -> None:
        cache = PttCache()
        self._collector(cache)._handle_line('{"t":1.0,"ptt":0.5}')
        latest = cache.latest()
        assert latest is not None
        assert latest.intercom is True

    def test_a_ptt_line_is_never_parsed_as_telemetry(self) -> None:
        """It routes ahead of the telemetry fallthrough; reaching that
        would log every press as a malformed sample."""
        telemetry = TelemetryCache()
        cache = PttCache()
        collector = CollectorServer(
            telemetry,
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
            ptt_cache=cache,
        )
        collector._handle_line('{"t":1.0,"ptt":0.5}')
        assert telemetry.latest() is None
        assert cache.latest() is not None

    def test_a_collector_with_no_ptt_cache_drops_the_line(self) -> None:
        """Correct behaviour rather than an error: nothing downstream is
        listening, and every pre-existing construction site passes no
        cache."""
        collector = CollectorServer(
            TelemetryCache(),
            WorldObjectsCache(),
            PetrovichIndicationCache(),
            PetrovichWheelCache(),
        )
        collector._handle_line('{"t":1.0,"ptt":0.5}')  # must not raise

    def test_a_malformed_ptt_line_is_dropped_not_raised(self) -> None:
        cache = PttCache()
        self._collector(cache)._handle_line('{"t":1.0,"ptt":"nope"}')
        assert cache.latest() is None


class TestPttEndpoint:
    @pytest.fixture
    def server(self) -> Iterator[tuple[str, PttCache]]:
        cache = PttCache()
        api = TelemetryAPIServer(
            TelemetryCache(), host="127.0.0.1", port=0, ptt_cache=cache
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
        with urllib.request.urlopen(f"{base_url}/ptt/state", timeout=5) as response:
            return json.loads(response.read())

    def test_null_before_the_trigger_has_moved(
        self, server: tuple[str, PttCache]
    ) -> None:
        base_url, _ = server
        assert self._get(base_url) is None

    def test_serves_the_raw_value_and_both_predicates(
        self, server: tuple[str, PttCache]
    ) -> None:
        """Both, deliberately: the raw value is the ground truth a consumer
        may want to debounce itself, and the booleans save every consumer
        re-deriving the same two thresholds."""
        base_url, cache = server
        cache.push(PttSample(11.423, 99.0, 0.5))
        payload = self._get(base_url)
        assert payload == {
            "t": pytest.approx(11.423),
            "received_wall_clock_s": pytest.approx(99.0),
            "raw": pytest.approx(0.5),
            "intercom": True,
            "radio": False,
        }
