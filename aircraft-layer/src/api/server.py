"""Mac-facing LAN API for querying the collector's cached telemetry state.

Plan stage 4. Unlike `collector.server.CollectorServer` (loopback-only, the
Export.lua push hop), this server is LAN-reachable by design — it's the hop
the body/brain process, on either Windows or Mac (compute topology note in
`plans/aircraft-layer/plan.md`), polls over the network. Read-only: two GET
endpoints, no way to push data in through this server.

- `GET /telemetry/latest` -> the most recent sample as JSON, or JSON `null`
  if the cache is still empty (not an error — Export.lua may not have
  connected/sent anything yet).
- `GET /telemetry/since/<wall_clock_timestamp>` -> a JSON array of samples
  received strictly after that wall-clock timestamp, oldest first. An empty
  array is the normal "nothing changed" result, per
  `collector.cache.TelemetryCache.since`.

Runs `http.server.ThreadingHTTPServer` (stdlib only, per plan decision 4) in
the same process as `CollectorServer`, sharing one `TelemetryCache` instance
— see `collector.__main__`.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlparse

from collector.cache import TelemetryCache

logger = logging.getLogger(__name__)

#: LAN-facing by design, unlike `collector.server.DEFAULT_HOST`.
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 7791

_LATEST_PATH = "/telemetry/latest"
_SINCE_PREFIX = "/telemetry/since/"


def _handle_latest(cache: TelemetryCache) -> dict[str, Any] | None:
    sample = cache.latest()
    return None if sample is None else sample.to_dict()


def _handle_since(
    cache: TelemetryCache, cursor_wall_clock_s: float
) -> list[dict[str, Any]]:
    return [s.to_dict() for s in cache.since(cursor_wall_clock_s)]


def _make_handler(cache: TelemetryCache) -> type[BaseHTTPRequestHandler]:
    class TelemetryRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == _LATEST_PATH:
                self._respond_json(200, _handle_latest(cache))
                return
            if path.startswith(_SINCE_PREFIX):
                raw_cursor = path[len(_SINCE_PREFIX) :]
                try:
                    cursor = float(raw_cursor)
                except ValueError:
                    self._respond_json(
                        400, {"error": f"invalid timestamp: {raw_cursor!r}"}
                    )
                    return
                self._respond_json(200, _handle_since(cache, cursor))
                return
            self._respond_json(404, {"error": f"not found: {path}"})

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
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._cache = cache
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
            (self._host, self._port), _make_handler(self._cache)
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
