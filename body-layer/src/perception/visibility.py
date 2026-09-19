"""Detectability filter for the naked-eye perception channel --
`plans/pb1.5-naked-eye-detection/plan.md`.

**These constants are a clear-weather, daylight upper bound, not an
average case.** Every screenshot the ladder below was calibrated against
was captured in near-perfect visual conditions, which is the right way to
fix a ceiling and the wrong way to describe a typical sortie. Vegetation,
light level and weather all push real detection *below* these figures,
sometimes to zero -- see `body-layer/ROADMAP.md`, "Detection under real
world conditions", for the factors and why they are expected to compose
as a multiplier on top of this rather than as a replacement for it. A
future conditions term belongs alongside the gates here; the three
angular thresholds themselves should survive it unchanged.

**Binocular premise, stated plainly so a future reader doesn't "correct"
these constants downward.** Per the plan's Decision #6 (resolved
2026-09-09, user-affirmed): this filter models a crew observer using
handheld BINOCULARS, not the unaided/naked eye -- even though the module,
channel, milestone, branch, and research file all keep the "naked_eye"
name (not renamed here, per that decision). `BINOCULAR_RANGE_MULTIPLIER`
below is a deliberate modeling choice for binocular-aided observation, not
a transcription of DCS's own `HelperAI.lua` `extra_eyesight_ratio` tuning
constant -- that constant's real role in ED's native detection formula is
unverified (see the plan's Risks section on `min_contrast_f`/
`min_fog_transparency`/`extra_eyesight_ratio` all being unaddressed here).
The numeric value happens to match `extra_eyesight_ratio` (4.0), but this
project owns the ×4 as "what a crew member sees through binoculars,"
independent of whatever `extra_eyesight_ratio` actually multiplies in DCS's
native code. Do not re-derive the defaults below from an unaided-eye
assumption and "correct" them to be stricter: the screenshot ladder
described under the angular-radius constants below measured *both* the
unaided view and the zoomed/binocular view of the same targets at the same
nine ranges, and they differ by roughly two recognition tiers. This module
is calibrated against the binocular column. Recalibrating it against the
unaided column would not be a correction, it would be a different
instrument -- and the place to model that properly is the deferred
"attention direction and detection cones" milestone, which owns the
per-optic split (see `body-layer/ROADMAP.md`).

The multiplier survived calibration unchanged, which is itself a result
worth keeping: reading the ladder as apparent angular size (true angular
size x magnification) makes the unaided and binocular columns land on the
*same* tier thresholds, with the optic supplying only the magnification.
That is why retuning the three angular constants below was enough, and no
per-optic curve had to be introduced here.

Composes three independent plausibility gates over one
`association.WorldObjectCandidate` (reused, not duplicated) against one
`OwnshipState`. All three must pass; failing any one returns `None`
(absence, not a fabricated weak-confidence guess -- deliberately stricter
than `association.py`'s ambiguous-match compromise, since there is no real
detection here to be ambiguous *about*):

1. **Cockpit occlusion mask** (`plans/cockpit-visibility/plan.md`,
   superseding the old flat `NAKED_EYE_FOV_HALF_WIDTH_DEG` azimuth cone --
   see below) -- `perception.geometry.body_relative_direction` rotates the
   candidate's direction out of world-horizontal and into the airframe's
   own frame (heading, pitch, bank all applied), then
   `perception.cockpit_mask.is_visible` tests it against Petrovich's
   station's maximum-depression-per-azimuth table plus a hard rear cutoff.
   Orthogonal to the angular-radius check below: look-direction
   plausibility, not detectability range.

   **Not the same gate PB-1.5 shipped.** The old `_within_fov` was a single
   azimuth cone off ownship *heading* with no elevation term at all -- a
   contact 90 m below and 60 deg off the nose passed exactly as easily as
   one on the horizon, which meant Petrovich could report contacts through
   the fuselage and the floor. It was also parameterized by the wrong
   instrument: `NAKED_EYE_FOV_HALF_WIDTH_DEG = 60.0` was the 9K113 sight's
   angular limit (user, 2026-09-16), not anything established about a human
   looking through cockpit glass -- see `todo/todo.md`'s entry on this. Both
   defects are fixed by the same replacement: a body-relative depression
   mask naturally bounds "how far down can he see" as a function of
   azimuth, which a heading-only cone structurally cannot express.
2. **Angular-radius recognition-tier range threshold**, replacing an
   invented range-multiplier curve. `HelperAI.lua`'s `min_angular_radius`
   table (`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-
   ambient-detection.md`, Session 5 Finding 3) is ED's own range-by-target-
   size curve, expressed as a threshold angular radius per recognition tier
   rather than a flat range. This module works it backwards into a range
   threshold: `range_threshold = object_model.size_m(object_type) /
   NAKED_EYE_GATING_ANGULAR_RADIUS_RAD * BINOCULAR_RANGE_MULTIPLIER`, capped
   at `NAKED_EYE_RANGE_CAP_M` as a sanity bound
   regardless of what the formula computes for a given object's looked-up
   size -- this project's own derivation from ED's published constants, not
   a verified reproduction of ED's actual formula (see the plan's Risks
   section: the native code also folds in `min_contrast_f`/
   `min_fog_transparency`, which this project has no input for).
3. **Terrain LOS** -- reuses `geometry.line_of_sight_clear` as-is; the piece
   `geometry.py`'s own docstring already anticipated needing ("turning
   'clear line of sight' into an actual detectability decision... [is] a
   concrete tier's job... not this shared helper's").

Pure aside from the LOS gate's `sqlite3.Connection` (the world-model seam,
mirroring `geometry.py`'s own posture) -- no network I/O.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Final

from perception import object_model
from perception.association import WorldObjectCandidate
from perception.cockpit_mask import COCKPIT_MASKS, STATION_CO_PILOT, is_visible
from perception.geometry import (
    GeoPosition,
    bearing_deg,
    body_relative_direction,
    line_of_sight_clear,
    range_m,
)
from perception.source import OwnshipState

#: Apparent-angular-radius thresholds (radians) per recognition tier,
#: **calibrated 2026-09-17 against real in-game screenshots** -- see
#: `body-layer/research/2026-09-17-vision-range-calibration-pass2.md` and
#: `tests/fixtures/vision_calibration.json`'s `png-2026-09-17` records.
#: `lowres` is bare existence ("something is there," no class implied);
#: `medres`/`hires` are the classification tiers; `iff` is friend/foe
#: discrimination.
#:
#: **These are no longer `HelperAI.lua`'s `min_angular_radius` values.**
#: They started as that table (0.0043 / 0.008 / 0.02, Session 5 Finding 3
#: of `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-
#: ambient-detection.md`), read backwards into a range threshold by this
#: project. A nine-range screenshot ladder (503 m to 8.89 km, flat desert,
#: clear, four optics per range) showed all three were wrong, and wrong in
#: *both* directions: the classification tiers were far too generous while
#: the presence tier was too strict. Each value below is now derived from
#: the observed tier boundary for a 7 m armored vehicle, using this
#: module's own `size / threshold * BINOCULAR_RANGE_MULTIPLIER` formula:
#:
#: * `medres` -- class first resolved at 1990 m, not at 2990 m:
#:   `7 / 1990 * 4 = 0.0141`. The old 0.008 implied class out to 3.5 km,
#:   ~1.8x further than observed.
#: * `hires` -- type first resolved at 1000 m, not at 1500 m:
#:   `7 / 1000 * 4 = 0.028`. The old 0.02 implied type out to 1.4 km.
#: * `lowres` -- presence was still unmistakable at 8.89 km, the farthest
#:   range photographed, so this is an *upper bound* on the threshold, not
#:   a measured boundary: `7 / 8890 * 4 = 0.00315`, rounded to 0.003
#:   (9333 m for a 7 m object). The old 0.0043 cut presence off at 6.5 km,
#:   inside the range where the ladder shows a clear row of contacts.
#:   **The real presence limit is further out than anything tested** -- a
#:   longer ladder would push this down again.
LOWRES_ANGULAR_RADIUS_RAD: Final[float] = 0.003
MEDRES_ANGULAR_RADIUS_RAD: Final[float] = 0.014
HIRES_ANGULAR_RADIUS_RAD: Final[float] = 0.028
#: Not used by this module -- friend/foe discrimination is out of scope
#: (plan Risks, "no coalition/IFF filtering"). Named anyway so the full
#: `min_angular_radius` table is visible in one place.
IFF_ANGULAR_RADIUS_RAD: Final[float] = 0.025

#: The tier this filter gates on. `lowres` over `medres`
#: (`plans/classification-refinement/plan.md` Stage 7, Decision 2, the
#: user-approved calibration change): the channel's *output* no longer
#: needs to honestly support a class claim at the gate itself, because
#: Stage 6 made classification a computed function of the achieved tier --
#: a `lowres`-only detection now emits `object_model.DEFAULT_OP_CLASS` at
#: level 1 (presence, "something is there"), not a fabricated class guess.
#: This widens the detection envelope ~1.86x range (~3.5x area) and is the
#: anti-omniscience calibration move: Petrovich now notices more, further
#: out, and says less about it until it closes. One-line revert: restore
#: `MEDRES_ANGULAR_RADIUS_RAD` / `"medres"` here.
NAKED_EYE_GATING_ANGULAR_RADIUS_RAD: Final[float] = LOWRES_ANGULAR_RADIUS_RAD
NAKED_EYE_GATING_TIER_NAME: Final[str] = "lowres"

#: See the module docstring's binocular premise. Same numeric value as
#: `HelperAI.lua`'s `extra_eyesight_ratio`, reinterpreted and owned by this
#: project as binocular magnification, not a transcription of that
#: constant's (unverified) native role.
BINOCULAR_RANGE_MULTIPLIER: Final[float] = 4.0

#: Outer range bound, applied regardless of what the angular-radius formula
#: computes for a given object's looked-up size, so a very large object
#: (e.g. a ship, ~28 km from the formula alone) can't produce an absurd
#: detection range.
#:
#: **Not** ED's `scan_rad_around_point` (2500 m), which this was until the
#: 2026-09-09 live probe. That value made the cap the dominant term rather
#: than a sanity bound -- it bound *every* ground vehicle, so the
#: angular-radius size curve had no effect at all below it, defeating the
#: point of deriving from ED's model. The probe also found Petrovich
#: detecting units the F10 map placed beyond 2500 m, and the pilot observed
#: seeing targets on screen well before any contact report
#: (`aircraft-layer/research/2026-09-09-pb15-ambient-callout-live-probe.md`,
#: Finding 5). Raised to match `association.RANGE_CAP_M`, so neither
#: detection channel is bounded tighter than the other for no reason.
#:
#: **Raised 5000 -> 10000 on 2026-09-17** by the screenshot calibration.
#: 5000 was the "raise it, we'll fine-tune later" placeholder; the ladder
#: then showed a row of ground vehicles plainly visible at 8.89 km, so a
#: 5 km cap was actively suppressing detections the player can see -- the
#: exact failure the no-omniscience invariant runs in reverse ("if the
#: player can see a unit, Petrovich should too"). 10000 keeps this a sanity
#: bound on the formula's output for very large objects (a ship computes
#: ~133 km from the angular-radius curve alone) without clipping anything
#: the ladder actually measured.
#:
#: Still not a measured limit: nothing was photographed beyond 8.89 km, so
#: whether real DCS visibility ends at 10 km, 15 km, or further is unknown.
#: With the calibrated `lowres` threshold a 7 m vehicle reaches 9333 m from
#: the formula, just inside this cap -- so for ordinary ground vehicles the
#: size curve still does the discriminating and the cap binds only ships
#: and other outsized objects.
#:
#: Note this no longer matches `association.RANGE_CAP_M` (5000). The two
#: were aligned when both were guesses; this one now has data behind it and
#: the other does not, so they are deliberately decoupled rather than
#: dragged along together.
NAKED_EYE_RANGE_CAP_M: Final[float] = 10000.0

#: A filter pass here is structurally weaker evidence than a real HelperAI
#: detection (`association.CONFIDENT_ASSOCIATION_CONFIDENCE = 0.6`) -- there
#: is no real detection-existence signal behind this channel at all, only an
#: ED-model-grounded plausibility filter (plan Invariant Check). Deliberately
#: capped below that value, at every achieved tier (see the three constants
#: below) -- even a `hires`-tier naked-eye pass is still just a visibility
#: filter, never a real detection-existence signal.
#:
#: `plans/classification-refinement/plan.md` Stage 6's worked confidence
#: table: presence (low) / class (medium) / type (high). This constant is
#: the `medres`/class-tier value, kept under its original name since every
#: existing caller and test already refers to it that way; the other two
#: tiers get their own constants immediately below.
NAKED_EYE_VISIBILITY_CONFIDENCE: Final[float] = 0.4

#: Level-1 (presence) tier confidence -- "something is there," the weakest
#: claim in the lattice. Unreachable until Stage 7 moves the gating tier to
#: `lowres`; declared now because Stage 6's tier-computation mechanism
#: already produces this branch, only the gate keeps it from being returned.
NAKED_EYE_PRESENCE_CONFIDENCE: Final[float] = 0.2

#: Level-3 (type) tier confidence -- the closest, most specific achieved
#: tier. Still below `association.CONFIDENT_ASSOCIATION_CONFIDENCE = 0.6`
#: (see above): a close, clear naked-eye look is still not a real HelperAI
#: detection-existence signal.
NAKED_EYE_TYPE_CONFIDENCE: Final[float] = 0.55


@dataclass(frozen=True, slots=True)
class VisibilityResult:
    """The outcome of a successful `check_visibility()` call -- always
    carries the exact (un-quantised) geometry; `check_visibility()` returns
    `None` instead of this type when any gate fails (see module docstring).
    Output quantisation to ED's ambient-callout vocabulary is
    `naked_eye_source.py`'s job, not this module's -- see that module's
    docstring.

    `tier` and `confidence` are the *achieved* recognition tier
    (`plans/classification-refinement/plan.md` Stage 6), not the flat
    `NAKED_EYE_GATING_TIER_NAME` constant this always returned before: a
    candidate that clears the gate can still resolve closer-in to `hires`
    (and its higher confidence) if it is near enough, independent of what
    tier the gate itself is set to. `naked_eye_source.py` maps `tier` onto a
    lattice level/value; this module only computes the geometry."""

    bearing_deg: float
    range_m: float
    tier: str
    confidence: float


def _achieved_tier(range_m: float, size_m: float) -> tuple[str, float]:
    """The tightest recognition tier `range_m` still satisfies for an object
    of characteristic size `size_m`, and that tier's confidence
    (Stage 6's worked table: presence low / class medium / type high). Each
    tier's threshold is independently capped at `NAKED_EYE_RANGE_CAP_M`, the
    same sanity bound `check_visibility`'s gate applies (module docstring
    gate #2) -- a very large object's `hires`/`medres` thresholds can both
    collapse onto the cap, which is expected, not a bug.

    The `lowres` branch is unreachable while `NAKED_EYE_GATING_ANGULAR_
    RADIUS_RAD` gates at `medres` (Stage 6) -- `check_visibility` already
    drops anything beyond the gating threshold before this function is ever
    called on it. It becomes reachable once Stage 7 moves the gate to
    `lowres`."""
    hires_threshold_m = min(
        NAKED_EYE_RANGE_CAP_M,
        (size_m / HIRES_ANGULAR_RADIUS_RAD) * BINOCULAR_RANGE_MULTIPLIER,
    )
    medres_threshold_m = min(
        NAKED_EYE_RANGE_CAP_M,
        (size_m / MEDRES_ANGULAR_RADIUS_RAD) * BINOCULAR_RANGE_MULTIPLIER,
    )
    if range_m <= hires_threshold_m:
        return "hires", NAKED_EYE_TYPE_CONFIDENCE
    if range_m <= medres_threshold_m:
        return "medres", NAKED_EYE_VISIBILITY_CONFIDENCE
    return "lowres", NAKED_EYE_PRESENCE_CONFIDENCE


def check_visibility(
    ownship: OwnshipState,
    candidate: WorldObjectCandidate,
    conn: sqlite3.Connection,
    theatre: str,
) -> VisibilityResult | None:
    """Run `candidate` through all three gates (see module docstring).
    Returns `None` on the first failing gate -- cheap geometric checks
    (cockpit mask, angular-radius range) before the expensive LOS
    terrain-sampling check, mirroring `association.associate()`'s own
    cheap-before-expensive ordering."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    target = GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)

    candidate_bearing_deg = bearing_deg(observer, target)
    body_direction = body_relative_direction(
        observer,
        target,
        heading_true_deg=ownship.heading_true_deg,
        pitch_deg=ownship.pitch_deg,
        bank_deg=ownship.bank_deg,
    )
    co_pilot_mask = COCKPIT_MASKS[STATION_CO_PILOT]
    if not is_visible(
        co_pilot_mask, body_direction.azimuth_deg, body_direction.elevation_deg
    ):
        return None

    candidate_range_m = range_m(observer, target)
    profile = object_model.profile_for(candidate.object_type)
    range_threshold_m = min(
        NAKED_EYE_RANGE_CAP_M,
        (profile.size_m / NAKED_EYE_GATING_ANGULAR_RADIUS_RAD)
        * BINOCULAR_RANGE_MULTIPLIER,
    )
    if candidate_range_m > range_threshold_m:
        return None

    if not line_of_sight_clear(conn, theatre, observer, target):
        return None

    achieved_tier, achieved_confidence = _achieved_tier(
        candidate_range_m, profile.size_m
    )
    return VisibilityResult(
        bearing_deg=candidate_bearing_deg,
        range_m=candidate_range_m,
        tier=achieved_tier,
        confidence=achieved_confidence,
    )
