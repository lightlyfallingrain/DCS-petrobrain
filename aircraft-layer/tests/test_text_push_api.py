"""Tests for `api.server`'s `POST /text/push` endpoint (BL-2.5)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.cache import TelemetryCache
from collector.text_sender import TextOverlaySender


class _RecordingTextOverlaySender(TextOverlaySender):
    """A `TextOverlaySender` double that records calls instead of sending UDP."""

    def __init__(self) -> None:
        super().__init__()
        self.sent_lines: list[str] = []

    def send_line(self, text: str) -> None:
        self.sent_lines.append(text)


@pytest.fixture
def running_server_with_sender() -> Iterator[
    tuple[TelemetryAPIServer, _RecordingTextOverlaySender]
]:
    cache = TelemetryCache()
    sender = _RecordingTextOverlaySender()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0, text_sender=sender)
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


def test_text_push_valid_forwards_to_sender(
    running_server_with_sender: tuple[TelemetryAPIServer, _RecordingTextOverlaySender],
) -> None:
    server, sender = running_server_with_sender
    status, body = _post(server, "/text/push", {"text": "CONTACT_DETECTED: BMP-2"})
    assert status == 200
    assert body == {"ok": True}
    assert sender.sent_lines == ["CONTACT_DETECTED: BMP-2"]


def test_text_push_missing_text_field_returns_400(
    running_server_with_sender: tuple[TelemetryAPIServer, _RecordingTextOverlaySender],
) -> None:
    server, sender = running_server_with_sender
    status, body = _post(server, "/text/push", {})
    assert status == 400
    assert isinstance(body, dict)
    assert "error" in body
    assert sender.sent_lines == []


def test_text_push_non_string_text_returns_400(
    running_server_with_sender: tuple[TelemetryAPIServer, _RecordingTextOverlaySender],
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(server, "/text/push", {"text": 123})
    assert status == 400
    assert sender.sent_lines == []


def test_text_push_empty_string_returns_400(
    running_server_with_sender: tuple[TelemetryAPIServer, _RecordingTextOverlaySender],
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(server, "/text/push", {"text": "   "})
    assert status == 400
    assert sender.sent_lines == []


def test_text_push_non_json_body_returns_400(
    running_server_with_sender: tuple[TelemetryAPIServer, _RecordingTextOverlaySender],
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(server, "/text/push", b"not json")
    assert status == 400
    assert sender.sent_lines == []


def test_text_push_without_configured_sender_returns_503() -> None:
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _post(server, "/text/push", {"text": "hello"})
        assert status == 503
        assert isinstance(body, dict)
        assert "error" in body
    finally:
        server.close()
        thread.join(timeout=5)
