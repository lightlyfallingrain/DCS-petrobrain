"""Collector-side receiver for the unit-velocity channel
(`plans/movement-detection/plan.md` Stage 1).

Structurally mirrors `f10_command_receiver.F10CommandReceiver` -- the second
Hook-to-collector inbound direction (the first was the F10 command channel):
`petrobrain-mission-telemetry-hook.lua` sends one UDP datagram per poll (1 Hz)
to this receiver over loopback, carrying the whole poll's unit-velocity
snapshot rather than one event per datagram like the F10 channel. Same
open()/serve_forever()/close() lifecycle, meant to run on its own background
thread (`collector/__main__.py`).

Wire format, one JSON object per datagram (matches `schema.unit_velocity.
UnitVelocitySnapshot.from_wire`):

    {"payload": "<count>|<t_sim>|<entries>", "bridge_call_ms": <float>}

A malformed or unparseable datagram is dropped and logged at debug level,
never crashes the receive loop -- same defensive posture as
`F10CommandReceiver._handle_datagram` and `collector.server._handle_line`."""

from __future__ import annotations

import json
import logging
import socket
import time
from types import TracebackType
from typing import Self

from collector.cache import UnitVelocityCache
from schema.unit_velocity import UnitVelocityParseError, UnitVelocitySnapshot

logger = logging.getLogger(__name__)

#: Loopback only, same reasoning as every other channel in this module.
#: A fifth, distinct loopback port: `collector.server.DEFAULT_PORT` (7790),
#: `text_sender.DEFAULT_PORT` (7792), `command_sender.DEFAULT_PORT` (7793),
#: `f10_command_receiver.DEFAULT_PORT` (7794), and this one (7795).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7795

_RECV_BUFFER_SIZE = 65536


class UnitVelocityReceiver:
    """Accepts unit-velocity snapshot datagrams from the mission-telemetry
    Hook script and pushes valid ones into a `UnitVelocityCache`. Structurally
    mirrors `F10CommandReceiver`'s open()/serve_forever()/close() shape."""

    def __init__(
        self,
        cache: UnitVelocityCache,
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
        logger.info("unit velocity receiver listening on %s:%d", self._host, self._port)

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def serve_forever(self) -> None:
        """Receive datagrams and push valid ones until `close()` is called
        from another thread -- same shutdown shape as
        `F10CommandReceiver.serve_forever`."""
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
                "dropping malformed (non-JSON) unit velocity datagram: %r", data
            )
            return
        if not isinstance(envelope, dict):
            logger.debug("dropping non-object unit velocity datagram: %r", data)
            return

        payload = envelope.get("payload")
        bridge_call_ms = envelope.get("bridge_call_ms")
        if not isinstance(payload, str) or isinstance(bridge_call_ms, bool):
            logger.debug("dropping malformed unit velocity envelope: %r", envelope)
            return
        if not isinstance(bridge_call_ms, int | float):
            logger.debug("dropping malformed unit velocity envelope: %r", envelope)
            return

        try:
            snapshot = UnitVelocitySnapshot.from_wire(
                payload,
                bridge_call_ms=float(bridge_call_ms),
                received_wall_clock_s=time.time(),
            )
        except UnitVelocityParseError:
            logger.debug("dropping malformed unit velocity payload: %r", payload)
            return

        logger.debug(
            "unit velocity snapshot: unit_count=%d bridge_call_ms=%.2f",
            snapshot.unit_count,
            snapshot.bridge_call_ms,
        )
        self._cache.push(snapshot)
