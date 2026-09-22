"""Tests for `transcribe_client.TranscribeClient`.

Against a real loopback `http.server`, not a mocked `urllib` -- the same
posture `test_aircraft_client.py` uses and for the same reason: this
client's whole job is a wire format, and a mock would agree with whatever
shape the client sent. The field name asserted here (`wav_b64`) is the
one `server.py`'s `POST /transcribe` actually reads; getting it wrong
would fail only on the real adapter.
"""

from __future__ import annotations

import base64
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from transcribe_client import TranscribeClient, TranscribeError


def _make_handler(
    received: list[dict[str, object]], status: int = 200
) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path == "/transcribe":
                length = int(self.headers.get("Content-Length", "0") or "0")
                received.append(json.loads(self.rfile.read(length)))
                self._respond(status, {"ok": status == 200})
                return
            self._respond(404, {"error": "not found"})

        def _respond(self, status: int, body: dict[str, object]) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return _Handler


@pytest.fixture
def server_and_received() -> Iterator[tuple[HTTPServer, list[dict[str, object]]]]:
    received: list[dict[str, object]] = []
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(received))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd, received
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def test_transcribe_posts_the_wav_as_base64(
    server_and_received: tuple[HTTPServer, list[dict[str, object]]],
) -> None:
    httpd, received = server_and_received
    TranscribeClient(f"http://127.0.0.1:{httpd.server_port}").transcribe(b"RIFF-WAV")

    assert len(received) == 1
    assert base64.b64decode(str(received[0]["wav_b64"])) == b"RIFF-WAV"


def test_transcribe_sends_nothing_else(
    server_and_received: tuple[HTTPServer, list[dict[str, object]]],
) -> None:
    """Capture knows nothing about recognition -- no model name, no
    engine, no urgency. One field is the whole contract."""
    httpd, received = server_and_received
    TranscribeClient(f"http://127.0.0.1:{httpd.server_port}").transcribe(b"x")
    assert list(received[0]) == ["wav_b64"]


def test_non_2xx_raises(
    server_and_received: tuple[HTTPServer, list[dict[str, object]]],
) -> None:
    """A 503 here is the ordinary case -- an adapter running without
    `--whisper-model` has no recogniser -- and it must surface rather
    than look like a clip that went through."""
    received: list[dict[str, object]] = []
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler(received, status=503))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        client = TranscribeClient(f"http://127.0.0.1:{httpd.server_port}")
        with pytest.raises(TranscribeError):
            client.transcribe(b"x")
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def test_unreachable_adapter_raises() -> None:
    client = TranscribeClient("http://127.0.0.1:1", timeout_s=0.5)
    with pytest.raises(TranscribeError, match="failed"):
        client.transcribe(b"x")
