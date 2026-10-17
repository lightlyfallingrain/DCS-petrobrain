"""`mission_memory.marks` -- `mark_here`/`mark_target`, Stage 3."""

from __future__ import annotations

from belief.cardinality import OP_1UNIT, new_cardinality_belief
from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact, ContactStore
from belief.position_belief import Covariance2D, PositionEstimate
from mission_memory.entries import MarkPayload
from mission_memory.marks import mark_here, mark_target
from mission_memory.store import MissionMemory
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


def test_mark_here_writes_an_ownship_anchored_entry() -> None:
    memory = MissionMemory()
    entry = mark_here(memory, _ownship(x=500.0, z=1500.0, alt_m=200.0), now_sim=0.0)

    assert entry.kind == "mark"
    assert entry.provenance == "commanded"
    assert entry.belief_ref is None
    assert isinstance(entry.payload, MarkPayload)
    assert entry.payload.anchor == "ownship"
    assert entry.pos is not None
    assert (entry.pos.x, entry.pos.z, entry.pos.y) == (500.0, 1500.0, 200.0)


def test_mark_here_indices_are_minted_through_append_and_never_reused() -> None:
    """The index comes from `store.MissionMemory.append`, the single
    construction site -- `marks.py` never mints its own, and a struck
    mark's number is retired with it (Co-moving Fields table)."""
    memory = MissionMemory()
    first = mark_here(memory, _ownship(), now_sim=0.0, label="LZ")
    second = mark_here(memory, _ownship(), now_sim=1.0, label="FARP")

    assert isinstance(first.payload, MarkPayload)
    assert isinstance(second.payload, MarkPayload)
    assert first.payload.index == 1
    assert second.payload.index == 2

    # Strike the first mark (an "update mark 1" path this plan does not
    # build yet, but the store must still honour the invariant if one
    # ever did): a replacement never reuses the struck mark's own number.
    third = memory.append(
        kind="mark",
        provenance="commanded",
        t_sim=2.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref=None,
        strikes=first.seq,
        payload=MarkPayload(index=0, label="LZ (moved)", anchor="ownship"),
    )
    assert isinstance(third.payload, MarkPayload)
    assert third.payload.index == 3
    assert memory.is_struck(first.seq)


def test_mark_target_writes_the_targets_believed_position() -> None:
    contacts = ContactStore()
    contact = _contact(x=2000.0, z=500.0)
    contacts._contacts[contact.id] = contact
    memory = MissionMemory()

    entry = mark_target(memory, contacts, contact.id, now_sim=0.0)

    assert entry is not None
    assert entry.belief_ref == contact.id
    assert isinstance(entry.payload, MarkPayload)
    assert entry.payload.anchor == "target"
    assert entry.pos is not None
    assert (entry.pos.x, entry.pos.z) == (2000.0, 500.0)


def test_mark_target_unknown_contact_returns_none() -> None:
    memory = MissionMemory()
    result = mark_target(memory, ContactStore(), "CONTACT_NOPE", now_sim=0.0)
    assert result is None
    assert memory.entries == []
