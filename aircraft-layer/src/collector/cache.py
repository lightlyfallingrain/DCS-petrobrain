"""Most-recent-state caches.

Pure in-memory bookkeeping, no I/O. `TelemetryCache` is fed by
`server.CollectorServer` (or, in tests, directly) and is what the
Mac-facing API (`GET /telemetry/latest`, `api.server`) reads from.
`WorldObjectsCache` (`plans/pb1-perception-logger/plan.md` stage 3) is its
`GET /world_objects/latest` sibling, fed from the same connection.
`PetrovichIndicationCache` (that plan's stage 4) is the same shape again,
for `GET /petrovich_indication/latest`. `PetrovichWheelCache` (BL-6, `plans/
bl6-commands-inspect-adapt/plan.md`) is the same shape once more, for
`GET /petrovich_wheel/latest`.

Originally also held a ring buffer for a `GET /telemetry/since/{timestamp}`
delta-query endpoint (plan decision 4), dropped after stage 5's live pause
test: `since()` filtered on receipt time, not content, so it returned every
paused-and-motionless sample as "new" -- not useful, and the body/brain
consumer polling model doesn't need gap-free history anyway (it can just
poll `/latest` as often as it needs). See `plans/aircraft-layer/plan.md`.

`F10CommandQueue` (`plans/f10-crew-commands/plan.md`) is a different shape
from every cache above: a **bounded FIFO event queue**, not a single-slot
"latest" cache. Two F10 selections landing inside one body-layer poll
interval must both survive -- a "latest" slot would silently collapse them
into one, a real behavioral loss for discrete commands (e.g. two different
menu picks) in a way it isn't for continuously-refreshed telemetry. Fed by
`collector.f10_command_receiver.F10CommandReceiver`; drained by
`GET /f10_commands/poll` (`api.server`), which -- unlike every `/latest`
endpoint -- mutates this queue's state on every call (drain-on-GET,
at-most-once delivery; see that endpoint's own docstring).

`Spu8Cache` (`plans/spu8-intercom/plan.md` Stage 1) is the same "latest of
one" shape as `PttCache`, for the SPU-8 intercom panel (pilot NET-1,
co-pilot ICS power, volume). Unlike every cache above, it also exposes
`gate_state()` -- a derived `Spu8GateState(gate_open, volume)` that
`collector.audio_sender.AudioPlaybackSender`'s real wiring consults once
per queued item, fail-safe-closed when no sample has arrived yet.
"""

from __future__ import annotations

from collections import deque
from typing import NamedTuple

from schema import (
    F10CommandEvent,
    PetrovichIndicationSample,
    PetrovichWheelSample,
    PttSample,
    Spu8Sample,
    TelemetrySample,
    UnitVelocitySnapshot,
    WorldObjectsSnapshot,
)

#: Bounded so a pathological flood of F10 selections (or a stuck poller)
#: cannot grow this queue unboundedly -- generous relative to any plausible
#: player selection rate (three menu items, hand-operated).
_MAX_QUEUE_LEN = 64


class TelemetryCache:
    """Holds the latest telemetry sample."""

    def __init__(self) -> None:
        self._latest: TelemetrySample | None = None

    def push(self, sample: TelemetrySample) -> None:
        """Record a newly-received sample as the current latest state."""
        self._latest = sample

    def latest(self) -> TelemetrySample | None:
        """Return the most recently pushed sample, or `None` if empty."""
        return self._latest


class WorldObjectsCache:
    """Holds the latest `LoGetWorldObjects` snapshot. Same shape as
    `TelemetryCache`, kept as a separate class rather than a generalized
    "latest of anything" cache -- `collector.server.CollectorServer` routes
    each incoming line to exactly one of the two by its JSON shape, and two
    small concrete classes are clearer at the call site than one generic one
    with a type parameter."""

    def __init__(self) -> None:
        self._latest: WorldObjectsSnapshot | None = None

    def push(self, snapshot: WorldObjectsSnapshot) -> None:
        """Record a newly-received snapshot as the current latest state."""
        self._latest = snapshot

    def latest(self) -> WorldObjectsSnapshot | None:
        """Return the most recently pushed snapshot, or `None` if empty."""
        return self._latest


class PetrovichIndicationCache:
    """Holds the latest `list_indication(HELPERAI_DEVICE_ID)` sample. Same
    shape as `TelemetryCache`/`WorldObjectsCache`, kept as its own small
    concrete class for the same reason `WorldObjectsCache` is -- one class
    per feed is clearer at the `collector.server` routing call site than a
    generic "latest of anything" cache."""

    def __init__(self) -> None:
        self._latest: PetrovichIndicationSample | None = None

    def push(self, sample: PetrovichIndicationSample) -> None:
        """Record a newly-received sample as the current latest state."""
        self._latest = sample

    def latest(self) -> PetrovichIndicationSample | None:
        """Return the most recently pushed sample, or `None` if empty."""
        return self._latest


class PetrovichWheelCache:
    """Holds the latest `list_indication(10)` (AI-Wheel) sample -- BL-6.
    Same shape as `PetrovichIndicationCache`, kept as its own small concrete
    class for the same reason that one is -- one class per feed is clearer
    at the `collector.server` routing call site than a generic "latest of
    anything" cache."""

    def __init__(self) -> None:
        self._latest: PetrovichWheelSample | None = None

    def push(self, sample: PetrovichWheelSample) -> None:
        """Record a newly-received sample as the current latest state."""
        self._latest = sample

    def latest(self) -> PetrovichWheelSample | None:
        """Return the most recently pushed sample, or `None` if empty."""
        return self._latest


class PttCache:
    """Holds the latest reading of the pilot's push-to-talk trigger
    (`plans/inbound-speech/plan.md` Stage 5).

    Latest-of-one, like every cache above, and the fit is closer here than
    anywhere else: the trigger is a *state*, not an event stream, and
    `Export.lua` sends a line only when it changes. A queue would hold a
    history nobody wants -- the one question a consumer ever asks is "is it
    down right now".
    """

    def __init__(self) -> None:
        self._latest: PttSample | None = None

    def push(self, sample: PttSample) -> None:
        """Record a newly-received sample as the current trigger state."""
        self._latest = sample

    def latest(self) -> PttSample | None:
        """Return the most recently pushed sample, or `None` if the trigger
        has not moved since the collector started -- the normal state at
        startup rather than an error: a trigger nobody has touched produces
        no lines at all."""
        return self._latest


class Spu8GateState(NamedTuple):
    """Snapshot `collector.audio_sender.AudioPlaybackSender` consults once
    per queued item, immediately before playback -- see that module's own
    docstring for why this is the single point gating/volume are checked.
    `Spu8Cache.gate_state()` is the only place this is constructed; kept
    here (not in `audio_sender.py`) since the cache is what actually knows
    the current SPU-8 state and `audio_sender.py` only consumes it."""

    gate_open: bool
    volume: float


class Spu8Cache:
    """Holds the latest SPU-8 intercom-panel sample (`plans/spu8-intercom/
    plan.md` Stage 1) -- pilot NET-1 (arg 377), co-pilot ICS power (arg
    664), and SPU-8 volume (arg 457). Same "latest of one" shape/reasoning
    as `PttCache`: `Export.lua` sends a line only on change, and the one
    question a consumer asks is "is the channel open right now, and how
    loud" -- not a history of switch flips.
    """

    def __init__(self) -> None:
        self._latest: Spu8Sample | None = None

    def push(self, sample: Spu8Sample) -> None:
        """Record a newly-received sample as the current panel state."""
        self._latest = sample

    def latest(self) -> Spu8Sample | None:
        """Return the most recently pushed sample, or `None` if no SPU-8
        line has arrived yet this session (the normal state at startup,
        same as `PttCache.latest`)."""
        return self._latest

    def gate_state(self) -> Spu8GateState:
        """`AudioPlaybackSender`'s real wiring (`__main__.py`) passes this
        method, unbound, as its `gate_state` provider.

        **Fail-safe-closed when no SPU-8 sample has arrived yet** (plan
        Decision 3) -- an unknown intercom state should not let anything
        through, in either direction. This is the production-path default;
        it differs deliberately from `AudioPlaybackSender`'s own
        constructor default (always-open), which exists only for call
        sites/tests that predate this feature and never wire a provider."""
        sample = self._latest
        if sample is None:
            return Spu8GateState(gate_open=False, volume=1.0)
        return Spu8GateState(gate_open=sample.gate_open, volume=sample.vol)


class UnitVelocityCache:
    """Holds the latest `UnitVelocitySnapshot` (`plans/movement-detection/
    plan.md` Stage 1). Same "latest of one" shape as `WorldObjectsCache`,
    kept as its own small concrete class for the same reason that one is --
    one class per feed is clearer at `unit_velocity_receiver`'s (and, unlike
    every cache above, the receiver's own, not `collector.server`'s) call
    site than a generic "latest of anything" cache."""

    def __init__(self) -> None:
        self._latest: UnitVelocitySnapshot | None = None

    def push(self, snapshot: UnitVelocitySnapshot) -> None:
        """Record a newly-received snapshot as the current latest state."""
        self._latest = snapshot

    def latest(self) -> UnitVelocitySnapshot | None:
        """Return the most recently pushed snapshot, or `None` if empty."""
        return self._latest


class F10CommandQueue:
    """Holds pending F10 radio-menu command selections
    (`plans/f10-crew-commands/plan.md`) -- a bounded FIFO, not a
    single-slot "latest" cache (see this module's own docstring for why).
    `push`/`drain_all`, not `push`/`latest` -- the first event-queue cache
    in this module, not a latest-value one."""

    def __init__(self, maxlen: int = _MAX_QUEUE_LEN) -> None:
        self._queue: deque[F10CommandEvent] = deque(maxlen=maxlen)

    def push(self, event: F10CommandEvent) -> None:
        """Enqueue one newly-received F10 command event. If the queue is
        already at `maxlen`, the oldest pending event is silently dropped
        (deque's own overflow behavior) -- an accepted, at-most-once-class
        loss under this module's docstring, and only reachable at a
        pathological selection rate."""
        self._queue.append(event)

    def drain_all(self) -> list[F10CommandEvent]:
        """Remove and return every currently-queued event, oldest first.
        Uses repeated `popleft()` rather than a snapshot-then-clear so a
        `push` racing this call (from the receiver's own thread) is never
        silently dropped by a clear() that fires after the snapshot was
        taken -- each `popleft()` is itself atomic under the GIL."""
        drained: list[F10CommandEvent] = []
        while True:
            try:
                drained.append(self._queue.popleft())
            except IndexError:
                return drained
