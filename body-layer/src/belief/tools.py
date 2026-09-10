"""The brain API's body, minus a transport -- `plans/pb2-contact-memory/
plan.md` Stage 4. Four plain functions mirror `plans/body-layer/plan.md`
§3.3's `get_contacts`/`describe_contact`/`get_contact_history`/
`find_contact` signatures and each contact-facing one returns that plan's
`{facts, summary, phrasing_hints}` triple (§3.4). BL-5 adds a transport over
this module; it does not rewrite it.

**What `facts` may and may not contain.** `facts` carries only what BL-2
actually knows about a `belief.contacts.Contact`: its id, its last perceived
classification, its `belief.decay.Certainty`, how long ago it was last
observed, its last *implied* (belief-derived, not ground-truth) position,
which source(s) contributed to it, and its bare attention state (this
stage's addition). §3.4's full response shape also has `position.confidence`,
`semantic` (world-model place references), a clock-bearing `relative_now`,
and `motion_when_seen` -- BL-3 (`plans/bl3-world-enrichment/plan.md`) adds
all four, but only when the optional `enrichment: belief.enrichment.
EnrichmentContext | None` parameter every contact-facing function below
takes is actually supplied; `None` (the default) leaves `facts` in exactly
BL-2's original shape, so existing callers are unaffected. Those keys are
**absent from the dict entirely, not present with a null value** when
enrichment is unavailable or a given fact has none to report -- a consumer
must be able to tell "BL-2/BL-3 doesn't know this yet" from "checked and
found nothing," and a present-but-null key collapses that distinction. The
same absent-not-empty rule is why `phrasing_hints` never carries an
`urgency` key here: urgency is a threat-assessment judgment this module has
no basis to compute (BL-4).

**Identity invariant.** Every function here reads only `Contact` fields,
which are themselves derived exclusively from `belief.percept.Percept`
(see `percept.py`/`contacts.py`'s own module docstrings) -- never
`Observation`'s DCS ground-truth position field or a DCS object id.
`position` below is `Contact.last_position`, the percept-implied position
from `perception.association_over_time.implied_position` at record time,
not a ground-truth coordinate.

**`summary`.** Per the plan's Decision 3 (user-confirmed), a minimal
one-line human-readable string per contact, built from `classification_raw`
and the `certainty` ladder. Real templating (structured wording rules,
per-attribute phrasing) is `plans/body-layer/plan.md` §6 BL-5a's job; this
is deliberately plain enough that it cannot be mistaken for that.

**`watch_contact`/`unwatch_contact`/`get_stats`.** Not part of §3.3's four
read tools (their eventual brain-facing equivalents -- `set_attention`,
`get_attention_state` -- are BL-4/BL-5 work this stage does not build), but
`belief.console`'s Stage 4 task constraint is that it "owns no belief logic
itself, just parses commands and formats `tools.py`'s output" -- so the
`watch <id>`/`unwatch <id>`/`stats` console commands' actual state mutation
and counting live here, in the same plain-function shape as the four §3.3
tools, rather than in the console's command dispatch.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal, TypedDict

from belief.contacts import Contact, ContactStore
from belief.decay import Certainty, certainty_of, position_confidence
from belief.enrichment import EnrichmentContext, motion_when_seen, relative_geometry

#: `phrasing_hints.certainty`'s vocabulary -- deliberately distinct wording
#: from the internal `belief.decay.Certainty` ladder (`"observed"` etc.),
#: since `phrasing_hints` is what a wording layer reads, not the belief
#: state itself. Kept as a small fixed mapping rather than reusing the
#: ladder's own strings verbatim, per §3.4's own example
#: (`phrasing_hints: {certainty: remembered}` for a `"tracked"`/`"estimated"`
#: contact, not the raw enum word).
_PHRASING_CERTAINTY: dict[Certainty, str] = {
    "observed": "current",
    "tracked": "recent",
    "estimated": "remembered",
    "lost": "lost",
}


class ContactResult(TypedDict):
    """The §3.4 `{facts, summary, phrasing_hints}` triple, returned by every
    contact-facing tool below (`get_contacts`'s list elements,
    `describe_contact`, `find_contact`'s list elements)."""

    facts: dict[str, object]
    summary: str
    phrasing_hints: dict[str, object]


ContactFilter = Literal["all", "visible", "watched"]


def _find_contact(store: ContactStore, contact_id: str) -> Contact | None:
    for contact in store.contacts:
        if contact.id == contact_id:
            return contact
    return None


def _contact_facts(
    contact: Contact,
    now_sim: float,
    store: ContactStore,
    enrichment: EnrichmentContext | None = None,
) -> dict[str, object]:
    certainty = certainty_of(contact, now_sim)
    facts: dict[str, object] = {
        "id": contact.id,
        "classification": {"value": contact.last_class_raw},
        "certainty": certainty,
        "visible": certainty == "observed",
        "last_seen_ago_s": round(max(0.0, now_sim - contact.last_seen_sim), 1),
        "position": {
            "dcs": {"x": contact.last_position.x, "z": contact.last_position.z}
        },
        "sources": sorted({span.source for span in contact.sighting_spans}),
        "attention": contact.attention,
    }
    if contact.attention_source is not None:
        facts["attention_source"] = contact.attention_source
    if enrichment is not None:
        _add_enrichment_facts(facts, contact, now_sim, store, enrichment)
    return facts


def _add_enrichment_facts(
    facts: dict[str, object],
    contact: Contact,
    now_sim: float,
    store: ContactStore,
    enrichment: EnrichmentContext,
) -> None:
    """BL-3's addition to `facts` -- `plans/bl3-world-enrichment/plan.md`.
    Mutates `facts` in place (the `position` dict already built by
    `_contact_facts` above gains a `confidence` key; `semantic`/
    `relative_now`/`motion_when_seen` are new top-level keys, the last one
    omitted entirely rather than `None` when `belief.enrichment.
    motion_when_seen` has too little history to derive a direction)."""
    position_conf = position_confidence(contact, now_sim)
    position_dict = facts["position"]
    assert isinstance(position_dict, dict)
    position_dict["confidence"] = position_conf

    world_position, semantic_facts = enrichment.cache.get_or_compute(
        enrichment.conn, enrichment.theatre, store, contact, now_sim
    )
    facts["semantic"] = [asdict(fact) for fact in semantic_facts]
    facts["relative_now"] = relative_geometry(enrichment.ownship, world_position)

    motion = motion_when_seen(store, contact)
    if motion is not None:
        facts["motion_when_seen"] = motion


def _contact_summary(contact: Contact, now_sim: float) -> str:
    certainty = certainty_of(contact, now_sim)
    if certainty == "observed":
        recency = "currently visible"
    else:
        ago_s = max(0.0, now_sim - contact.last_seen_sim)
        recency = f"last seen {ago_s:.0f}s ago"
    summary = f"{contact.last_class_raw}, {certainty}, {recency}."
    if contact.attention == "watch":
        summary += " Being watched."
    return summary


def _contact_phrasing_hints(contact: Contact, now_sim: float) -> dict[str, object]:
    certainty = certainty_of(contact, now_sim)
    return {"certainty": _PHRASING_CERTAINTY[certainty]}


def _contact_result(
    contact: Contact,
    now_sim: float,
    store: ContactStore,
    enrichment: EnrichmentContext | None = None,
) -> ContactResult:
    return ContactResult(
        facts=_contact_facts(contact, now_sim, store, enrichment),
        summary=_contact_summary(contact, now_sim),
        phrasing_hints=_contact_phrasing_hints(contact, now_sim),
    )


def get_contacts(
    store: ContactStore,
    now_sim: float,
    filter: ContactFilter | None = None,
    enrichment: EnrichmentContext | None = None,
) -> list[ContactResult]:
    """List current contacts, most-recently-seen first. `filter` is
    deliberately minimal -- `"visible"` (currently `certainty == "observed"`)
    and `"watched"` (`attention == "watch"`) are the only two BL-2 has real
    machinery for; §3.3's `"threats"`/`"near_aircraft"` still need threat
    assessment (BL-4), so they are not offered rather than faked. `enrichment`
    (BL-3, optional) is threaded into every returned result the same way."""
    contacts = store.contacts
    if filter == "visible":
        contacts = [c for c in contacts if certainty_of(c, now_sim) == "observed"]
    elif filter == "watched":
        contacts = [c for c in contacts if c.attention == "watch"]
    contacts = sorted(contacts, key=lambda c: c.last_seen_sim, reverse=True)
    return [
        _contact_result(contact, now_sim, store, enrichment) for contact in contacts
    ]


def describe_contact(
    store: ContactStore,
    contact_id: str,
    now_sim: float,
    enrichment: EnrichmentContext | None = None,
) -> ContactResult | None:
    """Everything BL-2/BL-3 knows about one contact, or `None` if
    `contact_id` does not exist -- callers must not invent a contact for an
    unknown id. `enrichment` (BL-3, optional) adds `position.confidence`,
    `semantic`, `relative_now`, and (where derivable) `motion_when_seen` to
    `facts`; omitted, this is byte-for-byte BL-2's original behavior."""
    contact = _find_contact(store, contact_id)
    if contact is None:
        return None
    return _contact_result(contact, now_sim, store, enrichment)


def get_contact_history(
    store: ContactStore, contact_id: str
) -> list[dict[str, object]]:
    """The contact's sighting-span/event history, oldest first: each
    contiguous span during which one source continuously contributed
    observations (`belief.contacts.SightingSpan`), interleaved with the
    lifecycle events `ContactStore.tick` has materialised for it
    (`belief.events.Event`). Returns an empty list for an unknown
    `contact_id` -- no separate `None` case, since "no history" and
    "unknown contact" are indistinguishable from the caller's point of view
    without also calling `describe_contact`."""
    contact = _find_contact(store, contact_id)
    if contact is None:
        return []
    entries: list[dict[str, object]] = []
    for span in contact.sighting_spans:
        entries.append(
            {
                "type": "sighting",
                "source": span.source,
                "start_sim": span.start_sim,
                "end_sim": span.end_sim,
            }
        )
    for event in store.events:
        if event.contact_id == contact_id:
            entries.append(
                {
                    "type": "event",
                    "kind": event.kind,
                    "t_sim": event.t_sim,
                    "certainty": event.certainty,
                }
            )

    def _sort_key(entry: dict[str, object]) -> float:
        value = entry.get("start_sim", entry.get("t_sim", 0.0))
        assert isinstance(value, float)
        return value

    entries.sort(key=_sort_key)
    return entries


def find_contact(
    store: ContactStore,
    text: str,
    now_sim: float,
    enrichment: EnrichmentContext | None = None,
) -> list[ContactResult]:
    """Text search over contacts' *perceived* classification
    (`Contact.last_class_raw`) -- never a truth field. Case-insensitive
    substring match; empty/whitespace-only `text` matches nothing rather
    than returning every contact. Most-recently-seen first, mirroring
    `get_contacts`. `enrichment` (BL-3, optional, not named in the plan's
    explicit function list but threaded here too for consistency with
    `get_contacts`/`describe_contact` -- both build the same `ContactResult`
    via `_contact_result`, so leaving this one unenriched would be a
    surprising, undocumented gap) is threaded into every returned result the
    same way."""
    needle = text.strip().lower()
    if not needle:
        return []
    matches = [c for c in store.contacts if needle in c.last_class_raw.lower()]
    matches.sort(key=lambda c: c.last_seen_sim, reverse=True)
    return [_contact_result(contact, now_sim, store, enrichment) for contact in matches]


def watch_contact(
    store: ContactStore, contact_id: str, source: str = "console"
) -> bool:
    """Mark a contact watched -- a bare attention enum + source field, no
    policy/cooldown/relevance scoring (that is BL-4). Returns whether
    `contact_id` was found."""
    contact = _find_contact(store, contact_id)
    if contact is None:
        return False
    contact.attention = "watch"
    contact.attention_source = source
    return True


def unwatch_contact(store: ContactStore, contact_id: str) -> bool:
    """Clear a contact's watched state. Returns whether `contact_id` was
    found."""
    contact = _find_contact(store, contact_id)
    if contact is None:
        return False
    contact.attention = "normal"
    contact.attention_source = None
    return True


def get_stats(store: ContactStore) -> dict[str, int]:
    """Observation/contact/event counts -- for measuring stream volume
    live, per the plan's Stage 4 acceptance and the PB-1.5 backlog note on
    needing this for calibration (`plans/pb2-contact-memory/plan.md`'s Risks
    & Unknowns, "Observation volume under `every_poll`")."""
    return {
        "observations": len(store.observations),
        "contacts": len(store.contacts),
        "events": len(store.events),
    }
