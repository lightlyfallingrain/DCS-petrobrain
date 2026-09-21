"""Tests for `perception.motion` -- `plans/movement-detection/plan.md`
Stage 2. Reproduces `body-layer/ROADMAP.md`'s 2026-09-20 sanity table
verbatim, plus the deliberate constant-bearing blind spot the design calls
out as a feature, not a bug -- pinned here so a later "fix" trips a test.
"""

from __future__ import annotations

import math

import pytest

from perception.geometry import GeoPosition
from perception.motion import (
    MOTION_ANGULAR_THRESHOLD_RAD_S,
    MOTION_VELOCITY_MAX_SKEW_S,
    Vec3,
    apparent_angular_rate_rad_s,
    evaluate_motion_gate,
    is_apparently_moving,
)

_OBSERVER = GeoPosition(x=0.0, z=0.0, alt_m=0.0)


def _crossing_target(range_m: float) -> GeoPosition:
    """A target due east of the observer -- so a velocity purely along the
    north-like x-axis is entirely perpendicular to the line of sight (pure
    crossing motion, exactly what the roadmap's sanity table assumes)."""
    return GeoPosition(x=0.0, z=range_m, alt_m=0.0)


def _crossing_velocity(speed_mps: float) -> Vec3:
    return Vec3(x=speed_mps, y=0.0, z=0.0)


# `body-layer/ROADMAP.md`'s 2026-09-20 sanity table, reproduced verbatim
# (plan Stage 2's explicit instruction) -- the middle row is the one that
# argues for the threshold: a slow truck at 5 km genuinely does not read as
# moving at a glance.
@pytest.mark.parametrize(
    "speed_mps,range_m,expected_moving",
    [
        (10.0, 2000.0, True),  # truck crossing at 2 km, ~17 arcmin/s
        (5.0, 5000.0, False),  # truck crossing at 5 km, ~3.4 arcmin/s
        (200.0, 5000.0, True),  # jet crossing at 5 km, ~137 arcmin/s
    ],
)
def test_roadmap_sanity_table(
    speed_mps: float, range_m: float, expected_moving: bool
) -> None:
    target = _crossing_target(range_m)
    velocity = _crossing_velocity(speed_mps)
    assert is_apparently_moving(_OBSERVER, target, velocity) is expected_moving


def test_constant_bearing_collision_course_reads_as_not_moving() -> None:
    """The design's deliberate blind spot (`body-layer/ROADMAP.md`
    2026-09-20): a unit closing directly along the line of sight has zero
    perpendicular velocity component, so it reads as "no movement"
    regardless of closing speed -- the general-aviation "hard to see an
    aircraft on a collision course" failure mode. **This is a feature, not
    a bug** -- do not "fix" it; this test exists to catch exactly that."""
    target = GeoPosition(x=0.0, z=1000.0, alt_m=0.0)
    # Velocity purely along +z, i.e. straight along the observer->target
    # line of sight -- a closing speed far above the threshold on any axis
    # that mattered, yet v_perp is exactly zero.
    velocity = Vec3(x=0.0, y=0.0, z=-200.0)
    assert is_apparently_moving(_OBSERVER, target, velocity) is False


def test_none_velocity_is_unknown_not_stopped() -> None:
    target = _crossing_target(2000.0)
    assert is_apparently_moving(_OBSERVER, target, None) is None


def test_zero_range_is_unknown() -> None:
    """Degenerate case (target coincident with observer) -- no line of
    sight to project against, so no honest verdict either way."""
    assert is_apparently_moving(_OBSERVER, _OBSERVER, Vec3(1.0, 0.0, 0.0)) is None


def test_apparent_angular_rate_non_axis_aligned() -> None:
    """A non-axis-aligned bearing (45 deg), per the project's rule that any
    angular-formula test must exercise one. Target at (1000, 1000): range =
    1000*sqrt(2), line-of-sight unit vector u = (1/sqrt2, 1/sqrt2, 0).
    Velocity purely along x: v = (10, 0, 0). v.u = 10/sqrt2;
    v_perp = v - (v.u)u = (5, -5, 0), |v_perp| = 5*sqrt(2).
    rate = |v_perp| / range = (5*sqrt(2)) / (1000*sqrt(2)) = 5/1000 =
    0.005 rad/s -- an exact closed form, independent of this module's own
    implementation."""
    target = GeoPosition(x=1000.0, z=1000.0, alt_m=0.0)
    velocity = Vec3(x=10.0, y=0.0, z=0.0)
    rate = apparent_angular_rate_rad_s(_OBSERVER, target, velocity)
    assert rate == pytest.approx(0.005, abs=1e-9)


def test_early_out_does_not_compute_full_vector_fields() -> None:
    """Below the cheap early-out (`|v| / range < threshold`), the gate never
    computes the full projection -- `perp_speed_mps`/`angular_rate_rad_s`
    stay `None` rather than a fabricated `0.0` (module docstring: "there is
    nothing honest to report ... beyond 'not computed'")."""
    target = _crossing_target(5000.0)
    result = evaluate_motion_gate(_OBSERVER, target, _crossing_velocity(5.0))
    assert result.moving is False
    assert result.speed_mps == pytest.approx(5.0)
    assert result.perp_speed_mps is None
    assert result.angular_rate_rad_s is None


def test_full_computation_populates_every_field_when_moving() -> None:
    target = _crossing_target(2000.0)
    result = evaluate_motion_gate(_OBSERVER, target, _crossing_velocity(10.0))
    assert result.moving is True
    assert result.speed_mps == pytest.approx(10.0)
    assert result.perp_speed_mps == pytest.approx(10.0)
    assert result.angular_rate_rad_s == pytest.approx(10.0 / 2000.0)


def test_threshold_value_matches_derivation() -> None:
    """8 arcmin/s = 2 arcmin/s lab baseline * 4 cockpit penalty."""
    assert MOTION_ANGULAR_THRESHOLD_RAD_S == pytest.approx(math.radians(8.0 / 60.0))


def test_max_skew_is_two_seconds() -> None:
    assert MOTION_VELOCITY_MAX_SKEW_S == 2.0
