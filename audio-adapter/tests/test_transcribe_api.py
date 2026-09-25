"""Tests for `server.TTSAdapterServer`'s `POST /transcribe` and
`GET /transcripts/poll` (`plans/inbound-speech/plan.md` Stage 3).

Structural copy of `test_server.py`'s pattern (real loopback server,
recording/fake collaborator doubles) plus a recording `STTEngine` double
standing in for the real whisper-cli binary -- this file never shells out."""

from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from server import TTSAdapterServer
from stt_engine import STTRecognitionError, Transcript
from transcript_queue import TranscriptQueue


class _FakeTTSEngine:
    def synthesize(self, text: str) -> bytes:
        return b"FAKE-WAV-BYTES"


class _NullSink:
    def deliver(self, audio: bytes, urgent: bool) -> None:
        pass


class _FakeSTTEngine:
    """Records requested WAV bytes; returns a fixed `Transcript` (or raises
    `STTRecognitionError`) regardless of content -- `command_matcher.
    match_transcript` runs for real against whatever text is returned, so
    these tests exercise the real match path, not a matcher double."""

    def __init__(
        self,
        text: str = "scan left",
        confidence: float = 0.9,
        should_fail: bool = False,
    ) -> None:
        self.text = text
        self.confidence = confidence
        self.should_fail = should_fail
        self.requested_wav: list[bytes] = []

    def transcribe(self, wav: bytes) -> Transcript:
        self.requested_wav.append(wav)
        if self.should_fail:
            raise STTRecognitionError("recognition failed (test double)")
        return Transcript(text=self.text, confidence=self.confidence, engine="fake")


def _make_server(
    stt_engine: _FakeSTTEngine | None,
) -> tuple[TTSAdapterServer, TranscriptQueue]:
    queue = TranscriptQueue()
    server = TTSAdapterServer(
        _FakeTTSEngine(),
        _NullSink(),
        host="127.0.0.1",
        port=0,
        stt_engine=stt_engine,
        transcript_queue=queue,
    )
    return server, queue


@pytest.fixture
def running_server_with_stt() -> Iterator[tuple[TTSAdapterServer, _FakeSTTEngine]]:
    engine = _FakeSTTEngine()
    server, _queue = _make_server(engine)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, engine
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


def _get(server: TTSAdapterServer, path: str) -> tuple[int, object]:
    url = f"http://127.0.0.1:{server.port}{path}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _wav_b64(payload: bytes = b"FAKE-CLIP-BYTES") -> str:
    return base64.b64encode(payload).decode("ascii")


def test_transcribe_then_poll_round_trips_a_matched_command(
    running_server_with_stt: tuple[TTSAdapterServer, _FakeSTTEngine],
) -> None:
    server, engine = running_server_with_stt
    status, body = _post(server, "/transcribe", {"wav_b64": _wav_b64()})
    assert status == 200
    assert body == {"ok": True}
    assert engine.requested_wav == [b"FAKE-CLIP-BYTES"]

    status, body = _get(server, "/transcripts/poll")
    assert status == 200
    assert isinstance(body, list)
    assert len(body) == 1
    event = body[0]
    assert event["transcript"] == "scan left"
    assert event["token"] == "scan_left"
    assert event["verb_anchored"] is True
    assert event["ambiguous"] is False
    assert isinstance(event["match_ratio"], float)
    assert isinstance(event["confidence"], float)
    assert isinstance(event["t_wall"], float)
    assert event["slots"] is None
    # Never audio-shaped fields.
    assert set(event) == {
        "transcript",
        "confidence",
        "token",
        "match_ratio",
        "verb_anchored",
        "ambiguous",
        "t_wall",
        "slots",
    }


def test_transcribe_carries_a_parsed_bearing_through_to_poll(
    running_server_with_stt: tuple[TTSAdapterServer, _FakeSTTEngine],
) -> None:
    """`plans/voice-command-completeness/plan.md` Stage 3's own regression
    guard: `MatchResult.slots` (formerly `bearing_degrees`) used to be
    computed by `command_matcher.match_transcript` and then dropped at this
    exact wire (`TranscriptEvent` carried seven fields, not eight). A legal,
    resolved bearing must now survive `POST /transcribe` -> `GET /transcripts/
    poll` intact, inside the `slots` dict."""
    server, engine = running_server_with_stt
    engine.text = "scan bearing three two zero"
    status, body = _post(server, "/transcribe", {"wav_b64": _wav_b64()})
    assert status == 200
    assert body == {"ok": True}

    status, body = _get(server, "/transcripts/poll")
    assert status == 200
    assert isinstance(body, list)
    assert len(body) == 1
    event = body[0]
    assert event["token"] == "scan_bearing_deg"
    assert event["slots"] == {"bearing_degrees": 320}


def test_poll_drains_and_is_empty_afterwards(
    running_server_with_stt: tuple[TTSAdapterServer, _FakeSTTEngine],
) -> None:
    server, _engine = running_server_with_stt
    _post(server, "/transcribe", {"wav_b64": _wav_b64()})
    _get(server, "/transcripts/poll")
    status, body = _get(server, "/transcripts/poll")
    assert status == 200
    assert body == []


def test_poll_with_nothing_pending_returns_empty_list(
    running_server_with_stt: tuple[TTSAdapterServer, _FakeSTTEngine],
) -> None:
    server, _engine = running_server_with_stt
    status, body = _get(server, "/transcripts/poll")
    assert status == 200
    assert body == []


def test_two_transcribes_before_a_poll_both_survive(
    running_server_with_stt: tuple[TTSAdapterServer, _FakeSTTEngine],
) -> None:
    server, _engine = running_server_with_stt
    _post(server, "/transcribe", {"wav_b64": _wav_b64()})
    _post(server, "/transcribe", {"wav_b64": _wav_b64()})
    status, body = _get(server, "/transcripts/poll")
    assert status == 200
    assert isinstance(body, list)
    assert len(body) == 2


def test_non_command_speech_enqueues_with_null_token(
    running_server_with_stt: tuple[TTSAdapterServer, _FakeSTTEngine],
) -> None:
    engine = _FakeSTTEngine(text="the tanks are on the ridge")
    server, _queue = _make_server(engine)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _post(server, "/transcribe", {"wav_b64": _wav_b64()})
        status, body = _get(server, "/transcripts/poll")
        assert status == 200
        assert isinstance(body, list)
        assert body[0]["token"] is None
        assert body[0]["verb_anchored"] is False
    finally:
        server.close()
        thread.join(timeout=5)


def test_transcribe_without_stt_engine_returns_503() -> None:
    server, _queue = _make_server(stt_engine=None)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _post(server, "/transcribe", {"wav_b64": _wav_b64()})
        assert status == 503
        assert isinstance(body, dict)
        assert "error" in body
    finally:
        server.close()
        thread.join(timeout=5)


def test_poll_without_stt_engine_configured_still_returns_empty_list() -> None:
    server, _queue = _make_server(stt_engine=None)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _get(server, "/transcripts/poll")
        assert status == 200
        assert body == []
    finally:
        server.close()
        thread.join(timeout=5)


def test_transcribe_recognition_failure_returns_503_and_does_not_enqueue() -> None:
    engine = _FakeSTTEngine(should_fail=True)
    server, _queue = _make_server(engine)
    server.open()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _post(server, "/transcribe", {"wav_b64": _wav_b64()})
        assert status == 503
        assert isinstance(body, dict)
        assert "error" in body
        status, body = _get(server, "/transcripts/poll")
        assert body == []
    finally:
        server.close()
        thread.join(timeout=5)


def test_transcribe_missing_wav_b64_returns_400(
    running_server_with_stt: tuple[TTSAdapterServer, _FakeSTTEngine],
) -> None:
    server, engine = running_server_with_stt
    status, body = _post(server, "/transcribe", {})
    assert status == 400
    assert isinstance(body, dict)
    assert "error" in body
    assert engine.requested_wav == []


def test_transcribe_invalid_base64_returns_400(
    running_server_with_stt: tuple[TTSAdapterServer, _FakeSTTEngine],
) -> None:
    server, engine = running_server_with_stt
    status, _body = _post(server, "/transcribe", {"wav_b64": "not-valid-base64!!"})
    assert status == 400
    assert engine.requested_wav == []


def test_transcribe_empty_decoded_audio_returns_400(
    running_server_with_stt: tuple[TTSAdapterServer, _FakeSTTEngine],
) -> None:
    server, engine = running_server_with_stt
    status, _body = _post(server, "/transcribe", {"wav_b64": _wav_b64(b"")})
    assert status == 400
    assert engine.requested_wav == []


def test_transcribe_non_json_body_returns_400(
    running_server_with_stt: tuple[TTSAdapterServer, _FakeSTTEngine],
) -> None:
    server, engine = running_server_with_stt
    status, _body = _post(server, "/transcribe", b"not json")
    assert status == 400
    assert engine.requested_wav == []


def test_speak_still_works_alongside_transcribe(
    running_server_with_stt: tuple[TTSAdapterServer, _FakeSTTEngine],
) -> None:
    server, _engine = running_server_with_stt
    status, body = _post(server, "/speak", {"text": "hello", "urgent": False})
    assert status == 200
    assert body == {"ok": True}
