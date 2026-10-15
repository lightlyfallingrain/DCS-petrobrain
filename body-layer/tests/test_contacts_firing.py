"""Integration tests for `plans/emitter-visibility/plan.md` Stage B
(`BL-B73`) -- `Contact.record`'s `is_firing`/`firing_targets_ownship`
assignment and `ContactStore.tick`'s `CONTACT_FIRING_SEEN` emission, end to
end through `ContactStore.ingest`/`tick`. Mirrors `test_contacts_burning.
py`'s own structure and `_observation` helper."""

from __future__ import annotations

from belief.contacts import ContactStore
from belief.events import CONTACT_DETECTED, CONTACT_FIRING_SEEN, EVENT_COOLDOWN_S
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.naked_eye_source import (
    PROVENANCE_EMITTER_FIRING,
    PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP,
    PROVENANCE_VISIBILITY_FILTER_ONLY,
)
from perception.source import DerivedWorldPosition, Observation, OwnshipState


def _ownship(t_sim: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=t_sim, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)


def _observation(
    *,
    obs_id: str,
    t_sim: float,
    provenance: str,
    bearing_deg: float = 0.0,
) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="Ural truck",
        bearing_deg=bearing_deg,
        range_m=1000.0,
        ownship_at_observation=_ownship(t_sim),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance=provenance,
    )


def test_founding_percept_without_emitter_provenance_leaves_is_firing_false() -> None:
    store = ContactStore()
    obs = _observation(
        obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_VISIBILITY_FILTER_ONLY
    )
    store.ingest([obs], now_sim=0.0)
    contact = store.contacts[0]
    assert contact.is_firing is False
    assert contact.firing_targets_ownship is False


def test_founding_percept_with_emitter_firing_provenance_sets_is_firing_true() -> None:
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_FIRING)
    store.ingest([obs], now_sim=0.0)
    contact = store.contacts[0]
    assert contact.is_firing is True
    assert contact.firing_targets_ownship is False


def test_founding_percept_targeting_ownship_sets_both_fields() -> None:
    store = ContactStore()
    obs = _observation(
        obs_id="OBS_1",
        t_sim=0.0,
        provenance=PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP,
    )
    store.ingest([obs], now_sim=0.0)
    contact = store.contacts[0]
    assert contact.is_firing is True
    assert contact.firing_targets_ownship is True


def test_is_firing_reverts_when_a_later_percept_no_longer_carries_the_provenance() -> (
    None
):
    """`record` overwrites, like `is_burning` -- not a fold."""
    store = ContactStore()
    obs1 = _observation(
        obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP
    )
    store.ingest([obs1], now_sim=0.0)
    contact = store.contacts[0]
    assert contact.is_firing is True
    assert contact.firing_targets_ownship is True

    obs2 = _observation(
        obs_id="OBS_2", t_sim=1.0, provenance=PROVENANCE_VISIBILITY_FILTER_ONLY
    )
    store.ingest([obs2], now_sim=1.0)
    assert contact.is_firing is False
    assert contact.firing_targets_ownship is False


def test_tick_emits_contact_firing_seen_after_the_entering_transition() -> None:
    store = ContactStore()
    obs1 = _observation(
        obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_VISIBILITY_FILTER_ONLY
    )
    store.ingest([obs1], now_sim=0.0)
    store.tick(now_sim=0.0)
    assert [event.kind for event in store.events] == [CONTACT_DETECTED]

    obs2 = _observation(obs_id="OBS_2", t_sim=1.0, provenance=PROVENANCE_EMITTER_FIRING)
    store.ingest([obs2], now_sim=1.0)
    store.tick(now_sim=1.0)

    kinds = [event.kind for event in store.events]
    assert kinds == [CONTACT_DETECTED, CONTACT_FIRING_SEEN]


def test_tick_emits_contact_firing_seen_when_founded_already_firing() -> None:
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_FIRING)
    store.ingest([obs], now_sim=0.0)
    store.tick(now_sim=0.0)

    kinds = [event.kind for event in store.events]
    assert kinds == [CONTACT_DETECTED, CONTACT_FIRING_SEEN]


def test_firing_event_carries_targets_ownship_from_the_contact() -> None:
    store = ContactStore()
    obs = _observation(
        obs_id="OBS_1",
        t_sim=0.0,
        provenance=PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP,
    )
    store.ingest([obs], now_sim=0.0)
    store.tick(now_sim=0.0)

    firing_events = [e for e in store.events if e.kind == CONTACT_FIRING_SEEN]
    assert len(firing_events) == 1
    assert firing_events[0].targets_ownship is True


def test_firing_event_not_targeting_ownship_carries_false() -> None:
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_FIRING)
    store.ingest([obs], now_sim=0.0)
    store.tick(now_sim=0.0)

    firing_events = [e for e in store.events if e.kind == CONTACT_FIRING_SEEN]
    assert len(firing_events) == 1
    assert firing_events[0].targets_ownship is False


def test_leaving_transition_emits_nothing() -> None:
    store = ContactStore()
    obs1 = _observation(obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_FIRING)
    store.ingest([obs1], now_sim=0.0)
    store.tick(now_sim=0.0)
    assert [event.kind for event in store.events] == [
        CONTACT_DETECTED,
        CONTACT_FIRING_SEEN,
    ]

    obs2 = _observation(
        obs_id="OBS_2", t_sim=1.0, provenance=PROVENANCE_VISIBILITY_FILTER_ONLY
    )
    store.ingest([obs2], now_sim=1.0)
    store.tick(now_sim=1.0)

    assert not any(e.kind == CONTACT_FIRING_SEEN for e in store.events[2:])


def test_event_cooldown_suppresses_rapid_reemission_but_not_after_it_elapses() -> None:
    store = ContactStore()
    obs1 = _observation(obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_FIRING)
    store.ingest([obs1], now_sim=0.0)
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    assert [event.kind for event in store.events] == [
        CONTACT_DETECTED,
        CONTACT_FIRING_SEEN,
    ]

    contact.is_firing = False
    store.tick(now_sim=0.5)
    contact.is_firing = True
    store.tick(now_sim=EVENT_COOLDOWN_S - 1.0)
    assert [event.kind for event in store.events] == [
        CONTACT_DETECTED,
        CONTACT_FIRING_SEEN,
    ]

    contact.is_firing = False
    store.tick(now_sim=EVENT_COOLDOWN_S)
    contact.is_firing = True
    store.tick(now_sim=EVENT_COOLDOWN_S + 1.0)
    kinds = [event.kind for event in store.events]
    assert kinds == [
        CONTACT_DETECTED,
        CONTACT_FIRING_SEEN,
        CONTACT_FIRING_SEEN,
    ]
