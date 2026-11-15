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
        self.probes_sent: list[tuple[int, list[tuple[int, int]]]] = []
        self.raise_on_probes_send = False

    def send_look_direction(self, hour: int, fov_half_deg: int) -> None:  # type: ignore[override]
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.sent.append((hour, fov_half_deg))

    def send_probe_points(  # type: ignore[override]
        self, seq: int, points: list[tuple[int, int]]
    ) -> None:
        if self.raise_on_probes_send:
            raise CommandSendError("simulated failure")
        self.probes_sent.append((seq, points))


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


# --- POST /command/probe_points (`plans/expected-area-look/plan.md`, --
# --- BL-B111, Stage 1) -- reuses the same LookDirectionSender instance ---


def test_probe_points_valid_forwards_to_sender(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, body = _post(
        server,
        "/command/probe_points",
        {"seq": 1, "points": [[100, -200], [300, 400]]},
    )
    assert status == 200
    assert body == {"ok": True}
    assert sender.probes_sent == [(1, [(100, -200), (300, 400)])]


def test_probe_points_empty_points_forwards_empty_list(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, body = _post(server, "/command/probe_points", {"seq": 0, "points": []})
    assert status == 200
    assert body == {"ok": True}
    assert sender.probes_sent == [(0, [])]


def test_probe_points_missing_fields_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, body = _post(server, "/command/probe_points", {"seq": 1})
    assert status == 400
    assert isinstance(body, dict)
    assert "error" in body
    assert sender.probes_sent == []


@pytest.mark.parametrize("seq", [-1, 1.5, "1", True, 2**31])
def test_probe_points_invalid_seq_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
    seq: object,
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(server, "/command/probe_points", {"seq": seq, "points": []})
    assert status == 400
    assert sender.probes_sent == []


def test_probe_points_too_many_points_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(
        server,
        "/command/probe_points",
        {"seq": 1, "points": [[0, 0]] * 7},
    )
    assert status == 400
    assert sender.probes_sent == []


@pytest.mark.parametrize(
    "point",
    [
        [0],  # wrong arity
        [0, 0, 0],
        ["0", 0],
        [0.5, 0],
        [True, 0],
        [2_000_001, 0],
        [0, -2_000_001],
    ],
)
def test_probe_points_invalid_point_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
    point: object,
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(
        server, "/command/probe_points", {"seq": 1, "points": [point]}
    )
    assert status == 400
    assert sender.probes_sent == []


def test_probe_points_without_configured_sender_returns_503() -> None:
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _post(server, "/command/probe_points", {"seq": 1, "points": []})
        assert status == 503
        assert isinstance(body, dict)
        assert "error" in body
    finally:
        server.close()
        thread.join(timeout=5)


def test_probe_points_send_failure_returns_500(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingLookDirectionSender
    ],
) -> None:
    server, sender = running_server_with_sender
    sender.raise_on_probes_send = True
    status, body = _post(server, "/command/probe_points", {"seq": 1, "points": []})
    assert status == 500
    assert isinstance(body, dict)
    assert "error" in body
