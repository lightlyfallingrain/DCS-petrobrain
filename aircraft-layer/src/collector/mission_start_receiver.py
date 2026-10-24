"""Collector-side receiver for the mission-start channel
(`plans/bl15-mission-start/plan.md`, BL-15 Stage 1).

Structurally mirrors `unit_velocity_receiver.UnitVelocityReceiver` --
`petrobrain-mission-start-hook.lua` sends one UDP datagram per
`onSimulationStart` firing (one-shot per mission start, not a per-poll
feed) to this receiver over loopback, which pushes it into a
`MissionStartCache`. Same open()/serve_forever()/close() lifecycle, meant
to run on its own background thread (`collector/__main__.py`).

Wire format, one JSON object per datagram (matches `schema.mission_start.
MissionStartEvent.from_dict`):

    {"sequence": <int>, "theatre": "<string>"|null}

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

from collector.cache import MissionStartCache
from schema import MissionStartEvent, MissionStartParseError

logger = logging.getLogger(__name__)

#: Loopback only, same reasoning as every other channel in this module.
#: A distinct loopback port: `collector.server.DEFAULT_PORT` (7790),
#: `text_sender.DEFAULT_PORT` (7792), `command_sender.DEFAULT_PORT` (7793),
#: 7794 (formerly the F10 command channel, retired by `BL-B96`),
#: `unit_velocity_receiver.DEFAULT_PORT` (7795),
#: `line_of_sight_receiver.DEFAULT_PORT` (7796),
#: `command_sender.LOOK_DIRECTION_DEFAULT_PORT` (7797),
#: `firing_receiver.DEFAULT_PORT` (7798), and this one (7799).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7799

_RECV_BUFFER_SIZE = 4096


class MissionStartReceiver:
    """Accepts mission-start datagrams from the Hook script and pushes
    valid ones into a `MissionStartCache`. Structurally mirrors
    `UnitVelocityReceiver`'s open()/serve_forever()/close() shape."""

    def __init__(
        self,
        cache: MissionStartCache,
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
        logger.info("mission start receiver listening on %s:%d", self._host, self._port)

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
            payload = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.debug(
                "dropping malformed (non-JSON) mission start datagram: %r", data
            )
            return
        if not isinstance(payload, dict):
            logger.debug("dropping non-object mission start datagram: %r", data)
            return

        try:
            event = MissionStartEvent.from_dict(
                payload, received_wall_clock_s=time.time()
            )
        except MissionStartParseError:
            logger.debug("dropping malformed mission start datagram: %r", data)
            return

        logger.debug(
            "mission start: sequence=%d theatre=%r", event.sequence, event.theatre
        )
        self._cache.push(event)
