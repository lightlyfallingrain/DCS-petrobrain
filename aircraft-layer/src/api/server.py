"""Mac-facing LAN API for querying the collector's cached telemetry +
world-objects + Petrovich-indication state.

Plan stage 4. Unlike `collector.server.CollectorServer` (loopback-only, the
Export.lua push hop), this server is LAN-reachable by design — it's the hop
the body/brain process, on either Windows or Mac (compute topology note in
`plans/aircraft-layer/plan.md`), polls over the network. Read-only.

- `GET /telemetry/latest` -> the most recent sample as JSON, or JSON `null`
  if the cache is still empty (not an error — Export.lua may not have
  connected/sent anything yet).
- `GET /world_objects/latest` -> the most recent `LoGetWorldObjects` snapshot
  as JSON, or JSON `null` on the same "not an error" basis. Added by
  `plans/pb1-perception-logger/plan.md` stage 3 as body-layer's Tier 3
  fallback data source; same shape/lifecycle as `/telemetry/latest`.
- `GET /petrovich_indication/latest` -> the most recent
  `list_indication(HELPERAI_DEVICE_ID)` sample as JSON (parsed
  `{leaf_name: text}` fields + timestamps), or JSON `null` on the same
  "not an error" basis. Added by `plans/pb1-perception-logger/plan.md`
  stage 4 as `HybridPerceptionSource`'s real detection-existence gate; same
  shape/lifecycle as the other two `/latest` endpoints. Raw parsed text
  only -- no detection/interpretation/association logic here, that is
  body-layer's job (`body-layer/src/perception/association.py`).
- `POST /text/push` -> the aircraft layer's first inbound/write path
  (`plans/dcs-text-panel-output/plan.md`, BL-2.5). Body `{"text": "<string>"}`;
  a non-empty (after `.strip()`) string forwards to
  `collector.text_sender.TextOverlaySender.send_line`, which fires the line at
  the in-cockpit overlay Hook script over loopback UDP, and responds
  `200 {"ok": true}`. `400 {"error": ...}` on a missing/invalid/empty `text`
  field or non-JSON body; `503 {"error": "text push not configured"}` if this
  server was built without a `text_sender` (matching the
  optional-cache-defaults-to-empty pattern below, rather than crashing). This
  endpoint carries opaque display strings only -- no aircraft state, no
  commands, no code -- everything else on this API remains read-only.
- `GET /petrovich_wheel/latest` -> the most recent `list_indication(10)`
  (Petrovich's AI-Wheel state) sample as JSON, or JSON `null` on the same
  "not an error" basis. Added by `plans/bl6-commands-inspect-adapt/plan.md`
  (BL-6) as a live diagnostic for `scan_area`'s `task-status` console
  command; same shape/lifecycle as the other `/latest` endpoints.
- `POST /command/petrovich_search` -> the aircraft layer's second
  inbound/write path (BL-6). Body `{"mode": "forward"|"boresight"}`; a valid
  mode forwards to `collector.command_sender.CommandSender.send_command`,
  which fires the JSON command at `Export.lua`'s new inbound UDP listener
  (driving Petrovich's AI Wheel), and responds `200 {"ok": true}` --
  matching `/text/push`'s "attempted the call" contract exactly: a `200`
  here means the datagram was hand off to the OS, never that Petrovich
  actually searched (that confirmation is `/petrovich_wheel/latest`'s job).
  `400 {"error": ...}` on a missing/invalid `mode` or non-JSON body;
  `503 {"error": "command channel not configured"}` if this server was
  built without a `command_sender`. Unlike `/text/push`, a send failure here
  propagates as `500 {"error": ...}` rather than being swallowed --
  `collector.command_sender.CommandSender.send_command` raises
  `CommandSendError` on a clearly-failed send (see that module's docstring
  for why this write path does not share `/text/push`'s
  never-raises posture).
- `POST /audio/play` -> the aircraft layer's third inbound/write path
  (BL-10 first slice, `plans/tts-voice-output/plan.md`). Body
  `{"audio_b64": "<base64 WAV bytes>", "urgent": bool}`; forwards the
  decoded bytes to `collector.audio_sender.AudioPlaybackSender.play_audio`,
  which plays them through `winsound` on this (Windows) box, and responds
  `200 {"ok": true}` -- same "attempted the call" contract as `/text/push`
  and `/command/petrovich_search`: a `200` means the audio was handed to
  the playback queue, never that it was actually heard. `400 {"error": ...}`
  on a missing/invalid `audio_b64`/`urgent` or non-JSON body; `503
  {"error": "audio playback not configured"}` if this server was built
  without an `audio_sender`. Like `/text/push` (and unlike
  `/command/petrovich_search`), this never propagates a `500` for a
  playback failure -- `AudioPlaybackSender.play_audio` never raises (plan
  Decision 5: audio is best-effort display-equivalent output, not a
  verifiable command).
- `POST /audio/stop` -> the aircraft layer's fourth inbound/write path
  (`plans/inbound-speech/plan.md` Stage 3 follow-up, "stop_talking"'s
  interrupt-only path). No request body is read or required -- forwards
  directly to `collector.audio_sender.AudioPlaybackSender.interrupt`,
  which clears the routine queue and stops in-flight playback without
  enqueueing anything, and responds `200 {"ok": true}`. `503
  {"error": "audio playback not configured"}` if this server was built
  without an `audio_sender`, same as `/audio/play`. Like `/audio/play`,
  this never propagates a `500` -- `AudioPlaybackSender.interrupt` never
  raises (it is `_clear_queue`/`_interrupt_playback`, the same two calls
  `/audio/play`'s own `urgent=True` path already uses, with the enqueue
  dropped). This is a debug/utility tool rather than a crew feature (user
  direction, 2026-09-20): it exists so a stop request can be silent --
  interrupting playback with no new audio to acknowledge it -- rather than
  needing to push an audio line just to reach the interrupt mechanism.

- `GET /f10_commands/poll` -> drains the collector's `F10CommandQueue`
  (`plans/f10-crew-commands/plan.md`) and returns every pending F10
  radio-menu selection as a JSON list, oldest first (`[]` if none pending,
  never `null` -- unlike every `/latest` endpoint above, this response is
  always a list). **Documented exception to every other endpoint's
  idempotent-read contract**: this one mutates collector-local queue state
  on every call, so it assumes exactly one poller (body-layer's
  `--crew-text --f10-commands`) -- a second concurrent poller would
  silently steal commands from the first. The queue defaults to a fresh,
  never-populated one (same optional-cache-defaults-to-empty pattern as
  `world_objects_cache`/`petrovich_indication_cache`/`petrovich_wheel_cache`
  above), so this endpoint always answers `200 []` rather than `503` when
  unconfigured -- there is no live effector here to be "not configured,"
  only an always-valid, possibly-empty queue.

- `GET /ptt/state` -> the pilot's push-to-talk trigger, or `null` before it
  has moved at all (`plans/inbound-speech/plan.md` Stage 5). A pure,
  idempotent read of a *state*, not a queue: the capture process polls it
  tens of times a second and must never consume anything by asking.
  **Since `plans/spu8-intercom/plan.md` Stage 2, the served `"intercom"`
  field is already gated by the SPU-8 switches** (`_handle_ptt_state`
  combines this with `Spu8Cache`) -- see that function's own docstring.
  `"radio"` is untouched.
- `GET /spu8/state` -> the SPU-8 intercom panel (pilot NET-1, co-pilot ICS
  power, volume), or `null` before the first line arrives
  (`plans/spu8-intercom/plan.md` Stage 1). Same shape/lifecycle as
  `/ptt/state`.
- `GET /unit_velocity/latest` -> the most recent `UnitVelocitySnapshot`
  (`plans/movement-detection/plan.md` Stage 1) as JSON, or JSON `null` on
  the same "not an error" basis as every other `/latest` endpoint. A
  **separate endpoint from `/world_objects/latest`, not merged into it**
  (that plan's Decision 2): merging would mean either holding a world-objects
  snapshot back until a matching velocity snapshot arrives, or emitting one
  timestamp for two feeds whose sim-clock stamps genuinely differ (5 Hz vs.
  1 Hz polls) -- silently destroying the provenance the dual-clock schema
  exists to preserve. The join (by `unit_name`, within a skew bound) is
  `perception.motion`'s job on the body-layer side, not this layer's.

A `GET /telemetry/since/{timestamp}` delta-query endpoint was implemented
and then dropped (stage 5): its cursor filtered on receipt time, not
content, so during a paused mission it returned every motionless sample as
"new" -- not a useful "changed" signal, and the body/brain consumer's
polling model doesn't need gap-free history anyway (it can just poll
`/latest` as often as it needs). See `plans/aircraft-layer/plan.md`. The
same reasoning applies to `/world_objects/latest` and
`/petrovich_indication/latest` -- no delta variant for either.

Runs `http.server.ThreadingHTTPServer` (stdlib only, per plan decision 4) in
the same process as `CollectorServer`, sharing one `TelemetryCache`, one
`WorldObjectsCache`, and one `PetrovichIndicationCache` instance — see
`collector.__main__`.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlparse

from collector.audio_sender import AudioPlaybackSender
from collector.cache import (
    F10CommandQueue,
    PetrovichIndicationCache,
    PetrovichWheelCache,
    PttCache,
    Spu8Cache,
    TelemetryCache,
    UnitVelocityCache,
    WorldObjectsCache,
)
from collector.command_sender import CommandSender, CommandSendError, SearchMode
from collector.text_sender import TextOverlaySender

logger = logging.getLogger(__name__)

#: LAN-facing by design, unlike `collector.server.DEFAULT_HOST`.
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 7791

_TELEMETRY_LATEST_PATH = "/telemetry/latest"
_WORLD_OBJECTS_LATEST_PATH = "/world_objects/latest"
_UNIT_VELOCITY_LATEST_PATH = "/unit_velocity/latest"
_PTT_STATE_PATH = "/ptt/state"
_SPU8_STATE_PATH = "/spu8/state"
_PETROVICH_INDICATION_LATEST_PATH = "/petrovich_indication/latest"
_PETROVICH_WHEEL_LATEST_PATH = "/petrovich_wheel/latest"
_TEXT_PUSH_PATH = "/text/push"
_COMMAND_PETROVICH_SEARCH_PATH = "/command/petrovich_search"
_F10_COMMANDS_POLL_PATH = "/f10_commands/poll"
_AUDIO_PLAY_PATH = "/audio/play"
_AUDIO_STOP_PATH = "/audio/stop"

#: `SearchMode`'s two valid wire values -- checked against the request
#: body's `mode` field before forwarding to `CommandSender.send_command`.
_VALID_SEARCH_MODES: tuple[SearchMode, ...] = ("forward", "boresight")


def _handle_telemetry_latest(cache: TelemetryCache) -> dict[str, Any] | None:
    sample = cache.latest()
    return None if sample is None else sample.to_dict()


def _handle_world_objects_latest(
    cache: WorldObjectsCache,
) -> dict[str, Any] | None:
    snapshot = cache.latest()
    return None if snapshot is None else snapshot.to_dict()


def _handle_unit_velocity_latest(
    cache: UnitVelocityCache,
) -> dict[str, Any] | None:
    snapshot = cache.latest()
    return None if snapshot is None else snapshot.to_dict()


def _handle_ptt_state(cache: PttCache, spu8_cache: Spu8Cache) -> dict[str, Any] | None:
    """`null` until the trigger first moves. That is the ordinary startup
    state, not an error -- `Export.lua` sends a line only on change, so an
    untouched trigger produces nothing. A consumer reads `null` as "not
    pressed", which is also what it means.

    **The served `"intercom"` field is already gated by the SPU-8 switches**
    (`plans/spu8-intercom/plan.md` Stage 2, plan Decision 1): `"intercom"`
    is `sample.intercom and spu8_gate_open`, where `spu8_gate_open` is
    `False` whenever `spu8_cache.latest() is None` -- fail-safe-closed, an
    unknown intercom state must not let capture through (plan Decision 3).
    `"radio"` is untouched -- a full press is talking to ATC/another
    player, independent of the SPU-8 gate. This is the entire capture-
    gating mechanism: `audio-adapter`'s `DcsPTT` already reads `"intercom"`
    verbatim off the wire, so no audio-adapter change is needed."""
    sample = cache.latest()
    if sample is None:
        return None
    spu8_sample = spu8_cache.latest()
    spu8_gate_open = spu8_sample is not None and spu8_sample.gate_open
    payload = sample.to_api_dict()
    payload["intercom"] = sample.intercom and spu8_gate_open
    return payload


def _handle_spu8_state(cache: Spu8Cache) -> dict[str, Any] | None:
    """`null` before the first SPU-8 line arrives -- same "not an error"
    posture as `/ptt/state`."""
    sample = cache.latest()
    return None if sample is None else sample.to_api_dict()


def _handle_petrovich_indication_latest(
    cache: PetrovichIndicationCache,
) -> dict[str, Any] | None:
    sample = cache.latest()
    return None if sample is None else sample.to_dict()


def _handle_petrovich_wheel_latest(
    cache: PetrovichWheelCache,
) -> dict[str, Any] | None:
    sample = cache.latest()
    return None if sample is None else sample.to_dict()


def _handle_f10_commands_poll(queue: F10CommandQueue) -> list[dict[str, Any]]:
    return [event.to_dict() for event in queue.drain_all()]


def _make_handler(
    cache: TelemetryCache,
    world_objects_cache: WorldObjectsCache,
    petrovich_indication_cache: PetrovichIndicationCache,
    petrovich_wheel_cache: PetrovichWheelCache,
    f10_command_queue: F10CommandQueue,
    text_sender: TextOverlaySender | None,
    command_sender: CommandSender | None,
    audio_sender: AudioPlaybackSender | None,
    unit_velocity_cache: UnitVelocityCache,
    ptt_cache: PttCache,
    spu8_cache: Spu8Cache,
) -> type[BaseHTTPRequestHandler]:
    class TelemetryRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == _TELEMETRY_LATEST_PATH:
                self._respond_json(200, _handle_telemetry_latest(cache))
                return
            if path == _WORLD_OBJECTS_LATEST_PATH:
                self._respond_json(
                    200, _handle_world_objects_latest(world_objects_cache)
                )
                return
            if path == _UNIT_VELOCITY_LATEST_PATH:
                self._respond_json(
                    200, _handle_unit_velocity_latest(unit_velocity_cache)
                )
                return
            if path == _PTT_STATE_PATH:
                self._respond_json(200, _handle_ptt_state(ptt_cache, spu8_cache))
                return
            if path == _SPU8_STATE_PATH:
                self._respond_json(200, _handle_spu8_state(spu8_cache))
                return
            if path == _PETROVICH_INDICATION_LATEST_PATH:
                self._respond_json(
                    200,
                    _handle_petrovich_indication_latest(petrovich_indication_cache),
                )
                return
            if path == _PETROVICH_WHEEL_LATEST_PATH:
                self._respond_json(
                    200, _handle_petrovich_wheel_latest(petrovich_wheel_cache)
                )
                return
            if path == _F10_COMMANDS_POLL_PATH:
                self._respond_json(200, _handle_f10_commands_poll(f10_command_queue))
                return
            self._respond_json(404, {"error": f"not found: {path}"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == _TEXT_PUSH_PATH:
                self._handle_text_push()
                return
            if path == _COMMAND_PETROVICH_SEARCH_PATH:
                self._handle_command_petrovich_search()
                return
            if path == _AUDIO_PLAY_PATH:
                self._handle_audio_play()
                return
            if path == _AUDIO_STOP_PATH:
                self._handle_audio_stop()
                return
            self._respond_json(404, {"error": f"not found: {path}"})

        def _handle_text_push(self) -> None:
            if text_sender is None:
                self._respond_json(503, {"error": "text push not configured"})
                return

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

            text_sender.send_line(text)
            self._respond_json(200, {"ok": True})

        def _handle_command_petrovich_search(self) -> None:
            if command_sender is None:
                self._respond_json(503, {"error": "command channel not configured"})
                return

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

            mode = data.get("mode")
            if mode not in _VALID_SEARCH_MODES:
                self._respond_json(
                    400,
                    {
                        "error": (
                            f"'mode' must be one of {_VALID_SEARCH_MODES}, got {mode!r}"
                        )
                    },
                )
                return

            try:
                command_sender.send_command(mode)
            except CommandSendError as exc:
                self._respond_json(500, {"error": str(exc)})
                return
            self._respond_json(200, {"ok": True})

        def _handle_audio_play(self) -> None:
            if audio_sender is None:
                self._respond_json(503, {"error": "audio playback not configured"})
                return

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

            audio_b64 = data.get("audio_b64")
            if not isinstance(audio_b64, str) or not audio_b64:
                self._respond_json(
                    400, {"error": "'audio_b64' must be a non-empty string"}
                )
                return
            try:
                audio = base64.b64decode(audio_b64, validate=True)
            except (binascii.Error, ValueError) as exc:
                self._respond_json(
                    400, {"error": f"'audio_b64' is not valid base64: {exc}"}
                )
                return
            if not audio:
                self._respond_json(400, {"error": "'audio_b64' decoded to no bytes"})
                return

            urgent = data.get("urgent", False)
            if not isinstance(urgent, bool):
                self._respond_json(400, {"error": "'urgent' must be a boolean"})
                return

            # Never raises -- see AudioPlaybackSender.play_audio's own
            # docstring and plan Decision 5 (this is /text/push's
            # never-raises posture, not /command/petrovich_search's
            # propagate-500 one).
            audio_sender.play_audio(audio, urgent)
            self._respond_json(200, {"ok": True})

        def _handle_audio_stop(self) -> None:
            """No request body is read -- `AudioPlaybackSender.interrupt`
            takes no arguments, so there is nothing to validate here
            (unlike every other `POST` handler above). Never raises --
            see `AudioPlaybackSender.interrupt`'s own docstring."""
            if audio_sender is None:
                self._respond_json(503, {"error": "audio playback not configured"})
                return
            audio_sender.interrupt()
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

    return TelemetryRequestHandler


class TelemetryAPIServer:
    """Owns the LAN-facing HTTP server; mirrors `CollectorServer`'s shape."""

    def __init__(
        self,
        cache: TelemetryCache,
        world_objects_cache: WorldObjectsCache | None = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        petrovich_indication_cache: PetrovichIndicationCache | None = None,
        text_sender: TextOverlaySender | None = None,
        petrovich_wheel_cache: PetrovichWheelCache | None = None,
        command_sender: CommandSender | None = None,
        f10_command_queue: F10CommandQueue | None = None,
        audio_sender: AudioPlaybackSender | None = None,
        unit_velocity_cache: UnitVelocityCache | None = None,
        ptt_cache: PttCache | None = None,
        spu8_cache: Spu8Cache | None = None,
    ) -> None:
        # `world_objects_cache`/`petrovich_indication_cache`/
        # `petrovich_wheel_cache`/`f10_command_queue`/`unit_velocity_cache`/
        # `spu8_cache` default to a fresh, never-populated cache/queue
        # rather than being required -- keeps every existing
        # `TelemetryAPIServer(cache, host=..., port=...)` call site (tests
        # included) working unchanged; the corresponding `/latest` (or
        # `/f10_commands/poll`) endpoint on such a server just always
        # answers `null` (or `[]`), same as an empty cache would -- and
        # `/ptt/state`'s served `"intercom"` correctly reads as fail-safe-
        # closed (plan Decision 3) against a never-populated `Spu8Cache`.
        # `text_sender`/`command_sender`/`audio_sender` default to `None`
        # rather than a real sender for the same reason --
        # `/text/push`/`/command/petrovich_search`/`/audio/play` answer
        # `503` rather than crashing when they aren't configured.
        self._cache = cache
        self._world_objects_cache = (
            world_objects_cache
            if world_objects_cache is not None
            else WorldObjectsCache()
        )
        self._petrovich_indication_cache = (
            petrovich_indication_cache
            if petrovich_indication_cache is not None
            else PetrovichIndicationCache()
        )
        self._petrovich_wheel_cache = (
            petrovich_wheel_cache
            if petrovich_wheel_cache is not None
            else PetrovichWheelCache()
        )
        self._f10_command_queue = (
            f10_command_queue if f10_command_queue is not None else F10CommandQueue()
        )
        self._unit_velocity_cache = (
            unit_velocity_cache
            if unit_velocity_cache is not None
            else UnitVelocityCache()
        )
        self._ptt_cache = ptt_cache if ptt_cache is not None else PttCache()
        self._spu8_cache = spu8_cache if spu8_cache is not None else Spu8Cache()
        self._text_sender = text_sender
        self._command_sender = command_sender
        self._audio_sender = audio_sender
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
            (self._host, self._port),
            _make_handler(
                self._cache,
                self._world_objects_cache,
                self._petrovich_indication_cache,
                self._petrovich_wheel_cache,
                self._f10_command_queue,
                self._text_sender,
                self._command_sender,
                self._audio_sender,
                self._unit_velocity_cache,
                self._ptt_cache,
                self._spu8_cache,
            ),
        )
        logger.info("telemetry API listening on %s:%d", self._host, self.port)

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
