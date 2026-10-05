"""Tests for `collector.cache.LineOfSightCache` -- `plans/dcs-driven-los/
plan.md` (X-B29). Mirrors `test_unit_velocity_cache.py`'s pattern
(single-slot "latest" cache)."""

from __future__ import annotations

from collector.cache import LineOfSightCache
from schema.line_of_sight import LineOfSightSnapshot


def _snapshot(t: float) -> LineOfSightSnapshot:
    return LineOfSightSnapshot.from_wire(
        f"1|1|1|0|45|{t}|Truck-1:1:1",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
    )


def test_empty_cache_returns_none() -> None:
    assert LineOfSightCache().latest() is None


def test_push_then_latest_returns_pushed_snapshot() -> None:
    cache = LineOfSightCache()
    snapshot = _snapshot(1.0)
    cache.push(snapshot)
    assert cache.latest() is snapshot


def test_latest_push_wins() -> None:
    cache = LineOfSightCache()
    cache.push(_snapshot(1.0))
    second = _snapshot(2.0)
    cache.push(second)
    assert cache.latest() is second
