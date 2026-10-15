"""Integration tests for `plans/emitter-visibility/plan.md` Stage A
(`BL-B72`) -- `Contact.record`'s `is_burning` assignment and `ContactStore.
tick`'s `CONTACT_BURNING_SEEN` emission, end to end through `ContactStore.
ingest`/`tick` (not the pure `burning_event_kind` unit tests, which live in
`test_events.py`). Mirrors `test_contacts_motion.py`'s own `_observation`
helper, substituting `provenance` for `apparent_motion`."""

from __future__ import annotations

from belief.contacts import ContactStore
from belief.events import CONTACT_BURNING_SEEN, CONTACT_DETECTED, EVENT_COOLDOWN_S
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.naked_eye_source import (
    PROVENANCE_EMITTER_BURNING,
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


def test_founding_percept_without_emitter_provenance_leaves_is_burning_false() -> None:
    store = ContactStore()
    obs = _observation(
        obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_VISIBILITY_FILTER_ONLY
    )
    store.ingest([obs], now_sim=0.0)
    assert store.contacts[0].is_burning is False


def test_founding_percept_with_emitter_burning_provenance_sets_is_burning_true() -> (
    None
):
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_BURNING)
    store.ingest([obs], now_sim=0.0)
    assert store.contacts[0].is_burning is True


def test_is_burning_reverts_when_a_later_percept_no_longer_carries_the_provenance() -> (
    None
):
    """`record` overwrites, like `last_class_raw` -- not a fold. A contact
    re-observed without the emitter bypass this poll (e.g. it cleared the
    range gate unaided) is no longer believed burning from that look."""
    store = ContactStore()
    obs1 = _observation(
        obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_BURNING
    )
    store.ingest([obs1], now_sim=0.0)
    contact = store.contacts[0]
    assert contact.is_burning is True

    obs2 = _observation(
        obs_id="OBS_2", t_sim=1.0, provenance=PROVENANCE_VISIBILITY_FILTER_ONLY
    )
    store.ingest([obs2], now_sim=1.0)
    assert contact.is_burning is False


def test_tick_emits_contact_burning_seen_after_the_entering_transition() -> None:
    store = ContactStore()
    obs1 = _observation(
        obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_VISIBILITY_FILTER_ONLY
    )
    store.ingest([obs1], now_sim=0.0)
    store.tick(now_sim=0.0)
    assert [event.kind for event in store.events] == [CONTACT_DETECTED]

    obs2 = _observation(
        obs_id="OBS_2", t_sim=1.0, provenance=PROVENANCE_EMITTER_BURNING
    )
    store.ingest([obs2], now_sim=1.0)
    store.tick(now_sim=1.0)

    kinds = [event.kind for event in store.events]
    assert kinds == [CONTACT_DETECTED, CONTACT_BURNING_SEEN]


def test_tick_emits_contact_burning_seen_when_founded_already_burning() -> None:
    """Unlike `CONTACT_MOTION_CHANGED` (whose `previous is None` is the
    ordinary first-tick suppression case), a contact founded already
    burning emits `CONTACT_BURNING_SEEN` on its very first tick -- see
    `burning_event_kind`'s own docstring."""
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_BURNING)
    store.ingest([obs], now_sim=0.0)
    store.tick(now_sim=0.0)

    kinds = [event.kind for event in store.events]
    assert kinds == [CONTACT_DETECTED, CONTACT_BURNING_SEEN]


def test_leaving_transition_emits_nothing() -> None:
    store = ContactStore()
    obs1 = _observation(
        obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_BURNING
    )
    store.ingest([obs1], now_sim=0.0)
    store.tick(now_sim=0.0)
    assert [event.kind for event in store.events] == [
        CONTACT_DETECTED,
        CONTACT_BURNING_SEEN,
    ]

    obs2 = _observation(
        obs_id="OBS_2", t_sim=1.0, provenance=PROVENANCE_VISIBILITY_FILTER_ONLY
    )
    store.ingest([obs2], now_sim=1.0)
    store.tick(now_sim=1.0)

    assert not any(e.kind == CONTACT_BURNING_SEEN for e in store.events[2:])


def test_event_cooldown_suppresses_rapid_reemission_but_not_after_it_elapses() -> None:
    store = ContactStore()
    obs1 = _observation(
        obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_BURNING
    )
    store.ingest([obs1], now_sim=0.0)
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    assert [event.kind for event in store.events] == [
        CONTACT_DETECTED,
        CONTACT_BURNING_SEEN,
    ]

    # Flip back and forth within the cooldown window -- the comparison
    # still notices each change (the snapshot updates), but emission is
    # suppressed.
    contact.is_burning = False
    store.tick(now_sim=0.5)
    contact.is_burning = True
    store.tick(now_sim=EVENT_COOLDOWN_S - 1.0)
    assert [event.kind for event in store.events] == [
        CONTACT_DETECTED,
        CONTACT_BURNING_SEEN,
    ]

    # Once the cooldown has elapsed, the next real entering transition
    # emits normally.
    contact.is_burning = False
    store.tick(now_sim=EVENT_COOLDOWN_S)
    contact.is_burning = True
    store.tick(now_sim=EVENT_COOLDOWN_S + 1.0)
    kinds = [event.kind for event in store.events]
    assert kinds == [
        CONTACT_DETECTED,
        CONTACT_BURNING_SEEN,
        CONTACT_BURNING_SEEN,
    ]
