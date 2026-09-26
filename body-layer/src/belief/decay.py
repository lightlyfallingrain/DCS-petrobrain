"""Per-attribute decay half-lives and the `certainty` lifecycle ladder --
`plans/pb2-contact-memory/plan.md` Stage 2, implementing `docs/concept/
PETROBRAIN_RUNTIME.md`'s "Uncertainty and memory decay" section (identity
slow, exact position fast, general area medium/slow, motion medium) as one
table, per that section's own framing: "those differences should come from
structured confidence, not improvised wording."

The concept doc does not name concrete seconds or a closed `certainty` enum
-- both are placeholder judgment calls made here, once, per the plan's
explicit instruction ("what matters structurally is that they live in one
table"; Stage 1's `SCOPE_UNCERTAINTY_M`/`GATE_GROWTH_RATE_MPS` in
`association_over_time.py` are the precedent for this kind of documented,
revisitable constant).

Four of the five half-lives are now consumed. `POSITION_HALF_LIFE_S` (and
`LOST_THRESHOLD_S` derived from it) drives `certainty_of` below.
`IDENTITY_HALF_LIFE_S` drives `classification_confidence_at`
(`plans/classification-refinement/plan.md` Stage 10's follow-up fix, once
`Contact.classification` existed for it to decay) -- the folded
`belief.classification.ClassificationBelief.confidence` this module's own
first paragraph promised identity would eventually key off, keyed off
`ClassificationBelief.established_sim` rather than `contact.last_seen_sim`
-- identity confidence decays from when the classification claim was last
confirmed, not from when the contact itself was last observed at all.
`MOTION_HALF_LIFE_S` **is now consumed** (`plans/movement-detection/
plan.md` Stage 3) by `motion_confidence_at` below, the same shape
`classification_confidence_at` already has -- it sat in this table unused
since BL-2 with a docstring explicitly reserving it for exactly this.
`GENERAL_AREA_HALF_LIFE_S` remains unconsumed -- `Contact` does not yet
track a general-area field to decay independently (BL-3/world-enrichment
territory: `general_area`). `OBJECT_ID_MEMORY_S` (`plans/
contact-duplication-ambiguity-runaway/plan.md`) is not a sixth independent
half-life but a reuse of `IDENTITY_HALF_LIFE_S` under a second name, drawn
straight from this same table rather than an ad hoc timeout -- see its own
docstring below. `GENERAL_AREA_HALF_LIFE_S` stays declared even unconsumed
so the *one table* this module's docstring promises remains complete, and
so a future BL-3 pass extends this table rather than starting a second one
elsewhere (the plan's "Complicates BL-4" second-order-effect note).

`MOTION_STOP_CONFIRM_S` (`plans/movement-detection/plan.md` Stage 3,
`belief.motion.fold_motion`'s demotion gate) is declared here, not in
`belief/motion.py` -- it is a decay-adjacent timing constant in the same
family as `LOST_THRESHOLD_S`/`OBJECT_ID_MEMORY_S` above, not part of the
fold *rule* itself, and this keeps every named-seconds constant this module
promises to hold in one table.

All functions here are pure functions of `(contact, now_sim)` -- no ticker,
no mutation, no wall-clock. `ContactStore.tick` (`contacts.py`) is the only
caller that turns `certainty_of`'s result into a state change.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final, Literal

from perception.gaze import FOCUS_DWELL_S, SCAN_CYCLE_PERIOD_S

if TYPE_CHECKING:
    from belief.contacts import Contact

#: Slowest-decaying attribute: what a contact *is*. A crew member does not
#: forget "that was a BMP" on the timescale it takes the BMP to drive out of
#: sight -- identity should long outlive position confidence. Consumed by
#: `classification_confidence_at` below, which decays `Contact.
#: classification.confidence` (never `.level`, which stays sticky by
#: design -- see `belief.classification`'s module docstring) since this
#: claim's `established_sim`.
IDENTITY_HALF_LIFE_S: Final[float] = 600.0

#: Fastest-decaying attribute: the exact perceived position. Chosen as the
#: order-of-magnitude time a ground vehicle needs to move roughly its own
#: uncertainty radius at `belief.position_belief.GATE_GROWTH_RATE_MPS`
#: (20 m/s) -- i.e. "trust the exact spot for about half a minute, then
#: start hedging." This is the one half-life `certainty_of` below actually
#: uses to separate "tracked" from "estimated".
POSITION_HALF_LIFE_S: Final[float] = 30.0

#: Medium decay: which way it was moving. Slower than exact position (a
#: heading estimate stays plausible longer than a point position does) but
#: faster than "roughly where it is" -- per the concept doc's own ordering.
#: Consumed by `motion_confidence_at` below (`plans/movement-detection/
#: plan.md` Stage 3), decaying `Contact.motion.confidence` since
#: `MotionBelief.established_sim` -- the identical shape
#: `classification_confidence_at` already has for identity.
MOTION_HALF_LIFE_S: Final[float] = 60.0

#: How long a `"moving"` claim must see continuous sub-threshold
#: (`apparent_motion=False`) evidence before `belief.motion.fold_motion`
#: actually demotes it to `"stopped"` -- the asymmetric promote-fast/
#: demote-slow rule `belief.motion`'s own module docstring states in full.
#: Uncalibrated (same debt class as `optics.BINOCULAR_OPTIC`'s
#: stabilisation penalty and `perception.motion.MOTION_COCKPIT_PENALTY`):
#: named, isolated, and movable in one place. Chosen as a small multiple of
#: a naked-eye poll interval -- long enough that one noisy sub-threshold
#: reading near the gate's own boundary doesn't immediately flip a genuinely
#: still-moving contact to "stopped," short enough that a crew member does
#: not keep hearing "moving" long after a vehicle has visibly halted.
MOTION_STOP_CONFIRM_S: Final[float] = 5.0

#: `plans/watch-reporting/plan.md` Decision 5a-ii -- how long a **masked**
#: LOS verdict must hold continuously before an engagement danger state is
#: allowed to clear, `MOTION_STOP_CONFIRM_S`'s direct twin (same
#: uncalibrated-placeholder status, same "named, isolated, movable in one
#: place" reasoning). **Deliberately asymmetric, in the fail-open
#: direction**: a **clear** verdict (the threat can see us) takes effect
#: immediately, no dwell -- only a masked-therefore-safer verdict has to
#: wait. A false danger call costs the pilot a glance; a missed one costs
#: the aircraft, so the dwell only ever delays the *optimistic* transition,
#: never the cautious one. Consumed by `belief.contacts.ContactStore.tick`'s
#: seventh block via `Contact.los_masked_since_sim`, `motion_pending_stop_
#: since_sim`'s direct twin in shape.
LOS_MASK_CONFIRM_S: Final[float] = 5.0

#: `plans/sortie-2026-09-26-fixes/decisions.md` Decision 1 -- the grace
#: window over which a spontaneous callout (`belief.contacts.ContactStore.
#: tick`'s sixth block, `CONTACT_RANGE_CROSSED`, and the fifth block,
#: `CONTACT_MOTION_CHANGED`) may still fire for a contact that is currently
#: unobservable (behind the cockpit mask from every gaze direction), based
#: on `Contact.unobservable_since_sim` tracking how long the mask check has
#: failed *continuously*. This is **a starting value to tune against a
#: flown sortie, not a measurement** -- proposed as roughly `OBSERVED_
#: WINDOW_S / 1.6`: short enough that a sustained rear-hemisphere leg of an
#: orbit does go quiet, long enough to cover "slid behind the doorframe for
#: a few seconds" (the user's own wording) without treating a brief
#: occlusion as silence. See Decision 1's "the general rule is the
#: no-omniscience invariant, applied to callouts" for why this is a grace
#: window on unobservability rather than a bare gaze-cone gate.
CALLOUT_OBSERVABILITY_GRACE_S: Final[float] = 10.0

#: Medium/slow decay: the general area, independent of the exact point.
#: Slower than motion -- "somewhere near that village" stays true long after
#: "moving north at that exact spot" has gone stale. Not yet consumed (no
#: `general_area` field exists on `Contact` yet; BL-3 adds it).
GENERAL_AREA_HALF_LIFE_S: Final[float] = 180.0

#: The window within which a contact counts as "currently being perceived"
#: rather than merely "recently tracked" -- **re-derived from the naked-eye
#: scan cycle (2C, `plans/detection-cones-slice2/plan.md` hard part 8),
#: not left at its pre-scan-loop value of 5.0.** Once Petrovich scans
#: rather than seeing the whole envelope at once, a flank o'clock is
#: genuinely un-gazed for up to `perception.gaze.SCAN_CYCLE_PERIOD_S -
#: perception.gaze.FOCUS_DWELL_S` (14 s) of every 16 s cycle while still
#: being tracked perfectly well -- the old 5.0 s window would hedge
#: "observed" language on nearly every tick for a flank contact he is
#: watching correctly. `SCAN_CYCLE_PERIOD_S` (16.0) is the smallest value
#: that clears the lower bound below with margin for a poll landing
#: awkwardly, and reads as exactly what it means: "seen within the current
#: scan cycle." Both assertions below test a real failure mode, not a
#: tautology -- see `perception.gaze`'s own module docstring for the
#: worked derivation and the plan-C fallback this bound anticipates.
OBSERVED_WINDOW_S: Final[float] = SCAN_CYCLE_PERIOD_S

# Lower bound: below `SCAN_CYCLE_PERIOD_S - FOCUS_DWELL_S` (the worst-case
# flank gap -- a cone visited for one dwell, not revisited for the rest of
# the cycle), a contact Petrovich is tracking correctly would read as
# "not observed" for most of every cycle. A later tuning pass that shrinks
# `OBSERVED_WINDOW_S` without noticing this relationship trips this
# assertion instead of silently reintroducing that hedge.
assert SCAN_CYCLE_PERIOD_S - FOCUS_DWELL_S < OBSERVED_WINDOW_S, (
    "OBSERVED_WINDOW_S must clear the worst-case flank gap "
    "(SCAN_CYCLE_PERIOD_S - FOCUS_DWELL_S) or a correctly-tracked flank "
    "contact reads as unobserved for most of every scan cycle"
)

# Upper bound: at or above `POSITION_HALF_LIFE_S`, the "tracked" band
# between "observed" and "estimated" (`certainty_of` below) vanishes
# silently -- `elapsed_s <= OBSERVED_WINDOW_S` would already be false
# exactly when `elapsed_s <= POSITION_HALF_LIFE_S` also turns false, so no
# elapsed time could ever land in "tracked" at all. This assertion is what
# stops a later widening of `OBSERVED_WINDOW_S` (e.g. hard part 8's plan-C
# fallback, 16 -> 20) from silently collapsing that middle certainty band
# instead of raising `POSITION_HALF_LIFE_S` alongside it.
assert OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S, (
    "OBSERVED_WINDOW_S must stay below POSITION_HALF_LIFE_S or the "
    "'tracked' certainty band collapses to nothing"
)

#: Past this much elapsed time since last observed, a contact is considered
#: lost outright rather than merely stale. Set to 4x `POSITION_HALF_LIFE_S`
#: -- long enough that "estimated" (stale-but-plausible) has had room to mean
#: something distinct from "tracked", short enough that a contact does not
#: linger indefinitely as "estimated" once the crew has plainly lost it.
LOST_THRESHOLD_S: Final[float] = 120.0

#: `plans/contact-duplication-ambiguity-runaway/plan.md`'s object-permanence
#: expiry window: how long a resolved `Observation.continues_observation_id`
#: match is still trusted as "the same real object," keyed off `contact.
#: last_seen_sim` (see `object_id_continuity_valid` below). Reused directly
#: from `IDENTITY_HALF_LIFE_S`, not an independently-chosen number -- object
#: id continuity is itself an identity claim ("I still believe this is the
#: same vehicle"), and this module's own docstring already names identity as
#: the slowest-decaying attribute. Deliberately *not* `LOST_THRESHOLD_S`:
#: that threshold governs the position/tracking narrative
#: (`certainty_of` below), and tying object_id memory to it would nullify
#: the identity claim at exactly the moment ("I lost him") the crew should
#: still trust it most. Deliberately larger than `LOST_THRESHOLD_S` (600s
#: > 120s) so a contact can pass all the way through "observed -> tracked ->
#: estimated -> lost" and still be validly reacquired via continuity in the
#: 120-600s window -- the "I lost him... it's the same guy" case. Inherits
#: `IDENTITY_HALF_LIFE_S`'s own placeholder-judgment-call status (see that
#: constant's docstring) -- revisit this constant specifically, not that one
#: first, if live sessions show continuity trusted too long or not long
#: enough; the two are conceptually distinct claims that happen to share a
#: value for now, not permanently coupled.
OBJECT_ID_MEMORY_S: Final[float] = IDENTITY_HALF_LIFE_S

#: The certainty lifecycle ladder. Four levels, evaluated top-down in
#: `certainty_of` (first match wins) rather than as independent predicates:
#:
#:   observed  -- currently being perceived (within `OBSERVED_WINDOW_S`).
#:   tracked   -- recently seen; position still trustworthy (within
#:                `POSITION_HALF_LIFE_S`).
#:   estimated -- position has decayed past its half-life but the contact is
#:                not yet given up on (within `LOST_THRESHOLD_S`).
#:   lost      -- past `LOST_THRESHOLD_S` since last observed.
#:
#: `docs/concept/PETROBRAIN_RUNTIME.md`'s "Uncertainty and memory decay"
#: section names the four *wordings* this ladder must support ("I see him." /
#: "I think he was..." / "Last saw him..." / "I lost him.") without naming
#: the enum itself -- this is that enum, derived to match.
Certainty = Literal["observed", "tracked", "estimated", "lost"]


def certainty_of(contact: Contact, now_sim: float) -> Certainty:
    """The contact's current `Certainty`, evaluated top-down against elapsed
    time since `contact.last_seen_sim`. Pure -- does not read or write
    `contact.last_emitted_certainty`; that comparison is `events.
    lifecycle_event_kind`'s job, not this function's."""
    elapsed_s = max(0.0, now_sim - contact.last_seen_sim)
    if elapsed_s <= OBSERVED_WINDOW_S:
        return "observed"
    if elapsed_s <= POSITION_HALF_LIFE_S:
        return "tracked"
    if elapsed_s <= LOST_THRESHOLD_S:
        return "estimated"
    return "lost"


def position_confidence(contact: Contact, now_sim: float) -> float:
    """Numeric position confidence, `(0, 1]`, exponentially decaying with a
    half-life of `POSITION_HALF_LIFE_S` since `contact.last_seen_sim` --
    BL-3's (`plans/bl3-world-enrichment/plan.md` step 2) numeric counterpart
    to `certainty_of`'s discrete ladder above, and the one number `belief.
    enrichment`'s `position`/`semantic`/`motion_when_seen` fields all key
    off. Pure, like every other function in this module -- no ticker, no
    mutation, no wall-clock."""
    elapsed_s = max(0.0, now_sim - contact.last_seen_sim)
    return math.pow(0.5, elapsed_s / POSITION_HALF_LIFE_S)


def classification_confidence_at(contact: Contact, now_sim: float) -> float:
    """Numeric classification confidence, `(0, 1]`, exponentially decaying
    with a half-life of `IDENTITY_HALF_LIFE_S` since `contact.classification.
    established_sim` -- the identity-attribute counterpart to `certainty_of`'s
    position-keyed ladder above, per this module's docstring. Decays only the
    *number*; `contact.classification.level` never decays (stays sticky by
    design, `belief.classification`'s module docstring) and this function
    does not touch it -- callers that need the folded claim's value/level
    still read `contact.classification` directly, only its `confidence` is
    read through here. Pure, like every other function in this module -- no
    ticker, no mutation, no wall-clock."""
    elapsed_s = max(0.0, now_sim - contact.classification.established_sim)
    return contact.classification.confidence * math.pow(
        0.5, elapsed_s / IDENTITY_HALF_LIFE_S
    )


def cardinality_confidence_at(contact: Contact, now_sim: float) -> float:
    """Numeric cardinality confidence, `(0, 1]`, exponentially decaying with
    a half-life of `IDENTITY_HALF_LIFE_S` since `contact.cardinality.
    established_sim` -- `classification_confidence_at`'s direct twin
    (`plans/group-contact-model/plan.md` Stage 1), reusing the same
    half-life rather than declaring a new one: how many things are there is
    an identity claim, the same reasoning `belief.cardinality`'s module
    docstring gives for reusing `IDENTITY_HALF_LIFE_S` in `fold_cardinality`'s
    own lockout constant. Decays only the *number*; `contact.cardinality.lo`/
    `.hi` never decay (the interval stays sticky by design, mirroring
    `ClassificationBelief.level`). Pure, like every other function in this
    module -- no ticker, no mutation, no wall-clock."""
    elapsed_s = max(0.0, now_sim - contact.cardinality.established_sim)
    return contact.cardinality.confidence * math.pow(
        0.5, elapsed_s / IDENTITY_HALF_LIFE_S
    )


def motion_confidence_at(contact: Contact, now_sim: float) -> float:
    """Numeric motion confidence, `(0, 1]`, exponentially decaying with a
    half-life of `MOTION_HALF_LIFE_S` since `contact.motion.established_sim`
    -- `classification_confidence_at`'s direct twin (`plans/
    movement-detection/plan.md` Stage 3), reusing the same "decay only the
    number" shape: `contact.motion.state` never decays, only `confidence`
    does. **Caller's responsibility to check `contact.motion is not None`
    first** -- unlike `classification`/`cardinality`, a contact's motion
    belief can genuinely stay `None` for its whole life (see `belief.motion`'s
    module docstring on why it is not seeded at founding), so this function
    has no honest answer to give for one and does not attempt to fabricate
    one. Pure, like every other function in this module -- no ticker, no
    mutation, no wall-clock."""
    assert contact.motion is not None, (
        "motion_confidence_at requires contact.motion to be set -- callers "
        "must check for None first (see this function's own docstring)"
    )
    elapsed_s = max(0.0, now_sim - contact.motion.established_sim)
    return contact.motion.confidence * math.pow(0.5, elapsed_s / MOTION_HALF_LIFE_S)


def object_id_continuity_valid(contact: Contact, now_sim: float) -> bool:
    """Whether a resolved `continues_observation_id` match onto `contact` is
    still trusted, per `OBJECT_ID_MEMORY_S`'s docstring above -- `True`
    (boundary inclusive, matching `certainty_of`'s own `<=` convention) at
    exactly `OBJECT_ID_MEMORY_S` elapsed since `contact.last_seen_sim`,
    `False` just past it. Anchored to `contact.last_seen_sim` (the most
    recent observation from *any* channel), not any one `PerceptionSource`'s
    own persistent map's last-touched time -- a contact kept fresh by one
    channel while another lost sight of the object should still honor that
    other channel's own stale-looking map entry, since the contact's
    identity was never actually in doubt. `belief.contacts.ContactStore.
    ingest` is the only caller: a resolved-but-expired match falls through
    to the ordinary gate/ambiguity path identically to an unresolved one --
    see that module's docstring. Pure, like every other function in this
    module -- no ticker, no mutation, no wall-clock."""
    elapsed_s = max(0.0, now_sim - contact.last_seen_sim)
    return elapsed_s <= OBJECT_ID_MEMORY_S
