"""Tests for `collector.cache.TelemetryCache`."""

from __future__ import annotations

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
