"""The classification specificity lattice -- `plans/classification-refinement/
plan.md` Stage 1 (this module's creation, a pure move) and Stage 2 (the
lattice + fusion mechanism added on top).

**Stage 1 content: `_op_class_of`/`class_compatibility`, re-homed from
`belief.association_over_time` verbatim.** They move here because Stage 2
would otherwise create a second class-resolution function in this module --
the lattice's `parent_class_of` needs exactly the same ED-vocabulary
resolution `_op_class_of` already does. `association_over_time.py` imports
both names from here so every existing caller and test import path
(`from belief.association_over_time import class_compatibility`) keeps
working unchanged. See that module's own docstring for the full rationale
behind the three-valued compatibility result -- unchanged by this move.

**Stage 2 content: the lattice and its fusion rule.** Four totally-ordered
*levels* (`SpecificityLevel`, 0-3) over a shallow *tree* of values -- a
level-3 (type) value's parent is its level-2 (class) value, resolved by
`parent_class_of` (a thin wrapper over `_op_class_of` above: the same
resolver serves both the association gate's compatibility check and the
lattice's parent-consistency check, by design -- one vocabulary bridge, not
two). `fold_classification` is the fusion rule `belief.contacts.Contact.
record` calls instead of overwriting: higher level + parent-consistent (or
unresolvable) -> refine; same level + same value -> reinforce; lower level
-> hold (the held claim survives untouched -- this is the oscillation fix);
same-or-higher level + resolvable + incompatible -> contradict, collapsing
to the deepest common ancestor the two claims still agree on (their shared
class if one exists, else the presence root). An "unresolvable" parent
(scope free text `object_model.profile_for` can't match, e.g. `"Slava
cruiser"`) always yields `unknown` comparability -- it never blocks a
refinement and never triggers a contradiction, mirroring `class_
compatibility`'s existing three-valued posture exactly.

`CLASSIFICATION_CONTRADICTION_LOCKOUT_S` guards against a spam path unique
to contradiction (persistent cross-channel disagreement: contradict ->
collapse -> refine -> contradict, at the poll rate): once a contradiction
collapses a contact's classification, no promotion *above* the collapsed
level is accepted until this many sim-seconds have passed. `fold_
classification` enforces it directly (given the caller's current lockout
deadline); `belief.contacts.Contact` owns the one timestamp field
(`classification_lockout_until_sim`) this needs, refreshed only when `fold_
classification` reports a fresh contradiction (`FoldOutcome.contradicted`).

Confidence is a small, explicitly-placeholder judgment call, not a
calibrated figure (the same posture as `association_over_time.py`'s
`SCOPE_UNCERTAINTY_M`/`GATE_GROWTH_RATE_MPS`): a fixed value per level for a
newly-observed claim (`_DEFAULT_CONFIDENCE_BY_LEVEL`), nudged toward a
ceiling on reinforcement, and floored to the lower of the two claims'
confidences on a collapse. Real calibration (and `belief.decay.
IDENTITY_HALF_LIFE_S`-driven decay of this confidence over time) is later
work this stage does not build -- see `decay.py`'s own docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Final, Literal

from perception import object_model

ClassCompatibility = Literal["compatible", "unknown", "incompatible"]


def _op_class_of(classification_raw: str) -> str | None:
    """Resolve `classification_raw` (either an already-bucketed naked-eye
    `OP_*` string, or scope/hybrid free text) to an `OP_*` bucket, or `None`
    if unknown. See module docstring."""
    if classification_raw.startswith("OP_") and (
        classification_raw != object_model.DEFAULT_OP_CLASS
    ):
        return classification_raw
    profile = object_model.profile_for(classification_raw)
    if profile.op_class == object_model.DEFAULT_OP_CLASS:
        return None
    return profile.op_class


def class_compatibility(a_raw: str, b_raw: str) -> ClassCompatibility:
    """Three-valued class compatibility between two `classification_raw`
    strings. See module docstring."""
    a_class = _op_class_of(a_raw)
    b_class = _op_class_of(b_raw)
    if a_class is None or b_class is None:
        return "unknown"
    return "compatible" if a_class == b_class else "incompatible"


class SpecificityLevel(IntEnum):
    """The lattice's total order over *levels* -- 0 (no identity claim at
    all) through 3 (a specific type). See module docstring. Ordering
    (`<`/`>`) is what makes "more specific" well-defined; `fold_
    classification` relies on it directly."""

    UNKNOWN = 0
    PRESENCE = 1
    CLASS = 2
    TYPE = 3


#: Level 1's one value -- "something is there," nothing more. ED has no
#: singular "something" ambient-callout fragment (investigator finding,
#: `plan.md`'s Session 6 addendum, Q2); `OP_GROUPSOMETHING` is its only
#: catch-all, so it doubles as the presence-level value. `_op_class_of`
#: already maps this string to `None` ("no class claim"), which is exactly
#: what level 1 means -- no special-casing needed anywhere else in this
#: module for that fact to hold.
PRESENCE_CLASS: Final[str] = object_model.DEFAULT_OP_CLASS


@dataclass(frozen=True, slots=True)
class ClassificationBelief:
    """One contact's held classification claim. `value` is `None` only at
    `SpecificityLevel.UNKNOWN` (no claim at all); at every other level it is
    the level's own value shape (`PRESENCE_CLASS`, an `OP_*` bucket, or a
    specific type/reporting-name string). `established_sim` is when this
    exact claim was last confirmed -- refreshed by `fold_classification` on
    every refine/reinforce, held fixed on a hold, reset to the fold's own
    `now_sim` on a collapse."""

    value: str | None
    level: SpecificityLevel
    confidence: float
    established_sim: float


#: Fixed per-level starting confidence for a newly-observed claim -- a
#: placeholder judgment call, not calibrated (see module docstring).
_DEFAULT_CONFIDENCE_BY_LEVEL: Final[dict[SpecificityLevel, float]] = {
    SpecificityLevel.UNKNOWN: 0.0,
    SpecificityLevel.PRESENCE: 0.3,
    SpecificityLevel.CLASS: 0.6,
    SpecificityLevel.TYPE: 0.9,
}

#: Reinforcement never pushes confidence past this -- there is always some
#: residual uncertainty, even after many consistent re-observations.
_CONFIDENCE_CEILING: Final[float] = 0.95

#: How much one reinforcing observation raises confidence, before the
#: ceiling above caps it.
_REINFORCE_CONFIDENCE_STEP: Final[float] = 0.05

#: See module docstring's contradiction-lockout paragraph. Default judgment
#: call, revisitable like every other constant in this file.
CLASSIFICATION_CONTRADICTION_LOCKOUT_S: Final[float] = 30.0


def new_classification_belief(
    value: str, level: SpecificityLevel, established_sim: float
) -> ClassificationBelief:
    """Build the `ClassificationBelief` a freshly perceived classification
    claim represents, at its default per-level confidence. The caller
    (`belief.contacts.Contact`) supplies `value`/`level` straight from a
    `belief.percept.Percept`'s `classification_raw`/`classification_level`
    -- this function does not know about `Percept` at all, keeping this
    module's only dependency on `belief/` siblings at zero."""
    return ClassificationBelief(
        value=value,
        level=level,
        confidence=_DEFAULT_CONFIDENCE_BY_LEVEL[level],
        established_sim=established_sim,
    )


def parent_class_of(value: str) -> str | None:
    """The `OP_*` class `value` resolves to: a level-3 value's parent class,
    or a level-2 value's own class (a no-op through the same resolver), or
    `None` for the level-1 presence value or any unresolvable free text.
    Thin wrapper over `_op_class_of` -- see module docstring on why the two
    lattice checks (association gate's compatibility, this lattice's parent
    consistency) share one resolver."""
    return _op_class_of(value)


@dataclass(frozen=True, slots=True)
class FoldOutcome:
    """`fold_classification`'s result: the `ClassificationBelief` to hold
    going forward, plus whether this fold was a contradiction -- the one
    bit `belief.contacts.Contact.record` needs to decide whether to (re)set
    its `classification_lockout_until_sim`. Refine/reinforce/hold all report
    `contradicted=False`."""

    classification: ClassificationBelief
    contradicted: bool


def fold_classification(
    held: ClassificationBelief | None,
    incoming: ClassificationBelief,
    now_sim: float,
    lockout_until_sim: float | None,
) -> FoldOutcome:
    """The fusion rule replacing last-writer-wins. `held` is `None` only for
    a contact's founding percept, in which case `incoming` is adopted
    outright. See module docstring for the refine/reinforce/hold/contradict
    table and the lockout's effect."""
    if held is None:
        return FoldOutcome(classification=incoming, contradicted=False)

    locked = lockout_until_sim is not None and now_sim < lockout_until_sim
    if locked and incoming.level > held.level:
        # Contradiction lockout: no promotion above the collapsed level
        # while locked -- see module docstring. Not itself a new
        # contradiction; the held (collapsed) claim simply survives.
        return FoldOutcome(classification=held, contradicted=False)

    if incoming.level > held.level:
        return _fold_higher(held, incoming, now_sim)
    if incoming.level == held.level:
        return _fold_same_level(held, incoming, now_sim)
    return FoldOutcome(classification=held, contradicted=False)  # hold


def _fold_higher(
    held: ClassificationBelief, incoming: ClassificationBelief, now_sim: float
) -> FoldOutcome:
    """`incoming.level > held.level`: refine if `incoming`'s ancestor at
    `held`'s depth agrees with `held.value` (or either side is
    unresolvable -- `unknown` comparability always permits refinement);
    otherwise the two claims disagree and this is a contradiction."""
    held_class = parent_class_of(held.value) if held.value is not None else None
    incoming_class = (
        parent_class_of(incoming.value) if incoming.value is not None else None
    )
    if held_class is None or incoming_class is None or held_class == incoming_class:
        return FoldOutcome(classification=incoming, contradicted=False)
    return FoldOutcome(
        classification=_collapse(held, incoming, held_class, incoming_class, now_sim),
        contradicted=True,
    )


def _fold_same_level(
    held: ClassificationBelief, incoming: ClassificationBelief, now_sim: float
) -> FoldOutcome:
    """`incoming.level == held.level`: reinforce on an identical value;
    otherwise the two claims are a genuine same-depth disagreement, which
    contradicts unless neither side's parent class resolves (inconclusive
    comparability -- the held claim survives untouched, same as a hold)."""
    if incoming.value == held.value:
        reinforced = ClassificationBelief(
            value=held.value,
            level=held.level,
            confidence=min(
                _CONFIDENCE_CEILING, held.confidence + _REINFORCE_CONFIDENCE_STEP
            ),
            established_sim=now_sim,
        )
        return FoldOutcome(classification=reinforced, contradicted=False)

    held_class = parent_class_of(held.value) if held.value is not None else None
    incoming_class = (
        parent_class_of(incoming.value) if incoming.value is not None else None
    )
    if held_class is None or incoming_class is None:
        return FoldOutcome(classification=held, contradicted=False)
    return FoldOutcome(
        classification=_collapse(held, incoming, held_class, incoming_class, now_sim),
        contradicted=True,
    )


def _collapse(
    held: ClassificationBelief,
    incoming: ClassificationBelief,
    held_class: str,
    incoming_class: str,
    now_sim: float,
) -> ClassificationBelief:
    """The deepest common ancestor two *resolvable, disagreeing* claims
    still share: their common class if `held_class == incoming_class`
    (reachable only from the same-level, different-type-value case --
    `_fold_higher` already treats equal classes as a refine, not a
    collapse), else the presence root, since presence is the only node
    every branch shares unconditionally. Confidence floors to the lower of
    the two claims'; this is the moment of disagreement, not a moment of
    growing certainty."""
    confidence = min(held.confidence, incoming.confidence)
    if held_class == incoming_class:
        return ClassificationBelief(
            value=held_class,
            level=SpecificityLevel.CLASS,
            confidence=confidence,
            established_sim=now_sim,
        )
    return ClassificationBelief(
        value=PRESENCE_CLASS,
        level=SpecificityLevel.PRESENCE,
        confidence=confidence,
        established_sim=now_sim,
    )
