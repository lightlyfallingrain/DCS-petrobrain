"""Tests for `belief.classification` -- the specificity lattice and its
fusion rule (`plans/classification-refinement/plan.md` Stage 2).

`class_compatibility`/`_op_class_of` themselves are already covered by
`test_association_over_time.py` (this module's Stage 1 move did not change
their behaviour) -- not re-tested here. This file covers what Stage 2 adds:
`SpecificityLevel`'s ordering, `parent_class_of`, `new_classification_belief`,
and `fold_classification`'s refine/reinforce/hold/contradict table plus the
contradiction lockout."""

from __future__ import annotations

from belief.classification import (
    AIR_DEFENSE_OP_CLASSES,
    CLASSIFICATION_CONTRADICTION_LOCKOUT_S,
    PRESENCE_CLASS,
    ClassificationBelief,
    SpecificityLevel,
    fold_classification,
    new_classification_belief,
    parent_class_of,
)
from perception import object_model


def _belief(
    value: str,
    level: SpecificityLevel,
    confidence: float = 0.5,
    established_sim: float = 0.0,
) -> ClassificationBelief:
    return ClassificationBelief(
        value=value, level=level, confidence=confidence, established_sim=established_sim
    )


# --- SpecificityLevel ordering ----------------------------------------------


def test_specificity_levels_are_totally_ordered() -> None:
    assert (
        SpecificityLevel.UNKNOWN
        < SpecificityLevel.PRESENCE
        < SpecificityLevel.CLASS
        < SpecificityLevel.TYPE
    )


# --- parent_class_of ---------------------------------------------------------


def test_parent_class_of_type_value_resolves_to_its_class() -> None:
    assert parent_class_of("T-72") == "OP_ARMORED"


def test_parent_class_of_class_value_is_a_no_op() -> None:
    assert parent_class_of("OP_ARMORED") == "OP_ARMORED"


def test_parent_class_of_presence_value_is_unresolvable() -> None:
    assert parent_class_of(PRESENCE_CLASS) is None


def test_parent_class_of_unmatched_free_text_is_unresolvable() -> None:
    assert parent_class_of("Slava cruiser") is None


# --- new_classification_belief -----------------------------------------------


def test_new_classification_belief_uses_default_confidence_by_level() -> None:
    presence = new_classification_belief(
        value=PRESENCE_CLASS, level=SpecificityLevel.PRESENCE, established_sim=5.0
    )
    class_level = new_classification_belief(
        value="OP_ARMORED", level=SpecificityLevel.CLASS, established_sim=5.0
    )
    type_level = new_classification_belief(
        value="T-72", level=SpecificityLevel.TYPE, established_sim=5.0
    )
    assert presence.confidence < class_level.confidence < type_level.confidence
    assert type_level.established_sim == 5.0


# --- fold_classification: founding percept -----------------------------------


def test_fold_with_no_held_belief_adopts_incoming_outright() -> None:
    incoming = _belief("OP_ARMORED", SpecificityLevel.CLASS)
    outcome = fold_classification(None, incoming, now_sim=0.0, lockout_until_sim=None)
    assert outcome.classification == incoming
    assert outcome.contradicted is False


# --- fold_classification: refine ---------------------------------------------


def test_fold_refines_class_to_type_when_parent_class_matches() -> None:
    held = _belief("OP_ARMORED", SpecificityLevel.CLASS, confidence=0.6)
    incoming = _belief(
        "T-72", SpecificityLevel.TYPE, confidence=0.9, established_sim=10.0
    )

    outcome = fold_classification(held, incoming, now_sim=10.0, lockout_until_sim=None)

    assert outcome.contradicted is False
    assert outcome.classification.level == SpecificityLevel.TYPE
    assert outcome.classification.value == "T-72"


def test_fold_refines_when_incoming_parent_is_unresolvable() -> None:
    """`unknown` comparability always permits refinement -- a scope-channel
    type value `object_model.profile_for` cannot resolve (e.g. `"Slava
    cruiser"`) must still refine, not be treated as incompatible."""
    held = _belief(PRESENCE_CLASS, SpecificityLevel.PRESENCE, confidence=0.3)
    incoming = _belief(
        "Slava cruiser", SpecificityLevel.TYPE, confidence=0.9, established_sim=1.0
    )

    outcome = fold_classification(held, incoming, now_sim=1.0, lockout_until_sim=None)

    assert outcome.contradicted is False
    assert outcome.classification.value == "Slava cruiser"
    assert outcome.classification.level == SpecificityLevel.TYPE


def test_fold_refines_presence_to_class() -> None:
    held = _belief(PRESENCE_CLASS, SpecificityLevel.PRESENCE, confidence=0.3)
    incoming = _belief(
        "OP_ARMORED", SpecificityLevel.CLASS, confidence=0.6, established_sim=1.0
    )

    outcome = fold_classification(held, incoming, now_sim=1.0, lockout_until_sim=None)

    assert outcome.contradicted is False
    assert outcome.classification.level == SpecificityLevel.CLASS
    assert outcome.classification.value == "OP_ARMORED"


# --- fold_classification: reinforce ------------------------------------------


def test_fold_reinforces_same_level_same_value_and_raises_confidence() -> None:
    held = _belief(
        "OP_ARMORED", SpecificityLevel.CLASS, confidence=0.6, established_sim=0.0
    )
    incoming = _belief(
        "OP_ARMORED", SpecificityLevel.CLASS, confidence=0.6, established_sim=5.0
    )

    outcome = fold_classification(held, incoming, now_sim=5.0, lockout_until_sim=None)

    assert outcome.contradicted is False
    assert outcome.classification.level == SpecificityLevel.CLASS
    assert outcome.classification.value == "OP_ARMORED"
    assert outcome.classification.confidence > held.confidence
    assert outcome.classification.established_sim == 5.0


def test_reinforce_confidence_does_not_exceed_the_ceiling() -> None:
    held = _belief(
        "OP_ARMORED", SpecificityLevel.CLASS, confidence=0.94, established_sim=0.0
    )
    incoming = _belief(
        "OP_ARMORED", SpecificityLevel.CLASS, confidence=0.6, established_sim=1.0
    )

    outcome = fold_classification(held, incoming, now_sim=1.0, lockout_until_sim=None)

    assert outcome.classification.confidence <= 0.95


# --- fold_classification: hold -----------------------------------------------


def test_fold_holds_when_incoming_is_a_lower_level() -> None:
    """The oscillation fix: a coarser observation never overwrites a more
    specific held claim -- the held claim survives untouched, field for
    field."""
    held = _belief("T-72", SpecificityLevel.TYPE, confidence=0.9, established_sim=3.0)
    incoming = _belief(
        "OP_ARMORED", SpecificityLevel.CLASS, confidence=0.6, established_sim=10.0
    )

    outcome = fold_classification(held, incoming, now_sim=10.0, lockout_until_sim=None)

    assert outcome.contradicted is False
    assert outcome.classification == held


def test_fold_holds_on_inconclusive_same_level_comparability() -> None:
    """Same level, different value, but neither side's parent class
    resolves -- inconclusive, not a contradiction. The held claim survives."""
    held = _belief(
        "Slava cruiser", SpecificityLevel.TYPE, confidence=0.9, established_sim=0.0
    )
    incoming = _belief(
        "Tarantul III corvette",
        SpecificityLevel.TYPE,
        confidence=0.9,
        established_sim=5.0,
    )

    outcome = fold_classification(held, incoming, now_sim=5.0, lockout_until_sim=None)

    assert outcome.contradicted is False
    assert outcome.classification == held


# --- fold_classification: contradict -----------------------------------------


def test_fold_contradicts_and_collapses_to_shared_class_when_types_disagree() -> None:
    """Two different specific types that resolve to the *same* class (both
    `T-72`/`BMP` are OP_ARMORED) collapse to that shared class, not all the
    way to presence."""
    held = _belief("T-72", SpecificityLevel.TYPE, confidence=0.9, established_sim=0.0)
    incoming = _belief(
        "BMP", SpecificityLevel.TYPE, confidence=0.9, established_sim=5.0
    )

    outcome = fold_classification(held, incoming, now_sim=5.0, lockout_until_sim=None)

    assert outcome.contradicted is True
    assert outcome.classification.level == SpecificityLevel.CLASS
    assert outcome.classification.value == "OP_ARMORED"
    assert outcome.classification.confidence == min(
        held.confidence, incoming.confidence
    )


def test_fold_contradicts_and_collapses_to_presence_when_classes_disagree() -> None:
    held = _belief(
        "OP_ARMORED", SpecificityLevel.CLASS, confidence=0.6, established_sim=0.0
    )
    incoming = _belief(
        "OP_TRUCK", SpecificityLevel.CLASS, confidence=0.6, established_sim=5.0
    )

    outcome = fold_classification(held, incoming, now_sim=5.0, lockout_until_sim=None)

    assert outcome.contradicted is True
    assert outcome.classification.level == SpecificityLevel.PRESENCE
    assert outcome.classification.value == PRESENCE_CLASS


def test_fold_contradicts_on_promotion_with_mismatched_parent() -> None:
    """A held class and an incoming, higher-level type whose own parent
    class disagrees with the held class -- promotion is rejected as a
    contradiction, not accepted as a refinement."""
    held = _belief(
        "OP_TRUCK", SpecificityLevel.CLASS, confidence=0.6, established_sim=0.0
    )
    incoming = _belief(
        "T-72", SpecificityLevel.TYPE, confidence=0.9, established_sim=5.0
    )

    outcome = fold_classification(held, incoming, now_sim=5.0, lockout_until_sim=None)

    assert outcome.contradicted is True
    assert outcome.classification.level == SpecificityLevel.PRESENCE


# --- contradiction lockout ---------------------------------------------------


def test_lockout_rejects_promotion_above_the_collapsed_level() -> None:
    held = _belief(
        PRESENCE_CLASS, SpecificityLevel.PRESENCE, confidence=0.3, established_sim=5.0
    )
    incoming = _belief(
        "T-72", SpecificityLevel.TYPE, confidence=0.9, established_sim=6.0
    )
    lockout_until_sim = 5.0 + CLASSIFICATION_CONTRADICTION_LOCKOUT_S

    outcome = fold_classification(
        held, incoming, now_sim=6.0, lockout_until_sim=lockout_until_sim
    )

    assert outcome.contradicted is False
    assert outcome.classification == held


def test_promotion_succeeds_again_once_the_lockout_expires() -> None:
    held = _belief(
        PRESENCE_CLASS, SpecificityLevel.PRESENCE, confidence=0.3, established_sim=5.0
    )
    incoming = _belief(
        "OP_ARMORED", SpecificityLevel.CLASS, confidence=0.6, established_sim=100.0
    )
    lockout_until_sim = 5.0 + CLASSIFICATION_CONTRADICTION_LOCKOUT_S

    outcome = fold_classification(
        held, incoming, now_sim=100.0, lockout_until_sim=lockout_until_sim
    )

    assert outcome.contradicted is False
    assert outcome.classification.level == SpecificityLevel.CLASS
    assert outcome.classification.value == "OP_ARMORED"


# --- AIR_DEFENSE_OP_CLASSES, the one copy (BL-B51) --------------------------


def test_air_defence_classes_cover_every_air_defence_class_in_the_object_model() -> (
    None
):
    """**The single drift guard for the single set** -- moved here from
    `tests/test_crew_console.py` when `BL-B51` consolidated three
    hand-enumerated copies (`belief.groups.AIR_DEFENSE_OP_CLASSES`,
    `belief.crew_console._AIR_DEFENCE_OP_CLASSES`,
    `eyesight_view._AIR_DEFENCE_CLASSES`) into
    `belief.classification.AIR_DEFENSE_OP_CLASSES`.

    It guards the drift that caused the `OP_LRSAM` omission, rather than
    only that one instance of it. The set is enumerated by hand against
    `perception.object_model`'s profile tables and nothing connects the
    two: when they gained a long-range SAM entry, no copy had a way to
    notice. `object_model` carries no structural air-defence marker to
    derive the set from (an `ObjectTypeProfile` is a size and an
    `op_class`, nothing more), so this test matches on the `OP_*` naming
    instead -- any class whose name says SAM or names a gun system must be
    covered.

    **`<=`, not `==`, and that distinction is the whole of `BL-B51`.** Two
    of the three retired copies were effectively pinned against a literal
    frozenset, which is a change *detector*: it fires when someone edits
    the set and stays silent when `object_model` grows underneath it,
    which is the only direction that loses coverage. The companion test
    below asserts that property directly.

    **Both tables are read, because the second runs only when the first
    misses**: `_KEYWORD_PROFILES` (70 entries) and
    `_REPORTING_NAME_KEYWORD_PROFILES` (61), 131 entries in all, carrying
    9 distinct `op_class` values between them (9 in the first table, 6 in
    the second, union 9).

    If a future profile entry introduces an air-defence class this pattern
    does not catch, that is a signal to give `object_model` a real marker,
    not to loosen the assertion."""
    profiled_classes = {
        profile.op_class
        for _keyword, profile in (
            *object_model._KEYWORD_PROFILES,
            *object_model._REPORTING_NAME_KEYWORD_PROFILES,
        )
    }
    air_defence_by_name = {
        op_class
        for op_class in profiled_classes
        if op_class.endswith("SAM") or op_class in {"OP_SPAAG", "OP_ZU23"}
    }

    assert air_defence_by_name, "naming heuristic matched nothing -- it has gone stale"
    assert air_defence_by_name <= AIR_DEFENSE_OP_CLASSES


def test_the_drift_guard_fires_on_a_new_air_defence_class_and_a_pin_would_not() -> None:
    """The guard's own red case, as a property rather than a manual
    mutation someone has to remember to repeat.

    The naming predicate is written out again here rather than imported
    from the test above, deliberately: sharing it would let a change to
    the predicate make both tests agree about nothing. The claim is that
    an air-defence class `AIR_DEFENSE_OP_CLASSES` does not hold fails the
    `<=` form **and passes the `==` form the retired copies used**, which
    is why `<=` is the guard and `==` is only a change detector.

    `OP_XLRSAM` is the value `BL-B51` measured with: injecting it as a
    profile turned `crew_console`'s `<=` test red and left
    `test_groups.py`'s literal pin green."""
    profiled_with_a_newcomer = set(AIR_DEFENSE_OP_CLASSES) | {"OP_XLRSAM"}
    air_defence_by_name = {
        op_class
        for op_class in profiled_with_a_newcomer
        if op_class.endswith("SAM") or op_class in {"OP_SPAAG", "OP_ZU23"}
    }

    assert "OP_XLRSAM" in air_defence_by_name
    assert not air_defence_by_name <= AIR_DEFENSE_OP_CLASSES
    # The `==` form is blind to the same newcomer: it never looks at
    # `object_model` at all, so it still holds.
    assert AIR_DEFENSE_OP_CLASSES == frozenset(
        {"OP_SRSAM", "OP_MRSAM", "OP_LRSAM", "OP_SPAAG", "OP_ZU23"}
    )
