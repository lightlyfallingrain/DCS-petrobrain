"""Tests for `belief.callouts` -- `plans/callout-scheduling/plan.md`, Slice
A (the scheduler): occupancy blocks speech, an expired candidate is dropped
unspoken and unacknowledged, a vanished contact's candidate is skipped in
favour of the next one, and the urgent path resets occupancy. Slice B
(aggregation) extends this file with its own tests in a separate commit."""

from __future__ import annotations

import pytest

from belief.callouts import (
    CALLOUT_MAX_AGE_S,
    CalloutScheduler,
    callout_priority,
    estimate_speech_duration_s,
)
from belief.contacts import ContactStore
from belief.events import Event
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _observation(
    *,
    obs_id: str,
    t_sim: float,
    classification_raw: str,
    classification_level: int,
    dwp_x: float = 99999.0,
    dwp_z: float = 99999.0,
) -> Observation:
    """`dwp_x`/`dwp_z` (`Contact.last_position`, i.e. the spatial-gate
    input) default to a shared value -- two calls with distinct values keep
    two observations from gate-merging into one contact, the only thing
    these Slice A tests need (no enrichment/clock/range control here,
    unlike Slice B's own fixture helper)."""
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=dwp_x, z=dwp_z, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=classification_level,
    )


# --- estimate_speech_duration_s ---------------------------------------------


def test_estimate_speech_duration_s_is_min_plus_words_over_rate() -> None:
    from belief.callouts import MIN_UTTERANCE_S, SPEECH_RATE_WPS

    text = "infantry, twelve o'clock, very close."
    expected = MIN_UTTERANCE_S + len(text.split()) / SPEECH_RATE_WPS
    assert estimate_speech_duration_s(text) == expected


def test_estimate_speech_duration_s_empty_string_is_just_the_floor() -> None:
    from belief.callouts import MIN_UTTERANCE_S

    assert estimate_speech_duration_s("") == MIN_UTTERANCE_S


# --- callout_priority --------------------------------------------------------


def _event(t_sim: float = 0.0) -> Event:
    return Event(
        id="E1",
        contact_id="C1",
        kind="CONTACT_DETECTED",
        t_sim=t_sim,
        certainty="observed",
    )


def test_callout_priority_ranks_priority_attention_above_watch_above_normal() -> None:
    event = _event()
    priority_facts: dict[str, object] = {"attention": "priority"}
    watch_facts: dict[str, object] = {"attention": "watch"}
    normal_facts: dict[str, object] = {"attention": "normal"}
    ignore_facts: dict[str, object] = {"attention": "ignore"}

    ranked = sorted(
        [priority_facts, watch_facts, normal_facts, ignore_facts],
        key=lambda facts: callout_priority(facts, event, now_sim=0.0),
    )
    assert ranked == [priority_facts, watch_facts, normal_facts, ignore_facts]


def test_callout_priority_ranks_nearer_range_above_farther_at_same_attention() -> None:
    event = _event()
    near: dict[str, object] = {
        "attention": "normal",
        "relative_now": {"range_m": 100.0},
    }
    far: dict[str, object] = {
        "attention": "normal",
        "relative_now": {"range_m": 9000.0},
    }
    assert callout_priority(near, event, 0.0) < callout_priority(far, event, 0.0)


def test_callout_priority_no_relative_now_sorts_last() -> None:
    """No `EnrichmentContext` (`relative_now` absent) must never sort ahead
    of a candidate with a real range -- `math.inf` fallback."""
    event = _event()
    unenriched: dict[str, object] = {"attention": "normal"}
    enriched: dict[str, object] = {
        "attention": "normal",
        "relative_now": {"range_m": 50000.0},
    }
    assert callout_priority(enriched, event, 0.0) < callout_priority(
        unenriched, event, 0.0
    )


def test_callout_priority_ranks_newer_event_above_older_at_same_range() -> None:
    older = _event(t_sim=0.0)
    newer = _event(t_sim=5.0)
    facts: dict[str, object] = {"attention": "normal"}
    assert callout_priority(facts, newer, 5.0) < callout_priority(facts, older, 5.0)


# --- CalloutScheduler.tick ---------------------------------------------------


def test_nothing_spoken_while_busy_until_sim_is_ahead() -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="BMP-2",
                classification_level=3,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    scheduler = CalloutScheduler(busy_until_sim=100.0)

    assert scheduler.tick(store, now_sim=1.0) == []
    # Nothing was consumed or acknowledged -- the candidate is still there,
    # simply not yet its turn.
    assert len(store.unacknowledged_events) == 1


def test_expired_candidate_is_never_spoken_and_never_acknowledged() -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="BMP-2",
                classification_level=3,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    scheduler = CalloutScheduler()

    past_deadline = CALLOUT_MAX_AGE_S + 1.0
    assert scheduler.tick(store, now_sim=past_deadline) == []
    # Expired, not spoken -- but a future brain's `poll_events` must still
    # see it (plan Decision 2: "body acks only what body said").
    assert len(store.unacknowledged_events) == 1
    # Re-ticking must not re-attempt it forever, and must still not speak it.
    assert scheduler.tick(store, now_sim=past_deadline + 1.0) == []
    assert len(store.unacknowledged_events) == 1


def test_vanished_contacts_candidate_is_skipped_and_the_next_is_taken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_A",
                t_sim=0.0,
                classification_raw="BMP-2",
                classification_level=3,
                dwp_x=0.0,
                dwp_z=0.0,
            ),
            _observation(
                obs_id="OBS_B",
                t_sim=0.0,
                classification_raw="T-72",
                classification_level=3,
                dwp_x=50000.0,
                dwp_z=0.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    vanished_id = store.contacts[0].id
    live_id = store.contacts[1].id

    import belief.callouts as callouts_module
    import belief.tools as tools_module

    real_describe_contact = tools_module.describe_contact

    def _describe_contact_unless_vanished(
        store_arg: ContactStore,
        contact_id: str,
        now_sim: float,
        enrichment: object = None,
    ) -> object:
        if contact_id == vanished_id:
            return None
        return real_describe_contact(
            store_arg, contact_id, now_sim, enrichment=enrichment
        )

    monkeypatch.setattr(
        callouts_module, "describe_contact", _describe_contact_unless_vanished
    )

    scheduler = CalloutScheduler()
    spoken = scheduler.tick(store, now_sim=1.0)

    assert spoken == ["T-72."]
    assert live_id not in {e.contact_id for e in store.unacknowledged_events}


def test_urgent_call_resets_occupancy_even_mid_routine_line() -> None:
    from belief.crew_console import CrewConsole

    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="BMP-2",
                classification_level=3,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store)
    # Simulate a routine line still believed in flight, far in the future.
    console.scheduler.busy_until_sim = 1000.0

    contact_id = store.contacts[0].id
    lines = console.handle_line(
        f"!inject-urgent {contact_id} Missile launch, break right!", now_sim=5.0
    )

    assert lines == ["Missile launch, break right!"]
    # `note_urgent` replaced the stale far-future occupancy with the
    # urgent line's own duration -- the scheduler is not still blocked.
    assert console.scheduler.busy_until_sim < 1000.0
    assert console.scheduler.busy_until_sim >= 5.0
