"""Tests for `collector.cache.TelemetryCache` (delta-since-last-query logic)."""

from __future__ import annotations

import pytest

from collector.cache import TelemetryCache
from schema import TelemetrySample


def make_sample(model_time: float, wall_clock: float) -> TelemetrySample:
    return TelemetrySample(
        dcs_model_time_s=model_time,
        received_wall_clock_s=wall_clock,
        position_x_m=0.0,
        position_y_m=0.0,
        position_z_m=0.0,
        pitch_rad=0.0,
        bank_rad=0.0,
        yaw_rad=0.0,
        heading_true_rad=0.0,
        ias_mps=0.0,
        tas_mps=0.0,
        altitude_msl_m=0.0,
        altitude_agl_m=0.0,
        altitude_radar_m=None,
    )


def test_latest_returns_none_when_empty() -> None:
    cache = TelemetryCache()

    assert cache.latest() is None


def test_latest_returns_most_recently_pushed_sample() -> None:
    cache = TelemetryCache()
    cache.push(make_sample(1.0, 100.0))
    cache.push(make_sample(2.0, 100.2))

    latest = cache.latest()

    assert latest is not None
    assert latest.dcs_model_time_s == 2.0


def test_since_returns_only_samples_after_cursor() -> None:
    cache = TelemetryCache()
    cache.push(make_sample(1.0, 100.0))
    cache.push(make_sample(2.0, 100.2))
    cache.push(make_sample(3.0, 100.4))

    result = cache.since(100.2)

    assert [s.dcs_model_time_s for s in result] == [3.0]


def test_since_with_cursor_before_all_samples_returns_everything() -> None:
    cache = TelemetryCache()
    cache.push(make_sample(1.0, 100.0))
    cache.push(make_sample(2.0, 100.2))

    result = cache.since(0.0)

    assert [s.dcs_model_time_s for s in result] == [1.0, 2.0]


def test_since_with_cursor_at_or_after_latest_returns_empty_nothing_changed() -> None:
    cache = TelemetryCache()
    cache.push(make_sample(1.0, 100.0))
    cache.push(make_sample(2.0, 100.2))

    result = cache.since(100.2)

    assert result == []


def test_since_preserves_chronological_order() -> None:
    cache = TelemetryCache()
    for i in range(5):
        cache.push(make_sample(float(i), 100.0 + i * 0.2))

    result = cache.since(0.0)

    assert [s.dcs_model_time_s for s in result] == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_ring_buffer_evicts_oldest_beyond_buffer_size() -> None:
    cache = TelemetryCache(buffer_size=3)
    for i in range(5):
        cache.push(make_sample(float(i), 100.0 + i))

    result = cache.since(0.0)

    # Only the last 3 pushed samples survive eviction.
    assert [s.dcs_model_time_s for s in result] == [2.0, 3.0, 4.0]
    assert len(cache) == 3


def test_buffer_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="buffer_size"):
        TelemetryCache(buffer_size=0)
