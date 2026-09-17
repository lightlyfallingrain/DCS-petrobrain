"""Tests for `api.server`'s `POST /audio/play` endpoint (BL-10 first slice,
`plans/tts-voice-output/plan.md`). Direct structural copy of
`test_text_push_api.py`'s pattern, against a recording `AudioPlaybackSender`
double (no real `winsound` call in automated tests)."""

from __future__ import annotations

import base64
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
    """An `AudioPlaybackSender` double that records calls instead of
    touching a real (or fake) `WavPlayer`/worker thread."""

    def __init__(self) -> None:
        super().__init__()
        self.played: list[tuple[bytes, bool]] = []

    def play_audio(self, audio: bytes, urgent: bool) -> None:
        self.played.append((audio, urgent))


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


def _post(server: TelemetryAPIServer, path: str, body: object) -> tuple[int, object]:
    url = f"http://127.0.0.1:{server.port}{path}"
    data = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_audio_play_valid_forwards_to_sender(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingAudioPlaybackSender
    ],
) -> None:
    server, sender = running_server_with_sender
    audio_b64 = base64.b64encode(b"FAKE-WAV-BYTES").decode("ascii")
    status, body = _post(
        server, "/audio/play", {"audio_b64": audio_b64, "urgent": False}
    )
    assert status == 200
    assert body == {"ok": True}
    assert sender.played == [(b"FAKE-WAV-BYTES", False)]


def test_audio_play_urgent_flag_threads_through(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingAudioPlaybackSender
    ],
) -> None:
    server, sender = running_server_with_sender
    audio_b64 = base64.b64encode(b"URGENT-WAV").decode("ascii")
    status, _body = _post(
        server, "/audio/play", {"audio_b64": audio_b64, "urgent": True}
    )
    assert status == 200
    assert sender.played == [(b"URGENT-WAV", True)]


def test_audio_play_urgent_defaults_to_false(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingAudioPlaybackSender
    ],
) -> None:
    server, sender = running_server_with_sender
    audio_b64 = base64.b64encode(b"DEFAULT-URGENT").decode("ascii")
    status, _body = _post(server, "/audio/play", {"audio_b64": audio_b64})
    assert status == 200
    assert sender.played == [(b"DEFAULT-URGENT", False)]


def test_audio_play_missing_audio_field_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingAudioPlaybackSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, body = _post(server, "/audio/play", {})
    assert status == 400
    assert isinstance(body, dict)
    assert "error" in body
    assert sender.played == []


def test_audio_play_non_string_audio_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingAudioPlaybackSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(server, "/audio/play", {"audio_b64": 123})
    assert status == 400
    assert sender.played == []


def test_audio_play_empty_string_audio_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingAudioPlaybackSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(server, "/audio/play", {"audio_b64": ""})
    assert status == 400
    assert sender.played == []


def test_audio_play_invalid_base64_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingAudioPlaybackSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(server, "/audio/play", {"audio_b64": "not-valid-base64!!!"})
    assert status == 400
    assert sender.played == []


def test_audio_play_non_bool_urgent_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingAudioPlaybackSender
    ],
) -> None:
    server, sender = running_server_with_sender
    audio_b64 = base64.b64encode(b"X").decode("ascii")
    status, _body = _post(
        server, "/audio/play", {"audio_b64": audio_b64, "urgent": "yes"}
    )
    assert status == 400
    assert sender.played == []


def test_audio_play_non_json_body_returns_400(
    running_server_with_sender: tuple[
        TelemetryAPIServer, _RecordingAudioPlaybackSender
    ],
) -> None:
    server, sender = running_server_with_sender
    status, _body = _post(server, "/audio/play", b"not json")
    assert status == 400
    assert sender.played == []


def test_audio_play_without_configured_sender_returns_503() -> None:
    cache = TelemetryCache()
    server = TelemetryAPIServer(cache, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        audio_b64 = base64.b64encode(b"X").decode("ascii")
        status, body = _post(server, "/audio/play", {"audio_b64": audio_b64})
        assert status == 503
        assert isinstance(body, dict)
        assert "error" in body
    finally:
        server.close()
        thread.join(timeout=5)
