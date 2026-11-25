"""Light-level astronomy and the per-optic, per-tier light factor curve --
`BL-B124` Stage 2, `plans/bl-b124-light-level/plan.md`.

**Pure, no DCS import.** `sun_elevation_deg` is ordinary local astronomy
over a mission's own date, mission wall clock (the amendment's
`abs_time_s`, seconds since 00:00 of the mission's start day, read from
`aircraft-layer`'s firing-events poll via `schema.firing.
MissionClockSample` -- see that module's own docstring) and ownship
lat/lon. `light_factor` is the anchored, per-optic, per-tier curve the
user's own dawn measurements established
(`docs/concept/detection-in-non-perfect-conditions.md`), piecewise-linear
between three measured anchor points and flat at the two end-point
tunables outside them.

**Wired into `body.py`'s poll loop as of Stage 4.** Stage 3 threaded a
`light_factor`/`sun_elevation_deg` parameter through `visibility.
tier_ranges()`/`check_visibility()`/`belief.optic_policy.py` with a true
no-op default; Stage 4 (`body._resolve_sun_elevation_deg`) computes a
real value every poll from the firing-events Hook's `mission_clock` and
ownship lat/lon, extrapolating between 1 Hz samples via model time and
forcing full dark (never a daylight fallback) once the clock has been
unreadable for longer than `MISSION_CLOCK_MAX_AGE_S`.

## `sun_elevation_deg`

Standard low-precision solar-position formula ("Astronomical Almanac"
low-precision series, ~0.01 deg accuracy -- ample for a light factor
whose own measured anchors are themselves only good to a few tenths of a
degree). DCS's mission clock carries no explicit timezone; this module
resolves one the same way the explore-notes derived it for the Syria test
mission (`round(lon_deg / 15.0)` hours east of UTC -- the "local mean
solar time" convention used whenever no political timezone is supplied,
and it reproduces the explore-notes' own UTC+3 for Syria's longitude
exactly). **Numerically verified against this plan's own anchor table**
(`docs/concept/detection-in-non-perfect-conditions.md`'s 2020-06-01 Syria
mission, N31 34'55" E40 17'01"): this formula puts sunrise at 05:19 local
against DCS's own reported 05:18:29, and the three anchor elevations at
-5.338/-3.482/+0.303 deg against the plan's stated -5.3/-3.5/+0.3 -- the
reproducible check any future reviewer can re-run is in this module's own
test file.

## `light_factor`

The three measured anchors (-5.3 deg/-3.5 deg/+0.3 deg, the plan's
amendment) carry a per-optic, per-tier `(presence, class, type)` factor,
computed as `measured_range / baseline_clear_day_range` against the
BTR-60 naked-eye calibration already established in this codebase
(`body-layer/research/2026-09-21-aspect-magnification-and-distinctiveness.md`
-- presence 3.1 km, class 0.4 km, type 0.2 km -- scaled per optic by its
own `presence_range_mult`/`class_range_mult`/`type_range_mult`, the same
baseline `optics.py`'s own multiplier table was derived against). A
computed ratio above 1.0 (the naked eye's `+0.3 deg` class/type figures,
0.8/0.4 and 0.25/0.2) is clamped to 1.0 -- the source doc's own caveat
("coarse measurements that show trends... do not treat these numbers as
definite truth") makes a >1.0 "better than clear daylight" reading noise,
not a real effect, and "any optic = almost daylight perf" is the doc's
own qualitative description of that anchor for every optic. **First-cut,
status=judgement data, same posture as `FIRE_LIFE_FRACTION_MAX`** -- the
test card (plan's "Test card outline" §1) is what turns these into
measurements. Declared as plain module data, not individual tunables
(plan's "Behaviour constants" section): the *shape* (which anchors exist,
in what order) is a code structure, not a dial.

Outside `[SIGHT_FULL_DARK_SUN_ELEV_DEG, EYE_FULL_DAYLIGHT_SUN_ELEV_DEG]`
the curve is flat: `(0.0, 0.0, 0.0)` below the full-dark elevation (every
optic sees nothing but light sources -- `perception.emitters.py`'s
existing unconditional bypass is untouched by this, module docstring),
`(1.0, 1.0, 1.0)` above the full-daylight elevation (today's behaviour,
unchanged). These two are genuinely "a sortie will want to move this"
constants and are declared through `tuning.real` below."""

from __future__ import annotations

import math

import tuning
from perception.optics import Optic

#: Below this sun elevation, every optic -- including the 9K113's orange
#: filter -- sees nothing but light sources (plan E4: "In real darkness,
#: cannot see anything"); a *smaller* (more negative) value here keeps
#: the 9K113 usable deeper into the night than measured, while a *larger*
#: (less negative) value goes fully blind earlier than measured, which is
#: the dangerous direction for the no-omniscience goal this feature
#: exists for -- an over-generous floor leaves Petrovich reporting a unit
#: no real crewman could see. Default -12.0 deg (~65 min before the test
#: mission's sunrise) is a first-cut estimate per the explore-notes, not
#: a measurement -- the test card's dawn pass (plan "Test card outline"
#: §1) narrows it. `hi=-6.0` keeps this value structurally below the
#: nearest measured anchor (-5.3 deg) by at least half a degree, so the
#: piecewise-linear curve below never has to reconcile an override that
#: crosses a fixed anchor.
SIGHT_FULL_DARK_SUN_ELEV_DEG: float = tuning.real(
    "perception.light_level.SIGHT_FULL_DARK_SUN_ELEV_DEG",
    -12.0,
    lo=-30.0,
    hi=-6.0,
    status="judgement",
)

#: Above this sun elevation, the naked eye (and every other optic) is at
#: its full clear-day range -- today's unmodified behaviour -- and a
#: *smaller* value here declares full daylight performance earlier than
#: measured, which is the dangerous direction since it under-dims a
#: still-dim morning, while a *larger* value only keeps dimming
#: performance later into the morning than measured. Default +6.0 deg
#: (~31 min after the test mission's sunrise) is a first-cut estimate per
#: the explore-notes, not a measurement -- the test card's dawn pass
#: narrows it. `lo=1.0` keeps this value
#: structurally above the nearest measured anchor (+0.3 deg) by at least
#: a few tenths of a degree, so the piecewise-linear curve below never
#: has to reconcile an override that crosses a fixed anchor.
EYE_FULL_DAYLIGHT_SUN_ELEV_DEG: float = tuning.real(
    "perception.light_level.EYE_FULL_DAYLIGHT_SUN_ELEV_DEG",
    6.0,
    lo=1.0,
    hi=15.0,
    status="judgement",
)

#: **Stage 4 -- how long `body.py` keeps extrapolating sun elevation from
#: the last mission-clock sample the firing-events Hook actually
#: reported before giving up and forcing full dark instead; a *smaller*
#: value here turns an ordinary single dropped poll into spurious
#: blindness (the sun moves ~0.004 deg/s, so extrapolating a few seconds
#: past the last sample is still accurate to well under the curve's own
#: measurement error), while a *larger* value risks hiding a genuinely
#: dead Hook/collector feed for longer before the user ever hears about
#: it** (user Q6: "mission should always have both readable. Error if
#: not."). Default 5.0 s is a few times the Hook's own 1 Hz poll cadence
#: -- generous enough to absorb one or two missed polls, tight enough
#: that a real failure surfaces within a handful of seconds rather than
#: minutes. `lo=2.0` keeps at least one full poll cycle of slack; `hi
#: =30.0` is the outer bound before "still extrapolating" stops being a
#: defensible reading of "the feed is fine, just slow this poll."
MISSION_CLOCK_MAX_AGE_S: float = tuning.real(
    "perception.light_level.MISSION_CLOCK_MAX_AGE_S",
    5.0,
    lo=2.0,
    hi=30.0,
    status="judgement",
)

#: The three measured dawn anchors, as sun elevation in degrees (plan's
#: amendment, date-corrected from the explore-notes' own minutes-from-
#: sunrise table using the test mission's confirmed 2020-06-01 date).
#: Fixed data, not tunable -- see module docstring.
_ANCHOR_M28_DEG: float = -5.3
_ANCHOR_M18_DEG: float = -3.5
_ANCHOR_P2_DEG: float = 0.3

#: One optic's `(presence, class, type)` factor at one anchor.
_TierFactors = tuple[float, float, float]
#: One optic's factor at all three anchors, in `(m28, m18, p2)` order --
#: matches `_ANCHOR_M28_DEG`/`_ANCHOR_M18_DEG`/`_ANCHOR_P2_DEG` above.
_AnchorFactors = tuple[_TierFactors, _TierFactors, _TierFactors]

#: Per-optic, per-tier factors at the three measured anchors (module
#: docstring's derivation: measured range / BTR-60 naked-eye baseline
#: scaled by the optic's own per-tier multiplier, clamped to `[0.0,
#: 1.0]`). Keyed by `optic.name` -- `perception.optics.py`'s four named
#: optics are the only keys this table needs; an optic not listed here
#: (none exist today) is treated as a no-op by `light_factor` below
#: rather than guessed at.
_MEASURED_FACTORS: dict[str, _AnchorFactors] = {
    # eye: -28min nothing seen; -18min presence 0.5/3.1, class 0.2/0.4,
    # type none; +2min presence 1.8/3.1, class/type clamp to 1.0 (doc's
    # own 0.8/0.4 and 0.25/0.2 both exceed 1.0 before clamping).
    "unaided": ((0.0, 0.0, 0.0), (0.161, 0.500, 0.0), (0.581, 1.0, 1.0)),
    # binocular: -28min nothing seen; -18min presence 1.3/7.502,
    # class 0.2/1.40, type none; +2min "any optic = almost daylight".
    "binocular": ((0.0, 0.0, 0.0), (0.173, 0.143, 0.0), (1.0, 1.0, 1.0)),
    # 9K113 wide: -28min presence 2.5/11.005, class 0.9/2.80,
    # type 0.5/1.30; -18min presence 5.0/11.005, class 1.0/2.80,
    # type 0.5/1.30; +2min "any optic = almost daylight".
    "sight_wide": (
        (0.227, 0.321, 0.385),
        (0.454, 0.357, 0.385),
        (1.0, 1.0, 1.0),
    ),
    # 9K113 narrow: -28min presence 7.0/18.011, class 2.0/5.50,
    # type 1.1/3.00; -18min presence 12.0/18.011, class 3.4/5.50,
    # type 1.8/3.00; +2min "any optic = almost daylight".
    "sight_narrow": (
        (0.389, 0.364, 0.367),
        (0.666, 0.618, 0.600),
        (1.0, 1.0, 1.0),
    ),
}


def _interp_scalar(xs: tuple[float, ...], ys: tuple[float, ...], x: float) -> float:
    """Piecewise-linear interpolation over parallel, strictly-increasing
    `xs`/`ys`. `x` is assumed to already lie within `[xs[0], xs[-1]]`;
    `light_factor` clamps outside that range itself before ever calling
    this helper."""
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        if x0 <= x <= x1:
            if x1 == x0:
                return ys[i]
            t = (x - x0) / (x1 - x0)
            return ys[i] + t * (ys[i + 1] - ys[i])
    return ys[-1]


def light_factor(optic: Optic, sun_elevation_deg: float) -> tuple[float, float, float]:
    """The `(presence, class, type)` multiplier this `optic` achieves at
    `sun_elevation_deg`, meant to multiply `optic.presence_range_mult`/
    `class_range_mult`/`type_range_mult` the same way those already scale
    `visibility.tier_ranges()`'s thresholds (Stage 3's threading point).

    Flat `(1.0, 1.0, 1.0)` at or above `EYE_FULL_DAYLIGHT_SUN_ELEV_DEG`
    (today's unmodified behaviour) and flat `(0.0, 0.0, 0.0)` at or below
    `SIGHT_FULL_DARK_SUN_ELEV_DEG` (every optic blind -- light sources are
    a separate, unconditional mechanism, `perception.emitters.py`, not
    touched by this factor). Piecewise-linear between the three measured
    anchors in between. An optic this module has no measured data for
    (none exist today, `perception.optics.py`'s four named optics are
    exhaustive) returns `(1.0, 1.0, 1.0)` -- a no-op, never a guess."""
    if sun_elevation_deg >= EYE_FULL_DAYLIGHT_SUN_ELEV_DEG:
        return (1.0, 1.0, 1.0)
    if sun_elevation_deg <= SIGHT_FULL_DARK_SUN_ELEV_DEG:
        return (0.0, 0.0, 0.0)

    measured = _MEASURED_FACTORS.get(optic.name)
    if measured is None:
        return (1.0, 1.0, 1.0)

    xs = (
        SIGHT_FULL_DARK_SUN_ELEV_DEG,
        _ANCHOR_M28_DEG,
        _ANCHOR_M18_DEG,
        _ANCHOR_P2_DEG,
        EYE_FULL_DAYLIGHT_SUN_ELEV_DEG,
    )
    presence = _interp_scalar(
        xs,
        (0.0, measured[0][0], measured[1][0], measured[2][0], 1.0),
        sun_elevation_deg,
    )
    class_ = _interp_scalar(
        xs,
        (0.0, measured[0][1], measured[1][1], measured[2][1], 1.0),
        sun_elevation_deg,
    )
    type_ = _interp_scalar(
        xs,
        (0.0, measured[0][2], measured[1][2], measured[2][2], 1.0),
        sun_elevation_deg,
    )
    return (presence, class_, type_)


def _julian_day(year: int, month: int, day: int, hour_utc: float) -> float:
    """Julian day number for a UTC calendar date and fractional
    hour-of-day, via the standard Fliegel-Van Flandern algorithm."""
    y, m = year, month
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd0 = (
        math.floor(365.25 * (y + 4716))
        + math.floor(30.6001 * (m + 1))
        + day
        + b
        - 1524.5
    )
    return jd0 + hour_utc / 24.0


def sun_elevation_deg(
    *,
    year: int,
    month: int,
    day: int,
    abs_time_s: float,
    lat_deg: float,
    lon_deg: float,
) -> float:
    """Sun elevation above the horizon, in degrees, for the mission's own
    `year`/`month`/`day` (`schema.firing.MissionClockSample`'s
    `env.mission.date`), `abs_time_s` (`timer.getAbsTime()`, seconds
    since 00:00 of the mission's start day -- still climbing past 86400
    across midnight, handled below as ordinary day rollover through the
    Julian day, not a modulo) and ownship `lat_deg`/`lon_deg`
    (`world-model`'s `coordinates.dcs_to_wgs84`). See module docstring
    for the formula's source, accuracy and timezone convention."""
    utc_offset_hours = round(lon_deg / 15.0)
    total_hours_utc = abs_time_s / 3600.0 - utc_offset_hours
    jd = _julian_day(year, month, day, 0.0) + total_hours_utc / 24.0
    d = jd - 2451545.0

    g = math.radians(_norm_deg(357.529 + 0.98560028 * d))
    q = _norm_deg(280.459 + 0.98564736 * d)
    ecliptic_longitude = math.radians(
        _norm_deg(q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    )
    obliquity = math.radians(23.439 - 0.00000036 * d)
    right_ascension = math.atan2(
        math.cos(obliquity) * math.sin(ecliptic_longitude), math.cos(ecliptic_longitude)
    )
    declination = math.asin(math.sin(obliquity) * math.sin(ecliptic_longitude))

    gmst_hours = (18.697374558 + 24.06570982441908 * d) % 24.0
    local_hour_angle_deg = _norm_deg(
        gmst_hours * 15.0 + lon_deg - math.degrees(right_ascension)
    )
    local_hour_angle = math.radians(local_hour_angle_deg)

    lat = math.radians(lat_deg)
    sin_altitude = math.sin(lat) * math.sin(declination) + math.cos(lat) * math.cos(
        declination
    ) * math.cos(local_hour_angle)
    sin_altitude = max(-1.0, min(1.0, sin_altitude))
    return math.degrees(math.asin(sin_altitude))


def _norm_deg(x: float) -> float:
    """Normalise an angle in degrees to `[0, 360)`."""
    return x % 360.0
