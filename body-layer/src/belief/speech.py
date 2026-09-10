"""`OutgoingSpeech`, body-written templates, and `route_event` -- the
outbound half of `plans/body-layer/plan.md` §2.1/§3.6, implementing
`plans/bl5a-text-mode-crew-interaction/plan.md`'s Stage 2.

**Three templated classes** (§2.1's "Outbound: three classes of speech",
class 1 -- "Templated, body-written"): command readbacks
(`render_readback`), contact reports (`render_contact_report`, single-
contact only -- see the "No contact clustering" note below), and urgent
reactive calls (`route_event` given an `UrgentCall`). All three are final
text body itself writes; no brain is ever consulted for them.

**`route_event` is the outbound routing gate.** It checks whether the thing
it was given is an urgent call *before* anything else: an `UrgentCall`
speaks immediately, pre-empting, with no cooldown/relevance/ack machinery
touched at all (§2.1: "exempt from the cooldown, relevance-scoring and
already-mentioned suppression... pre-empt in-progress speech"). Anything
else is a `belief.events.Event` (a BL-4 lifecycle/classification/attention
event drained from `ContactStore`'s queue) -- rendered through a per-kind
template if one exists, and auto-acknowledged (`belief.tools.
acknowledge_event`) the moment it is spoken, since body has already produced
final text for it and it must not resurface through a brain's future
`poll_events`/`list_events` call (plan Risks: "Auto-acknowledge interaction
with BL-5's `poll_events`").

**Why `UrgentCall`, not a `bypass_gate` field on `belief.events.Event`.**
The plan's §3.5/§5 sketches show `bypass_gate` as a field directly on a
generic "event" object. `belief.events.Event` (BL-4) has no such field, and
`events.py` is explicitly out of the Affected Modules list for this
milestone ("BL-5a is a consumer of the existing belief surface, not a
modifier of it") -- adding an unused field to a shared, already-large
dataclass for one caller would also mean grafting a new value onto
`EventKind`'s closed literal, since no existing kind means "urgent call."
`UrgentCall` is a small, separate type instead: `route_event` accepts
`Event | UrgentCall` and dispatches on which one it got, which is the same
"check bypass first" ordering the plan describes, without touching BL-4's
event model. No real threat-detection channel exists yet (missile launch,
tracer -- unbuilt, gated on unresolved DCS-internals questions per the
plan's Risks), so `UrgentCall` is only ever constructed by
`belief.crew_console`'s `!inject-urgent` test-harness command, never by
`ContactStore.tick`.

**Which lifecycle kinds get a template.** `CONTACT_DETECTED`/`CONTACT_LOST`/
`CONTACT_REACQUIRED` render the runtime doc's literal "C17 BMP" / "C17 lost"
/ "C17 reacquired" lines (adapted to this store's own `CONTACT_<n>` id
shape). `CONTACT_CLASSIFICATION_CHANGED` gets its own short transition
line. `CONTACT_ATTENTION_CHANGED` deliberately gets **no** template --
`route_event` returns `None` for it and does not acknowledge it -- because
every attention change the crew would care about either already got a
readback (the player's own `watch`/`ignore`/... command) or is an
area-driven change not yet in scope to narrate proactively (a real,
documented gap, not an oversight: a future milestone that wants to narrate
"entering a watched area raised attention on C22" adds a template here,
it does not need to touch this module's structure).

**No contact clustering.** `render_contact_report` reports one contact at a
time. §3.6's multi-contact `contact_group` worked example (composition
counts) needs data this codebase does not track yet
(`docs/concept/PETROBRAIN_RUNTIME.md` line 336: no clustering exists) --
out of scope per the plan's explicit scope cut, not an oversight; the
report format below has no unit-count/"group of" element for the same
reason.

**Contact report format (2026-09-10 user decision, superseding the original
"speak `describe_contact`'s `summary` verbatim" design).**
`"<COALITION> <unit type>, <clock> o'clock, <range>."` -- own format, built
from `facts["classification"]`/`facts["relative_now"]` directly rather than
reusing `belief.tools._contact_summary` (which stays certainty/recency-
phrased for the console debug tool and lifecycle-event lines; this format
is for the player-facing spoken/typed contact report only).
`_unit_type_display` reads the classification lattice's level+value
straight off `facts["classification"]` -- `"ground contact"`/`"unidentified
contact"` at the presence/unknown levels, `_OP_CLASS_DISPLAY`'s human word
for a `class`-level `OP_*` bucket, the value verbatim at `type` level (an
already-human reporting name/type string). Clock/range are omitted
entirely (not "unknown") when `relative_now` is absent -- no enrichment
supplied, same absent-not-null convention `tools.py` itself uses.

**Coalition is always `"UNKNOWN"` -- deliberately deferred, not a bug.**
No IFF/coalition perception channel exists (`perception.association`'s own
docstring: "no coalition/IFF filtering"). `LoGetWorldObjects` does carry
real DCS ground-truth coalition, but reading it directly into `Contact`
would violate the project's no-omniscience invariant (`percept.py`
structurally strips DCS truth fields on purpose) -- Petrovich would always
know true IFF for a target he's never actually identified. **User decision,
2026-09-10: when this is eventually built, coalition should be *inferred*,
not read from ground truth** -- from the unit type/vocabulary each
coalition is known to field, and from which side controls the terrain the
contact sits in (world-model territory data, not yet built either). Left
as a body-layer backlog item (`ROADMAP.md`), not built here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from belief.attention import Attention
from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext
from belief.events import (
    CONTACT_CLASSIFICATION_CHANGED,
    CONTACT_DETECTED,
    CONTACT_LOST,
    CONTACT_REACQUIRED,
    Event,
)
from belief.tools import ContactResult, acknowledge_event, describe_contact

Template = Literal["readback", "contact_report", "lifecycle_event", "threat_reaction"]
Urgency = Literal["normal", "critical"]


@dataclass(frozen=True, slots=True)
class OutgoingSpeech:
    """§5's `outgoing_speech` record, trimmed to what this milestone's
    body-written templates actually populate -- `author` is always
    `"body_template"` here (the brain-written class is §2.1's class 3, not
    built by this milestone)."""

    text: str
    template: Template
    bypass_gate: bool = False
    urgency: Urgency = "normal"
    author: Literal["body_template"] = "body_template"
    in_reply_to: str | None = None


@dataclass(frozen=True, slots=True)
class UrgentCall:
    """A manually-injected reactive urgent call -- see module docstring's
    "Why `UrgentCall`" note. `contact_id` is carried for logging/context
    only; `route_event` never looks the contact up for this path (an urgent
    call must speak even if body's own contact record is stale, gone, or
    was never associated with a specific contact at all -- "missile launch"
    is a threat-geometry event, not necessarily a per-contact one)."""

    contact_id: str
    text: str


#: Readback phrasing per attention level -- §2.1/§3.5's worked example
#: ("watch C17" -> "Watching C17.") for `"watch"`; the other three levels
#: follow the same fixed-phrasing convention.
_READBACK_TEMPLATES: dict[Attention, str] = {
    "watch": "Watching {id}.",
    "priority": "Prioritizing {id}.",
    "ignore": "Ignoring {id}.",
    "normal": "No longer watching {id}.",
}


def render_readback(attention_level: Attention, contact_id: str) -> OutgoingSpeech:
    """A command readback -- confirmation, fast and identical every time
    (§2.1), never brain-worded."""
    text = _READBACK_TEMPLATES[attention_level].format(id=contact_id)
    return OutgoingSpeech(text=text, template="readback")


#: `class`-level `OP_*` buckets -> a human word, for the contact report's
#: unit-type field. See module docstring's "Contact report format" note.
#: Every `OP_*` value `perception.object_model` actually assigns (checked
#: against its table) has an entry; an unmapped value falls back to itself
#: verbatim (`_unit_type_display`) rather than raising.
_OP_CLASS_DISPLAY: Final[dict[str, str]] = {
    "OP_ARMORED": "armor",
    "OP_TRUCK": "truck",
    "OP_INFANTRY": "infantry",
    "OP_SRSAM": "SAM",
    "OP_MRSAM": "SAM",
    "OP_SPAAG": "AAA",
    "OP_ZU23": "AAA",
    "OP_SHIP": "ship",
}

#: See module docstring's "Coalition is always UNKNOWN" note -- deliberately
#: deferred, not a bug.
_COALITION_PLACEHOLDER: Final[str] = "UNKNOWN"


def _unit_type_display(value: object, level: object) -> str:
    """The contact report's unit-type field, from `facts["classification"]`'s
    `value`/`level`. See module docstring's "Contact report format" note."""
    if level == "type" and isinstance(value, str) and value:
        return value
    if level == "class" and isinstance(value, str) and value:
        return _OP_CLASS_DISPLAY.get(value, value)
    if level == "presence":
        return "ground contact"
    return "unidentified contact"


def render_contact_report(
    store: ContactStore,
    contact_id: str,
    now_sim: float,
    enrichment: EnrichmentContext | None = None,
) -> OutgoingSpeech | None:
    """A single-contact report (see module docstring's "No contact
    clustering"/"Contact report format" notes). `None` if `contact_id` does
    not exist -- callers must not invent a contact for an unknown id, same
    convention as `belief.tools.describe_contact` itself."""
    result = describe_contact(store, contact_id, now_sim, enrichment=enrichment)
    if result is None:
        return None
    facts = result["facts"]
    classification = facts["classification"]
    assert isinstance(classification, dict)
    unit_type = _unit_type_display(
        classification.get("value"), classification.get("level")
    )
    text = f"{_COALITION_PLACEHOLDER} {unit_type}"
    relative_now = facts.get("relative_now")
    if relative_now is not None:
        assert isinstance(relative_now, dict)
        clock = relative_now["clock_position"]
        range_m = relative_now["range_m"]
        assert isinstance(range_m, float)
        text += f", {clock} o'clock, {range_m / 1000:.1f} km"
    text += "."
    return OutgoingSpeech(text=text, template="contact_report")


def _render_lifecycle_text(result: ContactResult, event: Event) -> str | None:
    """The per-kind template text for one lifecycle/classification event,
    or `None` for a kind with no template (see module docstring's "Which
    lifecycle kinds get a template")."""
    contact_id = str(result["facts"]["id"])
    if event.kind == CONTACT_DETECTED:
        classification = result["facts"]["classification"]
        assert isinstance(classification, dict)
        value = classification.get("value") or "unknown"
        return f"{contact_id} {value}."
    if event.kind == CONTACT_LOST:
        return f"{contact_id} lost."
    if event.kind == CONTACT_REACQUIRED:
        return f"{contact_id} reacquired."
    if event.kind == CONTACT_CLASSIFICATION_CHANGED:
        return f"{contact_id} identified as {event.classification}."
    return None


def route_event(
    store: ContactStore,
    event: Event | UrgentCall,
    now_sim: float,
    enrichment: EnrichmentContext | None = None,
) -> OutgoingSpeech | None:
    """The outbound routing gate (see module docstring). Returns the speech
    to say, or `None` if there is nothing to say (a lifecycle kind with no
    template, or a contact that no longer exists)."""
    if isinstance(event, UrgentCall):
        return OutgoingSpeech(
            text=event.text,
            template="threat_reaction",
            bypass_gate=True,
            urgency="critical",
        )

    result = describe_contact(store, event.contact_id, now_sim, enrichment=enrichment)
    if result is None:
        return None
    text = _render_lifecycle_text(result, event)
    if text is None:
        return None
    acknowledge_event(store, event.id)
    return OutgoingSpeech(text=text, template="lifecycle_event")
