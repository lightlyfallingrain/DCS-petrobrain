"""Tests for `api.server`'s `GET /line_of_sight/latest` and
`POST /command/look_direction` endpoints -- `plans/dcs-driven-los/plan.md`
(X-B29). Mirrors `test_unit_velocity_api.py` and `test_petrovich_search_api.
py`'s own structures."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import LineOfSightCache, TelemetryCache
from collector.command_sender import CommandSendError, LookDirectionSender
from schema.line_of_sight import LineOfSightSnapshot


def _snapshot() -> LineOfSightSnapshot:
    return LineOfSightSnapshot.from_wire(
        "172|12|12|3|45|1234.5|Truck-1:1:0",
        bridge_call_ms=1.6,
        received_wall_clock_s=1000.0,
    )


class _RecordingLookDirectionSender(LookDirectionSender):
    """A `LookDirectionSender` double that records calls instead of
    sending UDP -- mirrors `test_petrovich_search_api.py`'s own
    `_RecordingCommandSender`."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[int, int]] = []
        self.raise_on_send = False

    def send_look_direction(self, hour: int, fov_half_deg: int) -> None:  # type: ignore[override]
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.sent.append((hour, fov_half_deg))


@pytest.fixture
def running_server() -> Iterator[tuple[TelemetryAPIServer, LineOfSightCache]]:
    cache = TelemetryCache()
    line_of_sight_cache = LineOfSightCache()
    server = TelemetryAPIServer(
        cache, host="127.0.0.1", port=0, line_of_sight_cache=line_of_sight_cache
    )
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, line_of_sight_cache
    finally:
        server.close()
        thread.join(timeout=5)


@pytest.fixture
def running_server_with_sender() -> Iterator[
    tuple[TelemetryAPIServer, _RecordingLookDirectionSender]
]:
    cache = TelemetryCache()
    sender = _RecordingLookDirectionSender()
    server = TelemetryAPIServer(
        cache, host="127.0.0.1", port=0, look_direction_sender=sender
    )
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, sender
    finally:
        server.close()
        thread.join(timeout=5)


def _post(server: TelemetryAPIServer, path: str, body: object) -> tuple[int, object]:
    url = f"http://127.0.0.1:{server.port}{path}"
    data = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_empty_cache_returns_null(
    running_server: tuple[TelemetryAPIServer, LineOfSightCache],
) -> None:
    server, _cache = running_server
    with urllib.request.urlopen(
        f"http://127.0.0.1:{server.port}/line_of_sight/latest"
    ) as response:
        body = json.loads(response.read())
    assert body is None


def test_pushed_snapshot_is_returned(
    running_server: tuple[TelemetryAPIServer, LineOfSightCache],
) -> None:
    server, cache = running_server
    cache.push(_snapshot())
    with urllib.request.urlopen(
        f"http://127.0.0.1:{server.port}/line_of_sight/latest"
    ) as response:
        body = json.loads(response.read())
    assert body["units_in_bubble"] == 172
    assert body["verdicts"]["Truck-1"]["building_clear"] is True


def test_look_direction_valid_forwards_to_sender(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, body = _post(
        server, "/command/look_direction", {"hour": 3, "fov_half_deg": 90}
    )
    assert status == 200
    assert body == {"ok": True}
    assert sender.sent == [(3, 90)]


def test_look_direction_missing_fields_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, body = _post(server, "/command/look_direction", {"hour": 3})
    assert status == 400
    assert isinstance(body, dict)
    assert "error" in body
    assert sender.sent == []


@pytest.mark.parametrize("hour", [-1, 12, 1.5, "3", True])
def test_look_direction_invalid_hour_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
    hour: object,
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(
        server, "/command/look_direction", {"hour": hour, "fov_half_deg": 45}
    )
    assert status == 400
    assert sender.sent == []


@pytest.mark.parametrize("fov_half_deg", [4, 181, 45.5, "45"])
def test_look_direction_invalid_fov_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
    fov_half_deg: object,
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(
        server, "/command/look_direction", {"hour": 0, "fov_half_deg": fov_half_deg}
    )
    assert status == 400
    assert sender.sent == []


def test_look_direction_without_configured_sender_returns_503() -> None:
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _post(
            server, "/command/look_direction", {"hour": 0, "fov_half_deg": 45}
        )
        assert status == 503
        assert isinstance(body, dict)
        assert "error" in body
    finally:
        server.close()
        thread.join(timeout=5)


def test_look_direction_send_failure_returns_500(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
) -> None:
    server, sender = running_server_with_sender
    sender.raise_on_send = True
    status, body = _post(
        server, "/command/look_direction", {"hour": 0, "fov_half_deg": 45}
    )
    assert status == 500
    assert isinstance(body, dict)
    assert "error" in body
