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

**Binocular premise -- SUPERSEDED, 2026-09-20, final scope change of this
slice.** Per the plan's Decision #6 (resolved 2026-09-09, user-affirmed),
this filter originally modeled a crew observer using handheld BINOCULARS
*unconditionally*, for every candidate the cockpit mask admitted, with no
field-of-view cost at all -- even though the module, channel, milestone,
branch, and research file all kept the "naked_eye" name throughout
(not renamed, per that decision). **That premise is now recognised as the
single biggest source of over-detection in this channel** (user,
2026-09-20): Petrovich was permanently glassed-up, seeing binocular
magnification across the whole mask envelope as if he had raised
binoculars to look at every single candidate specifically. Real
observation is naked-eye by default. `check_visibility`'s `optic`
parameter now defaults to `optics.UNAIDED_OPTIC` (magnification 1.0), not
`optics.BINOCULAR_OPTIC` -- see that function's own docstring for the
mechanism, and `optics.py`'s module docstring for the full "Naked eye is
now the default" rationale. This paragraph is kept, marked superseded,
because the history matters: it explains why every constant below was
originally tuned against the binocular column, and the angular-radius
constants' own comments still describe that tuning.

**`BINOCULAR_RANGE_MULTIPLIER`'s round trip, stated honestly so a future
reader does not read a random walk back to a familiar number.** The value
below has been, across this one design slice: **4.0** (inherited,
unexamined, from `HelperAI.lua`'s `extra_eyesight_ratio` -- that
constant's real role in ED's native detection formula is unverified, see
the plan's Risks section on `min_contrast_f`/`min_fog_transparency`/
`extra_eyesight_ratio`) -> **8.0** (a same-session excursion: a realistic
8x30 instrument, magnification stated honestly with no hidden derating)
-> **4.0 again (final, current value below).** The final 4.0 is
numerically identical to the first but is a different fact: it is
independently derived from a real Б-6 6x30 (6x magnification) times a
~0.67 penalty for handheld use on a vibrating airframe (`optics.py`'s
`BINOCULAR_OPTIC` docstring has the arithmetic), not the restored
inherited `extra_eyesight_ratio` value. That derivation also happens to
match what the 2026-09-17 screenshot ladder's binocular column
independently shows -- the first time the physical argument and the
photographic evidence have produced the same number without either being
tuned to match the other. **Because both the multiplier and the three
angular-radius constants below are back to the values the 2026-09-17
calibration was run against, that calibration is current again, not
stale** -- `tests/test_vision_calibration.py` asserts this directly
rather than assuming it.

Do not re-derive the angular-radius constants below from an unaided-eye
assumption and "correct" them to be stricter for that reason alone: the
screenshot ladder measured *both* the unaided view and the zoomed/
binocular view of the same targets at the same nine ranges, and they
differ by roughly two recognition tiers at the ladder's own binocular
magnification. Reading the ladder as apparent angular size (true angular
size x magnification) makes the unaided and binocular columns land on the
*same* tier thresholds, with the optic supplying only the magnification --
that is why retuning the three angular constants below was never needed
across any of this slice's changes, only the magnification the formula
multiplies by.

**`optics.py`** (`plans/detection-cones-slice1/plan.md`) names both optics
this module distinguishes: `UNAIDED_OPTIC` (the default as of 2026-09-20)
and `BINOCULAR_OPTIC` (no longer the default; now carries a real field of
view, not `None` -- see that module's own docstring for why that is safe
now and was not before). The 9K113 sight is deliberately deferred out of
this slice (user, 2026-09-20) -- see `optics.py`'s own docstring.

Composes four independent plausibility gates over one
`association.WorldObjectCandidate` (reused, not duplicated) against one
`OwnshipState`. All four must pass; failing any one returns `None`
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
   threshold: `range_threshold = object_model.size_m(object_type) /
   NAKED_EYE_GATING_ANGULAR_RADIUS_RAD * BINOCULAR_RANGE_MULTIPLIER`, capped
   at `NAKED_EYE_RANGE_CAP_M` as a sanity bound
   regardless of what the formula computes for a given object's looked-up
   size -- this project's own derivation from ED's published constants, not
   a verified reproduction of ED's actual formula (see the plan's Risks
   section: the native code also folds in `min_contrast_f`/
   `min_fog_transparency`, which this project has no input for).
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
from typing import TYPE_CHECKING, Final

from perception import object_model
from perception.association import WorldObjectCandidate
from perception.cockpit_mask import COCKPIT_MASKS, STATION_CO_PILOT, is_visible
from perception.detection_trace import (
    DetectionTrace,
    DetectionTraceCollector,
    GateOutcome,
)
from perception.geometry import (
    GeoPosition,
    bearing_deg,
    body_relative_direction,
    line_of_sight_clear,
    range_m,
)
from perception.source import OwnshipState

if TYPE_CHECKING:
    # `Optic` is only used for annotations here -- the actual value (used
    # both as a type at runtime inside `check_visibility` and to resolve
    # its `optic` parameter's default) is imported lazily inside that
    # function. See its docstring for why: `optics.py` imports
    # `BINOCULAR_RANGE_MULTIPLIER` from this module at its own module
    # scope (`plans/detection-cones-slice1/plan.md` Decision 1 -- this
    # module keeps owning the constant), and a plain top-level import of
    # `optics.py` back into this module would make the two modules
    # genuinely circular: whichever of the two happens to be imported
    # first would fail, because it would trigger a full load of the
    # other, which itself needs the first one fully loaded.
    from perception.optics import Optic

#: **Current again, as of 2026-09-20** -- these three thresholds were
#: derived using `BINOCULAR_RANGE_MULTIPLIER = 4.0` (see that constant's
#: own docstring for the full round trip: 4.0 -> 8.0 -> 4.0). The
#: constant went to 8.0 for part of this design slice, which made this
#: block briefly stale, and is back to 4.0 now -- the worked-example
#: numbers below (`* 4`) are correct again, not historical.
#: `tests/test_vision_calibration.py` checks this directly.
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

#: See the module docstring's "round trip" note for the full chronology.
#: This is `BINOCULAR_OPTIC.magnification` (`optics.py`) -- the multiplier
#: `check_visibility` applies whenever that (now non-default) optic is
#: passed explicitly, and the one `_achieved_tier` and the angular-radius
#: thresholds above were calibrated against on 2026-09-17.
#:
#: **Round trip, final value 2026-09-20:** 4.0 (inherited, unexamined,
#: from `HelperAI.lua`'s `extra_eyesight_ratio`) -> 8.0 (a same-session
#: excursion: a realistic 8x30, magnification stated honestly, no
#: derating) -> **4.0 again.** The final value is numerically identical to
#: the first but is not the restored inherited number -- it is
#: independently derived, a Б-6 6x30's real 6x magnification times a
#: ~0.67 penalty for handheld use on a vibrating airframe
#: (`optics.py`'s `BINOCULAR_OPTIC` docstring has the arithmetic), and it
#: also happens to match what the 2026-09-17 screenshot ladder's
#: binocular column independently shows. Two independent lines of
#: evidence landing on the same number is a real confirmation of this
#: value, not evidence the excursion through 8.0 was wasted -- that
#: excursion is what replaced an unexamined borrowed constant with a
#: derived one that happens to agree with it.
#:
#: **No longer the default multiplier applied to every candidate.** As of
#: this same change, `check_visibility`'s default `optic` is
#: `UNAIDED_OPTIC` (magnification 1.0), not `BINOCULAR_OPTIC` -- see the
#: module docstring's superseded "Binocular premise" section and that
#: function's own docstring. This constant now only applies when
#: `BINOCULAR_OPTIC` is passed explicitly (no concrete `PerceptionSource`
#: does so yet, plan Decision 4).
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


def _achieved_tier(
    range_m: float,
    size_m: float,
    magnification: float = BINOCULAR_RANGE_MULTIPLIER,
) -> tuple[str, float]:
    """The tightest recognition tier `range_m` still satisfies for an object
    of characteristic size `size_m`, and that tier's confidence
    (Stage 6's worked table: presence low / class medium / type high). Each
    tier's threshold is independently capped at `NAKED_EYE_RANGE_CAP_M`, the
    same sanity bound `check_visibility`'s gate applies (module docstring
    gate #2) -- a very large object's `hires`/`medres` thresholds can both
    collapse onto the cap, which is expected, not a bug.

    `magnification` generalises the old hardcoded `BINOCULAR_RANGE_
    MULTIPLIER` reference (`plans/detection-cones-slice1/plan.md`) --
    defaults to it, so every existing call site (which passes no
    `magnification` argument) is unaffected.

    The `lowres` branch is unreachable while `NAKED_EYE_GATING_ANGULAR_
    RADIUS_RAD` gates at `medres` (Stage 6) -- `check_visibility` already
    drops anything beyond the gating threshold before this function is ever
    called on it. It becomes reachable once Stage 7 moves the gate to
    `lowres`."""
    hires_threshold_m = min(
        NAKED_EYE_RANGE_CAP_M,
        (size_m / HIRES_ANGULAR_RADIUS_RAD) * magnification,
    )
    medres_threshold_m = min(
        NAKED_EYE_RANGE_CAP_M,
        (size_m / MEDRES_ANGULAR_RADIUS_RAD) * magnification,
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
    *,
    optic: Optic | None = None,
    trace: DetectionTraceCollector | None = None,
) -> VisibilityResult | None:
    """Run `candidate` through all four gates: cockpit mask, per-optic field
    of view (`plans/detection-cones-slice1/plan.md`), angular-radius range,
    terrain LOS (see module docstring for the latter two). Returns `None`
    on the first failing gate -- cheap geometric checks (cockpit mask, FOV,
    angular-radius range) before the expensive LOS terrain-sampling check,
    mirroring `association.associate()`'s own cheap-before-expensive
    ordering.

    `optic` defaults to `optics.UNAIDED_OPTIC` (magnification 1.0), as of
    2026-09-20 -- this was `BINOCULAR_OPTIC` for most of that slice's
    development but is now naked-eye by default (module docstring's
    superseded "Binocular premise" section has the full reasoning: modelling
    Petrovich as permanently glassed-up, with binocular magnification and
    no field-of-view cost across the whole cockpit-mask envelope, was the
    single biggest source of over-detection in this channel). Accepted as
    `None` and resolved inside this function rather than as a literal
    `Optic = UNAIDED_OPTIC` default expression, to avoid a real circular
    import between this module and `optics.py` (see the `TYPE_CHECKING`
    import above) -- behaviourally identical: calling `check_visibility(...)`
    with no `optic` argument is the same as passing `UNAIDED_OPTIC`
    explicitly, which is what the regression test below actually pins.

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
    It now uses `optic.magnification`, so the traced threshold is by
    construction the one the gate used. Second, the FOV gate returned
    without recording, which would have broken BL-9's one-entry-per-call
    invariant the moment slice 2 wires a non-default optic; `GateOutcome`
    gained `OPTIC_FOV` and the gate now records like every other."""
    from perception.optics import UNAIDED_OPTIC, within_optic_fov

    if optic is None:
        optic = UNAIDED_OPTIC

    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    target = GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)

    candidate_bearing_deg = bearing_deg(observer, target)
    candidate_range_m = range_m(observer, target)
    profile = object_model.profile_for(candidate.object_type)
    size_curve_threshold_m = (
        profile.size_m / NAKED_EYE_GATING_ANGULAR_RADIUS_RAD
    ) * optic.magnification
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
    co_pilot_mask = COCKPIT_MASKS[STATION_CO_PILOT]
    if not is_visible(
        co_pilot_mask, body_direction.azimuth_deg, body_direction.elevation_deg
    ):
        _record(GateOutcome.COCKPIT_MASK)
        return None

    if not within_optic_fov(
        optic, body_direction.azimuth_deg, body_direction.elevation_deg
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
        candidate_range_m, profile.size_m, optic.magnification
    )
    _record(GateOutcome.ADMITTED, achieved_tier=achieved_tier)
    return VisibilityResult(
        bearing_deg=candidate_bearing_deg,
        range_m=candidate_range_m,
        tier=achieved_tier,
        confidence=achieved_confidence,
    )
