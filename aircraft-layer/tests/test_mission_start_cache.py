"""Tests for `collector.cache.MissionStartCache` -- `plans/
bl15-mission-start/plan.md` (BL-15 Stage 1). Mirrors
`test_unit_velocity_cache.py`'s pattern (single-slot "latest" cache)."""

from __future__ import annotations

from collector.cache import MissionStartCache
from schema import MissionStartEvent


def _event(sequence: int, theatre: str | None = "Syria") -> MissionStartEvent:
    return MissionStartEvent(
        sequence=sequence, theatre=theatre, received_wall_clock_s=1000.0
    )


def test_empty_cache_returns_none() -> None:
    assert MissionStartCache().latest() is None


def test_push_then_latest_returns_pushed_event() -> None:
    cache = MissionStartCache()
    event = _event(1)
    cache.push(event)
    assert cache.latest() is event


def test_latest_push_wins() -> None:
    cache = MissionStartCache()
    cache.push(_event(1))
    second = _event(2)
    cache.push(second)
    assert cache.latest() is second
