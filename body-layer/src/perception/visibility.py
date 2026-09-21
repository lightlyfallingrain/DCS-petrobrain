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

**Binocular premise -- SUPERSEDED, 2026-09-20.** Per the plan's Decision #6
(resolved 2026-09-09, user-affirmed), this filter originally modeled a
crew observer using handheld BINOCULARS *unconditionally*, for every
candidate the cockpit mask admitted, with no field-of-view cost at all --
even though the module, channel, milestone, branch, and research file all
kept the "naked_eye" name throughout (not renamed, per that decision).
**That premise is now recognised as the single biggest source of
over-detection in this channel** (user, 2026-09-20): Petrovich was
permanently glassed-up, seeing binocular magnification across the whole
mask envelope as if he had raised binoculars to look at every single
candidate specifically. Real observation is naked-eye by default.
`check_visibility`'s `optic` parameter defaults to `optics.UNAIDED_OPTIC`,
not `optics.BINOCULAR_OPTIC` -- see that function's own docstring for the
mechanism, and `optics.py`'s module docstring for the full "Naked eye is
now the default" rationale.

**Per-tier multipliers, not one flat figure (slice 2A, `plans/
detection-cones-slice2/plan.md`, `body-layer/research/
2026-09-21-slice2-model-decisions.md` decision 1).** `BINOCULAR_RANGE_
MULTIPLIER` -- the single 4.0 this module used to apply uniformly to all
three recognition-tier thresholds -- is retired. Each `optics.Optic` now
carries three independently-measured multipliers
(`presence_range_mult`/`class_range_mult`/`type_range_mult`), all derived
from the BTR-60 (see `optics.py`'s own docstring for the table and the
"why the BTR-60 alone" reasoning); `UNAIDED_OPTIC` is 1.0 on every tier.
The angular-radius constants below (`LOWRES`/`MEDRES`/`HIRES_ANGULAR_
RADIUS_RAD`) are themselves unchanged by this -- they are the target's own
apparent-size threshold per tier, independent of which optic is looking
through them; only the multiplier that scales each threshold into a range
changed, and it now varies by tier rather than being one number.

**`optics.py`** (`plans/detection-cones-slice1/plan.md`, extended by slice
2A) names both optics this module distinguishes: `UNAIDED_OPTIC` (the
default) and `BINOCULAR_OPTIC` (not the default; carries a real field of
view, not `None`, and its own three per-tier multipliers). The 9K113 sight
is deliberately deferred out of this slice (user, 2026-09-20) -- see
`optics.py`'s own docstring.

Deleting `BINOCULAR_RANGE_MULTIPLIER` also dissolves the real circular
import this module and `optics.py` used to have -- `optics.py` no longer
needs anything from this module, so `Optic`/`UNAIDED_OPTIC`/
`within_optic_fov` are now an ordinary top-level import here, not the
`TYPE_CHECKING`/function-local workaround this docstring used to explain.

Composes five independent plausibility gates over one
`association.WorldObjectCandidate` (reused, not duplicated) against one
`OwnshipState`. All five must pass; failing any one returns `None`
(absence, not a fabricated weak-confidence guess -- deliberately stricter
than `association.py`'s ambiguous-match compromise, since there is no real
detection here to be ambiguous *about*):

0. **Gaze** (`plans/detection-cones-slice2/plan.md`'s 2B, `perception.gaze`)
   -- evaluated **first**, ahead of every other gate. `perception.gaze.
   within_gaze` tests the same body-relative azimuth the cockpit mask below
   also consumes against `gaze`'s wedge; `gaze is None` means "no
   restriction," a true no-op (today's behaviour, and this parameter's
   default). The ordering is load-bearing, not incidental: a bearing
   comparison against a wedge is the cheapest, most selective test
   available, and skipping every downstream gate for a candidate outside
   the current gaze is what makes attention direction *the* optimisation
   rather than a pass added on top of a correct model (plan's hard part
   3) -- the saving only actually lands once something narrower than the
   full envelope is gazed (2C), but the ordering is fixed here so that
   later slice doesn't have to reorder anything. **This does move which
   gate a rear-hemisphere candidate is recorded against once a real gaze
   restriction is active** -- see `detection_trace.py`'s own docstring on
   `GateOutcome.GAZE`.
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
2. **Per-optic field of view** (`plans/detection-cones-slice1/plan.md`) --
   `optics.within_optic_fov` tests the same body-relative direction against
   `optic`'s own (circular) field-of-view half-angle, `None` meaning
   unrestricted. A narrower cone stacked on top of the cockpit mask, not a
   replacement for it -- see `check_visibility`'s own docstring.
3. **Angular-radius recognition-tier range threshold**, replacing an
   invented range-multiplier curve. `HelperAI.lua`'s `min_angular_radius`
   table (`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-
   ambient-detection.md`, Session 5 Finding 3) is ED's own range-by-target-
   size curve, expressed as a threshold angular radius per recognition tier
   rather than a flat range. This module works it backwards into a range
   threshold: `range_threshold = size / NAKED_EYE_GATING_ANGULAR_RADIUS_RAD
   * optic.presence_range_mult`, capped at `NAKED_EYE_RANGE_CAP_M` as a
   sanity bound regardless of what the formula computes for a given
   object's looked-up size -- this project's own derivation from ED's
   published constants, not a verified reproduction of ED's actual formula
   (see the plan's Risks section: the native code also folds in
   `min_contrast_f`/`min_fog_transparency`, which this project has no input
   for). This gate uses `profile.size_m` (see point 4 of the next
   paragraph for why), so it is the exact same threshold as the `lowres`
   tier below -- gate admission and achieving at least `lowres` can never
   disagree.

   **`object_model.apparent_extent_m` is aspect-aware, but only
   `medres`/`hires` use it -- the gate above and the `lowres` tier do
   not** (`plans/aspect-aware-profiles/plan.md`, corrected by
   `body-layer/research/2026-09-21-aspect-magnification-and-
   distinctiveness.md` Finding 1, the same day the aspect-aware branch was
   first merged). A four-instrument BTR-60 measurement found *presence*
   identical at every aspect tested (1.00x ratio, 90 deg vs. 0/20 deg AOB,
   across binoculars and both 9K113 FOV settings) while *class*/*type*
   moved by 1.33x-2.31x with aspect. Physically: detection is a contrast
   event against terrain, driven by presented area regardless of which
   silhouette the object turns; recognition is a shape event and needs the
   shape. So `apparent_extent_m` (real `length_m`/`width_m`/`height_m`
   projected onto the observer's line of sight, using the angle between
   the candidate's heading and the observer-to-candidate bearing --
   `_aspect_deg` below) feeds only `_achieved_tier`'s `medres`/`hires`
   thresholds; the gate here and `_achieved_tier`'s `lowres` threshold use
   the plain, aspect-invariant `profile.size_m` -- see that function's own
   docstring for the full reasoning and why the two size measures must
   stay split, not unified. `apparent_extent_m` falls back to plain
   `profile.size_m` anyway whenever a profile carries no measured
   dimensions (every row except the two S-300 ones migrated so far) or the
   candidate's heading is unknown this tick.
4. **Terrain LOS** -- reuses `geometry.line_of_sight_clear` as-is; the piece
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
from perception.detection_trace import (
    DetectionTrace,
    DetectionTraceCollector,
    GateOutcome,
)
from perception.gaze import Gaze, within_gaze
from perception.geometry import (
    GeoPosition,
    bearing_deg,
    body_relative_direction,
    line_of_sight_clear,
    range_m,
)
from perception.optics import UNAIDED_OPTIC, Optic, within_optic_fov
from perception.source import OwnshipState

#: **Historical derivation, `BINOCULAR_RANGE_MULTIPLIER` itself is retired
#: (slice 2A)** -- these three thresholds were originally derived using
#: `BINOCULAR_RANGE_MULTIPLIER = 4.0` (see the module docstring's "Per-tier
#: multipliers" note for why that single constant was replaced by
#: `optics.Optic`'s three per-tier multipliers). The worked examples below
#: still use `* 4` because that is the arithmetic that actually produced
#: these three angular-radius values on 2026-09-17 -- they are unchanged by
#: slice 2A and do not need re-deriving; only the multiplier applied to
#: them at query time changed, and it is now per-tier rather than one
#: constant. `tests/test_vision_calibration.py` checks the values directly.
#:
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


def _aspect_deg(
    candidate_heading_true_deg: float | None, candidate_bearing_deg: float
) -> float | None:
    """The angle between the candidate's heading and the observer-to-
    candidate bearing, wrapped to `[0, 180]` -- 0 deg means the candidate is
    viewed from directly ahead or astern (its heading is aligned with, or
    opposite to, the line of sight), 90 deg means broadside
    (`plans/aspect-aware-profiles/plan.md`'s "The formula" section).
    `None` whenever the candidate's heading is unknown this tick
    (`WorldObjectCandidate.heading_true_deg`'s tri-state contract) -- never
    guessed, since a wrong guess here would fabricate a specific aspect
    `object_model.apparent_extent_m` would then silently trust."""
    if candidate_heading_true_deg is None:
        return None
    delta = (candidate_heading_true_deg - candidate_bearing_deg + 180.0) % 360.0 - 180.0
    return abs(delta)


def _achieved_tier(
    range_m: float,
    presence_size_m: float,
    recognition_extent_m: float,
    optic: Optic = UNAIDED_OPTIC,
    distinctiveness: float = 1.0,
) -> tuple[str, float]:
    """The tightest recognition tier `range_m` still satisfies, and that
    tier's confidence (Stage 6's worked table: presence low / class medium
    / type high).

    **Slice 2A (`plans/detection-cones-slice2/plan.md`) replaces the old
    single `magnification` with `optic`'s three per-tier multipliers, and
    adds `distinctiveness` -- the clamp (decisions doc decision 3) that is
    this model's main evidence for infantry and radar dishes:**

        presence = presence_size_m / LOWRES_ANGULAR_RADIUS_RAD * optic.presence_range_mult
        class    = min(presence, recognition_extent_m / MEDRES_ANGULAR_RADIUS_RAD
                                  * optic.class_range_mult * distinctiveness)
        type     = min(class, recognition_extent_m / HIRES_ANGULAR_RADIUS_RAD
                               * optic.type_range_mult)

    Each threshold is chained through `min()` against the tier above it
    (and, for `presence`, against `NAKED_EYE_RANGE_CAP_M`) rather than
    capped independently -- this is what makes tier monotonicity
    (`type <= class <= presence`) a structural guarantee rather than
    something that has to be separately checked and clamped: a distinctive
    object's raw class/type figure can run past its own presence range
    (an infantryman classifies as easily as he is detected), and chaining
    the `min()`s is what stops that from inverting the ladder.
    `distinctiveness` deliberately does **not** appear in the `type`
    threshold -- measured 0.2 km infantry type range against 0.6 km
    presence is a third, not equal, so a specific-type identification
    still needs resolved detail that a distinctive silhouette alone does
    not buy (see the decisions doc's "one row does not fit" note for the
    one measurement this still doesn't explain).

    **Two different size measures, deliberately, per `body-layer/research/
    2026-09-21-aspect-magnification-and-distinctiveness.md` Finding 1 --
    do not unify them.** A same-day, four-instrument BTR-60 measurement
    found presence identical at every aspect tested (1.00x ratio, 90 deg
    vs. 0/20 deg AOB, in all three instruments) while class/type moved
    1.33x-2.31x. Physically: detection is a contrast event against terrain,
    driven by presented area, not by which silhouette the object happens to
    turn; recognition is a shape event and needs the shape. So:

    - `presence_size_m` (aspect-invariant, `profile.size_m`) drives the
      `presence` threshold above -- and must be the exact same value
      `check_visibility`'s own range-admission gate uses, so a candidate
      can never be admitted by the gate and then fail to achieve even
      `lowres` here, or the reverse. This is why the `presence` threshold
      is computed explicitly below rather than left as an implicit
      "anything that reaches this point" fallback: an explicit,
      self-contained computation is the only way this function can't
      silently drift out of sync with the gate's own arithmetic if either
      is edited later.
    - `recognition_extent_m` (aspect-aware, `object_model.apparent_extent_m`)
      drives `class`/`type` -- where the measured aspect effect actually
      belongs.

    The final fallback return (range beyond even the `lowres` threshold) is
    unreachable from `check_visibility` -- its own gate already drops
    anything beyond that exact threshold before calling this function --
    but is kept as an explicit, best-effort `lowres` result rather than a
    crash, since `test_vision_calibration.py` calls this function directly
    against screenshot ground truth without going through that gate."""
    presence_threshold_m = min(
        NAKED_EYE_RANGE_CAP_M,
        (presence_size_m / LOWRES_ANGULAR_RADIUS_RAD) * optic.presence_range_mult,
    )
    class_threshold_m = min(
        presence_threshold_m,
        (recognition_extent_m / MEDRES_ANGULAR_RADIUS_RAD)
        * optic.class_range_mult
        * distinctiveness,
    )
    type_threshold_m = min(
        class_threshold_m,
        (recognition_extent_m / HIRES_ANGULAR_RADIUS_RAD) * optic.type_range_mult,
    )
    if range_m <= type_threshold_m:
        return "hires", NAKED_EYE_TYPE_CONFIDENCE
    if range_m <= class_threshold_m:
        return "medres", NAKED_EYE_VISIBILITY_CONFIDENCE
    if range_m <= presence_threshold_m:
        return "lowres", NAKED_EYE_PRESENCE_CONFIDENCE
    # Beyond even the presence threshold -- unreachable from
    # check_visibility itself (its own gate already dropped this candidate
    # at the identical presence_size_m-derived threshold before calling
    # this function), but test_vision_calibration.py calls this function
    # directly against screenshot ground truth without going through that
    # gate. Explicit best-effort fallback rather than a crash, matching
    # this function's pre-existing contract of always returning a tier.
    return "lowres", NAKED_EYE_PRESENCE_CONFIDENCE


def check_visibility(
    ownship: OwnshipState,
    candidate: WorldObjectCandidate,
    conn: sqlite3.Connection,
    theatre: str,
    *,
    optic: Optic | None = None,
    gaze: Gaze | None = None,
    trace: DetectionTraceCollector | None = None,
) -> VisibilityResult | None:
    """Run `candidate` through all five gates: gaze, cockpit mask, per-optic
    field of view (`plans/detection-cones-slice1/plan.md`), angular-radius
    range, terrain LOS (see module docstring for all but the first).
    Returns `None` on the first failing gate -- cheap geometric checks
    (gaze, cockpit mask, FOV, angular-radius range) before the expensive
    LOS terrain-sampling check, mirroring `association.associate()`'s own
    cheap-before-expensive ordering; gaze goes first among the cheap ones
    (module docstring, gate 0).

    `gaze` (`plans/detection-cones-slice2/plan.md`'s 2B) defaults to `None`
    -- no restriction, today's behaviour. A caller resolves the effective
    per-candidate gaze *before* calling this function (`perception.gaze.
    gaze_for`, which also implements the peripheral-stimulus bypass) --
    this function only ever applies whatever `Gaze | None` it is handed.
    `gaze.center_azimuth_deg` (or `0.0` if `gaze is None`) also becomes the
    boresight `within_optic_fov` is tested against below -- an optic is
    pointed by the head, not bolted to the airframe (`optics.py`'s own
    docstring), so the optic FOV cone follows wherever the gaze is
    currently centred.

    `optic` defaults to `optics.UNAIDED_OPTIC`, as of 2026-09-20 -- this
    was `BINOCULAR_OPTIC` for most of that slice's development but is now
    naked-eye by default (module docstring's superseded "Binocular premise"
    section has the full reasoning: modelling Petrovich as permanently
    glassed-up, with binocular magnification and no field-of-view cost
    across the whole cockpit-mask envelope, was the single biggest source
    of over-detection in this channel). Accepted as `None` and resolved
    inside this function rather than as a literal `Optic = UNAIDED_OPTIC`
    default expression -- kept this way for continuity with that history
    even though the circular import that originally forced it is gone as
    of slice 2A (module docstring): `optics.py` no longer imports anything
    from this module, so `Optic`/`UNAIDED_OPTIC`/`within_optic_fov` are now
    an ordinary top-level import here. Behaviourally identical either way:
    calling `check_visibility(...)` with no `optic` argument is the same as
    passing `UNAIDED_OPTIC` explicitly, which is what the regression test
    below actually pins.

    The FOV gate is a new cone on top of the cockpit mask, not a
    replacement for it -- an optic can only narrow what the mask already
    admits. For `UNAIDED_OPTIC` (`fov_half_angle_deg is None`)
    `within_optic_fov` always passes, so the gate is a no-op for the
    default path. `BINOCULAR_OPTIC` now carries a real field-of-view value
    (`optics.py`'s own docstring), but is not wired into any concrete
    `PerceptionSource` yet -- passing it is possible today only by an
    explicit caller, none of which exist.

    `trace` (`perception.detection_trace`, BL-9) is additive and defaults
    to `None` -- a true no-op, same pattern `overlay_client`/`speech_client`
    already use elsewhere in this codebase. When set, records exactly one
    `DetectionTrace` entry per call, at whichever gate decided this
    candidate's fate (or `ADMITTED` if it cleared all four) -- see that
    module's docstring for why `range_threshold_m`/`threshold_bound` are
    always populated regardless of which gate fired. No change to this
    function's existing return value or gate order.

    **Merge note (2026-09-20).** BL-9 and cones slice 1 were developed in
    parallel and their interaction produced two defects that neither
    branch's own tests could see, both fixed here. First, BL-9 computed the
    traced `range_threshold_m` with `BINOCULAR_RANGE_MULTIPLIER` hardcoded;
    once the default optic became the naked eye that would have made every
    trace row report a threshold 4x larger than the one actually applied --
    the trace silently misreporting the exact quantity it exists to measure.
    It now uses `optic.presence_range_mult` (slice 2A renamed the constant
    it originally used, `optic.magnification`, into three per-tier
    multipliers -- the gate/trace use the presence one, same as the
    admission gate below), so the traced threshold is by construction the
    one the gate used. Second, the FOV gate returned without recording,
    which would have broken BL-9's one-entry-per-call invariant the moment
    slice 2 wires a non-default optic; `GateOutcome` gained `OPTIC_FOV` and
    the gate now records like every other."""
    if optic is None:
        optic = UNAIDED_OPTIC

    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    target = GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)

    candidate_bearing_deg = bearing_deg(observer, target)
    candidate_range_m = range_m(observer, target)
    profile = object_model.profile_for(candidate.object_type)
    aspect_deg = _aspect_deg(candidate.heading_true_deg, candidate_bearing_deg)
    recognition_extent_m = object_model.apparent_extent_m(profile, aspect_deg)
    # The range-admission gate (and, below, the lowres/presence tier) use
    # the aspect-INVARIANT profile.size_m, not the aspect-aware extent
    # above -- `body-layer/research/2026-09-21-aspect-magnification-and-
    # distinctiveness.md` Finding 1 measured presence identical at every
    # aspect (1.00x ratio across three instruments), while only class/type
    # moved with aspect. See `_achieved_tier`'s own docstring for the full
    # reasoning; the two size measures must not be unified.
    size_curve_threshold_m = (
        profile.size_m / NAKED_EYE_GATING_ANGULAR_RADIUS_RAD
    ) * optic.presence_range_mult
    range_threshold_m = min(NAKED_EYE_RANGE_CAP_M, size_curve_threshold_m)
    threshold_bound = (
        "range_cap" if NAKED_EYE_RANGE_CAP_M <= size_curve_threshold_m else "size_curve"
    )

    def _record(outcome: GateOutcome, achieved_tier: str | None = None) -> None:
        if trace is None:
            return
        trace.record(
            DetectionTrace(
                object_id=candidate.object_id,
                object_type=candidate.object_type,
                t_sim=ownship.t_sim,
                true_bearing_deg=candidate_bearing_deg,
                true_range_m=candidate_range_m,
                range_threshold_m=range_threshold_m,
                threshold_bound=threshold_bound,
                outcome=outcome,
                achieved_tier=achieved_tier,
            )
        )

    body_direction = body_relative_direction(
        observer,
        target,
        heading_true_deg=ownship.heading_true_deg,
        pitch_deg=ownship.pitch_deg,
        bank_deg=ownship.bank_deg,
    )

    if gaze is not None and not within_gaze(gaze, body_direction.azimuth_deg):
        _record(GateOutcome.GAZE)
        return None

    co_pilot_mask = COCKPIT_MASKS[STATION_CO_PILOT]
    if not is_visible(
        co_pilot_mask, body_direction.azimuth_deg, body_direction.elevation_deg
    ):
        _record(GateOutcome.COCKPIT_MASK)
        return None

    boresight_azimuth_deg = gaze.center_azimuth_deg if gaze is not None else 0.0
    if not within_optic_fov(
        optic,
        boresight_azimuth_deg,
        body_direction.azimuth_deg,
        body_direction.elevation_deg,
    ):
        _record(GateOutcome.OPTIC_FOV)
        return None

    if candidate_range_m > range_threshold_m:
        _record(GateOutcome.RANGE_OR_SIZE)
        return None

    if not line_of_sight_clear(conn, theatre, observer, target):
        _record(GateOutcome.TERRAIN_LOS)
        return None

    achieved_tier, achieved_confidence = _achieved_tier(
        candidate_range_m,
        profile.size_m,
        recognition_extent_m,
        optic,
        object_model.distinctiveness_of(profile),
    )
    _record(GateOutcome.ADMITTED, achieved_tier=achieved_tier)
    return VisibilityResult(
        bearing_deg=candidate_bearing_deg,
        range_m=candidate_range_m,
        tier=achieved_tier,
        confidence=achieved_confidence,
    )
