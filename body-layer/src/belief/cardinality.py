"""The cardinality belief -- `plans/group-contact-model/plan.md` Stage 1
(this module's creation, mechanism only, no behaviour change) and Stage 2
(perception actually supplying cardinality evidence to fold).

Deliberately a sibling of `classification.py`, mirroring its structure line
for line: interval containment stands in for the classification lattice's
specificity levels, and `fold_cardinality` is `fold_classification`'s direct
analogue -- refine on a strictly narrower, containing claim; reinforce on an
identical one; hold on a strictly wider, containing one; contradict (collapse
to the interval *hull*, confidence floored, a lockout armed) on disjoint
claims. See that module's docstring for the fusion-rule shape this one
copies; only the "more specific" test differs (containment rather than a
total-ordered level).

**The ladder is not invented.** `CountBucket`'s eight named intervals are
ED's own vocabulary, taken verbatim from `aircraft-layer/research/
2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` (Session 5
Finding 2: `OP_1UNIT`, `OP_2UNITS`, `OP_3UNITS`, `OP_TO5UNITS`,
`OP_5TO7UNITS`, `OP_8TO10UNITS`, `OP_ABOUT15UNITS`, `OP_MORETHAN15UNITS`) --
the same fragment bank whose clock/range buckets `naked_eye_source.py`
already quantises onto. **`OP_TO5UNITS` (4,5) and `OP_5TO7UNITS` (5,7)
literally overlap at 5** in the plan's own stated boundaries -- kept exactly
as given rather than "fixed," since the instruction is to use ED's names and
boundaries, not invent cleaner ones. `perception.clustering.count_bucket_for`
resolves the ambiguity only where a *single* observed count must pick one
bucket *name*; this module's intervals are used purely for containment
comparison, where a harmless one-count overlap costs nothing.

`UNKNOWN` (0, inf) and `OP_GROUP` (2, inf) are not counts but shapes --
`UNKNOWN` is the cardinality lattice's root (reachable when the fold's hull
spans everything a candidate contradiction could hold), `OP_GROUP` is "several
somethings," ED's own coarse formation fragment paired with `OP_SINGLE`
(single-object clusters just use the exact-count ladder above instead, since
`perception.clustering` always knows the real member count for its own
cluster -- `OP_SINGLE`/`OP_GROUP` are not consumed by this codebase's own
count_bucket_for selection, but are declared here so the full vocabulary this
module's docstring promises is complete from the start, mirroring `decay.py`'s
own "declare the whole table even if not yet consumed" precedent).

**The one honest asymmetry** (plan's own framing, restated here since it
governs this fold rule specifically): counts legitimately change -- a vehicle
drives off, one is destroyed -- and this model cannot distinguish that from a
perception error. Both are handled identically (widen via contradiction, then
re-narrow once the lockout expires), which converges correctly either way at
the cost of a lockout's worth of hedged reporting.

`CARDINALITY_CONTRADICTION_LOCKOUT_S` defaults to the same value as
`classification.CLASSIFICATION_CONTRADICTION_LOCKOUT_S` but is declared
separately, following the precedent `decay.OBJECT_ID_MEMORY_S` set: two
conceptually distinct claims that happen to share a value for now, not
permanently coupled -- revisit this constant specifically if live sessions
show cardinality re-promotion locked out too long or not long enough."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class CountBucket:
    """One named interval on the cardinality ladder -- `hi` is `math.inf`
    for the two open-ended buckets (`OP_MORETHAN15UNITS`, `UNKNOWN`)."""

    name: str
    lo: int
    hi: float


OP_1UNIT: Final[CountBucket] = CountBucket("OP_1UNIT", 1, 1)
OP_2UNITS: Final[CountBucket] = CountBucket("OP_2UNITS", 2, 2)
OP_3UNITS: Final[CountBucket] = CountBucket("OP_3UNITS", 3, 3)
OP_TO5UNITS: Final[CountBucket] = CountBucket("OP_TO5UNITS", 4, 5)
OP_5TO7UNITS: Final[CountBucket] = CountBucket("OP_5TO7UNITS", 5, 7)
OP_8TO10UNITS: Final[CountBucket] = CountBucket("OP_8TO10UNITS", 8, 10)
OP_ABOUT15UNITS: Final[CountBucket] = CountBucket("OP_ABOUT15UNITS", 11, 15)
OP_MORETHAN15UNITS: Final[CountBucket] = CountBucket("OP_MORETHAN15UNITS", 16, math.inf)
#: The lattice's root -- "no cardinality claim at all." Reachable from a
#: contradiction whose hull spans everything the two disagreeing claims
#: could mean.
UNKNOWN: Final[CountBucket] = CountBucket("UNKNOWN", 0, math.inf)
#: ED's coarse formation fragment -- "several somethings," paired with
#: `OP_SINGLE` (not modelled separately here: a single-object cluster just
#: uses `OP_1UNIT`). Not selected by `perception.clustering.
#: count_bucket_for` (which always has a real member count to pick an exact
#: bucket from), but declared for containment comparisons against a
#: hypothetical future coarse-only source.
OP_GROUP: Final[CountBucket] = CountBucket("OP_GROUP", 2, math.inf)

#: The exact-count ladder, ascending -- excludes `UNKNOWN`/`OP_GROUP`
#: (shapes, not counts). `perception.clustering.count_bucket_for` selects
#: from this same set of names.
CARDINALITY_LADDER: Final[tuple[CountBucket, ...]] = (
    OP_1UNIT,
    OP_2UNITS,
    OP_3UNITS,
    OP_TO5UNITS,
    OP_5TO7UNITS,
    OP_8TO10UNITS,
    OP_ABOUT15UNITS,
    OP_MORETHAN15UNITS,
)

#: Every named bucket, by name -- resolves a `perception`-emitted
#: `count_bucket` string (or `"UNKNOWN"`/`"OP_GROUP"`) back to its interval.
_BUCKETS_BY_NAME: Final[dict[str, CountBucket]] = {
    bucket.name: bucket for bucket in (*CARDINALITY_LADDER, UNKNOWN, OP_GROUP)
}


@dataclass(frozen=True, slots=True)
class CardinalityBelief:
    """One contact's held cardinality claim -- `belief.classification.
    ClassificationBelief`'s field-for-field twin. `lo`/`hi` are the held
    interval (inclusive; `hi` may be `math.inf`); `established_sim` is when
    this exact interval was last confirmed, following `ClassificationBelief.
    established_sim`'s own convention (refreshed on refine/reinforce, held
    fixed on a hold, reset to the fold's `now_sim` on a collapse)."""

    lo: int
    hi: float
    confidence: float
    established_sim: float


#: Placeholder starting confidence for a newly-observed cardinality claim --
#: not calibrated, the same posture as `classification._DEFAULT_CONFIDENCE_
#: BY_LEVEL`. A single fixed value rather than a per-bucket table: unlike
#: classification's level (which really does carry different evidentiary
#: weight per level), a fresh count reading is equally trustworthy whether
#: it says "one" or "a group of about ten" -- both come from the same
#: cluster-member-count mechanism.
_DEFAULT_CONFIDENCE: Final[float] = 0.5

#: Reinforcement ceiling/step -- identical values to `classification.py`'s,
#: reused rather than re-derived since both express the same "residual
#: uncertainty never fully resolves" judgment call.
_CONFIDENCE_CEILING: Final[float] = 0.95
_REINFORCE_CONFIDENCE_STEP: Final[float] = 0.05

#: See module docstring's lockout paragraph.
CARDINALITY_CONTRADICTION_LOCKOUT_S: Final[float] = 30.0


def new_cardinality_belief(
    bucket: CountBucket, established_sim: float
) -> CardinalityBelief:
    """Build the `CardinalityBelief` a freshly perceived `bucket` represents,
    at the placeholder default confidence. Mirrors `classification.
    new_classification_belief`'s role."""
    return CardinalityBelief(
        lo=bucket.lo,
        hi=bucket.hi,
        confidence=_DEFAULT_CONFIDENCE,
        established_sim=established_sim,
    )


def cardinality_belief_from_bucket_name(
    name: str, established_sim: float
) -> CardinalityBelief:
    """`new_cardinality_belief`, resolving `name` (a `perception`-emitted
    `count_bucket` string) against `_BUCKETS_BY_NAME` first. Raises
    `KeyError` on an unrecognised name -- `perception.clustering.
    count_bucket_for` is the only producer of this string and is guaranteed
    to emit one of this module's own names, so an unrecognised value means a
    real bug upstream, not a case to degrade silently."""
    return new_cardinality_belief(_BUCKETS_BY_NAME[name], established_sim)


@dataclass(frozen=True, slots=True)
class FoldCardinalityOutcome:
    """`fold_cardinality`'s result -- `classification.FoldOutcome`'s twin."""

    cardinality: CardinalityBelief
    contradicted: bool


def fold_cardinality(
    held: CardinalityBelief | None,
    incoming: CardinalityBelief,
    now_sim: float,
    lockout_until_sim: float | None,
) -> FoldCardinalityOutcome:
    """The fusion rule `belief.contacts.Contact.record` calls instead of
    overwriting. `held` is `None` only for a contact's founding percept, in
    which case `incoming` is adopted outright -- see module docstring for
    the refine/reinforce/hold/contradict table, keyed off interval
    containment rather than a total-ordered level."""
    if held is None:
        return FoldCardinalityOutcome(cardinality=incoming, contradicted=False)

    if incoming.lo == held.lo and incoming.hi == held.hi:
        return FoldCardinalityOutcome(
            cardinality=_reinforce(held, now_sim), contradicted=False
        )

    locked = lockout_until_sim is not None and now_sim < lockout_until_sim

    incoming_narrower = held.lo <= incoming.lo and incoming.hi <= held.hi
    held_narrower = incoming.lo <= held.lo and held.hi <= incoming.hi

    if incoming_narrower:
        # incoming is a strict subset of held -- refine.
        if locked:
            return FoldCardinalityOutcome(cardinality=held, contradicted=False)
        return FoldCardinalityOutcome(cardinality=incoming, contradicted=False)

    if held_narrower:
        # held is a strict subset of incoming -- incoming is wider, hold.
        return FoldCardinalityOutcome(cardinality=held, contradicted=False)

    intersect_lo = max(held.lo, incoming.lo)
    intersect_hi = min(held.hi, incoming.hi)
    if intersect_lo <= intersect_hi:
        # Genuine partial overlap -- neither claim contains the other, but
        # they agree on a non-empty range. Not one of the plan's four named
        # cases (which assume near-partition, per module docstring's
        # OP_TO5UNITS/OP_5TO7UNITS note); the honest generalisation is to
        # refine down to the intersection, the narrowest claim both
        # readings still support.
        if locked:
            return FoldCardinalityOutcome(cardinality=held, contradicted=False)
        narrowed = CardinalityBelief(
            lo=intersect_lo,
            hi=intersect_hi,
            confidence=min(held.confidence, incoming.confidence),
            established_sim=now_sim,
        )
        return FoldCardinalityOutcome(cardinality=narrowed, contradicted=False)

    # Disjoint -- genuine contradiction, collapse to the hull.
    hull = CardinalityBelief(
        lo=min(held.lo, incoming.lo),
        hi=max(held.hi, incoming.hi),
        confidence=min(held.confidence, incoming.confidence),
        established_sim=now_sim,
    )
    return FoldCardinalityOutcome(cardinality=hull, contradicted=True)


def _reinforce(held: CardinalityBelief, now_sim: float) -> CardinalityBelief:
    return CardinalityBelief(
        lo=held.lo,
        hi=held.hi,
        confidence=min(
            _CONFIDENCE_CEILING, held.confidence + _REINFORCE_CONFIDENCE_STEP
        ),
        established_sim=now_sim,
    )
