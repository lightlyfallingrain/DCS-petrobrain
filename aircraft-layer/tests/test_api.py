from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import TelemetryCache
from schema import TelemetrySample


def _sample(t: float, wall: float) -> TelemetrySample:
    return TelemetrySample(
        dcs_model_time_s=t,
        received_wall_clock_s=wall,
        position_x_m=1.0,
        position_y_m=2.0,
        position_z_m=3.0,
        pitch_rad=0.1,
        bank_rad=0.2,
        yaw_rad=0.3,
        heading_true_rad=0.4,
        ias_mps=50.0,
        tas_mps=55.0,
        altitude_msl_m=100.0,
        altitude_agl_m=90.0,
        altitude_radar_m=None,
    )


@pytest.fixture
def running_server() -> Iterator[tuple[TelemetryAPIServer, TelemetryCache]]:
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, cache
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


def test_latest_empty_cache_returns_null(
    running_server: tuple[TelemetryAPIServer, TelemetryCache],
) -> None:
    server, _cache = running_server
    status, body = _get(server, "/telemetry/latest")
    assert status == 200
    assert body is None


def test_latest_returns_most_recent_sample(
    running_server: tuple[TelemetryAPIServer, TelemetryCache],
) -> None:
    server, cache = running_server
    cache.push(_sample(t=1.0, wall=100.0))
    cache.push(_sample(t=2.0, wall=101.0))
    status, body = _get(server, "/telemetry/latest")
    assert status == 200
    assert isinstance(body, dict)
    assert body["dcs_model_time_s"] == 2.0
    assert body["received_wall_clock_s"] == 101.0
    assert body["altitude_radar_m"] is None


def test_since_returns_only_later_samples_in_order(
    running_server: tuple[TelemetryAPIServer, TelemetryCache],
) -> None:
    server, cache = running_server
    cache.push(_sample(t=1.0, wall=100.0))
    cache.push(_sample(t=2.0, wall=101.0))
    cache.push(_sample(t=3.0, wall=102.0))
    status, body = _get(server, "/telemetry/since/100.0")
    assert status == 200
    assert isinstance(body, list)
    assert [s["dcs_model_time_s"] for s in body] == [2.0, 3.0]


def test_since_nothing_changed_returns_empty_list(
    running_server: tuple[TelemetryAPIServer, TelemetryCache],
) -> None:
    server, cache = running_server
    cache.push(_sample(t=1.0, wall=100.0))
    status, body = _get(server, "/telemetry/since/100.0")
    assert status == 200
    assert body == []


def test_since_invalid_timestamp_returns_400(
    running_server: tuple[TelemetryAPIServer, TelemetryCache],
) -> None:
    server, _cache = running_server
    status, body = _get(server, "/telemetry/since/not-a-number")
    assert status == 400
    assert isinstance(body, dict)
    assert "error" in body


def test_unknown_path_returns_404(
    running_server: tuple[TelemetryAPIServer, TelemetryCache],
) -> None:
    server, _cache = running_server
    status, _body = _get(server, "/nope")
    assert status == 404
