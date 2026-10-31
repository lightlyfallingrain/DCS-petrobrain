"""Shared, time-throttled progress reporting for world-model build
operations.

**Why this exists**: a long build stage that logs nothing for minutes is
indistinguishable from a hang. This has come up three times against real
`syria-full` runs (Stage 5 road-junction detection, then Stage 3 OSM
overlay twice -- see `plans/osm-landcover-optimization/progress-logging.md`
for the audit and root-cause behind this module) with a different ad hoc
fix each time. This module is the one mechanism every stage should use
instead, so the fix generalizes rather than recurring per-stage. See
`world-model/CLAUDE.md`'s "Progress reporting" convention.

Two entry points, for the two shapes a long operation can take:

- `ThrottledProgress`: for work that returns control to Python regularly (a
  `for` loop over rows/chunks/batches -- SRTM grid rows, junction-detection
  chunks, `.routes` route boundaries, OSM-cache read batches). Call
  `.maybe_log(...)` once per iteration; it only actually logs once
  `interval_s` has elapsed since the last line, so a fast loop costs one
  throttle check per iteration and a slow one still gets a heartbeat.
  Time-based, not count-based -- per-item cost varies (an empty desert
  chunk vs. a dense city chunk, a filtered-out node vs. a kept one), so a
  fixed every-N-items interval logs in bursts and then goes silent for
  minutes -- exactly the failure mode this module exists to prevent.

- `Heartbeat`: for work that runs inside a single call with **no** Python
  callback at all for extended stretches (pyosmium's `apply_file` under a
  `KeyFilter` plus its C++ two-pass area assembly -- see `osm.pbf`).
  Confirmed safe by measurement, not assumed: pyosmium 4.3.1's `apply_file`
  releases the GIL periodically on its own, even across stretches with zero
  Python callbacks (a background thread ticked every ~1.0s throughout a
  10.3s `apply_file` call where most elements were filtered out before ever
  reaching a callback -- see the progress-logging plan's "GIL release"
  finding). Wrap the call in `with Heartbeat(report_fn):`; a background
  daemon thread calls `report_fn()` every `interval_s` seconds until the
  block exits, regardless of what the main thread is doing at that moment
  (parsing, or a nested Python callback's own DB writes) -- so it gives a
  heartbeat across the *whole* call, not just the parts that call back into
  Python.

Both default to `DEFAULT_INTERVAL_S` (30s): "at most every 30s, at least
every ~30s while work continues" is this project's standing convention, not
a per-module judgment call.

**Estimates are fine, labelled**: exact done/total counts aren't always
available (`Heartbeat`'s whole reason to exist is a stretch with no exact
progress signal). `maybe_log`/`log`'s `estimated=True` marks `done`/`total`/
the percentage with a leading `~` rather than omitting them -- a rough ETA
(e.g. elapsed time against a file-size-calibrated expected duration) is more
useful than no ETA at all, as long as it is clearly not exact.
"""

import logging
import threading
import time
from collections.abc import Callable
from typing import Self

DEFAULT_INTERVAL_S = 30.0


def _format_count(value: float) -> str:
    """Format a `done`/`total` value without ever flipping to scientific
    notation -- Python's `f'{v:g}'` does that above ~1e6, which real
    theatre-scale counts (millions of OSM elements, hundreds of thousands
    of grid cells) routinely exceed."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def format_progress(
    operation: str,
    elapsed_s: float,
    done: float | None = None,
    total: float | None = None,
    estimated: bool = False,
    **counters: object,
) -> str:
    """Build one progress line: `<operation>: <done>/<total or ?> (<pct if
    total known>, <key=value counters>, <elapsed>s elapsed[, ~<remaining>s
    remaining])`.

    `estimated=True` marks `done`/`total`/the percentage with a leading `~`
    -- see the module docstring's "Estimates are fine, labelled". The
    `remaining` figure, when shown, is always `~`-prefixed regardless of
    `estimated`, since any linear extrapolation from a partial rate is
    inherently rough.
    """
    mark = "~" if estimated else ""
    done_repr = f"{mark}{_format_count(done)}" if done is not None else "?"
    total_repr = _format_count(total) if total is not None else "?"

    inner: list[str] = []
    if done is not None and total:
        pct = 100.0 * done / total
        inner.append(f"{mark}{pct:.1f}%")
    for key, value in counters.items():
        inner.append(f"{key}={value}")
    inner.append(f"{elapsed_s:.0f}s elapsed")
    if done is not None and total is not None and 0 < done < total:
        remaining_s = elapsed_s / done * (total - done)
        inner.append(f"~{remaining_s:.0f}s remaining")

    return f"{operation}: {done_repr}/{total_repr} ({', '.join(inner)})"


class ThrottledProgress:
    """Logs at most once every `interval_s` seconds. Construct once per
    operation (starts its own elapsed-time clock immediately), then call
    `.maybe_log(...)` from inside the loop being monitored -- cheap to call
    every iteration; it is a no-op except when the interval has elapsed.

    `clock` is injectable so tests can advance time deterministically
    instead of depending on real wall-clock sleeps (see `tests/
    test_progress.py`).
    """

    def __init__(
        self,
        target_logger: logging.Logger,
        operation: str,
        total: float | None = None,
        interval_s: float = DEFAULT_INTERVAL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._logger = target_logger
        self._operation = operation
        self._total = total
        self._interval_s = interval_s
        self._clock = clock
        self._started_at = clock()
        self._last_logged_at: float | None = None

    def maybe_log(
        self,
        done: float | None = None,
        *,
        estimated: bool = False,
        **counters: object,
    ) -> bool:
        """Log a throttled progress line if `interval_s` has elapsed since
        the last one (or since construction, for the first call). Returns
        whether it logged."""
        now = self._clock()
        if (
            self._last_logged_at is not None
            and now - self._last_logged_at < self._interval_s
        ):
            return False
        self._emit(now, done, estimated, counters)
        return True

    def log(
        self,
        done: float | None = None,
        *,
        estimated: bool = False,
        **counters: object,
    ) -> None:
        """Log immediately, bypassing the throttle -- for an up-front "N
        items to process" line or a final summary -- and reset the throttle
        window so a `maybe_log` right after this doesn't immediately fire
        again."""
        self._emit(self._clock(), done, estimated, counters)

    def _emit(
        self,
        now: float,
        done: float | None,
        estimated: bool,
        counters: dict[str, object],
    ) -> None:
        self._last_logged_at = now
        self._logger.info(
            format_progress(
                self._operation,
                now - self._started_at,
                done,
                self._total,
                estimated,
                **counters,
            )
        )


class Heartbeat:
    """Background daemon thread that calls `report_fn()` every `interval_s`
    seconds, from `__enter__` until `__exit__` -- for a single call with no
    Python callback to hook progress reporting into (see the module
    docstring's `apply_file` case).

    `report_fn` must be cheap and safe to call from a non-main thread while
    the wrapped call is still running -- typically reading a few shared
    counters (plain attribute reads under the GIL are safe without a lock;
    the worst case is observing a slightly stale value, never a torn one)
    and calling `ThrottledProgress.log`.

    A context manager rather than a bare start/stop pair so the thread is
    always stopped and joined on the way out, including when the wrapped
    call raises.
    """

    def __init__(
        self,
        report_fn: Callable[[], None],
        interval_s: float = DEFAULT_INTERVAL_S,
    ) -> None:
        self._report_fn = report_fn
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(self._interval_s):
            self._report_fn()

    def __enter__(self) -> "Self":
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._stop.set()
        self._thread.join(timeout=self._interval_s + 5.0)
