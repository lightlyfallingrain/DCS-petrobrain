"""Tests for `api.server`'s `GET /mission_start/latest` endpoint --
`plans/bl15-mission-start/plan.md` (BL-15 Stage 1). Mirrors
`test_unit_velocity_api.py`'s pattern."""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import MissionStartCache, TelemetryCache
from schema import MissionStartEvent


def _event(sequence: int = 1, theatre: str | None = "Syria") -> MissionStartEvent:
    return MissionStartEvent(
        sequence=sequence, theatre=theatre, received_wall_clock_s=1000.0
    )


@pytest.fixture
def running_server() -> Iterator[tuple[TelemetryAPIServer, MissionStartCache]]:
    cache = TelemetryCache()
    mission_start_cache = MissionStartCache()
    server = TelemetryAPIServer(
        cache, host="127.0.0.1", port=0, mission_start_cache=mission_start_cache
    )
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, mission_start_cache
    finally:
        server.close()


def test_empty_cache_returns_null(
    running_server: tuple[TelemetryAPIServer, MissionStartCache],
) -> None:
    server, _cache = running_server
    with urllib.request.urlopen(
        f"http://127.0.0.1:{server.port}/mission_start/latest"
    ) as response:
        body = json.loads(response.read())
    assert body is None


def test_pushed_event_is_returned(
    running_server: tuple[TelemetryAPIServer, MissionStartCache],
) -> None:
    server, cache = running_server
    cache.push(_event(sequence=3, theatre="Afghanistan"))
    with urllib.request.urlopen(
        f"http://127.0.0.1:{server.port}/mission_start/latest"
    ) as response:
        body = json.loads(response.read())
    assert body == {
        "sequence": 3,
        "theatre": "Afghanistan",
        "received_wall_clock_s": 1000.0,
    }


def test_null_theatre_is_returned_as_json_null(
    running_server: tuple[TelemetryAPIServer, MissionStartCache],
) -> None:
    server, cache = running_server
    cache.push(_event(sequence=1, theatre=None))
    with urllib.request.urlopen(
        f"http://127.0.0.1:{server.port}/mission_start/latest"
    ) as response:
        body = json.loads(response.read())
    assert body["theatre"] is None


def test_without_configured_cache_returns_null() -> None:
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.port}/mission_start/latest"
        ) as response:
            body = json.loads(response.read())
        assert body is None
    finally:
        server.close()
