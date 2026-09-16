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
which source(s) contributed to it, and its attention state (BL-2 Stage 4
added the bare mark; BL-4 makes `facts.attention` the *effective* value --
direct mark folded with area membership via `belief.attention.
effective_attention` -- and `facts.attention_source` distinguishes a direct
mark from an area-derived one). §3.4's full response shape also has
`position.confidence`,
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
no basis to compute (BL-6, per `plans/bl4-attention-events/plan.md`'s
"Narrows BL-6" second-order-effect note -- attention is not threat).

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

**`set_attention`/`get_stats`.** Not part of §3.3's four read tools, but
`belief.console`'s Stage 4 task constraint is that it "owns no belief logic
itself, just parses commands and formats `tools.py`'s output" -- so the
`stats` console command's actual counting lives here, in the same
plain-function shape as the four §3.3 tools, rather than in the console's
command dispatch. `set_attention` *is* named directly in §3.3 (BL-4, `plans/
bl4-attention-events/plan.md`) -- it replaces BL-2 Stage 4's `watch_contact`/
`unwatch_contact` with the general four-level form; `console.py`'s `watch`/
`unwatch` commands now call it with `level="watch"`/`"normal"` rather than
having their own tool functions, so existing console output is unchanged.

**`watch_area`/`unwatch_area`/`list_areas`, `get_attention_state`,
`list_events`/`acknowledge_event`.** BL-4's remaining additions. `watch_area`/
`unwatch_area` mirror `set_attention`'s console-facing shape but for
`belief.attention.AttentionArea` registration rather than a single contact's
direct mark; `list_areas` is not one of §3.3's named tools (same "console
needs it, so it lives here, not in console.py" reasoning as `stats`).
`list_events`/`acknowledge_event` are BL-4's event-queue mechanism this
stage builds in full -- BL-5 only adds the transport and the `{facts,
summary, phrasing_hints}` wrapping around them (plan's Q2 decision).

**`scan_area`/`get_task_status`/`cancel_task`.** BL-6 (`plans/
bl6-commands-inspect-adapt/plan.md`), §3.3's tool-set freeze point.
`scan_area` composes two existing pieces of machinery rather than adding
new belief logic: it registers a `"watch"`-level `belief.attention.
AttentionArea` (exactly `watch_area`'s own call into `store.add_area`) and,
over the same area, a `belief.tasks.PendingIntent` (`belief.tasks.
TaskStore.create`) -- the same "one command, two existing registries"
pattern `watch_area` itself already established for areas alone. **This
function stays pure/DCS-I/O free**, per the project's hard testability
requirement -- it never triggers a real Petrovich search; that live
trigger is `console.py`'s `scan-area` handler's job (the same "wire the
live effect one layer up" split BL-2.5 drew for the overlay push, not
inside `tools.py`). Every description below must therefore be read
together with the tool registry's (`tool_api.py`) explicit caveat: this
tool asks Petrovich to search and reports whether something relevant was
subsequently observed in the named area -- it never aims him at a bearing,
and a `"failed"` outcome from `get_task_status` never means "confirmed
empty" (see `belief.tasks`'s own module docstring for the full epistemic
caveat, and the plan's "Risks & Unknowns" for why this is a *harder* gap
than an earlier design's). `cancel_task` also removes the `AttentionArea`
`scan_area` registered (the plan's Decision 3, user-resolved 2026-09-11):
cancelling a scan stops watching that area entirely, not just its own
success/timeout bookkeeping."""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal, TypedDict

from belief.attention import (
    Attention,
    AttentionArea,
    RelativeSector,
    Sector,
    effective_attention,
)
from belief.contacts import Contact, ContactStore
from belief.decay import (
    Certainty,
    certainty_of,
    classification_confidence_at,
    position_confidence,
)
from belief.enrichment import (
    EnrichmentContext,
    SemanticFact,
    motion_when_seen,
    relative_geometry,
    semantic_facts_for,
)
from belief.events import Event
from belief.mission_phase import MissionPhaseTracker, mission_phase_relevance
from belief.tasks import PendingIntent, TaskKind, TaskStore
from perception.geometry import GeoPosition
from perception.source import OwnshipState
from query.search import PlaceMatch, find_place_by_name

#: `scan_area`'s default deadline, in sim-seconds -- BL-6 (`plans/
#: bl6-commands-inspect-adapt/plan.md`'s Risks & Unknowns: "still a
#: placeholder needing live-sortie calibration," same status the plan's
#: original design carried). Long enough to cover one un-aimed `SRCH FWD`
#: sweep plus a real detection's association latency, short enough that a
#: console operator gets a `"failed"` answer within one sitting rather than
#: waiting indefinitely.
DEFAULT_SCAN_DEADLINE_S: float = 60.0

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


class ToolResult(TypedDict):
    """The same `{facts, summary, phrasing_hints}` triple as `ContactResult`
    (§3.4), for BL-5's three new tools whose subject isn't a single
    contact: `find_place`'s per-match results, `describe_our_position`,
    `get_situation`. Kept as a separate TypedDict rather than reusing
    `ContactResult` so a reader isn't misled into thinking these results
    carry contact-shaped `facts`."""

    facts: dict[str, object]
    summary: str
    phrasing_hints: dict[str, object]


ContactFilter = Literal["all", "visible", "watched"]


def _find_contact(store: ContactStore, contact_id: str) -> Contact | None:
    for contact in store.contacts:
        if contact.id == contact_id:
            return contact
    return None


def _classification_facts(contact: Contact, now_sim: float) -> dict[str, object]:
    """`facts.classification`'s shape, moved *toward* `plans/body-layer/
    plan.md` §3.4's specified `{value, confidence}` (this stage adds
    `level` too, since the lattice level is exactly what makes the
    `CONTACT_CLASSIFICATION_CHANGED` transition legible) -- reads
    `Contact.classification` (the folded best claim), not
    `last_class_raw` (`plans/classification-refinement/plan.md`'s design
    section: "everything user-facing ... reads `Contact.classification`
    instead"). `confidence` is read through `belief.decay.
    classification_confidence_at`, not `classification.confidence` raw --
    the design section's "confidence is free to fall" invariant, decaying
    over `IDENTITY_HALF_LIFE_S` since the claim's `established_sim`. `level`
    is read straight off the held claim -- it never decays, by design."""
    classification = contact.classification
    return {
        "value": classification.value,
        "level": classification.level.name.lower(),
        "confidence": classification_confidence_at(contact, now_sim),
    }


def _contact_facts(
    contact: Contact,
    now_sim: float,
    store: ContactStore,
    attention_level: Attention,
    attention_area_id: str | None,
    enrichment: EnrichmentContext | None = None,
) -> dict[str, object]:
    certainty = certainty_of(contact, now_sim)
    facts: dict[str, object] = {
        "id": contact.id,
        "classification": _classification_facts(contact, now_sim),
        "certainty": certainty,
        "visible": certainty == "observed",
        "last_seen_ago_s": round(max(0.0, now_sim - contact.last_seen_sim), 1),
        "position": {
            "dcs": {"x": contact.last_position.x, "z": contact.last_position.z}
        },
        "sources": sorted({span.source for span in contact.sighting_spans}),
        "attention": attention_level,
    }
    if attention_area_id is not None:
        facts["attention_source"] = f"area:{attention_area_id}"
    elif contact.attention_source is not None:
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


def _format_range_km(range_m: float) -> str:
    """`range_m`, formatted for `_contact_summary`'s appended fragment --
    1 decimal place of kilometres (e.g. `"3.0 km"`, `"0.4 km"`). No existing
    km-rounding helper exists elsewhere in the codebase to reuse (checked
    `naked_eye_source.py`'s `_quantise_range_m`, a classification-bucket
    helper, not a display formatter)."""
    return f"{range_m / 1000:.1f} km"


def _contact_summary(
    contact: Contact,
    now_sim: float,
    attention_level: Attention,
    relative_now: dict[str, object] | None = None,
) -> str:
    certainty = certainty_of(contact, now_sim)
    if certainty == "observed":
        recency = "currently visible"
    else:
        ago_s = max(0.0, now_sim - contact.last_seen_sim)
        recency = f"last seen {ago_s:.0f}s ago"
    classification_value = contact.classification.value or "unknown"
    summary = f"{classification_value}, {certainty}, {recency}."
    if attention_level == "watch":
        summary += " Being watched."
    elif attention_level == "priority":
        summary += " Priority attention."
    if relative_now is not None:
        clock_position = relative_now["clock_position"]
        range_m = relative_now["range_m"]
        assert isinstance(range_m, float)
        summary = summary.rstrip(".")
        summary += f", {clock_position} o'clock, {_format_range_km(range_m)}."
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
    attention_level, attention_area_id = effective_attention(
        contact.attention, contact.last_position, store.areas
    )
    facts = _contact_facts(
        contact, now_sim, store, attention_level, attention_area_id, enrichment
    )
    relative_now = facts.get("relative_now")
    assert relative_now is None or isinstance(relative_now, dict)
    return ContactResult(
        facts=facts,
        summary=_contact_summary(contact, now_sim, attention_level, relative_now),
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
    and `"watched"` are the only two with real machinery; §3.3's
    `"threats"`/`"near_aircraft"` still need threat assessment (BL-6), so
    they are not offered rather than faked. `"watched"` (BL-4) is now
    `effective_attention in ("watch", "priority")` -- a contact inside a
    watched/priority `AttentionArea` shows up here even with an unmarked
    direct attention, matching what `facts.attention` reports for it via
    `describe_contact`. `enrichment` (BL-3, optional) is threaded into every
    returned result the same way."""
    contacts = store.contacts
    if filter == "visible":
        contacts = [c for c in contacts if certainty_of(c, now_sim) == "observed"]
    elif filter == "watched":
        contacts = [
            c
            for c in contacts
            if effective_attention(c.attention, c.last_position, store.areas)[0]
            in ("watch", "priority")
        ]
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
    """Text search over contacts' *perceived* classification -- never a
    truth field. Searches the held best claim (`Contact.classification.
    value`), not `last_class_raw` (`plans/classification-refinement/
    plan.md`'s design section: everything user-facing reads `classification`
    instead), so a contact refined to `"T-72"` is still found by `"T-72"`
    even if the most recent contributing percept was a coarser re-sighting.
    Case-insensitive substring match; empty/whitespace-only `text` matches
    nothing rather than returning every contact; a contact whose
    classification is still unresolved (`value is None`) never matches.
    Most-recently-seen first, mirroring `get_contacts`. `enrichment` (BL-3,
    optional, not named in the plan's explicit function list but threaded
    here too for consistency with `get_contacts`/`describe_contact` -- both
    build the same `ContactResult` via `_contact_result`, so leaving this
    one unenriched would be a surprising, undocumented gap) is threaded
    into every returned result the same way."""
    needle = text.strip().lower()
    if not needle:
        return []
    matches = [
        c
        for c in store.contacts
        if c.classification.value is not None
        and needle in c.classification.value.lower()
    ]
    matches.sort(key=lambda c: c.last_seen_sim, reverse=True)
    return [_contact_result(contact, now_sim, store, enrichment) for contact in matches]


def set_attention(
    store: ContactStore, contact_id: str, level: Attention, source: str = "console"
) -> bool:
    """Mark a contact's *direct* attention (BL-4, `plans/
    bl4-attention-events/plan.md`'s §3.3 `set_attention` signature) --
    replaces BL-2 Stage 4's `watch_contact`/`unwatch_contact` with the
    general four-level form. `level == "normal"` clears `attention_source`
    to `None` (the neutral default carries no source, matching
    `unwatch_contact`'s old behavior exactly); every other level records
    `source`. Returns whether `contact_id` was found. Note this sets the
    contact's own *direct* mark only -- `facts.attention`/`get_contacts`'s
    `"watched"` filter both report the *effective* value (`belief.attention.
    effective_attention`), which an `AttentionArea` can raise above what
    this function alone sets."""
    contact = _find_contact(store, contact_id)
    if contact is None:
        return False
    contact.attention = level
    contact.attention_source = source if level != "normal" else None
    return True


def watch_area(
    store: ContactStore,
    center: GeoPosition,
    radius_m: float,
    level: Attention = "watch",
    sector: Sector | None = None,
    source: str = "console",
    relative_sector: RelativeSector | None = None,
) -> AttentionArea:
    """Register a new `belief.attention.AttentionArea` (BL-4). `center` is
    an already-resolved `GeoPosition` -- turning a bearing/range pair (or,
    later, a place name via `find_place`) into that position is the
    caller's job, not this function's (`console.py`'s `watch-area` command
    does the bearing/range resolution via `perception.geometry.
    project_from_bearing_range`; see the plan's "watch_area's place-name
    gap" risk for why `find_place` resolution is explicitly out of scope
    here). Returns the stored `AttentionArea`, including its store-minted
    `id`, so the caller can report it back to the user."""
    return store.add_area(
        center=center,
        radius_m=radius_m,
        level=level,
        source=source,
        sector=sector,
        relative_sector=relative_sector,
    )


def unwatch_area(store: ContactStore, area_id: str) -> bool:
    """Unregister an `AttentionArea`. Returns whether `area_id` was found."""
    return store.remove_area(area_id)


def list_areas(store: ContactStore) -> list[AttentionArea]:
    """Every registered `AttentionArea`, for `console.py`'s `areas`
    command -- not one of §3.3's named tools, same "console needs it, so it
    lives here" reasoning as `get_stats`."""
    return store.areas


def get_attention_state(
    store: ContactStore, contact_id: str
) -> dict[str, object] | None:
    """A contact's direct mark alongside its effective attention (BL-4,
    §3.3) -- `None` if `contact_id` does not exist. `direct_source`/`area_id`
    are omitted (not `None`) when there is no direct source or no area
    contributed the effective value, the same absent-not-empty convention
    as `facts` elsewhere in this module."""
    contact = _find_contact(store, contact_id)
    if contact is None:
        return None
    effective, area_id = effective_attention(
        contact.attention, contact.last_position, store.areas
    )
    state: dict[str, object] = {
        "contact_id": contact.id,
        "direct": contact.attention,
        "effective": effective,
    }
    if contact.attention_source is not None:
        state["direct_source"] = contact.attention_source
    if area_id is not None:
        state["area_id"] = area_id
    return state


def _event_to_dict(event: Event) -> dict[str, object]:
    """One `belief.events.Event` flattened to a plain dict for `list_events`
    -- mirrors `get_contact_history`'s existing event-entry shape (`type`
    omitted here since every element of `list_events`'s result is an event,
    unlike `get_contact_history`'s mixed sighting/event list), extended
    with the id an `acknowledge_event` call needs and the classification/
    attention transition fields when the event's kind populates them."""
    entry: dict[str, object] = {
        "id": event.id,
        "contact_id": event.contact_id,
        "kind": event.kind,
        "t_sim": event.t_sim,
        "certainty": event.certainty,
    }
    if event.previous_classification is not None:
        entry["previous_classification"] = event.previous_classification
    if event.classification is not None:
        entry["classification"] = event.classification
    if event.direction is not None:
        entry["direction"] = event.direction
    if event.previous_attention is not None:
        entry["previous_attention"] = event.previous_attention
    if event.attention is not None:
        entry["attention"] = event.attention
    return entry


def list_events(
    store: ContactStore, unacknowledged_only: bool = True
) -> list[dict[str, object]]:
    """BL-4's event-queue read (`plans/bl4-attention-events/plan.md`'s Q2
    decision -- this milestone builds the full mechanism, BL-5 only wraps
    it). `unacknowledged_only=True` (the default) is `store.
    unacknowledged_events`; `False` returns the complete log, oldest
    first (matching `store.events`'s own emission order)."""
    events = store.unacknowledged_events if unacknowledged_only else store.events
    return [_event_to_dict(event) for event in events]


def acknowledge_event(store: ContactStore, event_id: str) -> bool:
    """Mark one event acknowledged. Returns whether `event_id` was found."""
    return store.acknowledge_event(event_id)


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


def find_place(enrichment: EnrichmentContext, text: str) -> list[ToolResult]:
    """`plans/bl5-tool-api/plan.md`'s net-new name->position tool --
    wraps world-model's `query.search.find_place_by_name` (the world-model
    in-process seam, same seam `belief.enrichment` already uses via
    `query.describe.describe_position`) in the `{facts, summary,
    phrasing_hints}` triple every other tool in this module returns.
    Deliberately naive substring matching, same caveat as `find_place_by_
    name`'s own docstring: "the LZ" or "the ridge to the west" will not
    resolve here, only names literally close to a stored feature's `name`
    field."""
    matches = find_place_by_name(enrichment.conn, text)
    return [_place_result(match) for match in matches]


def _place_result(match: PlaceMatch) -> ToolResult:
    facts: dict[str, object] = {
        "name": match.name,
        "kind": match.kind,
        "feature_id": match.feature_id,
        "position": {"dcs": {"x": match.x, "z": match.z}},
        "confidence": match.confidence,
        "provenance": match.provenance,
    }
    summary = f"{match.name} ({match.kind})"
    phrasing_hints: dict[str, object] = {
        "confidence": "exact" if match.confidence >= 1.0 else "approximate"
    }
    return ToolResult(facts=facts, summary=summary, phrasing_hints=phrasing_hints)


def _our_position_summary(
    ownship: OwnshipState, semantic_facts: list[SemanticFact]
) -> str:
    if semantic_facts:
        location = max(semantic_facts, key=lambda fact: fact.confidence).text
    else:
        location = "an unknown location"
    return (
        f"Currently {location}, heading {ownship.heading_true_deg:.0f} deg, "
        f"{ownship.alt_m:.0f}m altitude."
    )


def describe_our_position(enrichment: EnrichmentContext) -> ToolResult:
    """Ownship position + world-model semantic facts (`plans/
    bl5-tool-api/plan.md`'s Decision 3: `enrichment` is required, not
    optional -- there is no smaller "BL-2-shape" fallback this tool can
    degrade to, unlike the contact-facing tools' optional `enrichment`).
    Reuses `belief.enrichment.semantic_facts_for` (the same mapping
    `_add_enrichment_facts` uses for a contact's position) with
    `position_conf=1.0`, since ownship's own telemetry position is ground
    truth, not a belief-derived, decaying estimate -- there is no
    `position_confidence` to fold in here."""
    ownship = enrichment.ownship
    position = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    semantic_facts = semantic_facts_for(
        enrichment.conn, enrichment.theatre, position, 1.0
    )
    facts: dict[str, object] = {
        "position": {"dcs": {"x": ownship.x, "z": ownship.z}},
        "alt_m": ownship.alt_m,
        "heading_true_deg": ownship.heading_true_deg,
        "semantic": [asdict(fact) for fact in semantic_facts],
    }
    summary = _our_position_summary(ownship, semantic_facts)
    return ToolResult(facts=facts, summary=summary, phrasing_hints={})


def _select_from_tier(
    contacts: list[Contact], mission_phase_tracker: MissionPhaseTracker | None
) -> Contact:
    """Picks one contact from an already-filtered attention tier (BL-7,
    `plans/bl7-mission-phase-relevance/plan.md`). When mission-phase data is
    loaded and there is an active phase, `mission_phase_relevance` (distance
    to that phase's route waypoint, ascending -- closer wins) is the
    tie-break *before* `last_seen_sim`, but only when a relevance value is
    available for every candidate; otherwise this falls back to the
    original `last_seen_sim`-only rule, unchanged from before this
    milestone. Attention rank itself (which tier a contact is even in)
    stays the dominant signal -- this function only orders within one
    already-chosen tier."""
    if mission_phase_tracker is not None:
        phase = mission_phase_tracker.current_phase()
        if phase is not None:
            route = mission_phase_tracker.data.route
            relevances: dict[str, float] = {}
            for contact in contacts:
                relevance = mission_phase_relevance(contact.last_position, phase, route)
                if relevance is None:
                    break
                relevances[contact.id] = relevance
            else:
                return min(
                    contacts,
                    key=lambda contact: (
                        relevances[contact.id],
                        -contact.last_seen_sim,
                    ),
                )
    return max(contacts, key=lambda contact: contact.last_seen_sim)


def _highest_attention_contact(
    store: ContactStore,
    now_sim: float,
    mission_phase_tracker: MissionPhaseTracker | None = None,
) -> Contact | None:
    """Deterministic stand-in for a real relevance score (BL-6 hasn't built
    one yet, per `plans/bl5-tool-api/plan.md`'s Risks & Unknowns):
    `priority` > `watch` > most-recently-observed `visible`, in that order.
    Ties within a tier break per `_select_from_tier` above -- mission-phase
    proximity first (BL-7, when available), `last_seen_sim` otherwise."""
    priority: list[Contact] = []
    watch: list[Contact] = []
    for contact in store.contacts:
        effective, _ = effective_attention(
            contact.attention, contact.last_position, store.areas
        )
        if effective == "priority":
            priority.append(contact)
        elif effective == "watch":
            watch.append(contact)
    if priority:
        return _select_from_tier(priority, mission_phase_tracker)
    if watch:
        return _select_from_tier(watch, mission_phase_tracker)
    visible = [c for c in store.contacts if certainty_of(c, now_sim) == "observed"]
    if visible:
        return _select_from_tier(visible, mission_phase_tracker)
    return None


def get_situation(
    store: ContactStore,
    now_sim: float,
    enrichment: EnrichmentContext,
    mission_phase_tracker: MissionPhaseTracker | None = None,
) -> ToolResult:
    """Aggregate sitrep (`plans/bl5-tool-api/plan.md`): contact counts
    (total/visible/watched), the highest-attention contact (see
    `_highest_attention_contact`), the unacknowledged event count, and
    `describe_our_position`'s own summary line, folded into one `{facts,
    summary, phrasing_hints}` result. `enrichment` is required for the same
    reason as `describe_our_position`'s -- this tool has no meaning without
    ownship/world-model access.

    `mission_phase_tracker` (BL-7, optional) adds `facts["mission_phase"]`:
    **absent entirely** when no tracker is supplied (no mission data
    loaded -- the same absent-not-empty convention this module already
    uses for `enrichment`-gated facts), present but `None` when a tracker
    is loaded but ownship hasn't reached the first phase's waypoint yet,
    and the active phase's name otherwise -- so a caller can tell "no
    mission data" from "before first phase" instead of both collapsing to
    a missing/null value. The summary line only gets a `"Phase: <name>."`
    fragment appended when a phase is actually active, mirroring
    `unacknowledged_events`'s "only mention it if there's something to
    say" pattern."""
    total = len(store.contacts)
    visible = sum(1 for c in store.contacts if certainty_of(c, now_sim) == "observed")
    watched = sum(
        1
        for c in store.contacts
        if effective_attention(c.attention, c.last_position, store.areas)[0]
        in ("watch", "priority")
    )
    unacknowledged = len(store.unacknowledged_events)
    our_position = describe_our_position(enrichment)

    facts: dict[str, object] = {
        "contact_counts": {"total": total, "visible": visible, "watched": watched},
        "unacknowledged_events": unacknowledged,
        "our_position_summary": our_position["summary"],
    }

    active_phase = None
    if mission_phase_tracker is not None:
        active_phase = mission_phase_tracker.current_phase()
        facts["mission_phase"] = active_phase.name if active_phase is not None else None

    highest = _highest_attention_contact(store, now_sim, mission_phase_tracker)
    summary_parts = [f"{total} contact(s) ({visible} visible, {watched} watched)."]
    if highest is not None:
        highest_result = _contact_result(highest, now_sim, store, enrichment)
        facts["highest_attention_contact"] = highest_result
        summary_parts.append(f"Highest attention: {highest_result['summary']}")
    if unacknowledged:
        summary_parts.append(f"{unacknowledged} unacknowledged event(s).")
    if active_phase is not None:
        summary_parts.append(f"Phase: {active_phase.name}.")
    summary_parts.append(our_position["summary"])

    return ToolResult(facts=facts, summary=" ".join(summary_parts), phrasing_hints={})


def poll_events(store: ContactStore) -> list[dict[str, object]]:
    """`plans/bl5-tool-api/plan.md`'s Decision 4: the exact name §3.3's
    tool list uses for BL-4's already-built unacknowledged-events read
    (`list_events(store, unacknowledged_only=True)`) -- a one-line wrapper,
    not a rewrite. `console.py`'s `events` command keeps calling
    `list_events` directly (unchanged); this is the name the tool registry
    (`tool_api.py`) exposes."""
    return list_events(store, unacknowledged_only=True)


def scan_area(
    store: ContactStore,
    tasks: TaskStore,
    center: GeoPosition,
    radius_m: float,
    reason: str,
    now_sim: float,
    deadline_s: float = DEFAULT_SCAN_DEADLINE_S,
    sector: Sector | None = None,
    relative_sector: RelativeSector | None = None,
) -> PendingIntent:
    """Ask Petrovich to search, and register what "found something relevant"
    would mean for that ask -- BL-6 (`plans/bl6-commands-inspect-adapt/
    plan.md`). Registers a `"watch"`-level `AttentionArea` (`store.add_area`,
    the same call `watch_area` makes) and a `belief.tasks.PendingIntent`
    over that same area (`tasks.create`), whose `deadline_sim` is
    `now_sim + deadline_s`. `now_sim` -- unlike `watch_area`'s signature --
    is required here because `PendingIntent.created_sim`/`deadline_sim` are
    sim-time, never wall clock, the same replay-determinism requirement
    every other `belief.*` timestamp in this codebase carries; `center` is
    an already-resolved `GeoPosition`, same division of responsibility as
    `watch_area`'s own docstring (bearing/range resolution is the caller's
    job, `console.py`'s `scan-area` handler).

    **Does not trigger a live search.** This function is pure/DCS-I/O free
    (see this module's own docstring) -- the console command handler that
    calls this is also responsible for the live effector call, wrapped in
    its own failure handling, so a failed live trigger never prevents the
    belief-state task from being registered. Returns the stored
    `PendingIntent`, including its store-minted `id`, so the caller can
    report it back."""
    area = store.add_area(
        center=center,
        radius_m=radius_m,
        level="watch",
        source="scan_area",
        sector=sector,
        relative_sector=relative_sector,
    )
    kind: TaskKind = "scan_area"
    return tasks.create(
        kind=kind,
        area=area,
        created_sim=now_sim,
        deadline_sim=now_sim + deadline_s,
        reason=reason,
    )


def get_task_status(tasks: TaskStore, task_id: str) -> PendingIntent | None:
    """A `scan_area` (or any future task kind's) current status, or `None`
    if `task_id` does not exist. **`"failed"` never means "confirmed
    empty"** -- see `belief.tasks`'s module docstring for the full epistemic
    caveat this function's result must be read with; a future wording layer
    must not upgrade a timeout into a stronger claim than the task's own
    status makes."""
    return tasks.get(task_id)


def cancel_task(store: ContactStore, tasks: TaskStore, task_id: str) -> bool:
    """Cancel a still-pending task and remove the `AttentionArea` it
    registered (the plan's Decision 3, user-resolved 2026-09-11: cancelling
    a scan stops watching that area entirely, not just its own
    success/timeout bookkeeping). Returns whether `task_id` was found --
    mirrors `unwatch_area`'s/`TaskStore.cancel`'s own "unknown id returns
    `False`" convention. Reads `task.area.id` off the found task before
    calling `store.remove_area`, since `TaskStore` itself never holds a
    `ContactStore` reference (see `belief.tasks.TaskStore.cancel`'s
    docstring)."""
    task = tasks.get(task_id)
    if task is None:
        return False
    tasks.cancel(task_id)
    store.remove_area(task.area.id)
    return True
