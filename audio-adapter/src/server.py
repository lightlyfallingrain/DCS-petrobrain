"""`audio-adapter`'s own inbound HTTP server -- `POST /speak`, the one call
body-layer's `AudioAdapterClient` makes for outbound speech
(`plans/tts-voice-output/plan.md` stage 1/4) -- plus, since Stage 3 of
`plans/inbound-speech/plan.md`, the inbound-speech pair `POST /transcribe`
and `GET /transcripts/poll`.

Structurally a direct copy of `aircraft-layer/src/api/server.py`'s
`/text/push` handler shape (validate the JSON body, forward to a
collaborator, respond `200`/`400`/`503`/`500`) -- reused deliberately rather
than inventing a second request-parsing idiom. `GET /transcripts/poll`
copies that same file's `GET /f10_commands/poll` shape instead: drain a
bounded FIFO queue on every call, empty state `[]`, never `null`.

`POST /stop` (`plans/inbound-speech/plan.md` Stage 3 follow-up) is the
interrupt-only counterpart to `/speak`: no body, no synthesis, just
`AudioSink.interrupt()` -- stop whatever is currently playing/queued on the
configured target and say nothing new. It exists because `stop_talking` is
a stated exception to this project's usual readback/confirm rule (user
direction, 2026-09-20: "no readback or confirmation, just stop talking...
more of a debug tool than crew feature") -- reaching the aircraft-layer's
`AudioPlaybackSender._interrupt_playback`/`_clear_queue` previously required
pushing a new urgent audio line through `/speak`, which is what produced an
audible "Copy." every time. `AudioSink.interrupt()` reaches the same
mechanism (for `--target aircraft-layer`, forwarding to the aircraft
layer's own new `POST /audio/stop`; for `--target local`, killing whatever
`afplay` process is in flight) without ever synthesizing or delivering
anything.

This server is target-agnostic: it always synthesizes via a `TTSEngine`
(`tts_engine.py`) and then calls one `AudioSink.deliver`, without knowing
whether that sink plays the WAV locally (`--target local`, `afplay`) or
forwards it to the aircraft layer over HTTP (`--target aircraft-layer`,
`aircraft_client.py`) -- `__main__.py` is the only place that decides which
concrete sink is wired in (plan Decision 8).

`POST /transcribe`/`GET /transcripts/poll` are wired only when `__main__.py`
passes an `STTEngine` -- without one (`stt_engine=None`, the constructor
default), `POST /transcribe` answers `503` and `GET /transcripts/poll`
always drains an empty queue, the same "optional collaborator, 503 when
absent" posture `aircraft-layer/src/api/server.py`'s `text_sender`/
`command_sender`/`audio_sender` already use for their own optional
collaborators.

**Body-layer never sees audio, WAV paths, or engine names across this
seam** (`plans/inbound-speech/plan.md` Decision 6) -- `POST /transcribe`
decodes the WAV, recognises it, matches it, and enqueues text plus match
metadata only; nothing audio-shaped is ever stored in `TranscriptQueue` or
returned by `GET /transcripts/poll`.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Protocol, Self
from urllib.parse import urlparse

from command_matcher import match_transcript
from latency_log import LatencyLogWriter
from stt_engine import STTEngine, STTRecognitionError
from transcript_queue import TranscriptEvent, TranscriptQueue
from tts_engine import TTSEngine, TTSSynthesisError

logger = logging.getLogger(__name__)

#: Loopback only -- body-layer's `AudioAdapterClient` is expected to run on
#: the same box as this server for now (mirrors the compute-topology note
#: in root `CLAUDE.md`: Mac runs both Ollama/brain and, now, TTS).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7795

_SPEAK_PATH = "/speak"
_TRANSCRIBE_PATH = "/transcribe"
_TRANSCRIPTS_POLL_PATH = "/transcripts/poll"
_STOP_PATH = "/stop"

#: The capture side mints a fixed ~12-char id (`uuid.uuid4().hex[:12]`,
#: `capture_loop.CaptureLoop`) -- a generous cap on what this server
#: accepts from any caller costs nothing and forecloses an attacker-
#: controlled LAN peer growing `--latency-log`/`--speech-log` without
#: bound (security plan review, `plans/voice-latency-instrumentation/
#: plan.md`: low-probability/low-impact on this project's single-user LAN
#: scope, but cheap to close outright).
_MAX_CORRELATION_ID_LEN = 128


def _validate_correlation_id(value: object) -> tuple[str | None, str | None]:
    """`None` is always valid (no id supplied). A present value must be a
    `str` of at most `_MAX_CORRELATION_ID_LEN` characters. Returns
    `(correlation_id, error)` -- exactly one of the pair is `None`,
    mirroring every other field validation in this module's handlers."""
    if value is None:
        return None, None
    if not isinstance(value, str) or len(value) > _MAX_CORRELATION_ID_LEN:
        return None, (
            "'correlation_id' must be a string of at most "
            f"{_MAX_CORRELATION_ID_LEN} characters"
        )
    return value, None


def _log_latency(
    latency_log: LatencyLogWriter | None,
    *,
    stage: str,
    correlation_id: str | None,
    outcome: str,
    **fields: float | None,
) -> None:
    """Writes one `--latency-log` row, if configured -- a true no-op
    otherwise. `fields` are whichever extra numeric fields this call site
    has -- the monotonic-derived timings (`synth_duration_s`/
    `deliver_duration_s`/`transcribe_duration_s`/`match_duration_s`) and,
    for `/transcribe`, the capture side's own `t_ptt_release_wall` (ordinary
    wall-clock, cross-machine, context only -- see `latency_log.py`'s
    module docstring on which fields the reducer trusts) -- passed straight
    through so each call site names its own, rather than this helper
    assuming a fixed shape across `/speak` and `/transcribe`."""
    if latency_log is None:
        return
    row: dict[str, object] = {
        "stage": stage,
        "correlation_id": correlation_id,
        "outcome": outcome,
    }
    row.update(fields)
    latency_log.write(row)


class AudioDeliveryError(RuntimeError):
    """Raised by an `AudioSink.deliver` implementation when it cannot
    deliver synthesized audio to its destination (local playback failure,
    or -- for the aircraft-layer sink -- a failed HTTP hop)."""


class AudioSink(Protocol):
    def deliver(
        self, audio: bytes, urgent: bool, correlation_id: str | None = None
    ) -> None:
        """Deliver synthesized WAV bytes to their destination. Raises
        `AudioDeliveryError` on failure -- this call itself never swallows
        anything; `_handle_speak` below is where the swallow-vs-fail
        decision for the HTTP response is made (plan Decision 5).

        `correlation_id` (`plans/voice-latency-instrumentation/plan.md`
        Stage 1-4) is accepted and forwarded by every implementation of
        this protocol, purely for logging -- it never changes delivery
        behaviour. `None` (the default) for every caller that has none to
        give, which is every call site before this plan and every local-
        target call site after it; only `AircraftLayerAudioSink` actually
        has anywhere to send it (the aircraft-layer worker thread's own
        enqueue/playback-start/playback-finish log lines)."""
        ...

    def interrupt(self) -> None:
        """Stop whatever this sink is currently delivering/playing and drop
        anything queued, without delivering anything new (`plans/
        inbound-speech/plan.md` Stage 3 follow-up -- `POST /stop`'s
        interrupt-only path, `stop_talking`'s stated exception to this
        project's usual readback/confirm rule). Raises `AudioDeliveryError`
        on failure, same contract as `deliver` -- `_handle_stop` below
        makes the same swallow-vs-fail call `_handle_speak` makes for
        `deliver`."""
        ...


def _make_handler(
    engine: TTSEngine,
    sink: AudioSink,
    stt_engine: STTEngine | None,
    transcript_queue: TranscriptQueue,
    latency_log: LatencyLogWriter | None = None,
) -> type[BaseHTTPRequestHandler]:
    class SpeakRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == _TRANSCRIPTS_POLL_PATH:
                self._respond_json(
                    200, [event.to_dict() for event in transcript_queue.drain_all()]
                )
                return
            self._respond_json(404, {"error": f"not found: {path}"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == _SPEAK_PATH:
                self._handle_speak()
                return
            if path == _TRANSCRIBE_PATH:
                self._handle_transcribe()
                return
            if path == _STOP_PATH:
                self._handle_stop()
                return
            self._respond_json(404, {"error": f"not found: {path}"})

        def _read_body(self) -> bytes | None:
            """Read the request body per `Content-Length`, guarding the
            header itself before touching `rfile`.

            A missing header reads as zero bytes, same as before. A
            non-numeric value used to raise `ValueError` straight out of
            `do_POST` -- `ThreadingHTTPServer` isolates that to a stray
            traceback on one connection rather than a crash, but a
            malformed request should get a clean `400`, not a traceback. A
            *negative* value is worse than cosmetic: `self.rfile.read(n)`
            with a negative `n` reads until EOF rather than a bounded
            amount, so on a connection with no EOF forthcoming that
            handler thread blocks indefinitely on a single bad request.
            Non-numeric and negative share one rejection branch below (same
            message, same `400`) since neither ever reaches `rfile.read`.
            Returns `None` (having already sent the `400`) when the header
            cannot be trusted."""
            raw_header = self.headers.get("Content-Length", "0") or "0"
            try:
                length = int(raw_header)
            except ValueError:
                length = -1
            if length < 0:
                self._respond_json(
                    400, {"error": f"invalid Content-Length: {raw_header!r}"}
                )
                return None
            return self.rfile.read(length) if length > 0 else b""

        def _handle_speak(self) -> None:
            raw_body = self._read_body()
            if raw_body is None:
                return
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond_json(400, {"error": "body must be valid JSON"})
                return
            if not isinstance(data, dict):
                self._respond_json(400, {"error": "body must be a JSON object"})
                return

            text = data.get("text")
            if not isinstance(text, str) or not text.strip():
                self._respond_json(400, {"error": "'text' must be a non-empty string"})
                return

            urgent = data.get("urgent", False)
            if not isinstance(urgent, bool):
                self._respond_json(400, {"error": "'urgent' must be a boolean"})
                return

            correlation_id, error = _validate_correlation_id(data.get("correlation_id"))
            if error is not None:
                self._respond_json(400, {"error": error})
                return

            synth_start = time.monotonic()
            try:
                audio = engine.synthesize(text)
            except TTSSynthesisError as exc:
                logger.warning("TTS synthesis failed for %r: %s", text, exc)
                _log_latency(
                    latency_log,
                    stage="speak",
                    correlation_id=correlation_id,
                    outcome="synthesis_failed",
                    synth_duration_s=time.monotonic() - synth_start,
                )
                self._respond_json(503, {"error": f"synthesis failed: {exc}"})
                return
            synth_duration_s = time.monotonic() - synth_start

            deliver_start = time.monotonic()
            try:
                sink.deliver(audio, urgent, correlation_id)
            except AudioDeliveryError as exc:
                logger.warning("audio delivery failed for %r: %s", text, exc)
                _log_latency(
                    latency_log,
                    stage="speak",
                    correlation_id=correlation_id,
                    outcome="delivery_failed",
                    synth_duration_s=synth_duration_s,
                    deliver_duration_s=time.monotonic() - deliver_start,
                )
                self._respond_json(500, {"error": f"delivery failed: {exc}"})
                return

            # `deliver_duration_s` means "handed off to the sink" -- full
            # playback time for `--target local` (`deliver()` blocks on
            # `afplay`/`winsound` until the WAV finishes), but only an
            # *enqueue* ack for `--target aircraft-layer` (`POST /audio/play`
            # returns once the collector's queue has accepted the clip, not
            # once it has actually played -- see `AircraftLayerAudioSink`
            # and the aircraft-layer worker thread's own log lines for that
            # path's true playback timing).
            _log_latency(
                latency_log,
                stage="speak",
                correlation_id=correlation_id,
                outcome="ok",
                synth_duration_s=synth_duration_s,
                deliver_duration_s=time.monotonic() - deliver_start,
            )
            self._respond_json(200, {"ok": True})

        def _handle_transcribe(self) -> None:
            """`POST /transcribe` (`{"wav_b64": str}`) -- decode -> `STTEngine.
            transcribe` -> `command_matcher.match_transcript` -> enqueue one
            `TranscriptEvent`. Mirrors `_handle_audio_play`'s own base64
            decode shape (`aircraft-layer/src/api/server.py`), the existing
            precedent for taking audio over this project's HTTP seams.

            Never forwards the WAV or the engine name anywhere past this
            method -- only `transcript.text` and the matcher's output reach
            `TranscriptQueue` (module docstring's "body-layer never sees
            audio" invariant)."""
            if stt_engine is None:
                self._respond_json(503, {"error": "speech recognition not configured"})
                return

            raw_body = self._read_body()
            if raw_body is None:
                return
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond_json(400, {"error": "body must be valid JSON"})
                return
            if not isinstance(data, dict):
                self._respond_json(400, {"error": "body must be a JSON object"})
                return

            wav_b64 = data.get("wav_b64")
            if not isinstance(wav_b64, str) or not wav_b64:
                self._respond_json(
                    400, {"error": "'wav_b64' must be a non-empty string"}
                )
                return
            try:
                wav = base64.b64decode(wav_b64, validate=True)
            except (binascii.Error, ValueError) as exc:
                self._respond_json(
                    400, {"error": f"'wav_b64' is not valid base64: {exc}"}
                )
                return
            if not wav:
                self._respond_json(400, {"error": "'wav_b64' decoded to no bytes"})
                return

            correlation_id, error = _validate_correlation_id(data.get("correlation_id"))
            if error is not None:
                self._respond_json(400, {"error": error})
                return
            t_ptt_release_wall = data.get("t_ptt_release_wall")
            if t_ptt_release_wall is not None and (
                not isinstance(t_ptt_release_wall, (int, float))
                or isinstance(t_ptt_release_wall, bool)
            ):
                self._respond_json(
                    400, {"error": "'t_ptt_release_wall' must be a number"}
                )
                return

            transcribe_start = time.monotonic()
            try:
                transcript = stt_engine.transcribe(wav)
            except STTRecognitionError as exc:
                logger.warning("speech recognition failed: %s", exc)
                _log_latency(
                    latency_log,
                    stage="transcribe",
                    correlation_id=correlation_id,
                    outcome="recognition_failed",
                    transcribe_duration_s=time.monotonic() - transcribe_start,
                )
                self._respond_json(503, {"error": f"recognition failed: {exc}"})
                return
            transcribe_duration_s = time.monotonic() - transcribe_start

            match_start = time.monotonic()
            match = match_transcript(transcript.text)
            match_duration_s = time.monotonic() - match_start

            transcript_queue.push(
                TranscriptEvent(
                    transcript=transcript.text,
                    confidence=transcript.confidence,
                    token=match.token,
                    match_ratio=match.match_ratio,
                    verb_anchored=match.verb_anchored,
                    ambiguous=match.ambiguous,
                    t_wall=time.time(),
                    slots=match.slots,
                    correlation_id=correlation_id,
                )
            )
            _log_latency(
                latency_log,
                stage="transcribe",
                correlation_id=correlation_id,
                outcome="ok",
                transcribe_duration_s=transcribe_duration_s,
                match_duration_s=match_duration_s,
                t_ptt_release_wall=(
                    float(t_ptt_release_wall)
                    if t_ptt_release_wall is not None
                    else None
                ),
            )
            self._respond_json(200, {"ok": True})

        def _handle_stop(self) -> None:
            """`POST /stop` (no request body -- `AudioSink.interrupt` takes
            no arguments) -- forwards straight to `sink.interrupt()`. No
            synthesis step, no engine involved: this is the interrupt-only
            path, not a shorter `/speak` call."""
            try:
                sink.interrupt()
            except AudioDeliveryError as exc:
                logger.warning("audio interrupt failed: %s", exc)
                self._respond_json(500, {"error": f"interrupt failed: {exc}"})
                return
            self._respond_json(200, {"ok": True})

        def _respond_json(self, status: int, body: Any) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            logger.debug("%s - %s", self.address_string(), format % args)

    return SpeakRequestHandler


class TTSAdapterServer:
    """Owns the `POST /speak` + `POST /transcribe` + `GET /transcripts/poll`
    HTTP server; mirrors `aircraft-layer`'s `TelemetryAPIServer` open()/
    close()/serve_forever() shape.

    `stt_engine`/`transcript_queue` are Stage 3 additions
    (`plans/inbound-speech/plan.md`). `stt_engine` defaults to `None` --
    outbound-speech-only callers (this project's existing tests, and any
    future run with no recogniser configured) need not construct one;
    `_handle_transcribe` answers `503` in that case (module docstring).
    `transcript_queue` defaults to a fresh, empty `TranscriptQueue` --
    always constructed so `GET /transcripts/poll` always has something to
    drain (an empty list, not a 503), whether or not `stt_engine` is set."""

    def __init__(
        self,
        engine: TTSEngine,
        sink: AudioSink,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        stt_engine: STTEngine | None = None,
        transcript_queue: TranscriptQueue | None = None,
        latency_log: LatencyLogWriter | None = None,
    ) -> None:
        self._engine = engine
        self._sink = sink
        self._host = host
        self._port = port
        self._stt_engine = stt_engine
        self._transcript_queue = (
            transcript_queue if transcript_queue is not None else TranscriptQueue()
        )
        #: `--latency-log` (`plans/voice-latency-instrumentation/plan.md`
        #: Stage 2) -- `None` (the default) is a true no-op, same posture as
        #: every other optional collaborator on this class.
        self._latency_log = latency_log
        self._httpd: ThreadingHTTPServer | None = None

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def port(self) -> int:
        """Bound port. Useful when constructed with `port=0` (OS-assigned)."""
        if self._httpd is None:
            raise RuntimeError("call open() before reading port")
        return int(self._httpd.server_address[1])

    def open(self) -> None:
        """Bind and start listening. Does not block."""
        self._httpd = ThreadingHTTPServer(
            (self._host, self._port),
            _make_handler(
                self._engine,
                self._sink,
                self._stt_engine,
                self._transcript_queue,
                self._latency_log,
            ),
        )
        logger.info("audio-adapter listening on %s:%d", self._host, self.port)

    def close(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def serve_forever(self) -> None:
        """Serve requests until `close()` is called from another thread."""
        if self._httpd is None:
            raise RuntimeError("call open() before serve_forever()")
        self._httpd.serve_forever()
