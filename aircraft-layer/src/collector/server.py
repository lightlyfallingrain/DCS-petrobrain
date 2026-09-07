"""Local TCP listener that receives Export.lua's telemetry + world-objects push.

Export.lua is deliberately dumb (plan decision 2): it only ever pushes its
own ownship state (and, since `plans/pb1-perception-logger/plan.md` stage 3,
`LoGetWorldObjects` ground truth) to this local collector over loopback, and
never listens for or answers requests itself. This server is the other end
of that single push connection -- it accepts one connection at a time from
Export.lua running inside the same DCS install, reads newline-delimited JSON
lines, and feeds each parsed line into whichever of `TelemetryCache`/
`WorldObjectsCache` matches its shape.

Both line kinds share one connection and one JSON-lines wire format but have
distinct shapes: a telemetry line is a flat object with a top-level `"x"`
key; a world-objects line has a top-level `"objects"` key instead (see
`schema.TelemetrySample`/`schema.WorldObjectsSnapshot`). `_handle_line`
distinguishes them by that key's presence before parsing, rather than trying
one parser and falling back to the other on failure -- a genuinely malformed
line of either kind should be logged and dropped once, not misattributed to
the wrong schema's error message.

This module is intentionally thin. Its correctness against a real Export.lua
is validated by the live DCS mission test (plan stage 3), not by unit tests
-- the parsing and caching logic it delegates to (`schema.TelemetrySample`,
`schema.WorldObjectsSnapshot`, `TelemetryCache`, `WorldObjectsCache`) is
what's unit-tested.
"""

from __future__ import annotations

import json
import logging
import socket
import time
from types import TracebackType
from typing import Self

from collector.cache import TelemetryCache, WorldObjectsCache
from schema import (
    TelemetryParseError,
    TelemetrySample,
    WorldObjectParseError,
    WorldObjectsSnapshot,
)

logger = logging.getLogger(__name__)

#: Loopback-only by design -- Export.lua and the collector run on the same
#: Windows box (plan decision 2); nothing outside this machine should be able
#: to push telemetry samples.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7790


class CollectorServer:
    """Accepts a single local Export.lua connection and feeds a cache."""

    def __init__(
        self,
        cache: TelemetryCache,
        world_objects_cache: WorldObjectsCache,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._cache = cache
        self._world_objects_cache = world_objects_cache
        self._host = host
        self._port = port
        self._socket: socket.socket | None = None

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

    def open(self) -> None:
        """Bind and start listening. Does not block."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self._host, self._port))
        sock.listen(1)
        self._socket = sock
        logger.info("collector listening on %s:%d", self._host, self._port)

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def serve_forever(self) -> None:
        """Accept connections and feed the cache until interrupted.

        Export.lua connects once per mission (it reconnects in
        `LuaExportStart`/`LuaExportStop`), so this loop re-accepts after each
        disconnect rather than exiting.
        """
        if self._socket is None:
            raise RuntimeError("call open() before serve_forever()")
        while True:
            conn, addr = self._socket.accept()
            logger.info("Export.lua connected from %s", addr)
            try:
                self._handle_connection(conn)
            except OSError:
                logger.warning(
                    "Export.lua connection from %s dropped abruptly",
                    addr,
                    exc_info=True,
                )
            finally:
                conn.close()
                logger.info("Export.lua connection from %s closed", addr)

    def _handle_connection(self, conn: socket.socket) -> None:
        buffered = ""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                return
            buffered += chunk.decode("utf-8", errors="replace")
            while "\n" in buffered:
                line, buffered = buffered.split("\n", 1)
                self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        stripped = line.strip()
        if not stripped:
            return
        logger.debug("received line: %r", line)

        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            logger.warning("dropping malformed (non-JSON) line: %r", line)
            return
        if not isinstance(data, dict):
            logger.warning("dropping non-object line: %r", line)
            return

        if "objects" in data:
            try:
                snapshot = WorldObjectsSnapshot.from_dict(
                    data, received_wall_clock_s=time.time()
                )
            except WorldObjectParseError:
                logger.warning("dropping malformed world-objects line: %r", line)
                return
            logger.debug("parsed world-objects snapshot: %r", snapshot)
            self._world_objects_cache.push(snapshot)
            return

        try:
            sample = TelemetrySample.from_dict(data, received_wall_clock_s=time.time())
        except TelemetryParseError:
            logger.warning("dropping malformed telemetry line: %r", line)
            return
        logger.debug("parsed sample: %r", sample)
        self._cache.push(sample)
