"""Detectability filter for the naked-eye perception channel --
`plans/pb1.5-naked-eye-detection/plan.md`.

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
assumption and "correct" them to be stricter -- the resulting infantry
~900 m / truck ~3 km / T-72 ~3.5 km ranges are the intended target
behaviour, confirmed with the user.

Composes three independent plausibility gates over one
`association.WorldObjectCandidate` (reused, not duplicated) against one
`OwnshipState`. All three must pass; failing any one returns `None`
(absence, not a fabricated weak-confidence guess -- deliberately stricter
than `association.py`'s ambiguous-match compromise, since there is no real
detection here to be ambiguous *about*):

1. **FOV cone** -- `NAKED_EYE_FOV_HALF_WIDTH_DEG` off ownship true heading.
   Orthogonal to the angular-radius check below: look-direction
   plausibility, not detectability range.
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
from perception.geometry import GeoPosition, bearing_deg, line_of_sight_clear, range_m
from perception.source import OwnshipState

#: Half-width of the naked-eye scanning arc from ownship true heading,
#: degrees. Narrower than `association.py`'s
#: `FORWARD_HEMISPHERE_HALF_WIDTH_DEG = 90.0` deliberately: Hybrid's window
#: is a loose plausibility backstop behind a real detection-existence gate;
#: this one is the *primary* gate here and should model an actual scanning
#: arc, not just "somewhere plausible."
NAKED_EYE_FOV_HALF_WIDTH_DEG: Final[float] = 60.0

#: `HelperAI.lua`'s `min_angular_radius` table (radians), Session 5 Finding
#: 3. `lowres` is ED's bare-existence threshold ("something is there," no
#: class implied); `medres`/`hires` are classification tiers; `iff` is the
#: friend/foe discrimination tier. All four are carried as named constants
#: so the gating tier is a one-line change, not a redesign, if the default
#: proves too generous or too strict once live-tested.
LOWRES_ANGULAR_RADIUS_RAD: Final[float] = 0.0043
MEDRES_ANGULAR_RADIUS_RAD: Final[float] = 0.008
HIRES_ANGULAR_RADIUS_RAD: Final[float] = 0.02
#: Not used by this module -- friend/foe discrimination is out of scope
#: (plan Risks, "no coalition/IFF filtering"). Named anyway so the full
#: `min_angular_radius` table is visible in one place.
IFF_ANGULAR_RADIUS_RAD: Final[float] = 0.025

#: The tier this filter gates on. `medres` over bare `lowres`: this
#: channel's output includes a coarse class (`object_model.py`'s `op_class`),
#: which `lowres` alone (bare existence, no class implied) would not
#: honestly support -- plan's Proposed Defaults section.
NAKED_EYE_GATING_ANGULAR_RADIUS_RAD: Final[float] = MEDRES_ANGULAR_RADIUS_RAD
NAKED_EYE_GATING_TIER_NAME: Final[str] = "medres"

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
#: With this value the size curve does the discriminating -- infantry ~900 m,
#: truck ~3 km, T-72 ~3.5 km, SA-3 launcher ~4.5 km all fall below the cap --
#: and only ships are capped. Deliberately un-tuned; the user's instruction
#: was "raise it, we'll fine-tune later," so treat it as a starting point to
#: calibrate during live acceptance testing, not a settled number.
NAKED_EYE_RANGE_CAP_M: Final[float] = 5000.0

#: A filter pass here is structurally weaker evidence than a real HelperAI
#: detection (`association.CONFIDENT_ASSOCIATION_CONFIDENCE = 0.6`) -- there
#: is no real detection-existence signal behind this channel at all, only an
#: ED-model-grounded plausibility filter (plan Invariant Check). Deliberately
#: capped below that value.
NAKED_EYE_VISIBILITY_CONFIDENCE: Final[float] = 0.4


@dataclass(frozen=True, slots=True)
class VisibilityResult:
    """The outcome of a successful `check_visibility()` call -- always
    carries the exact (un-quantised) geometry; `check_visibility()` returns
    `None` instead of this type when any gate fails (see module docstring).
    Output quantisation to ED's ambient-callout vocabulary is
    `naked_eye_source.py`'s job, not this module's -- see that module's
    docstring."""

    bearing_deg: float
    range_m: float
    tier: str
    confidence: float


def check_visibility(
    ownship: OwnshipState,
    candidate: WorldObjectCandidate,
    conn: sqlite3.Connection,
    theatre: str,
) -> VisibilityResult | None:
    """Run `candidate` through all three gates (see module docstring).
    Returns `None` on the first failing gate -- cheap geometric checks
    (FOV, angular-radius range) before the expensive LOS terrain-sampling
    check, mirroring `association.associate()`'s own cheap-before-expensive
    ordering."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    target = GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)

    candidate_bearing_deg = bearing_deg(observer, target)
    if not _within_fov(ownship.heading_true_deg, candidate_bearing_deg):
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

    return VisibilityResult(
        bearing_deg=candidate_bearing_deg,
        range_m=candidate_range_m,
        tier=NAKED_EYE_GATING_TIER_NAME,
        confidence=NAKED_EYE_VISIBILITY_CONFIDENCE,
    )


def _within_fov(ownship_heading_deg: float, candidate_bearing_deg: float) -> bool:
    delta = (candidate_bearing_deg - ownship_heading_deg + 180.0) % 360.0 - 180.0
    return abs(delta) <= NAKED_EYE_FOV_HALF_WIDTH_DEG
