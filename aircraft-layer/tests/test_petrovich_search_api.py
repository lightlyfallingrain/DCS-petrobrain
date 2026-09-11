"""Tests for `api.server`'s `POST /command/petrovich_search` and
`GET /petrovich_wheel/latest` endpoints -- BL-6 (`plans/
bl6-commands-inspect-adapt/plan.md`). Mirrors `test_text_push_api.py`'s
structure, plus the raise-on-failure difference documented in
`collector.command_sender`'s module docstring."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import PetrovichWheelCache, TelemetryCache
from collector.command_sender import CommandSender, CommandSendError
from schema import PetrovichWheelSample


class _RecordingCommandSender(CommandSender):
    """A `CommandSender` double that records calls instead of sending UDP."""

    def __init__(self) -> None:
        super().__init__()
        self.sent_modes: list[str] = []
        self.raise_on_send = False

    def send_command(self, mode: str) -> None:  # type: ignore[override]
        if self.raise_on_send:
            raise CommandSendError("simulated failure")
        self.sent_modes.append(mode)


@pytest.fixture
def running_server_with_sender() -> Iterator[
    tuple[TelemetryAPIServer, _RecordingCommandSender]
]:
    cache = TelemetryCache()
    sender = _RecordingCommandSender()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0, command_sender=sender)
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


def _get(server: TelemetryAPIServer, path: str) -> tuple[int, object]:
    url = f"http://127.0.0.1:{server.port}{path}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_petrovich_search_valid_mode_forwards_to_sender(
    running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
) -> None:
    server, sender = running_server_with_sender
    status, body = _post(server, "/command/petrovich_search", {"mode": "forward"})
    assert status == 200
    assert body == {"ok": True}
    assert sender.sent_modes == ["forward"]


def test_petrovich_search_boresight_mode_forwards_to_sender(
    running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(server, "/command/petrovich_search", {"mode": "boresight"})
    assert status == 200
    assert sender.sent_modes == ["boresight"]


def test_petrovich_search_missing_mode_returns_400(
    running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
) -> None:
    server, sender = running_server_with_sender
    status, body = _post(server, "/command/petrovich_search", {})
    assert status == 400
    assert isinstance(body, dict)
    assert "error" in body
    assert sender.sent_modes == []


def test_petrovich_search_invalid_mode_returns_400(
    running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(server, "/command/petrovich_search", {"mode": "sideways"})
    assert status == 400
    assert sender.sent_modes == []


def test_petrovich_search_non_json_body_returns_400(
    running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(server, "/command/petrovich_search", b"not json")
    assert status == 400
    assert sender.sent_modes == []


def test_petrovich_search_without_configured_sender_returns_503() -> None:
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _post(server, "/command/petrovich_search", {"mode": "forward"})
        assert status == 503
        assert isinstance(body, dict)
        assert "error" in body
    finally:
        server.close()
        thread.join(timeout=5)


def test_petrovich_search_send_failure_returns_500(
    running_server_with_sender: tuple[TelemetryAPIServer, _RecordingCommandSender],
) -> None:
    server, sender = running_server_with_sender
    sender.raise_on_send = True
    status, body = _post(server, "/command/petrovich_search", {"mode": "forward"})
    assert status == 500
    assert isinstance(body, dict)
    assert "error" in body


def test_petrovich_wheel_latest_empty_cache_returns_null() -> None:
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _get(server, "/petrovich_wheel/latest")
        assert status == 200
        assert body is None
    finally:
        server.close()
        thread.join(timeout=5)


def test_petrovich_wheel_latest_returns_most_recent_sample() -> None:
    cache = TelemetryCache()
    wheel_cache = PetrovichWheelCache()
    server = TelemetryAPIServer(
        cache, host="127.0.0.1", port=0, petrovich_wheel_cache=wheel_cache
    )
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        wheel_cache.push(
            PetrovichWheelSample(
                dcs_model_time_s=2.0,
                received_wall_clock_s=101.0,
                fields={"state": "SEARCHING"},
            )
        )
        status, body = _get(server, "/petrovich_wheel/latest")
        assert status == 200
        assert isinstance(body, dict)
        assert body["dcs_model_time_s"] == 2.0
        assert body["fields"]["state"] == "SEARCHING"
    finally:
        server.close()
        thread.join(timeout=5)
