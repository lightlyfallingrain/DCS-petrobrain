"""Tests for `api.server`'s `POST /audio/stop` endpoint (`plans/
inbound-speech/plan.md` Stage 3 follow-up, the interrupt-only stop path).
Structural copy of `test_audio_play_api.py`'s pattern, against a recording
`AudioPlaybackSender` double (no real `winsound` call in automated tests) --
simpler than `/audio/play` since this endpoint reads no request body."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from api.server import TelemetryAPIServer
from collector.audio_sender import AudioPlaybackSender
from collector.cache import TelemetryCache


class _RecordingAudioPlaybackSender(AudioPlaybackSender):
    """An `AudioPlaybackSender` double that records `interrupt()` calls
    instead of touching a real (or fake) `WavPlayer`/worker thread."""

    def __init__(self) -> None:
        super().__init__()
        self.interrupt_calls = 0

    def interrupt(self) -> None:
        self.interrupt_calls += 1


@pytest.fixture
def running_server_with_sender() -> Iterator[
    tuple[TelemetryAPIServer, _RecordingAudioPlaybackSender]
]:
    cache = TelemetryCache()
    sender = _RecordingAudioPlaybackSender()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0, audio_sender=sender)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, sender
    finally:
        server.close()
        thread.join(timeout=5)


def _post(server: TelemetryAPIServer, path: str) -> tuple[int, object]:
    url = f"http://127.0.0.1:{server.port}{path}"
    request = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(request) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_audio_stop_forwards_to_sender_interrupt(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingAudioPlaybackSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, body = _post(server, "/audio/stop")
    assert status == 200
    assert body == {"ok": True}
    assert sender.interrupt_calls == 1


def test_audio_stop_without_configured_sender_returns_503() -> None:
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _post(server, "/audio/stop")
        assert status == 503
        assert isinstance(body, dict)
        assert "error" in body
    finally:
        server.close()
        thread.join(timeout=5)
