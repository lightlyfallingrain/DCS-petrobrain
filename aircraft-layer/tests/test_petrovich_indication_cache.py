"""Tests for `collector.cache.PetrovichIndicationCache`."""

from __future__ import annotations

from collector.cache import PetrovichIndicationCache
from schema import PetrovichIndicationSample


def make_sample(model_time: float, wall_clock: float) -> PetrovichIndicationSample:
    return PetrovichIndicationSample(
        dcs_model_time_s=model_time,
        received_wall_clock_s=wall_clock,
        fields={},
    )


def test_latest_returns_none_when_empty() -> None:
    cache = PetrovichIndicationCache()

    assert cache.latest() is None


def test_latest_returns_most_recently_pushed_sample() -> None:
    cache = PetrovichIndicationCache()
    cache.push(make_sample(1.0, 100.0))
    cache.push(make_sample(2.0, 100.2))

    latest = cache.latest()

    assert latest is not None
    assert latest.dcs_model_time_s == 2.0
