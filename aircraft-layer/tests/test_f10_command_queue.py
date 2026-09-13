"""Tests for `collector.cache.F10CommandQueue` -- `plans/f10-crew-commands/
plan.md`. Mirrors `test_cache.py`'s style, for the one bounded-FIFO cache
in this module rather than the "latest value" caches that file covers."""

from __future__ import annotations

from collector.cache import F10CommandQueue
from schema import F10CommandEvent


def _event(command: str, wall_clock: float = 100.0) -> F10CommandEvent:
    return F10CommandEvent(command=command, received_wall_clock_s=wall_clock)


def test_drain_all_returns_empty_list_when_empty() -> None:
    queue = F10CommandQueue()

    assert queue.drain_all() == []


def test_drain_all_returns_events_oldest_first_and_empties_the_queue() -> None:
    queue = F10CommandQueue()
    queue.push(_event("watch_nearest", 1.0))
    queue.push(_event("scan_forward", 2.0))

    drained = queue.drain_all()

    assert [event.command for event in drained] == ["watch_nearest", "scan_forward"]
    assert queue.drain_all() == []


def test_queue_respects_maxlen_by_dropping_oldest() -> None:
    queue = F10CommandQueue(maxlen=2)
    queue.push(_event("watch_nearest", 1.0))
    queue.push(_event("scan_forward", 2.0))
    queue.push(_event("cancel_task", 3.0))

    drained = queue.drain_all()

    assert [event.command for event in drained] == ["scan_forward", "cancel_task"]
