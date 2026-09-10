"""Tests for `belief.decay` -- the `certainty` ladder (`plans/pb2-contact-
memory/plan.md` Stage 2). Each level/boundary gets its own test, per the
plan's acceptance criteria ("each `certainty` row is pinned by a test")."""

from __future__ import annotations

from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact
from belief.decay import (
    LOST_THRESHOLD_S,
    OBSERVED_WINDOW_S,
    POSITION_HALF_LIFE_S,
    certainty_of,
)
from perception.geometry import GeoPosition


def _contact(last_seen_sim: float) -> Contact:
    return Contact(
        id="CONTACT_1",
        last_position=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        last_position_uncertainty_m=0.0,
        last_class_raw="OP_TRUCK",
        classification=new_classification_belief(
            value="OP_TRUCK",
            level=SpecificityLevel.CLASS,
            established_sim=last_seen_sim,
        ),
        first_seen_sim=last_seen_sim,
        last_seen_sim=last_seen_sim,
    )


def test_certainty_is_observed_at_zero_elapsed() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert certainty_of(contact, now_sim=0.0) == "observed"


def test_certainty_is_observed_at_the_observed_window_boundary() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert certainty_of(contact, now_sim=OBSERVED_WINDOW_S) == "observed"


def test_certainty_is_tracked_just_past_the_observed_window() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert certainty_of(contact, now_sim=OBSERVED_WINDOW_S + 0.1) == "tracked"


def test_certainty_is_tracked_at_the_position_half_life_boundary() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert certainty_of(contact, now_sim=POSITION_HALF_LIFE_S) == "tracked"


def test_certainty_is_estimated_just_past_the_position_half_life() -> None:
    contact = _contact(last_seen_sim=0.0)
    assert certainty_of(contact, now_sim=POSITION_HALF_LIFE_S + 0.1) == "estimated"


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
