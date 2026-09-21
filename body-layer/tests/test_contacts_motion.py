"""Integration tests for `plans/movement-detection/plan.md` Stage 3 --
`Contact.record`'s motion fold and `ContactStore.tick`'s `CONTACT_MOTION_
CHANGED` emission, end to end through `ContactStore.ingest`/`tick` (not the
pure `fold_motion`/`motion_event_kind` unit tests, which live in
`test_belief_motion.py`/`test_events.py`). Mirrors `test_contacts.py`'s own
`_observation` helper, extended with `apparent_motion`."""

from __future__ import annotations

from belief.contacts import ContactStore
from belief.decay import MOTION_STOP_CONFIRM_S
from belief.events import CONTACT_DETECTED, CONTACT_MOTION_CHANGED, EVENT_COOLDOWN_S
from belief.motion import MotionBelief
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


def _ownship(t_sim: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=t_sim, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)


def _observation(
    *,
    obs_id: str,
    t_sim: float,
    apparent_motion: bool | None = None,
) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(t_sim),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        apparent_motion=apparent_motion,
    )


def test_founding_percept_with_no_motion_evidence_leaves_motion_none() -> None:
    """The scope/hybrid channel supplies no motion evidence at all --
    `Contact.motion` stays honestly `None`, not silently "stopped"."""
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=None)
    store.ingest([obs], now_sim=0.0)
    assert store.contacts[0].motion is None


def test_one_moving_observation_promotes_immediately() -> None:
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=True)
    store.ingest([obs], now_sim=0.0)
    contact = store.contacts[0]
    assert contact.motion is not None
    assert contact.motion.state == "moving"


def test_demotion_needs_confirm_window_not_one_observation() -> None:
    store = ContactStore()
    obs1 = _observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=True)
    store.ingest([obs1], now_sim=0.0)
    contact = store.contacts[0]
    assert contact.motion is not None and contact.motion.state == "moving"

    obs2 = _observation(obs_id="OBS_2", t_sim=1.0, apparent_motion=False)
    store.ingest([obs2], now_sim=1.0)
    assert contact.motion.state == "moving"  # one sub-threshold reading, not enough

    obs3 = _observation(
        obs_id="OBS_3", t_sim=1.0 + MOTION_STOP_CONFIRM_S, apparent_motion=False
    )
    store.ingest([obs3], now_sim=1.0 + MOTION_STOP_CONFIRM_S)
    assert contact.motion.state == "stopped"


def test_none_apparent_motion_never_demotes_or_promotes() -> None:
    store = ContactStore()
    obs1 = _observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=True)
    store.ingest([obs1], now_sim=0.0)
    contact = store.contacts[0]

    obs2 = _observation(obs_id="OBS_2", t_sim=1.0, apparent_motion=None)
    store.ingest([obs2], now_sim=1.0)
    assert contact.motion is not None and contact.motion.state == "moving"


def test_tick_emits_contact_motion_changed_after_promotion() -> None:
    store = ContactStore()
    obs1 = _observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=None)
    store.ingest([obs1], now_sim=0.0)
    store.tick(now_sim=0.0)
    assert [event.kind for event in store.events] == [CONTACT_DETECTED]

    obs2 = _observation(obs_id="OBS_2", t_sim=1.0, apparent_motion=True)
    store.ingest([obs2], now_sim=1.0)
    store.tick(now_sim=1.0)

    kinds = [event.kind for event in store.events]
    assert kinds == [CONTACT_DETECTED, CONTACT_MOTION_CHANGED]
    change_event = store.events[-1]
    assert change_event.previous_motion is None
    assert change_event.motion == "moving"


def test_event_cooldown_suppresses_emission_without_losing_the_transition() -> None:
    """Mirrors `test_contacts.py`'s own `test_event_cooldown_suppresses_
    rapid_reemission_but_not_after_it_elapses` for the new motion kind.
    State flips are forced directly on `Contact.motion` (bypassing the
    fold) so this test targets `tick`'s cooldown gate specifically, not
    `fold_motion`'s own confirm-window behaviour -- that's this file's
    sibling `test_demotion_needs_confirm_window_not_one_observation`."""
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=True)
    store.ingest([obs], now_sim=0.0)
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    assert [event.kind for event in store.events] == [
        CONTACT_DETECTED,
        CONTACT_MOTION_CHANGED,
    ]

    # Flip back within the cooldown window (the first CONTACT_MOTION_CHANGED
    # was emitted at t=0.0): the state comparison still notices the change
    # (the snapshot updates), but emission is suppressed.
    contact.motion = MotionBelief(state="stopped", confidence=0.5, established_sim=1.0)
    store.tick(now_sim=EVENT_COOLDOWN_S - 1.0)
    assert contact.last_emitted_motion == "stopped"
    assert [event.kind for event in store.events] == [
        CONTACT_DETECTED,
        CONTACT_MOTION_CHANGED,
    ]

    # Once the cooldown has elapsed, the next real change emits normally,
    # comparing against the true (already-updated) last-emitted state.
    contact.motion = MotionBelief(state="moving", confidence=0.5, established_sim=2.0)
    store.tick(now_sim=EVENT_COOLDOWN_S + 1.0)
    kinds = [event.kind for event in store.events]
    assert kinds == [
        CONTACT_DETECTED,
        CONTACT_MOTION_CHANGED,
        CONTACT_MOTION_CHANGED,
    ]
    assert store.events[-1].previous_motion == "stopped"
    assert store.events[-1].motion == "moving"
