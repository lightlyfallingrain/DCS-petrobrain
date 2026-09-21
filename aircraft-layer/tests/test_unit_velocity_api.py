"""Tests for `api.server`'s `GET /unit_velocity/latest` endpoint. Mirrors
`test_world_objects_api.py`'s pattern."""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import TelemetryCache, UnitVelocityCache
from schema.unit_velocity import UnitVelocitySnapshot


def _snapshot() -> UnitVelocitySnapshot:
    return UnitVelocitySnapshot.from_wire(
        "1|1234.5|Truck-1:1.0:0.0:2.0",
        bridge_call_ms=4.2,
        received_wall_clock_s=1000.0,
    )


@pytest.fixture
def running_server() -> Iterator[tuple[TelemetryAPIServer, UnitVelocityCache]]:
    cache = TelemetryCache()
    unit_velocity_cache = UnitVelocityCache()
    server = TelemetryAPIServer(
        cache, host="127.0.0.1", port=0, unit_velocity_cache=unit_velocity_cache
    )
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, unit_velocity_cache
    finally:
        server.close()


def test_empty_cache_returns_null(
    running_server: tuple[TelemetryAPIServer, UnitVelocityCache],
) -> None:
    server, _cache = running_server
    with urllib.request.urlopen(
        f"http://127.0.0.1:{server.port}/unit_velocity/latest"
    ) as response:
        body = json.loads(response.read())
    assert body is None


def test_pushed_snapshot_is_returned(
    running_server: tuple[TelemetryAPIServer, UnitVelocityCache],
) -> None:
    server, cache = running_server
    cache.push(_snapshot())
    with urllib.request.urlopen(
        f"http://127.0.0.1:{server.port}/unit_velocity/latest"
    ) as response:
        body = json.loads(response.read())
    assert body["unit_count"] == 1
    assert body["samples"]["Truck-1"]["vx"] == 1.0
