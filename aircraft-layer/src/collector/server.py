"""Local TCP listener that receives Export.lua's telemetry + world-objects +
Petrovich-indication push.

Export.lua is deliberately dumb (plan decision 2): it only ever pushes its
own ownship state (and, since `plans/pb1-perception-logger/plan.md` stage 3,
`LoGetWorldObjects` ground truth, and since that plan's stage 4,
`list_indication(HELPERAI_DEVICE_ID)`'s raw dump) to this local collector
over loopback, and never listens for or answers requests itself. This
server is the other end of that single push connection -- it accepts one
connection at a time from Export.lua running inside the same DCS install,
reads newline-delimited JSON lines, and feeds each parsed line into
whichever of `TelemetryCache`/`WorldObjectsCache`/`PetrovichIndicationCache`
matches its shape.

All line kinds share one connection and one JSON-lines wire format but have
distinct shapes: a telemetry line is a flat object with a top-level `"x"`
key; a world-objects line has a top-level `"objects"` key instead; a
Petrovich-indication line has a top-level `"indication"` key instead; a
Petrovich-wheel line (BL-6, `plans/bl6-commands-inspect-adapt/plan.md`) has
a top-level `"wheel"` key instead; a push-to-talk line has a top-level
`"ptt"` key instead; a SPU-8 intercom-state line (`plans/spu8-intercom/
plan.md` Stage 1) has a top-level `"net1"` key instead (see
`schema.TelemetrySample`/`schema.WorldObjectsSnapshot`/
`schema.PetrovichIndicationSample`/`schema.PetrovichWheelSample`/
`schema.PttSample`/`schema.Spu8Sample`). `_handle_line` distinguishes them
by that key's presence before parsing, rather than trying each parser in
turn and falling back on failure -- a genuinely malformed line of any kind
should be logged and dropped once, not misattributed to the wrong schema's
error message.

This module is intentionally thin. Its correctness against a real Export.lua
is validated by the live DCS mission test (plan stage 3), not by unit tests
-- the parsing and caching logic it delegates to (`schema.TelemetrySample`,
`schema.WorldObjectsSnapshot`, `schema.PetrovichIndicationSample`,
`TelemetryCache`, `WorldObjectsCache`, `PetrovichIndicationCache`) is what's
unit-tested.
"""

from __future__ import annotations

import json
import logging
import socket
import time
from types import TracebackType
from typing import Self

from collector.cache import (
    PetrovichIndicationCache,
    PetrovichWheelCache,
    PttCache,
    Spu8Cache,
    TelemetryCache,
    WorldObjectsCache,
)
from schema import (
    PetrovichIndicationParseError,
    PetrovichIndicationSample,
    PetrovichWheelParseError,
    PetrovichWheelSample,
    PttParseError,
    PttSample,
    Spu8ParseError,
    Spu8Sample,
    TelemetryParseError,
    TelemetrySample,
    WorldObjectParseError,
    WorldObjectsSnapshot,
)

logger = logging.getLogger(__name__)


#: Wire-format version this collector expects the deployed `Export.lua` to
#: report on connect. Bump BOTH this and `EXPORT_SCRIPT_VERSION` in
#: `aircraft-layer/dcs-export/Export.lua` in the same commit whenever the wire
#: format changes.
#:
#: Export.lua is deployed by *copying* into `Saved Games\DCS\Scripts\`, so the
#: running copy can lag this repository silently and indefinitely. On
#: 2026-09-21 a sortie ran an `Export.lua` predating the `is_ownship` flag
#: (shipped 2026-09-09): ownship was evaluated as a detection candidate on
#: every poll, 4113 times in one flight, and a Windows probe plus an hour of
#: tracing went into a bug that did not exist in the code. A mismatch warning
#: costs one log line and makes that failure loud instead of invisible.
EXPECTED_EXPORT_VERSION = "2026-10-05"
#: Bumped 2026-10-05 (`plans/spu8-intercom/plan.md` Stage 1) for the new
#: SPU-8 intercom state feed (args 377/664/457, wire key "net1") -- an
#: additive wire-format change (an old deployed script keeps working, it
#: just never sends a "net1" line, so `Spu8Cache` stays empty and
#: downstream gating/volume default to their documented fail-safe/
#: backward-compatible values), but the version string still moves per
#: this file's own version-bump rule.
#: Bumped again 2026-09-22 (`b` suffix, `plans/movement-detection/plan.md`
#: Stage 1) for the `unit_name` field added to `WorldObjectSample` -- the
#: join key the unit-velocity feed needs (see `schema/world_objects.py`'s
#: docstring). Additive-only (an old deployed script keeps working, it just
#: never sends `unit_name`, and the schema tolerates its absence), but the
#: version string still moves so a stale-Export.lua sortie's `dcs.log`
#: reflects that this field cannot be trusted yet -- same "make the mismatch
#: loud" reasoning as the paragraph above, not a claim that this specific
#: change is unsafe to skip.
#: Loopback-only by design -- Export.lua and the collector run on the same
#: Windows box (plan decision 2); nothing outside this machine should be able
#: to push telemetry samples.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7790

#: Sleep before retrying `accept()` after an unexpected `OSError` (see
#: `serve_forever`'s own docstring) -- a persistent failure then degrades to
#: a slow retry loop instead of a hot CPU spin, and this is deliberately
#: coarser than any latency budget in this pipeline: the point is to stop
#: burning CPU on a channel that isn't recovering, not to bound recovery
#: time tightly.
_ACCEPT_ERROR_BACKOFF_S = 1.0


class CollectorServer:
    """Accepts a single local Export.lua connection and feeds a cache."""

    def __init__(
        self,
        cache: TelemetryCache,
        world_objects_cache: WorldObjectsCache,
        petrovich_indication_cache: PetrovichIndicationCache,
        petrovich_wheel_cache: PetrovichWheelCache,
        # Optional so every existing construction site -- and every test
        # that does not care about the trigger -- keeps working unchanged.
        # A collector without a PTT cache simply drops ptt lines, which is
        # the correct behaviour for one: nothing downstream is listening.
        ptt_cache: PttCache | None = None,
        # Same optional-cache reasoning as ptt_cache above: a collector
        # without a Spu8Cache simply drops "net1" lines.
        spu8_cache: Spu8Cache | None = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._cache = cache
        self._world_objects_cache = world_objects_cache
        self._petrovich_indication_cache = petrovich_indication_cache
        self._petrovich_wheel_cache = petrovich_wheel_cache
        self._ptt_cache = ptt_cache
        self._spu8_cache = spu8_cache
        self._host = host
        self._port = port
        self._socket: socket.socket | None = None
        # Set as the *first* statement of close(), before the socket is
        # actually closed -- see close()'s own comment for why the ordering
        # matters.
        self._shutting_down = False

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
        # Set *before* the socket is actually closed -- a blocked accept()
        # on another thread can only observe this closure after the
        # syscall below runs, so the flag write happens-before the OSError
        # it is meant to explain. See serve_forever()'s docstring for why
        # inferring shutdown from self._socket's value instead (the
        # previous approach) is not safe here.
        self._shutting_down = True
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def serve_forever(self) -> None:
        """Accept connections and feed the cache until interrupted.

        Export.lua connects once per mission (it reconnects in
        `LuaExportStart`/`LuaExportStop`), so this loop re-accepts after each
        disconnect rather than exiting.

        **`accept()` itself is guarded, not just `_handle_connection`.**
        Before this, an `OSError` from `accept()` (as opposed to from a
        connection already in hand) was unguarded -- structurally the same
        gap as the silent daemon-thread death found in the watch-reporting
        review, and named as latent hardening in the 2026-09-26 security
        review (no live trigger found, but the same shape cost a whole
        sortie once already on this project). A caught error that just
        loops back to `accept()` immediately would trade a dead thread for
        a hot CPU spin with no operator-visible signal, which is not
        obviously better -- so this logs at `ERROR` (visible in a default,
        non-`--debug` run, unlike every other line this module logs) and
        backs off `_ACCEPT_ERROR_BACKOFF_S` before retrying, so a persistent
        failure shows up in the collector's own log as a repeating `ERROR`
        line instead of either silence or a busy loop.

        `close()` from another thread also unblocks a pending `accept()`
        with an `OSError` -- that is the intended shutdown path, not a
        failure, and is distinguished from a real failure by the explicit
        `self._shutting_down` flag, **not** by inferring intent from
        `self._socket`'s value. `close()` does `self._socket.close()` then
        `self._socket = None` as two separate statements; a blocked
        `accept()` can raise from the `close()` call while `self._socket`
        still holds the (now-closed) old socket object, so checking
        `self._socket is None` in the `except` block below races that
        second statement -- confirmed live (not theoretical) to
        misclassify a clean shutdown as a failure on most runs. `close()`
        sets `self._shutting_down = True` as its *first* statement, before
        the socket is actually closed, so that flag's write always
        happens-before the `OSError` it is checked against. The socket
        used for each `accept()` call is still captured into a local
        (`sock`) at the top of the loop -- `close()` can flip `self._socket`
        to `None` on another thread at any point, so re-reading that
        attribute (as opposed to the separate `_shutting_down` flag) after
        the exception fires would risk calling `.accept()` on `None` on the
        very next iteration.
        """
        if self._socket is None:
            raise RuntimeError("call open() before serve_forever()")
        while True:
            sock = self._socket
            if sock is None:
                # close() ran on another thread since the previous
                # iteration -- intended shutdown, not a failure.
                return
            try:
                conn, addr = sock.accept()
            except OSError:
                if self._shutting_down:
                    # close() ran on another thread -- intended shutdown,
                    # not a failure.
                    return
                logger.exception(
                    "collector accept() failed unexpectedly -- Export.lua "
                    "ingest is stalled until this recovers; retrying in "
                    "%.1fs",
                    _ACCEPT_ERROR_BACKOFF_S,
                )
                time.sleep(_ACCEPT_ERROR_BACKOFF_S)
                continue
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

        if "export_version" in data:
            reported = str(data.get("export_version"))
            if reported == EXPECTED_EXPORT_VERSION:
                logger.info("Export.lua wire-format version %s (matches)", reported)
            else:
                logger.warning(
                    "Export.lua VERSION MISMATCH: deployed copy reports %s, this "
                    "collector expects %s. The deployed script is a COPY in "
                    "Saved Games\\DCS\\Scripts\\ and may be stale -- re-copy it "
                    "from aircraft-layer/dcs-export/Export.lua. Data from this "
                    "session may be missing fields this collector assumes.",
                    reported,
                    EXPECTED_EXPORT_VERSION,
                )
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

        if "indication" in data:
            try:
                indication_sample = PetrovichIndicationSample.from_dict(
                    data, received_wall_clock_s=time.time()
                )
            except PetrovichIndicationParseError:
                logger.warning("dropping malformed petrovich-indication line: %r", line)
                return
            logger.debug("parsed petrovich-indication sample: %r", indication_sample)
            self._petrovich_indication_cache.push(indication_sample)
            return

        if "ptt" in data:
            # Ahead of the telemetry fallthrough for the same reason every
            # other named kind is: a line carrying "ptt" is never a
            # telemetry sample, and letting it reach TelemetrySample.
            # from_dict would log it as malformed.
            try:
                ptt_sample = PttSample.from_dict(
                    data, received_wall_clock_s=time.time()
                )
            except PttParseError:
                logger.warning("dropping malformed ptt line: %r", line)
                return
            logger.debug("parsed ptt sample: %r", ptt_sample)
            if self._ptt_cache is not None:
                self._ptt_cache.push(ptt_sample)
            return

        if "wheel" in data:
            try:
                wheel_sample = PetrovichWheelSample.from_dict(
                    data, received_wall_clock_s=time.time()
                )
            except PetrovichWheelParseError:
                logger.warning("dropping malformed petrovich-wheel line: %r", line)
                return
            logger.debug("parsed petrovich-wheel sample: %r", wheel_sample)
            self._petrovich_wheel_cache.push(wheel_sample)
            return

        if "net1" in data:
            # Ahead of the telemetry fallthrough for the same reason the
            # "ptt" branch above is.
            try:
                spu8_sample = Spu8Sample.from_dict(
                    data, received_wall_clock_s=time.time()
                )
            except Spu8ParseError:
                logger.warning("dropping malformed spu8 line: %r", line)
                return
            logger.debug("parsed spu8 sample: %r", spu8_sample)
            if self._spu8_cache is not None:
                self._spu8_cache.push(spu8_sample)
            return

        try:
            sample = TelemetrySample.from_dict(data, received_wall_clock_s=time.time())
        except TelemetryParseError:
            logger.warning("dropping malformed telemetry line: %r", line)
            return
        logger.debug("parsed sample: %r", sample)
        self._cache.push(sample)
