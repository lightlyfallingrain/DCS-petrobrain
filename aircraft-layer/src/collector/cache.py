"""Most-recent-state cache and delta-since-last-query ring buffer.

Pure in-memory bookkeeping, no I/O. `TelemetryCache` is fed by
`server.CollectorServer` (or, in tests, directly) and is what a later
Mac-facing API (`GET /telemetry/latest`, `GET /telemetry/since/{timestamp}`)
will read from — that API is out of scope for this stage, but the cache/
schema boundary it depends on is designed here per the plan.
"""

from __future__ import annotations

from collections import deque

from schema import TelemetrySample

#: Default ring-buffer depth. At the plan's 5 Hz export rate this holds
#: roughly the last 20 seconds of samples -- comfortably more than one poll
#: interval for the crew-cognition-rate consumers this is built for.
DEFAULT_BUFFER_SIZE = 100


class TelemetryCache:
    """Holds the latest telemetry sample plus a bounded history."""

    def __init__(self, buffer_size: int = DEFAULT_BUFFER_SIZE) -> None:
        if buffer_size < 1:
            raise ValueError("buffer_size must be at least 1")
        self._buffer: deque[TelemetrySample] = deque(maxlen=buffer_size)

    def push(self, sample: TelemetrySample) -> None:
        """Record a newly-received sample as the current latest state.

        Samples are expected to arrive in non-decreasing
        `received_wall_clock_s` order (the collector assigns that timestamp
        at receipt time, so this holds as long as a single collector process
        feeds the cache). Out-of-order pushes are still stored, but
        `since()`'s ordering guarantee only holds for in-order input.
        """
        self._buffer.append(sample)

    def latest(self) -> TelemetrySample | None:
        """Return the most recently pushed sample, or `None` if empty."""
        if not self._buffer:
            return None
        return self._buffer[-1]

    def since(self, cursor_wall_clock_s: float) -> list[TelemetrySample]:
        """Return samples received strictly after `cursor_wall_clock_s`.

        Returned in chronological (receipt) order. An empty list is the
        expected, normal result of "nothing changed since your last poll" --
        callers should not treat it as an error.

        Note: if `cursor_wall_clock_s` predates the oldest sample still held
        in the ring buffer, samples between the cursor and the buffer's
        oldest retained entry have already been evicted and are silently
        not returned. Callers polling at a reasonable interval relative to
        `buffer_size` / export rate won't hit this; a caller that goes
        quiet for longer than the buffer's retained window will observe a
        gap rather than an error.
        """
        return [
            s for s in self._buffer if s.received_wall_clock_s > cursor_wall_clock_s
        ]

    def __len__(self) -> int:
        return len(self._buffer)
