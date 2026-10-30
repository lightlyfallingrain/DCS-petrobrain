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


def signed_angular_delta_deg(from_deg: float, to_deg: float) -> float:
    """Signed angular delta from `from_deg` to `to_deg`, in `(-180, 180]`,
    positive clockwise -- `angular_delta_deg`'s signed sibling
    (`plans/attack-run/plan.md` Decision 6). `angular_delta_deg` above
    answers "how far apart" (always non-negative, direction discarded);
    this answers "which way and how far" -- `step`'s own ordering primitive
    needs the sign to tell `step left` from `step right`, and the
    change-driven emit rule (`attack_run.AttackRunState`) needs the sign to
    compare a *direction* of error against the last spoken one, not just
    its magnitude."""
    diff = (to_deg - from_deg) % 360.0
    return diff - 360.0 if diff > 180.0 else diff


def range_m(observer: GeoPosition, target: GeoPosition) -> float:
    """Straight-line (slant) range from `observer` to `target`, metres.
    Includes the altitude component -- ground range alone would understate
    range for anything but a level shot, and nothing in either tier's design
    needs ground range specifically."""
    delta_x = target.x - observer.x
    delta_z = target.z - observer.z
    delta_alt = target.alt_m - observer.alt_m
    return math.sqrt(delta_x * delta_x + delta_z * delta_z + delta_alt * delta_alt)


def horizontal_range_m(observer: GeoPosition, target: GeoPosition) -> float:
    """Ground (horizontal) range from `observer` to `target`, metres --
    `range_m`'s altitude-excluding sibling. `plans/
    bl-b104-ground-contacts-on-ground/plan.md` Decision 3: reported range
    stays slant (`range_m`), but a surface percept's range model and the
    belief-truth log's position-error comparison both need the horizontal
    quantity, not conflated with altitude the way a flat-model slant range
    always was."""
    delta_x = target.x - observer.x
    delta_z = target.z - observer.z
    return math.hypot(delta_x, delta_z)


def elevation_deg(observer: GeoPosition, target: GeoPosition) -> float:
    """World-horizon-relative elevation from `observer` to `target`,
    degrees, positive up -- pitch/bank independent by construction (a pure
    function of the two positions' altitudes and horizontal separation).
    `plans/pov-view/plan.md` (`BL-B99`): the forward POV debug view's
    elevation axis, and `DetectionTrace.true_elevation_deg`, both read
    this value unconverted, since it is already the frame they want."""
    delta_alt = target.alt_m - observer.alt_m
    horizontal_m = math.hypot(target.x - observer.x, target.z - observer.z)
    return math.degrees(math.atan2(delta_alt, horizontal_m))


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

    **This flat convention now applies to air contacts alone**
    (`plans/bl-b104-ground-contacts-on-ground/plan.md` Decision 4): a
    surface contact's altitude is replaced immediately after this call
    (`belief.association_over_time.implied_position`, from `Percept.
    surface_alt_m`), so for a ground unit this function's own "observer's
    own altitude" assumption is a transient value, corrected before
    anything reads it.

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


def alignment_direction(
    observer: GeoPosition,
    target: GeoPosition,
    *,
    heading_true_deg: float,
    pitch_deg: float,
) -> BodyRelativeDirection:
    """`body_relative_direction` called with `bank_deg=0.0` -- attack-run
    guidance's own named wrapper (`plans/attack-run/plan.md` Decision 3).

    **The zero is the whole implementation, and naming it here is the
    point.** Rolling in at 45 degrees of bank, the full airframe frame
    mixes azimuth and elevation -- at 90 degrees of bank a target dead
    ahead and low reads as a pure *azimuth* error, and the guidance would
    say "come left" when the pilot needs to pull. With bank removed,
    `azimuth_deg` is a **heading** error ("come left" = turn) and
    `elevation_deg` is a **pitch** error ("higher" = pull), which are the
    pilot's two controls -- `body_relative_direction`'s steps 1-2 (yaw,
    pitch) are exactly that decomposition; step 3 (bank) is skipped by
    fixing this one argument, rather than re-deriving the rotation here.
    A bare `body_relative_direction(..., bank_deg=0.0)` call site would
    read as a forgotten argument to the next reader; this name says it is
    deliberate."""
    return body_relative_direction(
        observer,
        target,
        heading_true_deg=heading_true_deg,
        pitch_deg=pitch_deg,
        bank_deg=0.0,
    )


def heading_relative_to_body_relative(
    azimuth_heading_deg: float,
    elevation_heading_deg: float,
    *,
    heading_true_deg: float,
    pitch_deg: float,
    bank_deg: float,
) -> BodyRelativeDirection:
    """Rotate a *heading*-relative direction -- azimuth already relative to
    the aircraft's heading, elevation the depression below the
    world-horizontal plane -- into the true body-relative frame
    `within_field_of_regard` and `within_optic_fov` both expect.

    **F5** (`docs/acceptance/2026-10-20-sortie-feedback.md`): the 9K113's
    mechanical limits are relative to the airframe's own boresight, not to
    the ground -- *"nose low position at high altitude would allow a near
    scan... it is not about distance, but angles relative to boresight"*;
    *"the limits are the mechanical rotation limits around aircraft axis.
    When aircraft rotates, so do the coordinate axis."* `belief.optic_
    policy.search_pattern` has no notion of pitch or bank at all (its
    elevation is pure `atan2(altitude_agl_m, range_m)`), so its steps are
    ground-anchored and level-flight-only; this is the conversion that
    makes them usable as a body-relative aim or regard check.

    **Reuses `body_relative_direction` rather than re-deriving its pitch/
    bank rotation.** A unit-range synthetic target is placed at
    `(azimuth_heading_deg, elevation_heading_deg)` in the *heading* frame
    (yaw already removed, exactly as `search_pattern`'s own inputs are),
    then rotated back out to world north/east with `heading_true_deg` --
    the algebraic inverse of `body_relative_direction`'s own yaw-removal
    step. Handing that synthetic target to `body_relative_direction` with
    the *same* `heading_true_deg` cancels the yaw exactly, leaving only the
    pitch/bank rotation that function already implements -- so a future
    change to that rotation (or to its sign conventions) only has one place
    to be made correctly."""
    azimuth_rad = math.radians(azimuth_heading_deg)
    elevation_rad = math.radians(elevation_heading_deg)
    forward = math.cos(elevation_rad) * math.cos(azimuth_rad)
    right = math.cos(elevation_rad) * math.sin(azimuth_rad)
    up = math.sin(elevation_rad)

    heading_rad = math.radians(heading_true_deg)
    north = forward * math.cos(heading_rad) - right * math.sin(heading_rad)
    east = forward * math.sin(heading_rad) + right * math.cos(heading_rad)

    origin = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    target = GeoPosition(x=north, z=east, alt_m=up)
    return body_relative_direction(
        origin,
        target,
        heading_true_deg=heading_true_deg,
        pitch_deg=pitch_deg,
        bank_deg=bank_deg,
    )


def world_direction_from_body(
    body_azimuth_deg: float,
    body_elevation_deg: float,
    *,
    heading_true_deg: float,
    pitch_deg: float,
    bank_deg: float,
) -> tuple[float, float]:
    """Inverse of `body_relative_direction`'s rotation (`[[BL-B80]]`,
    `plans/9k113-sight-pointing/plan.md`, "Simulated head" -- the
    `SightHead`'s own frame conversion): given a direction already
    expressed in the airframe's body frame (`BodyRelativeDirection`'s own
    sign convention), returns the equivalent world-true direction --
    `(azimuth_true_deg` in `[0, 360)`, `elevation_deg` above the
    world-horizontal plane`)` -- at the given attitude.

    **Built on `body_relative_direction`, not a separate derivation**, the
    same construction `heading_relative_to_body_relative` uses for its own
    inverse-of-the-yaw-step case: a unit-range vector is built directly in
    the body frame from `body_azimuth_deg`/`body_elevation_deg`, then each
    of `body_relative_direction`'s three rotation steps (yaw, pitch, bank)
    is undone in the reverse order it applies them (bank, pitch, yaw) --
    each step's inverse is its transpose, since every one of these is an
    orthonormal rotation. A future change to `body_relative_direction`'s
    rotation (or its sign conventions) is undone here by the same
    transpose relationship, not by an independent re-derivation that could
    drift out of step with it."""
    az_rad = math.radians(body_azimuth_deg)
    el_rad = math.radians(body_elevation_deg)
    forward1 = math.cos(el_rad) * math.cos(az_rad)
    right2 = math.cos(el_rad) * math.sin(az_rad)
    up2 = math.sin(el_rad)

    bank_rad = math.radians(bank_deg)
    # Undo step 3 (bank): the transpose of `body_relative_direction`'s own
    # right1/up1 -> right2/up2 rotation.
    right1 = right2 * math.cos(bank_rad) + up2 * math.sin(bank_rad)
    up1 = -right2 * math.sin(bank_rad) + up2 * math.cos(bank_rad)

    pitch_rad = math.radians(pitch_deg)
    # Undo step 2 (pitch): the transpose of forward0/up0 -> forward1/up1.
    forward0 = forward1 * math.cos(pitch_rad) - up1 * math.sin(pitch_rad)
    up0 = forward1 * math.sin(pitch_rad) + up1 * math.cos(pitch_rad)
    right0 = right1

    heading_rad = math.radians(heading_true_deg)
    # Undo step 1 (yaw): the transpose of north/east -> forward0/right0.
    north = forward0 * math.cos(heading_rad) - right0 * math.sin(heading_rad)
    east = forward0 * math.sin(heading_rad) + right0 * math.cos(heading_rad)
    up = up0

    azimuth_true_deg = math.degrees(math.atan2(east, north)) % 360.0
    elevation_deg = math.degrees(math.atan2(up, math.hypot(north, east)))
    return azimuth_true_deg, elevation_deg


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
