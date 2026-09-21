"""Tests for `collector.cache.UnitVelocityCache` -- `plans/
movement-detection/plan.md` Stage 1. Mirrors `test_world_objects_cache.py`'s
pattern (single-slot "latest" cache)."""

from __future__ import annotations

from collector.cache import UnitVelocityCache
from schema.unit_velocity import UnitVelocitySnapshot


def _snapshot(t: float) -> UnitVelocitySnapshot:
    return UnitVelocitySnapshot.from_wire(
        f"1|{t}|Truck-1:1.0:0.0:0.0", bridge_call_ms=0.5, received_wall_clock_s=1000.0
    )


def test_empty_cache_returns_none() -> None:
    assert UnitVelocityCache().latest() is None


def test_push_then_latest_returns_pushed_snapshot() -> None:
    cache = UnitVelocityCache()
    snapshot = _snapshot(1.0)
    cache.push(snapshot)
    assert cache.latest() is snapshot


def test_latest_push_wins() -> None:
    cache = UnitVelocityCache()
    cache.push(_snapshot(1.0))
    second = _snapshot(2.0)
    cache.push(second)
    assert cache.latest() is second
