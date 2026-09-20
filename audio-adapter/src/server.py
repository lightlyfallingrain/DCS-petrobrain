"""`audio-adapter`'s own inbound HTTP server -- `POST /speak`, the one call
body-layer's `AudioAdapterClient` makes (`plans/tts-voice-output/plan.md`
stage 1/4).

Structurally a direct copy of `aircraft-layer/src/api/server.py`'s
`/text/push` handler shape (validate the JSON body, forward to a
collaborator, respond `200`/`400`/`503`/`500`) -- reused deliberately rather
than inventing a second request-parsing idiom.

This server is target-agnostic: it always synthesizes via a `TTSEngine`
(`tts_engine.py`) and then calls one `AudioSink.deliver`, without knowing
whether that sink plays the WAV locally (`--target local`, `afplay`) or
forwards it to the aircraft layer over HTTP (`--target aircraft-layer`,
`aircraft_client.py`) -- `__main__.py` is the only place that decides which
concrete sink is wired in (plan Decision 8).
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Protocol, Self
from urllib.parse import urlparse

from tts_engine import TTSEngine, TTSSynthesisError

logger = logging.getLogger(__name__)

#: Loopback only -- body-layer's `AudioAdapterClient` is expected to run on
#: the same box as this server for now (mirrors the compute-topology note
#: in root `CLAUDE.md`: Mac runs both Ollama/brain and, now, TTS).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7795

_SPEAK_PATH = "/speak"


class AudioDeliveryError(RuntimeError):
    """Raised by an `AudioSink.deliver` implementation when it cannot
    deliver synthesized audio to its destination (local playback failure,
    or -- for the aircraft-layer sink -- a failed HTTP hop)."""


class AudioSink(Protocol):
    def deliver(self, audio: bytes, urgent: bool) -> None:
        """Deliver synthesized WAV bytes to their destination. Raises
        `AudioDeliveryError` on failure -- this call itself never swallows
        anything; `_handle_speak` below is where the swallow-vs-fail
        decision for the HTTP response is made (plan Decision 5)."""
        ...


def _make_handler(engine: TTSEngine, sink: AudioSink) -> type[BaseHTTPRequestHandler]:
    class SpeakRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == _SPEAK_PATH:
                self._handle_speak()
                return
            self._respond_json(404, {"error": f"not found: {path}"})

        def _handle_speak(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""
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

            try:
                audio = engine.synthesize(text)
            except TTSSynthesisError as exc:
                logger.warning("TTS synthesis failed for %r: %s", text, exc)
                self._respond_json(503, {"error": f"synthesis failed: {exc}"})
                return

            try:
                sink.deliver(audio, urgent)
            except AudioDeliveryError as exc:
                logger.warning("audio delivery failed for %r: %s", text, exc)
                self._respond_json(500, {"error": f"delivery failed: {exc}"})
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
    """Owns the `POST /speak` HTTP server; mirrors
    `aircraft-layer`'s `TelemetryAPIServer` open()/close()/serve_forever()
    shape."""

    def __init__(
        self,
        engine: TTSEngine,
        sink: AudioSink,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._engine = engine
        self._sink = sink
        self._host = host
        self._port = port
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
            (self._host, self._port), _make_handler(self._engine, self._sink)
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
