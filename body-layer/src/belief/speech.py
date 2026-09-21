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

**No contact clustering in `render_contact_report` itself.** It reports one
contact at a time, and always will -- §3.6's multi-contact `contact_group`
worked example is answered a different way: `belief.callouts.
render_group_report` (`plans/callout-scheduling/plan.md`) builds a group
line from several contacts' `facts`, at *speech time*, without this module
gaining any notion of a persisted group. See that function's own docstring
and `belief.callouts`' module docstring for the full "report space, not
world space" argument -- grouping is a view over several `describe_contact`
results, not a new belief-state entity, and not a reuse of `perception.
clustering`'s optical-resolvability question.

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
contact sits in, not ground truth.

**Stage 4b -- the count clause (`plans/group-contact-model/plan.md`,
"Stage 4b design -- speech and events").** A contact whose `Contact.
cardinality` holds a plural interval speaks a hedged quantity word ahead of
the unit type -- `"several contacts, ..."`, `"a handful of trucks, ..."`.
**Grammar is polished only where it is obviously wrong, not where it is merely
imperfect** (user, 2026-09-19: *"Petrovich is Russian, we don't expect perfect
grammar. Value/effort is low on fine tuning grammar beyond obvious mistakes."*).
Slightly-off English is **in character** for a Soviet-trained weapons operator
speaking a second language, so `"a couple of armor"` (a mass noun taking a
count phrase) and `"three T-72"` (an unpluralised type designation) are left
as they are, deliberately. The line worth fixing is the one a listener hears as
a *defect* rather than an accent -- `"a handful trucks"` was missing a word,
which is a different thing from being stilted. Do not add pluralisation rules,
article handling, or agreement logic here without a reason beyond tidiness;
that cost buys nothing this character needs.

**The phrase carries its own connector**: `"several"`/`"many"` take a bare
noun, while `"a handful"` requires `"of"` to be grammatical, so
`_cardinality_phrase` returns `"a handful of"` and composition stays a plain
phrase-plus-noun join. An earlier revision generalised from the user's own
worked example, `"several contacts, eleven o'clock, two kilometres"`,
verbatim) -- never an exact number (`_cardinality_phrase`); a singular contact (or one with no cardinality fact
at all) is unaffected, byte-for-byte, by construction (`_contact_report_
text`'s guard). This vocabulary is deliberately never precise: settled
decision 2 ("precision only when available and useful") wants a caller
holding an actual question, and none exists yet -- see `_cardinality_phrase`'s
docstring. `render_contact_report`, `_render_lifecycle_text`'s
`CONTACT_DETECTED`/`CONTACT_REACQUIRED` branches, and `render_watch_nearest_
readback` all gain the clause for free, since all three call `_contact_
report_text` directly. `CONTACT_CLASSIFICATION_CHANGED` does **not** gain
it -- it builds its own line directly from `_unit_type_display`, not through
`_contact_report_text`, by construction rather than an added exclusion (a
classification-change callout volunteering count chatter on an event about
something else entirely would be exactly the unrequested cardinality
narration settled decision 4 warns against).

**Contact report fine tuning -- the cheap `speech.py` items (`ROADMAP.md`,
opened 2026-09-18, this pass 2026-09-19).** Units are spelled out for TTS
(`_format_range_km` now returns `"5 kilometres"`, not `"5 km"`; the
enrichment-distance parenthetical `_round_enrichment_fragment` rounds now
reads `"(~400 metres)"`, not `"(~400m)"` -- shorthand is not read correctly).
British "kilometres"/"metres" was kept rather than switched to American
spelling, matching this file's own pre-existing usage (this docstring's
"eleven o'clock, two kilometres" worked example, `tools.py`'s own
`"1 decimal place of kilometres"` docstring) -- either spelling is equally
sayable, so there was nothing to gain from churning it. Below
`_VERY_CLOSE_RANGE_M` (500 m), `_format_range_km` says `"very close"`
instead of a figure -- the roadmap's own reasoning: at that range the exact
number stops mattering and the fact of proximity starts to. Acronym/
designation respelling for TTS (`_TTS_TOKEN_RESPELL`/`_respell_for_tts`) is
a small, explicit per-token table applied only at `_unit_type_display`'s/
`_plural_unit_type_display`'s `type` level, deliberately **not** a blanket
rule -- a blanket rule would also respell `"SAM"`, which TTS already reads
correctly on its own (the roadmap's named exception, and `_OP_CLASS_
DISPLAY`'s existing acronym, untouched by this table since it lives at
`class` level, not `type`). Checked against the real sayable vocabulary
rather than guessed: the roadmap's own worked example, `"LR"`, does not
occur anywhere in `_OP_CLASS_DISPLAY`/`_OP_CLASS_DISPLAY_PLURAL` or in
`perception.reporting_names`'s 377-entry reporting-name catalogue (the full
vocabulary a `type`-level classification value can hold), so it was left
out rather than added on faith; the table's one populated entry, the
`Mi-8`/`Mi-24`/`Mi-26`/`Mi-28` family, is the actual reporting-name shape
that produced the live "read as one blended token" finding. See
`enrichment.py`'s own docstring for the matching `belief/enrichment.py`
items -- the `NEAR_FACT_RADIUS_M`-gated "on {label}"/"next to {label}"
short-range wording, which `_round_enrichment_fragment` above now also has
to pass through unchanged (no distance figure at all, by construction, so
its regex simply does not match)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Final, Literal

from belief.attention import Attention
from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext
from belief.events import (
    CONTACT_CARDINALITY_CHANGED,
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


def render_cancel_readback(what_was_cancelled: str | None) -> OutgoingSpeech:
    """The F10 "Cancel Task" readback. `what_was_cancelled` is a plain human
    phrase for the cancelled task (`"the scan to the left"`, `"the scan
    north"`), or `None` when the task's shape yields no better description
    than "whatever you last asked for".

    **Speaks no task id** (live-test finding 2026-09-16: the player heard
    `"cancelled task TASK_4"`). That is the same rule this module already
    applies to contacts -- see `_contact_report_text`'s "no id spoken
    anywhere", added when `watch_nearest` was found speaking `"Watching
    CONTACT_1"`. A pilot cannot track `TASK_<n>` any better than
    `CONTACT_<n>` by ear, and the id exists for the console and the task
    store, not for the crew. `crew_console.py` owns the task -> phrase
    mapping, this function only formats it."""
    if what_was_cancelled is None:
        return OutgoingSpeech(text="Copy, stopping.", template="readback")
    return OutgoingSpeech(
        text=f"Copy, stopping {what_was_cancelled}.", template="readback"
    )


def render_say_again() -> OutgoingSpeech:
    """`plans/inbound-speech/plan.md` Stage 2 -- spoken when a voice
    transcript falls below `belief.voice_commands.CONFIRM_FLOOR`, or was a
    verb-anchored command attempt that resolved to nothing (an unmatched
    phrase, or an illegal bearing `audio_adapter.command_matcher` detected).
    Fixed phrasing, no caller-supplied description -- there is nothing
    coherent to describe yet at this confidence. **Not the same signal as
    silence**: a clip the adapter's own signal-level gate rejected never
    reaches this far and produces no speech at all (module docstring
    behaviour #1) -- this is only for speech that was heard and not
    understood."""
    return OutgoingSpeech(text="Say again?", template="readback")


# No `render_stop_acknowledged` here (removed, `plans/inbound-speech/
# plan.md` Stage 3 follow-up, user direction 2026-09-20). `stop_talking`
# used to speak "Copy." right after interrupting playback -- that was
# itself the bug: the acknowledgement had to go out over the same channel
# it was interrupting, so asking Petrovich to stop talking made him talk
# once more. `stop_talking` is now the one dispatched token with **no
# readback at all** (`crew_console.CrewConsole._handle_stop_talking`'s own
# docstring is the fuller account) -- every render_* function in this
# module remains "templated, body-written" speech for a token that *does*
# speak; this is the deliberate, stated exception, not an omission.


def render_confirm_request(description: str) -> OutgoingSpeech:
    """`plans/inbound-speech/plan.md` Stage 2's confirm-band interrogative
    readback (Decision 4 Layer 3): `render_confirm_request("scan left")`
    -> `"Scan left, confirm?"`. `description` is a plain human phrase for
    the best-matching candidate command -- `belief.voice_commands`/
    `belief.crew_console` own picking it (from the matched token, or from
    the best of two ambiguous candidates), this function only formats it,
    mirroring `render_scan_readback`'s division of labour."""
    capitalized = description[:1].upper() + description[1:] if description else ""
    return OutgoingSpeech(text=f"{capitalized}, confirm?", template="readback")


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
}

#: `_OP_CLASS_DISPLAY`'s plural sibling, for `_plural_unit_type_display`. See
#: module docstring's "Stage 4b -- the count clause" note. No
#: `"OP_GROUPSOMETHING"` entry, for the identical reason `_OP_CLASS_DISPLAY`
#: has none (Sec 4 of the Stage 4b design): a class-level classification can
#: never hold that value.
_OP_CLASS_DISPLAY_PLURAL: Final[dict[str, str]] = {
    "OP_ARMORED": "armor",  # already a mass noun -- singular form doubles as plural
    "OP_TRUCK": "trucks",
    "OP_INFANTRY": "infantry",  # mass noun
    "OP_SRSAM": "SAMs",
    "OP_MRSAM": "SAMs",
    "OP_SPAAG": "AAA",  # mass/acronym -- unchanged
    "OP_ZU23": "AAA",
    "OP_SHIP": "ships",
}

#: Matches a `belief.enrichment.SemanticFact.text` fragment's trailing
#: distance parenthetical (e.g. the `"(439m)"` in `"near a road (439m)"`).
#: See `_round_enrichment_fragment`.
_ENRICHMENT_DISTANCE_RE: Final = re.compile(r"\((\d+)m\)$")

#: Per-token TTS respelling (2026-09-19 roadmap item, "Contact report fine
#: tuning" -- cheap items). A table, not a blanket rule, because a blanket
#: acronym-spacing rule would also mangle `"SAM"`, which TTS already reads
#: correctly on its own (`_OP_CLASS_DISPLAY`'s exception, unaffected by this
#: table). Checked against the actual sayable vocabulary rather than
#: guessed: the roadmap's own worked example, `"LR"`, does not occur
#: anywhere in `_OP_CLASS_DISPLAY`/`_OP_CLASS_DISPLAY_PLURAL` or in
#: `perception.reporting_names`'s 377-entry reporting-name catalogue (the
#: full vocabulary a `type`-level classification value can hold), so it is
#: not in this table -- see this module's `implementation.md` note. The
#: `Mi-XX` family (`Mi-8`/`Mi-24`/`Mi-26`/`Mi-28`, the only rotorcraft
#: reporting names sharing that "letter(s)-dash-digits" shape) is: only
#: `"Mi-8"` was actually heard misread live, but all four are the identical
#: shape for the identical reason (a two-character prefix plus digits reads
#: as one blended token, not as characters), so all four get the same fix
#: rather than leaving three of them inconsistently unfixed.
_TTS_TOKEN_RESPELL: Final[dict[str, str]] = {
    "mi-8": "M I 8",
    "mi-24": "M I 24",
    "mi-26": "M I 26",
    "mi-28": "M I 28",
}


def _respell_for_tts(text: str) -> str:
    """Apply `_TTS_TOKEN_RESPELL` word-by-word (space-separated tokens,
    case-insensitive match), leaving any token not in the table alone --
    the safe default a per-token table exists to preserve (see the table's
    own docstring on why this is not a blanket acronym rule)."""
    return " ".join(
        _TTS_TOKEN_RESPELL.get(token.lower(), token) for token in text.split(" ")
    )


def _unit_type_display(value: object, level: object) -> str:
    """The contact report's unit-type field, from `facts["classification"]`'s
    `value`/`level`. See module docstring's "Contact report format" note.
    Lowercase throughout, consistent with `_OP_CLASS_DISPLAY`'s own
    vocabulary (acronyms like `"SAM"`/`"AAA"` excepted)."""
    if level == "type" and isinstance(value, str) and value:
        return _respell_for_tts(value)
    if level == "class" and isinstance(value, str) and value:
        return _OP_CLASS_DISPLAY.get(value, value)
    if level == "presence":
        return "ground"
    return "contact"


def _plural_unit_type_display(value: object, level: object) -> str:
    """`_unit_type_display`'s plural sibling, used only when
    `_cardinality_phrase` returns a phrase (see `_contact_report_text`'s
    guard). Deliberately never pluralizes a `type`-level value (a raw DCS
    type string, e.g. `"T-72"`) -- see the Stage 4b design's "sayable at
    every specificity level" note; settled decision 5 keeps wording fixes
    like inventing a pluralization rule for arbitrary type strings out of
    this stage. The presence/fallback branch returns `"contacts"`, not
    `_unit_type_display`'s `"ground"`/`"contact"` split -- a bare "ground"
    doesn't pluralize sensibly, and "several contacts" is what actually
    reads right."""
    if level == "type" and isinstance(value, str) and value:
        return _respell_for_tts(value)
    if level == "class" and isinstance(value, str) and value:
        return _OP_CLASS_DISPLAY_PLURAL.get(value, value)
    return "contacts"


#: Spoken numbers for an exactly-known count, used only where precision has
#: been earned (see `_cardinality_phrase`'s `attended` parameter). Digits are
#: spelled because TTS reads numerals inconsistently; beyond twelve the hedge
#: is used instead, since a crew member who says "seventeen" about vehicles he
#: is looking at is claiming a count no one makes by eye.
_SPOKEN_NUMBERS: Final[dict[int, str]] = {
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
}


def _cardinality_phrase(lo: int, hi: float, attended: bool = False) -> str | None:
    """The count clause's vocabulary (`plans/group-contact-model/plan.md`'s
    Stage 4b design, Sec 1) -- reads `lo`/`hi` magnitude directly rather than
    matching a `belief.cardinality.CountBucket` name, since a folded interval
    (an intersection or a contradiction hull) need not equal any one named
    bucket.

    `None` means "no clause at all" (an exactly-one interval). Otherwise the
    register is deliberately **hedged**: `"a couple of"` for two or three,
    `"a handful of"` for four or five, `"many"` from sixteen up, and the safe
    default `"several"` for everything else plural -- never wrong to say about
    any plural count. Each phrase carries its own connector, because the
    grammar is per-phrase: `"several trucks"` is correct with a bare noun and
    `"a handful trucks"` is not.

    **`attended` is where precision is earned** (user, 2026-09-19: "a group of
    watched/tracked contacts is, for whatever reason, more important and should
    get more detailed reports, including unit counts"). The user's standing
    rule is that an exact count is spoken only when it is both *available* and
    *useful* -- and attention is precisely the usefulness signal, since the
    crew deliberately marked this contact. So a watched or priority contact
    whose interval is exactly known (`lo == hi`) speaks the number; everything
    else keeps the hedge. This is the caller-holding-a-question that the
    Stage 4b design noted did not yet exist -- it did, under a different name.

    Note the honesty condition is unchanged either way: an exact number is
    only ever spoken when the belief itself is exact, so attention buys
    *disclosure* of precision already held, never manufactured precision."""
    if lo == 1 and hi == 1:
        return None
    if attended and lo == hi and lo in _SPOKEN_NUMBERS:
        return _SPOKEN_NUMBERS[lo]
    if lo >= 16:
        return "many"
    if lo == 4 and hi <= 5:
        return "a handful of"
    if lo >= 2 and hi <= 3:
        return "a couple of"
    return "several"


#: Below this slant range, the exact figure stops mattering and the fact of
#: proximity starts to (2026-09-19 roadmap item) -- `_format_range_km`
#: speaks `"very close"` instead of a rounded distance. Threshold, not a
#: rounding artefact: it is checked against the raw `range_m`, before the
#: nearest-0.5-km rounding below ever runs.
_VERY_CLOSE_RANGE_M: Final[float] = 500.0


def _format_range_km(range_m: float) -> str:
    """Round a range in metres to the nearest 0.5 km, spelled out for TTS
    (`5000.0 -> "5 kilometres"`, `1500.0 -> "1.5 kilometres"`) -- shorthand
    like `"km"` is not spoken correctly. Below `_VERY_CLOSE_RANGE_M`, returns
    `"very close"` instead of a figure (see that constant's docstring). See
    module docstring's "Contact report format" note.

    Spelled `"kilometres"` (not `"kilometers"`), matching this file's own
    existing British spelling elsewhere (the module docstring's own worked
    example, `"two kilometres"`) rather than picking a spelling fresh --
    either reads fine for TTS, so there is nothing to gain from churning it."""
    if range_m < _VERY_CLOSE_RANGE_M:
        return "very close"
    range_km = round(range_m / 500.0) * 0.5
    if range_km == int(range_km):
        range_str = str(int(range_km))
    else:
        range_str = f"{range_km:g}"
    return f"{range_str} kilometres"


def _round_enrichment_fragment(text: str) -> str:
    """Round a `SemanticFact.text` fragment's trailing `"(NNNm)"` distance to
    the nearest 100 m, prefixed with `~` and spelled out for TTS
    (`"near a road (439m)"` -> `"near a road (~400 metres)"`). Text with no
    trailing distance parenthetical (e.g. `"inside Anapa"`, or `enrichment.
    py`'s new `"on {label}"`/`"next to {label}"` proximity phrasing, which
    carries no distance figure at all) passes through unchanged.
    `SemanticFact.text` itself (`enrichment.py`) is not touched -- this is a
    display-only post-process scoped to this module, see module docstring's
    "No coalition token"/"Contact report format" notes."""
    match = _ENRICHMENT_DISTANCE_RE.search(text)
    if match is None:
        return text
    rounded = round(int(match.group(1)) / 100.0) * 100
    return f"{text[: match.start()]}(~{rounded} metres)"


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
    selection (`max(semantic, key=lambda fact: fact["confidence"])`).

    **Count clause (`plans/group-contact-model/plan.md` Stage 4b).** A
    plural cardinality prepends a hedged quantity word (`"several"`/
    `"a handful"`/`"many"`, never an exact number -- `_cardinality_phrase`)
    and switches the unit-type word to its plural form
    (`_plural_unit_type_display`). This is a branch, not a literal early
    `return`, because the trailing clock/range/semantic logic below is
    shared by both branches and must not be duplicated. **Regression guard:
    on the singular path (`facts["cardinality"]` absent, or present with an
    exactly-one interval) this calls the exact same `_unit_type_display`
    with the exact same arguments and executes no new code** -- every
    existing test in this module is that guard."""
    classification = facts["classification"]
    assert isinstance(classification, dict)
    cardinality = facts.get("cardinality")
    phrase = None
    if isinstance(cardinality, dict):
        # `watch`/`priority` mean the crew deliberately picked this contact,
        # which is the "useful" half of the user's precision rule -- see
        # `_cardinality_phrase`'s `attended` parameter.
        attended = facts.get("attention") in ("watch", "priority")
        phrase = _cardinality_phrase(
            cardinality["lo"], cardinality["hi"], attended=attended
        )
    if phrase is None:
        text = _unit_type_display(
            classification.get("value"), classification.get("level")
        )
    else:
        text = (
            f"{phrase} "
            f"{_plural_unit_type_display(classification.get('value'), classification.get('level'))}"
        )
    relative_now = facts.get("relative_now")
    if relative_now is not None:
        assert isinstance(relative_now, dict)
        clock = relative_now["clock_position"]
        range_m = relative_now["range_m"]
        assert isinstance(range_m, float)
        text += f", {clock} o'clock, {_format_range_km(range_m)}"
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


def render_group_report(facts_list: list[dict[str, object]]) -> OutgoingSpeech:
    """A speech-time-only group report (`plans/callout-scheduling/plan.md`,
    "Aggregation" section) -- `belief.callouts.group_candidates` has already
    decided `facts_list` all share the same `_unit_type_display`/
    `_format_range_km` words, so this function does no grouping decision of
    its own; it only composes one line from several `describe_contact`
    results, reusing exactly the vocabulary a single-contact report already
    uses rather than adding a second phrasing path:

    - the group interval is `lo = sum(member.lo)`, `hi = sum(member.hi)` --
      the same lower-bound idea as `belief.tools._estimated_units_lower_
      bound`, applied per group instead of over the whole store. A member
      with no `facts["cardinality"]` at all (the exactly-one default every
      contact is seeded with) contributes `(1, 1)`.
    - fed into the existing `_cardinality_phrase`/`_plural_unit_type_
      display`, so the register stays hedged ("several infantry", "a
      couple of trucks"). An exact count is spoken only when *every*
      member's own interval is exact (`lo == hi`) **and** every member is
      individually attended (`watch`/`priority`) -- tightened from
      `_cardinality_phrase`'s own single-contact `attended` rule, so a
      group never manufactures precision by averaging a mix of watched and
      unwatched members.
    - clock/range are taken from the group's **nearest** member (by
      `relative_now.range_m`) -- a crew reports the near edge of a cluster,
      not its centroid. Every member of a group is guaranteed to carry
      `relative_now` (`group_candidates` only ever buckets members that
      have one).
    - the semantic-enrichment fragment is dropped entirely for a group --
      one enrichment fact true of one member (e.g. "near a road") is not
      necessarily true of the whole group, unlike `_contact_report_text`'s
      single-contact case."""
    classification = facts_list[0]["classification"]
    assert isinstance(classification, dict)
    value = classification.get("value")
    level = classification.get("level")

    lo_total = 0
    hi_total = 0.0
    all_exact = True
    all_attended = True
    for facts in facts_list:
        cardinality = facts.get("cardinality")
        if isinstance(cardinality, dict):
            lo = cardinality["lo"]
            hi = cardinality["hi"]
        else:
            lo = hi = 1
        lo_total += lo
        hi_total += hi
        if lo != hi:
            all_exact = False
        if facts.get("attention") not in ("watch", "priority"):
            all_attended = False

    phrase = _cardinality_phrase(
        lo_total, hi_total, attended=all_attended and all_exact
    )
    if phrase is None:
        text = _unit_type_display(value, level)
    else:
        text = f"{phrase} {_plural_unit_type_display(value, level)}"

    nearest_relative_now: dict[str, object] | None = None
    nearest_range_m = math.inf
    for facts in facts_list:
        relative_now = facts.get("relative_now")
        if not isinstance(relative_now, dict):
            continue
        range_m = relative_now["range_m"]
        assert isinstance(range_m, float)
        if range_m < nearest_range_m:
            nearest_range_m = range_m
            nearest_relative_now = relative_now
    if nearest_relative_now is not None:
        clock = nearest_relative_now["clock_position"]
        text += f", {clock} o'clock, {_format_range_km(nearest_range_m)}"

    text += "."
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
    raw `event.classification` enum string). `CONTACT_CARDINALITY_CHANGED`
    (`plans/group-contact-model/plan.md` Stage 4b) gets no template either,
    joining this pattern -- settled decision 4: a bare cardinality move is
    not worth interrupting for at this hedged register. The event is real,
    logged, and visible to `poll_events`/the debug console; it simply never
    renders to speech."""
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
            return (
                f"unit at {clock} o'clock, {_format_range_km(range_m)} is {unit_type}."
            )
        return f"unit is {unit_type}."
    if event.kind == CONTACT_CARDINALITY_CHANGED:
        return None
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
