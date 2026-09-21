"""The apparent-angular-rate movement gate -- `plans/movement-detection/
plan.md`, turning `body-layer/ROADMAP.md`'s 2026-09-20 design into code.

**The velocity vector must never leave this module.** `perception/` must
not import `belief/` (`source.py`'s module docstring), and this module is
the one place that boundary is load-bearing for movement specifically: only
the tri-state `bool | None` verdict (`is_apparently_moving`) is allowed to
cross into `Observation.apparent_motion` -- omniscience is removed by this
gate, not by the source that supplied `velocity` (DCS truth, taken from
`Object.getVelocity()` in the mission-scripting environment, per the
roadmap's explicit "the omniscience is then removed by the gate, not by
the source" design).

**The gate, stated precisely.** Given observer position `o`, target
position `p`, target *absolute* velocity `v` (DCS m/s, not relative to
ownship -- see below):

    d = p - o ;  range = |d| ;  u = d / range
    v_perp = v - (v . u) u
    rate_rad_s = |v_perp| / range
    moving = rate_rad_s >= MOTION_ANGULAR_THRESHOLD_RAD_S

**The `t` in `s = v*t` cancels and must not appear anywhere in this
module.** The ~1 s perceptual integration window is part of the
*derivation* of `MOTION_ANGULAR_THRESHOLD_RAD_S` below (8 arcmin of
displacement accumulated over about a second), not a term in the
comparison -- both `s = v*t` and the range the angle is measured against
carry the same `t`, so it cancels. Reaching for the inter-poll `dt` here
would make the verdict poll-rate-dependent and break replay determinism.

**Cheap early-out first, exactly as the roadmap specifies.** Since
`|v_perp| <= |v|`, if `|v| / range < threshold` the candidate is rejected
with one divide and one compare, no vector algebra at all -- most
candidates die here (`evaluate_motion_gate`'s first branch).

**Absolute velocity, not ownship-relative.** A stationary truck seen from a
moving helicopter sweeps across the field of view but does not *look* like
it's moving, because it's static against its background; humans discount
self-motion through optic flow (the roadmap's own reasoning). The one
documented exception -- a target against empty sky, with no static
background to be judged against -- is **not implemented** here (the
roadmap's own accepted limitation): its only beneficiaries are air contacts,
which almost always clear this threshold on absolute velocity anyway.

**The constant-bearing blind spot is not a bug.** A unit on a
constant-bearing collision course has `v` aligned with `u` (the line of
sight), so `v_perp` is exactly zero and `rate_rad_s` reads zero regardless
of closing speed -- the general-aviation "an aircraft on an intercept
course is hard to see because the eye perceives no motion" blind spot,
falling directly out of the geometry with no special-casing. **Do not
special-case it away.**

Threshold, written as its derivation rather than the bare product (the
`BINOCULAR_OPTIC` stabilisation-penalty precedent, `optics.py`): 2 arcmin/s
human smooth-motion detection in lab conditions, times 4 for canopy
vibration, scanning-not-fixating, and divided attention -- three effects lab
conditions exclude by design and that all stack in a real cockpit. Both
factors are uncalibrated, same debt class as `BINOCULAR_OPTIC`'s ~0.67
stabilisation penalty: named, isolated, and movable in one place rather than
buried in a single unexplained number.

Pure, no I/O, no `belief/` import -- mirrors `optics.py`/`cockpit_mask.py`'s
own posture."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from perception.geometry import GeoPosition

#: Human smooth-motion detection threshold under lab conditions
#: (fixating on a known location) -- the conservative end: a *higher*
#: threshold makes motion *harder* to detect, per the roadmap's own framing.
MOTION_THRESHOLD_LAB_ARCMIN_PER_S: Final[float] = 2.0

#: Covers canopy vibration smearing the image, scanning rather than
#: fixating, and divided attention -- three effects lab conditions exclude
#: by design and that all stack in a real cockpit. Uncalibrated (module
#: docstring); a sortie can measure it later.
MOTION_COCKPIT_PENALTY: Final[float] = 4.0

#: 8 arcmin/s = 0.133 deg/s = 2.327e-3 rad/s. The perceptual integration
#: window this is derived over (~1 s) does not appear as a term anywhere in
#: this module -- see the module docstring's "the `t` ... cancels" section.
MOTION_ANGULAR_THRESHOLD_RAD_S: Final[float] = math.radians(
    MOTION_THRESHOLD_LAB_ARCMIN_PER_S * MOTION_COCKPIT_PENALTY / 60.0
)

#: `plans/movement-detection/plan.md` Decision 3: objects arrive at 5 Hz,
#: velocity at 1 Hz, so worst-case skew is ~1 s plus transport. Beyond this
#: bound a joined velocity sample is dropped to `None` (unknown, never
#: reused as stale) -- tolerable because a ground vehicle's velocity barely
#: changes over ~1 s, and anything whose velocity *does* change materially
#: that fast (aircraft) exceeds `MOTION_ANGULAR_THRESHOLD_RAD_S` by one to
#: two orders of magnitude regardless, so the verdict is insensitive to the
#: staleness. Consumed by `naked_eye_source.py`'s join step, not by this
#: module's own gate functions (which take an already-resolved velocity).
MOTION_VELOCITY_MAX_SKEW_S: Final[float] = 2.0


@dataclass(frozen=True, slots=True)
class Vec3:
    """A DCS-native velocity vector, metres/second. `y` is the vertical
    component (DCS convention -- `x`/`z` are the north-like/east-like
    horizontal axes `perception.geometry.GeoPosition` uses for position;
    `y` maps onto `GeoPosition.alt_m`'s axis, not a fourth one)."""

    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class MotionGateResult:
    """The gate's full inputs/verdict, for `perception.detection_trace`'s
    consumption (`plans/movement-detection/plan.md`'s Affected Modules
    section: "record the gate's inputs and verdict ... so a negative is
    inspectable rather than silent"). `is_apparently_moving` below returns
    only `moving` -- the tri-state boolean that is the only thing allowed to
    cross into `belief/` (module docstring).

    `perp_speed_mps`/`angular_rate_rad_s` are `None` when the cheap
    early-out alone decided the verdict (module docstring) -- the full
    vector projection was never computed, so there is nothing honest to
    report for either field beyond "not computed", not `0.0`."""

    moving: bool | None
    speed_mps: float | None
    perp_speed_mps: float | None
    angular_rate_rad_s: float | None


def apparent_angular_rate_rad_s(
    observer: GeoPosition, target: GeoPosition, velocity: Vec3
) -> float:
    """The full gate expression (module docstring): the component of
    `velocity` perpendicular to the observer->target line of sight, divided
    by range. Always does the full vector projection -- callers wanting the
    cheap early-out first should use `evaluate_motion_gate`/
    `is_apparently_moving` instead, not this function directly.

    Returns `0.0` for a target at zero range (degenerate; unreachable in
    practice since `range_m` between distinct DCS objects is never exactly
    zero, but defined rather than raising)."""
    dx = target.x - observer.x
    dz = target.z - observer.z
    dalt = target.alt_m - observer.alt_m
    range_m = math.sqrt(dx * dx + dz * dz + dalt * dalt)
    if range_m <= 0.0:
        return 0.0

    ux, uz, ualt = dx / range_m, dz / range_m, dalt / range_m
    v_dot_u = velocity.x * ux + velocity.z * uz + velocity.y * ualt
    vperp_x = velocity.x - v_dot_u * ux
    vperp_z = velocity.z - v_dot_u * uz
    vperp_alt = velocity.y - v_dot_u * ualt
    vperp_mag = math.sqrt(vperp_x * vperp_x + vperp_z * vperp_z + vperp_alt * vperp_alt)
    return vperp_mag / range_m


def evaluate_motion_gate(
    observer: GeoPosition, target: GeoPosition, velocity: Vec3 | None
) -> MotionGateResult:
    """The gate, with the cheap early-out first (module docstring) and every
    intermediate value preserved for `perception.detection_trace`. `velocity
    is None` (no velocity sample joined this poll -- unknown, never
    "stopped") is the only case that yields `moving=None`; every other
    outcome is a definite `True`/`False`, since a real velocity sample is
    always either above or at-or-below the threshold."""
    if velocity is None:
        return MotionGateResult(
            moving=None, speed_mps=None, perp_speed_mps=None, angular_rate_rad_s=None
        )

    dx = target.x - observer.x
    dz = target.z - observer.z
    dalt = target.alt_m - observer.alt_m
    range_m = math.sqrt(dx * dx + dz * dz + dalt * dalt)
    speed_mps = math.sqrt(
        velocity.x * velocity.x + velocity.y * velocity.y + velocity.z * velocity.z
    )

    if range_m <= 0.0:
        # Degenerate (target at observer's own position) -- no line of
        # sight to project against, so no honest verdict either way.
        return MotionGateResult(
            moving=None,
            speed_mps=speed_mps,
            perp_speed_mps=None,
            angular_rate_rad_s=None,
        )

    # Early-out: |v_perp| <= |v| always, so if |v| / range already clears
    # the threshold, v_perp cannot possibly clear it either -- one divide,
    # one compare, no vector algebra (module docstring).
    if speed_mps / range_m < MOTION_ANGULAR_THRESHOLD_RAD_S:
        return MotionGateResult(
            moving=False,
            speed_mps=speed_mps,
            perp_speed_mps=None,
            angular_rate_rad_s=None,
        )

    rate_rad_s = apparent_angular_rate_rad_s(observer, target, velocity)
    return MotionGateResult(
        moving=rate_rad_s >= MOTION_ANGULAR_THRESHOLD_RAD_S,
        speed_mps=speed_mps,
        perp_speed_mps=rate_rad_s * range_m,
        angular_rate_rad_s=rate_rad_s,
    )


def is_apparently_moving(
    observer: GeoPosition, target: GeoPosition, velocity: Vec3 | None
) -> bool | None:
    """The gate's tri-state verdict -- the only thing `perception/` is
    allowed to hand across the `belief/` boundary for movement (module
    docstring). `None` means "unknown" (no velocity sample), never
    "stopped"."""
    return evaluate_motion_gate(observer, target, velocity).moving
