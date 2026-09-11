"""Tests for `collector.cache.PetrovichWheelCache` -- BL-6."""

from __future__ import annotations

from collector.cache import PetrovichWheelCache
from schema import PetrovichWheelSample


def make_sample(model_time: float, wall_clock: float) -> PetrovichWheelSample:
    return PetrovichWheelSample(
        dcs_model_time_s=model_time,
        received_wall_clock_s=wall_clock,
        fields={},
    )


def test_latest_returns_none_when_empty() -> None:
    cache = PetrovichWheelCache()

    assert cache.latest() is None


def test_latest_returns_most_recently_pushed_sample() -> None:
    cache = PetrovichWheelCache()
    cache.push(make_sample(1.0, 100.0))
    cache.push(make_sample(2.0, 100.2))

    latest = cache.latest()

    assert latest is not None
    assert latest.dcs_model_time_s == 2.0
