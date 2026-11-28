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
  never arrives for a unit that is destroyed mid-burst is *not* what this
  bounds (that case is removed immediately by the `S_EVENT_DEAD`/`_CRASH`
  path below, independent of the watchdog); it bounds a start whose end
  never arrives because the event itself is dropped while the unit is
  still alive and still firing, so no entry outlives its watchdog whatever
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
- `S_EVENT_DEAD`/`S_EVENT_CRASH` naming a unit with an open `FIRING` or
  `LAUNCH_FLASH` entry removes that entry outright, independent of its
  watchdog -- a dead unit is not firing, and does not wait for a timer to
  say so.
- Every ingest call prunes entries past their own `expires_at_sim` against
  the *batch's own* `dcs_model_time_s` -- this is what makes the watchdog
  real: an entry with no further events at all still disappears once its
  own expiry passes.
- `S_EVENT_SHOT` (`[[BL-B124]]` Stage 5) opens/refreshes a `LAUNCH_FLASH`
  entry for the initiator: `since_sim` = the event's own time,
  `expires_at_sim = now + LAUNCH_FLASH_DURATION_S` -- a fixed, few-second
  window, never watchdog-extended by further events the way `FIRING` is.
  Never overwrites an existing `FIRING` entry for the same unit.

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

from schema.firing import (
    FiringEventBatch,
    FiringParseError,
    FiringRawEvent,
    MissionClockSample,
    OwnWeaponRawEvent,
)

logger = logging.getLogger(__name__)

#: Loopback only, same reasoning as every other channel in this module. An
#: distinct loopback port: `collector.server.DEFAULT_PORT` (7790),
#: 7792 (formerly `text_sender.TextOverlaySender`, retired by `BL-B96`), `command_sender.DEFAULT_PORT` (7793),
#: 7794 (formerly the F10 command channel, retired by `BL-B96`),
#: `unit_velocity_receiver.DEFAULT_PORT` (7795),
#: `line_of_sight_receiver.DEFAULT_PORT` (7796),
#: `command_sender.LOOK_DIRECTION_DEFAULT_PORT` (7797), and this one (7798).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7798

_RECV_BUFFER_SIZE = 65536

#: `EmitterTracker`'s gun-fire entry kind. A bare string, not an import of
#: body-layer's `perception.emitters.EmitterKind` -- aircraft-layer does
#: not depend on body-layer (root `CLAUDE.md`'s "Module independence"), so
#: the two sides agree on this string by convention, the same way
#: `source.py`'s `PROVENANCE_EMITTER_*` constants agree with `perception.
#: emitters.EmitterKind.value` by convention rather than a shared import.
#: `EMITTER_KIND_LAUNCH_FLASH` below is this tracker's second entry kind
#: (`[[BL-B124]]` Stage 5); `S_EVENT_SHOT`'s `LAUNCH_SMOKE` seam
#: (`[[BL-B74]]`) is still not built, so those two remain the only two.
EMITTER_KIND_FIRING: Final[str] = "firing"

#: `[[BL-B124]]` Stage 5 -- a missile/rocket launch's few-second light
#: source (`S_EVENT_SHOT`, treated the same for missiles and rockets per
#: the user's own words, `explore-notes.md`: "Treat missile and rocket
#: launch similarly"). Never `EmitterKind.LAUNCH_SMOKE`'s name
#: (`[[BL-B74]]`'s own long decaying smoke tail, explicitly out of scope
#: here -- the user's own distinction, "the plume is there for a few
#: seconds. And smoke trail, though that we do not see in the dark").
EMITTER_KIND_LAUNCH_FLASH: Final[str] = "launch_flash"

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
#: further event naming the same unit at all.** This is NOT the backstop
#: for "the unit was destroyed mid-burst" -- that case is handled
#: immediately and unconditionally by the `S_EVENT_DEAD`/`_CRASH` removal
#: path below (`_DEATH_KINDS`), independent of this timer. This watchdog's
#: only remaining real case is "`S_EVENT_SHOOTING_END` never arrives for a
#: unit that is still alive and still firing" -- the bridge drops the
#: `END` event, or (per `aircraft-layer/research/2026-09-24-damage-and-
#: firing-events-over-mission-bridge.md`, lines ~178-179) `S_EVENT_
#: SHOOTING_START` turns out not to retrigger mid-burst, in which case a
#: sustained engagement (continuous AAA holding the player, exactly this
#: feature's own target scenario) produces no further events at all until
#: the eventual `END`. **A *smaller* value here risks ending a sighting
#: while the unit is still genuinely shooting at the player, mid-attack --
#: the one failure mode this feature exists to prevent.** A *larger* value
#: only risks showing a unit as firing for longer after a dropped `END`
#: that was never going to be followed by a `DEAD`/`CRASH` either, which is
#: doubly rare (lost event + unit survives). Set generously above any
#: plausible single continuous engagement, since the downside of
#: overshooting is small and the downside of undershooting is a false "not
#: firing anymore" read on a unit still shooting at the aircraft. Whether
#: `S_EVENT_SHOOTING_START` retriggers mid-burst is still unconfirmed and
#: needs a live answer (plan's Risks & Unknowns) before this value's true
#: safe floor is known; until then this stays a conservative guess rather
#: than a measured bound. Same no-tuning-mechanism-yet note as
#: `FIRING_MIN_VISIBLE_S` above.
FIRING_WATCHDOG_S: Final[float] = 180.0

#: **Behaviour-affecting -- how long a missile/rocket launch (`S_EVENT_
#: SHOT`) stays a `LAUNCH_FLASH` light source after the event, "a few
#: seconds" per the user** (`explore-notes.md`: "the plume is there for a
#: few seconds"). A *smaller* value here risks the flash disappearing
#: before even one body-layer poll samples it at the 1 Hz Hook cadence;
#: a *larger* value keeps a launch visible as a light source longer than
#: a real launch flash/plume actually burns. Default 4.0 s is the user's
#: own rough figure; no measurement exists yet (plan's own "Risks &
#: Unknowns"), so this stays a first-cut guess narrowed by the test
#: card, same posture `FIRING_MIN_VISIBLE_S`/`FIRING_WATCHDOG_S` above
#: already take. Same no-tuning-mechanism-yet note as those two.
LAUNCH_FLASH_DURATION_S: Final[float] = 4.0

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

#: `[[BL-B67]]` Stage 5 -- how long an `OwnWeaponLedger` entry survives
#: after its own `gone_t` is set (plan: "keeps entries 60s after
#: gone_t"). Generous past any plausible poll gap on the body-layer side
#: -- the consumer (`perception.own_weapons.OwnWeaponTracker`) only ever
#: needs the entry to still exist for the one or two polls immediately
#: after `gone_t`, to diff against its own last-seen snapshot and emit
#: `missile_gone`; this is slack for a missed poll, not a feature. Same
#: no-tuning-mechanism-yet posture as every other behaviour-affecting
#: constant in this module (see `FIRING_MIN_VISIBLE_S`'s own note).
OWN_WEAPON_RETENTION_S: Final[float] = 60.0

#: `[[BL-B67]]` Stage 5 -- the ledger's own cap (plan: "caps at 32"), well
#: above "the run never has more than one in flight" (the Hook-side
#: `PB_OWN_WEAPONS` cap is 8) -- this side's own entries additionally
#: linger for `OWN_WEAPON_RETENTION_S` after `gone_t`, so a busy sortie
#: with several runs across the retention window needs headroom beyond
#: the Hook's own in-flight cap. The oldest entry (by `shot_t`) is dropped
#: when a new one would exceed this.
OWN_WEAPON_LEDGER_CAP: Final[int] = 32


class OwnWeaponEntry:
    """One of our own weapons, as the ledger currently believes it
    (`[[BL-B67]]` Stage 5 plan: "`{type, category, guidance, exists_at_
    shot, shot_t, gone_t | None}`") -- mutable, updated in place for the
    same reason `ActiveEmitter` above is."""

    __slots__ = (
        "category",
        "exists_at_shot",
        "gone_t",
        "guidance",
        "shot_t",
        "type_name",
    )

    def __init__(
        self,
        type_name: str | None,
        category: int | None,
        guidance: int | None,
        exists_at_shot: bool | None,
        shot_t: float,
        gone_t: float | None = None,
    ) -> None:
        self.type_name = type_name
        self.category = category
        self.guidance = guidance
        self.exists_at_shot = exists_at_shot
        self.shot_t = shot_t
        self.gone_t = gone_t

    def to_dict(self) -> dict[str, object]:
        return {
            "type_name": self.type_name,
            "category": self.category,
            "guidance": self.guidance,
            "exists_at_shot": self.exists_at_shot,
            "shot_t": self.shot_t,
            "gone_t": self.gone_t,
        }


class OwnWeaponLedger:
    """A small, `seq`-keyed ledger of our own weapons (`[[BL-B67]]` Stage
    5 plan: "a small `OwnWeaponLedger` beside `EmitterTracker`, fed the
    same batches"). Composed directly into `EmitterTracker` (below) --
    `ingest()` is called from the same `EmitterTracker.ingest()` call
    that feeds the firing-emitter latch, and `snapshot()` feeds `GET
    /firing/latest`'s own `"own_weapons"` key, mirroring `EmitterTracker`
    itself in every structural respect (a plain `dict`, no lock, "dict
    mutation/iteration under the GIL is effectively atomic enough").

    **Mission-restart reset is the caller's job, not this class's own.**
    `EmitterTracker.ingest` already detects `dcs_model_time_s` regression
    before calling into this ledger -- `clear()` is called from there,
    the same single place every other state in this module resets on a
    mission boundary, rather than this class re-deriving the same check
    independently."""

    def __init__(self) -> None:
        self._entries: dict[int, OwnWeaponEntry] = {}

    def clear(self) -> None:
        self._entries.clear()

    def ingest(self, own_events: tuple[OwnWeaponRawEvent, ...], now: float) -> None:
        """Apply this poll's own-weapon entries, in order, then prune
        every entry whose `gone_t` is more than `OWN_WEAPON_RETENTION_S`
        old, and enforce `OWN_WEAPON_LEDGER_CAP` (plan: "caps at 32")."""
        for event in own_events:
            if event.kind == "OWN_SHOT":
                self._entries[event.seq] = OwnWeaponEntry(
                    type_name=event.type_name,
                    category=event.category,
                    guidance=event.guidance,
                    exists_at_shot=event.exists_at_shot,
                    shot_t=event.t_sim,
                )
            elif event.kind == "OWN_GONE":
                existing = self._entries.get(event.seq)
                if existing is not None:
                    existing.gone_t = event.t_sim

        for seq in [
            seq
            for seq, entry in self._entries.items()
            if entry.gone_t is not None and now - entry.gone_t > OWN_WEAPON_RETENTION_S
        ]:
            del self._entries[seq]

        while len(self._entries) > OWN_WEAPON_LEDGER_CAP:
            oldest_seq = min(self._entries, key=lambda seq: self._entries[seq].shot_t)
            del self._entries[oldest_seq]

    def snapshot(self) -> dict[str, object]:
        """A plain, JSON-ready dict, `{str(seq): entry.to_dict()}` --
        `GET /firing/latest`'s own `"own_weapons"` key."""
        return {str(seq): entry.to_dict() for seq, entry in self._entries.items()}


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
    GIL is treated as "effectively atomic enough" for this codebase;
    no lock is taken."""

    def __init__(self) -> None:
        self._active: dict[str, ActiveEmitter] = {}
        self._last_dcs_model_time_s: float | None = None
        #: The most recent poll's own `MissionClockSample`, or `None` --
        #: either no batch has arrived yet, or the most recent batch's own
        #: read failed/was absent (`BL-B124`). Overwritten every `ingest()`
        #: call with exactly what that batch reported -- this tracker does
        #: not try to paper over a transient miss by holding onto a stale
        #: reading; a consumer that wants "last known good" behaviour
        #: builds that on its own side (deferred to Stage 4, out of this
        #: stage's scope).
        self._last_mission_clock: MissionClockSample | None = None
        #: `[[BL-B67]]` Stage 5 -- composed directly into this tracker
        #: (`OwnWeaponLedger`'s own docstring on why), fed the same
        #: batches and cleared on the same mission-restart detection this
        #: `ingest()` already does for `self._active`.
        self._own_weapons = OwnWeaponLedger()

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
            self._own_weapons.clear()
        self._last_dcs_model_time_s = now
        self._last_mission_clock = batch.mission_clock

        for event in batch.events:
            self._apply(event, now)
        self._own_weapons.ingest(batch.own_events, now)

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
            # starts creating them. `LAUNCH_FLASH` is removed alongside
            # `FIRING` -- a dead unit is not a light source any more than
            # it is still firing.
            if existing is not None and existing.kind in (
                EMITTER_KIND_FIRING,
                EMITTER_KIND_LAUNCH_FLASH,
            ):
                del self._active[event.initiator]
        elif event.kind == "S_EVENT_SHOT":
            # `[[BL-B124]]` Stage 5 -- a missile/rocket launch, a few-
            # second `LAUNCH_FLASH` light source at the launcher's own
            # name (the initiator of the shot, same join key `FIRING`
            # uses). **Does not overwrite an existing `FIRING` entry** --
            # a unit already tracked as gun-firing (its own watchdog is
            # already the longer-lived, more informative state for
            # visibility purposes) stays `FIRING`; only a unit with no
            # active entry, or one already `LAUNCH_FLASH`, gets this
            # entry (re)started. `[[BL-B74]]`'s `LAUNCH_SMOKE` seam is
            # untouched -- a different, longer-lived kind this stage does
            # not build.
            existing = self._active.get(event.initiator)
            if existing is None or existing.kind == EMITTER_KIND_LAUNCH_FLASH:
                self._active[event.initiator] = ActiveEmitter(
                    kind=EMITTER_KIND_LAUNCH_FLASH,
                    since_sim=event.t_sim,
                    expires_at_sim=now + LAUNCH_FLASH_DURATION_S,
                    targets_ownship=False,
                )

    def snapshot(self) -> dict[str, object]:
        """A plain, JSON-ready dict -- `GET /firing/latest`'s body
        (`api.server._handle_firing_latest`), mirroring every other
        `*Snapshot.to_dict()` shape in this module even though this one is
        computed on demand rather than stored. `None` entries never
        appear in `active`: it only ever holds units this tracker
        currently believes are emitting. `mission_clock` (`BL-B124`) is
        `None` whenever the most recent batch's own read was absent or
        failed -- the same "not an error, just unavailable this poll"
        posture every other optional sub-wire field in this codebase
        takes."""
        return {
            "dcs_model_time_s": self._last_dcs_model_time_s,
            "received_wall_clock_s": time.time(),
            "active": {
                name: emitter.to_dict() for name, emitter in self._active.items()
            },
            "mission_clock": (
                self._last_mission_clock.to_dict()
                if self._last_mission_clock is not None
                else None
            ),
            "own_weapons": self._own_weapons.snapshot(),
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

        mission_clock_raw = envelope.get("mission_clock")
        if not isinstance(mission_clock_raw, str):
            mission_clock_raw = None

        try:
            batch = FiringEventBatch.from_wire(
                payload,
                bridge_call_ms=float(bridge_call_ms),
                received_wall_clock_s=time.time(),
                mission_clock_raw=mission_clock_raw,
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
