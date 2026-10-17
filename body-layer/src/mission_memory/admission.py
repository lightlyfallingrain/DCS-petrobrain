"""The worth-remembering admission rules -- plan Decision 3.

Imports `belief` (the one direction Decision 1 allows); reads a settled
`ContactStore`; calls `store.MissionMemory.append` to write entries, never
constructing `Entry` itself (`tests/test_mission_memory_store.py`'s
`test_admission_and_marks_never_construct_entry_directly` enforces this).
Holds every tuning constant Stage 2/3 introduce.

**Stage 2: the `group` and `air_defence` rules.** `mark`/`fired_on` are
Stage 3 (`marks.py`); `attack_run` is deferred (plan's effort/value flag).

**Writer is driven by belief-state transitions, not by percepts or
callouts** (Decision 3): `step` is called once per poll, from
`_mission_memory_step` in `logger.py`, after `ContactStore.tick()` has
settled this poll's belief and before any speech is drained.

**`Contact.last_percept` is not read here.** That field's own docstring
(`belief/contacts.py`) names `belief.attack_run` as its one sanctioned
reader outside the fields already pulled onto `Contact` itself; this
module lives outside `belief/` entirely and has no standing exception.
`SeenHow.optic` is instead read from `Contact.sighting_spans[-1].source`
-- the same channel-identifier string, already a legitimate per-contact
field -- and `SeenHow.range_m` stays `None` (the schema's own nullable
field for exactly this case: a real fact genuinely unavailable here)."""

from __future__ import annotations

import math
from typing import Final

import tuning
from belief.classification import (
    AIR_DEFENSE_OP_CLASSES,
    SpecificityLevel,
    parent_class_of,
)
from belief.contacts import Contact, ContactStore
from belief.decay import certainty_of
from belief.enrichment import EnrichmentContext
from belief.mission_phase import MissionPhaseInfo
from belief.speech import cardinality_phrase
from belief.threat import envelope_for
from coordinates import dcs_to_wgs84
from mission_memory.entries import (
    AirDefencePayload,
    CompositionItem,
    Entry,
    EntryPosition,
    GroupPayload,
    MotionInfo,
    PhaseInfo,
    SeenHow,
    ThreatInfo,
)
from mission_memory.store import MissionMemory

#: Decision 3's admission floor for the `group` rule: a contact's
#: classification must have reached `CLASS` specificity *and* be held at
#: or above this confidence before its first memory entry is written.
#: **Reuse-before-declaring per the plan** -- searched for an existing
#: "is this nameable yet" threshold on the describe/callout path
#: (`grep -rn "confidence >=\|CONFIDENCE_FLOOR" src/belief/`, 2026-10-17)
#: and found none: `classification.py`'s per-level confidences
#: (`_DEFAULT_CONFIDENCE_BY_LEVEL`) are starting values for a fold, not a
#: gate anything already checks before speaking or describing a class.
#: So this is a new key, not a second copy of an existing one.
GROUP_ENTRY_CONFIDENCE_FLOOR: Final[float] = tuning.fraction(
    "mission_memory.admission.GROUP_ENTRY_CONFIDENCE_FLOOR",
    0.5,
    status="agreed-guess",
)

#: Minimum believed-position displacement, in metres, a re-sighting must
#: show before a new group/air-defence memory line is written in place of
#: the standing one -- set this too low and the log churns on ordinary
#: position-belief jitter rather than real movement, since `belief.
#: position_belief.PositionEstimate` is a continuously fused estimate
#: carrying per-look noise, not the discrete ~500 m step buckets an
#: earlier model used. Unmeasured; Sortie A (plan's Implementation Plan)
#: is what actually calibrates this.
RESIGHT_MOVE_M: Final[float] = tuning.real(
    "mission_memory.admission.RESIGHT_MOVE_M",
    250.0,
    lo=50.0,
    hi=2000.0,
    status="agreed-guess",
)

#: The minimum sim-time, in seconds, between two memory entries for the
#: same contact -- even a genuine material change (Decision 3's "material
#: change" test) must wait this long since that contact's last entry
#: before it is written again, so a contact oscillating right at the
#: `RESIGHT_MOVE_M` boundary cannot flap the log every poll.
RESIGHT_MIN_INTERVAL_S: Final[float] = tuning.real(
    "mission_memory.admission.RESIGHT_MIN_INTERVAL_S",
    60.0,
    lo=5.0,
    hi=600.0,
    status="agreed-guess",
)


def _to_phase_info(phase: MissionPhaseInfo | None) -> PhaseInfo | None:
    if phase is None:
        return None
    return PhaseInfo(name=phase.name, waypoint_index=phase.waypoint_index)


def _composition_for(contact: Contact) -> tuple[CompositionItem, ...]:
    """One contact's own classification/cardinality, as the single-element
    composition list a per-contact entry carries. Empty when the contact
    has no classification value at all (`UNKNOWN` level) -- callers only
    reach this once a class-level-or-above check has already passed, but
    it stays total rather than assuming that."""
    value = contact.classification.value
    if value is None:
        return ()
    word = cardinality_phrase(contact.cardinality.lo, contact.cardinality.hi)
    return (
        CompositionItem(
            op_class=value,
            lo=contact.cardinality.lo,
            hi=contact.cardinality.hi,
            confidence=contact.classification.confidence,
            count_word=word,
        ),
    )


def _motion_info(contact: Contact) -> MotionInfo:
    state = contact.motion.state if contact.motion is not None else None
    # `dir` stays `None` through Stage 2/3 -- no direction belief exists
    # yet (plan Decision 2, point 1; explore-notes.md's two gaps).
    return MotionInfo(state=state, dir=None)


def _seen_how(contact: Contact, now_sim: float) -> SeenHow | None:
    """See module docstring on why this reads `sighting_spans`, never
    `last_percept`. `None` only for a contact with no sighting span at
    all, which `ContactStore.ingest`/`from_percept` never produces -- kept
    as a graceful `None` rather than assumed impossible, consistent with
    `pos`/`seen`'s own nullable schema."""
    if not contact.sighting_spans:
        return None
    return SeenHow(
        optic=contact.sighting_spans[-1].source,
        range_m=None,
        confidence=contact.classification.confidence,
        certainty=certainty_of(contact, now_sim),
    )


def _build_entry_position(
    contact: Contact,
    contacts: ContactStore,
    now_sim: float,
    theatre: str | None,
    enrichment: EnrichmentContext | None,
) -> EntryPosition:
    """Decision 8: every position comes from the *believed* `x`/`z`, never
    a DCS ground-truth position. `lat`/`lon` -- `dcs_to_wgs84` on the
    believed `x`/`z` -- are `None` for an unregistered theatre (caught,
    never raised past here: a memory write must never kill the poll
    loop). `landmark` is populated only from `enrichment.semantic_facts_for`'s
    own near-fact radius (via `EnrichmentContext.cache.get_or_compute`,
    reusing its per-contact cache rather than recomputing) -- `None`,
    the common case, when no `EnrichmentContext` is wired or no fact is
    in range (Decision 9)."""
    position = contact.position
    lat: float | None = None
    lon: float | None = None
    if theatre is not None:
        try:
            lat, lon = dcs_to_wgs84(theatre, position.x, position.z)
        except ValueError:
            lat, lon = None, None

    landmark: str | None = None
    if enrichment is not None:
        _world_position, facts = enrichment.cache.get_or_compute(
            enrichment.conn, enrichment.theatre, contacts, contact, now_sim
        )
        if facts:
            landmark = facts[0].text

    return EntryPosition(
        x=position.x,
        z=position.z,
        y=contact.last_alt_m,
        uncertainty_m=position.radius_m(),
        as_of_sim=position.as_of_sim,
        lat=lat,
        lon=lon,
        landmark=landmark,
    )


def _group_link_for(
    contacts: ContactStore, memory: MissionMemory, contact: Contact
) -> int | None:
    """The latest live memory entry's `seq` for some *other* member of
    `contact`'s `belief.groups.Group`, if it belongs to one with more than
    one member and that other member already has a written entry.

    **One-directional at write time, by design.** Decision 4 forbids
    mutating a past entry, so a group-mate written *before* `contact`
    cannot be retroactively linked -- it only gains the link the next time
    *it itself* is re-written (a resight or material change). Both
    `group`/`air_defence` entries call this the same way, which is what
    makes the link eventually symmetric across the two kinds without
    either one ever being edited in place."""
    group = contacts.group_for_contact(contact.id)
    if group is None or len(group.member_contact_ids) < 2:
        return None
    for other_id in group.member_contact_ids:
        if other_id == contact.id:
            continue
        seq = memory.latest_live_seq(other_id)
        if seq is not None:
            return seq
    return None


def _composition_changed(
    previous: tuple[CompositionItem, ...], current: tuple[CompositionItem, ...]
) -> bool:
    if len(previous) != len(current):
        return True
    for prev_item, cur_item in zip(previous, current):
        if prev_item.op_class != cur_item.op_class:
            return True
        if prev_item.lo != cur_item.lo or prev_item.hi != cur_item.hi:
            return True
    return False


def _material_change(
    last_entry: Entry,
    position_x: float,
    position_z: float,
    composition: tuple[CompositionItem, ...],
    motion: MotionInfo,
) -> bool:
    """Decision 3's "material change" test: believed position moved at
    least `RESIGHT_MOVE_M`, **or** composition changed class or
    cardinality bucket, **or** motion state changed. Does not itself
    check `RESIGHT_MIN_INTERVAL_S` -- callers gate on that separately,
    since it applies identically whether or not this test fires."""
    if last_entry.pos is not None:
        moved_m = math.hypot(
            position_x - last_entry.pos.x, position_z - last_entry.pos.z
        )
        if moved_m >= RESIGHT_MOVE_M:
            return True
    last_payload = last_entry.payload
    if isinstance(last_payload, (GroupPayload, AirDefencePayload)):
        if _composition_changed(last_payload.composition, composition):
            return True
        if isinstance(last_payload, GroupPayload) and last_payload.motion.state != (
            motion.state
        ):
            return True
    return False


def _maybe_write_entry_for_contact(
    memory: MissionMemory,
    contacts: ContactStore,
    contact: Contact,
    now_sim: float,
    theatre: str | None,
    phase: PhaseInfo | None,
    enrichment: EnrichmentContext | None,
) -> None:
    classification = contact.classification
    is_air_defence = (
        classification.value is not None
        and parent_class_of(classification.value) in AIR_DEFENSE_OP_CLASSES
    )
    nameable = classification.level >= SpecificityLevel.CLASS

    if is_air_defence:
        _maybe_write_air_defence(
            memory, contacts, contact, now_sim, theatre, phase, enrichment
        )
        return

    if not nameable:
        return
    if classification.confidence < GROUP_ENTRY_CONFIDENCE_FLOOR:
        last = memory.latest_entry(contact.id)
        if last is None:
            # Not yet nameable confidently enough for a *first* entry.
            return
        # Already has a standing entry from when it was nameable (e.g. a
        # contradiction knocked confidence back down since) -- Stage 2
        # does not retract a standing entry on a confidence dip, it only
        # stops offering new material-change writes until confidence
        # recovers. Falling through to the material-change check below
        # with the current (sub-floor) confidence is deliberate: a real
        # position/class/motion change is still worth recording even
        # while confidence is temporarily low.
    _write_group_entry(memory, contacts, contact, now_sim, theatre, phase, enrichment)


def _write_group_entry(
    memory: MissionMemory,
    contacts: ContactStore,
    contact: Contact,
    now_sim: float,
    theatre: str | None,
    phase: PhaseInfo | None,
    enrichment: EnrichmentContext | None,
) -> None:
    composition = _composition_for(contact)
    motion = _motion_info(contact)
    last_entry = memory.latest_entry(contact.id)

    if last_entry is not None:
        if now_sim - last_entry.t_sim < RESIGHT_MIN_INTERVAL_S:
            return
        if not _material_change(
            last_entry, contact.position.x, contact.position.z, composition, motion
        ):
            return

    pos = _build_entry_position(contact, contacts, now_sim, theatre, enrichment)
    memory.append(
        kind="group",
        provenance="observed",
        t_sim=now_sim,
        phase=phase,
        pos=pos,
        seen=_seen_how(contact, now_sim),
        belief_ref=contact.id,
        strikes=last_entry.seq if last_entry is not None else None,
        payload=GroupPayload(
            composition=composition,
            motion=motion,
            ad_link=_group_link_for(contacts, memory, contact),
        ),
    )


def _maybe_write_air_defence(
    memory: MissionMemory,
    contacts: ContactStore,
    contact: Contact,
    now_sim: float,
    theatre: str | None,
    phase: PhaseInfo | None,
    enrichment: EnrichmentContext | None,
) -> None:
    """Decision 3's `air_defence` rule: always its own entry, independent
    of `GROUP_ENTRY_CONFIDENCE_FLOOR` (the table's "always" -- air-defence
    identification is treated as worth recording the moment the class
    resolves, not gated on the same nameability floor as an ordinary
    group)."""
    composition = _composition_for(contact)
    motion = _motion_info(contact)
    last_entry = memory.latest_entry(contact.id)

    if last_entry is not None:
        if now_sim - last_entry.t_sim < RESIGHT_MIN_INTERVAL_S:
            return
        if not _material_change(
            last_entry, contact.position.x, contact.position.z, composition, motion
        ):
            return

    threat_envelope = envelope_for(contact.classification)
    threat = (
        ThreatInfo(
            envelope_m=threat_envelope.range_max_m,
            source=contact.classification.value,
        )
        if threat_envelope is not None and contact.classification.value is not None
        else None
    )
    pos = _build_entry_position(contact, contacts, now_sim, theatre, enrichment)
    memory.append(
        kind="air_defence",
        provenance="observed",
        t_sim=now_sim,
        phase=phase,
        pos=pos,
        seen=_seen_how(contact, now_sim),
        belief_ref=contact.id,
        strikes=last_entry.seq if last_entry is not None else None,
        payload=AirDefencePayload(
            composition=composition,
            group_link=_group_link_for(contacts, memory, contact),
            threat=threat,
        ),
    )


def step(
    memory: MissionMemory,
    contacts: ContactStore,
    now_sim: float,
    theatre: str | None = None,
    phase: MissionPhaseInfo | None = None,
    enrichment: EnrichmentContext | None = None,
) -> None:
    """Run every admission rule, once, over every current contact. Called
    once per poll by `logger._mission_memory_step`, after
    `ContactStore.tick()` -- see module docstring."""
    phase_info = _to_phase_info(phase)
    for contact in contacts.contacts:
        _maybe_write_entry_for_contact(
            memory, contacts, contact, now_sim, theatre, phase_info, enrichment
        )
