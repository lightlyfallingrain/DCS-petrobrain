"""The commanded-mark path -- plan Decision 6, Stage 3.

Reachable by voice and by the brain tool only -- no new F10 radio-menu
entry (BL-10 carries an explicit instruction not to re-expand the F10
tree, and this module does not get to quietly overrule it). Two fixed
forms: `mark_here` (ownship's current position) and `mark_target` (the
currently selected attack-run target's believed position, reusing
`select_target`'s own notion of "the current target"). The richer mark
forms the explore notes ask for (a named landmark, a grid coordinate) need
open-vocabulary speech and are BL-10/SRS territory -- `MarkPayload.anchor`
already has room for them.

Imports `belief` (Decision 1's one allowed direction). Calls
`store.MissionMemory.append`, never constructing `Entry` directly
(`tests/test_mission_memory_store.py`'s
`test_admission_and_marks_never_construct_entry_directly` enforces this).

**Position building is deliberately not shared with `admission.
_build_entry_position`.** That helper is keyed on a `Contact` (it reuses
`EnrichmentContext.cache.get_or_compute`'s per-contact cache and
terrain-aware lookup); a mark's subject is sometimes ownship itself, which
has no `Contact`. The small amount of position-building logic duplicated
here (`dcs_to_wgs84`, a landmark from `semantic_facts_for`) is accepted
rather than forced into one shape neither call site actually wants -- see
`_mark_position`'s own docstring."""

from __future__ import annotations

from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext, semantic_facts_for
from coordinates import dcs_to_wgs84
from mission_memory.entries import Entry, EntryPosition, MarkPayload, PhaseInfo
from mission_memory.store import MissionMemory
from perception.geometry import GeoPosition
from perception.source import OwnshipState

#: A mark's own position confidence for `semantic_facts_for`'s nearness
#: weighting -- always `1.0`. Unlike a contact's believed position, a mark
#: is set *now*, from a source (ownship telemetry, or the selected
#: target's current fused belief) with no separate staleness to discount;
#: `semantic_facts_for`'s `position_conf` parameter exists to fold in a
#: *stale look's* uncertainty, which does not apply here.
_MARK_POSITION_CONFIDENCE = 1.0


def _mark_position(
    x: float,
    z: float,
    alt_m: float,
    uncertainty_m: float,
    now_sim: float,
    theatre: str | None,
    enrichment: EnrichmentContext | None,
) -> EntryPosition:
    """Decision 8: `lat`/`lon` from the believed `x`/`z` only, `None` for
    an unregistered theatre (caught, never raised). `landmark` from
    `enrichment.semantic_facts_for`'s own near-fact radius, `None` when no
    `EnrichmentContext` is wired or nothing is in range (Decision 9) --
    same posture as `admission._build_entry_position`, without that
    function's per-contact cache (see module docstring)."""
    lat: float | None = None
    lon: float | None = None
    if theatre is not None:
        try:
            lat, lon = dcs_to_wgs84(theatre, x, z)
        except ValueError:
            lat, lon = None, None

    landmark: str | None = None
    if enrichment is not None:
        facts = semantic_facts_for(
            enrichment.conn,
            enrichment.theatre,
            GeoPosition(x=x, z=z, alt_m=alt_m),
            _MARK_POSITION_CONFIDENCE,
        )
        if facts:
            landmark = facts[0].text

    return EntryPosition(
        x=x,
        z=z,
        y=alt_m,
        uncertainty_m=uncertainty_m,
        as_of_sim=now_sim,
        lat=lat,
        lon=lon,
        landmark=landmark,
    )


def mark_here(
    memory: MissionMemory,
    ownship: OwnshipState,
    now_sim: float,
    *,
    theatre: str | None = None,
    phase: PhaseInfo | None = None,
    enrichment: EnrichmentContext | None = None,
    label: str | None = None,
) -> Entry:
    """Mark ownship's current position. Always succeeds -- there is no
    missing-input case for "where are we right now" the way there is for
    `mark_target`."""
    pos = _mark_position(
        ownship.x, ownship.z, ownship.alt_m, 0.0, now_sim, theatre, enrichment
    )
    return memory.append(
        kind="mark",
        provenance="commanded",
        t_sim=now_sim,
        phase=phase,
        pos=pos,
        seen=None,
        belief_ref=None,
        strikes=None,
        payload=MarkPayload(index=0, label=label, anchor="ownship"),
    )


def mark_target(
    memory: MissionMemory,
    contacts: ContactStore,
    contact_id: str,
    now_sim: float,
    *,
    theatre: str | None = None,
    phase: PhaseInfo | None = None,
    enrichment: EnrichmentContext | None = None,
    label: str | None = None,
) -> Entry | None:
    """Mark the currently selected target's believed position. Returns
    `None` for an unknown `contact_id` -- the caller (`crew_console.
    _handle_mark_target`) is expected to have already resolved "the
    selected target" via `_active_attack_target_task`; this is the second,
    defensive check, matching every other target-keyed command's
    "unknown id" convention (`tools.describe_contact`'s own docstring:
    "callers must not invent a contact for an unknown id")."""
    contact = contacts.contact(contact_id)
    if contact is None:
        return None
    pos = _mark_position(
        contact.position.x,
        contact.position.z,
        contact.last_alt_m,
        contact.position.radius_m(),
        now_sim,
        theatre,
        enrichment,
    )
    return memory.append(
        kind="mark",
        provenance="commanded",
        t_sim=now_sim,
        phase=phase,
        pos=pos,
        seen=None,
        belief_ref=contact_id,
        strikes=None,
        payload=MarkPayload(index=0, label=label, anchor="target"),
    )
