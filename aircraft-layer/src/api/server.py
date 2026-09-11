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

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlparse

from collector.cache import (
    PetrovichIndicationCache,
    PetrovichWheelCache,
    TelemetryCache,
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
_PETROVICH_INDICATION_LATEST_PATH = "/petrovich_indication/latest"
_PETROVICH_WHEEL_LATEST_PATH = "/petrovich_wheel/latest"
_TEXT_PUSH_PATH = "/text/push"
_COMMAND_PETROVICH_SEARCH_PATH = "/command/petrovich_search"

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


def _make_handler(
    cache: TelemetryCache,
    world_objects_cache: WorldObjectsCache,
    petrovich_indication_cache: PetrovichIndicationCache,
    petrovich_wheel_cache: PetrovichWheelCache,
    text_sender: TextOverlaySender | None,
    command_sender: CommandSender | None,
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
            self._respond_json(404, {"error": f"not found: {path}"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == _TEXT_PUSH_PATH:
                self._handle_text_push()
                return
            if path == _COMMAND_PETROVICH_SEARCH_PATH:
                self._handle_command_petrovich_search()
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
    ) -> None:
        # `world_objects_cache`/`petrovich_indication_cache`/
        # `petrovich_wheel_cache` default to a fresh, never-populated cache
        # rather than being required -- keeps every existing
        # `TelemetryAPIServer(cache, host=..., port=...)` call site (tests
        # included) working unchanged; the corresponding `/latest` endpoint
        # on such a server just always answers `null`, same as an empty
        # cache would. `text_sender`/`command_sender` default to `None`
        # rather than a real sender for the same reason -- `/text/push`/
        # `/command/petrovich_search` answer `503` rather than crashing
        # when they aren't configured.
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
        self._text_sender = text_sender
        self._command_sender = command_sender
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
                self._text_sender,
                self._command_sender,
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
