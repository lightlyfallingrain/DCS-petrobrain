"""`mission_memory.tools` -- the two brain-facing tool functions, Stage 5
(`plans/bl8-mission-memory/plan.md` Decision 5)."""

from __future__ import annotations

import pytest

from belief.cardinality import OP_1UNIT, new_cardinality_belief
from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact, ContactStore
from belief.position_belief import Covariance2D, PositionEstimate
from mission_memory.store import MissionMemory
from mission_memory.tools import recall_memory, remember_location
from perception.source import OwnshipState

_ZERO_COV = Covariance2D(xx=0.0, zz=0.0, xz=0.0)


def _ownship(x: float = 0.0, z: float = 0.0, alt_m: float = 500.0) -> OwnshipState:
    return OwnshipState(
        x=x,
        z=z,
        alt_m=alt_m,
        heading_true_deg=0.0,
        pitch_deg=0.0,
        bank_deg=0.0,
        t_sim=0.0,
    )


def _contact(
    contact_id: str = "CONTACT_1", x: float = 1000.0, z: float = 0.0
) -> Contact:
    return Contact(
        id=contact_id,
        position=PositionEstimate(
            x=x,
            z=z,
            covariance=_ZERO_COV,
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=_ZERO_COV,
        ),
        last_alt_m=0.0,
        last_class_raw="OP_BTR",
        classification=new_classification_belief(
            value="OP_BTR", level=SpecificityLevel.CLASS, established_sim=0.0
        ),
        cardinality=new_cardinality_belief(OP_1UNIT, 0.0),
    )


def test_remember_location_default_anchor_marks_ownship() -> None:
    memory = MissionMemory()
    contacts = ContactStore()

    result = remember_location(
        memory, _ownship(x=500.0, z=1500.0), contacts, now_sim=0.0
    )

    assert result is not None
    assert result["kind"] == "mark"
    assert result["payload"]["anchor"] == "ownship"
    assert result["struck_by"] is None


def test_remember_location_target_anchor_marks_the_named_contact() -> None:
    memory = MissionMemory()
    contacts = ContactStore()
    contact = _contact(x=2000.0, z=500.0)
    contacts._contacts[contact.id] = contact

    result = remember_location(
        memory,
        _ownship(),
        contacts,
        now_sim=0.0,
        anchor="target",
        contact_id=contact.id,
    )

    assert result is not None
    assert result["belief_ref"] == contact.id
    assert result["payload"]["anchor"] == "target"


def test_remember_location_target_anchor_without_contact_id_raises() -> None:
    memory = MissionMemory()
    contacts = ContactStore()
    with pytest.raises(ValueError):
        remember_location(memory, _ownship(), contacts, now_sim=0.0, anchor="target")


def test_remember_location_target_anchor_unknown_contact_returns_none() -> None:
    memory = MissionMemory()
    contacts = ContactStore()

    result = remember_location(
        memory,
        _ownship(),
        contacts,
        now_sim=0.0,
        anchor="target",
        contact_id="CONTACT_NOPE",
    )

    assert result is None
    assert memory.entries == []


def test_recall_memory_passes_through_to_query() -> None:
    memory = MissionMemory()
    remember_location(memory, _ownship(), ContactStore(), now_sim=0.0)

    results = recall_memory(memory, kind="mark")

    assert len(results) == 1
    assert results[0]["kind"] == "mark"
