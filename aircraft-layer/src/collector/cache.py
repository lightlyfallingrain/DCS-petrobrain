"""Most-recent-state caches.

Pure in-memory bookkeeping, no I/O. `TelemetryCache` is fed by
`server.CollectorServer` (or, in tests, directly) and is what the
Mac-facing API (`GET /telemetry/latest`, `api.server`) reads from.
`WorldObjectsCache` (`plans/pb1-perception-logger/plan.md` stage 3) is its
`GET /world_objects/latest` sibling, fed from the same connection.

Originally also held a ring buffer for a `GET /telemetry/since/{timestamp}`
delta-query endpoint (plan decision 4), dropped after stage 5's live pause
test: `since()` filtered on receipt time, not content, so it returned every
paused-and-motionless sample as "new" -- not useful, and the body/brain
consumer polling model doesn't need gap-free history anyway (it can just
poll `/latest` as often as it needs). See `plans/aircraft-layer/plan.md`.
"""

from __future__ import annotations

from schema import TelemetrySample, WorldObjectsSnapshot


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
