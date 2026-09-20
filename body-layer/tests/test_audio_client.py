"""Tests for `belief.audio_client.AudioAdapterClient`.

Exercised against a real loopback `http.server` instance rather than a
mocked `urllib`, mirroring `test_aircraft_client.py`'s own pattern."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from belief.audio_client import AudioAdapterClient, AudioAdapterError


def _make_handler(
    received: list[dict[str, object]],
    status: int = 200,
    transcripts: list[dict[str, object]] | None = None,
) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path == "/speak":
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = json.loads(self.rfile.read(length))
                received.append(body)
                self._respond(status, {"ok": status == 200})
                return
            self._respond(404, {"error": "not found"})

        def do_GET(self) -> None:
            if self.path == "/transcripts/poll":
                self._respond(status, transcripts if transcripts is not None else [])
                return
            self._respond(404, {"error": "not found"})

        def _respond(self, status: int, body: object) -> None:
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


def test_push_speech_posts_text_and_urgent(
    server_and_received: tuple[HTTPServer, list[dict[str, object]]],
) -> None:
    httpd, received = server_and_received
    client = AudioAdapterClient(f"http://127.0.0.1:{httpd.server_port}")
    client.push_speech("Watching Charlie one seven.", urgent=False)

    assert received == [{"text": "Watching Charlie one seven.", "urgent": False}]


def test_push_speech_urgent_true(
    server_and_received: tuple[HTTPServer, list[dict[str, object]]],
) -> None:
    httpd, received = server_and_received
    client = AudioAdapterClient(f"http://127.0.0.1:{httpd.server_port}")
    client.push_speech("Missile launch, break right.", urgent=True)

    assert received[0]["urgent"] is True


def test_push_speech_unreachable_host_raises() -> None:
    client = AudioAdapterClient("http://127.0.0.1:1", timeout_s=1.0)
    with pytest.raises(AudioAdapterError):
        client.push_speech("hello", urgent=False)


@contextmanager
def _start_server(
    transcripts: list[dict[str, object]] | None,
) -> Iterator[HTTPServer]:
    httpd = HTTPServer(("127.0.0.1", 0), _make_handler([], transcripts=transcripts))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def test_get_transcripts_returns_empty_list_when_nothing_pending() -> None:
    with _start_server(transcripts=[]) as httpd:
        client = AudioAdapterClient(f"http://127.0.0.1:{httpd.server_port}")
        assert client.get_transcripts() == []


def test_get_transcripts_returns_pending_transcripts_in_order() -> None:
    events = [
        {
            "transcript": "scan left",
            "confidence": 0.9,
            "token": "scan_left",
            "match_ratio": 1.0,
            "verb_anchored": True,
            "ambiguous": False,
            "t_wall": 123.0,
        },
        {
            "transcript": "watch nearest",
            "confidence": 0.8,
            "token": "watch_nearest",
            "match_ratio": 1.0,
            "verb_anchored": True,
            "ambiguous": False,
            "t_wall": 124.0,
        },
    ]
    with _start_server(transcripts=events) as httpd:
        client = AudioAdapterClient(f"http://127.0.0.1:{httpd.server_port}")
        assert client.get_transcripts() == events


def test_get_transcripts_unreachable_host_raises() -> None:
    client = AudioAdapterClient("http://127.0.0.1:1", timeout_s=1.0)
    with pytest.raises(AudioAdapterError):
        client.get_transcripts()
