"""Tests for `perception.light_level` -- `BL-B124` Stage 2,
`plans/bl-b124-light-level/plan.md`.

`sun_elevation_deg`'s accuracy is checked against the plan's own anchor
table (`docs/concept/detection-in-non-perfect-conditions.md`'s
2020-06-01 Syria test mission) within a generous tolerance -- the
explore-notes themselves note the formula puts sunrise ~4 minutes off
DCS's own reported sunrise, "likely refraction/model difference", so this
is a sanity check on the formula's shape and order of magnitude, not a
byte-exact oracle."""

from __future__ import annotations

import pytest

from perception.light_level import (
    EYE_FULL_DAYLIGHT_SUN_ELEV_DEG,
    SIGHT_FULL_DARK_SUN_ELEV_DEG,
    light_factor,
    sun_elevation_deg,
)
from perception.optics import (
    BINOCULAR_OPTIC,
    SIGHT_NARROW_OPTIC,
    SIGHT_WIDE_OPTIC,
    UNAIDED_OPTIC,
    Optic,
)

# The test mission's own position, N31 34'55" E40 17'01" (the user's
# measurement setup, docs/concept/detection-in-non-perfect-conditions.md).
_LAT_DEG = 31 + 34 / 60 + 55 / 3600
_LON_DEG = 40 + 17 / 60 + 1 / 3600
_YEAR, _MONTH, _DAY = 2020, 6, 1

#: DCS's own reported sunrise for the test mission.
_DCS_SUNRISE_S = 5 * 3600 + 18 * 60 + 29


def _elevation_at_offset_s(offset_s: float) -> float:
    return sun_elevation_deg(
        year=_YEAR,
        month=_MONTH,
        day=_DAY,
        abs_time_s=_DCS_SUNRISE_S + offset_s,
        lat_deg=_LAT_DEG,
        lon_deg=_LON_DEG,
    )


class TestSunElevationDeg:
    def test_matches_dcs_sunrise_within_a_few_minutes(self) -> None:
        """Elevation at DCS's own reported sunrise instant should be
        close to zero -- the explore-notes' own ~4-minute discrepancy is
        the expected order of magnitude, not a bug."""
        elevation = _elevation_at_offset_s(0.0)
        assert abs(elevation) < 1.0

    def test_minus_28_minutes_matches_the_plans_anchor(self) -> None:
        elevation = _elevation_at_offset_s(-28 * 60)
        assert elevation == pytest.approx(-5.3, abs=0.1)

    def test_minus_18_minutes_matches_the_plans_anchor(self) -> None:
        elevation = _elevation_at_offset_s(-18 * 60)
        assert elevation == pytest.approx(-3.5, abs=0.1)

    def test_plus_2_minutes_matches_the_plans_anchor(self) -> None:
        elevation = _elevation_at_offset_s(2 * 60)
        assert elevation == pytest.approx(0.3, abs=0.1)

    def test_elevation_rises_monotonically_through_the_dawn_window(self) -> None:
        offsets = [-40 * 60, -28 * 60, -18 * 60, 0.0, 2 * 60, 20 * 60]
        elevations = [_elevation_at_offset_s(o) for o in offsets]
        assert elevations == sorted(elevations)

    def test_abs_time_s_past_86400_rolls_over_the_calendar_day(self) -> None:
        """`timer.getAbsTime()` keeps climbing past 86400 across
        midnight (module docstring) -- a second day's worth of seconds
        plus the same dawn offset should reproduce (approximately) the
        same elevation a day later, not raise or silently wrap."""
        day_1 = _elevation_at_offset_s(-18 * 60)
        day_2 = sun_elevation_deg(
            year=_YEAR,
            month=_MONTH,
            day=_DAY,
            abs_time_s=86400.0 + _DCS_SUNRISE_S - 18 * 60,
            lat_deg=_LAT_DEG,
            lon_deg=_LON_DEG,
        )
        # The sun's own declination drifts a little day to day in June,
        # so this is a loose tolerance -- the point is "did not raise and
        # landed near the same dawn", not exact reproduction.
        assert day_2 == pytest.approx(day_1, abs=0.5)

    def test_noon_is_high_and_midnight_is_low(self) -> None:
        noon = _elevation_at_offset_s(7 * 3600)  # ~12:18 local
        midnight = _elevation_at_offset_s(-5 * 3600 - 18 * 60)  # ~00:00 local
        assert noon > 60.0
        assert midnight < -30.0

    @pytest.mark.parametrize("abs_time_s", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_abs_time_s_raises(self, abs_time_s: float) -> None:
        """`[[BL-B137]]` -- defence in depth alongside `schema.firing.
        MissionClockSample.from_wire`'s own wire-boundary guard, since
        this function is also reachable with a locally-extrapolated
        `abs_time_s` that never passes back through that parser
        (`body._resolve_sun_elevation_deg`). Mutation proof this guard
        is load-bearing: removing it lets a NaN `abs_time_s` reach the
        final clamp and silently resolve to 90.0 deg (full daylight) --
        see `test_without_the_guard_nan_silently_resolves_to_full_
        daylight` below, which demonstrates that exact failure mode
        directly against the clamp the guard exists to pre-empt."""
        with pytest.raises(ValueError):
            sun_elevation_deg(
                year=_YEAR,
                month=_MONTH,
                day=_DAY,
                abs_time_s=abs_time_s,
                lat_deg=_LAT_DEG,
                lon_deg=_LON_DEG,
            )

    def test_without_the_guard_nan_silently_resolves_to_full_daylight(self) -> None:
        """Not a test of this module's own code -- a demonstration, run
        directly against the bare clamp `sun_elevation_deg` guards
        ahead of, that the finding this guard exists for is real: a NaN
        `sin_altitude` is **not** held clean by `max(-1.0, min(1.0,
        nan))` the way an ordinary out-of-range value would be. `min`/
        `max` keep their first argument whenever a NaN comparison makes
        it `False`, so this is exactly `90.0`, not merely "wrong" --
        the one outcome `[[BL-B137]]`'s finding, and this feature's own
        design (user Q6), both call out as the forbidden fallback."""
        import math

        sin_altitude = float("nan")
        clamped = max(-1.0, min(1.0, sin_altitude))
        assert math.degrees(math.asin(clamped)) == 90.0


class TestLightFactor:
    def test_flat_at_one_above_full_daylight(self) -> None:
        for optic in (
            UNAIDED_OPTIC,
            BINOCULAR_OPTIC,
            SIGHT_WIDE_OPTIC,
            SIGHT_NARROW_OPTIC,
        ):
            assert light_factor(optic, EYE_FULL_DAYLIGHT_SUN_ELEV_DEG) == (
                1.0,
                1.0,
                1.0,
            )
            assert light_factor(optic, EYE_FULL_DAYLIGHT_SUN_ELEV_DEG + 10.0) == (
                1.0,
                1.0,
                1.0,
            )

    def test_flat_at_zero_below_full_dark(self) -> None:
        for optic in (
            UNAIDED_OPTIC,
            BINOCULAR_OPTIC,
            SIGHT_WIDE_OPTIC,
            SIGHT_NARROW_OPTIC,
        ):
            assert light_factor(optic, SIGHT_FULL_DARK_SUN_ELEV_DEG) == (0.0, 0.0, 0.0)
            assert light_factor(optic, SIGHT_FULL_DARK_SUN_ELEV_DEG - 10.0) == (
                0.0,
                0.0,
                0.0,
            )

    def test_unknown_optic_is_a_no_op(self) -> None:
        unknown = Optic(
            name="not_a_real_optic",
            presence_range_mult=1.0,
            class_range_mult=1.0,
            type_range_mult=1.0,
            fov_half_angle_deg=None,
        )
        assert light_factor(unknown, -8.0) == (1.0, 1.0, 1.0)

    def test_sight_narrow_outperforms_eye_at_dusk(self) -> None:
        """The whole point of this feature (goal check E3): at dusk, the
        9K113 narrow field holds up far better than the naked eye."""
        eye = light_factor(UNAIDED_OPTIC, -3.5)
        narrow = light_factor(SIGHT_NARROW_OPTIC, -3.5)
        assert narrow[0] > eye[0]
        assert narrow[1] > eye[1]

    def test_eye_type_is_zero_at_minus_18_minutes(self) -> None:
        """Goal check E2: below sunrise, the eye and binoculars never
        give a type at any range."""
        eye = light_factor(UNAIDED_OPTIC, -3.5)
        binocular = light_factor(BINOCULAR_OPTIC, -3.5)
        assert eye[2] == 0.0
        assert binocular[2] == 0.0

    def test_interpolates_between_measured_anchors(self) -> None:
        """A sun elevation strictly between two measured anchors falls
        strictly between their factors -- the curve is piecewise-linear,
        not a step function (goal check E6)."""
        at_m28 = light_factor(SIGHT_NARROW_OPTIC, -5.3)
        at_m18 = light_factor(SIGHT_NARROW_OPTIC, -3.5)
        midpoint = light_factor(SIGHT_NARROW_OPTIC, -4.4)
        assert at_m28[0] < midpoint[0] < at_m18[0]

    def test_every_factor_component_stays_within_unit_interval(self) -> None:
        for optic in (
            UNAIDED_OPTIC,
            BINOCULAR_OPTIC,
            SIGHT_WIDE_OPTIC,
            SIGHT_NARROW_OPTIC,
        ):
            for elevation in (
                -30.0,
                -12.0,
                -8.0,
                -5.3,
                -4.4,
                -3.5,
                -1.0,
                0.3,
                3.0,
                6.0,
                20.0,
            ):
                presence, class_, type_ = light_factor(optic, elevation)
                for component in (presence, class_, type_):
                    assert 0.0 <= component <= 1.0
