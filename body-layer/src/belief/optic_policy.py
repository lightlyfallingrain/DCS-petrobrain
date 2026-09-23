"""When Petrovich raises binoculars, and when he puts them down.

`plans/binocular-optic/plan.md` Stage 2. The optical model already existed
and was unreachable; this is the decision that reaches it.

**It is a phase cycle, not an interrupt** (user direction, 2026-09-23:
*"when scan detects target, do not immediately raise binoculars. First
complete the current sector naked eye scan to get as many naked eye
detections as possible, then raise binoculars to take a closer look"*):

- **Scan phase** -- the naked-eye plan runs to completion. Detections
  accumulate; nothing is glassed.
- **Glass phase** -- entered only at a phase boundary, and only when there
  is something worth looking at. Ends on its own conditions, hands back.

**That structure is what enforces the cost.** The user's rule was *"at
least one naked eye scan before next binocular usage"*, and rather than a
timer that could be got wrong, a glass phase is simply unreachable except
from the end of a scan phase -- the illegal state cannot be expressed. Its
length then follows whatever plan is active, which is exactly the
*"depends on scan mode"* the user asked for: a free scan cycles in 16 s, a
commanded o'clock sector far faster, and **nothing here computes that** --
it is the plan's own period.

**Why this lives in `belief`.** The decision reads beliefs -- what is
detected, at what class, at what range -- and `perception` may not import
`belief` (`perception/source.py`'s module docstring). `gaze.py` resolved
this exact tension already and its resolution is reused verbatim: belief
decides, `logger` hands perception a frozen value per poll, perception
owns the act. `decide` is a pure function of its inputs, so replay stays
deterministic for the same reason `gaze_at` does.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from itertools import pairwise
from typing import Final

from perception.geometry import GeoPosition, bearing_deg, range_m
from perception.object_model import apparent_extent_m, distinctiveness_of, profile_for
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC, Optic
from perception.visibility import tier_ranges

#: The longest one look can last. The user's number, and a ceiling rather
#: than a duration: `look_is_finished` normally ends a look sooner, when
#: there is nothing left to learn from it. This fires only when recognition
#: simply is not happening, which is exactly the case where continuing to
#: stare buys nothing and costs the scan.
MAX_LOOK_S: Final[float] = 6.0

#: Above this rate of attitude change, binoculars come down (user:
#: *"jittery flying and hard manouvering lowers binoculars, they are
#: useless unless the flight is fairly smooth"*).
#:
#: **This gate sees manoeuvring, not vibration, and does not need to see
#: vibration.** Body-layer samples attitude about once a second, which
#: aliases anything faster -- but `BINOCULAR_OPTIC`'s own stabilisation
#: penalty already prices the fact that a helicopter cockpit is never
#: still. Modelling the shake twice would double-count it. What this
#: catches is the aircraft being thrown around, which is both observable at
#: this rate and the thing that actually makes an instrument unusable.
#:
#: Uncalibrated, like every perception constant before its first sortie.
STEADY_RATE_LIMIT_DEG_S: Final[float] = 12.0

#: How much closer a contact must get before a failed identification is
#: worth retrying (user: *"if ID failed, try again when we get closer"*).
#:
#: **A range test rather than a timer, deliberately.** A contact at
#: constant range has not become more identifiable, so a retry there
#: re-asks a question already answered and spends the look that another
#: contact could have used.
RETRY_RANGE_FRACTION: Final[float] = 0.8

#: The widest sector a binocular *search* will sweep (user: *"cap binocular
#: scan at 30 deg azimuth, there's no wide area binocular scan"*). A wider
#: commanded scan simply gets no search phase -- see `plans/binocular-optic/
#: plan.md` D6 for the arithmetic that makes a 180-degree sweep absurd
#: (~60 steps) where a 30-degree one is about twelve.
MAX_SEARCH_SECTOR_HALF_WIDTH_DEG: Final[float] = 15.0


class OpticPhase(str, Enum):
    """Which half of the cycle is running."""

    SCANNING = "scanning"
    GLASSING = "glassing"


@dataclass(frozen=True)
class LookTarget:
    """One contact worth a closer look, with what the decision needs about
    it. Built by the caller from live beliefs; this module never touches a
    `Contact` directly, so the policy stays testable without a store."""

    contact_id: str
    azimuth_deg: float
    elevation_deg: float
    range_m: float
    object_type: str
    #: The specificity the contact is already believed at -- `"presence"`,
    #: `"class"`, `"type"`, or `"unknown"` (`belief.classification.
    #: SpecificityLevel`'s own vocabulary, lowercased). It selects *which*
    #: tier a look would gain, which is what makes the trigger "raise to
    #: classify" rather than "raise to identify".
    current_level: str


@dataclass(frozen=True)
class OpticState:
    """The cycle's own state, carried across polls by the runner.

    Frozen and replaced rather than mutated, so a poll that decides nothing
    returns the identical object and a replay produces the identical
    sequence."""

    phase: OpticPhase = OpticPhase.SCANNING
    phase_started_sim: float = 0.0
    #: Where the current look points, body-relative. `None` while scanning.
    look_azimuth_deg: float | None = None
    look_elevation_deg: float | None = None
    #: Range at the last attempt, per contact -- `RETRY_RANGE_FRACTION`'s
    #: input. Contacts are never removed: the map is bounded by how many
    #: distinct contacts one sortie produces, and forgetting an attempt
    #: would let a contact be re-glassed forever at the same range.
    attempted_at_range_m: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class OpticDecision:
    """What perception should do this poll."""

    optic: Optic
    #: Where to point, when glassing. `None` means "leave the scan plan
    #: alone" -- the scan phase does not override the gaze at all.
    look_azimuth_deg: float | None = None
    look_elevation_deg: float | None = None


def is_steady(
    attitude_samples: Sequence[tuple[float, float, float, float]],
) -> bool:
    """Whether the aircraft is flying smoothly enough to use binoculars.

    `attitude_samples` is `(t_sim, pitch_deg, bank_deg, heading_deg)`,
    oldest first -- whatever recent history the caller has. Fewer than two
    samples is treated as steady: at startup there is no evidence of
    manoeuvring, and refusing to look until proven calm would make the
    instrument unusable for the first seconds of every mission.

    Heading is wrapped before differencing, so crossing north is not a
    360-degree-per-second manoeuvre.
    """
    if len(attitude_samples) < 2:
        return True

    for (t0, pitch0, bank0, hdg0), (t1, pitch1, bank1, hdg1) in pairwise(
        attitude_samples
    ):
        dt = t1 - t0
        if dt <= 0.0:
            continue  # duplicate or out-of-order sample; no rate to read
        heading_delta = (hdg1 - hdg0 + 180.0) % 360.0 - 180.0
        rate = (
            max(
                abs(pitch1 - pitch0),
                abs(bank1 - bank0),
                abs(heading_delta),
            )
            / dt
        )
        if rate > STEADY_RATE_LIMIT_DEG_S:
            return False
    return True


def improvement_window_m(
    object_type: str, *, current_level: str
) -> tuple[float, float]:
    """The range band in which binoculars would move this contact up a
    tier: `(unaided_range, binocular_range)` for whichever tier is next.

    **Whatever tier is next, not always type.** The user's brief said both
    *"raise to classify"* and *"at distance where binoculars would identify
    type"*, and the first is the general rule the second is an instance of:
    a contact known only to exist is worth glassing to learn what *kind* of
    thing it is, and one already classed is worth glassing to learn what it
    *is*. Reading it as type-only made the feature nearly unusable, and the
    numbers say why -- for a 7 m vehicle:

        presence -> class:   500 m unaided,  1750 m glassed
        class    -> type:    250 m unaided,   750 m glassed

    Classification is both the commoner want and the far wider band. A
    type-only trigger would have confined binoculars to inside 750 m, where
    the interesting question is usually *"what is that"* at three times
    that range.

    **Computed from the existing calibration rather than tuned.** Closer
    than the lower bound, the naked eye reaches that tier on the next dwell
    anyway, so glassing there spends the look to learn nothing; beyond the
    upper bound the binoculars cannot reach it either. The window is
    exactly the band where the instrument is the difference, and it comes
    out of `tier_ranges` -- the same code the eye itself uses -- not from a
    threshold invented here.

    A contact already at `type` has no next tier: `(0.0, 0.0)`, a window
    nothing falls inside.
    """
    profile = profile_for(object_type)
    # Aspect is unknown for a belief (the contact may have turned since it
    # was last seen), so the profile's own extent is used. A wrong guess
    # costs at most one wasted look, which `RETRY_RANGE_FRACTION` then
    # stops from repeating.
    extent = apparent_extent_m(profile, None)
    distinctiveness = distinctiveness_of(profile)

    def ranges(optic: Optic) -> tuple[float, float, float]:
        return tier_ranges(
            presence_size_m=profile.size_m,
            recognition_extent_m=extent,
            optic=optic,
            distinctiveness=distinctiveness,
        )

    _, unaided_class_m, unaided_type_m = ranges(UNAIDED_OPTIC)
    _, binocular_class_m, binocular_type_m = ranges(BINOCULAR_OPTIC)

    if current_level == "type":
        return 0.0, 0.0
    if current_level == "class":
        return unaided_type_m, binocular_type_m
    # presence, unknown, or anything else a belief can hold: the next thing
    # worth learning is what kind of thing it is.
    return unaided_class_m, binocular_class_m


def can_still_improve(target: LookTarget) -> bool:
    """Whether a look at this contact could raise its tier at all, ignoring
    whether one has been tried before.

    **Separate from `is_worth_a_look`, and the separation is load-bearing.**
    A look marks every contact it covers as attempted the moment it starts
    (they all get its benefit, so they all bear the retry rule) -- so if the
    stop condition asked "is this still *worth* a look", every look would
    end on the poll after it began, because the contact it was aimed at had
    just been marked. The retry rule governs *starting* a look; this governs
    *continuing* one. A test caught the conflation.
    """
    if target.current_level == "type":
        return False
    lower_m, upper_m = improvement_window_m(
        target.object_type, current_level=target.current_level
    )
    return lower_m < target.range_m <= upper_m


def is_worth_a_look(target: LookTarget, state: OpticState) -> bool:
    """Whether this contact would gain anything from a *new* look now."""
    if not can_still_improve(target):
        return False
    attempted_at = state.attempted_at_range_m.get(target.contact_id)
    if attempted_at is None:
        return True
    # Tried before: only worth repeating once it has genuinely closed.
    return target.range_m <= attempted_at * RETRY_RANGE_FRACTION


def choose_look(targets: Sequence[LookTarget]) -> LookTarget | None:
    """Which direction to point, given everything worth looking at.

    **Picks the direction holding the most targets, not the nearest one**
    (user: *"if binocular FOV sees multiple units at once, they all get the
    benefit"*). The optic is a property of the look rather than of a
    target, so a look that covers three unresolved contacts resolves three;
    choosing the nearest instead would spend the same look on one. Ties
    break toward the closest, which is the one most likely to resolve.
    """
    if not targets:
        return None
    half_angle = BINOCULAR_OPTIC.fov_half_angle_deg
    if half_angle is None:  # pragma: no cover -- binoculars always have one
        return min(targets, key=lambda t: t.range_m)

    def covered(centre: LookTarget) -> tuple[int, float]:
        count = sum(
            1
            for other in targets
            if _angular_separation_deg(centre, other) <= half_angle
        )
        return count, -centre.range_m

    return max(targets, key=covered)


def _angular_separation_deg(a: LookTarget, b: LookTarget) -> float:
    """True angular separation between two look directions -- not an
    azimuth difference, for the same reason `within_optic_fov` is not a
    box: a circular eyepiece does not admit a target because azimuth and
    elevation each pass independently."""
    az_delta = math.radians(a.azimuth_deg - b.azimuth_deg)
    el_a = math.radians(a.elevation_deg)
    el_b = math.radians(b.elevation_deg)
    cos_sep = math.sin(el_a) * math.sin(el_b) + math.cos(el_a) * math.cos(
        el_b
    ) * math.cos(az_delta)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_sep))))


def look_is_finished(
    state: OpticState, now_sim: float, targets: Sequence[LookTarget]
) -> bool:
    """Whether the current look has nothing left to give.

    The user's stop condition, which is sharper than the timer beside it:

    > unit(s) looked at gained more detailed identification / no other
    > units in FOV at distance where more detailed identification can be
    > expected

    Both halves are one predicate -- **no contact inside the field of view
    is still within the improvement window** -- since a contact that has
    been identified has left the window by definition, and one that never
    could be was never in it. `MAX_LOOK_S` then only fires when recognition
    is not happening at all.
    """
    if now_sim - state.phase_started_sim >= MAX_LOOK_S:
        return True
    return not any(
        _target_in_current_look(state, target) and can_still_improve(target)
        for target in targets
    )


def _target_in_current_look(state: OpticState, target: LookTarget) -> bool:
    if state.look_azimuth_deg is None or state.look_elevation_deg is None:
        return False
    half_angle = BINOCULAR_OPTIC.fov_half_angle_deg
    if half_angle is None:  # pragma: no cover
        return True
    centre = LookTarget(
        contact_id="",
        azimuth_deg=state.look_azimuth_deg,
        elevation_deg=state.look_elevation_deg,
        range_m=0.0,
        object_type="",
        current_level="unknown",
    )
    return _angular_separation_deg(centre, target) <= half_angle


def lower_binoculars(state: OpticState, now_sim: float) -> OpticState:
    """Put them down now, whatever the cycle was doing.

    Called when the player issues any command (user: *"new command from
    player lowers binoculars"*) -- not per command type: the pilot asking
    for something is itself evidence that what Petrovich is doing matters
    less than what was just asked for.
    """
    if state.phase is OpticPhase.SCANNING:
        return state
    return replace(
        state,
        phase=OpticPhase.SCANNING,
        phase_started_sim=now_sim,
        look_azimuth_deg=None,
        look_elevation_deg=None,
    )


def decide(
    state: OpticState,
    *,
    now_sim: float,
    scan_cycle_period_s: float,
    targets: Sequence[LookTarget],
    steady: bool,
) -> tuple[OpticState, OpticDecision]:
    """Advance the cycle one poll and say what to look through.

    Pure: same inputs, same outputs, no clock read and no store access --
    which is what keeps a replay identical, the property `gaze_at` was
    built around and this has to preserve.
    """
    if state.phase is OpticPhase.GLASSING:
        if not steady or look_is_finished(state, now_sim, targets):
            return (
                replace(
                    state,
                    phase=OpticPhase.SCANNING,
                    phase_started_sim=now_sim,
                    look_azimuth_deg=None,
                    look_elevation_deg=None,
                ),
                OpticDecision(optic=UNAIDED_OPTIC),
            )
        return state, OpticDecision(
            optic=BINOCULAR_OPTIC,
            look_azimuth_deg=state.look_azimuth_deg,
            look_elevation_deg=state.look_elevation_deg,
        )

    # Scanning. A look can only start at a completed scan cycle -- this is
    # the lockout, and it is a structural property rather than a rule.
    scan_complete = now_sim - state.phase_started_sim >= scan_cycle_period_s
    if not scan_complete or not steady:
        return state, OpticDecision(optic=UNAIDED_OPTIC)

    worth_looking = [target for target in targets if is_worth_a_look(target, state)]
    chosen = choose_look(worth_looking)
    if chosen is None:
        # Nothing to look at: the scan cycle restarts rather than the
        # aircraft waiting in a completed phase forever.
        return (
            replace(state, phase_started_sim=now_sim),
            OpticDecision(optic=UNAIDED_OPTIC),
        )

    attempted = dict(state.attempted_at_range_m)
    for target in worth_looking:
        if _angular_separation_deg(chosen, target) <= (
            BINOCULAR_OPTIC.fov_half_angle_deg or 0.0
        ):
            # Every contact this look covers counts as attempted, not just
            # the one it was centred on -- they all get the benefit, so
            # they all bear the retry rule.
            attempted[target.contact_id] = target.range_m

    return (
        OpticState(
            phase=OpticPhase.GLASSING,
            phase_started_sim=now_sim,
            look_azimuth_deg=chosen.azimuth_deg,
            look_elevation_deg=chosen.elevation_deg,
            attempted_at_range_m=attempted,
        ),
        OpticDecision(
            optic=BINOCULAR_OPTIC,
            look_azimuth_deg=chosen.azimuth_deg,
            look_elevation_deg=chosen.elevation_deg,
        ),
    )


def look_target_for(
    contact_id: str,
    *,
    observer: GeoPosition,
    target_position: GeoPosition,
    heading_true_deg: float,
    object_type: str,
    current_level: str,
) -> LookTarget:
    """Build a `LookTarget` from a contact's believed position.

    Lives here rather than in the caller so the azimuth/elevation
    convention is stated once: body-relative azimuth (0 dead ahead,
    positive clockwise) and elevation positive up, the same frame
    `within_optic_fov` tests in.
    """
    true_bearing = bearing_deg(observer, target_position)
    slant_m = range_m(observer, target_position)
    azimuth = (true_bearing - heading_true_deg + 540.0) % 360.0 - 180.0
    height_delta = target_position.alt_m - observer.alt_m
    elevation = math.degrees(math.asin(max(-1.0, min(1.0, height_delta / slant_m))))
    return LookTarget(
        contact_id=contact_id,
        azimuth_deg=azimuth,
        elevation_deg=elevation,
        range_m=slant_m,
        object_type=object_type,
        current_level=current_level,
    )
