"""Tests for `api.server`'s `GET /world_objects/latest` endpoint."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import TelemetryCache, WorldObjectsCache
from schema import WorldObjectSample, WorldObjectsSnapshot


def _snapshot(t: float, wall: float) -> WorldObjectsSnapshot:
    return WorldObjectsSnapshot(
        dcs_model_time_s=t,
        received_wall_clock_s=wall,
        objects=(
            WorldObjectSample(
                object_id=7,
                object_type="BMP-2",
                coalition=1.0,
                lat_deg=35.1,
                lon_deg=35.9,
                altitude_m=50.0,
                heading_true_rad=1.2,
            ),
        ),
    )


@pytest.fixture
def running_server() -> Iterator[
    tuple[TelemetryAPIServer, TelemetryCache, WorldObjectsCache]
]:
    cache = TelemetryCache()
    world_objects_cache = WorldObjectsCache()
    server = TelemetryAPIServer(cache, world_objects_cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, cache, world_objects_cache
    finally:
        server.close()
        thread.join(timeout=5)


def _get(server: TelemetryAPIServer, path: str) -> tuple[int, object]:
    url = f"http://127.0.0.1:{server.port}{path}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_world_objects_latest_empty_cache_returns_null(
    running_server: tuple[TelemetryAPIServer, TelemetryCache, WorldObjectsCache],
) -> None:
    server, _cache, _world_objects_cache = running_server
    status, body = _get(server, "/world_objects/latest")
    assert status == 200
    assert body is None


def test_world_objects_latest_returns_most_recent_snapshot(
    running_server: tuple[TelemetryAPIServer, TelemetryCache, WorldObjectsCache],
) -> None:
    server, _cache, world_objects_cache = running_server
    world_objects_cache.push(_snapshot(t=1.0, wall=100.0))
    world_objects_cache.push(_snapshot(t=2.0, wall=101.0))

    status, body = _get(server, "/world_objects/latest")

    assert status == 200
    assert isinstance(body, dict)
    assert body["dcs_model_time_s"] == 2.0
    assert body["received_wall_clock_s"] == 101.0
    assert body["objects"][0]["object_type"] == "BMP-2"


def test_telemetry_and_world_objects_caches_are_independent(
    running_server: tuple[TelemetryAPIServer, TelemetryCache, WorldObjectsCache],
) -> None:
    server, _cache, world_objects_cache = running_server
    world_objects_cache.push(_snapshot(t=5.0, wall=200.0))

    telemetry_status, telemetry_body = _get(server, "/telemetry/latest")
    world_objects_status, world_objects_body = _get(server, "/world_objects/latest")

    assert telemetry_status == 200
    assert telemetry_body is None
    assert world_objects_status == 200
    assert isinstance(world_objects_body, dict)


def test_default_world_objects_cache_answers_null_when_omitted() -> None:
    # A `TelemetryAPIServer` constructed without a `world_objects_cache`
    # (every existing pre-stage-3 call site) must keep working -- its
    # `/world_objects/latest` just always answers null.
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _get(server, "/world_objects/latest")
        assert status == 200
        assert body is None
    finally:
        server.close()
        thread.join(timeout=5)
