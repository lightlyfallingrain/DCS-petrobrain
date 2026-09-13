"""Collector-side receiver for the F10 radio-menu command channel
(`plans/f10-crew-commands/plan.md`).

This is the aircraft layer's first **Hook-to-collector** inbound direction
-- every other channel in this module either flows DCS -> collector (the
telemetry/world-objects/indication feeds, `collector.server`) or
collector -> Hook/Export.lua (`text_sender.py`, `command_sender.py`). Here,
`petrobrain-f10-commands-hook.lua` sends one UDP datagram per drained F10
selection to this receiver over loopback, the reverse of that second
direction, mirroring `CollectorServer`'s own open()/serve_forever()/close()
lifecycle (a blocking receive loop run on a background thread by
`collector/__main__.py`) rather than owning its own thread internally.

**Validates every datagram against a fixed allowed-token vocabulary
(`ALLOWED_COMMANDS`) before enqueueing.** A malformed or unrecognized
payload is dropped and logged at debug level, never enqueued -- this keeps
this loopback socket from becoming a general remote-exec surface even
though only three fixed strings are ever meaningful downstream
(`belief.crew_console.CrewConsole.handle_f10_command`)."""

from __future__ import annotations

import json
import logging
import socket
import time
from types import TracebackType
from typing import Final, Self

from collector.cache import F10CommandQueue
from schema import F10CommandEvent, F10CommandParseError

logger = logging.getLogger(__name__)

#: Loopback only -- the Hook script runs inside the same DCS process tree
#: as the collector's UDP peer, exactly like every other channel in this
#: module. A fourth, distinct loopback port: `collector.server.DEFAULT_PORT`
#: (7790, Export.lua -> collector, TCP), `text_sender.DEFAULT_PORT` (7792,
#: collector -> overlay Hook, UDP), `command_sender.DEFAULT_PORT` (7793,
#: collector -> Export.lua command listener, UDP), and this one (7794,
#: Hook -> collector, UDP).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7794

#: The only three tokens `petrobrain-f10-commands-hook.lua` is registered
#: to ever send (its own registration snippet is the single source of
#: truth for the labels; this tuple is the single source of truth for
#: which tokens are accepted here) -- kept in sync by hand, per the plan's
#: "Risks & Unknowns" note. Adding a fourth command means adding one
#: literal here and one `missionCommands.addCommand` call in the Hook
#: script's registration snippet, nothing else.
ALLOWED_COMMANDS: Final[tuple[str, ...]] = (
    "watch_nearest",
    "scan_forward",
    "cancel_task",
)

_RECV_BUFFER_SIZE = 4096


class F10CommandReceiver:
    """Accepts F10-command datagrams from the Hook script and enqueues
    valid ones into an `F10CommandQueue`. Structurally mirrors
    `collector.server.CollectorServer`'s open()/serve_forever()/close()
    shape -- `serve_forever` is meant to be run on its own thread by the
    caller (see `collector/__main__.py`), not by this class itself."""

    def __init__(
        self,
        queue: F10CommandQueue,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._queue = queue
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
        """Bound port. Useful when constructed with `port=0` (OS-assigned),
        mirroring `api.server.TelemetryAPIServer.port`."""
        if self._socket is None:
            raise RuntimeError("call open() before reading port")
        return int(self._socket.getsockname()[1])

    def open(self) -> None:
        """Bind the receive socket. Does not block."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self._host, self._port))
        self._socket = sock
        logger.info("F10 command receiver listening on %s:%d", self._host, self._port)

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def serve_forever(self) -> None:
        """Receive datagrams and enqueue valid ones until `close()` is
        called from another thread (closing a bound UDP socket while a
        `recvfrom` is blocked on it raises `OSError`, which ends this
        loop -- same shutdown shape as `CollectorServer.serve_forever`)."""
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
            logger.debug("dropping malformed (non-JSON) F10 command datagram: %r", data)
            return
        if not isinstance(payload, dict):
            logger.debug("dropping non-object F10 command datagram: %r", data)
            return

        try:
            event = F10CommandEvent.from_dict(
                payload, received_wall_clock_s=time.time()
            )
        except F10CommandParseError:
            logger.debug("dropping malformed F10 command datagram: %r", data)
            return

        if event.command not in ALLOWED_COMMANDS:
            logger.debug("dropping unrecognized F10 command: %r", event.command)
            return

        logger.debug("enqueued F10 command: %r", event.command)
        self._queue.push(event)
