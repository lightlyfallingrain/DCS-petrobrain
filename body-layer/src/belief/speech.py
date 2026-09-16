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

**Which lifecycle kinds get a template (2026-09-11 revision -- terser
crew-text, ids/coalition dropped, see "Contact report format" below).**
`CONTACT_DETECTED`/`CONTACT_REACQUIRED` render the full positional-callout
format (`_contact_report_text`, shared with `render_contact_report`) with
**no id spoken** -- the pilot cannot track `CONTACT_<n>` ids by ear, so
speaking one is net noise, not help (the id still exists internally and on
typed/console surfaces -- `watch <id>`, `status <id>`, the debug console --
this only changes what is *spoken*). `CONTACT_LOST` gets **no template at
all** -- `_render_lifecycle_text` returns `None` for it, the same pattern
`CONTACT_ATTENTION_CHANGED` already follows: there is no current position to
report, and a bare "lost" callout with nothing else to say is not worth
interrupting the pilot for. `CONTACT_CLASSIFICATION_CHANGED` gets its own
position-bearing line, `"unit at {clock} o'clock, {range} km is {unit
type}."` (range clause omitted when no `relative_now` is available), built
from the contact's *current* `facts["classification"]` via the same
`_unit_type_display` helper `_contact_report_text` uses -- not the raw
`event.classification` enum string. `CONTACT_ATTENTION_CHANGED` deliberately
gets **no** template -- `route_event` returns `None` for it and does not
acknowledge it -- because every attention change the crew would care about
either already got a readback (the player's own `watch`/`ignore`/... command)
or is an area-driven change not yet in scope to narrate proactively (a real,
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
"speak `describe_contact`'s `summary` verbatim" design; extended 2026-09-11
to add the semantic-enrichment fragment and share the format with two
lifecycle kinds; extended again 2026-09-11 to drop the coalition token and
ids entirely, and round range/distance for terser crew-text).**
`"<unit type>[, <clock> o'clock, <range> km][ <best semantic fact text>]."`
-- built by the shared, id-less `_contact_report_text` helper from
`facts["classification"]`/`facts["relative_now"]`/`facts["semantic"]`
directly rather than reusing `belief.tools._contact_summary` (which stays
certainty/recency-phrased for the console debug tool and the minimal
lifecycle lines). `render_contact_report` (player-initiated `describe_contact`)
and `_render_lifecycle_text`'s `CONTACT_DETECTED`/`CONTACT_REACQUIRED`
branches both call this one helper directly, with no id prepended anywhere
-- see "Which lifecycle kinds get a template" above for why ids were
dropped from spoken text entirely (2026-09-11). `_unit_type_display` reads
the classification lattice's level+value straight off `facts["classification"]`
-- `"ground"`/`"contact"` at the presence/unknown levels, `_OP_CLASS_DISPLAY`'s
human word for a `class`-level `OP_*` bucket, the value verbatim at `type`
level (an already-human reporting name/type string); all words lowercase,
consistent with `_OP_CLASS_DISPLAY`'s existing lowercase vocabulary (`"SAM"`/
`"AAA"` stay as acronyms, not a casing-style exception). Clock/range are
omitted entirely (not "unknown") when `relative_now` is absent -- no
enrichment supplied, same absent-not-null convention `tools.py` itself uses.
Range is rounded to the nearest 0.5 km with no trailing `.0` (`_format_
range_km`, e.g. `5.0 -> "5"`, `1.5 -> "1.5"`). The semantic fragment is the
highest-confidence `belief.enrichment.SemanticFact.text` among
`facts["semantic"]`, mirroring `belief.console.format_event_for_overlay`'s
own selection (`max(..., key=lambda fact: fact["confidence"])`); omitted
when `facts["semantic"]` is absent/empty; its embedded trailing distance
(e.g. `"near a road (439m)"`) is rounded to the nearest 100 m with a `~`
prefix (`_round_enrichment_fragment`, regex-based -- `SemanticFact.text`
itself, in `enrichment.py`, is untouched and shared with the unaffected
console/debug path).

**No coalition token.** The original `"UNKNOWN"` placeholder prefix (deferred
IFF/coalition inference -- no perception channel exists, and reading
`LoGetWorldObjects`'s real coalition into `Contact` would break the
no-omniscience invariant `percept.py` enforces) was removed entirely
(2026-09-11) rather than kept as a visible placeholder -- a pilot hearing
"UNKNOWN truck" on every single callout is net noise, not information, when
no callout can ever say anything else yet. When coalition inference is
eventually built (`ROADMAP.md` backlog item, unchanged), that work
reintroduces a coalition token at that point, conditioned on actually having
one to say -- inferred from unit-type vocabulary and which side's terrain the
contact sits in, not ground truth."""

from __future__ import annotations

import re
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


def render_scan_readback(sector_label: str) -> OutgoingSpeech:
    """The F10 "Scan" family's readback (`plans/f10-command-vocabulary/
    plan.md` Stage 6) -- fixed phrasing, mirroring `render_readback`'s "fast
    and identical every time" posture rather than `render_watch_nearest_
    readback`'s contact-derived one, since a scan has no contact to
    describe yet. `sector_label` is a plain human phrase for the sector
    scanned (`"ahead"`, `"to the left"`, `"north"`, ...) -- `crew_console.py`
    owns the token -> label mapping, this function only formats it."""
    return OutgoingSpeech(text=f"Scanning {sector_label}.", template="readback")


def render_watch_nearest_readback(facts: dict[str, object]) -> OutgoingSpeech:
    """The F10 "Watch Nearest" readback (`plans/f10-crew-commands/plan.md`).
    Unlike a typed `watch <id>`, the player named no contact, so the readback
    identifies it the way a contact report does -- `"Watching <unit
    type>[, <clock> o'clock, <range> km][ <semantic fact>]."` via the shared
    `_contact_report_text`, no id spoken (see module docstring's "Contact
    report format" note). `facts` is `belief.tools.describe_contact`'s."""
    return OutgoingSpeech(
        text=f"Watching {_contact_report_text(facts)}", template="readback"
    )


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
    "OP_GROUPSOMETHING": "group",
}

#: Matches a `belief.enrichment.SemanticFact.text` fragment's trailing
#: distance parenthetical (e.g. the `"(439m)"` in `"near a road (439m)"`).
#: See `_round_enrichment_fragment`.
_ENRICHMENT_DISTANCE_RE: Final = re.compile(r"\((\d+)m\)$")


def _unit_type_display(value: object, level: object) -> str:
    """The contact report's unit-type field, from `facts["classification"]`'s
    `value`/`level`. See module docstring's "Contact report format" note.
    Lowercase throughout, consistent with `_OP_CLASS_DISPLAY`'s own
    vocabulary (acronyms like `"SAM"`/`"AAA"` excepted)."""
    if level == "type" and isinstance(value, str) and value:
        return value
    if level == "class" and isinstance(value, str) and value:
        return _OP_CLASS_DISPLAY.get(value, value)
    if level == "presence":
        return "ground"
    return "contact"


def _format_range_km(range_m: float) -> str:
    """Round a range in metres to the nearest 0.5 km, formatted without a
    trailing `.0` (`5000.0 -> "5"`, `1500.0 -> "1.5"`). See module
    docstring's "Contact report format" note."""
    range_km = round(range_m / 500.0) * 0.5
    if range_km == int(range_km):
        return str(int(range_km))
    return f"{range_km:g}"


def _round_enrichment_fragment(text: str) -> str:
    """Round a `SemanticFact.text` fragment's trailing `"(NNNm)"` distance to
    the nearest 100 m, prefixed with `~` (`"near a road (439m)"` ->
    `"near a road (~400m)"`). Text with no trailing distance parenthetical
    (e.g. `"inside Anapa"`) passes through unchanged. `SemanticFact.text`
    itself (`enrichment.py`) is not touched -- this is a display-only
    post-process scoped to this module, see module docstring's "No coalition
    token"/"Contact report format" notes."""
    match = _ENRICHMENT_DISTANCE_RE.search(text)
    if match is None:
        return text
    rounded = round(int(match.group(1)) / 100.0) * 100
    return f"{text[: match.start()]}(~{rounded}m)"


def _contact_report_text(facts: dict[str, object]) -> str:
    """The id-less, coalition-less positional-callout text shared by
    `render_contact_report` and `_render_lifecycle_text`'s `CONTACT_DETECTED`/
    `CONTACT_REACQUIRED` branches (see module docstring's "Contact report
    format" note). Format: `"<unit type>[, <clock> o'clock, <range> km][
    <best semantic fact text>]."` -- clock/range omitted when `relative_now`
    is absent, the semantic fragment omitted when `facts["semantic"]` is
    absent/empty, both the module's existing absent-not-null convention. The
    semantic fragment picks the highest-confidence `belief.enrichment.
    SemanticFact`, mirroring `belief.console.format_event_for_overlay`'s own
    selection (`max(semantic, key=lambda fact: fact["confidence"])`)."""
    classification = facts["classification"]
    assert isinstance(classification, dict)
    text = _unit_type_display(classification.get("value"), classification.get("level"))
    relative_now = facts.get("relative_now")
    if relative_now is not None:
        assert isinstance(relative_now, dict)
        clock = relative_now["clock_position"]
        range_m = relative_now["range_m"]
        assert isinstance(range_m, float)
        text += f", {clock} o'clock, {_format_range_km(range_m)} km"
    semantic = facts.get("semantic")
    if isinstance(semantic, list) and semantic:
        best = max(semantic, key=lambda fact: fact["confidence"])
        text += f" {_round_enrichment_fragment(best['text'])}"
    text += "."
    return text


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
    text = _contact_report_text(result["facts"])
    return OutgoingSpeech(text=text, template="contact_report")


def _render_lifecycle_text(result: ContactResult, event: Event) -> str | None:
    """The per-kind template text for one lifecycle/classification event,
    or `None` for a kind with no template (see module docstring's "Which
    lifecycle kinds get a template"). `CONTACT_DETECTED`/`CONTACT_REACQUIRED`
    speak the shared `_contact_report_text` positional-callout format
    directly, with no id spoken (2026-09-11 -- a pilot cannot track
    `CONTACT_<n>` ids by ear). `CONTACT_LOST` has no template at all -- there
    is no current position to report. `CONTACT_CLASSIFICATION_CHANGED` speaks
    a position-bearing identification line built from the contact's
    *current* `facts["classification"]` via `_unit_type_display` (not the
    raw `event.classification` enum string)."""
    if event.kind == CONTACT_DETECTED or event.kind == CONTACT_REACQUIRED:
        return _contact_report_text(result["facts"])
    if event.kind == CONTACT_LOST:
        return None
    if event.kind == CONTACT_CLASSIFICATION_CHANGED:
        classification = result["facts"]["classification"]
        assert isinstance(classification, dict)
        unit_type = _unit_type_display(
            classification.get("value"), classification.get("level")
        )
        relative_now = result["facts"].get("relative_now")
        if relative_now is not None:
            assert isinstance(relative_now, dict)
            clock = relative_now["clock_position"]
            range_m = relative_now["range_m"]
            assert isinstance(range_m, float)
            return f"unit at {clock} o'clock, {_format_range_km(range_m)} km is {unit_type}."
        return f"unit is {unit_type}."
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
