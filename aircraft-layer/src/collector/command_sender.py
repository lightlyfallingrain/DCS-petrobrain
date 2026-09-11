"""Collector-side sender for the Petrovich-search command channel (BL-6,
`plans/bl6-commands-inspect-adapt/plan.md`).

This is the aircraft layer's **second** outbound hop, mirroring
`collector.text_sender.TextOverlaySender`'s DCS-ward flow: the collector
fires a small JSON command at `Export.lua`'s new inbound UDP listener over
loopback, the same "collector -> Export.lua" direction `TextOverlaySender`
already established for the in-cockpit overlay (BL-2.5).

**Deliberate asymmetry from `TextOverlaySender.send_line`, flagged
explicitly per the plan:** `send_line` never raises, because a missing
overlay listener is an expected, everyday state carrying an opaque display
string -- losing one line is cosmetic. `send_command` is different: it
drives a real effector (Petrovich's AI Wheel), and a dropped command is a
real behavioral gap the caller needs to know about, not a state to
silently swallow. `send_command` therefore raises `CommandSendError` on a
clearly-failed send (an `OSError` from the underlying socket), the same
raise-on-failure posture `aircraft_client.AircraftLayerClient.
push_text_line` already established for this project's other write path.
Note this still cannot promise the command *worked* -- UDP is
fire-and-forget, so a `send_command` call that does not raise means only
"the datagram was handed to the OS," never "Petrovich actually searched."
Live confirmation of that is `GET /petrovich_wheel/latest`'s job, not this
sender's."""

from __future__ import annotations

import json
import logging
import socket
from types import TracebackType
from typing import Literal, Self

logger = logging.getLogger(__name__)

#: Loopback only -- `Export.lua`'s new inbound command listener runs inside
#: the same DCS process tree as the collector's UDP peer, exactly like
#: `collector.text_sender.DEFAULT_HOST`/`DEFAULT_PORT` for the existing
#: outbound-to-overlay channel. A distinct port from both
#: `collector.server.DEFAULT_PORT` (Export.lua -> collector, TCP) and
#: `collector.text_sender.DEFAULT_PORT` (collector -> overlay Hook script,
#: UDP) -- this is a third, separate loopback channel.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7793

#: Petrovich search mode -- `"forward"` (`SRCH FWD`, a long wheel-button
#: hold) or `"boresight"` (`SRCH BRST`, a short press). Matches
#: `aircraft_client.AircraftLayerClient.trigger_petrovich_search`'s own
#: `Literal` exactly, the type flowing unchanged from body-layer's tool call
#: through this sender to Export.lua's JSON command.
SearchMode = Literal["forward", "boresight"]


class CommandSendError(RuntimeError):
    """Raised when `CommandSender.send_command` cannot hand its datagram to
    the OS -- see the module docstring for why this sender, unlike
    `TextOverlaySender`, does not swallow that failure."""


class CommandSender:
    """Sends short JSON command datagrams to `Export.lua`'s inbound command
    listener over UDP. Structurally mirrors `TextOverlaySender`'s
    open-once/close-on-shutdown lifecycle (see that class's own docstring
    for why, even though UDP is connectionless) -- only `send_command`'s
    failure posture differs."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
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
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def send_command(self, mode: SearchMode) -> None:
        """Send `{"op": "petrovich_search", "mode": mode}` to `Export.lua`'s
        command listener. Raises `CommandSendError` if the underlying socket
        send fails (see the module docstring for why this call, unlike
        `TextOverlaySender.send_line`, does not swallow that failure)."""
        if self._socket is None:
            self.open()
        sock = self._socket
        assert sock is not None  # `open()` above always sets it

        payload = json.dumps({"op": "petrovich_search", "mode": mode}).encode("utf-8")
        try:
            sock.sendto(payload, (self._host, self._port))
        except OSError as exc:
            logger.warning(
                "petrovich-search command send failed: mode=%r", mode, exc_info=True
            )
            raise CommandSendError(f"failed to send command {mode!r}: {exc}") from exc
