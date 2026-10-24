"""The one-shot read path's collector-side correlation point -- `plans/
effector-sequences/plan.md` Stage 4, S4.2 ("readback by need", option B).

**Synchronous at the collector, not an async ticket.** `POST
/query/read_args` blocks the HTTP worker thread for up to
`ARG_READ_TIMEOUT_S`, round-tripping a UDP command to `Export.lua` and
waiting for its TCP reply on the *existing* Export.lua<->collector
connection (`collector.server.CollectorServer`'s own socket, not a new
one) -- the collector is the one process already holding both sockets, so
the correlation belongs here rather than in body-layer (which would need
its own async polling) or in `Export.lua` (which cannot address a specific
HTTP caller). An async design (mint a request id now, poll for the reply
later) would delay a single-row "Observ on" switch flip by one full
body-layer poll (about 1 s) past today's timing -- see the plan's own
"Synchronous, not an async ticket" rationale.

`read_id` is minted by this broker itself (`secrets.token_hex(6)`, a
CSPRNG, not `random` -- good practice for a correlation key even though it
is never attacker-influenced here, per the security plan review), never
taken from the caller -- a LAN actor cannot predict or collide one."""

from __future__ import annotations

import logging
import secrets
import threading
from dataclasses import dataclass
from typing import Final

from collector.command_sender import CommandSender, CommandSendError
from schema import WatchedArgsParseError, parse_arg_values

logger = logging.getLogger(__name__)

#: A transport bound, not Petrovich behaviour -- about 15 frames at 60 fps.
#: Plain literal per root `CLAUDE.md`'s tuning rule (this is a protocol
#: constant, not something that changes what Petrovich does).
ARG_READ_TIMEOUT_S: Final[float] = 0.25

#: At most this many reads may be outstanding (sent, awaiting a reply) at
#: once; a ninth concurrent request is refused rather than queued -- bounds
#: how many `threading.Event` slots a request flood can hold open.
MAX_OUTSTANDING_READS: Final[int] = 8

#: `read_id` length, matching `Export.lua`'s own `[%w_]{1,16}` bound.
_READ_ID_HEX_CHARS: Final[int] = 6


class ArgReadTimeout(RuntimeError):
    """No reply arrived for a read request within `ARG_READ_TIMEOUT_S`."""


class ArgReadBrokerBusy(RuntimeError):
    """`MAX_OUTSTANDING_READS` requests are already in flight."""


@dataclass(frozen=True, slots=True)
class ArgReadResult:
    """One completed one-shot read -- the model time the reply carried,
    plus the validated arg->value map."""

    dcs_model_time_s: float
    values: dict[int, float]


class _Slot:
    __slots__ = ("event", "result")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: ArgReadResult | None = None


class ArgReadBroker:
    """Owns the outstanding-read slot table. One instance per collector
    process, shared between the API handler thread(s) that call `read`
    and the `CollectorServer` connection thread that calls
    `handle_reply_line` as each `"read_id"` TCP line arrives."""

    def __init__(self, command_sender: CommandSender) -> None:
        self._command_sender = command_sender
        self._lock = threading.Lock()
        self._slots: dict[str, _Slot] = {}

    def read(self, args: list[int]) -> ArgReadResult:
        """Requests `args` from `Export.lua` and blocks until the reply
        arrives or `ARG_READ_TIMEOUT_S` elapses.

        Raises `ArgReadBrokerBusy` if `MAX_OUTSTANDING_READS` requests are
        already outstanding; `CommandSendError` if the UDP send itself
        fails (no datagram was ever sent, so no slot is left behind);
        `ArgReadTimeout` if the datagram was sent but no reply (or only an
        invalid one, dropped at WARNING by `handle_reply_line`) arrived in
        time."""
        with self._lock:
            if len(self._slots) >= MAX_OUTSTANDING_READS:
                raise ArgReadBrokerBusy(
                    f"{MAX_OUTSTANDING_READS} reads already outstanding"
                )
            read_id = secrets.token_hex(_READ_ID_HEX_CHARS)
            slot = _Slot()
            self._slots[read_id] = slot

        try:
            self._command_sender.send_read_args(read_id, args)
        except CommandSendError:
            with self._lock:
                self._slots.pop(read_id, None)
            raise

        if not slot.event.wait(ARG_READ_TIMEOUT_S):
            with self._lock:
                # A reply racing this pop is simply dropped by
                # `handle_reply_line`'s own "unknown read_id" branch below
                # -- the slot is gone either way once this returns.
                self._slots.pop(read_id, None)
            raise ArgReadTimeout(
                f"no reply for read_id={read_id!r} within {ARG_READ_TIMEOUT_S}s"
            )

        with self._lock:
            self._slots.pop(read_id, None)
        assert slot.result is not None  # set together with event.set() below
        return slot.result

    def handle_reply_line(self, data: dict[str, object]) -> None:
        """Called by `collector.server.CollectorServer._handle_line` for a
        `"read_id"` line. Validates `"values"` with the same
        `schema.parse_arg_values` the continuous feed's `WatchedArgsState.
        from_dict` uses (security plan review required change 1) --
        a malformed reply is dropped at WARNING, and the waiting `read()`
        call times out to `ArgReadTimeout` rather than ever seeing a bad
        value. A reply for an unknown or already-timed-out `read_id` is
        dropped at DEBUG -- a late reply racing a timeout, or a stale one
        from a previous request, is expected, not an error."""
        read_id = data.get("read_id")
        if not isinstance(read_id, str):
            logger.warning("dropping read_args reply with no read_id: %r", data)
            return
        model_time = data.get("t")
        if isinstance(model_time, bool) or not isinstance(model_time, (int, float)):
            logger.warning("dropping read_args reply with bad/missing 't': %r", data)
            return
        try:
            values = parse_arg_values(data.get("values"))
        except WatchedArgsParseError:
            logger.warning("dropping malformed read_args reply values: %r", data)
            return

        with self._lock:
            slot = self._slots.get(read_id)
            if slot is None:
                logger.debug(
                    "dropping read_args reply for unknown/late read_id=%r", read_id
                )
                return
            slot.result = ArgReadResult(
                dcs_model_time_s=float(model_time), values=values
            )
            slot.event.set()
