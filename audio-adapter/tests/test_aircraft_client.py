"""Tests for `aircraft_client.AircraftLayerClient`/`AircraftLayerAudioSink`.

Exercised against a real loopback `http.server` instance rather than a
mocked `urllib`, mirroring `aircraft-layer/tests/test_api.py`'s and
`body-layer/tests/test_aircraft_client.py`'s own pattern -- cheap to spin
up and catches real wire-format mismatches a mock would paper over."""

from __future__ import annotations

import base64
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aircraft_client import (
    AircraftLayerAudioSink,
    AircraftLayerClient,
    AircraftLayerError,
)
from server import AudioDeliveryError


def _make_handler(
    received: list[dict[str, object]], status: int = 200
) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path == "/audio/play":
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = json.loads(self.rfile.read(length))
                received.append(body)
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


def test_play_audio_posts_base64_and_urgent(
    server_and_received: tuple[HTTPServer, list[dict[str, object]]],
) -> None:
    httpd, received = server_and_received
    client = AircraftLayerClient(f"http://127.0.0.1:{httpd.server_port}")
    client.play_audio(b"FAKE-WAV-BYTES", urgent=True)

    assert len(received) == 1
    body = received[0]
    assert body["urgent"] is True
    assert base64.b64decode(str(body["audio_b64"])) == b"FAKE-WAV-BYTES"


def test_play_audio_urgent_false(
    server_and_received: tuple[HTTPServer, list[dict[str, object]]],
) -> None:
    httpd, received = server_and_received
    client = AircraftLayerClient(f"http://127.0.0.1:{httpd.server_port}")
    client.play_audio(b"X", urgent=False)

    assert received[0]["urgent"] is False


def test_play_audio_unreachable_host_raises_aircraft_layer_error() -> None:
    client = AircraftLayerClient("http://127.0.0.1:1", timeout_s=1.0)
    with pytest.raises(AircraftLayerError):
        client.play_audio(b"X", urgent=False)


def test_audio_sink_deliver_wraps_transport_failure_as_audio_delivery_error() -> None:
    sink = AircraftLayerAudioSink("http://127.0.0.1:1", timeout_s=1.0)
    with pytest.raises(AudioDeliveryError):
        sink.deliver(b"X", False)


def test_audio_sink_deliver_succeeds_against_real_server(
    server_and_received: tuple[HTTPServer, list[dict[str, object]]],
) -> None:
    httpd, received = server_and_received
    sink = AircraftLayerAudioSink(f"http://127.0.0.1:{httpd.server_port}")
    sink.deliver(b"SINK-BYTES", True)

    assert len(received) == 1
    assert base64.b64decode(str(received[0]["audio_b64"])) == b"SINK-BYTES"
    assert received[0]["urgent"] is True
