"""`Contact`, `SightingSpan`, `ContactStore` -- `plans/pb2-contact-memory/
plan.md` Stage 1's persistent belief record and its append-only observation
log, extended by Stage 2 with decay-driven certainty and lifecycle events
(`CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED`). BL-4 (`plans/
bl4-attention-events/plan.md`) adds `ContactStore`'s `AttentionArea`
registry and unacknowledged-event queue, and extends `tick` with a third
event kind (`CONTACT_ATTENTION_CHANGED`) plus a per-contact-per-kind
emission cooldown applied to all three kinds -- see `tick`'s own docstring
and `belief.events`'s module docstring for the cooldown's full rationale.

Everything a `Contact` knows comes from a `belief.percept.Percept` --
`ContactStore.ingest` never reads `perception.source.Observation`'s DCS
ground-truth position field or its object id (see `percept.py`'s module
docstring for why that boundary is structural, not a convention to
remember).

`ingest`'s primary contact-identity mechanism, for any re-observation of a
previously-seen object on either perception channel, is now object-
permanence correlation via `Percept.continues_observation_id`
(`plans/contact-duplication-ambiguity-runaway/plan.md`) -- the
spatial/class gate in `belief.association_over_time` is the *exception*
path: founding observations, and reacquisitions where correlation didn't
resolve or has expired (`belief.decay.object_id_continuity_valid`), not the
common case. See `ingest`'s own docstring for the exact decision order.

`ContactStore.tick` is Stage 2's addition: it materialises lifecycle events
purely from `now_sim` (never wall clock, preserving BL-0's replay
determinism) by comparing each contact's freshly computed `belief.decay.
Certainty` against its `last_emitted_certainty`, via `belief.events.
lifecycle_event_kind`. `tick` owns event-id minting and the
`last_emitted_certainty` update; the comparison logic itself lives in
`events.py`, kept pure and store-agnostic -- the same split Stage 1 drew
between `association_over_time.passes_gate` (pure decision) and `ingest`
(bookkeeping).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Final

from belief.association_over_time import (
    implied_position,
    passes_gate,
    percept_position_uncertainty,
)
from belief.attention import (
    Attention,
    AttentionArea,
    RelativeSector,
    Sector,
    effective_attention,
    project_relative_area,
)
from belief.cardinality import (
    CARDINALITY_CONTRADICTION_LOCKOUT_S,
    OP_1UNIT,
    CardinalityBelief,
    cardinality_belief_from_bucket_name,
    fold_cardinality,
    new_cardinality_belief,
)
from belief.classification import (
    CLASSIFICATION_CONTRADICTION_LOCKOUT_S,
    ClassificationBelief,
    SpecificityLevel,
    class_compatibility,
    fold_classification,
    new_classification_belief,
)
from belief.decay import (
    CALLOUT_OBSERVABILITY_GRACE_S,
    LOS_MASK_CONFIRM_S,
    OBSERVED_WINDOW_S,
    Certainty,
    certainty_of,
    object_id_continuity_valid,
)
from belief.events import (
    CONTACT_ATTENTION_CHANGED,
    CONTACT_CARDINALITY_CHANGED,
    CONTACT_CLASSIFICATION_CHANGED,
    CONTACT_ENGAGEMENT_CHANGED,
    CONTACT_MOTION_CHANGED,
    CONTACT_RANGE_CROSSED,
    EVENT_COOLDOWN_S,
    Event,
    EventKind,
    attention_event_kind,
    cardinality_event,
    classification_event,
    lifecycle_event_kind,
    motion_event_kind,
)
from belief.groups import Group, GroupStore
from belief.motion import MotionBelief, MotionState, fold_motion
from belief.percept import Percept, percept_of
from belief.position_belief import (
    PositionEstimate,
    clamp_to_detection_envelope,
    fold_position,
)
from belief.threat import envelope_for
from perception.association import RANGE_CAP_M as _HYBRID_RANGE_CAP_M
from perception.cockpit_mask import COCKPIT_MASKS, STATION_CO_PILOT, is_visible
from perception.geometry import (
    GeoPosition,
    body_relative_direction,
    range_m,
)
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    Observation,
    OwnshipState,
)
from perception.visibility import NAKED_EYE_RANGE_CAP_M as _NAKED_EYE_RANGE_CAP_M

#: `plans/position-belief-runaway/debug.md` -- the physical detection-range
#: cap `clamp_to_detection_envelope` checks a fused position against,
#: keyed by `Percept.source`. Each concrete channel already enforces its
#: own cap when *admitting* a look (`perception.visibility.check_visibility`
#: for naked-eye, `perception.association.associate` for the scope/hybrid
#: channel) -- this is the same physical bound, reused rather than
#: reinvented, applied to the *fused belief* instead of a single look. An
#: unrecognised source (should not arise; both concrete sources are listed)
#: falls back to the larger of the two -- conservative in the direction of
#: never spuriously rejecting a fusion this module has no data to judge.
_MAX_DETECTION_RANGE_M: Final[dict[str, float]] = {
    SOURCE_NAKED_EYE_VISUAL_FILTERED: _NAKED_EYE_RANGE_CAP_M,
    SOURCE_PETROVICH_DETECTION_ASSOCIATED: _HYBRID_RANGE_CAP_M,
}
_FALLBACK_MAX_DETECTION_RANGE_M: Final[float] = max(_MAX_DETECTION_RANGE_M.values())


def _max_detection_range_m(source: str) -> float:
    """`_MAX_DETECTION_RANGE_M[source]`, or the conservative fallback for a
    source this table does not name -- see that table's own docstring."""
    return _MAX_DETECTION_RANGE_M.get(source, _FALLBACK_MAX_DETECTION_RANGE_M)


#: `plans/watch-reporting/plan.md` Decision 5 -- the user's own cap: a
#: watched contact's whole-kilometre range mark is only ever announced
#: inside this radius. Past it, `CONTACT_RANGE_CROSSED` simply stops firing
#: (`Contact.last_announced_range_km` is left at whatever it last was, per
#: `tick`'s sixth block).
WATCH_RANGE_REPORT_MAX_KM: Final[int] = 5

#: Decision 5a-i's floor on the uncertainty-derived deadband -- a Schmitt
#: gap around the whole-kilometre boundary, sized so a very tight position
#: estimate still gets a minimal gap (a zero deadband would silently
#: reintroduce the jitter bug this amendment exists to fix).
RANGE_CROSS_MIN_DEADBAND_M: Final[float] = 50.0

#: Decision 5a-i's ceiling -- half a kilometre band. Past this down-range
#: sigma (`belief.position_belief.PositionEstimate.range_uncertainty_m`),
#: the estimate cannot resolve *which* kilometre it is in, so a crossing is
#: suppressed entirely rather than announced on a coin flip.
RANGE_CROSS_MAX_SIGMA_M: Final[float] = 500.0

#: Decision 4e's Schmitt trigger -- enter an envelope at `1.0 x` its max
#: range, leave at `1.5 x`. Without the gap, a contact sitting near the
#: boundary flaps between "danger" and "safe from" every few seconds and
#: burns the `EVENT_COOLDOWN_S` budget doing it.
ENGAGEMENT_LEAVING_HYSTERESIS: Final[float] = 1.5

#: `ContactStore`-minted contact id prefix. Distinct in shape from the
#: per-source `Observation.id` prefixes (`perception.source.
#: OBSERVATION_ID_PREFIX_*`) -- a contact id never collides with an
#: observation id because the two id spaces are never compared or merged.
_CONTACT_ID_PREFIX = "CONTACT"

#: `ContactStore`-minted `Event.id` prefix, distinct in shape from both id
#: spaces above for the same reason -- an event id never collides with a
#: contact id or an observation id.
_EVENT_ID_PREFIX = "EVENT"

#: `ContactStore`-minted `AttentionArea.id` prefix, distinct in shape from
#: every id space above for the same reason (BL-4).
_AREA_ID_PREFIX = "AREA"


def _callout_may_speak(contact: Contact, ownship: OwnshipState, now_sim: float) -> bool:
    """`plans/sortie-2026-09-26-fixes/plan.md` Stage 1 (Fix A). Updates
    `contact.last_observable_sim`'s bookkeeping against the contact's
    *current true* bearing (the same primitive `perception.visibility`
    already uses at detection time -- `perception.cockpit_mask.is_visible`
    against `perception.geometry.body_relative_direction`, not the
    narrower gaze cone: Decision 1 is explicit that a contact merely out of
    current gaze must still get its tracking update, only a *physically
    unseeable from any gaze direction* one may not) and returns whether a
    spontaneous callout (`ContactStore.tick`'s fifth and sixth blocks) may
    still speak about it right now.

    **Requires having been genuinely observable at least once, not merely
    "not yet unobservable for too long."** The grace window (`belief.decay.
    CALLOUT_OBSERVABILITY_GRACE_S`) is Decision 1's memory of a *recent*
    sighting -- "a contact sliding behind the doorframe for a few seconds
    is still tracked" -- which presupposes there was something to remember.
    A contact whose bearing has been behind the cockpit mask continuously
    since it was founded (e.g. a percept from a non-naked-eye channel that
    was never actually glimpsed) has no such memory to draw on: granting it
    a fresh `CALLOUT_OBSERVABILITY_GRACE_S` window on its very first
    evaluated tick would let a permanently astern contact speak for the
    whole grace period regardless, which is exactly the "outside FOV/
    cockpit-masked" defect this fix exists to close. So the gate is "is it
    observable now, or was it observable within the last `CALLOUT_
    OBSERVABILITY_GRACE_S` seconds" -- never "how long has it merely been
    failing," which trivially starts at zero on a contact's first failing
    check and would let *any* permanently-masked contact through for one
    full grace window.

    Only ever called with `ownship` non-`None` -- `tick`'s two calling
    blocks are both already gated on that."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    body_direction = body_relative_direction(
        observer,
        contact.last_position,
        heading_true_deg=ownship.heading_true_deg,
        pitch_deg=ownship.pitch_deg,
        bank_deg=ownship.bank_deg,
    )
    co_pilot_mask = COCKPIT_MASKS[STATION_CO_PILOT]
    observable = is_visible(
        co_pilot_mask, body_direction.azimuth_deg, body_direction.elevation_deg
    )
    if observable:
        contact.last_observable_sim = now_sim
        return True

    if contact.last_observable_sim is None:
        return False
    return now_sim - contact.last_observable_sim < CALLOUT_OBSERVABILITY_GRACE_S


@dataclass
class SightingSpan:
    """A contiguous span of sim-time during which one source continuously
    contributed observations to a contact. Not merged across a source
    change or a gap -- Stage 1 does not define what counts as a "gap" (that
    is a decay/lifecycle question, Stage 2); this stage only extends the
    current span when the *same source* observes again, and opens a new span
    otherwise."""

    start_sim: float
    end_sim: float
    source: str


@dataclass
class Contact:
    """One persistent belief record. `last_class_raw` is always derived
    from the most recent percept merged into this contact, never from any
    earlier one -- there is no fusion or averaging of classification claims
    (that is `classification`'s job, a separate fold, see below).

    **`last_position` and `last_position_uncertainty_m` are no longer a raw
    percept's own numbers -- `plans/precise-position-belief/plan.md` Stage
    4.** The real state is `position: PositionEstimate`
    (`belief.position_belief`) -- a fused mean (x, z) plus its own 2x2
    covariance, refined by `belief.position_belief.fold_position` on every
    `record()` call (real covariance fusion/triangulation, not a running
    average or a last-writer-wins overwrite -- see that module's docstring).
    `last_position`/`last_position_uncertainty_m` are read-only properties
    derived from `position` (`GeoPosition(x=position.x, z=position.z,
    alt_m=last_alt_m)`, `position.radius_m()` respectively) kept for every
    pre-Stage-4 reader that wants those exact names/shapes -- assigning to
    either raises `AttributeError`, only `record()`/`from_percept()` ever
    change the underlying `position`/`last_alt_m` fields, via `fold_
    position`, never a direct field write. `last_alt_m` is *not* fused (no
    altitude uncertainty model exists) -- it is simply the most recent
    look's own flat-projection altitude (`perception.geometry.
    project_from_bearing_range`'s "target at observer's own altitude"
    convention), same placeholder status it always had.

    `association_over_time.passes_gate`'s 2D gate (Stage 3) budgets `position
    .covariance` (inflated for elapsed motion) against the *incoming*
    percept's own ellipse; gating on the incoming side alone silently
    treated `last_position` as exact, which it is not -- see that module's
    docstring for the live duplication bug this fixes (2026-09-09) and for
    the gate's own anisotropy, now drawn from this real fused covariance
    rather than an isotropic proxy.

    `classification` is `plans/classification-refinement/plan.md` Stage 2's
    addition: the contact's *folded* best classification claim (`belief.
    classification.ClassificationBelief`), monotone non-decreasing in
    specificity except on contradiction -- see that module's docstring for
    the fold rule. Unlike `last_position`/`last_class_raw`, `record` does
    not simply overwrite this with the incoming percept's claim.

    `last_class_raw` is kept anyway, with its exact original meaning (the
    most recent percept's raw classification string), because it -- not
    `classification` -- is `belief.association_over_time`'s gate input: the
    gate asks "is this new percept compatible with what I last *saw*,"
    and feeding it the folded best claim would make the gate progressively
    stricter over a contact's life, eventually rejecting genuine
    re-observations of a contact whose type was refined once. Everything
    user-facing (`tools.py`, `console.py`, events) reads `classification`
    instead. This dual field is a real readability cost, called out here and
    in `classification.py`'s own docstring.

    `classification_lockout_until_sim` is `fold_classification`'s one piece
    of per-contact state: set (or refreshed) only when a fold reports a
    fresh contradiction (`belief.classification.FoldOutcome.contradicted`),
    read back on every subsequent fold to enforce `belief.classification.
    CLASSIFICATION_CONTRADICTION_LOCKOUT_S`.

    `cardinality` is `plans/group-contact-model/plan.md` Stage 1's addition:
    the contact's folded best cardinality claim (`belief.cardinality.
    CardinalityBelief`, via `fold_cardinality`) -- `classification`'s direct
    sibling, same fold-instead-of-overwrite posture. Seeded from the founding
    percept's own `count_bucket` when it carries one (Stage 2: naked-eye's
    cluster-derived count), or `OP_1UNIT` when it does not (the scope/hybrid
    channel, which supplies no count evidence at all -- `record` leaves
    `cardinality` untouched, a hold, whenever a later percept's `count_
    bucket` is also `None`, rather than treating "no evidence" as "exactly
    one"). `cardinality_lockout_until_sim` is `fold_cardinality`'s one piece
    of per-contact state, mirroring `classification_lockout_until_sim`
    exactly.

    `last_emitted_certainty` is Stage 2 (of `plans/pb2-contact-memory/
    plan.md`)'s addition: the `belief.decay.Certainty` this contact held the
    last time `ContactStore.tick` computed one for it, `None` until the
    first `tick()` call after creation. It is written only by `ContactStore.
    tick` (never by `record`/`ingest`) -- `record` updates *what* is known
    about the contact; `tick` is solely responsible for noticing *when that
    knowledge's freshness* has crossed a lifecycle boundary. Kept on
    `Contact` rather than in a side table because it is exactly the
    "last-emitted state" `events.lifecycle_event_kind` needs compared
    against, per contact.

    `last_emitted_attention` is BL-4's twin of `last_emitted_certainty`/
    `last_emitted_classification` (`plans/bl4-attention-events/plan.md`):
    the *effective* attention (`belief.attention.effective_attention`'s
    result -- direct mark folded with area membership) this contact held
    the last time `tick` computed one, `None` until the first `tick()`
    call. Storing the effective value (not just the direct mark) means a
    contact walking into or out of a watched area, with no change to its
    own direct mark, is exactly the kind of transition this comparison
    catches.

    `motion` is `plans/movement-detection/plan.md` Stage 3's addition:
    the contact's folded motion belief (`belief.motion.MotionBelief`, via
    `fold_motion`) -- unlike `classification`/`cardinality`, this is
    `None`-able for the contact's whole life, not just before founding: only
    the naked-eye channel supplies motion evidence at all, so a contact seen
    solely through the scope/hybrid channel never gets a motion percept and
    stays honestly `None` (see `belief.motion`'s module docstring).
    `motion_pending_stop_since_sim` is `fold_motion`'s own demotion-countdown
    state, the asymmetric-fold twin of `classification_lockout_until_sim`/
    `cardinality_lockout_until_sim` above.

    `last_emitted_motion` is `last_emitted_cardinality`'s twin, for `belief.
    events.motion_event_kind`'s comparison -- written only by `ContactStore.
    tick`, never by `record`.

    `last_event_emitted_sim` is BL-4's per-contact-per-kind emission
    cooldown state (`belief.events.EVENT_COOLDOWN_S`): the `t_sim` at which
    an event of each `EventKind` was last actually appended to the log for
    this contact. Deliberately separate from the three `last_emitted_*`
    snapshots above -- those are compared every tick to decide *whether*
    something changed and are always kept current; this dict only gates
    whether a detected change is *allowed to emit* right now. See `belief.
    events`'s module docstring for why this is not the same mechanism as
    `classification.py`'s `CLASSIFICATION_CONTRADICTION_LOCKOUT_S`."""

    id: str
    #: The fused believed position -- `belief.position_belief.
    #: PositionEstimate` (mean x/z + 2x2 covariance + `as_of_sim`). Read via
    #: `last_position`/`last_position_uncertainty_m` below, not directly, by
    #: every caller that predates Stage 4.
    position: PositionEstimate
    #: The most recent look's own flat-projection altitude -- not fused
    #: (no altitude uncertainty model exists). See `last_position`'s own
    #: docstring paragraph above.
    last_alt_m: float
    last_class_raw: str
    classification: ClassificationBelief
    #: Defaults to a freshly-seeded `OP_1UNIT` claim (rather than being a
    #: required constructor argument) so every existing direct `Contact(...)`
    #: call site -- test helpers included -- keeps compiling and behaving
    #: exactly as before (`plans/group-contact-model/plan.md` Stage 1's
    #: merge criterion: the existing suite passes untouched).
    #: `established_sim=0.0` here is a construction-time placeholder only;
    #: `from_percept` immediately re-seeds it at the founding percept's own
    #: `t_sim` for every contact actually created through `ContactStore`.
    cardinality: CardinalityBelief = field(
        default_factory=lambda: new_cardinality_belief(OP_1UNIT, 0.0)
    )
    contributing_observation_ids: list[str] = field(default_factory=list)
    first_seen_sim: float = 0.0
    last_seen_sim: float = 0.0
    sighting_spans: list[SightingSpan] = field(default_factory=list)
    classification_lockout_until_sim: float | None = None
    cardinality_lockout_until_sim: float | None = None
    last_emitted_certainty: Certainty | None = None
    #: Stage 3's twin of `last_emitted_certainty`, for `belief.events.
    #: classification_event`'s comparison -- written only by `ContactStore.
    #: tick`, never by `record`.
    last_emitted_classification: ClassificationBelief | None = None
    attention: Attention = "normal"
    attention_source: str | None = None
    last_emitted_attention: Attention | None = None
    #: `plans/group-contact-model/plan.md` Stage 4b's twin of
    #: `last_emitted_classification`, for `belief.events.cardinality_event`'s
    #: comparison -- written only by `ContactStore.tick`, never by `record`.
    last_emitted_cardinality: tuple[int, float] | None = None
    motion: MotionBelief | None = None
    motion_pending_stop_since_sim: float | None = None
    last_emitted_motion: MotionState | None = None
    last_event_emitted_sim: dict[EventKind, float] = field(default_factory=dict)
    #: `plans/watch-reporting/plan.md` Decision 5's kilometre-crossing
    #: bookkeeping -- the whole-kilometre band this contact was last
    #: *announced* at, `None` whenever it is not currently watched or has
    #: never been announced since it started being watched (both the
    #: "never watched yet" and "just re-watched" cases -- see `ContactStore.
    #: tick`'s sixth block for the silent-seed/clear-on-unwatch rules this
    #: field's `None` state drives). Written only by `tick`, never by
    #: `record` -- this is a speech-adjacent bookkeeping field, not a belief
    #: fold.
    last_announced_range_km: int | None = None
    #: `plans/watch-reporting/plan.md` Stage 4's engagement bookkeeping --
    #: the believed engaged/not-engaged state this contact was last
    #: *evaluated* at, `None` whenever it is not currently watched or has
    #: no resolvable envelope (`ContactStore.tick`'s seventh block clears
    #: it, the same "clear on unwatch" rule `last_announced_range_km`
    #: follows). Unlike that field, there is no silent seed -- the first
    #: evaluation after `None` compares against an implicit `False`
    #: ("outside"), so a contact already inside its envelope the moment it
    #: is recognised *does* fire (Decision 1's "seed as outside" rule).
    #: Written only by `tick`, never by `record`.
    last_emitted_engagement: bool | None = None
    #: `fold_motion`'s `motion_pending_stop_since_sim` twin for the LOS
    #: term's asymmetric dwell (`belief.decay.LOS_MASK_CONFIRM_S`,
    #: Decision 5a-ii): the sim-time a **masked** LOS sample first started
    #: holding continuously, reset to `None` the instant any sample comes
    #: back clear. `None` means "not currently in a masked run."
    los_masked_since_sim: float | None = None
    #: `plans/sortie-2026-09-26-fixes/plan.md` Stage 1 (Fix A) -- the sim
    #: time this contact's current true bearing was last confirmed to clear
    #: `perception.cockpit_mask.is_visible`, updated every tick it does.
    #: `None` means "never confirmed observable" -- a contact founded from a
    #: non-naked-eye percept that has been behind the mask since it came
    #: into existence, with no sighting memory to draw on. This tracks
    #: whether Petrovich could physically see this bearing *at all* right
    #: now (any gaze direction), not whether a threat's terrain LOS to us is
    #: masked (`los_masked_since_sim`'s own concern). Drives the grace
    #: window (`belief.decay.CALLOUT_OBSERVABILITY_GRACE_S`) on `ContactStore.
    #: tick`'s fifth and sixth blocks' spontaneous callouts, via `_callout_
    #: may_speak` -- see that function's own docstring for why this is "last
    #: confirmed observable" rather than "how long has it been failing."
    last_observable_sim: float | None = None
    #: `plans/dcs-driven-los/plan.md` (X-B29) -- the most recent look's own
    #: DCS-driven LOS fact (`building_clear and terrain_clear`), set
    #: unconditionally from `Percept.live_los_clear` in `record()`/
    #: `from_percept()`. An overwrite, not a fold -- the same semantics as
    #: `last_class_raw` (a raw most-recent-look value), since there is no
    #: ordering/specificity relation between "clear" and "masked" to fold
    #: over. `None` means "no live verdict as of the most recent look" --
    #: never a guessed clear/masked. `ContactStore.tick`'s engagement term
    #: treats this as meaningful only while the contact is within
    #: `belief.decay.OBSERVED_WINDOW_S` of its own `last_seen_sim`, and as
    #: unknown (fail-open) otherwise -- see that block's own comments.
    live_los_clear: bool | None = None

    @property
    def last_position(self) -> GeoPosition:
        """`position`'s (x, z) plus `last_alt_m` -- see `position`'s own
        field docstring above. Read-only: `record`/`from_percept` are the
        only writers, both via `fold_position`, never a direct assignment
        to this property."""
        return GeoPosition(x=self.position.x, z=self.position.z, alt_m=self.last_alt_m)

    @property
    def last_position_uncertainty_m(self) -> float:
        """`position.radius_m()` -- the fused covariance's own scalar
        reduction, kept under this exact pre-Stage-4 name for every reader
        that wants a single number rather than the full `PositionEstimate`.
        Read-only, same posture as `last_position` above."""
        return self.position.radius_m()

    def record(self, percept: Percept) -> None:
        """Fold `percept` into this contact's last-known state. Called only
        by `ContactStore.ingest`, which has already decided this percept
        belongs to this contact (via the gate in `belief.
        association_over_time`, or as this contact's founding observation).

        `position` is *fused* here (`belief.position_belief.fold_position`),
        not overwritten -- unlike `last_class_raw`/`classification`'s split,
        there is no separate "most recent raw position" field any more: the
        percept-gate (`association_over_time.passes_gate`) reads `position.
        covariance` directly (see that module's docstring), so there is
        nothing left that needs the pre-fusion number."""
        look_position = implied_position(percept)
        prior_position = self.position
        observer = GeoPosition(
            x=percept.ownship_at_observation.x,
            z=percept.ownship_at_observation.z,
            alt_m=percept.ownship_at_observation.alt_m,
        )
        fused_position = fold_position(
            prior_position,
            x=look_position.x,
            z=look_position.z,
            uncertainty=percept_position_uncertainty(percept),
            look_bearing_deg=percept.bearing_deg,
            t_sim=percept.t_sim,
        )
        self.position = clamp_to_detection_envelope(
            fused_position,
            prior_position,
            observer,
            _max_detection_range_m(percept.source),
        )
        self.last_alt_m = look_position.alt_m
        self.last_class_raw = percept.classification_raw
        incoming = new_classification_belief(
            value=percept.classification_raw,
            level=SpecificityLevel(percept.classification_level),
            established_sim=percept.t_sim,
        )
        outcome = fold_classification(
            self.classification,
            incoming,
            percept.t_sim,
            self.classification_lockout_until_sim,
        )
        self.classification = outcome.classification
        if outcome.contradicted:
            self.classification_lockout_until_sim = (
                percept.t_sim + CLASSIFICATION_CONTRADICTION_LOCKOUT_S
            )
        if percept.count_bucket is not None:
            incoming_cardinality = cardinality_belief_from_bucket_name(
                percept.count_bucket, established_sim=percept.t_sim
            )
            cardinality_outcome = fold_cardinality(
                self.cardinality,
                incoming_cardinality,
                percept.t_sim,
                self.cardinality_lockout_until_sim,
            )
            self.cardinality = cardinality_outcome.cardinality
            if cardinality_outcome.contradicted:
                self.cardinality_lockout_until_sim = (
                    percept.t_sim + CARDINALITY_CONTRADICTION_LOCKOUT_S
                )
        motion_outcome = fold_motion(
            self.motion,
            percept.apparent_motion,
            percept.t_sim,
            self.motion_pending_stop_since_sim,
        )
        self.motion = motion_outcome.motion
        self.motion_pending_stop_since_sim = motion_outcome.pending_stop_since_sim
        self.contributing_observation_ids.append(percept.observation_id)
        self.last_seen_sim = percept.t_sim
        self.live_los_clear = percept.live_los_clear
        self._extend_or_open_span(percept)

    def _extend_or_open_span(self, percept: Percept) -> None:
        if self.sighting_spans and self.sighting_spans[-1].source == percept.source:
            self.sighting_spans[-1].end_sim = percept.t_sim
        else:
            self.sighting_spans.append(
                SightingSpan(
                    start_sim=percept.t_sim,
                    end_sim=percept.t_sim,
                    source=percept.source,
                )
            )

    @staticmethod
    def from_percept(contact_id: str, percept: Percept) -> Contact:
        """Found a new contact from its first percept. `position` is
        founded via `fold_position(None, ...)` -- the same call `record`
        makes on every subsequent percept, just with no prior to fuse
        against -- so a founding contact and a re-observed one build their
        first covariance identically (`belief.position_belief.
        fold_position`'s own docstring)."""
        look_position = implied_position(percept)
        observer = GeoPosition(
            x=percept.ownship_at_observation.x,
            z=percept.ownship_at_observation.z,
            alt_m=percept.ownship_at_observation.alt_m,
        )
        founding_position = fold_position(
            None,
            x=look_position.x,
            z=look_position.z,
            uncertainty=percept_position_uncertainty(percept),
            look_bearing_deg=percept.bearing_deg,
            t_sim=percept.t_sim,
        )
        contact = Contact(
            id=contact_id,
            position=clamp_to_detection_envelope(
                founding_position,
                None,
                observer,
                _max_detection_range_m(percept.source),
            ),
            last_alt_m=look_position.alt_m,
            last_class_raw=percept.classification_raw,
            classification=new_classification_belief(
                value=percept.classification_raw,
                level=SpecificityLevel(percept.classification_level),
                established_sim=percept.t_sim,
            ),
            cardinality=(
                cardinality_belief_from_bucket_name(
                    percept.count_bucket, established_sim=percept.t_sim
                )
                if percept.count_bucket is not None
                else new_cardinality_belief(OP_1UNIT, percept.t_sim)
            ),
            # `held=None` -- `fold_motion` adopts the founding percept's own
            # motion evidence outright (its own "no prior claim to demote
            # away from" rule), or stays `None` when the founding percept
            # carries no motion evidence at all (`belief.motion`'s module
            # docstring).
            motion=fold_motion(
                None, percept.apparent_motion, percept.t_sim, None
            ).motion,
            first_seen_sim=percept.t_sim,
            last_seen_sim=percept.t_sim,
            live_los_clear=percept.live_los_clear,
        )
        contact.contributing_observation_ids.append(percept.observation_id)
        contact.sighting_spans.append(
            SightingSpan(
                start_sim=percept.t_sim, end_sim=percept.t_sim, source=percept.source
            )
        )
        return contact


class ContactStore:
    """Holds all known contacts plus an append-only observation log keyed by
    `Observation.id`. `ingest` is the only way a `Contact` is created or
    updated; `tick` is Stage 1's placeholder for Stage 2's decay/lifecycle
    ticker."""

    def __init__(self) -> None:
        self._contacts: dict[str, Contact] = {}
        self._observations: dict[str, Observation] = {}
        self._events: list[Event] = []
        self._areas: dict[str, AttentionArea] = {}
        self._acknowledged_event_ids: set[str] = set()
        #: `plans/contact-duplication-ambiguity-runaway/plan.md`'s
        #: object-permanence index: every `Observation.id` ever ingested,
        #: mapped to the contact it was folded into. Populated for *every*
        #: observation regardless of which path (continuity, gate merge, or
        #: founding) produced that contact -- a later percept's
        #: `continues_observation_id` may name an observation from a
        #: gate-merge poll, not only a prior continuity hit, so this index
        #: must cover all three. Never pruned or re-keyed -- an id minted 50
        #: polls ago still resolves, which is what makes gap-length
        #: irrelevant to whether continuity *can* resolve (see `ingest`'s
        #: docstring for the separate question of whether it is *trusted*).
        self._observation_id_to_contact_id: dict[str, str] = {}
        self._next_contact_number = 0
        self._next_event_number = 0
        self._next_area_number = 0
        #: `plans/group-reporting/plan.md` Stage 2 -- the associative
        #: group-membership belief, reconciled once per `tick()` call from
        #: the current `Contact` set (a cross-contact pass, so it cannot
        #: live inside the per-contact loop above). See `belief.groups`'
        #: module docstring for the cohesion rule and the split/merge
        #: reconciliation it performs against its own prior state.
        self._groups = GroupStore()

    @property
    def contacts(self) -> list[Contact]:
        """All known contacts, insertion order."""
        return list(self._contacts.values())

    @property
    def observations(self) -> dict[str, Observation]:
        """The append-only observation log, keyed by `Observation.id`. A
        read-only view -- callers must not mutate the returned dict."""
        return dict(self._observations)

    @property
    def events(self) -> list[Event]:
        """Every lifecycle event materialised so far by `tick`, in the order
        it was emitted. A read-only view -- callers must not mutate the
        returned list."""
        return list(self._events)

    @property
    def areas(self) -> list[AttentionArea]:
        """Every registered `AttentionArea`, insertion order (BL-4). A
        read-only view -- callers must not mutate the returned list."""
        return list(self._areas.values())

    @property
    def groups(self) -> list[Group]:
        """Every currently persisted associative group (`plans/
        group-reporting/plan.md` Stage 2), insertion order. A read-only
        view -- callers must not mutate the returned list."""
        return self._groups.groups

    def group_for_contact(self, contact_id: str) -> Group | None:
        """The `Group` `contact_id` currently belongs to, or `None` --
        delegates to `belief.groups.GroupStore.group_for_contact`."""
        return self._groups.group_for_contact(contact_id)

    def contact(self, contact_id: str) -> Contact | None:
        """Named lookup of one `Contact` by id, or `None` if it does not
        exist -- `plans/contact-report-flood/plan.md` Stage 1. Nothing
        outside `ingest`/`_resolve_continuity` could resolve an id back to
        a `Contact` from outside this module before this; added for
        `belief.callouts.CalloutScheduler`'s merge-echo suppression check,
        which needs to look up *other* contacts than the one an event
        already names."""
        return self._contacts.get(contact_id)

    def mark_group_spoken(
        self,
        group_id: str,
        signature: str,
        now_sim: float,
        *,
        member_contact_ids: frozenset[str] = frozenset(),
        leading_contact_id: str | None = None,
        differentiated: bool = False,
    ) -> bool:
        """Delegates to `belief.groups.GroupStore.mark_spoken` -- see that
        method's docstring."""
        return self._groups.mark_spoken(
            group_id,
            signature,
            now_sim,
            member_contact_ids=member_contact_ids,
            leading_contact_id=leading_contact_id,
            differentiated=differentiated,
        )

    @property
    def unacknowledged_events(self) -> list[Event]:
        """Every materialised event whose `id` has not been passed to
        `acknowledge_event` yet, in emission order (BL-4's event queue).
        Acknowledged ids are tracked in a plain `set[str]`, not a mutable
        field on the frozen `Event` dataclass -- keeps every existing
        `Event` construction site and test untouched (`plans/
        bl4-attention-events/plan.md`'s explicit design choice)."""
        return [
            event
            for event in self._events
            if event.id not in self._acknowledged_event_ids
        ]

    def acknowledge_event(self, event_id: str) -> bool:
        """Mark `event_id` acknowledged. Returns whether an event with that
        id actually exists in the log -- acknowledging an unknown id is not
        silently accepted, mirroring `ingest`/`tick`'s own "unknown id
        returns `False`" convention elsewhere in this module's siblings
        (`tools.py`'s `watch`/`unwatch`)."""
        if not any(event.id == event_id for event in self._events):
            return False
        self._acknowledged_event_ids.add(event_id)
        return True

    def add_area(
        self,
        center: GeoPosition,
        radius_m: float | None,
        level: Attention,
        source: str,
        sector: Sector | None = None,
        relative_sector: RelativeSector | None = None,
        relative_clock_hour: int | None = None,
    ) -> AttentionArea:
        """Register a new `AttentionArea`, minting its `id` the same way
        `_new_contact_id`/`_new_event_id` mint theirs. Returns the stored
        `AttentionArea` (with its minted `id`) so a caller (`tools.
        watch_area`) can report it back.

        Passing `relative_sector` or `relative_clock_hour` (Stage 5,
        `plans/voice-command-completeness/plan.md` Decision 5) makes this
        an ownship-anchored area (`belief.attention`'s module docstring,
        second kind): `center` is then only its initial projection,
        replaced on every `reproject_relative_areas` call. `sector`,
        `relative_sector`, and `relative_clock_hour` are pairwise mutually
        exclusive -- they are three different frames for the same angular
        filter, and silently letting one win would make the resulting
        area's behaviour depend on `area_wedge_deg`'s precedence rule
        rather than on what the caller asked for."""
        directional = [
            name
            for name, value in (
                ("sector", sector),
                ("relative_sector", relative_sector),
                ("relative_clock_hour", relative_clock_hour),
            )
            if value is not None
        ]
        if len(directional) > 1:
            raise ValueError(
                "add_area takes at most one of sector (compass-absolute), "
                "relative_sector (ownship-relative), or relative_clock_hour "
                "(ownship-relative, single o'clock hour) -- they are "
                f"different frames for the same angular filter, got {directional!r}"
            )
        area = AttentionArea(
            id=self._new_area_id(),
            center=center,
            radius_m=radius_m,
            level=level,
            source=source,
            sector=sector,
            relative_sector=relative_sector,
            relative_clock_hour=relative_clock_hour,
        )
        self._areas[area.id] = area
        return area

    def reproject_relative_areas(
        self, ownship_position: GeoPosition, heading_true_deg: float
    ) -> int:
        """Re-anchor every ownship-anchored area onto ownship's current
        pose, returning how many were updated (0 when none are registered,
        the overwhelmingly common case).

        Called once per telemetry tick from `logger.py`'s `Runner.run_once`,
        *before* `ingest`/`tick`, so the same tick's contacts are judged
        against a fresh projection rather than the previous tick's
        (`plans/f10-command-vocabulary/plan.md` D2). Fixed ground areas are
        returned unchanged by `project_relative_area`, so this is safe to
        call with any mix of the two kinds."""
        updated = 0
        for area_id, area in self._areas.items():
            projected = project_relative_area(area, ownship_position, heading_true_deg)
            if projected is not area:
                self._areas[area_id] = projected
                updated += 1
        return updated

    def get_area(self, area_id: str) -> AttentionArea | None:
        """Look up a currently-registered `AttentionArea` by id, or `None`
        if it is not (or no longer) registered. `belief.tasks.TaskStore.
        tick` uses this to resolve a task's area against its live
        projection each tick rather than trusting `PendingIntent.area`'s
        captured reference, which `reproject_relative_areas` above can
        silently leave stale (it replaces the stored entry via
        `dataclasses.replace`, a new object, rather than mutating in
        place) -- see that method's docstring and `belief.tasks`'s module
        docstring for the full rationale."""
        return self._areas.get(area_id)

    def remove_area(self, area_id: str) -> bool:
        """Unregister an `AttentionArea`. Returns whether `area_id` was
        found."""
        if area_id not in self._areas:
            return False
        del self._areas[area_id]
        return True

    def ingest(self, observations: list[Observation], now_sim: float) -> list[Contact]:
        """Run each of `observations` through the percept->contact gate
        against every existing contact and create/update accordingly.

        **Object-permanence shortcut, checked first**
        (`plans/contact-duplication-ambiguity-runaway/plan.md`): if the
        percept's `continues_observation_id` resolves (via
        `_observation_id_to_contact_id`) to a contact, and `belief.decay.
        object_id_continuity_valid` still trusts that contact's identity as
        of `now_sim`, the percept is folded directly onto it -- the
        spatial/class gate is skipped entirely. The class-compatibility
        check (`belief.classification.class_compatibility`) is still applied
        as defense-in-depth against the one residual risk this shortcut
        cannot rule out (DCS reusing an `object_id` across a real
        kill/respawn boundary, see the plan's Risks section): an
        incompatible class falls through to the gate identically to an
        unresolved or expired match, never a forced merge. There is no third
        code path -- only "continuity trusted" vs. "continuity not
        available, use the gate."

        **Gate/ambiguity decision rule** (`plans/pb2-contact-memory/plan.md`
        Stage 1), reached whenever continuity does not apply -- a founding
        observation, a non-correlating reacquisition, or an expired/
        incompatible continuity match: exactly one existing contact passes
        both gates -> merge into it; zero, or two-or-more, -> create a new
        contact. Ambiguity between two-or-more candidates is deliberately
        never resolved by a best-match tiebreak -- see
        `association_over_time`'s module docstring.

        **Same-source, same-poll exclusion** (`plans/group-contact-model/
        plan.md` Stage 3a): two observations sharing both `source` and
        `t_sim` may never resolve to the same contact via the gate branch
        above. This rests on a precondition about both current sources that
        must hold for this rule to be sound, and is not re-checked here --
        post-Stage-2 naked-eye emits one `Observation` per resolution
        cluster (two clusters are separable by construction) and the
        scope/hybrid channel emits one `Observation` per DCS `object_id`
        (two object ids are two real objects), so **neither source can ever
        emit two reports of the same thing in one poll**. A future source
        that could would violate this rule's premise and must be excluded
        from it explicitly.

        Enforced with a read-only pre-scan over `observations`, before the
        main loop below: `_resolve_continuity` is evaluated once per
        observation and memoized (so the main loop never calls it a second
        time -- calling it twice could let a contact refreshed mid-batch
        change its own continuity verdict mid-batch), and every observation
        that resolves by continuity records its contact id under
        `claimed[(source, t_sim)]`. The pre-scan mutates nothing else. Its
        purpose is order-independence: the majority child of a split (see
        `naked_eye_source._build_observations`) claims the parent contact by
        continuity before any minority child reaches the gate, regardless of
        the order `cluster_candidates`/`_build_observations` happened to
        emit them in -- neither defines an order. The main loop then filters
        gate candidates by `candidate.id not in claimed[(source, t_sim)]`
        *before* counting how many pass, so a percept whose only candidates
        are all claimed this poll sees zero and founds a new contact -- the
        same outcome the ambiguity rule already produces, through the same
        code path. Whichever contact an observation ends up on -- merged
        (by continuity or the gate) or founded -- is added to
        `claimed[(source, t_sim)]` before the next observation in the batch
        is processed, so three same-poll, same-source observations against
        one old contact correctly produce three separate contacts rather
        than the third silently merging into the second's brand-new one.

        The gate's own formula (`association_over_time.passes_gate`) is
        untouched by this rule -- it is association bookkeeping, the same
        category as `_resolve_continuity`, not a change to the gate's
        geometry.

        Returns the list of `Contact`s touched by this call, one per
        observation processed, in the same order -- a contact may appear
        more than once if multiple observations in this batch merged into
        it.
        """
        continuity_by_observation_id: dict[str, Contact | None] = {}
        claimed: dict[tuple[str, float], set[str]] = {}
        for observation in observations:
            percept = percept_of(observation)
            resolved = self._resolve_continuity(percept, now_sim)
            continuity_by_observation_id[observation.id] = resolved
            if resolved is not None:
                claimed.setdefault((percept.source, percept.t_sim), set()).add(
                    resolved.id
                )

        touched: list[Contact] = []
        for observation in observations:
            self._observations[observation.id] = observation
            percept = percept_of(observation)
            claim_key = (percept.source, percept.t_sim)

            contact = continuity_by_observation_id[observation.id]
            if contact is not None:
                contact.record(percept)
            else:
                already_claimed = claimed.get(claim_key, set())
                passing = [
                    candidate
                    for candidate in self._contacts.values()
                    if candidate.id not in already_claimed
                    and passes_gate(percept, candidate, now_sim)
                ]

                if len(passing) == 1:
                    contact = passing[0]
                    contact.record(percept)
                else:
                    contact = Contact.from_percept(self._new_contact_id(), percept)
                    self._contacts[contact.id] = contact

            claimed.setdefault(claim_key, set()).add(contact.id)
            self._observation_id_to_contact_id[observation.id] = contact.id
            touched.append(contact)
        return touched

    def _resolve_continuity(self, percept: Percept, now_sim: float) -> Contact | None:
        """The object-permanence shortcut lookup for one percept -- `None`
        whenever continuity does not apply, in which case `ingest` falls
        through to the ordinary gate. See `ingest`'s docstring for the full
        decision (unresolved index lookup, expired `object_id_continuity_
        valid`, and incompatible class are all treated identically here)."""
        if percept.continues_observation_id is None:
            return None
        contact_id = self._observation_id_to_contact_id.get(
            percept.continues_observation_id
        )
        if contact_id is None:
            return None
        contact = self._contacts.get(contact_id)
        if contact is None:
            return None
        if not object_id_continuity_valid(contact, now_sim):
            return None
        if (
            class_compatibility(percept.classification_raw, contact.last_class_raw)
            == "incompatible"
        ):
            return None
        return contact

    def tick(
        self,
        now_sim: float,
        ownship: OwnshipState | None = None,
    ) -> None:
        """Materialise lifecycle, classification, *and* attention events
        for every known contact as of `now_sim`. For each contact, per event
        kind: compute its current state, compare against the contact's own
        last-emitted snapshot of that state, append the resulting `Event`
        (if any, and if `belief.events.EVENT_COOLDOWN_S` has elapsed since
        this contact last actually emitted that kind -- BL-4's chatter
        suppression) to the log, then update the snapshot regardless of
        whether an event fired or was suppressed by cooldown -- the
        comparison on the *next* `tick()` call must be against this call's
        result, not the last emitted event (see `Contact.last_event_emitted_
        sim`'s docstring for why the cooldown check and the snapshot update
        are deliberately independent).

        **Ordering, per contact: lifecycle event first, then classification,
        then cardinality, then motion, then attention, then range-crossing**
        (`plans/classification-refinement/plan.md` Stage 3, extended by
        `plans/bl4-attention-events/plan.md`, then `plans/
        group-contact-model/plan.md` Stage 4b, then `plans/
        movement-detection/plan.md` Stage 3, then `plans/watch-reporting/
        plan.md` Stage 2) -- a `CONTACT_DETECTED` must precede that same
        contact's first classification refinement, cardinality/motion
        change, or attention change, never follow it. Cardinality and
        motion both sit ahead of attention since all three are
        identity/state-shaped beliefs about what/how-many/whether-moving,
        and attention's own event should still see the contact's fully
        up-to-date facts first. Range-crossing sits last and reuses
        `current_attention` from the attention block directly, rather than
        recomputing `belief.attention.effective_attention` a second time --
        it needs to already know whether this contact is watched.

        **`ownship` (`plans/watch-reporting/plan.md` Stage 2) drives the
        sixth block alone** -- every existing caller passes only `now_sim`,
        which leaves `ownship` at its `None` default and makes the
        range-crossing block a no-op (see that block's own docstring). Not
        threaded into any of the five pre-existing blocks above, which have
        no use for ownship position.

        **An eighth, cross-contact block runs once per `tick()` call, after
        every contact's per-contact blocks above** (`plans/
        group-reporting/plan.md` Stage 2): associative group-membership
        reconciliation (`belief.groups.GroupStore.reconcile`), placed after
        attention/engagement rather than inside the per-contact loop, since
        it is not a per-contact computation and a group's own disclosure
        (Stage 3) needs each member's already-current attention/threat
        state to render from.

        **`reconcile`'s input is filtered to not-`lost` contacts** (`BL-B23`,
        `body-layer/BACKLOG.md`, found by the Performance Reviewer during
        `plans/group-cohesion-redesign/performance.md`): `_cluster_contacts`
        is O(n^2) in whatever it is handed, and `self._contacts` has no
        delete path at all, so passing it the full historical set makes
        clustering cost scale with **total objects ever folded over the
        sortie**, not with how many are actually out there right now --
        measured there at 70-180 ms/tick for the 500-800-contact band a
        long mission plausibly accumulates. The fix is **not** to prune
        `_contacts` (a `lost` contact is still memory Petrovich should
        have -- `describe_contact`/`get_contact_history` must keep
        answering for it); it is to keep a `lost` contact out of
        *clustering* specifically, the one O(n^2) consumer, via the exact
        same `belief.decay.certainty_of` ladder the first block above
        already computes `current_certainty` from -- no new timestamp, no
        new per-contact field. Re-admission is automatic, not a special
        case: `certainty_of` is a pure function of `now_sim - contact.
        last_seen_sim`, so a contact `ingest` reobserves this same poll
        (which runs before `tick`, see `logger.Runner.run_once`) already
        reads `elapsed_s == 0` here and is included again, with no memory
        of ever having been excluded. Group *coherence* across a member's
        exclusion needs no extra code either: `GroupStore.reconcile`
        already recomputes every cluster from scratch each call and
        reconciles by majority-member-overlap (its own docstring) -- a
        `Group` missing a now-excluded member simply reconciles to a
        smaller cluster (same id, if still >= `GROUP_REPORTING_MIN_
        MEMBERS`) or is dropped (if not), exactly as it already handles any
        other membership change.

        Driven purely by `now_sim`, never wall clock -- calling `tick`
        repeatedly with the same `now_sim` is idempotent after the first
        call (no repeated events), since both snapshots are already up to
        date by then. This is what preserves BL-0's replay determinism: the
        same recorded stream, ticked at the same sim-times, always produces
        the same event log."""
        for contact in self._contacts.values():
            current_certainty = certainty_of(contact, now_sim)
            kind = lifecycle_event_kind(
                contact.last_emitted_certainty, current_certainty
            )
            if kind is not None and self._cooldown_elapsed(contact, kind, now_sim):
                self._events.append(
                    Event(
                        id=self._new_event_id(),
                        contact_id=contact.id,
                        kind=kind,
                        t_sim=now_sim,
                        certainty=current_certainty,
                    )
                )
                contact.last_event_emitted_sim[kind] = now_sim
            contact.last_emitted_certainty = current_certainty

            direction = classification_event(
                contact.last_emitted_classification, contact.classification
            )
            if direction is not None and self._cooldown_elapsed(
                contact, CONTACT_CLASSIFICATION_CHANGED, now_sim
            ):
                self._events.append(
                    Event(
                        id=self._new_event_id(),
                        contact_id=contact.id,
                        kind=CONTACT_CLASSIFICATION_CHANGED,
                        t_sim=now_sim,
                        certainty=current_certainty,
                        previous_classification=(
                            contact.last_emitted_classification.value
                            if contact.last_emitted_classification is not None
                            else None
                        ),
                        classification=contact.classification.value,
                        direction=direction,
                    )
                )
                contact.last_event_emitted_sim[CONTACT_CLASSIFICATION_CHANGED] = now_sim
            contact.last_emitted_classification = contact.classification

            current_cardinality = (contact.cardinality.lo, contact.cardinality.hi)
            cardinality_kind = cardinality_event(
                contact.last_emitted_cardinality, current_cardinality
            )
            if cardinality_kind is not None and self._cooldown_elapsed(
                contact, CONTACT_CARDINALITY_CHANGED, now_sim
            ):
                self._events.append(
                    Event(
                        id=self._new_event_id(),
                        contact_id=contact.id,
                        kind=CONTACT_CARDINALITY_CHANGED,
                        t_sim=now_sim,
                        certainty=current_certainty,
                        previous_cardinality=contact.last_emitted_cardinality,
                        cardinality=current_cardinality,
                    )
                )
                contact.last_event_emitted_sim[CONTACT_CARDINALITY_CHANGED] = now_sim
            contact.last_emitted_cardinality = current_cardinality

            # `plans/sortie-2026-09-26-fixes/plan.md` Stage 1 (Fix A):
            # computed once per contact per tick (when `ownship` is given)
            # and reused by both this block and the sixth block below --
            # both are spontaneous-callout paths with the identical
            # structural gap (no visibility check of any kind), per
            # Decision 4.2's choice to fix `CONTACT_MOTION_CHANGED`
            # alongside `CONTACT_RANGE_CROSSED`. `ownship is None` (every
            # pre-existing caller that omits it) leaves this `True` -- a
            # true no-op, matching this block's pre-fix behaviour exactly,
            # since there is no bearing to check without ownship.
            observable_or_grace = (
                _callout_may_speak(contact, ownship, now_sim)
                if ownship is not None
                else True
            )

            current_motion: MotionState | None = (
                contact.motion.state if contact.motion is not None else None
            )
            motion_kind = motion_event_kind(contact.last_emitted_motion, current_motion)
            if (
                motion_kind is not None
                and observable_or_grace
                and self._cooldown_elapsed(contact, CONTACT_MOTION_CHANGED, now_sim)
            ):
                self._events.append(
                    Event(
                        id=self._new_event_id(),
                        contact_id=contact.id,
                        kind=CONTACT_MOTION_CHANGED,
                        t_sim=now_sim,
                        certainty=current_certainty,
                        previous_motion=contact.last_emitted_motion,
                        motion=current_motion,
                    )
                )
                contact.last_event_emitted_sim[CONTACT_MOTION_CHANGED] = now_sim
            contact.last_emitted_motion = current_motion

            current_attention, _area_id = effective_attention(
                contact.attention, contact.last_position, self.areas
            )
            attention_kind = attention_event_kind(
                contact.last_emitted_attention, current_attention
            )
            if attention_kind is not None and self._cooldown_elapsed(
                contact, CONTACT_ATTENTION_CHANGED, now_sim
            ):
                self._events.append(
                    Event(
                        id=self._new_event_id(),
                        contact_id=contact.id,
                        kind=CONTACT_ATTENTION_CHANGED,
                        t_sim=now_sim,
                        certainty=current_certainty,
                        previous_attention=contact.last_emitted_attention,
                        attention=current_attention,
                    )
                )
                contact.last_event_emitted_sim[CONTACT_ATTENTION_CHANGED] = now_sim
            contact.last_emitted_attention = current_attention

            # Sixth block: whole-kilometre range crossings for a watched
            # contact (`plans/watch-reporting/plan.md` Decisions 1/5/5a).
            # **Gated (and its own bookkeeping kept) at emission, not via a
            # pure comparison function in `events.py`** -- unlike every
            # block above, `last_announced_range_km` is only meaningful for
            # a watched contact, and computing/emitting it for every
            # contact in the theatre would flood the event log (see
            # `CONTACT_RANGE_CROSSED`'s own docstring).
            if ownship is not None:
                is_watched = current_attention in ("watch", "priority")
                if not is_watched:
                    # Decision 1: clear on un-watch so a re-watched contact
                    # re-seeds rather than comparing against a stale mark.
                    contact.last_announced_range_km = None
                elif contact.last_announced_range_km is None:
                    # Decision 1: silent seed -- the first tick this
                    # contact is watched (or the first tick after being
                    # re-watched), emit nothing.
                    observer = GeoPosition(
                        x=ownship.x, z=ownship.z, alt_m=ownship.alt_m
                    )
                    contact.last_announced_range_km = math.floor(
                        range_m(observer, contact.last_position) / 1000.0
                    )
                else:
                    observer = GeoPosition(
                        x=ownship.x, z=ownship.z, alt_m=ownship.alt_m
                    )
                    range_m_value = range_m(observer, contact.last_position)
                    current_km = math.floor(range_m_value / 1000.0)
                    if (
                        current_km != contact.last_announced_range_km
                        and current_km <= WATCH_RANGE_REPORT_MAX_KM
                    ):
                        # Decision 5a-i: the deadband is the belief's own
                        # down-range uncertainty, floored/ceilinged rather
                        # than a bare tuned constant.
                        sigma_m = contact.position.range_uncertainty_m(observer)
                        if sigma_m <= RANGE_CROSS_MAX_SIGMA_M:
                            # The single km-mark boundary between the old
                            # and new bands -- for an adjacent (+-1 km)
                            # crossing, the one shared edge; for a rarer
                            # multi-km jump in one tick (e.g. a
                            # reacquisition after a gap), the first edge
                            # outside the narrower of the two bands.
                            boundary_km = (
                                min(current_km, contact.last_announced_range_km) + 1
                            )
                            deadband_m = max(RANGE_CROSS_MIN_DEADBAND_M, sigma_m)
                            past_deadband = (
                                abs(range_m_value - boundary_km * 1000.0) >= deadband_m
                            )
                            # Decision 5: gate on freshness, not just the
                            # arithmetic -- a decayed position must never
                            # manufacture a crossing nobody observed. An
                            # `"estimated"` contact keeps its own last-
                            # announced mark untouched (resumes announcing
                            # on reacquisition), which is why this check
                            # guards the field update below too, not only
                            # the event.
                            fresh = certainty_of(contact, now_sim) in (
                                "observed",
                                "tracked",
                            )
                            # Fix A (Stage 1): the observability gate
                            # governs both the event and the `last_
                            # announced_range_km` update, matching `fresh`'s
                            # own shape immediately above -- a contact that
                            # has been unobservable past the grace window
                            # must not silently adopt a new baseline either,
                            # the same "nobody observed it" reasoning as the
                            # freshness gate.
                            if past_deadband and fresh and observable_or_grace:
                                if self._cooldown_elapsed(
                                    contact, CONTACT_RANGE_CROSSED, now_sim
                                ):
                                    self._events.append(
                                        Event(
                                            id=self._new_event_id(),
                                            contact_id=contact.id,
                                            kind=CONTACT_RANGE_CROSSED,
                                            t_sim=now_sim,
                                            certainty=current_certainty,
                                            previous_range_km=contact.last_announced_range_km,
                                            range_km=current_km,
                                        )
                                    )
                                    contact.last_event_emitted_sim[
                                        CONTACT_RANGE_CROSSED
                                    ] = now_sim
                                contact.last_announced_range_km = current_km

            # Seventh block: believed engagement state for a watched
            # contact (`plans/watch-reporting/plan.md` Decision 4).
            # Reuses `is_watched` from the sixth block above -- both are
            # only meaningful for a watched contact, and both are gated
            # (and their own bookkeeping kept) at emission, not via a pure
            # comparison function in `events.py` (see `CONTACT_ENGAGEMENT_
            # CHANGED`'s own docstring).
            if ownship is not None:
                envelope = envelope_for(contact.classification) if is_watched else None
                if envelope is None:
                    # Not watched, or `belief.threat.envelope_for` has
                    # nothing for this belief (unresolved, or a class/type
                    # with no threat row) -- clear both pieces of state so
                    # a later re-watch/re-classification re-seeds rather
                    # than comparing against a stale mark.
                    contact.last_emitted_engagement = None
                    contact.los_masked_since_sim = None
                else:
                    observer = GeoPosition(
                        x=ownship.x, z=ownship.z, alt_m=ownship.alt_m
                    )
                    range_m_value = range_m(observer, contact.last_position)
                    prior_engaged = (
                        contact.last_emitted_engagement
                        if contact.last_emitted_engagement is not None
                        else False  # Decision 1: seed as outside
                    )
                    max_range_m = envelope.range_max_m * (
                        ENGAGEMENT_LEAVING_HYSTERESIS if prior_engaged else 1.0
                    )
                    range_ok = envelope.range_min_m <= range_m_value <= max_range_m
                    alt_ok = ownship.alt_agl_m >= envelope.alt_min_m

                    if not (range_ok and alt_ok):
                        # Short-circuit: `current_engaged` is `False`
                        # whatever LOS says, so asking is pure cost. Watch
                        # count is not capped in code either: one
                        # `AttentionArea` ("watch left") can pull an
                        # arbitrary number of contacts into
                        # watch-equivalent attention.
                        #
                        # **The reset is load-bearing, not tidying.**
                        # Skipping the term also skips the masking
                        # bookkeeping below, so without it a contact that
                        # drifts out of range keeps a stale
                        # `los_masked_since_sim`; on re-entry `masked_for_s`
                        # is instantly far past `LOS_MASK_CONFIRM_S` and it
                        # reads as masked on its first tick back. Clearing
                        # it also states the honest thing: a masking dwell
                        # accumulated while the threat could not reach us
                        # measures nothing worth carrying.
                        los_ok = True
                        contact.los_masked_since_sim = None
                    elif (
                        contact.live_los_clear is None
                        or (now_sim - contact.last_seen_sim) > OBSERVED_WINDOW_S
                    ):
                        # `plans/dcs-driven-los/plan.md` (X-B29): no fresh
                        # live verdict -- either the naked-eye channel has
                        # never carried one for this contact this poll, or
                        # it is stale relative to the last time Petrovich
                        # actually looked at it. Correct degradation is
                        # fail-open, the same posture as "no world-model
                        # connection" under the pre-X-B29 design: a watch is
                        # a standing instruction to keep looking, not a
                        # subscription to continuous truth (plan SS11a) --
                        # with no fresh look, there is nothing to clear a
                        # danger state on.
                        los_ok = True
                        contact.los_masked_since_sim = None
                    elif contact.live_los_clear:
                        contact.los_masked_since_sim = None
                        los_ok = True
                    else:
                        if contact.los_masked_since_sim is None:
                            contact.los_masked_since_sim = now_sim
                        masked_for_s = now_sim - contact.los_masked_since_sim
                        # Decision 5a-ii: a masked verdict may only
                        # clear a danger state after holding
                        # continuously for LOS_MASK_CONFIRM_S -- until
                        # then, still treated as having LOS (fail-open,
                        # in the direction of not clearing a warning
                        # too eagerly).
                        los_ok = masked_for_s < LOS_MASK_CONFIRM_S

                    current_engaged = range_ok and alt_ok and los_ok
                    if current_engaged != prior_engaged and self._cooldown_elapsed(
                        contact, CONTACT_ENGAGEMENT_CHANGED, now_sim
                    ):
                        self._events.append(
                            Event(
                                id=self._new_event_id(),
                                contact_id=contact.id,
                                kind=CONTACT_ENGAGEMENT_CHANGED,
                                t_sim=now_sim,
                                certainty=current_certainty,
                                previous_engaged=prior_engaged,
                                engaged=current_engaged,
                            )
                        )
                        contact.last_event_emitted_sim[CONTACT_ENGAGEMENT_CHANGED] = (
                            now_sim
                        )
                    contact.last_emitted_engagement = current_engaged

        # Eighth block, cross-contact: associative group reconciliation
        # (`plans/group-reporting/plan.md` Stage 2). Unlike the seven
        # blocks above, this is not a per-contact computation and cannot
        # live inside the loop -- it runs once per `tick()` call, after
        # every contact's attention (and this call's engagement) state is
        # already current, since a group's own rendering (Stage 3) needs
        # each member's up-to-date attention/threat to lead the line with.
        #
        # `BL-B23`: filtered to not-`lost` contacts -- see this method's
        # own docstring above for why this is the right exclusion
        # (clustering input only) rather than pruning `_contacts` itself.
        self._groups.reconcile(
            [
                contact
                for contact in self._contacts.values()
                if certainty_of(contact, now_sim) != "lost"
            ],
            now_sim,
        )

    @staticmethod
    def _cooldown_elapsed(contact: Contact, kind: EventKind, now_sim: float) -> bool:
        """Whether `EVENT_COOLDOWN_S` has elapsed since `contact` last
        actually emitted an event of `kind` -- `True` (no suppression) if it
        never has. Gates emission only; never gates the state-snapshot
        comparison that decided a change occurred (see `tick`'s docstring)."""
        last_emitted = contact.last_event_emitted_sim.get(kind)
        return last_emitted is None or (now_sim - last_emitted) >= EVENT_COOLDOWN_S

    def _new_contact_id(self) -> str:
        self._next_contact_number += 1
        return f"{_CONTACT_ID_PREFIX}_{self._next_contact_number}"

    def _new_event_id(self) -> str:
        self._next_event_number += 1
        return f"{_EVENT_ID_PREFIX}_{self._next_event_number}"

    def _new_area_id(self) -> str:
        self._next_area_number += 1
        return f"{_AREA_ID_PREFIX}_{self._next_area_number}"
