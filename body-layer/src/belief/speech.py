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
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from belief.attention import Attention
from belief.contacts import Contact, ContactStore
from belief.enrichment import EnrichmentContext
from belief.events import (
    CONTACT_CARDINALITY_CHANGED,
    CONTACT_CLASSIFICATION_CHANGED,
    CONTACT_DETECTED,
    CONTACT_ENGAGEMENT_CHANGED,
    CONTACT_LOST,
    CONTACT_MOTION_CHANGED,
    CONTACT_RANGE_CROSSED,
    CONTACT_REACQUIRED,
    Event,
)
from belief.groups import AIR_DEFENSE_OP_CLASSES, Group
from belief.threat import envelope_for
from belief.tools import ContactResult, acknowledge_event, describe_contact
from belief.utterance import ReferenceCandidate

Template = Literal["readback", "contact_report", "lifecycle_event", "threat_reaction"]
Urgency = Literal["normal", "critical"]


@dataclass(frozen=True, slots=True)
class OutgoingSpeech:
    """§5's `outgoing_speech` record, trimmed to what this milestone's
    body-written templates actually populate -- `author` is always
    `"body_template"` here (the brain-written class is §2.1's class 3, not
    built by this milestone).

    `content_signature` (`plans/group-undermerging/debug.md`, the
    2026-10-01 sortie's second finding) is the substance of `text` with
    any purely positional clause (clock/range) stripped out -- `None` for
    every template that does not need the distinction (every caller then
    falls back to comparing `text` itself, unchanged behaviour). Only
    `render_group_disclosure` sets it: a group's own re-disclosure trigger
    must fire on a *content* change (a new member, a firmed-up
    classification, a changed threat lead), never on range/clock alone --
    the user's own words, flying away from an already-fully-reported
    group while it re-spoke its entire composition every ~500 m of
    opening range: *"that's still constant reports that add no value...
    repeating the whole group composition every time adds noise."*
    Comparing `text` itself (as the pre-fix code did) makes that
    impossible, since clock/range is baked into `text` and changes on
    almost every tick a group is being closed on or opened from."""

    text: str
    template: Template
    bypass_gate: bool = False
    urgency: Urgency = "normal"
    author: Literal["body_template"] = "body_template"
    in_reply_to: str | None = None
    content_signature: str | None = None


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


#: Radio brevity: English articles carry no information in a report and cost
#: speaking time (user, 2026-09-23, from the five-fix sortie transcript).
#: `"scanning to the left"` becomes `"scanning left"`, `"a couple of
#: contacts"` becomes `"couple contacts"`. This is a register, not a style
#: preference -- it is how crews actually talk on an intercom, and every
#: word costs a slice of a channel one person can occupy at a time.


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
    return OutgoingSpeech(text=f"Copy, stop {what_was_cancelled}.", template="readback")


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


#: D11's closed set, spoken plainly -- `speech.py` owns the wording (D5:
#: "the model classifies against a closed set; it never writes what
#: Petrovich says"), the decider only ever names the reason token.
_UNABLE_TEMPLATES: dict[str, str] = {
    "NO_SUCH_COMMAND": "Unable, no such command.",
    "NO_MATCH": "Unable, I don't see it.",
    "NO_LINE_OF_SIGHT": "Unable, no line of sight.",
}


def render_unable(reason: str) -> OutgoingSpeech:
    """`plans/brain-layer/plan.md` D11's "unable, `<reason>`" -- one of the
    three closed tokens the code (or, where genuine judgement remains, the
    decider) named. An unrecognised `reason` (defensive -- `StubDecider`
    never emits one) still speaks a plain "unable" rather than raising,
    the same degrade-rather-than-crash posture `belief.crew_console`'s
    other optional-input paths already take."""
    return OutgoingSpeech(
        text=_UNABLE_TEMPLATES.get(reason, "Unable."), template="readback"
    )


def render_lost_contact() -> OutgoingSpeech:
    """`plans/brain-layer/plan.md` D4's "lost him" -- spoken when a brain
    reply names (or, for `ASK`, narrows to zero) a contact that is no
    longer in the store by the time the reply is drained. Not silence:
    the pilot asked for something and deserves to know why nothing
    happened (D4's own wording)."""
    return OutgoingSpeech(text="Lost him.", template="readback")


def render_stand_by() -> OutgoingSpeech:
    """`plans/brain-layer/plan.md` D8 -- spoken once, deterministically by
    body (no model involvement), when a brain reply has not landed within
    `belief.crew_console.STAND_BY_AFTER_S` of the escalation that is
    still outstanding."""
    return OutgoingSpeech(text="Stand by.", template="readback")


def render_disambiguation(candidates: Sequence[ReferenceCandidate]) -> OutgoingSpeech:
    """`plans/brain-layer/plan.md` D9's A/B question -- "which one --
    the one by the village, or the one on the road?" -- built entirely
    from `candidates`' own `why` strings (`belief.tools.find_contact`'s
    summaries), never from a model-written sentence (D5). No id is spoken
    (this module's existing "no id spoken anywhere" convention, see
    `_contact_report_text`'s docstring).

    Caps at the first three candidates for the spoken phrase -- more than
    that is unreadable as a spoken list and D9's mechanism only exists to
    narrow, not enumerate, every survivor; the full candidate list is
    still what `belief.crew_console` revalidates the pilot's answer
    against, this function only decides what gets *said*."""
    phrases = [candidate.why for candidate in candidates[:3]]
    if not phrases:
        return OutgoingSpeech(text="Which one?", template="readback")
    if len(phrases) == 1:
        joined = phrases[0]
    else:
        joined = ", or ".join(phrases)
    return OutgoingSpeech(text=f"Which one -- {joined}?", template="readback")


def render_clear(direction_label: str | None) -> OutgoingSpeech:
    """The `report_*` family's empty answer (`plans/
    voice-command-completeness/plan.md` Decision 2, user 2026-09-23):
    `"Clear."` for `report_all`, `"<direction>, clear."` for a directional
    family with nothing in it (`"Three o'clock, clear."`, `"North,
    clear."`). `direction_label` is a plain, lowercase human phrase for the
    direction asked about (`"three o'clock"`, `"north"`) -- `None` for
    `report_all`, which names no direction at all. `crew_console.py` owns
    picking the label (the token -> label mapping is command-vocabulary
    territory, this function only formats and capitalizes it), mirroring
    `render_confirm_request`'s own division of labour.

    **Not used when the direction cannot be seen at all** -- see
    `render_no_view` for the rear-hemisphere carve-out this function must
    never paper over."""
    if direction_label is None:
        return OutgoingSpeech(text="Clear.", template="contact_report")
    capitalized = direction_label[:1].upper() + direction_label[1:]
    return OutgoingSpeech(text=f"{capitalized}, clear.", template="contact_report")


def render_no_view(direction_label: str) -> OutgoingSpeech:
    """The rear-hemisphere carve-out `render_clear` must never speak
    (`plans/voice-command-completeness/plan.md` Decision 2): a direction
    Petrovich cannot see at all is not "clear" -- answering "clear" would
    claim a look the cockpit mask (`perception.cockpit_mask`'s
    `rear_cutoff_deg`) makes physically impossible, the no-omniscience
    invariant inverted (asserting absence from nothing, rather than
    inventing presence from nothing). `direction_label` is lowercase and
    spoken mid-sentence, unlike `render_clear`'s sentence-initial
    capitalized one -- `"Can't see north."`, not `"Can't see North."`;
    `crew_console.py` owns picking the label, same division of labour as
    `render_clear`."""
    return OutgoingSpeech(
        text=f"Can't see {direction_label}.", template="contact_report"
    )


def render_report(group_texts: list[str], truncated: bool) -> OutgoingSpeech:
    """Joins a report's per-group texts (`crew_console.CrewConsole.
    _handle_report`'s own `_contact_report_text`/`render_group_report`
    calls, one full sentence each, already ending in a period) into the
    **one** utterance a report is always spoken as (`plans/
    voice-command-completeness/plan.md` Decision 1b: "One utterance, not
    one line per group, is the whole point" -- `plans/callout-scheduling/`
    removed the backlog by never having more than one thing in flight, and
    a report that pushed several lines through `_print` in a loop would
    reintroduce exactly that). `truncated` appends `" And more."` when the
    caller capped the group count (`REPORT_MAX_GROUPS`) below the number of
    groups that actually matched."""
    text = " ".join(group_texts)
    if truncated:
        text += " And more."
    return OutgoingSpeech(text=text, template="contact_report")


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


def render_no_contact(only_clock_label: str | None = None) -> OutgoingSpeech:
    """`follow`'s match-floor failure (`plans/watch-reporting/plan.md`
    Decision 2b-iii): "watch nothing and say so" rather than watching the
    least-bad candidate, which would be worse than admitting no match --
    the pilot would get confident reports about the wrong object.

    `only_clock_label`, when given (already formatted, e.g. `"two
    o'clock"`), narrows the wording to `"Nothing at two o'clock."` -- used
    only when the clock was the sole qualifier the pilot gave, since
    naming the one thing he actually said is more informative than the
    generic line. `None` (descriptor or range was also given, or nothing
    was given at all) speaks the generic `"Nothing like that."`."""
    if only_clock_label is not None:
        return OutgoingSpeech(
            text=f"Nothing at {only_clock_label}.", template="contact_report"
        )
    return OutgoingSpeech(text="Nothing like that.", template="contact_report")


#: `class`-level `OP_*` buckets -> a human word, for the contact report's
#: unit-type field. See module docstring's "Contact report format" note.
#:
#: **Exhaustiveness is enforced by a test, not by this comment.** An earlier
#: version of this note claimed every value `perception.object_model` assigns
#: had an entry, and it was true when written. `OP_LRSAM` was added to the
#: object model later and never added here, so a live sortie produced
#: *"unit at 12 o'clock, 2 kilometres is OP_LRSAM"* -- an internal identifier
#: read aloud to the pilot. `test_speech.py` now derives the set of assigned
#: classes from `object_model` itself and asserts both tables cover it, so
#: the next class added to the object model fails a test instead of reaching
#: the audio channel.
#:
#: The three SAM tiers are spoken apart rather than collapsed to "SAM"
#: (user, 2026-09-23, from that sortie): the difference between a short-range
#: and a long-range SAM is the difference between a threat you can fly around
#: and one you cannot, so flattening them discards the most decision-relevant
#: thing in the call.
_OP_CLASS_DISPLAY: Final[dict[str, str]] = {
    "OP_ARMORED": "armor",
    "OP_TRUCK": "truck",
    "OP_INFANTRY": "infantry",
    "OP_SRSAM": "short range SAM",
    "OP_MRSAM": "medium range SAM",
    "OP_LRSAM": "long range SAM",
    "OP_SPAAG": "AAA",
    "OP_ZU23": "AAA",
    "OP_SHIP": "ship",
    # The object model's default class -- "some group of something", which
    # is what an unrecognised DCS type falls back to. It was documented here
    # as unreachable at `class` level; the same sortie disproved that
    # (*"unit at 9 o'clock, very close is OP_GROUPSOMETHING"*), so it gets a
    # sayable word rather than an assertion.
    "OP_GROUPSOMETHING": "group",
}

#: `_OP_CLASS_DISPLAY`'s plural sibling, for `_plural_unit_type_display`. See
#: module docstring's "Stage 4b -- the count clause" note. It used to carry a
#: comment explaining why `"OP_GROUPSOMETHING"` needed no entry -- a
#: class-level classification supposedly could never hold that value. A live
#: sortie said otherwise, so it has one, and the exhaustiveness test covers
#: this table too.
_OP_CLASS_DISPLAY_PLURAL: Final[dict[str, str]] = {
    "OP_ARMORED": "armor",  # already a mass noun -- singular form doubles as plural
    "OP_TRUCK": "trucks",
    "OP_INFANTRY": "infantry",  # mass noun
    "OP_SRSAM": "short range SAMs",
    "OP_MRSAM": "medium range SAMs",
    "OP_LRSAM": "long range SAMs",
    "OP_SPAAG": "AAA",  # mass/acronym -- unchanged
    "OP_ZU23": "AAA",
    "OP_SHIP": "ships",
    "OP_GROUPSOMETHING": "contacts",  # "groups" reads as formations, not contacts
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
    # "AAA" reads as three letters; the crew word is "triple A" (user,
    # 2026-09-23). Unlike the Mi-XX entries this is not a mis-reading fix but
    # a vocabulary one -- the letters are pronounced correctly and are still
    # the wrong thing to say.
    "aaa": "triple A",
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


def _identification_lead(value: object, unit_type: str) -> str:
    """The noun an identification line opens with: the contact's class when
    that is known, else `"unit"` (user, 2026-09-23).

    *"armor 11 o'clock, very close is BTR-80"* tells the pilot what he is
    being asked to look at before it tells him what it turned out to be;
    *"unit at 11 o'clock..."* made him wait for the payload. The article
    goes with it, for the same brevity reason as everything else here.

    The class is derived from the identified type rather than read from the
    contact, because at the moment a classification *changes* the new value
    is the type and the previous class word is not carried in the event. A
    type whose profile falls to the object model's default class yields
    nothing sayable -- `BM-30` and `SA-10 Flap Lid radar` both do -- so
    those keep `"unit"` rather than opening with `"group"`, which would read
    as a formation rather than as a description. Nor does the lead repeat
    the payload: *"truck ... is truck"* is a stutter, not a report --
    and so is *"truck ... is KrAZ truck"* (a real live callout,
    `plans/position-belief-runaway/debug.md`), where the class word is not
    the *whole* type string but still reads back as the same word once
    spoken. The original check only caught an exact match; it is now a
    whole-word containment test (`\btruck\b` against `"kraz truck"`), since
    a type name repeating the class word anywhere as its own word is the
    same stutter, not merely the identical-string case.
    """
    if not isinstance(value, str) or not value:
        return "unit"
    from perception import object_model

    op_class = object_model.profile_for(value).op_class
    if op_class == object_model.DEFAULT_OP_CLASS:
        return "unit"
    word = _OP_CLASS_DISPLAY.get(op_class)
    if not word:
        return "unit"
    spoken = _respell_for_tts(word)
    # "truck 11 o'clock ... is truck" says the same word twice and sounds
    # like a stutter rather than a report -- and so does "... is KrAZ
    # truck", where the class word appears as its own word inside a longer
    # type name. A whole-word containment test catches both; a bare
    # substring test would not (it would also risk a false hit on an
    # unrelated word that merely contains these letters, which `\b`
    # avoids).
    if re.search(rf"\b{re.escape(spoken.lower())}\b", unit_type.lower()):
        return "unit"
    return spoken


def _unmapped_class_display(value: str, generic: str) -> str:
    """What to say for a `class` value neither display table maps.

    **Internal identifiers are suppressed; everything else passes through.**
    A `class`-level value is not always an `OP_*` bucket -- it can be a raw
    DCS type name or free text from the scope/hybrid channel, and those are
    already sayable, so replacing them would throw away real information.
    Only the `OP_` prefix marks a value as this codebase's own vocabulary,
    which the pilot has no reason to have heard of.

    That distinction was learned the expensive way in both directions. The
    original behaviour returned every unmapped value verbatim, which is why
    a sortie heard *"...is OP_LRSAM"*. The first fix replaced every unmapped
    value with a generic word, which the existing tests immediately caught:
    it would have reduced *"BMP-2"* to *"contact"*.

    Falling back to a generic word costs one level of specificity, which is
    what an unrecognised classification means anyway. A vocabulary gap should
    cost specificity, never intelligibility.
    """
    if value.startswith("OP_"):
        return generic
    return value


def _unit_type_display(value: object, level: object) -> str:
    """The contact report's unit-type field, from `facts["classification"]`'s
    `value`/`level`. See module docstring's "Contact report format" note.
    Lowercase throughout, consistent with `_OP_CLASS_DISPLAY`'s own
    vocabulary (acronyms like `"SAM"`/`"AAA"` excepted)."""
    if level == "type" and isinstance(value, str) and value:
        return _respell_for_tts(value)
    if level == "class" and isinstance(value, str) and value:
        # Respelled as well as mapped: the respell table used to be
        # type-level only, on the reasoning that class words needed no
        # fixing. "AAA" is a class word and does need it.
        return _respell_for_tts(
            _OP_CLASS_DISPLAY.get(value, _unmapped_class_display(value, "contact"))
        )
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
        return _respell_for_tts(
            _OP_CLASS_DISPLAY_PLURAL.get(
                value, _unmapped_class_display(value, "contacts")
            )
        )
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
        return "handful"
    if lo >= 2 and hi <= 3:
        return "couple"
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
    # "1 kilometres" was heard live (2026-09-23). Only exactly 1 takes the
    # singular: 0.5 and 1.5 are both plural in English, which is why this is
    # an equality check rather than a "less than or equal to one" test.
    unit = "kilometre" if range_km == 1 else "kilometres"
    return f"{range_str} {unit}"


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


def _contact_report_text(
    facts: dict[str, object],
    *,
    lead: str | None = None,
    event_clause: str | None = None,
) -> str:
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
    existing test in this module is that guard.

    **`lead`/`event_clause` (`plans/watch-reporting/plan.md` Decision 3).**
    Both optional, both `None` by default so every pre-existing caller is
    byte-for-byte unaffected. `lead`, when given, already carries its own
    trailing punctuation/spacing (`"Danger, "`, `"Safe from "`) and is
    simply prepended -- no separator logic here, since the two wordings
    this milestone needs join differently ("Danger, SAM..." vs. "Safe from
    SAM...") and baking a comma in would get one of them wrong.
    `event_clause`, when given, is inserted before the terminating period
    in place of -- not in addition to -- the automatic `", moving"` clause
    below: a motion callout that got both would read "armor, two o'clock,
    three kilometres, moving, moving.\""""
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
    if lead is not None:
        text = f"{lead}{text}"
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
    if event_clause is not None:
        text += f", {event_clause}"
    else:
        motion = facts.get("motion")
        # `plans/movement-detection/plan.md` Stage 4 -- one trimmable
        # clause, deliberately last and deliberately thin (this milestone's
        # value is the belief and the event, not wording iteration). Only
        # `"moving"` is ever spoken: a crew member volunteers motion when
        # there IS motion to report, not a "stationary" clause on every
        # single contact report -- the semantic-fragment/count-clause
        # precedent above (both omitted rather than stated when there's
        # nothing notable to add). Suppressed entirely when `event_clause`
        # was supplied -- see this function's own docstring.
        if isinstance(motion, dict) and motion.get("state") == "moving":
            text += ", moving"
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
    "Aggregation" section) -- `belief.callouts.group_facts` has already
    decided `facts_list` all share the same `_unit_type_display`/
    `_format_range_km` words, so this function does no grouping decision of
    its own; it only composes one line from several `describe_contact`
    results, reusing exactly the vocabulary a single-contact report already
    uses rather than adding a second phrasing path. (`group_facts`'s own
    caller since `plans/group-reporting/plan.md`'s Stage 4 is `belief.
    crew_console.CrewConsole._handle_report`'s residual bucketing of
    contacts with no persisted `belief.groups.Group` -- `belief.callouts.
    group_candidates`, this function's original caller, is retired.)

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
      `relative_now` (`group_facts` only ever buckets members that have
      one).
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


def _classification_key(facts: dict[str, object]) -> tuple[object, object]:
    """`(value, level)` out of `facts["classification"]` -- the grouping
    key `_group_composition_clause` buckets on, factored out so `render_
    group_disclosure`'s pair/couple wording (below) can ask the identical
    "do these members share one classification" question without
    duplicating the dict-shape assertion."""
    classification = facts["classification"]
    assert isinstance(classification, dict)
    return (classification.get("value"), classification.get("level"))


#: `plans/group-undermerging/review.md`'s Finding 1 fix (2026-10-01,
#: superseding a same-day fix that corrected `"a armor"` to `"an armor"`
#: instead of removing the article). `"Armor"` is a mass noun -- it takes
#: no indefinite article in any form, so `"an armor"` is not English
#: either, and patching the vowel mismatch while keeping the article was
#: fixing the wrong half of the bug.
#:
#: The real fix is to drop the article for every class/type word a
#: count==1 composition phrase can hold, mass noun or not, and this
#: matches this module's own existing convention rather than inventing a
#: new one: every other singular rendering in this file -- `_contact_
#: report_text`'s own single-contact line, `_identification_lead`'s
#: `"armor 11 o'clock..."` -- already speaks a bare class/type noun with
#: no leading article. So does every one of the user's own worked
#: examples (`plans/group-cohesion-redesign/explore-notes-delta-
#: taxonomy.md`): `"AAA in the group"`, `"Shilka and zsu"`, `"SRSAM,
#: Shilka, armor 2 o'clock 2.5 km"` -- count nouns (`"Shilka"`, `"zsu"`)
#: appear exactly as bare as mass nouns (`"AAA"`, `"armor"`) in a
#: composition list; the one article in that file, `"there's a zsu"`, sits
#: in a different sentence frame (an existential singular announcement),
#: not a composition clause, so it is not evidence for treating count
#: nouns differently here. There is accordingly no count-noun/mass-noun
#: split to maintain in this function at all -- removing `_with_
#: indefinite_article` rather than growing it.


#: `_classification_level`'s undifferentiated levels, named here too so
#: `_group_composition_clause` can test for them without importing a
#: function whose own name reads oddly applied to a bare `(value, level)`
#: key rather than a facts dict.
_UNDIFFERENTIATED_LEVELS: Final = ("presence", "unknown")


def _undifferentiated_phrase(count: int) -> str:
    """How `_group_composition_clause` names member(s) with no class/type
    yet, aggregated into one phrase rather than one `"a ground"` per member
    (the Finding 2 fix, `plans/group-undermerging/review.md`) -- the user's
    own worked examples are the specification: *"SAM and something"* for a
    single undifferentiated member alongside a known one, *"a couple of
    contacts"* / *"two contacts"* for more than one. A lone member is
    `"something"`, not `"a contact"` -- `_unit_type_display`'s own
    `"contact"` fallback reads as a tracked, nameable thing, while
    `"something"` reads as genuinely unclassified, matching the example's
    own word. More than one reuses `_plural_unit_type_display`'s presence-
    level fallback, `"contacts"`, counted the same way a real class would
    be. Where the examples do not cover a count (three or more
    undifferentiated members alongside a differentiated one), this follows
    the many-contacts fallback already used elsewhere in this function
    rather than inventing new wording."""
    if count == 1:
        return "something"
    if count in _SPOKEN_NUMBERS:
        return f"{_SPOKEN_NUMBERS[count]} contacts"
    return "many contacts"


def _group_composition_clause(member_facts: Sequence[dict[str, object]]) -> str:
    """The per-class member breakdown for `render_group_disclosure`'s
    composition line (`plans/group-reporting/plan.md` Stage 3's worked
    example, rows 2-4): buckets `member_facts` by `_classification_key` and
    counts real members per bucket -- an **exact** count, never a
    `_cardinality_phrase` hedge, because this is a literal groupby over
    already-individuated, already-identified `Contact`s (the plan's own
    "not new belief machinery" framing), not an estimate of how many real
    objects one unresolved cluster stands for. Reuses `_SPOKEN_NUMBERS`/
    `_unit_type_display`/`_plural_unit_type_display` exactly as the
    single-contact vocabulary already does, so a mass-noun class (e.g.
    `"armor"`, which has no distinct plural form) reads the same way here
    as it already does in a single contact's own count clause -- a known,
    accepted quirk of that vocabulary, not new to this function.

    **Undifferentiated (`presence`/`unknown` level) members are aggregated
    into one trailing phrase, never counted as their own noun phrase per
    member.** This was a real defect (`plans/group-undermerging/review.md`
    Finding 2): calling `_unit_type_display(None, "presence")` per member
    and composing it like a real class produced `"a ground and a truck"`
    for a 2-member group with one undifferentiated member -- `"ground"` is
    `_unit_type_display`'s internal fallback word, not something a crew
    member says about an unclassified contact. See `_undifferentiated_
    phrase` for the aggregated wording, matched against the user's own
    examples (*"SAM and something"*).

    Callers must still not call this with an empty sequence, or with
    *only* undifferentiated members -- see `render_group_disclosure`'s own
    "Group"/"a couple of contacts" bare-word branches for that case, which
    this function deliberately leaves to the caller rather than rendering
    itself (a composition clause with nothing differentiated to lead with
    is a different sentence shape, not this one with an empty prefix)."""
    order: list[tuple[object, object]] = []
    counts: dict[tuple[object, object], int] = {}
    undifferentiated_count = 0
    for facts in member_facts:
        key = _classification_key(facts)
        _, level = key
        if level in _UNDIFFERENTIATED_LEVELS:
            undifferentiated_count += 1
            continue
        if key not in counts:
            order.append(key)
            counts[key] = 0
        counts[key] += 1

    phrases: list[str] = []
    for key in order:
        value, level = key
        count = counts[key]
        if count == 1:
            phrases.append(_unit_type_display(value, level))
        elif count in _SPOKEN_NUMBERS:
            phrases.append(
                f"{_SPOKEN_NUMBERS[count]} {_plural_unit_type_display(value, level)}"
            )
        else:
            phrases.append(f"many {_plural_unit_type_display(value, level)}")

    if undifferentiated_count:
        phrases.append(_undifferentiated_phrase(undifferentiated_count))

    assert phrases, (
        "_group_composition_clause called with only undifferentiated "
        "members -- see this function's own docstring"
    )
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + f" and {phrases[-1]}"


def _group_member_facts(
    store: ContactStore,
    group: Group,
    now_sim: float,
    enrichment: EnrichmentContext | None = None,
) -> list[dict[str, object]] | None:
    """The member-facts gathering loop `render_group_disclosure` needs, and
    `belief.callouts.group_priority` (`plans/group-reporting/plan.md`
    Stage 4 design, section 3) needs too, for its own `range_m`/
    `attention_rank` -- extracted here rather than gathered twice, once per
    caller. Returns `None` under the same "fewer than two members still
    resolve" guard `render_group_disclosure` already enforces -- there is
    nothing coherent left to score or report as a group.

    Does not resolve `Contact` objects, only `describe_contact` facts --
    `render_group_disclosure`'s own threat-leading logic needs the real
    `Contact.classification` (`belief.threat.envelope_for`'s argument type),
    which this function deliberately does not gather, since `belief.
    callouts` has no use for it and no license to hold a `Contact` at all."""
    member_facts: list[dict[str, object]] = []
    for member_id in sorted(group.member_contact_ids):
        result = describe_contact(store, member_id, now_sim, enrichment=enrichment)
        if result is None:
            continue
        member_facts.append(result["facts"])
    if len(member_facts) < 2:
        return None
    return member_facts


def _member_contacts_for(
    store: ContactStore, member_facts: Sequence[dict[str, object]]
) -> list[Contact]:
    """`member_facts`' own `Contact` objects, in the same order -- the real
    `Contact.classification` `envelope_for`/the delta taxonomy need, which
    `describe_contact`'s facts dict deliberately does not carry (`belief.
    callouts` has no license to hold a `Contact` at all; this module, which
    already imports `Contact`, does)."""
    contacts_by_id = {contact.id: contact for contact in store.contacts}
    member_contacts: list[Contact] = []
    for facts in member_facts:
        contact_id = facts["id"]
        assert isinstance(contact_id, str)
        member_contacts.append(contacts_by_id[contact_id])
    return member_contacts


def _leading_index(member_contacts: Sequence[Contact]) -> int | None:
    """Index into `member_contacts` of the member with the widest
    resolvable engagement envelope (`belief.threat.envelope_for`), or
    `None` if no member resolves one. Shared by `render_group_disclosure`'s
    composition logic and `group_membership_state`'s leader-change
    bookkeeping, so the two never silently diverge on what "the leader"
    means."""
    leading_index: int | None = None
    leading_range_max_m = -1.0
    for index, contact in enumerate(member_contacts):
        envelope = envelope_for(contact.classification)
        if envelope is not None and envelope.range_max_m > leading_range_max_m:
            leading_range_max_m = envelope.range_max_m
            leading_index = index
    return leading_index


def _classification_level(facts: dict[str, object]) -> object:
    """`facts["classification"]["level"]`, typed through an explicit
    `isinstance` assertion rather than a bare `.get` on an `object`-typed
    dict value -- shared by every "is this member still undifferentiated"
    check in this module's group-disclosure taxonomy."""
    classification = facts["classification"]
    assert isinstance(classification, dict)
    return classification.get("level")


def _is_differentiated(member_facts: Sequence[dict[str, object]]) -> bool:
    """Whether any member has crossed from undifferentiated
    (`presence`/`unknown` classification level) to a real class/type --
    the first-differentiation signal both the full-disclosure branch and
    `group_membership_state` read."""
    return any(
        _classification_level(facts) not in ("presence", "unknown")
        for facts in member_facts
    )


def _is_air_defence(facts: dict[str, object]) -> bool:
    """Whether `facts`' believed classification resolves to one of
    `belief.groups.AIR_DEFENSE_OP_CLASSES` -- the delta taxonomy's
    "more air defence is always news" test (`plans/
    group-cohesion-redesign/plan.md` §4 Correction 2). Reads `perception.
    object_model.profile_for` on the classification's raw value, the same
    no-omniscience lookup `_identification_lead`/`belief.groups.
    _representative_size_m` already use for a believed classification --
    never a DCS `object_type`."""
    classification = facts["classification"]
    assert isinstance(classification, dict)
    value = classification.get("value")
    if not isinstance(value, str) or not value:
        return False
    from perception import object_model

    return object_model.profile_for(value).op_class in AIR_DEFENSE_OP_CLASSES


def _nearest_clock_position(member_facts: Sequence[dict[str, object]]) -> int | None:
    """The clock position of the group's nearest member (by `relative_now.
    range_m`) -- the same "report the near edge of a cluster" convention
    `render_group_disclosure`'s own clock/range clause and `render_group_
    report` already use, factored out so the membership-delta branch can
    build its own "in {clock} o'clock group" clause without duplicating
    the nearest-member scan."""
    nearest_clock: int | None = None
    nearest_range_m = math.inf
    for facts in member_facts:
        relative_now = facts.get("relative_now")
        if not isinstance(relative_now, dict):
            continue
        range_m = relative_now["range_m"]
        assert isinstance(range_m, float)
        if range_m < nearest_range_m:
            nearest_range_m = range_m
            clock = relative_now["clock_position"]
            assert isinstance(clock, int)
            nearest_clock = clock
    return nearest_clock


def group_membership_state(
    store: ContactStore,
    group: Group,
    now_sim: float,
    enrichment: EnrichmentContext | None = None,
) -> tuple[frozenset[str], str | None, bool] | None:
    """`(member_contact_ids, leading_contact_id, differentiated)` -- the
    three delta-taxonomy signals `render_group_disclosure` itself computes
    to decide *what* to say, gathered again here for a caller
    (`belief.callouts.CalloutScheduler.tick`) that needs the exact same
    values to pass to `GroupStore.mark_spoken`/`ContactStore.
    mark_group_spoken` *after* a successful disclosure, so the next call to
    `render_group_disclosure` reads back what was actually last spoken.

    Mirrors the existing double-`_group_member_facts`-call pattern already
    between this module and `belief.callouts` (that module gathers its own
    copy for `group_priority`) rather than growing `OutgoingSpeech` a new
    field to smuggle this out of `render_group_disclosure` -- the two calls
    are cheap `describe_contact` lookups, not a new I/O cost class.

    Returns `None` under the same `_group_member_facts` "fewer than two
    members still resolve" guard `render_group_disclosure` itself enforces."""
    member_facts = _group_member_facts(store, group, now_sim, enrichment)
    if member_facts is None:
        return None
    member_contacts = _member_contacts_for(store, member_facts)
    leading_index = _leading_index(member_contacts)
    leading_contact_id = (
        member_contacts[leading_index].id if leading_index is not None else None
    )
    member_ids = frozenset(contact.id for contact in member_contacts)
    differentiated = _is_differentiated(member_facts)
    return member_ids, leading_contact_id, differentiated


def _render_full_group_composition(
    member_facts: list[dict[str, object]],
    leading_index: int | None,
    differentiated: bool,
) -> tuple[str, str]:
    """The full-roster disclosure composition -- `(text, content_signature)`
    before either has its trailing `"."`/clock-range/watched clause
    stripped by the caller's own needs. Unchanged in substance from the
    original Stage 3 design (`plans/group-reporting/plan.md`); factored out
    so it has exactly one implementation shared by `render_group_
    disclosure`'s own never-spoken/first-differentiation branches (the push
    path, gated by the delta taxonomy) and `render_group_full_disclosure`
    below (the "report" pull path, which always wants the full roster and
    must never see a delta or a silent `None` -- see that function's own
    docstring for why the two paths cannot share one taxonomy-gated
    function)."""
    if leading_index is not None:
        leading_classification = member_facts[leading_index]["classification"]
        assert isinstance(leading_classification, dict)
        leading_word = _unit_type_display(
            leading_classification.get("value"),
            leading_classification.get("level"),
        )
        rest = member_facts[:leading_index] + member_facts[leading_index + 1 :]
        if rest:
            text = f"Danger, {leading_word}. Also {_group_composition_clause(rest)}"
        else:
            text = f"Danger, {leading_word}."
    else:
        is_pair = len(member_facts) == 2
        homogeneous = len({_classification_key(facts) for facts in member_facts}) == 1
        if differentiated and is_pair and homogeneous:
            value, level = _classification_key(member_facts[0])
            text = f"Pair of {_plural_unit_type_display(value, level)}"
        elif differentiated:
            composition = _group_composition_clause(member_facts)
            text = composition[0].upper() + composition[1:]
        elif is_pair:
            value, level = _classification_key(member_facts[0])
            text = f"A couple of {_plural_unit_type_display(value, level)}"
        else:
            text = "Group"

    # `content_signature` (module docstring's `OutgoingSpeech` entry,
    # `plans/group-undermerging/debug.md`): the composition decided above
    # is the whole substance of a group disclosure -- clock/range is
    # positional, not content, and must not be part of what decides
    # whether this is "the same thing already said." Captured here,
    # before the clock/range clause below is appended to `text`, and
    # given the same trailing "watched"/"." treatment so the two strings
    # differ only by the clock/range clause itself.
    content_signature = text

    nearest_relative_now: dict[str, object] | None = None
    nearest_range_m = math.inf
    for facts in member_facts:
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

    watched = any(
        facts.get("attention") in ("watch", "priority") for facts in member_facts
    )
    if watched:
        text += ", watched"
        content_signature += ", watched"

    text += "."
    content_signature += "."
    return text, content_signature


def render_group_full_disclosure(
    store: ContactStore,
    group: Group,
    now_sim: float,
    enrichment: EnrichmentContext | None = None,
) -> OutgoingSpeech | None:
    """The always-full-roster group disclosure for a pull-based query --
    `belief.crew_console.CrewConsole._handle_report`'s "report" command,
    per the delta taxonomy's own worked example (`plans/
    group-cohesion-redesign/plan.md` §4, explore-notes-delta-taxonomy.md):
    *`Pilot: "report"` -> "SRSAM, Shilka, armor 2 o'clock 2.5 km. ..."`* --
    the report roll-up always names the group's current full composition,
    never a delta, regardless of what the group last said on the push path.

    **Deliberately does not call `render_group_disclosure`.** That
    function's taxonomy decides full/delta/silent by comparing against
    `Group.last_spoken_*` -- exactly right for `CalloutScheduler`'s push
    path, which must not re-announce a group's whole roster on every tick,
    but exactly wrong for a report, which the pre-existing call site's own
    comment already documented as "pull-based, so it always speaks fresh --
    no gate here." Before the delta taxonomy existed the two needs
    coincided (`render_group_disclosure` only ever produced the full
    composition), so one function served both call sites; the taxonomy
    split that coincidence, and this function is the pull path's own,
    taxonomy-free half of what `render_group_disclosure` used to always do.

    Returns `None` under the same `_group_member_facts` "fewer than two
    members still resolve" guard every other group-reading function in this
    module uses -- the only reason this can return nothing, since there is
    no taxonomy gate here to also return `None`."""
    member_facts = _group_member_facts(store, group, now_sim, enrichment)
    if member_facts is None:
        return None
    member_contacts = _member_contacts_for(store, member_facts)
    leading_index = _leading_index(member_contacts)
    differentiated = _is_differentiated(member_facts)
    text, content_signature = _render_full_group_composition(
        member_facts, leading_index, differentiated
    )
    return OutgoingSpeech(
        text=text, template="contact_report", content_signature=content_signature
    )


def render_group_disclosure(
    store: ContactStore,
    group: Group,
    now_sim: float,
    enrichment: EnrichmentContext | None = None,
) -> OutgoingSpeech | None:
    """`plans/group-reporting/plan.md` Stage 3's disclosure ladder for a
    persisted `belief.groups.Group` -- **not** `render_group_report` above,
    which was `belief.callouts.group_candidates`'s speech-time, report-space
    aggregation of several *events* (`group_candidates` itself is retired
    as of Stage 4 -- see this module's own docstring). This function reads
    a real, persisted associative belief instead. (The plan's own prose
    names both functions `render_group_report`; this one is named `render_
    group_disclosure` instead, deliberately, to avoid colliding with the
    function that already existed under that name and stays live, as the
    residual report-space path -- see `belief.callouts`' own docstring,
    "`group_facts`/`render_group_report` are report-space bucketing.")

    Stage 4 wires this function into `belief.callouts.CalloutScheduler.tick`
    (the live speech path) and into `belief.crew_console.CrewConsole.
    _handle_report` (the on-demand "report" command) -- both read this
    same function so a pushed callout and a pulled report describe one
    group identically.

    Returns `None` if fewer than two members still resolve to a live
    `Contact` (`_group_member_facts` returns `None`), or if the delta
    taxonomy below decides this tick is silent at the group level.

    **The delta taxonomy** (`plans/group-cohesion-redesign/plan.md` §4,
    rebuilt against worked utterances rather than rules inferred from
    them) decides whether this call is a full disclosure, a short delta
    clause, or silent, by comparing the group's *current* state against
    what it last said (`Group.last_spoken_signature`/`.last_spoken_
    member_contact_ids`/`.last_spoken_leading_contact_id`/`.last_spoken_
    differentiated`), in this priority order -- first match decides, since
    only one utterance is ever returned per call:

    1. **Never spoken** (`last_spoken_signature is None`): full disclosure.
    2. **The leading member changed** (a new leader, or leader gained --
       `None` to some contact id): a short `"Now leading: {type}."` delta,
       never a full restatement (Correction 1) -- reusing `_identification_
       lead`'s sibling vocabulary, `_unit_type_display`. **Leader *lost*
       (some contact id to `None`) is deliberately NOT this branch** -- no
       worked example covers "the group just de-escalated," and losing the
       one threat-capable member is, in every case this taxonomy's
       departure rule already covers, a member *departing* the group
       (silent at group level, told via that member's own lifecycle event
       if it matters) rather than a new fact needing its own delta clause.
       A judgment call, not a worked-example-backed rule -- flagged here
       rather than silently assumed.
    3. **First differentiation** (`not last_spoken_differentiated and`
       differentiated now): full disclosure, once.
    4. **A newly arrived, differentiated member is worth announcing** --
       either its class was not already known among the group's
       *continuing* members (a genuinely new class joining), or it belongs
       to `belief.groups.AIR_DEFENSE_OP_CLASSES` (another instance of an
       already-known air-defence class still counts as news, Correction 2,
       *"more air defense does make a difference"*): a delta clause
       composing just the newly-worth-announcing arrivals via `_group_
       composition_clause`, suffixed `", in {clock} o'clock group"` -- the
       "group" disambiguation word the user's own examples use exactly
       here (*"so it's not a single shilka that is detected"*). An
       undifferentiated arrival (still `presence`/`unknown`) is never
       itself delta-worthy; it simply joins the roster silently until it
       differentiates (at which point it is a *continuing* member, not a
       new arrival, so §3's crossing above is what would speak it, if
       anything does).
    5. **Otherwise, silent** -- covers "one more truck/armor makes no
       difference," "members only departed, no new arrivals, same leader,"
       and a non-leading member's own type refinement (already told via
       its own `CONTACT_CLASSIFICATION_CHANGED` event, per module
       docstring's "Which lifecycle kinds get a template").

    **The full-disclosure composition itself is unchanged from the
    original Stage 3 design** -- only the branch conditions above are new.
    **Threat leads the line** (`belief.threat.envelope_for`, called on each
    member's own `Contact.classification` -- the no-omniscience boundary is
    upstream of this call, in `envelope_for` itself): the member with the
    widest resolvable engagement envelope leads with `"Danger, {type}."`,
    and every other member's composition follows as `"Also {composition}"`.

    **With no threat-capable member, the quantity word tracks classification
    specificity, the same rule `_cardinality_phrase` already applies to a
    single contact's own count clause -- never a precise count paired with
    a vague class, never a vague count paired with a precise one** (user
    direction 2026-09-28, extending `plans/group-contact-model/plan.md`'s
    settled "count precision must track classification specificity" rule
    from *within* one contact's cardinality to *across* a group's members).
    A two-member group is the only size this stage words specially:

    - **Undifferentiated** (every member still at `presence`/`unknown`
      level -- nothing precise is known to speak): `"A couple of
      {contacts}"` for a pair, the bare word `"Group"` for three or more.
      `"a couple of"` is `_cardinality_phrase`'s own hedge for two-or-three,
      reused here rather than invented, because the quantity being hedged
      is genuinely the same kind of vague count.
    - **Differentiated, and every member shares one classification** (a
      real, identical class/type across the whole group): `"Pair of
      {plural}"` for a pair (e.g. *"Pair of T-72s"*) -- the exact-count form
      of the same word, earned because the classification being counted is
      itself exact. Three or more homogeneous members still go through
      `_group_composition_clause`'s existing `_SPOKEN_NUMBERS` ladder
      (`"Three T-72s"`), unchanged by this stage.
    - **Differentiated but mixed** (a real classification exists, but not
      every member shares it): `_group_composition_clause` as before --
      `"Armor and truck"` already names each member exactly once, with
      no quantity word to pick between at all and no indefinite article
      on either (`plans/group-undermerging/review.md` Finding 1).

    A sentence never reaches for both "pair" and "a couple of" together,
    because the classification specificity that selects one rules out the
    other -- this is one ladder with two rungs, not two competing
    vocabularies needing a tiebreak.

    Clock/range are taken from the group's nearest member (`_contact_report_
    text`'s single-contact convention, restated here since a group has no
    such helper of its own), and a trailing `", watched"` is appended when
    any member is under `watch`/`priority` attention -- the group-level
    analogue of a single contact's own trailing motion clause. **Neither
    clause/trailing-word is attached to a delta branch** (§4's own worked
    examples -- `"Now leading: SRSAM."`, `"Shilka, in 2 o'clock group"` --
    carry no separate range figure and no watched marker): the leader-delta
    carries no positional clause at all, and the membership-delta's own
    `", in {clock} o'clock group"` suffix already is its positional
    clause."""
    member_facts = _group_member_facts(store, group, now_sim, enrichment)
    if member_facts is None:
        return None
    member_contacts = _member_contacts_for(store, member_facts)
    leading_index = _leading_index(member_contacts)
    leading_contact_id = (
        member_contacts[leading_index].id if leading_index is not None else None
    )
    differentiated = _is_differentiated(member_facts)

    never_spoken = group.last_spoken_signature is None
    leader_changed = (
        leading_contact_id is not None
        and leading_contact_id != group.last_spoken_leading_contact_id
    )
    first_differentiation = not group.last_spoken_differentiated and differentiated

    delta_members: list[dict[str, object]] = []
    if not (never_spoken or leader_changed or first_differentiation):
        current_member_ids = frozenset(contact.id for contact in member_contacts)
        new_arrival_ids = current_member_ids - group.last_spoken_member_contact_ids
        known_classes = {
            _classification_key(facts)
            for facts in member_facts
            if facts["id"] in group.last_spoken_member_contact_ids
            and _classification_level(facts) not in ("presence", "unknown")
        }
        for facts in member_facts:
            if facts["id"] not in new_arrival_ids:
                continue
            if _classification_level(facts) in ("presence", "unknown"):
                continue
            key = _classification_key(facts)
            is_new_class = key not in known_classes
            is_air_defence_repeat = not is_new_class and _is_air_defence(facts)
            if is_new_class or is_air_defence_repeat:
                delta_members.append(facts)

    if never_spoken or first_differentiation:
        text, content_signature = _render_full_group_composition(
            member_facts, leading_index, differentiated
        )
    elif leader_changed:
        assert leading_index is not None
        leading_classification = member_facts[leading_index]["classification"]
        assert isinstance(leading_classification, dict)
        leading_word = _unit_type_display(
            leading_classification.get("value"), leading_classification.get("level")
        )
        text = f"Now leading: {leading_word}."
        content_signature = text
    elif delta_members:
        composition = _group_composition_clause(delta_members)
        composed = composition[0].upper() + composition[1:]
        clock = _nearest_clock_position(member_facts)
        if clock is not None:
            text = f"{composed}, in {clock} o'clock group."
        else:
            text = f"{composed}, in the group."
        content_signature = text
    else:
        return None

    return OutgoingSpeech(
        text=text, template="contact_report", content_signature=content_signature
    )


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
            lead = _identification_lead(classification.get("value"), unit_type)
            return (
                f"{lead} {clock} o'clock, {_format_range_km(range_m)} is {unit_type}."
            )
        return f"{_identification_lead(classification.get('value'), unit_type)} is {unit_type}."
    if event.kind == CONTACT_CARDINALITY_CHANGED:
        return None
    if event.kind == CONTACT_MOTION_CHANGED:
        # `plans/watch-reporting/plan.md` Stage 1 -- watched-only (gated by
        # `belief.callouts.CalloutScheduler.tick`, not here; this function
        # only renders). `event.motion` is `None` only when `current is
        # None`, which `belief.events.motion_event_kind` already refuses to
        # fire an event for -- reachable here only if a caller routed a
        # motion event through this function directly, so this is
        # defensive, not a real path.
        if event.motion is None:
            return None
        return _contact_report_text(result["facts"], event_clause=event.motion)
    if event.kind == CONTACT_RANGE_CROSSED:
        # `plans/watch-reporting/plan.md` Decision 3, REVISED 2026-09-25
        # (user, after flying it). The original reading gave this kind no
        # affixes, because "the range *is* the news, and it is already in
        # the body". Flown, that made a *belief update about a contact he
        # is not currently looking at* word-for-word indistinguishable
        # from a fresh sighting: he heard "ground, 10 o'clock, 2 km" while
        # a commanded `scan right` was in force and reasonably read it as
        # a detection defect (`plans/callout-outside-gaze/debug.md`).
        #
        # His wording, and it beats merely tagging provenance: it carries
        # the one thing the bare form threw away -- *which direction* the
        # range crossed. The number alone cannot say, because the pilot
        # does not hold the previous number in his head; "three
        # kilometres" is only news if you know it was four a moment ago.
        #
        # The direction needs no new state: the event already snapshots
        # the whole-kilometre band either side of the crossing, which is
        # what `belief.contacts`' range block compared to decide the event
        # fires at all.
        if event.range_km is None or event.previous_range_km is None:
            # Defensive only: `belief.events.range_crossing_event` never
            # emits this kind without both bands. Falling back to the bare
            # form is better than saying a direction we cannot support.
            return _contact_report_text(result["facts"])
        closing = event.range_km < event.previous_range_km
        lead = "Getting closer, " if closing else "Moving away, "
        return _contact_report_text(result["facts"], lead=lead)
    if event.kind == CONTACT_ENGAGEMENT_CHANGED:
        # Decision 3's two wordings, taken from `docs/concept/
        # STATE_TRANSITIONS.md`'s own "danger <unit> <where>"/"safe from
        # <unit> <where>" rather than invented. `lead` already carries its
        # own trailing punctuation/spacing, per `_contact_report_text`'s
        # own docstring.
        if event.engaged is None:
            return None
        lead = "Danger, " if event.engaged else "Safe from "
        return _contact_report_text(result["facts"], lead=lead)
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
