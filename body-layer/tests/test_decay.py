"""Tests for `belief.decay` -- the `certainty` ladder (`plans/pb2-contact-
memory/plan.md` Stage 2). Each level/boundary gets its own test, per the
plan's acceptance criteria ("each `certainty` row is pinned by a test")."""

from __future__ import annotations

import pytest

from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact
from belief.decay import (
    GROUP_REIDENTIFY_WINDOW_S,
    IDENTITY_HALF_LIFE_S,
    LAST_I_SAW_GROWTH_THRESHOLD_M,
    LOST_THRESHOLD_S,
    MOTION_HALF_LIFE_S,
    OBJECT_ID_MEMORY_S,
    OBSERVED_WINDOW_S,
    POSITION_HALF_LIFE_S,
    certainty_of,
    classification_confidence_at,
    distance_since_last_seen_m,
    motion_confidence_at,
    object_id_continuity_valid,
    position_confidence,
)
from belief.motion import MotionBelief
from belief.position_belief import Covariance2D, PositionEstimate
from perception.gaze import FOCUS_DWELL_S, SCAN_CYCLE_PERIOD_S


def _contact(
    last_seen_sim: float,
    classification_established_sim: float | None = None,
    last_class_raw: str = "OP_TRUCK",
) -> Contact:
    """`last_class_raw` defaults to the plain `"OP_TRUCK"` class string
    every pre-`[[BL-B112]]` test here already used -- `profile_for` matches
    it via the generic `"truck"` keyword (`OP_TRUCK`, 15.0 m/s,
    `immobile=False`). A handful of `certainty_of` tests below instead pass
    a real DCS `object_type` keyword (`"5p73 s-125 ln"`, SA-3) to get an
    `immobile=True` profile -- see `association_over_time.contact_growth_
    rate_mps`'s own docstring for why the growth rate, not the class
    string, is what `certainty_of`'s tracked/estimated boundary now
    reads."""
    return Contact(
        id="CONTACT_1",
        position=PositionEstimate(
            x=0.0,
            z=0.0,
            covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
            as_of_sim=last_seen_sim,
            fused_at_sim=last_seen_sim,
            fused_covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
        ),
        last_alt_m=0.0,
        last_class_raw=last_class_raw,
        classification=new_classification_belief(
            value="OP_TRUCK",
            level=SpecificityLevel.CLASS,
            established_sim=(
                last_seen_sim
                if classification_established_sim is None
                else classification_established_sim
            ),
        ),
        first_seen_sim=last_seen_sim,
        last_seen_sim=last_seen_sim,
    )


# -- OBSERVED_WINDOW_S's two bounds (2C, plans/detection-cones-slice2/
# plan.md hard part 8) -- each pins a real failure mode, not the current
# value. --------------------------------------------------------------------


def test_observed_window_is_derived_from_the_scan_cycle_period() -> None:
    assert OBSERVED_WINDOW_S == pytest.approx(SCAN_CYCLE_PERIOD_S)
    assert OBSERVED_WINDOW_S == pytest.approx(16.0)


def test_observed_window_clears_the_worst_case_flank_gap() -> None:
    # Lower bound: a flank o'clock is un-gazed for up to
    # SCAN_CYCLE_PERIOD_S - FOCUS_DWELL_S (14 s) of every 16 s cycle while
    # Petrovich is tracking it correctly. If OBSERVED_WINDOW_S ever dropped
    # to or below that gap, a correctly-tracked flank contact would read
    # as "not observed" for most of every scan cycle -- the exact defect
    # this bound exists to prevent.
    worst_case_flank_gap_s = SCAN_CYCLE_PERIOD_S - FOCUS_DWELL_S
    assert worst_case_flank_gap_s < OBSERVED_WINDOW_S


def test_observed_window_stays_below_the_position_half_life() -> None:
    # `position_confidence`'s own concern now (`[[BL-B112]]`, decay.py's
    # own comment above the assertion this mirrors) -- not `certainty_of`'s
    # tracked band, which no longer reads `POSITION_HALF_LIFE_S` at all.
    assert OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S


def test_certainty_is_observed_at_zero_elapsed() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert certainty_of(contact, now_sim=0.0) == "observed"


def test_certainty_is_observed_at_the_observed_window_boundary() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert certainty_of(contact, now_sim=OBSERVED_WINDOW_S) == "observed"


def test_certainty_is_tracked_just_past_the_observed_window() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert certainty_of(contact, now_sim=OBSERVED_WINDOW_S + 0.1) == "tracked"


# -- `[[BL-B112]]`: tracked/estimated is growth-distance-based, not a bare
# POSITION_HALF_LIFE_S elapsed-time boundary (explore-notes.md, user,
# 2026-11-12: "use 'last I saw' if it is a mobile unit. Use when location
# inaccuracy grows to >= 0.5 km."). -----------------------------------------


def test_distance_since_last_seen_grows_with_the_class_rate() -> None:
    # OP_TRUCK (via the plain "OP_TRUCK" class string) resolves to 15.0
    # m/s (test_association_over_time.py's own calibration anchor for this
    # class) -- an air contact by `_contact`'s own default (`on_surface=
    # False`), so `contact_growth_rate_mps` takes the unconditional
    # class-rate branch regardless of `Contact.motion`.
    contact = _contact(last_seen_sim=0.0)
    assert distance_since_last_seen_m(contact, now_sim=10.0) == pytest.approx(150.0)


def test_certainty_is_tracked_below_the_growth_threshold() -> None:
    # ~32.3 s elapsed * 15.0 m/s = ~499 m, just below
    # LAST_I_SAW_GROWTH_THRESHOLD_M (500 m) -- "tracked" fact, even though
    # this elapsed time is already past the old POSITION_HALF_LIFE_S
    # boundary (30 s default). That is the point of this test: the
    # boundary is distance now, not elapsed time.
    contact = _contact(last_seen_sim=0.0)
    now_sim = LAST_I_SAW_GROWTH_THRESHOLD_M / 15.0 - 1.0
    assert distance_since_last_seen_m(contact, now_sim) < LAST_I_SAW_GROWTH_THRESHOLD_M
    assert certainty_of(contact, now_sim) == "tracked"


def test_certainty_is_estimated_once_growth_crosses_the_threshold() -> None:
    contact = _contact(last_seen_sim=0.0)
    now_sim = LAST_I_SAW_GROWTH_THRESHOLD_M / 15.0 + 1.0
    assert now_sim <= LOST_THRESHOLD_S, "fixture must stay inside the estimated band"
    assert distance_since_last_seen_m(contact, now_sim) >= LAST_I_SAW_GROWTH_THRESHOLD_M
    assert certainty_of(contact, now_sim) == "estimated"


def test_immobile_contact_never_reaches_estimated_via_growth() -> None:
    """Explore-notes.md Q3: *"a SAM site that is not a mobile SAM unit
    itself, will not move... SA-2 is and remains stationary."* An immobile
    profile (`"5p73 s-125 ln"`, SA-3) always has `distance_since_last_seen_m
    == 0.0` (`association_over_time.contact_growth_rate_mps`'s `profile.
    immobile` branch), so it stays "tracked" fact for as long as
    `certainty_of`'s elapsed-time ladder allows at all -- right up to
    `LOST_THRESHOLD_S`, never hedged as "estimated" along the way."""
    contact = _contact(last_seen_sim=0.0, last_class_raw="5p73 s-125 ln")
    now_sim = LOST_THRESHOLD_S
    assert distance_since_last_seen_m(contact, now_sim) == 0.0
    assert certainty_of(contact, now_sim) == "tracked"


def test_immobile_contact_still_goes_lost_at_the_lost_threshold() -> None:
    """Q2's "use current implementation": `LOST_THRESHOLD_S` stays purely
    elapsed-time for every contact, immobile ones included -- this is the
    hand-off to mission memory, not a claim the unit could have moved."""
    contact = _contact(last_seen_sim=0.0, last_class_raw="5p73 s-125 ln")
    assert certainty_of(contact, now_sim=LOST_THRESHOLD_S + 0.1) == "lost"


def test_certainty_is_estimated_at_the_lost_threshold_boundary() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert certainty_of(contact, now_sim=LOST_THRESHOLD_S) == "estimated"


def test_certainty_is_lost_just_past_the_lost_threshold() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert certainty_of(contact, now_sim=LOST_THRESHOLD_S + 0.1) == "lost"


def test_certainty_stays_lost_arbitrarily_far_past_the_threshold() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert certainty_of(contact, now_sim=LOST_THRESHOLD_S * 100.0) == "lost"


def test_negative_elapsed_time_is_clamped_to_observed() -> None:
    """`now_sim` earlier than `last_seen_sim` should never happen in a
    correctly-driven replay, but `certainty_of` clamps rather than returning
    a nonsensical negative-elapsed certainty."""
    contact = _contact(last_seen_sim=100.0)
    assert certainty_of(contact, now_sim=0.0) == "observed"


def test_position_confidence_is_one_at_zero_elapsed() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert position_confidence(contact, now_sim=0.0) == pytest.approx(1.0)


def test_position_confidence_is_half_at_the_half_life() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert position_confidence(contact, now_sim=POSITION_HALF_LIFE_S) == pytest.approx(
        0.5
    )


def test_position_confidence_is_a_quarter_at_two_half_lives() -> None:
    contact = _contact(last_seen_sim=0.0)
    confidence = position_confidence(contact, now_sim=POSITION_HALF_LIFE_S * 2.0)
    assert confidence == pytest.approx(0.25)


def test_position_confidence_negative_elapsed_time_is_clamped_to_one() -> None:
    contact = _contact(last_seen_sim=100.0)
    assert position_confidence(contact, now_sim=0.0) == pytest.approx(1.0)


def test_position_confidence_decays_monotonically() -> None:
    contact = _contact(last_seen_sim=0.0)
    earlier = position_confidence(contact, now_sim=10.0)
    later = position_confidence(contact, now_sim=20.0)
    assert later < earlier


def test_classification_confidence_is_unchanged_at_zero_elapsed() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert classification_confidence_at(contact, now_sim=0.0) == (
        contact.classification.confidence
    )


def test_classification_confidence_halves_at_the_identity_half_life() -> None:
    contact = _contact(last_seen_sim=0.0)
    held = contact.classification.confidence
    decayed = classification_confidence_at(contact, now_sim=IDENTITY_HALF_LIFE_S)
    assert decayed == pytest.approx(held / 2.0)


def test_classification_confidence_keeps_falling_well_past_the_half_life() -> None:
    contact = _contact(last_seen_sim=0.0)
    held = contact.classification.confidence
    decayed = classification_confidence_at(contact, now_sim=IDENTITY_HALF_LIFE_S * 4.0)
    assert decayed == pytest.approx(held / 16.0)
    assert 0.0 < decayed < held


def test_classification_confidence_keys_off_established_sim_not_last_seen_sim() -> None:
    """A contact re-observed recently (`last_seen_sim` fresh) whose
    classification claim was folded long ago (`established_sim` stale --
    e.g. a `hold` outcome, which leaves `established_sim` untouched per
    `belief.classification`'s fold table) still decays from the claim's own
    timestamp, not the contact's."""
    contact = _contact(last_seen_sim=1000.0, classification_established_sim=0.0)
    held = contact.classification.confidence
    decayed = classification_confidence_at(contact, now_sim=IDENTITY_HALF_LIFE_S)
    assert decayed == pytest.approx(held / 2.0)


def test_classification_confidence_negative_elapsed_time_is_clamped() -> None:
    contact = _contact(last_seen_sim=0.0, classification_established_sim=100.0)
    assert classification_confidence_at(contact, now_sim=0.0) == (
        contact.classification.confidence
    )


def test_motion_confidence_is_unchanged_at_zero_elapsed() -> None:
    contact = _contact(last_seen_sim=0.0)
    contact.motion = MotionBelief(state="moving", confidence=0.5, established_sim=0.0)
    assert motion_confidence_at(contact, now_sim=0.0) == pytest.approx(0.5)


def test_motion_confidence_halves_at_the_motion_half_life() -> None:
    contact = _contact(last_seen_sim=0.0)
    contact.motion = MotionBelief(state="moving", confidence=0.5, established_sim=0.0)
    decayed = motion_confidence_at(contact, now_sim=MOTION_HALF_LIFE_S)
    assert decayed == pytest.approx(0.25)


def test_motion_confidence_keys_off_established_sim_not_last_seen_sim() -> None:
    contact = _contact(last_seen_sim=1000.0)
    contact.motion = MotionBelief(state="stopped", confidence=0.5, established_sim=0.0)
    decayed = motion_confidence_at(contact, now_sim=MOTION_HALF_LIFE_S)
    assert decayed == pytest.approx(0.25)


def test_motion_confidence_requires_motion_to_be_set() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert contact.motion is None
    with pytest.raises(AssertionError):
        motion_confidence_at(contact, now_sim=0.0)


def test_object_id_continuity_is_valid_at_exactly_the_memory_window_boundary() -> None:
    """Boundary inclusive, matching `certainty_of`'s own `<=` convention --
    `plans/contact-duplication-ambiguity-runaway/plan.md`'s Decay section."""
    contact = _contact(last_seen_sim=0.0)
    assert object_id_continuity_valid(contact, now_sim=OBJECT_ID_MEMORY_S) is True


def test_object_id_continuity_is_invalid_just_past_the_memory_window() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert (
        object_id_continuity_valid(contact, now_sim=OBJECT_ID_MEMORY_S + 0.1) is False
    )


def test_object_id_continuity_is_valid_between_lost_threshold_and_memory_window() -> (
    None
):
    """`OBJECT_ID_MEMORY_S` (600s) is deliberately larger than
    `LOST_THRESHOLD_S` (120s): a contact well past `LOST_THRESHOLD_S` --
    `certainty_of` already returns `"lost"` -- must still be a valid
    continuity target, matching the "I lost him... it's the same guy"
    scenario the decay ordering is meant to preserve."""
    contact = _contact(last_seen_sim=0.0)
    now_sim = LOST_THRESHOLD_S + 50.0
    assert now_sim < OBJECT_ID_MEMORY_S
    assert certainty_of(contact, now_sim) == "lost"
    assert object_id_continuity_valid(contact, now_sim) is True


def test_group_reidentify_window_is_twice_the_position_half_life() -> None:
    """`GROUP_REIDENTIFY_WINDOW_S` (`plans/group-contact-identity/plan.md`
    Stage 1) is derived, not independently chosen -- see its own
    docstring. Pinned here, not re-derived, so a future retuning of
    `POSITION_HALF_LIFE_S` moves this with it rather than silently
    decoupling the two."""
    assert GROUP_REIDENTIFY_WINDOW_S == 2.0 * POSITION_HALF_LIFE_S
    assert GROUP_REIDENTIFY_WINDOW_S == 60.0
