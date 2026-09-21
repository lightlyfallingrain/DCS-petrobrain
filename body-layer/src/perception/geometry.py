"""Bearing/range/LOS-terrain-masking helpers -- shared by every
`PerceptionSource` tier, per both investigator sessions behind
`plans/pb1-perception-logger/plan.md`: neither Petrovich's own UI nor
`LoGetWorldObjects` carries a native range field, so range must always be
derived externally, and both tiers need the same derivation.

Bearing reference is **true heading**, per `plans/pb1-perception-logger/
plan.md` decision 2 (recorded once in `plans/body-layer/plan.md` §5).

Coordinate convention: DCS `x` is the north/lat-like axis, `z` is the
east/lon-like axis (`world-model`'s coordinate subsystem convention, see
`aircraft-layer/src/schema/__init__.py`'s docstring). A compass bearing
clockwise from north is therefore `atan2(delta_z, delta_x)`, not the
mathematical-convention `atan2(dy, dx)`.

World-model seam: `elevation_at` calls `query.describe_position` (the
`plans/body-layer/plan.md` §1 in-process seam) for a single-point lookup.
`line_of_sight_clear` below is a thin wrapper around world-model's own
`query.line_of_sight.line_of_sight_clear`
(`plans/world-model-los-generalization/plan.md`) -- the algorithm itself,
including the reasoning for why it samples `store.reader.sample_grid`
directly instead of going through `describe_position`, now lives in that
module's docstring, not here.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from query.describe import describe_position
from query.line_of_sight import line_of_sight_clear as _wm_line_of_sight_clear
from store.reader import sample_grid

#: Default number of interior points sampled along the observer->target
#: ground track for `line_of_sight_clear`. Interior only (excludes both
#: endpoints, which are the observer's/target's own ground position and are
#: not meaningful "is terrain in the way" checks).
_DEFAULT_LOS_SAMPLES = 20


@dataclass(frozen=True, slots=True)
class GeoPosition:
    """A bare DCS-native 3D position -- deliberately not `perception.source.
    OwnshipState` (which also carries `t_sim`/heading not needed here) or a
    full target record. Used for both the observer and the target in the
    functions below."""

    x: float
    z: float
    alt_m: float


def open_world_model(db_path: Path) -> sqlite3.Connection:
    """Open a world-model region `.sqlite` read-only.

    Deliberately does not import `build.pipeline.open_region_db` (which is
    exactly this one-line stdlib call) -- that module transitively imports
    the whole ingest pipeline (`build.ingest_osm`, `build.ingest_srtm`,
    `terrain.*`, `dcs_data.*`, ...), none of which this read-only query path
    needs. Kept as a local stdlib call instead of adding that coupling.
    """
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def bearing_deg(observer: GeoPosition, target: GeoPosition) -> float:
    """True bearing from `observer` to `target`, degrees clockwise from
    north, in `[0, 360)`."""
    delta_x = target.x - observer.x
    delta_z = target.z - observer.z
    return math.degrees(math.atan2(delta_z, delta_x)) % 360.0


def angular_delta_deg(a: float, b: float) -> float:
    """Smallest absolute angle between two bearings, in degrees (0-180) --
    moved here from `belief.attention`'s own private `_angular_delta_deg`
    by `plans/detection-cones-slice2/plan.md`'s 2B (hard part 5): it is the
    one piece genuinely shared between `belief.attention.area_contains`'s
    absolute-bearing wedge test and `perception.gaze.within_gaze`'s
    body-relative one -- small, frame-independent shortest-angle
    arithmetic, not a parallel implementation of either predicate. Both
    modules import this function rather than each defining their own copy."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def range_m(observer: GeoPosition, target: GeoPosition) -> float:
    """Straight-line (slant) range from `observer` to `target`, metres.
    Includes the altitude component -- ground range alone would understate
    range for anything but a level shot, and nothing in either tier's design
    needs ground range specifically."""
    delta_x = target.x - observer.x
    delta_z = target.z - observer.z
    delta_alt = target.alt_m - observer.alt_m
    return math.sqrt(delta_x * delta_x + delta_z * delta_z + delta_alt * delta_alt)


def project_from_bearing_range(
    observer: GeoPosition, bearing_deg: float, range_m: float
) -> GeoPosition:
    """Inverse of `bearing_deg()`/`range_m()` above: given an observer
    position, a true bearing (degrees clockwise from north), and a slant
    range, return the position that bearing/range pair implies.

    `range_m()` above returns *slant* range (includes the altitude
    component), but a bearing/range pair alone cannot disambiguate how much
    of that range is horizontal vs. vertical -- doing so needs a terrain
    model, which this function deliberately does not have (see next
    paragraph). This function therefore assumes the target is at the
    observer's own altitude (ground range == slant range), which is exactly
    the "flat, no terrain" simplification `plans/pb2-contact-memory/plan.md`
    Stage 1 calls for.

    Deliberately crude, by design -- `belief.association_over_time`'s only
    caller uses this to get an uncertainty-gated candidate position for
    percept<->contact matching, not to populate `Observation.
    derived_world_position` (which stays real ground truth from a
    concrete source's own candidate lookup, never this projection).

    **Does not change for BL-3** (`plans/bl3-world-enrichment/plan.md`) --
    `belief.association_over_time`'s gating depends on this function's exact
    flat behavior and tuned radius constants, so BL-3's terrain-aware
    estimate lives alongside it instead, as `project_terrain_aware` below,
    used only for the `position`/`relative_now`/`semantic` fields shown to
    the brain, never for percept<->contact gating.
    """
    bearing_rad = math.radians(bearing_deg)
    delta_x = range_m * math.cos(bearing_rad)
    delta_z = range_m * math.sin(bearing_rad)
    return GeoPosition(
        x=observer.x + delta_x, z=observer.z + delta_z, alt_m=observer.alt_m
    )


def project_terrain_aware(
    conn: sqlite3.Connection,
    theatre: str,
    observer: GeoPosition,
    bearing_deg: float,
    range_m: float,
    *,
    max_iterations: int,
) -> GeoPosition:
    """Terrain-aware counterpart to `project_from_bearing_range` above --
    BL-3 (`plans/bl3-world-enrichment/plan.md` step 1), used only to
    populate the `position`/`relative_now`/`semantic` fields
    `belief.enrichment` shows the brain, never for `belief.
    association_over_time`'s percept<->contact gating (see that function's
    own docstring for why the two must stay separate).

    A bearing/slant-range pair alone cannot say how much of the range is
    horizontal vs. vertical -- that split depends on the target's altitude,
    which this function resolves by treating it as a fixed-point problem:
    target altitude depends on terrain elevation at the target's horizontal
    position, which depends on the horizontal/vertical split of the slant
    range, which depends on target altitude. Starting from the flat
    assumption (target at observer altitude), each iteration re-derives the
    horizontal position from the current altitude estimate, samples terrain
    elevation there (`store.reader.sample_grid`, the same primitive
    `line_of_sight_clear` above uses, not `describe_position` -- avoids
    repeating its road/settlement/navaid joins every iteration), and adopts
    that as the next altitude estimate.

    `max_iterations` is a caller-supplied policy knob, not a module
    constant -- `belief.enrichment` decides it per contact (single-shot by
    default, more iterations when the contact is close or watched); this
    function stays ignorant of that policy, same posture as
    `perception.object_model`'s `classification_level` on `Observation`.

    Falls back to the flat `project_from_bearing_range` result if
    `sample_grid` ever returns `None` (elevation data unavailable at the
    sampled point) -- absence of data must never be papered over with a
    guessed altitude.
    """
    bearing_rad = math.radians(bearing_deg)
    cos_bearing = math.cos(bearing_rad)
    sin_bearing = math.sin(bearing_rad)

    target_alt_m = observer.alt_m
    horizontal_x = observer.x
    horizontal_z = observer.z

    for _ in range(max(1, max_iterations)):
        delta_alt_m = target_alt_m - observer.alt_m
        horizontal_range_m = math.sqrt(
            max(0.0, range_m * range_m - delta_alt_m * delta_alt_m)
        )
        horizontal_x = observer.x + horizontal_range_m * cos_bearing
        horizontal_z = observer.z + horizontal_range_m * sin_bearing
        terrain_m = sample_grid(conn, "elevation", horizontal_x, horizontal_z)
        if terrain_m is None:
            return project_from_bearing_range(observer, bearing_deg, range_m)
        target_alt_m = terrain_m

    return GeoPosition(x=horizontal_x, z=horizontal_z, alt_m=target_alt_m)


@dataclass(frozen=True, slots=True)
class BodyRelativeDirection:
    """A target direction expressed in the airframe's own frame rather than
    world-horizontal -- `plans/cockpit-visibility/plan.md`'s enabling fact
    for a real cockpit occlusion mask (see `body_relative_direction` below).

    `azimuth_deg` is signed, `(-180, 180]`, clockwise-positive: `0` is
    straight down the nose, `+90` is directly off the right side, `-90`
    directly off the left, `180`/`-180` is dead astern.

    `elevation_deg` is signed, positive = above the airframe boresight
    (roughly the pilot's/co-pilot's forward line of sight), negative =
    below it. `perception.cockpit_mask` works in *depression* (positive =
    down), which is simply `-elevation_deg` -- kept as elevation here
    because that is the natural sign for a rotation result, not to make the
    caller do the negation twice."""

    azimuth_deg: float
    elevation_deg: float


def body_relative_direction(
    observer: GeoPosition,
    target: GeoPosition,
    *,
    heading_true_deg: float,
    pitch_deg: float,
    bank_deg: float,
) -> BodyRelativeDirection:
    """Direction from `observer` to `target`, rotated out of world-horizontal
    and into the observer airframe's own frame (`plans/cockpit-visibility/
    plan.md` D1) -- the piece `perception.visibility`'s old `_within_fov`
    never had: a heading-only azimuth cone treats a target as equally
    visible whether it is level with the aircraft or far below it, and
    ignores bank entirely even though rolling toward a target is exactly
    what opens up a real downward view to that side.

    Pure vector rotation, no state, no I/O -- deliberately kept separate
    from `perception.cockpit_mask`'s table lookup (`plans/cockpit-
    visibility/plan.md` D3/point 2: "keep the geometry pure and separately
    testable from the gate") so the rotation math and the mask shape can
    each be tested, and later re-derived, independently.

    Derivation: build the observer->target vector in world coordinates
    (`north`/`east`/`up`, matching this module's DCS `x`=north/`z`=east/
    `alt_m`=up convention), then remove the airframe's own attitude from it
    in three steps, innermost-first:

    1. **Yaw** -- rotate `(north, east)` by `-heading_true_deg` about the
       vertical axis, so `forward0`/`right0` are horizontal components in
       the airframe's *heading* frame (still ignoring pitch/bank).
    2. **Pitch** -- rotate `(forward0, up)` by `-pitch_deg` about the
       (unaffected) right axis, so `forward1`/`up1` are in the airframe's
       *heading+pitch* frame. A target dead along the nose (wherever the
       nose is pointed, pitched or not) reduces to `forward1 = range`,
       `up1 = 0` here -- verified directly in `test_geometry.py`.
    3. **Bank** -- rotate `(right1, up1)` by `-bank_deg` about the
       (unaffected) forward axis, completing the transform into the full
       airframe frame.

    `azimuth_deg`/`elevation_deg` are then read off the resulting
    `(forward, right, up)` triple with `atan2`, exactly as `bearing_deg`/
    `elevation_at` read off world coordinates elsewhere in this module.

    Degenerate case: `observer == target` (zero range) returns
    `azimuth_deg=0.0, elevation_deg=0.0` rather than raising -- `atan2(0, 0)`
    is well-defined as `0.0` in Python, so this is really just documenting
    the behaviour, not adding a special case."""
    delta_x = target.x - observer.x
    delta_z = target.z - observer.z
    delta_alt = target.alt_m - observer.alt_m

    north = delta_x
    east = delta_z
    up = delta_alt

    heading_rad = math.radians(heading_true_deg)
    pitch_rad = math.radians(pitch_deg)
    bank_rad = math.radians(bank_deg)

    # Step 1: remove yaw (heading).
    forward0 = north * math.cos(heading_rad) + east * math.sin(heading_rad)
    right0 = -north * math.sin(heading_rad) + east * math.cos(heading_rad)
    up0 = up

    # Step 2: remove pitch.
    forward1 = forward0 * math.cos(pitch_rad) + up0 * math.sin(pitch_rad)
    up1 = -forward0 * math.sin(pitch_rad) + up0 * math.cos(pitch_rad)
    right1 = right0

    # Step 3: remove bank.
    right2 = right1 * math.cos(bank_rad) - up1 * math.sin(bank_rad)
    up2 = right1 * math.sin(bank_rad) + up1 * math.cos(bank_rad)

    azimuth_deg = math.degrees(math.atan2(right2, forward1))
    elevation_deg = math.degrees(math.atan2(up2, math.hypot(forward1, right2)))
    return BodyRelativeDirection(azimuth_deg=azimuth_deg, elevation_deg=elevation_deg)


def elevation_at(
    conn: sqlite3.Connection, theatre: str, x: float, z: float
) -> float | None:
    """DCS terrain elevation (metres MSL) at `(x, z)`, via world-model's
    `query.describe_position`. `None` means "unavailable" -- absence
    reported as absence, matching `describe_position`'s own rule -- never a
    fabricated default (e.g. sea level)."""
    return describe_position(conn, theatre, x, z).elevation.dcs_m


def line_of_sight_clear(
    conn: sqlite3.Connection,
    theatre: str,
    observer: GeoPosition,
    target: GeoPosition,
    *,
    samples: int = _DEFAULT_LOS_SAMPLES,
) -> bool:
    """Whether the straight sightline from `observer` to `target` is clear
    of terrain, per world-model's elevation grid.

    Thin wrapper around `query.line_of_sight.line_of_sight_clear` -- unpacks
    this module's own `GeoPosition` observer/target into the bare
    `(x, z, alt_m)` tuples that primitive takes, and returns its result
    unchanged. See that function's docstring for the algorithm itself (the
    sampling loop, absence handling, and why it reads `store.reader.
    sample_grid` directly rather than through `describe_position`).
    """
    return _wm_line_of_sight_clear(
        conn,
        theatre,
        (observer.x, observer.z, observer.alt_m),
        (target.x, target.z, target.alt_m),
        samples=samples,
    )
