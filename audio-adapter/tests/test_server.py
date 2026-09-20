"""Tests for `server.TTSAdapterServer`'s `POST /speak` endpoint.

Structural copy of `aircraft-layer/tests/test_text_push_api.py`'s pattern:
a real loopback HTTP server, a recording double standing in for the real
`TTSEngine`/`AudioSink` collaborators."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from server import AudioDeliveryError, TTSAdapterServer
from tts_engine import TTSSynthesisError


class _FakeEngine:
    """Records requested text; returns a fixed fake WAV payload unless
    `should_fail` is set."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.requested_text: list[str] = []

    def synthesize(self, text: str) -> bytes:
        self.requested_text.append(text)
        if self.should_fail:
            raise TTSSynthesisError("synthesis failed (test double)")
        return b"FAKE-WAV-BYTES"


class _RecordingSink:
    """Records `(audio, urgent)` deliveries; raises `AudioDeliveryError`
    when `should_fail` is set."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.delivered: list[tuple[bytes, bool]] = []

    def deliver(self, audio: bytes, urgent: bool) -> None:
        if self.should_fail:
            raise AudioDeliveryError("delivery failed (test double)")
        self.delivered.append((audio, urgent))


@pytest.fixture
def running_server() -> Iterator[tuple[TTSAdapterServer, _FakeEngine, _RecordingSink]]:
    engine = _FakeEngine()
    sink = _RecordingSink()
    server = TTSAdapterServer(engine, sink, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, engine, sink
    finally:
        server.close()
        thread.join(timeout=5)


def _post(server: TTSAdapterServer, path: str, body: object) -> tuple[int, object]:
    url = f"http://127.0.0.1:{server.port}{path}"
    data = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_speak_valid_synthesizes_and_delivers(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, engine, sink = running_server
    status, body = _post(
        server, "/speak", {"text": "Watching Charlie one seven.", "urgent": False}
    )
    assert status == 200
    assert body == {"ok": True}
    assert engine.requested_text == ["Watching Charlie one seven."]
    assert sink.delivered == [(b"FAKE-WAV-BYTES", False)]


def test_speak_urgent_flag_threads_through_to_sink(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, _engine, sink = running_server
    status, _body = _post(
        server, "/speak", {"text": "Missile launch, break right.", "urgent": True}
    )
    assert status == 200
    assert sink.delivered == [(b"FAKE-WAV-BYTES", True)]


def test_speak_urgent_defaults_to_false(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, _engine, sink = running_server
    status, _body = _post(server, "/speak", {"text": "Contact."})
    assert status == 200
    assert sink.delivered == [(b"FAKE-WAV-BYTES", False)]


def test_speak_missing_text_field_returns_400(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, engine, sink = running_server
    status, body = _post(server, "/speak", {})
    assert status == 400
    assert isinstance(body, dict)
    assert "error" in body
    assert engine.requested_text == []
    assert sink.delivered == []


def test_speak_empty_text_returns_400(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, engine, _sink = running_server
    status, _body = _post(server, "/speak", {"text": "   "})
    assert status == 400
    assert engine.requested_text == []


def test_speak_non_string_text_returns_400(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, engine, _sink = running_server
    status, _body = _post(server, "/speak", {"text": 123})
    assert status == 400
    assert engine.requested_text == []


def test_speak_non_bool_urgent_returns_400(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, engine, _sink = running_server
    status, _body = _post(server, "/speak", {"text": "hello", "urgent": "yes"})
    assert status == 400
    assert engine.requested_text == []


def test_speak_non_json_body_returns_400(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, engine, _sink = running_server
    status, _body = _post(server, "/speak", b"not json")
    assert status == 400
    assert engine.requested_text == []


def test_speak_synthesis_failure_returns_503() -> None:
    engine = _FakeEngine(should_fail=True)
    sink = _RecordingSink()
    server = TTSAdapterServer(engine, sink, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _post(server, "/speak", {"text": "hello"})
        assert status == 503
        assert isinstance(body, dict)
        assert "error" in body
        assert sink.delivered == []
    finally:
        server.close()
        thread.join(timeout=5)


def test_speak_delivery_failure_returns_500() -> None:
    engine = _FakeEngine()
    sink = _RecordingSink(should_fail=True)
    server = TTSAdapterServer(engine, sink, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _post(server, "/speak", {"text": "hello"})
        assert status == 500
        assert isinstance(body, dict)
        assert "error" in body
    finally:
        server.close()
        thread.join(timeout=5)


def test_speak_unknown_path_returns_404(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, _engine, _sink = running_server
    status, _body = _post(server, "/nonexistent", {})
    assert status == 404
