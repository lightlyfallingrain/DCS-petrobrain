"""Collector-side receiver and emitter state machine for the firing-event
channel -- `plans/emitter-visibility/plan.md` Stage B (`AC-B8`).

**The state machine lives here, not in body-layer.** `perception/` is
deliberately recomputed-per-poll and stateless (the plan's "Answers to the
five design questions" #1) -- body-layer's job is to turn "who is
currently emitting" into visibility and callouts, not to own the latch and
watchdog that decide *who that is*. Mirrors `UnitVelocityReceiver`/
`LineOfSightReceiver`'s open()/serve_forever()/close() lifecycle for the
network half; `EmitterTracker` below is the new piece, a small stateful
machine fed raw, already-parsed `FiringRawEvent`s and queried for a
poll-shaped snapshot (`GET /firing/latest`, `api.server`).

**The latch and the watchdog, from the plan's "Co-moving Fields" table:**

- `S_EVENT_SHOOTING_START` opens an entry: `since_sim` = the event's own
  time, `expires_at_sim = now + FIRING_WATCHDOG_S` -- a start whose end
  never arrives (the unit dies mid-burst and no `S_EVENT_SHOOTING_END`
  follows) is still bounded, so no entry outlives its watchdog whatever
  the event stream does or fails to do.
- `S_EVENT_SHOOTING_END` tightens the same entry's expiry to
  `max(now, since_sim + FIRING_MIN_VISIBLE_S)` -- **one formula covers
  both of the plan's two END rows** (a same-batch END right after START,
  and a later-batch END arriving after the unit had already been firing
  for a while): if `since_sim` is recent, the `max` resolves to
  `since_sim + FIRING_MIN_VISIBLE_S`, which is comfortably in the future --
  a sub-poll burst still survives at least one body-layer poll. If
  `since_sim` is old (the unit had already been firing long enough that
  `FIRING_MIN_VISIBLE_S` has already elapsed), the `max` resolves to `now`,
  and the entry is gone on the very next `snapshot()` -- exactly the
  plan's "gone on the next poll at the latest."
- `S_EVENT_DEAD`/`S_EVENT_CRASH` naming a unit with an open `FIRING` entry
  removes that entry outright, independent of its watchdog -- a dead unit
  is not firing, and does not wait for a timer to say so.
- Every ingest call prunes entries past their own `expires_at_sim` against
  the *batch's own* `dcs_model_time_s` -- this is what makes the watchdog
  real: an entry with no further events at all still disappears once its
  own expiry passes.

**Mission-restart reset.** `dcs_model_time_s` going backwards between two
ingested batches (a new mission, or a bridge reconnect) clears every
tracked entry -- "no entry survives a mission boundary" (plan). A small
negative tolerance (`_RESTART_TOLERANCE_S`) absorbs harmless jitter between
two polls of the *same* running mission (the Hook's own `timer.getTime()`
is monotonic within one mission, but two samples a second apart are not
guaranteed byte-identical across the collector's own receive ordering)."""

from __future__ import annotations

import json
import logging
import socket
import time
from types import TracebackType
from typing import Final, Self

from schema.firing import FiringEventBatch, FiringParseError, FiringRawEvent

logger = logging.getLogger(__name__)

#: Loopback only, same reasoning as every other channel in this module. An
#: eighth, distinct loopback port: `collector.server.DEFAULT_PORT` (7790),
#: `text_sender.DEFAULT_PORT` (7792), `command_sender.DEFAULT_PORT` (7793),
#: `f10_command_receiver.DEFAULT_PORT` (7794),
#: `unit_velocity_receiver.DEFAULT_PORT` (7795),
#: `line_of_sight_receiver.DEFAULT_PORT` (7796),
#: `command_sender.LOOK_DIRECTION_DEFAULT_PORT` (7797), and this one (7798).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7798

_RECV_BUFFER_SIZE = 65536

#: `EmitterTracker`'s only entry kind today -- `S_EVENT_SHOT`'s
#: `LAUNCH_SMOKE` seam (`[[BL-B74]]`) is not built, so the tracker never
#: produces anything else. A bare string, not an import of body-layer's
#: `perception.emitters.EmitterKind` -- aircraft-layer does not depend on
#: body-layer (root `CLAUDE.md`'s "Module independence"), so the two sides
#: agree on this string by convention, the same way `source.py`'s
#: `PROVENANCE_EMITTER_*` constants agree with `perception.emitters.
#: EmitterKind.value` by convention rather than a shared import.
EMITTER_KIND_FIRING: Final[str] = "firing"

#: **Behaviour-affecting -- how long a gun-fire sighting survives one body-
#: layer poll past the `S_EVENT_SHOOTING_END` that closed it (or past the
#: `S_EVENT_SHOOTING_START` that opened it, if no `END` has arrived yet).**
#: A *smaller* value here risks a sub-poll burst (`START`/`END` landing in
#: the same drained batch, plan "Co-moving Fields" row 2) going invisible
#: before body-layer's own 1 Hz poll ever samples it; a *larger* value
#: keeps reporting a unit as firing after it has actually stopped. Set to
#: the poll interval itself (1.0 s, matching every `dostring_in`-based feed
#: in this codebase) plus a safety margin, so a burst landing anywhere in
#: one poll window is guaranteed visible to the very next body-layer poll.
#: **This subproject has no `tuning.*` loader yet** (unlike body-layer,
#: root `CLAUDE.md`'s "Behaviour-affecting constants are tunable" section)
#: -- declared as an ordinary module constant; flagged in the implementer's
#: report as a candidate for that mechanism if/when aircraft-layer grows
#: one.
FIRING_MIN_VISIBLE_S: Final[float] = 1.5

#: **Behaviour-affecting -- the longest a `FIRING` entry survives with no
#: `S_EVENT_SHOOTING_END` ever arriving** (the unit is destroyed mid-burst,
#: or the `END` event is lost). A *smaller* value risks closing an entry
#: while the unit is still genuinely firing (a long burst with no gap); a
#: *larger* value risks showing a unit as firing well after it stopped, if
#: its `END` event is ever dropped by the bridge. Set generously above any
#: plausible single burst duration (`FIRING_MIN_VISIBLE_S` already covers
#: the short-burst case; this is the backstop for the no-`END`-at-all case,
#: not the ordinary path). Same no-tuning-mechanism-yet note as
#: `FIRING_MIN_VISIBLE_S` above.
FIRING_WATCHDOG_S: Final[float] = 10.0

#: Absorbs harmless non-monotonicity between two polls of the *same*
#: running mission (see module docstring's "Mission-restart reset" note) --
#: a real mission restart resets `timer.getTime()` to (near) zero, which is
#: seconds of regression, not a sub-second jitter.
_RESTART_TOLERANCE_S: Final[float] = 0.5

#: Event kinds that remove an open `FIRING` entry for the unit they name,
#: independent of its watchdog -- "a dead unit is not firing" (plan
#: "Co-moving Fields" row: "initiator seen as `S_EVENT_DEAD`/`_CRASH`...
#: the `FIRING` entry is removed").
_DEATH_KINDS: Final[frozenset[str]] = frozenset({"S_EVENT_DEAD", "S_EVENT_CRASH"})


class ActiveEmitter:
    """One unit's currently-tracked emitter state. Mutable (plain
    attributes, not frozen) -- `EmitterTracker` updates `expires_at_sim` in
    place as further events arrive for the same unit, mirroring
    `LiveLosCoverage`'s own "mutable, updated in place" posture on the
    body-layer side."""

    __slots__ = ("expires_at_sim", "kind", "since_sim", "targets_ownship")

    def __init__(
        self,
        kind: str,
        since_sim: float,
        expires_at_sim: float,
        targets_ownship: bool,
    ) -> None:
        self.kind = kind
        self.since_sim = since_sim
        self.expires_at_sim = expires_at_sim
        self.targets_ownship = targets_ownship

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "since_sim": self.since_sim,
            "targets_ownship": self.targets_ownship,
        }


class EmitterTracker:
    """The latch/watchdog state machine (module docstring). `ingest()` is
    the only mutator, called once per received `FiringEventBatch`;
    `snapshot()` is a pure read, called once per `GET /firing/latest`.
    Thread safety: both are called from different threads in the real
    wiring (the receiver's background thread ingests, the API server's
    request-handling threads read) -- `dict` mutation/iteration under the
    GIL is the same "effectively atomic enough" posture
    `F10CommandQueue.drain_all`'s own docstring already accepts for this
    codebase; no lock is taken."""

    def __init__(self) -> None:
        self._active: dict[str, ActiveEmitter] = {}
        self._last_dcs_model_time_s: float | None = None

    def ingest(self, batch: FiringEventBatch) -> None:
        """Apply one poll's drained events, in order, then prune every
        entry whose `expires_at_sim` the batch's own `dcs_model_time_s` has
        passed. Events are applied in the order the Hook script drained
        them, which is event-arrival order within that poll -- a `START`
        followed later in the same batch by its own `END` therefore
        applies the `START` branch first, then the `END` branch tightens
        the same entry's expiry, exactly the "same drained batch" case the
        module docstring's latch formula is built to handle."""
        now = batch.dcs_model_time_s
        if (
            self._last_dcs_model_time_s is not None
            and now < self._last_dcs_model_time_s - _RESTART_TOLERANCE_S
        ):
            logger.info(
                "firing tracker: dcs_model_time_s regressed (%.2f -> %.2f), "
                "treating as a mission boundary -- clearing all emitter state",
                self._last_dcs_model_time_s,
                now,
            )
            self._active.clear()
        self._last_dcs_model_time_s = now

        for event in batch.events:
            self._apply(event, now)

        for name in [
            name
            for name, emitter in self._active.items()
            if now > emitter.expires_at_sim
        ]:
            del self._active[name]

    def _apply(self, event: FiringRawEvent, now: float) -> None:
        if event.kind == "S_EVENT_SHOOTING_START":
            self._active[event.initiator] = ActiveEmitter(
                kind=EMITTER_KIND_FIRING,
                since_sim=event.t_sim,
                expires_at_sim=now + FIRING_WATCHDOG_S,
                targets_ownship=event.targets_ownship,
            )
        elif event.kind == "S_EVENT_SHOOTING_END":
            existing = self._active.get(event.initiator)
            if existing is not None and existing.kind == EMITTER_KIND_FIRING:
                existing.expires_at_sim = max(
                    now, existing.since_sim + FIRING_MIN_VISIBLE_S
                )
        elif event.kind in _DEATH_KINDS:
            existing = self._active.get(event.initiator)
            # "a `LAUNCH_SMOKE` entry is kept" (plan) -- not reachable today
            # since no `LAUNCH_SMOKE` entry is ever created, but the kind
            # check is left explicit rather than an unconditional `del` so
            # this method does not have to be revisited the day `[[BL-B74]]`
            # starts creating them.
            if existing is not None and existing.kind == EMITTER_KIND_FIRING:
                del self._active[event.initiator]
        # `S_EVENT_SHOT` -- the `[[BL-B74]]` seam, deliberately a no-op here
        # (module docstring, and `schema.firing`'s own "build the seam, not
        # the feature" note). The raw event is still parsed and reaches
        # this method; it is simply not acted on.

    def snapshot(self) -> dict[str, object]:
        """A plain, JSON-ready dict -- `GET /firing/latest`'s body
        (`api.server._handle_firing_latest`), mirroring every other
        `*Snapshot.to_dict()` shape in this module even though this one is
        computed on demand rather than stored. `None` entries never
        appear: `active` only ever holds units this tracker currently
        believes are emitting."""
        return {
            "dcs_model_time_s": self._last_dcs_model_time_s,
            "received_wall_clock_s": time.time(),
            "active": {
                name: emitter.to_dict() for name, emitter in self._active.items()
            },
        }


class FiringEventsReceiver:
    """Accepts firing-event-batch datagrams from the Hook script and feeds
    valid ones into an `EmitterTracker`. Structurally mirrors
    `LineOfSightReceiver`'s open()/serve_forever()/close() shape -- the
    one difference is what it hands the parsed payload to (`tracker.
    ingest()`, not `cache.push()`), because this feed needs a state
    machine, not a latest-of-one cache (module docstring)."""

    def __init__(
        self,
        tracker: EmitterTracker,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._tracker = tracker
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
        logger.info("firing events receiver listening on %s:%d", self._host, self._port)

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def serve_forever(self) -> None:
        """Receive datagrams and ingest valid ones until `close()` is
        called from another thread -- same shutdown shape as
        `LineOfSightReceiver.serve_forever`."""
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
                "dropping malformed (non-JSON) firing-events datagram: %r", data
            )
            return
        if not isinstance(envelope, dict):
            logger.debug("dropping non-object firing-events datagram: %r", data)
            return

        payload = envelope.get("payload")
        bridge_call_ms = envelope.get("bridge_call_ms")
        if not isinstance(payload, str) or isinstance(bridge_call_ms, bool):
            logger.debug("dropping malformed firing-events envelope: %r", envelope)
            return
        if not isinstance(bridge_call_ms, int | float):
            logger.debug("dropping malformed firing-events envelope: %r", envelope)
            return

        try:
            batch = FiringEventBatch.from_wire(
                payload,
                bridge_call_ms=float(bridge_call_ms),
                received_wall_clock_s=time.time(),
            )
        except FiringParseError:
            logger.debug("dropping malformed firing-events payload: %r", payload)
            return

        if batch.events:
            logger.debug(
                "firing events batch: n=%d bridge_call_ms=%.2f",
                len(batch.events),
                batch.bridge_call_ms,
            )
        self._tracker.ingest(batch)
