"""Tests for `belief.events` -- `lifecycle_event_kind` (`plans/pb2-contact-
memory/plan.md` Stage 2). Each transition case gets its own test."""

from __future__ import annotations

from belief.events import (
    CONTACT_DETECTED,
    CONTACT_LOST,
    CONTACT_REACQUIRED,
    lifecycle_event_kind,
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
