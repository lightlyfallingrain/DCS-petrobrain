"""Tests for `server.TTSAdapterServer`'s `POST /speak` endpoint.

Structural copy of `aircraft-layer/tests/test_text_push_api.py`'s pattern:
a real loopback HTTP server, a recording double standing in for the real
`TTSEngine`/`AudioSink` collaborators."""

from __future__ import annotations

import http.client
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
    when `should_fail` is set. `interrupt_calls`/`should_fail_interrupt`
    are `/stop`'s own counterpart, independent of `deliver`'s own
    `should_fail` flag."""

    def __init__(
        self, should_fail: bool = False, should_fail_interrupt: bool = False
    ) -> None:
        self.should_fail = should_fail
        self.should_fail_interrupt = should_fail_interrupt
        self.delivered: list[tuple[bytes, bool]] = []
        self.interrupt_calls = 0

    def deliver(self, audio: bytes, urgent: bool) -> None:
        if self.should_fail:
            raise AudioDeliveryError("delivery failed (test double)")
        self.delivered.append((audio, urgent))

    def interrupt(self) -> None:
        if self.should_fail_interrupt:
            raise AudioDeliveryError("interrupt failed (test double)")
        self.interrupt_calls += 1


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


def _post_raw_content_length(
    server: TTSAdapterServer,
    path: str,
    body: bytes,
    content_length: str | None,
) -> tuple[int, object]:
    """POST with a hand-set (possibly malformed) `Content-Length` header --
    `urllib.request.Request` always computes a correct one from `data`, so
    reaching the header-parsing guard in `server._read_body` needs a
    lower-level client. `content_length=None` omits the header entirely."""
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    try:
        conn.putrequest("POST", path)
        if content_length is not None:
            conn.putheader("Content-Length", content_length)
        conn.endheaders()
        conn.send(body)
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read())
    finally:
        conn.close()


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


# -- POST /stop (plans/inbound-speech/plan.md Stage 3 follow-up) ------------


def test_stop_calls_sink_interrupt_and_never_synthesizes(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, engine, sink = running_server
    status, body = _post(server, "/stop", b"")
    assert status == 200
    assert body == {"ok": True}
    assert sink.interrupt_calls == 1
    assert engine.requested_text == []
    assert sink.delivered == []


def test_stop_interrupt_failure_returns_500() -> None:
    engine = _FakeEngine()
    sink = _RecordingSink(should_fail_interrupt=True)
    server = TTSAdapterServer(engine, sink, host="127.0.0.1", port=0)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _post(server, "/stop", b"")
        assert status == 500
        assert isinstance(body, dict)
        assert "error" in body
    finally:
        server.close()
        thread.join(timeout=5)


# -- Content-Length guard (security review, 2026-09-26) --------------------
#
# A non-numeric header used to raise ValueError straight out of do_POST
# (ThreadingHTTPServer isolates that to a stray traceback on one connection,
# not a crash, but it should be a clean 400). A negative header is worse:
# self.rfile.read(n) with a negative n reads until EOF rather than a
# bounded amount, so it can block a handler thread indefinitely rather than
# just misbehaving. Both must now get a clean 400 before rfile.read is
# ever called.


def test_speak_missing_content_length_returns_400(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, engine, sink = running_server
    body = json.dumps({"text": "hello"}).encode("utf-8")
    status, resp_body = _post_raw_content_length(
        server, "/speak", body, content_length=None
    )
    # No Content-Length reads as an empty body (same as before this fix) --
    # empty is not valid JSON, so this still ends in a 400, just via the
    # existing JSON-validation path rather than the header guard.
    assert status == 400
    assert isinstance(resp_body, dict)
    assert "error" in resp_body
    assert engine.requested_text == []
    assert sink.delivered == []


def test_speak_non_numeric_content_length_returns_400(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, engine, sink = running_server
    body = json.dumps({"text": "hello"}).encode("utf-8")
    status, resp_body = _post_raw_content_length(
        server, "/speak", body, content_length="not-a-number"
    )
    assert status == 400
    assert isinstance(resp_body, dict)
    assert "error" in resp_body
    assert engine.requested_text == []
    assert sink.delivered == []


def test_speak_negative_content_length_returns_400(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    """A negative `Content-Length` must be rejected by `_read_body`'s own
    header guard, not fall through to the pre-existing JSON-validation
    path. Both paths happen to answer `400`, so asserting the status alone
    does not distinguish them -- the pre-fix code (`2802c4f`) already
    guarded the *read* with `self.rfile.read(length) if length > 0 else
    b""`, so a negative length there took the `else b""` branch and failed
    `json.loads("")` instead, answering `400` with `"body must be valid
    JSON"`. That passes this assertion's old status-only check but proves
    nothing about the header guard. Asserting the guard's own error message
    (`"invalid Content-Length: ..."`) instead fails against the pre-fix
    code -- confirmed empirically by reverting `server.py` to `2802c4f` and
    re-running this test."""
    server, engine, sink = running_server
    body = json.dumps({"text": "hello"}).encode("utf-8")
    status, resp_body = _post_raw_content_length(
        server, "/speak", body, content_length="-1"
    )
    assert status == 400
    assert isinstance(resp_body, dict)
    assert resp_body == {"error": "invalid Content-Length: '-1'"}
    assert engine.requested_text == []
    assert sink.delivered == []


def test_speak_valid_content_length_still_succeeds(
    running_server: tuple[TTSAdapterServer, _FakeEngine, _RecordingSink],
) -> None:
    server, engine, sink = running_server
    body = json.dumps({"text": "Watching Charlie one seven.", "urgent": False}).encode(
        "utf-8"
    )
    status, resp_body = _post_raw_content_length(
        server, "/speak", body, content_length=str(len(body))
    )
    assert status == 200
    assert resp_body == {"ok": True}
    assert engine.requested_text == ["Watching Charlie one seven."]
    assert sink.delivered == [(b"FAKE-WAV-BYTES", False)]
