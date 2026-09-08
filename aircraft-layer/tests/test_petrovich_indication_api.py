"""Tests for `api.server`'s `GET /petrovich_indication/latest` endpoint."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import PetrovichIndicationCache, TelemetryCache, WorldObjectsCache
from schema import PetrovichIndicationSample


def _sample(t: float, wall: float) -> PetrovichIndicationSample:
    return PetrovichIndicationSample(
        dcs_model_time_s=t,
        received_wall_clock_s=wall,
        fields={"middle_list_text": "Ural truck"},
    )


@pytest.fixture
def running_server() -> Iterator[tuple[TelemetryAPIServer, PetrovichIndicationCache]]:
    cache = TelemetryCache()
    world_objects_cache = WorldObjectsCache()
    petrovich_indication_cache = PetrovichIndicationCache()
    server = TelemetryAPIServer(
        cache,
        world_objects_cache,
        host="127.0.0.1",
        port=0,
        petrovich_indication_cache=petrovich_indication_cache,
    )
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, petrovich_indication_cache
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


def test_petrovich_indication_latest_empty_cache_returns_null(
    running_server: tuple[TelemetryAPIServer, PetrovichIndicationCache],
) -> None:
    server, _cache = running_server
    status, body = _get(server, "/petrovich_indication/latest")
    assert status == 200
    assert body is None


def test_petrovich_indication_latest_returns_most_recent_sample(
    running_server: tuple[TelemetryAPIServer, PetrovichIndicationCache],
) -> None:
    server, cache = running_server
    cache.push(_sample(t=1.0, wall=100.0))
    cache.push(_sample(t=2.0, wall=101.0))

    status, body = _get(server, "/petrovich_indication/latest")

    assert status == 200
    assert isinstance(body, dict)
    assert body["dcs_model_time_s"] == 2.0
    assert body["received_wall_clock_s"] == 101.0
    assert body["fields"]["middle_list_text"] == "Ural truck"


def test_default_petrovich_indication_cache_answers_null_when_omitted() -> None:
    # A `TelemetryAPIServer` constructed without a
    # `petrovich_indication_cache` (every pre-stage-4 call site) must keep
    # working -- its `/petrovich_indication/latest` just always answers null.
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _get(server, "/petrovich_indication/latest")
        assert status == 200
        assert body is None
    finally:
        server.close()
        thread.join(timeout=5)
