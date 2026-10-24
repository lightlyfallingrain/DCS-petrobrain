"""Collector-side receiver for the DCS-driven line-of-sight channel
(`plans/dcs-driven-los/plan.md`, X-B29).

Structurally mirrors `unit_velocity_receiver.UnitVelocityReceiver` -- the
second Hook-to-collector inbound-direction channel (after unit
velocity; `BL-B96` removed the original first, the F10 command channel):
`petrobrain-line-of-sight-hook.lua` sends one UDP datagram per
poll (1 Hz) to this receiver over loopback, carrying the whole poll's
line-of-sight snapshot. Same open()/serve_forever()/close() lifecycle, run
on its own background thread (`collector/__main__.py`).

Wire format, one JSON object per datagram (matches `schema.line_of_sight.
LineOfSightSnapshot.from_wire`):

    {"payload": "<units_in_bubble>|<units_in_wedge>|<sightlines_computed>|"
                "<hour_used>|<fov_half_deg_used>|<t_sim>|<entries>",
     "bridge_call_ms": <float>}

A malformed or unparseable datagram is dropped and logged at debug level,
never crashes the receive loop -- same defensive posture as
`UnitVelocityReceiver._handle_datagram`."""

from __future__ import annotations

import json
import logging
import socket
import time
from types import TracebackType
from typing import Self

from collector.cache import LineOfSightCache
from schema.line_of_sight import LineOfSightParseError, LineOfSightSnapshot

logger = logging.getLogger(__name__)

#: Loopback only, same reasoning as every other channel in this module. A
#: distinct loopback port: `collector.server.DEFAULT_PORT` (7790),
#: 7792 (formerly `text_sender.TextOverlaySender`, retired by `BL-B96`), `command_sender.DEFAULT_PORT` (7793),
#: 7794 (formerly the F10 command channel, retired by `BL-B96`),
#: `unit_velocity_receiver.DEFAULT_PORT` (7795), and this one (7796).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7796

_RECV_BUFFER_SIZE = 65536


class LineOfSightReceiver:
    """Accepts line-of-sight snapshot datagrams from the LOS Hook script
    and pushes valid ones into a `LineOfSightCache`. Structurally mirrors
    `UnitVelocityReceiver`'s open()/serve_forever()/close() shape."""

    def __init__(
        self,
        cache: LineOfSightCache,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._cache = cache
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

    @property
    def port(self) -> int:
        """Bound port. Useful when constructed with `port=0` (OS-assigned)."""
        if self._socket is None:
            raise RuntimeError("call open() before reading port")
        return int(self._socket.getsockname()[1])

    def open(self) -> None:
        """Bind the receive socket. Does not block."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self._host, self._port))
        self._socket = sock
        logger.info("line of sight receiver listening on %s:%d", self._host, self._port)

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def serve_forever(self) -> None:
        """Receive datagrams and push valid ones until `close()` is called
        from another thread -- same shutdown shape as
        `UnitVelocityReceiver.serve_forever`."""
        if self._socket is None:
            raise RuntimeError("call open() before serve_forever()")
        while True:
            try:
                data, _addr = self._socket.recvfrom(_RECV_BUFFER_SIZE)
            except OSError:
                return
            self._handle_datagram(data)

    def _handle_datagram(self, data: bytes) -> None:
        try:
            envelope = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.debug(
                "dropping malformed (non-JSON) line of sight datagram: %r", data
            )
            return
        if not isinstance(envelope, dict):
            logger.debug("dropping non-object line of sight datagram: %r", data)
            return

        payload = envelope.get("payload")
        bridge_call_ms = envelope.get("bridge_call_ms")
        if not isinstance(payload, str) or isinstance(bridge_call_ms, bool):
            logger.debug("dropping malformed line of sight envelope: %r", envelope)
            return
        if not isinstance(bridge_call_ms, int | float):
            logger.debug("dropping malformed line of sight envelope: %r", envelope)
            return

        try:
            snapshot = LineOfSightSnapshot.from_wire(
                payload,
                bridge_call_ms=float(bridge_call_ms),
                received_wall_clock_s=time.time(),
            )
        except LineOfSightParseError:
            logger.debug("dropping malformed line of sight payload: %r", payload)
            return

        logger.debug(
            "line of sight snapshot: units_in_bubble=%d units_in_wedge=%d "
            "sightlines_computed=%d bridge_call_ms=%.2f",
            snapshot.units_in_bubble,
            snapshot.units_in_wedge,
            snapshot.sightlines_computed,
            snapshot.bridge_call_ms,
        )
        self._cache.push(snapshot)
