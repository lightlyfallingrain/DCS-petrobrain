"""Tests for `belief.events` -- `lifecycle_event_kind` (`plans/pb2-contact-
memory/plan.md` Stage 2), `classification_event` (`plans/
classification-refinement/plan.md` Stage 3), `attention_event_kind`
(`plans/bl4-attention-events/plan.md`, BL-4), `cardinality_event`
(`plans/group-contact-model/plan.md` Stage 4b), and `motion_event_kind`
(`plans/movement-detection/plan.md` Stage 3). Each transition case gets
its own test."""

from __future__ import annotations

from belief.classification import ClassificationBelief, SpecificityLevel
from belief.events import (
    CONTACT_ATTENTION_CHANGED,
    CONTACT_CARDINALITY_CHANGED,
    CONTACT_DETECTED,
    CONTACT_LOST,
    CONTACT_MOTION_CHANGED,
    CONTACT_REACQUIRED,
    attention_event_kind,
    cardinality_event,
    classification_event,
    lifecycle_event_kind,
    motion_event_kind,
)


def _belief(value: str, level: SpecificityLevel) -> ClassificationBelief:
    return ClassificationBelief(
        value=value, level=level, confidence=0.5, established_sim=0.0
    )


def test_new_contact_first_tick_not_lost_is_detected() -> None:
    assert lifecycle_event_kind(None, "observed") == CONTACT_DETECTED
    assert lifecycle_event_kind(None, "tracked") == CONTACT_DETECTED
    assert lifecycle_event_kind(None, "estimated") == CONTACT_DETECTED


def test_new_contact_first_tick_already_lost_emits_nothing() -> None:
    assert lifecycle_event_kind(None, "lost") is None


def test_tracked_to_lost_is_contact_lost() -> None:
    assert lifecycle_event_kind("observed", "lost") == CONTACT_LOST
    assert lifecycle_event_kind("tracked", "lost") == CONTACT_LOST
    assert lifecycle_event_kind("estimated", "lost") == CONTACT_LOST


def test_lost_to_seen_again_is_contact_reacquired() -> None:
    assert lifecycle_event_kind("lost", "observed") == CONTACT_REACQUIRED
    assert lifecycle_event_kind("lost", "tracked") == CONTACT_REACQUIRED
    assert lifecycle_event_kind("lost", "estimated") == CONTACT_REACQUIRED


def test_still_lost_emits_nothing_again() -> None:
    assert lifecycle_event_kind("lost", "lost") is None


def test_certainty_sub_level_changes_while_alive_emit_nothing() -> None:
    """observed<->tracked<->estimated transitions are not lifecycle events
    -- only crossing into or out of `lost` is."""
    assert lifecycle_event_kind("observed", "tracked") is None
    assert lifecycle_event_kind("tracked", "estimated") is None
    assert lifecycle_event_kind("estimated", "observed") is None
    assert lifecycle_event_kind("tracked", "tracked") is None


# --- classification_event ----------------------------------------------


def test_first_tick_with_no_previous_classification_emits_nothing() -> None:
    current = _belief("OP_ARMORED", SpecificityLevel.CLASS)
    assert classification_event(None, current) is None


def test_higher_level_is_refined() -> None:
    previous = _belief("OP_ARMORED", SpecificityLevel.CLASS)
    current = _belief("T-72", SpecificityLevel.TYPE)
    assert classification_event(previous, current) == "refined"


def test_lower_level_is_contradicted() -> None:
    previous = _belief("T-72", SpecificityLevel.TYPE)
    current = _belief("OP_ARMORED", SpecificityLevel.CLASS)
    assert classification_event(previous, current) == "contradicted"


def test_same_level_different_value_is_contradicted() -> None:
    previous = _belief("OP_ARMORED", SpecificityLevel.CLASS)
    current = _belief("OP_TRUCK", SpecificityLevel.CLASS)
    assert classification_event(previous, current) == "contradicted"


def test_same_level_same_value_emits_nothing() -> None:
    """Reinforcement (and a hold, which never changes the held claim at
    all) must not fire an event even though confidence/established_sim may
    have changed -- the comparison deliberately ignores both."""
    previous = _belief("OP_ARMORED", SpecificityLevel.CLASS)
    current = _belief("OP_ARMORED", SpecificityLevel.CLASS)
    assert classification_event(previous, current) is None


# --- attention_event_kind ------------------------------------------------


def test_first_tick_with_no_previous_attention_emits_nothing() -> None:
    assert attention_event_kind(None, "normal") is None
    assert attention_event_kind(None, "watch") is None


def test_unchanged_attention_emits_nothing() -> None:
    assert attention_event_kind("normal", "normal") is None
    assert attention_event_kind("watch", "watch") is None
    assert attention_event_kind("priority", "priority") is None
    assert attention_event_kind("ignore", "ignore") is None


def test_any_real_change_emits_contact_attention_changed() -> None:
    assert attention_event_kind("normal", "watch") == CONTACT_ATTENTION_CHANGED
    assert attention_event_kind("watch", "normal") == CONTACT_ATTENTION_CHANGED
    assert attention_event_kind("watch", "priority") == CONTACT_ATTENTION_CHANGED
    assert attention_event_kind("priority", "ignore") == CONTACT_ATTENTION_CHANGED


# --- cardinality_event (`plans/group-contact-model/plan.md` Stage 4b) ------


def test_first_tick_with_no_previous_cardinality_emits_nothing() -> None:
    assert cardinality_event(None, (1, 1)) is None
    assert cardinality_event(None, (4, 5)) is None


def test_unchanged_cardinality_emits_nothing() -> None:
    assert cardinality_event((1, 1), (1, 1)) is None
    assert cardinality_event((4, 5), (4, 5)) is None


def test_cardinality_interval_change_is_contact_cardinality_changed() -> None:
    """Both a narrowing (refine) and a widening (contradiction-hull) case
    fire the event."""
    assert cardinality_event((1, 1), (2, 2)) == CONTACT_CARDINALITY_CHANGED
    assert cardinality_event((2, 5), (4, 5)) == CONTACT_CARDINALITY_CHANGED


def test_motion_established_for_the_first_time_emits_contact_motion_changed() -> None:
    """Unlike every other kind in this module, `previous is None` does NOT
    suppress the event here -- see `motion_event_kind`'s own docstring for
    why: `Contact.motion` can legitimately stay `None` for many ticks, so
    its first real establishment is exactly the transition worth reporting,
    not a synthetic first-tick artifact."""
    assert motion_event_kind(None, "moving") == CONTACT_MOTION_CHANGED
    assert motion_event_kind(None, "stopped") == CONTACT_MOTION_CHANGED


def test_current_none_never_emits() -> None:
    assert motion_event_kind(None, None) is None


def test_unchanged_motion_emits_nothing() -> None:
    assert motion_event_kind("moving", "moving") is None
    assert motion_event_kind("stopped", "stopped") is None


def test_motion_state_change_is_contact_motion_changed() -> None:
    assert motion_event_kind("stopped", "moving") == CONTACT_MOTION_CHANGED
    assert motion_event_kind("moving", "stopped") == CONTACT_MOTION_CHANGED
    assert cardinality_event((4, 5), (4, float("inf"))) == CONTACT_CARDINALITY_CHANGED
