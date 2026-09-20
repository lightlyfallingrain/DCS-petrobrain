"""HTTP client for the aircraft layer's `POST /audio/play` endpoint
(`plans/tts-voice-output/plan.md` stages 2/3/6).

Mirrors `body-layer/src/aircraft_client.py`'s shape (a thin `urllib.request`
wrapper, stdlib only, raise-on-failure for its one write call) -- this is
`audio-adapter`'s own, independent copy rather than an import of that module:
`audio-adapter` must stand alone (root `CLAUDE.md`'s module-independence
rule), and the world-model<->body-layer in-process import is the sole
sanctioned cross-subproject exception, not a precedent to extend here.

`AircraftLayerAudioSink` implements `server.AudioSink` -- the `--target
aircraft-layer` delivery mechanism (plan Decision 8), POSTing the
synthesized WAV as base64 JSON to a running aircraft-layer collector's
`POST /audio/play` (plan Decision 6: JSON body, not raw bytes, to reuse
that server's existing JSON scaffolding)."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

from server import AudioDeliveryError

_DEFAULT_TIMEOUT_S = 5.0

_AUDIO_PLAY_PATH = "/audio/play"
_AUDIO_STOP_PATH = "/audio/stop"


class AircraftLayerError(RuntimeError):
    """Raised when the aircraft-layer API is unreachable, times out, or
    returns a non-2xx response for `POST /audio/play`."""


class AircraftLayerClient:
    """Thin JSON POST client for one aircraft-layer instance's
    `POST /audio/play` endpoint. `base_url` has no trailing slash, e.g.
    `"http://192.168.1.50:7791"` (the aircraft-layer LAN API's default
    port, see `aircraft-layer/src/api/server.py`'s `DEFAULT_PORT`)."""

    def __init__(self, base_url: str, timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        self._base_url = base_url
        self._timeout_s = timeout_s

    def play_audio(self, audio: bytes, urgent: bool) -> None:
        """`POST /audio/play` with `{"audio_b64": <base64 WAV>, "urgent":
        bool}`. Raises `AircraftLayerError` on any failure (network error,
        non-2xx, invalid JSON) -- this call never swallows, matching
        `body-layer/src/aircraft_client.py`'s `push_text_line`'s
        raise-on-failure posture for its one write call."""
        url = f"{self._base_url}{_AUDIO_PLAY_PATH}"
        body = {
            "audio_b64": base64.b64encode(audio).decode("ascii"),
            "urgent": urgent,
        }
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise AircraftLayerError(f"request to {url} failed: {exc}") from exc

    def stop_audio(self) -> None:
        """`POST /audio/stop` (`plans/inbound-speech/plan.md` Stage 3
        follow-up) -- no request body, mirroring `AudioPlaybackSender.
        interrupt`'s no-argument contract on the aircraft-layer side.
        Raises `AircraftLayerError` on any failure, same posture as
        `play_audio`."""
        url = f"{self._base_url}{_AUDIO_STOP_PATH}"
        request = urllib.request.Request(url, data=b"", method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise AircraftLayerError(f"request to {url} failed: {exc}") from exc


class AircraftLayerAudioSink:
    """`server.AudioSink` that forwards synthesized audio to a running
    aircraft-layer collector for Windows-side `winsound` playback
    (`--target aircraft-layer`, plan Decision 8). Wraps
    `AircraftLayerClient.play_audio`'s `AircraftLayerError` into
    `server.AudioDeliveryError` -- `server.py`'s `_handle_speak` only knows
    about the latter, keeping the sink contract uniform across targets."""

    def __init__(self, base_url: str, timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        self._client = AircraftLayerClient(base_url, timeout_s=timeout_s)

    def deliver(self, audio: bytes, urgent: bool) -> None:
        try:
            self._client.play_audio(audio, urgent)
        except AircraftLayerError as exc:
            raise AudioDeliveryError(str(exc)) from exc

    def interrupt(self) -> None:
        """`server.AudioSink.interrupt` for `--target aircraft-layer` --
        forwards to `AircraftLayerClient.stop_audio`, wrapping its
        `AircraftLayerError` into `AudioDeliveryError` exactly as `deliver`
        does for `play_audio`."""
        try:
            self._client.stop_audio()
        except AircraftLayerError as exc:
            raise AudioDeliveryError(str(exc)) from exc
