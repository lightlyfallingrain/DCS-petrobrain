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
`line_of_sight_clear`'s repeated per-sample elevation reads instead call
`store.reader.sample_grid` directly -- the same primitive
`describe_position.elevation.dcs_m` is itself built on (see
`world-model/src/query/describe.py`'s module docstring), but without also
computing `describe_position`'s unrelated road/settlement/navaid joins on
every one of a LOS sample's dozen-plus points. This is a deliberate,
documented deviation from routing every world-model read through
`describe_position`, not an oversight -- flagged here so a future reader
doesn't assume it should be "fixed" without weighing the redundant-work
cost of the alternative.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from query.describe import describe_position
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

    Samples `samples` interior points along the observer->target ground
    track and compares the straight-sightline altitude at that point against
    the actual terrain elevation there. A sample where world-model has no
    elevation data (`None`) is skipped rather than treated as blocking or
    clear -- absence of data must never manufacture a detection outcome
    either way; it is simply not evidence.

    This is a plain geometric LOS check only -- no earth curvature, no
    atmospheric refraction, no target-size/optical-plausibility reasoning.
    Those, along with turning "clear line of sight" into an actual
    detectability decision, are a concrete tier's job (Tier 3's detectability
    gate, per `plans/pb1-perception-logger/plan.md`'s Invariant Check) -- not
    this shared helper's.
    """
    for i in range(1, samples):
        t = i / samples
        sample_x = observer.x + (target.x - observer.x) * t
        sample_z = observer.z + (target.z - observer.z) * t
        terrain_m = sample_grid(conn, "elevation", sample_x, sample_z)
        if terrain_m is None:
            continue
        sightline_alt_m = observer.alt_m + (target.alt_m - observer.alt_m) * t
        if terrain_m > sightline_alt_m:
            return False
    return True
