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
    rules_version: str | None = None,
    put_rules_response: dict[str, object] | None = None,
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

        def do_PUT(self) -> None:
            if self.path == "/rules":
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = json.loads(self.rfile.read(length))
                received.append(body)
                self._respond(
                    status,
                    put_rules_response
                    if put_rules_response is not None
                    else {
                        "version": body.get("version"),
                        "accepted": [],
                        "rejected": [],
                    },
                )
                return
            self._respond(404, {"error": "not found"})

        def do_GET(self) -> None:
            if self.path == "/transcripts/poll":
                self._respond(
                    status,
                    transcripts if transcripts is not None else [],
                    extra_headers=(
                        {"X-Rules-Version": rules_version}
                        if rules_version is not None
                        else None
                    ),
                )
                return
            self._respond(404, {"error": "not found"})

        def _respond(
            self,
            status: int,
            body: object,
            extra_headers: dict[str, str] | None = None,
        ) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            for name, value in (extra_headers or {}).items():
                self.send_header(name, value)
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


def test_push_speech_speaks_tilde_as_about(
    server_and_received: tuple[HTTPServer, list[dict[str, object]]],
) -> None:
    """Piper reads "~800" as "tilde 800" (2026-10-20 sortie)."""
    httpd, received = server_and_received
    client = AudioAdapterClient(base_url=f"http://127.0.0.1:{httpd.server_port}")
    client.push_speech("Fuel for ~ 20 minutes, road ~800 metres.", urgent=False)
    assert received[0]["text"] == "Fuel for about 20 minutes, road about 800 metres."


def test_push_speech_includes_correlation_id_when_given(
    server_and_received: tuple[HTTPServer, list[dict[str, object]]],
) -> None:
    """`plans/voice-latency-instrumentation/plan.md` Stage 3."""
    httpd, received = server_and_received
    client = AudioAdapterClient(f"http://127.0.0.1:{httpd.server_port}")
    client.push_speech("Contact.", urgent=False, correlation_id="corr-bl-1")
    assert received[0]["correlation_id"] == "corr-bl-1"


def test_push_speech_unreachable_host_raises() -> None:
    client = AudioAdapterClient("http://127.0.0.1:1", timeout_s=1.0)
    with pytest.raises(AudioAdapterError):
        client.push_speech("hello", urgent=False)


@contextmanager
def _start_server(
    transcripts: list[dict[str, object]] | None = None,
    rules_version: str | None = None,
    put_rules_response: dict[str, object] | None = None,
    received: list[dict[str, object]] | None = None,
) -> Iterator[HTTPServer]:
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        _make_handler(
            received if received is not None else [],
            transcripts=transcripts,
            rules_version=rules_version,
            put_rules_response=put_rules_response,
        ),
    )
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
        assert client.get_transcripts() == ([], None)


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
        assert client.get_transcripts() == (events, None)


def test_get_transcripts_unreachable_host_raises() -> None:
    client = AudioAdapterClient("http://127.0.0.1:1", timeout_s=1.0)
    with pytest.raises(AudioAdapterError):
        client.get_transcripts()


def test_get_transcripts_returns_the_rules_version_header() -> None:
    """`[[BL-17]]` D2 -- absent until the first successful `put_rules`;
    present (and read back verbatim) once the adapter has one."""
    with _start_server(transcripts=[], rules_version="abc123") as httpd:
        client = AudioAdapterClient(f"http://127.0.0.1:{httpd.server_port}")
        _, rules_version = client.get_transcripts()
        assert rules_version == "abc123"


def test_put_rules_posts_version_and_rules() -> None:
    received: list[dict[str, object]] = []
    with _start_server(received=received) as httpd:
        client = AudioAdapterClient(f"http://127.0.0.1:{httpd.server_port}")
        client.put_rules(
            "v1",
            [("turn_heading_relative", "turn <d:left|right>", "flight_control")],
        )
    assert received == [
        {
            "version": "v1",
            "rules": [
                {
                    "id": "turn_heading_relative",
                    "pattern": "turn <d:left|right>",
                    "category": "flight_control",
                }
            ],
        }
    ]


def test_put_rules_parses_accepted_and_rejected() -> None:
    with _start_server(
        put_rules_response={
            "version": "v1",
            "accepted": ["turn_heading_relative"],
            "rejected": [{"id": "bad_rule", "reason": "bad grammar"}],
        }
    ) as httpd:
        client = AudioAdapterClient(f"http://127.0.0.1:{httpd.server_port}")
        result = client.put_rules(
            "v1",
            [("turn_heading_relative", "turn <d:left|right>", "flight_control")],
        )
    assert result.version == "v1"
    assert result.accepted == ("turn_heading_relative",)
    assert result.rejected == (("bad_rule", "bad grammar"),)


def test_put_rules_unreachable_host_raises() -> None:
    client = AudioAdapterClient("http://127.0.0.1:1", timeout_s=1.0)
    with pytest.raises(AudioAdapterError):
        client.put_rules("v1", [])
