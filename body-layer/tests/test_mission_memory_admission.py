"""`mission_memory.admission` -- Stage 2's `group`/`air_defence` rules,
against a `ContactStore` built the same way `tests/test_belief_truth_log.
py`'s `_contact` fixture does: a real `ContactStore` with contacts injected
directly into its private dict, which is this codebase's own established
"fake store" pattern for these tests."""

from __future__ import annotations

from belief.cardinality import (
    OP_1UNIT,
    OP_TO5UNITS,
    CardinalityBelief,
    new_cardinality_belief,
)
from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact, ContactStore, SightingSpan
from belief.groups import Group
from belief.motion import MotionBelief
from belief.position_belief import Covariance2D, PositionEstimate
from mission_memory.admission import (
    GROUP_ENTRY_CONFIDENCE_FLOOR,
    RESIGHT_MIN_INTERVAL_S,
    RESIGHT_MOVE_M,
    step,
)
from mission_memory.entries import AirDefencePayload, GroupPayload
from mission_memory.store import MissionMemory

_ZERO_COV = Covariance2D(xx=0.0, zz=0.0, xz=0.0)


def _contact(
    *,
    contact_id: str = "CONTACT_1",
    x: float = 1000.0,
    z: float = 0.0,
    class_value: str | None = "OP_BTR",
    level: SpecificityLevel = SpecificityLevel.CLASS,
    confidence: float = 0.9,
    cardinality: CardinalityBelief | None = None,
    motion: MotionBelief | None = None,
    established_sim: float = 0.0,
    source: str = "naked_eye_visual_filtered",
) -> Contact:
    classification = new_classification_belief(
        value=class_value if class_value is not None else "OP_GROUPSOMETHING",
        level=level,
        established_sim=established_sim,
    )
    # `new_classification_belief` seeds the per-level default confidence;
    # override it directly where a test needs a specific value.
    classification = type(classification)(
        value=classification.value,
        level=classification.level,
        confidence=confidence,
        established_sim=classification.established_sim,
    )
    contact = Contact(
        id=contact_id,
        position=PositionEstimate(
            x=x,
            z=z,
            covariance=_ZERO_COV,
            as_of_sim=established_sim,
            fused_at_sim=established_sim,
            fused_covariance=_ZERO_COV,
        ),
        last_alt_m=0.0,
        last_class_raw=class_value or "unknown",
        classification=classification,
        cardinality=(
            cardinality
            if cardinality is not None
            else new_cardinality_belief(OP_1UNIT, established_sim)
        ),
        motion=motion,
        first_seen_sim=established_sim,
        last_seen_sim=established_sim,
    )
    contact.sighting_spans.append(
        SightingSpan(start_sim=established_sim, end_sim=established_sim, source=source)
    )
    return contact


def _store_with(*contacts: Contact) -> ContactStore:
    store = ContactStore()
    for contact in contacts:
        store._contacts[contact.id] = contact
    return store


# --- group rule -----------------------------------------------------------


def test_group_entry_written_once_crossing_the_confidence_floor() -> None:
    contact = _contact(confidence=GROUP_ENTRY_CONFIDENCE_FLOOR + 0.1)
    store = _store_with(contact)
    memory = MissionMemory()

    step(memory, store, now_sim=0.0)
    assert len(memory.entries) == 1
    assert memory.entries[0].kind == "group"
    assert memory.entries[0].belief_ref == "CONTACT_1"

    # Same poll state, re-run immediately -- must not write a second time
    # (not enough time has passed, and nothing changed).
    step(memory, store, now_sim=1.0)
    assert len(memory.entries) == 1


def test_below_confidence_floor_writes_nothing() -> None:
    contact = _contact(confidence=GROUP_ENTRY_CONFIDENCE_FLOOR - 0.1)
    store = _store_with(contact)
    memory = MissionMemory()

    step(memory, store, now_sim=0.0)
    assert memory.entries == []


def test_jitter_below_resight_move_m_writes_nothing() -> None:
    contact = _contact(confidence=GROUP_ENTRY_CONFIDENCE_FLOOR + 0.1, x=1000.0, z=0.0)
    store = _store_with(contact)
    memory = MissionMemory()
    step(memory, store, now_sim=0.0)
    assert len(memory.entries) == 1

    # Move by less than RESIGHT_MOVE_M and let enough time pass that the
    # interval gate would not itself be the reason nothing is written.
    contact.position = PositionEstimate(
        x=1000.0 + RESIGHT_MOVE_M * 0.1,
        z=0.0,
        covariance=_ZERO_COV,
        as_of_sim=RESIGHT_MIN_INTERVAL_S * 2,
        fused_at_sim=RESIGHT_MIN_INTERVAL_S * 2,
        fused_covariance=_ZERO_COV,
    )
    step(memory, store, now_sim=RESIGHT_MIN_INTERVAL_S * 2)
    assert len(memory.entries) == 1


def test_resight_past_the_move_threshold_strikes_and_appends() -> None:
    contact = _contact(confidence=GROUP_ENTRY_CONFIDENCE_FLOOR + 0.1, x=1000.0, z=0.0)
    store = _store_with(contact)
    memory = MissionMemory()
    step(memory, store, now_sim=0.0)
    first = memory.entries[0]

    contact.position = PositionEstimate(
        x=1000.0 + RESIGHT_MOVE_M * 2,
        z=0.0,
        covariance=_ZERO_COV,
        as_of_sim=RESIGHT_MIN_INTERVAL_S * 2,
        fused_at_sim=RESIGHT_MIN_INTERVAL_S * 2,
        fused_covariance=_ZERO_COV,
    )
    step(memory, store, now_sim=RESIGHT_MIN_INTERVAL_S * 2)

    entries = memory.entries
    assert len(entries) == 2
    assert entries[1].strikes == first.seq
    assert memory.is_struck(first.seq)


def test_resight_within_min_interval_is_suppressed_even_if_moved() -> None:
    contact = _contact(confidence=GROUP_ENTRY_CONFIDENCE_FLOOR + 0.1, x=1000.0, z=0.0)
    store = _store_with(contact)
    memory = MissionMemory()
    step(memory, store, now_sim=0.0)

    contact.position = PositionEstimate(
        x=1000.0 + RESIGHT_MOVE_M * 5,
        z=0.0,
        covariance=_ZERO_COV,
        as_of_sim=1.0,
        fused_at_sim=1.0,
        fused_covariance=_ZERO_COV,
    )
    step(memory, store, now_sim=1.0)
    assert len(memory.entries) == 1


# --- air defence rule ------------------------------------------------------


def test_air_defence_class_always_writes_its_own_entry() -> None:
    """Below the group floor on purpose -- the air-defence rule's
    "always" is independent of `GROUP_ENTRY_CONFIDENCE_FLOOR`."""
    contact = _contact(
        contact_id="CONTACT_AD",
        class_value="OP_SRSAM",
        confidence=GROUP_ENTRY_CONFIDENCE_FLOOR - 0.3,
    )
    store = _store_with(contact)
    memory = MissionMemory()

    step(memory, store, now_sim=0.0)
    assert len(memory.entries) == 1
    assert memory.entries[0].kind == "air_defence"


def test_air_defence_and_group_entries_link_both_ways_eventually() -> None:
    """Two contacts in one `belief.groups.Group`: a non-AD contact and an
    AD contact. Linking is one-directional at write time (Decision 4), so
    the AD entry links to the group entry immediately (written second),
    and the group entry only gains its own link back once it is re-written
    (module docstring's own explanation)."""
    group_contact = _contact(contact_id="CONTACT_GROUP", class_value="OP_BTR")
    ad_contact = _contact(contact_id="CONTACT_AD", class_value="OP_SRSAM")
    store = _store_with(group_contact, ad_contact)
    # `GroupStore.groups` (what `group_for_contact` reads) only returns a
    # group matched on the *most recent* `reconcile()` call -- injected
    # directly here (never calling `reconcile`), so both private fields
    # have to agree by hand: `_last_reconciled_sim` and the group's own
    # `last_observed_sim` must be equal, per `GroupStore.groups`'s filter.
    store._groups._groups = {"GROUP_1": _fake_group(group_contact.id, ad_contact.id)}
    store._groups._last_reconciled_sim = 0.0

    memory = MissionMemory()
    step(memory, store, now_sim=0.0)

    group_entry = next(e for e in memory.entries if e.belief_ref == "CONTACT_GROUP")
    ad_entry = next(e for e in memory.entries if e.belief_ref == "CONTACT_AD")
    assert isinstance(ad_entry.payload, AirDefencePayload)
    assert ad_entry.payload.group_link == group_entry.seq
    # Written in the same pass, before the AD entry existed yet.
    assert isinstance(group_entry.payload, GroupPayload)
    assert group_entry.payload.ad_link is None

    # Force the group contact's own re-write (material change) -- now it
    # can see the AD entry that already exists.
    group_contact.position = PositionEstimate(
        x=group_contact.position.x + RESIGHT_MOVE_M * 2,
        z=0.0,
        covariance=_ZERO_COV,
        as_of_sim=RESIGHT_MIN_INTERVAL_S * 2,
        fused_at_sim=RESIGHT_MIN_INTERVAL_S * 2,
        fused_covariance=_ZERO_COV,
    )
    step(memory, store, now_sim=RESIGHT_MIN_INTERVAL_S * 2)
    second_group_entry = next(
        e
        for e in memory.entries
        if e.belief_ref == "CONTACT_GROUP" and e.seq != group_entry.seq
    )
    assert isinstance(second_group_entry.payload, GroupPayload)
    assert second_group_entry.payload.ad_link == ad_entry.seq


def _fake_group(*member_ids: str) -> Group:
    return Group(
        id="GROUP_1",
        member_contact_ids=frozenset(member_ids),
        established_sim=0.0,
        last_reconciled_sim=0.0,
        last_observed_sim=0.0,
    )


# --- degenerate contact -----------------------------------------------------


def test_nullable_everything_contact_still_produces_a_valid_entry() -> None:
    """No motion belief, default `OP_1UNIT` cardinality, no world-model
    connection (`theatre=None`, `enrichment=None`) -- the common, mostly-
    empty case must still produce a valid, fully-decoded-shape entry
    rather than raising."""
    contact = _contact(
        confidence=GROUP_ENTRY_CONFIDENCE_FLOOR + 0.1,
        cardinality=new_cardinality_belief(OP_TO5UNITS, 0.0),
        motion=None,
    )
    store = _store_with(contact)
    memory = MissionMemory()

    step(memory, store, now_sim=0.0, theatre=None, phase=None, enrichment=None)

    assert len(memory.entries) == 1
    entry = memory.entries[0]
    assert entry.phase is None
    assert entry.pos is not None
    assert entry.pos.lat is None
    assert entry.pos.lon is None
    assert entry.pos.landmark is None
    assert isinstance(entry.payload, GroupPayload)
    assert entry.payload.motion.state is None
    assert entry.payload.motion.dir is None
    assert entry.payload.ad_link is None
