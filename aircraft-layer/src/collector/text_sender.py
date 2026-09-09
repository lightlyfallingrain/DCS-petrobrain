"""Collector-side sender for the in-cockpit text overlay channel (BL-2.5).

This is the aircraft layer's first *outbound* hop -- everywhere else in this
module, data flows DCS -> collector -> LAN API. Here it flows the other way:
the collector fires short display strings at a DCS Hook-state overlay script
(`aircraft-layer/dcs-export/petrobrain-overlay-hook.lua`) over loopback UDP,
mirroring the SRS-client -> SRS-overlay relationship this design is modeled on
(`aircraft-layer/research/2026-09-09-dcs-text-panel-output-channel.md`,
Finding 8).

Delivery is fire-and-forget, by design (plan "Risks & Unknowns"): a `send_line`
call that returns without raising means only "the datagram was handed to the
OS," never "the line appeared on screen." A missing listener (DCS not running,
or running without the overlay Hook script loaded) is an expected, everyday
state -- the same "`null` is not an error" posture already used for the
`/latest` endpoints' empty-cache case -- so `send_line` must never raise.
"""

from __future__ import annotations

import json
import logging
import socket
from types import TracebackType
from typing import Self

logger = logging.getLogger(__name__)

#: Loopback only -- the Hook-state overlay script runs inside the same DCS
#: process tree as the collector's UDP peer, exactly like
#: `collector.server.DEFAULT_HOST`/`DEFAULT_PORT` for the inbound side.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7792

#: Defensive server-side length cap (plan "Message Model"). `AutoScrollText`'s
#: own skin-level wrapping is expected to handle every string under this cap
#: without further truncation; the native overflow/clip behavior for a
#: longer string is genuinely unverified by static recon (Session 2's own
#: "Unresolved"), so truncating here removes that edge case cheaply rather
#: than relying on the inference that it merely overflows rather than crashes.
MAX_LINE_LENGTH = 200


class TextOverlaySender:
    """Sends short display-text lines to the overlay Hook script over UDP.

    One socket is opened once (`open()`/`__enter__`) and reused for every
    `send_line` call, mirroring `CollectorServer`'s
    open-once/close-on-shutdown lifecycle even though UDP itself is
    connectionless -- this just avoids a syscall per send.
    """

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

    def send_line(self, text: str) -> None:
        """Push one display line to the overlay. Never raises.

        Truncates to `MAX_LINE_LENGTH` before sending. A missing/unreachable
        listener (DCS not running, overlay Hook script not loaded, or -- on
        Windows -- a prior ICMP port-unreachable putting the loopback UDP
        socket into a transient `ECONNRESET`-class error state) is an
        expected, non-error condition here, not a bug to surface to the
        caller -- it is logged at debug level and swallowed.
        """
        if self._socket is None:
            self.open()
        sock = self._socket
        assert sock is not None  # `open()` above always sets it

        truncated = text[:MAX_LINE_LENGTH]
        payload = json.dumps({"text": truncated}).encode("utf-8")
        try:
            sock.sendto(payload, (self._host, self._port))
        except OSError:
            logger.debug(
                "overlay send failed (listener likely absent): %r",
                truncated,
                exc_info=True,
            )
