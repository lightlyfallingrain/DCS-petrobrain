"""Tests for `belief.tools`'s `facts["motion"]` -- `plans/
movement-detection/plan.md` Stage 4. Mirrors `test_tools.py`'s own
`_observation`/`_store_with_one_contact` helpers, extended with
`apparent_motion`."""

from __future__ import annotations

import pytest

from belief.contacts import ContactStore
from belief.decay import MOTION_HALF_LIFE_S
from belief.tools import describe_contact
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


def _ownship() -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)


def _observation(
    *, obs_id: str, t_sim: float, apparent_motion: bool | None
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
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        apparent_motion=apparent_motion,
    )


def test_facts_omit_motion_when_never_observed_for_movement() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=None)], now_sim=0.0
    )
    contact = store.contacts[0]
    result = describe_contact(store, contact.id, now_sim=0.0)
    assert result is not None
    assert "motion" not in result["facts"]


def test_facts_include_motion_state_and_confidence_when_moving() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=True)], now_sim=0.0
    )
    contact = store.contacts[0]
    result = describe_contact(store, contact.id, now_sim=0.0)
    assert result is not None
    motion_facts = result["facts"]["motion"]
    assert isinstance(motion_facts, dict)
    assert motion_facts["state"] == "moving"
    assert isinstance(motion_facts["confidence"], float)


def test_facts_motion_confidence_decays_with_elapsed_time() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=True)], now_sim=0.0
    )
    contact = store.contacts[0]
    held_confidence = contact.motion.confidence  # type: ignore[union-attr]
    fresh = describe_contact(store, contact.id, now_sim=0.0)
    later = describe_contact(store, contact.id, now_sim=MOTION_HALF_LIFE_S)
    assert fresh is not None and later is not None
    fresh_motion = fresh["facts"]["motion"]
    later_motion = later["facts"]["motion"]
    assert isinstance(fresh_motion, dict) and isinstance(later_motion, dict)
    assert fresh_motion["confidence"] == pytest.approx(held_confidence)
    assert later_motion["confidence"] == pytest.approx(held_confidence / 2.0)
    # `state` never decays -- only the confidence number does.
    assert later_motion["state"] == fresh_motion["state"] == "moving"
