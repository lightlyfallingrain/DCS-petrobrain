"""Tests for `tts_engine.PiperEngine` -- Piper's `piper.http_server` client
(`plans/audio-adapter-os-independent/plan.md` Decision 1).

Exercised against a real loopback `http.server.HTTPServer` double rather
than a mocked `urllib`, mirroring `test_aircraft_client.py`'s "real socket,
not a double" posture -- cheap to spin up and catches real wire-format
mismatches a mock would paper over. No live Piper needed for this class.

Also covers the outage-announcement state machine (Decision 3's amendment):
the first synthesis failure after a success (or ever) logs one `WARNING`
line naming the cause; later failures in the same outage log at `DEBUG`
only; the first success after an outage logs one `WARNING` recovery line.

Plus one skip-gated live test (mirroring `test_stt_engine.py`'s
`AUDIO_ADAPTER_WHISPER_BINARY`/`_MODEL` env-var convention):
`AUDIO_ADAPTER_PIPER_URL`, exercising a real running `piper.http_server`
end to end for a developer who has one up."""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tts_engine import DEFAULT_PIPER_VOICE, PiperEngine, TTSSynthesisError

_FAKE_WAV = b"RIFF\x00\x00\x00\x00WAVEfake-audio-bytes"


def _make_handler(
    received: list[dict[str, object]], responses: list[tuple[int, bytes]]
) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path == "/synthesize":
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = json.loads(self.rfile.read(length))
                received.append(body)
                status, payload = responses.pop(0) if responses else (200, _FAKE_WAV)
                self.send_response(status)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    return _Handler


@pytest.fixture
def server_received_responses() -> Iterator[
    tuple[HTTPServer, list[dict[str, object]], list[tuple[int, bytes]]]
]:
    received: list[dict[str, object]] = []
    responses: list[tuple[int, bytes]] = []
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(received, responses))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd, received, responses
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


_ServerFixture = tuple[HTTPServer, list[dict[str, object]], list[tuple[int, bytes]]]


def test_synthesize_posts_text_and_voice_returns_wav_bytes(
    server_received_responses: _ServerFixture,
) -> None:
    httpd, received, responses = server_received_responses
    responses.append((200, _FAKE_WAV))
    engine = PiperEngine(
        base_url=f"http://127.0.0.1:{httpd.server_port}", voice="test-voice"
    )

    audio = engine.synthesize("Watching Charlie one seven.")

    assert audio == _FAKE_WAV
    assert received[0]["text"] == "Watching Charlie one seven."
    assert received[0]["voice"] == "test-voice"


def test_default_voice_is_sent_when_not_overridden(
    server_received_responses: _ServerFixture,
) -> None:
    httpd, received, responses = server_received_responses
    responses.append((200, _FAKE_WAV))
    engine = PiperEngine(base_url=f"http://127.0.0.1:{httpd.server_port}")

    engine.synthesize("hello")

    assert received[0]["voice"] == DEFAULT_PIPER_VOICE


def test_synthesize_empty_text_raises() -> None:
    engine = PiperEngine(base_url="http://127.0.0.1:1")
    with pytest.raises(TTSSynthesisError):
        engine.synthesize("")


def test_synthesize_whitespace_only_text_raises() -> None:
    engine = PiperEngine(base_url="http://127.0.0.1:1")
    with pytest.raises(TTSSynthesisError):
        engine.synthesize("   ")


def test_synthesize_connection_refused_raises() -> None:
    engine = PiperEngine(base_url="http://127.0.0.1:1", timeout_s=1.0)
    with pytest.raises(TTSSynthesisError):
        engine.synthesize("hello")


def test_synthesize_non_200_raises(
    server_received_responses: _ServerFixture,
) -> None:
    httpd, _received, responses = server_received_responses
    responses.append((500, b"voice not found"))
    engine = PiperEngine(base_url=f"http://127.0.0.1:{httpd.server_port}")

    with pytest.raises(TTSSynthesisError):
        engine.synthesize("hello")


def test_synthesize_empty_response_raises(
    server_received_responses: _ServerFixture,
) -> None:
    httpd, _received, responses = server_received_responses
    responses.append((200, b""))
    engine = PiperEngine(base_url=f"http://127.0.0.1:{httpd.server_port}")

    with pytest.raises(TTSSynthesisError):
        engine.synthesize("hello")


# -- outage announcement state machine (Decision 3's amendment) -------------


def test_first_failure_logs_one_warning_line_naming_unreachable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="tts_engine")
    engine = PiperEngine(base_url="http://127.0.0.1:1", timeout_s=1.0)

    with pytest.raises(TTSSynthesisError):
        engine.synthesize("hello")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "unreachable" in warnings[0].getMessage().lower()


def test_second_consecutive_failure_logs_only_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="tts_engine")
    engine = PiperEngine(base_url="http://127.0.0.1:1", timeout_s=1.0)

    with pytest.raises(TTSSynthesisError):
        engine.synthesize("hello")
    caplog.clear()
    with pytest.raises(TTSSynthesisError):
        engine.synthesize("hello")

    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []
    assert len([r for r in caplog.records if r.levelno == logging.DEBUG]) == 1


def test_first_success_after_outage_logs_one_recovery_line(
    server_received_responses: _ServerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    httpd, _received, responses = server_received_responses
    caplog.set_level(logging.DEBUG, logger="tts_engine")
    responses.extend([(500, b"down"), (200, _FAKE_WAV)])
    engine = PiperEngine(base_url=f"http://127.0.0.1:{httpd.server_port}")

    with pytest.raises(TTSSynthesisError):
        engine.synthesize("hello")
    caplog.clear()

    audio = engine.synthesize("hello")

    assert audio == _FAKE_WAV
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "back" in warnings[0].getMessage().lower()


def test_success_with_no_prior_outage_logs_nothing_at_warning(
    server_received_responses: _ServerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    httpd, _received, responses = server_received_responses
    caplog.set_level(logging.DEBUG, logger="tts_engine")
    responses.append((200, _FAKE_WAV))
    engine = PiperEngine(base_url=f"http://127.0.0.1:{httpd.server_port}")

    engine.synthesize("hello")

    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


# -- live test against a real `piper.http_server` (skip-gated) --------------

#: Overridable via environment variable so a dev machine with a real Piper
#: server running somewhere can exercise this engine end to end -- mirrors
#: `test_stt_engine.py`'s `AUDIO_ADAPTER_WHISPER_BINARY`/`_MODEL` convention.
_LIVE_PIPER_URL = os.environ.get("AUDIO_ADAPTER_PIPER_URL", "")


@pytest.mark.skipif(
    not _LIVE_PIPER_URL,
    reason=(
        "AUDIO_ADAPTER_PIPER_URL not set -- no live piper.http_server to test against"
    ),
)
def test_synthesize_against_real_piper_http_server() -> None:
    engine = PiperEngine(base_url=_LIVE_PIPER_URL)
    audio = engine.synthesize("Watching Charlie one seven.")
    assert audio.startswith(b"RIFF")
