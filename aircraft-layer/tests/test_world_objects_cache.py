"""Tests for `collector.cache.WorldObjectsCache`."""

from __future__ import annotations

from collector.cache import WorldObjectsCache
from schema import WorldObjectsSnapshot


def make_snapshot(model_time: float, wall_clock: float) -> WorldObjectsSnapshot:
    return WorldObjectsSnapshot(
        dcs_model_time_s=model_time,
        received_wall_clock_s=wall_clock,
        objects=(),
    )


def test_latest_returns_none_when_empty() -> None:
    cache = WorldObjectsCache()

    assert cache.latest() is None


def test_latest_returns_most_recently_pushed_snapshot() -> None:
    cache = WorldObjectsCache()
    cache.push(make_snapshot(1.0, 100.0))
    cache.push(make_snapshot(2.0, 100.2))

    latest = cache.latest()

    assert latest is not None
    assert latest.dcs_model_time_s == 2.0
