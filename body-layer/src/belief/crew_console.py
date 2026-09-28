"""`CrewConsole` -- the typed-input/printed-output crew session (`plans/
bl5a-text-mode-crew-interaction/plan.md` Stage 4), simulating the player-
facing text channel a real SRS transport will eventually replace (PB-7/PB-8).

**Deliberately not an extension of `belief.console.Console`.** That module's
own docstring is explicit that it is a developer debug tool -- one command
maps to one `belief.tools` call, terse and tool-shaped, not conversational.
`CrewConsole` is the opposite kind of surface: it runs typed sentences
through `belief.utterance.parse_utterance`'s grammar instead of fixed verbs,
and it speaks *proactively* (`drain_events`) in a way the debug console never
does. See the plan's "Module boundary" decision for the full argument.
Both `--console` and `--crew-text` stay available on `logger.py` side by
side (mutually exclusive with each other this milestone, per the plan's
resolved decision).

**Dispatch.** `handle_line` sends one typed line through `parse_utterance`.
A `"handled"` disposition acts directly (`belief.tools.set_attention` or
`belief.tools.describe_contact`) and speaks a body-written template
(`belief.speech.render_readback`/`render_contact_report`) -- no brain call.
Anything else (`"escalated"`) is handed to `belief.escalation.
handle_player_utterance`, which this milestone's stand-in `BrainClient`s
never turn into spoken output (see `escalation.py`'s module docstring) --
consistent with §3.5's "if the brain does nothing, body says nothing."

**`drain_events`.** Called from the same poll-loop hook point BL-2.5's
`--overlay` already uses (after each `ContactStore.tick()`), it delegates
to `self.scheduler.tick` (`belief.callouts.CalloutScheduler`, `plans/
callout-scheduling/plan.md`) rather than rendering every currently-
unacknowledged event itself. The scheduler picks **at most one** thing to
say per call -- re-rendered from current belief the instant it is chosen,
never pre-rendered ahead of time -- which is the fix for the "callouts
backlogged" sortie finding: nothing is ever spoken later than the moment it
was decided true. See `belief.callouts`' own module docstring for the full
design (speech-time scheduling, sim-time occupancy, report-space
aggregation).

**`handle_command`.** `plans/f10-crew-commands/plan.md`'s second,
non-text input surface: `logger.py`'s `--crew-text --f10-commands` poll
loop drains player-selected DCS F10 radio-menu tokens
(`aircraft_client.get_f10_commands`) and dispatches each one here, through
the same `_print` funnel `handle_line`/`drain_events` already use --
`CrewConsole` has no separate "what F10 says" path to keep in sync with
what typed/spoken output produces.

**Watch is a cancellable standing mode, coexisting with scan.**
(`plans/watch-as-standing-mode/plan.md`, fixing a 2026-09-21 sortie finding:
`_handle_watch_nearest` used to call `belief.tools.set_attention` directly,
registering nothing "Cancel Task" could ever find -- "watch closest" then
"cancel task" reported "nothing to stop".) `_handle_watch_nearest` now also
registers a `belief.tasks.PendingIntent` of kind `"watch_contact"`
(`belief.tools.watch_contact_task`) when `self.tasks` is configured. A
`watch_contact` task has no success/timeout lifecycle -- unlike
`scan_area`, watching does not "succeed" or "time out" -- it just persists
until cancelled. It is independent of `scan_area`'s own task, so scan and
watch can be commanded and cancelled without either disturbing the other
(`logger._active_gaze` only ever reads `scan_area` tasks). Because one F10
"Cancel Task" item has no vocabulary to say *which* standing mode to end,
`_handle_cancel_task` cancels every currently-governing kind at once
(`_active_tasks_by_kind`) rather than guessing -- see that method's own
docstring for the full reasoning.

**`!inject-urgent <contact_id> <text...>`.** Stage 5's manual bypass_gate
proof (the plan's accepted decision: no real threat-detection channel
exists yet, so this is a clearly-labelled test harness, not a production
intent or a detector). Constructs a `belief.speech.UrgentCall` and routes it
through the same `route_event` gate the proactive path uses, demonstrating
ordering/pre-emption without pretending a real missile-launch/tracer
detector exists."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Final, TextIO

from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.attention import _SECTOR_CENTER_DEG, SECTORS, RelativeSector, Sector
from belief.audio_client import AudioAdapterClient, AudioAdapterError
from belief.brain_reply import validate_brain_reply
from belief.callouts import CalloutScheduler, group_facts, report_priority
from belief.classification import parent_class_of
from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext
from belief.escalation import (
    BrainClient,
    BrainReply,
    DebugPrintBrainClient,
    handle_player_utterance,
)
from belief.speech import (
    UrgentCall,
    _contact_report_text,
    render_cancel_readback,
    render_clear,
    render_confirm_request,
    render_contact_report,
    render_disambiguation,
    render_group_report,
    render_lost_contact,
    render_no_contact,
    render_no_view,
    render_readback,
    render_report,
    render_say_again,
    render_scan_readback,
    render_stand_by,
    render_unable,
    render_watch_nearest_readback,
    route_event,
)
from belief.tasks import PendingIntent, TaskKind, TaskStore
from belief.tools import (
    _find_contact,
    cancel_task,
    describe_contact,
    get_contacts,
    scan_area,
    set_attention,
    watch_contact_task,
)
from belief.utterance import (
    PartialParse,
    PlayerUtterance,
    ReferenceCandidate,
    parse_utterance,
)
from belief.voice_commands import (
    CONFIRM_LATE_ANSWER_GRACE_S,
    CONFIRM_WINDOW_S,
    BandDecision,
    PendingConfirmation,
    classify_response,
    classify_yes_no,
)
from perception.cockpit_mask import COCKPIT_MASKS, STATION_CO_PILOT
from perception.geometry import GeoPosition, angular_delta_deg

#: Spoken when "Cancel Task" finds nothing to cancel -- no task store wired
#: up, or no still-`pending` task. Deliberately not routed through
#: `speech.render_cancel_readback`: that template says "Copy, stopping",
#: which would claim an action that did not happen.
_NOTHING_TO_STOP: str = "nothing to stop"

#: Printed once at session startup (`logger.py`'s `main()`), mirroring
#: `belief.console.HELP_TEXT`'s role for the debug console.
HELP_TEXT = """\
Petrovich crew session -- type naturally, e.g.:
  watch <id or description>       have Petrovich keep an eye on a contact
  priority <id or description>    mark a contact the main threat
  ignore <id or description>      tell Petrovich to disregard a contact
  unwatch <id or description>     return a contact to normal attention
  where is <id or description>    ask where a contact was last seen
  status <id or description>      ask for a contact report

  !inject-urgent <id> <text>      test harness: force an urgent bypass_gate
                                   call (no real threat detector exists yet)
  !voice <token|-> <ratio> <confidence> <verb_anchored:0|1> <ambiguous:0|1> <text...>
                                   test harness: drive handle_transcript with
                                   an already-matched result, as if audio-adapter's
                                   command_matcher had produced it (Stage 3
                                   wires the real thing; no audio here)

Anything else is escalated (there is no brain to answer it yet).
"""

_UTTERANCE_ID_PREFIX = "UTTERANCE"

#: Prepended to the overlay-pushed copy of an urgent (`bypass_gate=True`)
#: line only -- see `CrewConsole._print`'s docstring and `plans/
#: overlay-speech-callouts/plan.md`'s resolved "Urgent-call visual
#: prominence" decision. `TextOverlaySender` has no color/bold mechanism,
#: so a plain text prefix is the only available distinction.
_URGENT_OVERLAY_PREFIX = "!! "

#: `scan_ahead`/`scan_left`/`scan_right`/`scan_full` -> `belief.attention.
#: RelativeSector` -- the ownship-relative half of the F10 scan vocabulary
#: (`plans/f10-command-vocabulary/plan.md` D1/D4). Also doubles as the
#: readback's spoken sector phrase.
_RELATIVE_SCAN_TOKENS: dict[str, RelativeSector] = {
    "scan_ahead": "ahead",
    "scan_left": "left",
    "scan_right": "right",
    "scan_full": "full",
}

#: Spoken phrasing for `_RELATIVE_SCAN_TOKENS`' sectors -- `render_scan_
#: readback`'s `sector_label` argument. `"full"` reads as "the full forward
#: arc" rather than the bare token, since "scanning full" alone reads oddly.
#: Articles dropped 2026-09-23 (user, from the five-fix sortie): "scanning
#: to the left" became "scanning left". Radio brevity is the register, not a
#: style preference -- an intercom is a channel one person occupies at a
#: time, and every article spends a slice of it carrying nothing.
_RELATIVE_SCAN_LABELS: dict[RelativeSector, str] = {
    "ahead": "ahead",
    "left": "left",
    "right": "right",
    "full": "full arc",
}

#: `scan_bearing_n`/... -> `belief.attention.Sector` -- the compass-absolute
#: half of the F10 scan vocabulary. Token suffixes match `Sector`'s own
#: literals lowercased, so this table is also how the token string is
#: parsed (no separate regex needed).
#: The `OP_*` buckets that count as air defence for the F10 "Watch ->
#: Nearest Air Defence" item, resolved via `belief.classification.
#: parent_class_of`. Exactly the air-defence entries in
#: `perception.object_model`'s profile table: the two gun systems
#: (`OP_SPAAG` Shilka, `OP_ZU23`) and the two SAM tiers (`OP_SRSAM` for
#: SA-3/8/9/13/15, `OP_MRSAM` for SA-6). Kept here rather than in
#: `object_model` because "which classes a *crew command* treats as air
#: defence" is a command-vocabulary question, not a property of the object
#: model -- a future `watch armour` would add its own set the same way.
#:
#: **`OP_LRSAM` was missing here until 2026-09-24**, so "watch nearest air
#: defence" silently could not select an S-300 -- the one emitter the vision
#: calibration found visible out to 8.89 km, i.e. the single contact this
#: command most needed to return. The omission was drift, not a decision:
#: this set was written when `object_model`'s profile table genuinely had no
#: long-range SAM entry, and the comment above ("exactly the air-defence
#: entries in `perception.object_model`") stayed true only until that table
#: gained one. A set enumerated by hand against another module's contents
#: has no mechanism to notice when that module grows.
_AIR_DEFENCE_OP_CLASSES: frozenset[str] = frozenset(
    {"OP_SPAAG", "OP_ZU23", "OP_SRSAM", "OP_MRSAM", "OP_LRSAM"}
)

#: The classification lattice levels at which an air-defence claim is
#: actually *known* rather than guessed -- `belief.classification.
#: SpecificityLevel`'s `CLASS` and `TYPE`, lowercased as
#: `tools._classification_facts` reports them.
_KNOWN_CLASS_LEVELS: frozenset[str] = frozenset({"class", "type"})

#: `_resolve_follow_target`'s descriptor -> `OP_*` class map (`plans/
#: watch-reporting/plan.md` Decision 2b-ii) -- `audio_adapter.vocabulary.
#: DESCRIPTOR_WORDS`'s hand-synced mirror on this side of the seam
#: (module independence -- body-layer cannot import `audio-adapter`).
#: `"sam"` maps to all three tiers deliberately: the descriptor vocabulary
#: is deliberately coarser than `speech._OP_CLASS_DISPLAY`'s three spoken
#: SAM words (Decision 4c's own finding that the `OP_SRSAM` bucket alone
#: spans a 4x range), since a pilot saying "follow SAM" has not yet
#: resolved which tier it is -- that is exactly what `follow` is for.
#: `"group"` is deliberately absent here -- it is not a classification
#: match at all, see `_descriptor_score`'s own `"group"` branch.
_FOLLOW_DESCRIPTOR_OP_CLASSES: dict[str, frozenset[str]] = {
    "armor": frozenset({"OP_ARMORED"}),
    "truck": frozenset({"OP_TRUCK"}),
    "infantry": frozenset({"OP_INFANTRY"}),
    "sam": frozenset({"OP_SRSAM", "OP_MRSAM", "OP_LRSAM"}),
    "aaa": frozenset({"OP_SPAAG", "OP_ZU23"}),
    "ship": frozenset({"OP_SHIP"}),
}

#: **Every weight and both thresholds below are guesses, uncalibrated in
#: the same way `callouts.SPEECH_RATE_WPS` is** (`plans/watch-reporting/
#: plan.md` Decision 2b-iii's own framing). `_resolve_follow_target` is a
#: stopgap for a brain-layer capability the user named explicitly -- when
#: free-text targeting arrives, delete the resolver and these constants
#: with it; do not tune them as if they modelled anything real.
W_FOLLOW_DESC_UNKNOWN: Final[float] = 1.0
W_FOLLOW_DESC_WRONG: Final[float] = 10.0
W_FOLLOW_CLOCK: Final[float] = 0.6
W_FOLLOW_RANGE: Final[float] = 0.3
#: Sized so a *maximal* single-qualifier miss can clear it on its own --
#: `W_FOLLOW_CLOCK`'s worst case (opposite clock, delta 6) is `3.6`, just
#: over this floor, so "follow two o'clock" against a contact sitting at
#: eight o'clock alone is refused rather than matched on a coin flip. A
#: `W_FOLLOW_DESC_WRONG` mismatch (10.0) always refuses alone, by a wide
#: margin -- deliberately, since a known-wrong class is a hard signal,
#: unlike an uncertain clock estimate (Decision 2b-iii's own "a pilot's
#: eyeball estimate of which hour it sits in is routinely an hour out").
FOLLOW_MATCH_FLOOR: Final[float] = 3.0
FOLLOW_SEPARATION: Final[float] = 0.5

#: `_parse_follow_slots_for_harness`'s own small word tables -- a
#: dev-aid-only mirror of `audio_adapter.vocabulary`'s real
#: `_CLOCK_WORDS`/`_RANGE_NUMBER_WORDS`/unit-word set, narrower and
#: unexported: this harness exists to tune `_resolve_follow_target`'s
#: weights without a redeploy, not to reproduce recognition-grade parsing.
_FOLLOW_HARNESS_CLOCK_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
_FOLLOW_HARNESS_RANGE_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_FOLLOW_HARNESS_RANGE_UNIT_WORDS: frozenset[str] = frozenset(
    {"km", "kilometre", "kilometres", "kilometer", "kilometers", "klick", "klicks"}
)


_BEARING_SCAN_TOKENS: dict[str, Sector] = {
    "scan_bearing_n": "N",
    "scan_bearing_ne": "NE",
    "scan_bearing_e": "E",
    "scan_bearing_se": "SE",
    "scan_bearing_s": "S",
    "scan_bearing_sw": "SW",
    "scan_bearing_w": "W",
    "scan_bearing_nw": "NW",
}

#: Spoken phrasing for `_BEARING_SCAN_TOKENS`' sectors -- full compass words,
#: not the two/three-letter literal, matching `_RELATIVE_SCAN_LABELS`'
#: register.
_SECTOR_SCAN_LABELS: dict[Sector, str] = {
    "N": "north",
    "NE": "northeast",
    "E": "east",
    "SE": "southeast",
    "S": "south",
    "SW": "southwest",
    "W": "west",
    "NW": "northwest",
}

#: Every F10 scan command's fixed `belief.tools.scan_area` reason (Stage 6)
#: -- an F10 button supplies no free-text justification the way a typed
#: `scan-area` command's trailing `reason` argument does.
_SCAN_COMMAND_REASON = "F10 scan command"

#: `report_clock_<p>` -> the ownship-relative hour, for `handle_command`'s
#: dispatch and `_describe_token_for_confirm`'s fallback description
#: (`plans/voice-command-completeness/plan.md` Stage 2). The nine forward
#: hours `audio-adapter/src/vocabulary.py`'s `FORWARD_CLOCK_POSITIONS`
#: recognises -- deliberately not all twelve, for the same reason that
#: table gives: Petrovich cannot see behind the aircraft, so a report about
#: an hour he has no honest answer for is not worth wiring (the clock
#: family is safe by construction, see `_handle_report`'s own docstring).
_CLOCK_REPORT_TOKENS: dict[str, int] = {
    f"report_clock_{p}": p for p in (8, 9, 10, 11, 12, 1, 2, 3, 4)
}

#: Spoken number words for `_CLOCK_REPORT_TOKENS`' hours -- lowercase,
#: mirroring `_SECTOR_SCAN_LABELS`' register; `render_clear`/
#: `_describe_token_for_confirm` capitalize where the word is
#: sentence-initial, this table only supplies the bare word.
_CLOCK_REPORT_LABELS: dict[int, str] = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
}

#: `scan_clock_<p>` -> the ownship-relative hour to scan (Stage 5,
#: `plans/voice-command-completeness/plan.md` Decision 5) --
#: `_CLOCK_REPORT_TOKENS`'s direct sibling for the `scan` verb rather than
#: `report`, same nine forward hours for the same no-omniscience reason
#: (Petrovich cannot see behind the aircraft, so scanning an hour he has
#: no honest answer for is not worth wiring). This is the fine-grained
#: ownship-relative vocabulary `_RELATIVE_SCAN_TOKENS` lacks: `left` spans
#: three o'clock hours (11, 10, 9), and there was previously no way to say
#: "just there" relative to the nose.
_CLOCK_SCAN_TOKENS: dict[str, int] = {
    f"scan_clock_{p}": p for p in (8, 9, 10, 11, 12, 1, 2, 3, 4)
}

#: `report_bearing_<compass>` -> `belief.attention.Sector` -- the
#: compass-absolute half of the report vocabulary, `_BEARING_SCAN_TOKENS`'
#: direct sibling for the `report` verb rather than `scan`.
_BEARING_REPORT_TOKENS: dict[str, Sector] = {
    "report_bearing_n": "N",
    "report_bearing_ne": "NE",
    "report_bearing_e": "E",
    "report_bearing_se": "SE",
    "report_bearing_s": "S",
    "report_bearing_sw": "SW",
    "report_bearing_w": "W",
    "report_bearing_nw": "NW",
}

#: At most this many groups are spoken in one report, joined into one
#: utterance (`plans/voice-command-completeness/plan.md` Decision 1b) --
#: an uncalibrated placeholder pending a live sortie's judgment on whether
#: three groups is useful or too long to sit through (that plan's
#: "Decisions Requiring User Input" item 3), isolated here so retuning it
#: never touches `_handle_report`'s own logic.
REPORT_MAX_GROUPS: Final[int] = 3


def _clock_delta(a: int, b: int) -> int:
    """Circular distance between two 1-12 clock positions, e.g.
    `_clock_delta(12, 1) == 1`, `_clock_delta(3, 9) == 6` --
    `belief.callouts._clock_diff`'s twin (that one is module-private to
    `callouts.py`), used by `_resolve_follow_target`'s clock scoring
    term."""
    diff = abs(a - b) % 12
    return min(diff, 12 - diff)


def _nearest_sector(degrees: int) -> Sector:
    """Quantises an absolute bearing onto the nearest of the eight
    compass `Sector`s (`plans/voice-command-completeness/plan.md` Decision
    3) -- `scan_bearing_deg(320)` reduces to `scan_bearing_nw`,
    `report_bearing_deg(5)` reduces to `report_bearing_n`. Per the user's
    2026-09-23 direction ("o'clock direction is enough, no need for x
    degrees granularity now"), the numeric bearing tokens act on exactly
    the same eight buckets `scan_bearing_*`/`report_bearing_*` already do
    -- no new geometry, no `AttentionArea.wedge_deg` use. `degrees` is
    assumed already a legal, 5-degree-multiple bearing (`audio_adapter.
    vocabulary.parse_bearing`'s own checksum already rejected anything
    else upstream of this call)."""
    return min(
        SECTORS,
        key=lambda sector: angular_delta_deg(
            float(degrees), _SECTOR_CENTER_DEG[sector]
        ),
    )


#: Plain human phrase per non-scan legacy token, for `_describe_token_for_
#: confirm`'s fallback table -- `render_confirm_request`'s `description`
#: argument (`"watch nearest, confirm?"`). Scan tokens instead reuse
#: `_RELATIVE_SCAN_LABELS`/`_SECTOR_SCAN_LABELS` directly (see that
#: function), since those already carry the exact spoken sector phrase.
_TOKEN_DESCRIPTIONS: dict[str, str] = {
    "watch_nearest": "watch nearest",
    "watch_nearest_air_defence": "watch nearest air defence",
    "cancel_task": "cancel everything",
    "cancel_scan": "stop scan",
    "cancel_watch": "stop watch",
    "report_all": "report",
}


def _describe_token_for_confirm(
    token: str, slots: dict[str, int | str] | None = None
) -> str:
    """A plain human phrase for `token`, for `belief.speech.
    render_confirm_request`'s `description` argument (Stage 2,
    `plans/inbound-speech/plan.md`, extended by `plans/
    voice-command-completeness/plan.md` Stage 2/3). Reuses `handle_command`'s
    own token->label tables (`_describe_task_for_speech`'s sibling, same
    "one table, two readers" idea) for every token this module now
    dispatches; anything outside that set falls back to the token name
    with underscores turned to spaces, which is honest rather than
    polished: there is no dispatch behind it yet for the confirm to be
    about.

    **`report_bearing_deg`/`scan_bearing_deg` say the quantised sector, not
    the number** (Decision 3 item 5: `"scan northwest, confirm?"`, never
    `"scan bearing 317, confirm?"`) -- the confirm prompt's job is to
    expose a misunderstanding, and repeating the raw number while the
    dispatch itself acts on a coarser bucket would hide the only
    discrepancy worth hearing, the same reasoning `render_scan_readback`'s
    own call site already follows. `slots["bearing_degrees"]` is only
    consulted for those two tokens; every other token ignores it."""
    if token in _RELATIVE_SCAN_TOKENS:
        return f"scan {_RELATIVE_SCAN_LABELS[_RELATIVE_SCAN_TOKENS[token]]}"
    if token in _BEARING_SCAN_TOKENS:
        return f"scan {_SECTOR_SCAN_LABELS[_BEARING_SCAN_TOKENS[token]]}"
    if token in _BEARING_REPORT_TOKENS:
        return f"report {_SECTOR_SCAN_LABELS[_BEARING_REPORT_TOKENS[token]]}"
    if token in _CLOCK_REPORT_TOKENS:
        clock = _CLOCK_REPORT_TOKENS[token]
        return f"report {_CLOCK_REPORT_LABELS[clock]} o'clock"
    if token in _CLOCK_SCAN_TOKENS:
        clock = _CLOCK_SCAN_TOKENS[token]
        return f"scan {_CLOCK_REPORT_LABELS[clock]} o'clock"
    if token == "follow":
        parts: list[str] = []
        follow_descriptor = slots.get("descriptor") if slots is not None else None
        follow_clock = slots.get("clock") if slots is not None else None
        follow_range_km = slots.get("range_km") if slots is not None else None
        if isinstance(follow_descriptor, str):
            parts.append(follow_descriptor)
        if isinstance(follow_clock, int):
            parts.append(f"{_CLOCK_REPORT_LABELS[follow_clock]} o'clock")
        if isinstance(follow_range_km, int):
            parts.append(f"{follow_range_km} km")
        return f"follow {' '.join(parts)}" if parts else "follow"
    bearing_degrees = slots.get("bearing_degrees") if slots is not None else None
    if token in ("scan_bearing_deg", "report_bearing_deg") and isinstance(
        bearing_degrees, int
    ):
        sector = _nearest_sector(bearing_degrees)
        verb = "scan" if token == "scan_bearing_deg" else "report"
        return f"{verb} {_SECTOR_SCAN_LABELS[sector]}"
    return _TOKEN_DESCRIPTIONS.get(token, token.replace("_", " "))


#: The canonical "what has real dispatch behaviour in `handle_command`" set
#: (`plans/voice-command-completeness/plan.md` Stage 1) -- every token this
#: method actually branches on, `stop_talking` included (a documented,
#: deliberate no-readback no-op, not a gap). Excludes `wake_petrovich`/
#: `cancel_nevermind`/`say_again` (handled above `handle_command` entirely,
#: per the module docstring -- this method never even sees those three
#: tokens) and `scan_bearing_deg`/`report_bearing_deg` are included even
#: though a missing `slots["bearing_degrees"]` degrades them to a "say
#: again" line rather than raising, matching every other graceful-
#: degradation branch in this class. `test_crew_console.py` asserts every
#: member of this set returns a non-empty result from `handle_command`.
DISPATCHED_COMMAND_TOKENS: frozenset[str] = frozenset(
    set(_RELATIVE_SCAN_TOKENS)
    | set(_BEARING_SCAN_TOKENS)
    | set(_CLOCK_REPORT_TOKENS)
    | set(_CLOCK_SCAN_TOKENS)
    | set(_BEARING_REPORT_TOKENS)
    | {
        "scan_bearing_deg",
        "report_bearing_deg",
        "report_all",
        "watch_nearest",
        "watch_nearest_air_defence",
        "follow",
        "cancel_task",
        "cancel_scan",
        "cancel_watch",
        "stop_talking",
    }
)


def _active_tasks_by_kind(tasks: list[PendingIntent]) -> list[PendingIntent]:
    """The single most-recently-created non-`"cancelled"` task per `kind`
    (`plans/watch-as-standing-mode/plan.md`) -- generalises `logger.
    _active_gaze`'s own "most recent wins" selection (there, scoped to
    `scan_area` alone for gaze purposes) to any kind, for `_handle_
    cancel_task`'s "what is currently governing" question. `tasks` is
    already insertion order (`TaskStore.tasks`'s own docstring), so a plain
    left-to-right overwrite into a per-kind dict leaves each kind's
    *latest* active task as the final value -- an older, superseded task of
    the same kind (e.g. a since-replaced `scan_area` command) is real
    history but not currently active by this definition, even though its
    own `status` may still read `"pending"`/`"succeeded"` rather than
    `"cancelled"`."""
    latest_by_kind: dict[TaskKind, PendingIntent] = {}
    for task in tasks:
        if task.status == "cancelled":
            continue
        latest_by_kind[task.kind] = task
    return list(latest_by_kind.values())


def _join_task_descriptions(descriptions: list[str]) -> str | None:
    """Joins `_describe_task_for_speech`'s per-task phrases into one
    readback subject for `_handle_cancel_task` -- `None` when there is
    nothing to name, the phrase itself when there is exactly one, or an
    `"and"`-joined list when several kinds were cancelled at once
    (`"the scan ahead and the watch"`). Kept deliberately plain (no
    Oxford comma logic, no more than the two kinds this milestone has) --
    a fancier list formatter is not worth building for a set that can only
    ever hold two items today."""
    if not descriptions:
        return None
    if len(descriptions) == 1:
        return descriptions[0]
    return " and ".join(descriptions)


logger = logging.getLogger(__name__)


#: `plans/brain-layer/plan.md` D8 -- how long an outstanding escalation
#: waits for a brain reply before Petrovich speaks "stand by" once, purely
#: deterministically (no model involvement). **Unmeasured**, same debt
#: class as `CONFIRM_WINDOW_S`/`DEFAULT_SCAN_DEADLINE_S` before it -- a
#: round guess at human patience, pending Stage 4's live-sortie tuning.
STAND_BY_AFTER_S: Final[float] = 2.0

#: `plans/brain-layer/plan.md` D4 -- a brain reply older than this (by
#: `EscalationPayload.t_sim`, carried back unchanged on `BrainReply.
#: t_sim`) is discarded silently rather than acted on or spoken, since the
#: game world has moved on in the time the brain took to answer.
#: **Unmeasured**, same debt class as `STAND_BY_AFTER_S` above.
BRAIN_REPLY_MAX_AGE_S: Final[float] = 20.0


@dataclass
class CrewConsole:
    """Holds the `ContactStore` every command reads/mutates through
    `belief.tools`/`belief.speech`, and the `BrainClient` escalations go to.
    `handle_line`/`drain_events` return the lines they spoke (mirroring
    `belief.console.Console.handle_line`'s return-what-was-produced shape)
    so tests can assert on output without capturing stdout."""

    store: ContactStore
    brain_client: BrainClient = field(default_factory=DebugPrintBrainClient)
    output: TextIO | None = None
    #: Mirrors `belief.console.Console.enrichment` -- `None` (the default)
    #: leaves every command's output byte-for-byte the no-enrichment shape,
    #: same guard as `belief.tools`'/`belief.console`'s own `enrichment`.
    enrichment: EnrichmentContext | None = None
    #: BL-6's `Console.aircraft_client` equivalent (`plans/
    #: bl6-commands-inspect-adapt/plan.md`), wired by `logger.py`'s
    #: `main()` in the `--crew-text` branch for parity with `--console`'s
    #: own wiring. Read by `_handle_scan` (`plans/f10-command-vocabulary/
    #: plan.md` Stage 6) to fire the live `trigger_petrovich_search` call
    #: after a scan's `PendingIntent` is registered -- `None` (the default)
    #: means a scan still registers belief-state, it just never fires a
    #: live search.
    aircraft_client: AircraftLayerClient | None = None
    #: BL-6's `belief.tasks.TaskStore` (`plans/f10-crew-commands/plan.md`,
    #: mirroring `aircraft_client`'s own reserved-field pattern above) --
    #: `_handle_scan`'s registration call and `_handle_cancel_task` are
    #: this field's readers. `logger.py`'s `--crew-text` branch wires this
    #: to the same `ConsolePerceptionRunner.tasks` instance its poll loop
    #: already ticks (`TaskStore.tick`), the same store `--console`'s
    #: `Console.tasks` reads/mutates. `None` (the default) means every
    #: `scan_*` token reports "no task store configured" and "Cancel Task"
    #: always reports "no pending task", rather than raising.
    tasks: TaskStore | None = None
    #: How many player commands this console has dispatched, F10 or spoken
    #: -- typed free text and voice's `"fallthrough"` disposition alike
    #: (`plans/binocular-optic/plan.md` D4: "not a special case per
    #: command"). Incremented from the two surface-level entry points that
    #: are each reached regardless of *how* the player phrased the request
    #: -- `handle_command`'s own top (token dispatch) and
    #: `_handle_utterance`'s top (every free-text utterance, typed or
    #: fallen-through from voice) -- never per-intent inside either one. A
    #: counter rather than a flag or a callback: the poll loop compares it
    #: across one iteration to learn "did the player ask for anything just
    #: now", which stays true for a command surface added later without
    #: this class knowing what the answer is used for. It is deliberately
    #: not reset -- a monotonic count is what makes the comparison safe
    #: across any number of commands in one poll.
    commands_handled: int = 0
    #: `plans/sortie-2026-09-26-fixes/decisions.md` Decision 2's `follow
    #: <target>` continuation: the contact id `_handle_follow` most recently
    #: resolved its target to. Reset to `None` at the top of every
    #: `handle_command` dispatch (the only surface `_handle_follow` is
    #: reachable from) so a stale value from an earlier `follow` can never
    #: leak into an unrelated later command's evaluation. `logger.py`'s
    #: "any command lowers binoculars" glue block reads this alongside
    #: `OpticState.look_contact_id` to decide whether the just-dispatched
    #: `follow` named the contact already being glassed -- if so, the look
    #: continues rather than being lowered and immediately re-pointed at
    #: the same target.
    last_command_target_contact_id: str | None = None
    #: Optional sink for every recognised transcript and what was done
    #: about it (`--speech-log`). Same optional-collaborator shape as
    #: `overlay_client`/`speech_client`: `None` is a true no-op.
    #:
    #: **It exists because an unmatched utterance was previously
    #: unobservable.** A transcript that matched no command fell through to
    #: escalation, and the default brain client does nothing at all -- so
    #: the most interesting case for debugging recognition, "what did he
    #: hear that he could not act on", left no trace anywhere. Matched ones
    #: are logged too: false fires are only findable by seeing what he
    #: *did* act on.
    transcript_log: Callable[[dict[str, object]], None] | None = None
    #: In-cockpit text overlay mirror (`plans/overlay-speech-callouts/
    #: plan.md`), mirroring `logger.ConsolePerceptionRunner.overlay_client`'s
    #: None-means-no-op pattern exactly. **Deliberately a separate field
    #: from `aircraft_client` above** -- that field is reserved for a
    #: different purpose (live search-trigger commands, per its own
    #: docstring) and has no reader today; this one is read by `_print`
    #: every time `CrewConsole` produces spoken text. `logger.py`'s
    #: `--crew-text` branch wires this to the same `AircraftLayerClient`
    #: instance already used for telemetry when `--overlay` is passed, no
    #: separate URL/flag needed, matching `--console --overlay`'s own
    #: wiring.
    overlay_client: AircraftLayerClient | None = None
    #: Spoken-audio sink (BL-10 first slice, `plans/tts-voice-output/
    #: plan.md`), mirroring `overlay_client`'s None-means-no-op pattern
    #: exactly -- a third, separate optional field read by `_print`
    #: alongside `overlay_client` every time `CrewConsole` produces spoken
    #: text. `bypass_gate` (already computed for the overlay `"!! "`
    #: prefix) is threaded straight through as `push_speech`'s `urgent`
    #: argument -- no new signal invented, matching the plan's Decision 3.
    #: `logger.py`'s `--crew-text --speech-audio` branch wires this to a
    #: `belief.audio_client.AudioAdapterClient` built from `--audio-adapter-url`,
    #: independent of `--overlay`'s own `AircraftLayerClient` wiring (a
    #: different process, a different URL).
    speech_client: AudioAdapterClient | None = None

    #: Optional callback invoked for every line this console speaks, with
    #: `(line, urgent)` -- `logger` wires it to `belief_truth_log.
    #: BeliefTruthLogWriter.write_speech` so what Petrovich says lands on
    #: the same timeline as the belief-versus-truth rows (user,
    #: 2026-09-25: "then all the information would be in one log file").
    #:
    #: **A callback rather than the writer itself, deliberately.** This
    #: module lives in `belief/` and `belief_truth_log` imports *from*
    #: `belief/` -- holding the writer here would close that loop. The
    #: callback keeps the dependency pointing one way, and matches the
    #: optional-sink shape `output`/`overlay_client`/`speech_client`
    #: already use. `logger` supplies a closure that can read the current
    #: gaze and optic at call time, which is the part that makes these
    #: rows answer "what was he looking at when he said that".
    speech_log_sink: Callable[[str, bool], None] | None = None
    #: `plans/callout-scheduling/plan.md` -- the speech-time scheduler
    #: `drain_events` delegates to. One scheduler per `CrewConsole`
    #: (per-session occupancy state), mirroring every other optional-sink
    #: field above in spirit though it is never `None`: unlike
    #: `overlay_client`/`speech_client`, scheduling applies to *every*
    #: sink (the plan's Decision 1 -- "One crew voice, one channel"), so
    #: there is no no-op state for this field to have.
    scheduler: CalloutScheduler = field(default_factory=CalloutScheduler)
    _next_utterance_number: int = field(default=0, repr=False)
    #: Stage 2 of `plans/inbound-speech/plan.md`'s confirm-band state --
    #: set by `handle_transcript` when a matched command lands in the
    #: confirm band (or is ambiguous), cleared on the next call once it is
    #: answered, discarded, or expired (`CONFIRM_WINDOW_S`). `None` means
    #: no question is currently open.
    _pending_confirmation: PendingConfirmation | None = field(default=None, repr=False)
    #: `now_sim` at which the last confirm question stopped being
    #: answerable -- set when one expires, so a yes/no word arriving just
    #: after the window can still be recognised as a *late answer* rather
    #: than escalated to the brain layer as free speech (see
    #: `CONFIRM_LATE_ANSWER_GRACE_S`, and `handle_transcript`'s own
    #: docstring for why that escalation was the defect the pilot heard).
    #: `None` means no question has ever expired on this console.
    _confirmation_expired_sim: float | None = field(default=None, repr=False)
    #: `plans/brain-layer/plan.md` -- every escalation currently awaiting a
    #: brain reply, keyed by `utterance_id`: `(t_sim it was escalated at,
    #: the belief.utterance.PartialParse that was escalated, the original
    #: transcript)`. `_handle_brain_reply` pops its entry once a reply
    #: lands (or is aged out); `_speak_stand_by_if_due` reads it every
    #: poll to decide whether D8's "stand by" is due. **The transcript is
    #: Stage 2's own addition** -- D10's validator (`belief.brain_reply`)
    #: needs the pilot's own original words to check a `PICK ... BECAUSE
    #: <words>` reply's quote is genuine, and nothing else on this class
    #: already keeps it once escalation has posted. `brain-layer` itself
    #: only ever holds one job in flight (D3), but body-side this stays a
    #: dict rather than a single optional slot -- a reply can arrive for
    #: an id no longer of interest (raced by a newer escalation
    #: client-side, `belief.brain_client.BrainLayerClient`'s own
    #: newest-wins slot), and `.pop` on a dict degrades to `None` cleanly
    #: rather than needing a separate "does this match what I'm tracking"
    #: branch.
    _pending_escalations: dict[str, tuple[float, PartialParse, str]] = field(
        default_factory=dict, repr=False
    )
    #: Which `_pending_escalations` keys D8's "stand by" has already been
    #: spoken for -- so it fires **once** per question, not once per poll
    #: while the question remains outstanding.
    _stand_by_spoken_for: set[str] = field(default_factory=set, repr=False)

    def handle_line(self, line: str, now_sim: float) -> list[str]:
        stripped = line.strip()
        if not stripped:
            return []
        if stripped.startswith("!inject-urgent"):
            lines, bypass_gate = self._handle_inject_urgent(stripped, now_sim)
            self._print(lines, now_sim, bypass_gate=bypass_gate)
            return lines
        if stripped.startswith("!voice"):
            return self._handle_voice_test_command(stripped, now_sim)
        lines = self._handle_utterance(stripped, now_sim)
        self._print(lines, now_sim, bypass_gate=False)
        return lines

    def drain_events(self, now_sim: float) -> list[str]:
        """Speak at most one currently-unacknowledged event, chosen and
        rendered fresh from current belief by `self.scheduler.tick`
        (`belief.callouts.CalloutScheduler`, see that module's docstring
        and `_print`'s docstring). Called once per poll from `logger.py`'s
        `--crew-text` loop, after `ContactStore.tick()`."""
        spoken = self.scheduler.tick(self.store, now_sim, self.enrichment)
        # A scheduler-drained line never carries `bypass_gate=True` (only an
        # injected `UrgentCall`, routed through `handle_line`'s
        # `!inject-urgent` branch, does) -- see `_print`'s docstring.
        self._print(spoken, now_sim, bypass_gate=False)
        return spoken

    def drain_brain(self, now_sim: float) -> list[str]:
        """`plans/brain-layer/plan.md` -- drains `self.brain_client.
        poll_replies()`, revalidates each reply against *current* belief
        (D4) and speaks the result, and, first, speaks D8's deterministic
        "stand by" for any escalation that has been outstanding too long.
        Called once per poll from `logger.py`'s `--crew-text` loop,
        alongside `drain_events`/`_poll_f10_commands`/`_poll_transcripts`
        -- the established pattern for pulling asynchronous input into
        this loop without ever blocking it (`belief.brain_client.
        BrainLayerClient.handle`'s own docstring is where the
        never-blocks guarantee actually lives; this method is a plain
        synchronous poll, like the other three)."""
        self._speak_stand_by_if_due(now_sim)
        try:
            replies = self.brain_client.poll_replies()
        except Exception:
            # division: a poll failure here degrades to log-and-continue,
            # the same per-call isolation `_poll_f10_commands`/
            # `_poll_transcripts` (logger.py) already give their own
            # clients, applied here to the one client owned by this class
            # instead of by the poll-loop function.
            logger.warning("brain reply poll failed (continuing)", exc_info=True)
            return []
        lines: list[str] = []
        for reply in replies:
            lines.extend(self._handle_brain_reply(reply, now_sim))
        return lines

    def _speak_stand_by_if_due(self, now_sim: float) -> None:
        """D8: speak "stand by" **once** for any escalation that has been
        outstanding for at least `STAND_BY_AFTER_S` and has not already
        had it spoken. No model involvement -- body already knows how
        long it has been waiting."""
        for utterance_id, (
            started_sim,
            _parse,
            _transcript,
        ) in self._pending_escalations.items():
            if utterance_id in self._stand_by_spoken_for:
                continue
            if now_sim - started_sim >= STAND_BY_AFTER_S:
                self._stand_by_spoken_for.add(utterance_id)
                self._print([render_stand_by().text], now_sim)

    def _handle_brain_reply(self, reply: BrainReply, now_sim: float) -> list[str]:
        """D4's revalidation table, in full -- plus D10's validator
        (`belief.brain_reply.validate_brain_reply`), run first: a reply
        this class did not itself ask for a valid answer to (a `PICK` of
        an unoffered id, an ungrounded `BECAUSE` quote, an unknown
        `CONFIRM` token, an unrecognised `UNABLE` reason) is degraded to
        `ASK`/`UNABLE NO_MATCH` *before* any of D4's own table applies --
        D4 revalidates a reply against *current* belief, D10 validates
        that it was ever a legal reply at all; the two are independent
        checks in sequence, not alternatives.

        `pending` is popped unconditionally -- whether or not the reply
        turns out to be actionable, this utterance is no longer
        outstanding once a reply for it has landed."""
        pending = self._pending_escalations.pop(reply.utterance_id, None)
        self._stand_by_spoken_for.discard(reply.utterance_id)
        if pending is None:
            # A reply for an utterance this session is no longer
            # tracking -- superseded client-side, or a duplicate poll.
            # Nothing to revalidate against; discard silently, same
            # honest-silence posture `NullBrainClient` already documents.
            return []
        _started_sim, parse, transcript = pending
        reply = validate_brain_reply(
            reply, parse, transcript, DISPATCHED_COMMAND_TOKENS
        )

        if reply.t_sim is not None and now_sim - reply.t_sim > BRAIN_REPLY_MAX_AGE_S:
            logger.info(
                "discarding stale brain reply for %s (age %.1fs)",
                reply.utterance_id,
                now_sim - reply.t_sim,
            )
            return []

        if reply.kind == "unable":
            lines = [render_unable(reply.reason or "").text]
        elif reply.kind == "confirm":
            lines = self._handle_brain_confirm(reply, now_sim)
        elif reply.kind == "pick":
            lines = self._handle_brain_pick(reply, parse, now_sim)
        else:  # "ask"
            lines = self._handle_brain_ask(parse, now_sim)

        self._print(lines, now_sim)
        return lines

    def _handle_brain_confirm(self, reply: BrainReply, now_sim: float) -> list[str]:
        """D9: a `CONFIRM <token>` reply sets `_pending_confirmation`,
        reusing the exact mechanism the voice confirm-band already built
        -- "there is not a second confirm mechanism." D10's membership
        check (`token` must be in `DISPATCHED_COMMAND_TOKENS`) is now
        `belief.brain_reply.validate_brain_reply`'s job, run by
        `_handle_brain_reply` before this method is ever called -- a
        `reply.kind` that reaches here as `"confirm"` has already had its
        token validated. The inline check below is kept as a second,
        cheap line of defence rather than removed, in case a future
        caller ever reaches this method without going through the
        validator first."""
        token = reply.token
        if token is None or token not in DISPATCHED_COMMAND_TOKENS:
            return [render_unable("NO_SUCH_COMMAND").text]
        description = _describe_token_for_confirm(token)
        self._pending_confirmation = PendingConfirmation(
            token=token, description=description, pending_since_sim=now_sim
        )
        return [render_confirm_request(description).text]

    def _handle_brain_pick(
        self, reply: BrainReply, parse: PartialParse, now_sim: float
    ) -> list[str]:
        """D4: `PICK <id>`, contact still present -> act and read back as
        today; contact gone -> "lost him"."""
        contact_id = reply.contact_id
        if contact_id is None or _find_contact(self.store, contact_id) is None:
            return [render_lost_contact().text]
        return self._act(replace(parse, referenced_contact_id=contact_id), now_sim)

    def _handle_brain_ask(self, parse: PartialParse, now_sim: float) -> list[str]:
        """D4: `ASK` revalidates against *current* survivors among the
        candidates originally offered (`parse.
        referenced_contact_candidates`), not whatever the reply itself
        might claim -- the reply's whole point is "ask the pilot," it
        carries no new candidate list of its own. >=2 survivors -> ask,
        using them; exactly 1 -> confirm it rather than acting (see
        `PendingConfirmation.contact_pick`'s own docstring for why); 0 ->
        "lost him"."""
        survivors: list[ReferenceCandidate] = [
            candidate
            for candidate in parse.referenced_contact_candidates
            if _find_contact(self.store, candidate.id) is not None
        ]
        if len(survivors) >= 2:
            return [render_disambiguation(survivors).text]
        if len(survivors) == 1:
            candidate = survivors[0]
            description = candidate.why
            self._pending_confirmation = PendingConfirmation(
                token=None,
                description=description,
                pending_since_sim=now_sim,
                contact_pick=(candidate.id, parse),
            )
            return [render_confirm_request(description).text]
        return [render_lost_contact().text]

    def _note_player_command(self) -> None:
        """Record that the player asked for something. See
        `commands_handled`."""
        self.commands_handled += 1

    def handle_command(
        self,
        token: str,
        now_sim: float,
        slots: dict[str, int | str] | None = None,
    ) -> list[str]:
        """Dispatches one player-issued command token -- originally F10
        radio-menu selections only (`plans/f10-crew-commands/plan.md`),
        this is now the single dispatcher for every input surface that
        resolves to a token: `logger.py`'s `--crew-text --f10-commands`
        poll loop (`aircraft_client.get_f10_commands`), a voice `"act"`
        disposition (`_act_on_voice_decision`), and a committed confirm-band
        answer (`handle_transcript`). Renamed from `handle_f10_command`
        (`plans/voice-command-completeness/plan.md` Stage 1, Decision 4) --
        the F10 radio menu is the transport being retired, not the concept
        this method dispatches, which voice already shared with it.

        **`DISPATCHED_COMMAND_TOKENS`** (module-level, below) is the
        canonical "what has real behaviour here" set -- `test_crew_console.
        py` asserts every member either returns a non-empty result or is a
        documented no-op (`stop_talking`). `wake_petrovich`/
        `cancel_nevermind`/`say_again` are never passed to this method at
        all (handled above it, per the module docstring); an unrecognized
        token (including a genuinely unknown one) is now **logged**, not
        silently swallowed -- the failure mode this milestone exists to fix
        was silence: a recognised token reaching this method and doing
        nothing was indistinguishable, from the cockpit, from not having
        been heard at all."""
        self._note_player_command()
        # Reset before dispatch -- see `last_command_target_contact_id`'s
        # own docstring for why a stale value from an earlier `follow`
        # must not leak into this command's evaluation.
        self.last_command_target_contact_id = None
        bearing_degrees = slots.get("bearing_degrees") if slots is not None else None
        if not isinstance(bearing_degrees, int):
            bearing_degrees = None
        if token in _RELATIVE_SCAN_TOKENS:
            relative_sector = _RELATIVE_SCAN_TOKENS[token]
            lines = self._handle_scan(
                now_sim,
                relative_sector=relative_sector,
                sector_label=_RELATIVE_SCAN_LABELS[relative_sector],
            )
        elif token in _BEARING_SCAN_TOKENS:
            sector = _BEARING_SCAN_TOKENS[token]
            lines = self._handle_scan(
                now_sim, sector=sector, sector_label=_SECTOR_SCAN_LABELS[sector]
            )
        elif token == "scan_bearing_deg":
            if bearing_degrees is None:
                lines = ["say again -- no bearing heard"]
            else:
                sector = _nearest_sector(bearing_degrees)
                lines = self._handle_scan(
                    now_sim, sector=sector, sector_label=_SECTOR_SCAN_LABELS[sector]
                )
        elif token in _CLOCK_SCAN_TOKENS:
            clock = _CLOCK_SCAN_TOKENS[token]
            lines = self._handle_scan(
                now_sim,
                relative_clock_hour=clock,
                sector_label=f"{_CLOCK_REPORT_LABELS[clock]} o'clock",
            )
        elif token == "watch_nearest":
            lines = self._handle_watch_nearest(now_sim)
        elif token == "watch_nearest_air_defence":
            lines = self._handle_watch_nearest(now_sim, air_defence_only=True)
        elif token == "follow":
            lines = self._handle_follow(now_sim, slots)
        elif token == "cancel_task":
            lines = self._handle_cancel_task()
        elif token == "cancel_scan":
            lines = self._handle_cancel_task(kinds=("scan_area",))
        elif token == "cancel_watch":
            lines = self._handle_cancel_task(kinds=("watch_contact",))
        elif token == "stop_talking":
            # No readback, no `_print` call at all -- `stop_talking` is a
            # stated exception to every other token's "dispatch, then
            # readback" shape (see `_handle_stop_talking`'s own docstring).
            self._handle_stop_talking()
            return []
        elif token == "report_all":
            lines = self._handle_report(now_sim)
        elif token in _CLOCK_REPORT_TOKENS:
            lines = self._handle_report(now_sim, clock=_CLOCK_REPORT_TOKENS[token])
        elif token in _BEARING_REPORT_TOKENS:
            lines = self._handle_report(now_sim, sector=_BEARING_REPORT_TOKENS[token])
        elif token == "report_bearing_deg":
            if bearing_degrees is None:
                lines = ["say again -- no bearing heard"]
            else:
                lines = self._handle_report(
                    now_sim, sector=_nearest_sector(bearing_degrees)
                )
        else:
            logger.warning("no dispatch behaviour for command token %r", token)
            return []
        self._print(lines, now_sim)
        return lines

    def _believed_air_defence(self, facts: dict[str, object]) -> bool:
        """Whether this contact is *believed* to be air defence -- the
        predicate behind the F10 "Watch -> Nearest Air Defence" item.

        **Reads the folded classification belief, never DCS ground truth**
        (this project's no-omniscience invariant, `belief.percept`'s module
        docstring). A contact is air defence here only if Petrovich's held
        claim has actually resolved that far: the claim's lattice level must
        be `class` or `type` (`_KNOWN_CLASS_LEVELS`), and its value must
        resolve through `belief.classification.parent_class_of` into
        `_AIR_DEFENCE_OP_CLASSES`.

        A `presence`-level contact -- "something is there", the naked-eye
        channel's `lowres` tier -- is therefore **never** matched, even if
        the thing really is an SA-8. That is the correct behaviour, not a
        gap to close later: the crew has no basis to call it air defence
        yet, and answering "nearest air defence" with an unidentified blob
        would be exactly the fabricated-knowledge failure the invariant
        exists to prevent. The honest consequence is that this command can
        report nothing while an unidentified SAM sits in plain sight."""
        classification = facts.get("classification")
        if not isinstance(classification, dict):
            return False
        level = classification.get("level")
        if not isinstance(level, str) or level not in _KNOWN_CLASS_LEVELS:
            return False
        value = classification.get("value")
        if not isinstance(value, str):
            return False
        return parent_class_of(value) in _AIR_DEFENCE_OP_CLASSES

    def _nearest_contact_id(
        self,
        now_sim: float,
        predicate: Callable[[dict[str, object]], bool] | None = None,
    ) -> str | None:
        """The currently-nearest contact by range, for the F10 "Watch"
        items. New glue logic, not a rediscovery of existing selection
        logic -- `belief.tools`/`belief.attention` have no "nearest by
        range" helper today, only `_highest_attention_contact`'s
        attention-tier-then-phase selection, a different question. Requires
        `self.enrichment` (range comes from `facts["relative_now"]
        ["range_m"]`, BL-3) -- returns `None` when it is unset or no
        contact has a resolvable range.

        `predicate`, when given, restricts the search to contacts whose
        `facts` it accepts (`_believed_air_defence` for the air-defence
        item). It filters *before* the nearest-by-range comparison, so the
        result is the nearest matching contact, not "the nearest contact,
        if it happens to match"."""
        if self.enrichment is None:
            return None
        nearest_id: str | None = None
        nearest_range_m: float | None = None
        for result in get_contacts(self.store, now_sim, enrichment=self.enrichment):
            facts = result["facts"]
            if predicate is not None and not predicate(facts):
                continue
            relative_now = facts.get("relative_now")
            if not isinstance(relative_now, dict):
                continue
            range_m = relative_now.get("range_m")
            if not isinstance(range_m, float):
                continue
            if nearest_range_m is None or range_m < nearest_range_m:
                contact_id = facts["id"]
                assert isinstance(contact_id, str)
                nearest_range_m = range_m
                nearest_id = contact_id
        return nearest_id

    def _handle_watch_nearest(
        self, now_sim: float, *, air_defence_only: bool = False
    ) -> list[str]:
        """The F10 "Watch -> Nearest" and "Watch -> Nearest Air Defence"
        items. The two differ only in the selection predicate; everything
        after it -- marking the contact, the readback -- is shared, since
        what "watch this" *means* does not change with how the contact was
        picked. The empty-result wording does differ: "no air defence
        contact" is a materially different statement from "no contact",
        and collapsing them would let the crew hear the wrong one.

        **Registers a cancellable `belief.tasks.PendingIntent` when
        `self.tasks` is configured** (`plans/watch-as-standing-mode/
        plan.md`, closing the root cause the 2026-09-21 sortie flagged:
        this used to call `set_attention` directly with nothing behind it
        for "Cancel Task" to find). Without a task store this falls back to
        the old direct `set_attention` call -- the same graceful-
        degradation shape `_handle_scan` already follows for a missing
        `enrichment`, so watch still works standalone, it just is not
        cancellable."""
        contact_id = self._nearest_contact_id(
            now_sim,
            predicate=self._believed_air_defence if air_defence_only else None,
        )
        if contact_id is None:
            return [
                "no air defence contact to watch"
                if air_defence_only
                else "no contact to watch"
            ]
        if self.tasks is not None:
            task = watch_contact_task(
                self.store, self.tasks, contact_id, now_sim, source="player"
            )
            found = task is not None
        else:
            found = set_attention(self.store, contact_id, "watch", source="player")
        result = describe_contact(
            self.store, contact_id, now_sim, enrichment=self.enrichment
        )
        if not found or result is None:
            return [f"no such contact: {contact_id}"]
        return [render_watch_nearest_readback(result["facts"]).text]

    def _descriptor_score(self, descriptor: str, facts: dict[str, object]) -> float:
        """The descriptor term of `_resolve_follow_target`'s score --
        `"group"` reads `facts["cardinality"]` (the user's own example
        word, `cardinality.lo > 1`), every other descriptor reads the
        classification lattice through `_FOLLOW_DESCRIPTOR_OP_CLASSES`.
        `0.0` on an exact match, `W_FOLLOW_DESC_UNKNOWN` when the contact
        is presence-level/unclassified (Decision 2b-iii: "he is pointing
        at a thing he *believes* is armour -- matching it is right"),
        `W_FOLLOW_DESC_WRONG` when it is a *different*, known class."""
        if descriptor == "group":
            cardinality = facts.get("cardinality")
            if isinstance(cardinality, dict):
                lo = cardinality.get("lo")
                if isinstance(lo, int) and lo > 1:
                    return 0.0
            return W_FOLLOW_DESC_WRONG
        classification = facts.get("classification")
        if not isinstance(classification, dict):
            return W_FOLLOW_DESC_UNKNOWN
        level = classification.get("level")
        if not isinstance(level, str) or level not in _KNOWN_CLASS_LEVELS:
            return W_FOLLOW_DESC_UNKNOWN
        value = classification.get("value")
        if not isinstance(value, str):
            return W_FOLLOW_DESC_UNKNOWN
        if parent_class_of(value) in _FOLLOW_DESCRIPTOR_OP_CLASSES.get(
            descriptor, frozenset()
        ):
            return 0.0
        return W_FOLLOW_DESC_WRONG

    def _resolve_follow_target(
        self,
        now_sim: float,
        descriptor: str | None,
        clock: int | None,
        range_km: int | None,
    ) -> tuple[str | None, list[str]]:
        """`plans/watch-reporting/plan.md` Decision 2b-iii's scoring
        resolver -- **a stopgap for the brain layer, not a model of
        anything** (the user's own framing, 2026-09-24: "this really
        needs the brain so I can freetext tell which contact to
        follow"). Delete this, do not extend it, once free-text
        targeting exists; its weights are guesses standing in for
        comprehension.

        Candidate set is `_handle_report`'s own (`belief.tools.
        get_contacts`, drop `certainty == "lost"`, drop anything with no
        `relative_now`). Score is `(descriptor, clock, range)`, all
        optional and additive, lower is better -- ties within
        `FOLLOW_SEPARATION` are broken by nearer range rather than asked
        about (a confirm round trip costs seconds while the pilot is
        pointing at something *now*; `cancel watch` + re-issue is one
        utterance if the pick is wrong). Returns `(contact_id, [])` on a
        win, or `(None, [<line to speak>])` when nothing clears
        `FOLLOW_MATCH_FLOOR` or no candidate exists at all."""
        assert self.enrichment is not None
        candidates: list[dict[str, object]] = []
        for result in get_contacts(self.store, now_sim, enrichment=self.enrichment):
            facts = result["facts"]
            if facts.get("certainty") == "lost":
                continue
            if not isinstance(facts.get("relative_now"), dict):
                continue
            candidates.append(facts)

        if not candidates:
            return None, ["no contact to watch"]

        def _score(facts: dict[str, object]) -> float:
            total = 0.0
            relative_now = facts.get("relative_now")
            assert isinstance(relative_now, dict)
            if descriptor is not None:
                total += self._descriptor_score(descriptor, facts)
            if clock is not None:
                actual_clock = relative_now["clock_position"]
                assert isinstance(actual_clock, int)
                total += _clock_delta(clock, actual_clock) * W_FOLLOW_CLOCK
            if range_km is not None:
                actual_range_m = relative_now["range_m"]
                assert isinstance(actual_range_m, float)
                total += abs(range_km - actual_range_m / 1000.0) * W_FOLLOW_RANGE
            return total

        scored = sorted(
            ((_score(facts), facts) for facts in candidates), key=lambda item: item[0]
        )
        best_score, best_facts = scored[0]
        if best_score > FOLLOW_MATCH_FLOOR:
            only_clock = descriptor is None and range_km is None and clock is not None
            if only_clock:
                assert clock is not None
                label = f"{_CLOCK_REPORT_LABELS[clock]} o'clock"
                return None, [render_no_contact(label).text]
            return None, [render_no_contact().text]

        winner = best_facts
        tied = [
            facts for score, facts in scored if score - best_score < FOLLOW_SEPARATION
        ]
        if len(tied) > 1:
            # Decision 2b-iii: ties prefer the nearer contact, never ask.
            def _range_m(facts: dict[str, object]) -> float:
                relative_now = facts.get("relative_now")
                assert isinstance(relative_now, dict)
                range_m = relative_now["range_m"]
                assert isinstance(range_m, float)
                return range_m

            winner = min(tied, key=_range_m)

        contact_id = winner["id"]
        assert isinstance(contact_id, str)
        return contact_id, []

    def _handle_follow(
        self, now_sim: float, slots: dict[str, int | str] | None
    ) -> list[str]:
        """`follow [<descriptor>] [<clock> o'clock] [<n> km]` -- resolves
        via `_resolve_follow_target` and, on a win, watches exactly the
        same way `_handle_watch_nearest` does (a cancellable task when
        `self.tasks` is configured, a bare `set_attention` otherwise),
        with the identical readback (`render_watch_nearest_readback`) --
        the player named no id either way, so the two commands describe
        their winner identically."""
        descriptor = slots.get("descriptor") if slots is not None else None
        clock = slots.get("clock") if slots is not None else None
        range_km = slots.get("range_km") if slots is not None else None
        if not isinstance(descriptor, str):
            descriptor = None
        if not isinstance(clock, int):
            clock = None
        if not isinstance(range_km, int):
            range_km = None
        if descriptor is None and clock is None and range_km is None:
            # A malformed/empty-slots call -- unreachable from a real
            # `follow` match (the matcher never returns `token="follow"`
            # with `slots=None`), but a defensive, request-shape check
            # that comes before the environment check below, since "you
            # asked for nothing" is true regardless of what is configured.
            return ["say again -- follow needs at least one of what/where/how far"]
        if self.enrichment is None:
            return ["no world-model connection configured"]

        contact_id, no_match_lines = self._resolve_follow_target(
            now_sim, descriptor, clock, range_km
        )
        if contact_id is None:
            return no_match_lines

        self.last_command_target_contact_id = contact_id
        if self.tasks is not None:
            task = watch_contact_task(
                self.store, self.tasks, contact_id, now_sim, source="player"
            )
            found = task is not None
        else:
            found = set_attention(self.store, contact_id, "watch", source="player")
        result = describe_contact(
            self.store, contact_id, now_sim, enrichment=self.enrichment
        )
        if not found or result is None:
            return [f"no such contact: {contact_id}"]
        return [render_watch_nearest_readback(result["facts"]).text]

    def _handle_scan(
        self,
        now_sim: float,
        *,
        sector_label: str,
        sector: Sector | None = None,
        relative_sector: RelativeSector | None = None,
        relative_clock_hour: int | None = None,
    ) -> list[str]:
        """Registers a real `belief.tasks.PendingIntent` via `belief.tools.
        scan_area`, with `center`/`radius_m`/`reason` all fixed (ownship's
        own position, `None` (unbounded), `_SCAN_COMMAND_REASON`) rather than
        player-supplied, since an F10 button carries no bearing/range/
        free-text the way a typed `scan-area` command does. `radius_m=None`
        is a deliberate choice, not a missing value: an F10 sector scan
        should get everything visible within its wedge, per `todo/todo.md`'s
        "Scan geometry: drop the invented radius" -- the area's own
        `radius_m` field documents the reasoning in full. At most one of
        `sector`/`relative_sector`/`relative_clock_hour` (Stage 5's own
        o'clock family, `plans/voice-command-completeness/plan.md`
        Decision 5) is set by the caller (`handle_command`'s lookup
        tables), never more than one -- `scan_area`/`ContactStore.add_area`
        would raise `ValueError` if they were.

        **Fires no DCS effector, deliberately** (live-test finding
        2026-09-16). This handler used to call `aircraft_client.
        trigger_petrovich_search("forward")`, inherited from the hollow
        pre-`f10-command-vocabulary` `scan_forward` item and never
        questioned when D5 wrapped a real task around it. That drives DCS
        Petrovich's **9K113 sight**, which `docs/concept/
        state-transitions.jpg`'s own glossary assigns to a different verb:
        *Scan = visual scan for targets*, *Observ = scan with 9K113*. Scan
        is meant to be this project's own naked-eye/binocular perception
        (`perception.naked_eye_source`), not the AI wheel. The trigger
        stays available on `aircraft_client` for a future `Observ` command,
        which is blocked on the still-unidentified 9K113 OBSERV OFF control
        (`body-layer/ROADMAP.md`).

        **Known consequence: a scan currently changes attention, not
        perception.** `perception.visibility`'s naked-eye gate uses a fixed
        cockpit occlusion mask (`perception.cockpit_mask`,
        `plans/cockpit-visibility/plan.md`) that no command steers, so
        "scan left" registers an `AttentionArea` and a task but does not
        change which contacts are detected. Making the
        scanned sector actually drive perception is backlogged
        (`todo/todo.md`, "Scan commands should drive naked-eye perception")
        -- deliberately not done here, per user direction 2026-09-16 to
        unwire the wrong effector first and model the scan pattern
        separately.

        Requires both `self.enrichment` (for ownship's position) and
        `self.tasks` (to register the task) -- returns a plain one-line
        message without raising when either is unset, the same graceful-
        degradation shape `_handle_watch_nearest` already follows for a
        missing `enrichment`."""
        if self.enrichment is None:
            return ["no world-model connection configured"]
        if self.tasks is None:
            return ["no task store configured"]
        ownship = self.enrichment.ownship
        center = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
        # The returned `PendingIntent` is deliberately not bound: the task
        # exists so `cancel_task` has something to cancel and `TaskStore.
        # tick` can complete it, and the readback names the sector rather
        # than the task, so nothing here reads it back.
        scan_area(
            self.store,
            self.tasks,
            center,
            None,
            _SCAN_COMMAND_REASON,
            now_sim,
            sector=sector,
            relative_sector=relative_sector,
            relative_clock_hour=relative_clock_hour,
        )
        return [render_scan_readback(sector_label).text]

    def _handle_report(
        self,
        now_sim: float,
        *,
        clock: int | None = None,
        sector: Sector | None = None,
    ) -> list[str]:
        """`report_all`/`report_clock_<p>`/`report_bearing_<compass>`/
        `report_bearing_deg` (the last reduced to `sector` by
        `handle_command` before this is ever called) -- `plans/
        voice-command-completeness/plan.md` Decision 1: **a read of current
        belief and nothing else.** No `AttentionArea`, no `PendingIntent`,
        no gaze change, no `aircraft_client` call -- "report is always
        about current belief. Scan tells to go look" (user, 2026-09-23).
        At most one of `clock`/`sector` is set by the caller; neither set
        means `report_all`.

        **Source of facts, in order** (Decision 1's numbered steps):
        `belief.tools.get_contacts`, then drop `certainty == "lost"`
        (contacts are never pruned, so without this a report grows
        monotonically over a sortie -- `"estimated"` stays, since a
        remembered contact is still belief), then drop anything with no
        `relative_now` (no `self.enrichment` -> the whole family answers
        the same graceful-degradation line `_handle_scan` already uses),
        then the family filter, then group+render.

        **The rear-hemisphere carve-out (Decision 2) applies only to
        `sector`.** The clock family is safe by construction (`_CLOCK_
        REPORT_TOKENS` only names the eight-to-four forward hemisphere,
        same as `audio_adapter.vocabulary.FORWARD_CLOCK_POSITIONS` and for
        the identical reason) -- `report_all` never claims a direction at
        all. A `sector` request asks about an absolute compass direction
        that may sit behind the aircraft; answering "clear" there would
        claim a look the cockpit mask makes physically impossible, so an
        empty result for a rear-hemisphere `sector` speaks `render_no_view`
        instead of `render_clear`. A contact that *is* believed to sit
        there is still reported normally -- belief survives the aircraft
        turning away; only the *absence* claim is withheld."""
        if self.enrichment is None:
            return ["no world-model connection configured"]

        direction_label: str | None = None
        rear_hemisphere = False
        if clock is not None:
            direction_label = f"{_CLOCK_REPORT_LABELS[clock]} o'clock"
        elif sector is not None:
            direction_label = _SECTOR_SCAN_LABELS[sector]
            heading = self.enrichment.ownship.heading_true_deg
            relative_deg = angular_delta_deg(_SECTOR_CENTER_DEG[sector], heading)
            rear_cutoff_deg = COCKPIT_MASKS[STATION_CO_PILOT].rear_cutoff_deg
            rear_hemisphere = relative_deg >= rear_cutoff_deg

        center_deg = _SECTOR_CENTER_DEG[sector] if sector is not None else None
        facts_list: list[dict[str, object]] = []
        for result in get_contacts(self.store, now_sim, enrichment=self.enrichment):
            facts = result["facts"]
            if facts.get("certainty") == "lost":
                continue
            relative_now = facts.get("relative_now")
            if not isinstance(relative_now, dict):
                continue
            if clock is not None and relative_now["clock_position"] != clock:
                continue
            if center_deg is not None:
                bearing_deg = relative_now["bearing_deg"]
                assert isinstance(bearing_deg, float)
                if angular_delta_deg(bearing_deg, center_deg) > 45.0:
                    continue
            facts_list.append(facts)

        if not facts_list:
            if rear_hemisphere:
                assert direction_label is not None
                return [render_no_view(direction_label).text]
            return [render_clear(direction_label).text]

        groups = sorted(
            group_facts(facts_list),
            key=lambda group: min(report_priority(facts) for facts in group),
        )
        texts = [
            _contact_report_text(group[0])
            if len(group) == 1
            else render_group_report(group).text
            for group in groups[:REPORT_MAX_GROUPS]
        ]
        truncated = len(groups) > REPORT_MAX_GROUPS
        return [render_report(texts, truncated).text]

    def _describe_task_for_speech(self, task: PendingIntent) -> str | None:
        """A plain human phrase for `task`, for `speech.render_cancel_
        readback` -- `"the scan to the left"`, `"the scan north"`,
        `"the watch"` -- or `None` when the task's shape yields nothing
        better than "whatever you last asked for".

        For a `scan_area` task, reads the frame fields (`relative_sector`/
        `sector`/`relative_clock_hour`, Stage 5's own o'clock field) straight
        off the task's captured `area`. Unlike the geometry fields, those
        three are never rewritten by `ContactStore.reproject_relative_areas`
        -- it replaces `center`/`wedge_deg` only -- so the captured
        reference is safe to read here, and going through `store.get_area`
        would return the same frame anyway. (`TaskStore.tick` *does* have to
        resolve the live area; see its own docstring for why the two
        differ.)

        For a `watch_contact` task (`plans/watch-as-standing-mode/
        plan.md`), always `"the watch"` -- never the watched contact's id
        or type, matching `render_cancel_readback`'s own "no ids in
        speech" rule and keeping the phrase as terse as the scan
        fallback's own bare `"the scan"`."""
        if task.kind == "watch_contact":
            return "watch"
        if task.kind != "scan_area":
            return None
        area = task.area
        assert area is not None  # every scan_area task carries an area
        if area.relative_sector is not None:
            return f"scan {_RELATIVE_SCAN_LABELS[area.relative_sector]}"
        if area.relative_clock_hour is not None:
            return f"scan {_CLOCK_REPORT_LABELS[area.relative_clock_hour]} o'clock"
        if area.sector is not None:
            return f"scan {_SECTOR_SCAN_LABELS[area.sector]}"
        return "scan"

    def _handle_cancel_task(self, kinds: tuple[str, ...] | None = None) -> list[str]:
        """Cancels the single currently-*governing* task of each kind in
                `self.tasks`, regardless of source (plan Decision 3). Every
                `scan_*` token registers a real task via `_handle_scan` above (D5,
                `plans/f10-command-vocabulary/plan.md`), and every `watch_nearest*`
                token now does too (`plans/watch-as-standing-mode/plan.md`), so this
                is no longer the always-"no pending task" dead path it was before
                those fixes -- a scan and/or a watch followed by "Cancel Task"
                genuinely cancels them.

        **`kinds` selects which standing modes to end; `None` means all of
                them (2026-09-23, reversing this method's own earlier decision).**
                The original reasoning was sound given what existed: there was no
                vocabulary to say "cancel the watch" as opposed to the scan, so
                guessing was worse than stopping everything and naming each thing
                stopped. The user's answer once he had flown it was to supply the
                missing vocabulary instead -- *"stop watching <unit>"* and *"stop
                scan"* are separate actions, and **one cancel must not silently end
                the other mode**. Stopping a scan while watching a contact is an
                ordinary thing to want, and the cancel-everything reading made it
                impossible to express.

                So the menu now carries `cancel_scan` and `cancel_watch`, and
                `cancel_task` remains as the deliberate all-modes form -- kept, not
                left over: *"cancel that"* is a real thing to say when several
                things are running, and its readback names both, so it cannot be
                mistaken for a narrow cancel.

                **"Currently governing" means the single most-recently-created
                still-active task *per kind*, not literally every non-cancelled
                task ever created.** Superseding a scan with a newer one (or a
                watch with a newer one) does not retroactively cancel the earlier
                task -- `logger._active_gaze` already only honours the newest
                `scan_area` task via its own "most recent wins" tie-break, and an
                older, superseded task of either kind is inert but not `cancelled`.
                Treating every merely-inert task as "active" would make one Cancel
                Task press cancel a whole session's worth of stale scans, so this
                groups active tasks by `kind` and keeps only each group's newest
                (`_active_tasks_by_kind`) -- exactly the selection
                `logger._active_gaze` already uses for gaze, generalised to any
                kind.

                **That selection now decides only what the readback NAMES. What
                gets cancelled is every active task of the selected kinds
                (2026-09-25, user, after flying it).** Cancelling only each kind's
                newest task *resurrected* the one it had superseded: an older
                `scan_area` is inert precisely because a newer one outranks it in
                `logger._active_gaze`'s "most recent wins" tie-break, so cancelling
                the newer one promotes the older one straight back into governing
                the gaze. He said "cancel", confirmed "cancel everything", heard
                both current modes named -- and an earlier "scan south" was still
                steering afterwards.

                The original worry ("a whole session's worth of stale scans") had
                it backwards: those stale tasks are exactly what resurrects, and
                cancelling them is free because they were already inert. **Cancel
                everything must really cancel everything** -- the user's own words.
                The readback keeps naming only the governing tasks, because naming
                every stale scan would be noise about things that were not doing
                anything anyway.

                **Cones 2C sortie fix, unchanged: "active" means `status !=
                "cancelled"`, not `status == "pending"`.** A `scan_area` task is a
                standing mode (`belief.tasks.TaskStatus`'s own docstring) that
                `TaskStore.tick` can flip to `"succeeded"` within seconds of being
                issued (the moment any contact is seen in its area) -- under a
                `"pending"`-only filter, that task had already dropped out of this
                list by the time a player heard it and said "Cancel Task," which
                produced the sortie's "'nothing to stop'" finding. `TaskStore.
                cancel` itself is fixed the same way, so cancelling a resolved task
                here now genuinely ends its mode (`logger._active_gaze` stops
                honouring it), not just a bookkeeping no-op. A `watch_contact` task
                never leaves `"pending"` on its own (`TaskStore.tick` skips any task
                with no `area`), so this same "active" definition covers it too
                without a separate case.

                The readback names *what* was cancelled, never the task id
                (live-test finding 2026-09-16: the player heard `"cancelled task
                TASK_4"`). See `speech.render_cancel_readback` for why -- the same
                no-ids-in-speech rule this codebase already applies to contacts."""
        # Both no-store and nothing-active say the same thing, and it is
        # deliberately *not* `render_cancel_readback` -- that template says
        # "Copy, stopping", which would claim to have stopped something
        # when nothing was cancelled at all.
        if self.tasks is None:
            return [_NOTHING_TO_STOP]
        # Cancel EVERY active task of the selected kinds, not only each
        # kind's newest -- see this method's "supersession is not
        # cancellation" note above. The readback still names only the
        # governing ones, so the wording is unchanged.
        governing = _active_tasks_by_kind(self.tasks.tasks)
        doomed = [task for task in self.tasks.tasks if task.status != "cancelled"]
        if kinds is not None:
            governing = [task for task in governing if task.kind in kinds]
            doomed = [task for task in doomed if task.kind in kinds]
        if not doomed:
            return [_NOTHING_TO_STOP]
        descriptions: list[str] = []
        for task in governing:
            description = self._describe_task_for_speech(task)
            if description is not None:
                descriptions.append(description)
        for task in doomed:
            cancel_task(self.store, self.tasks, task.id)
        return [render_cancel_readback(_join_task_descriptions(descriptions)).text]

    def _handle_stop_talking(self) -> None:
        """`stop_talking` -- interrupts whatever is currently playing and
        drops whatever is queued, and says **nothing at all** (user
        direction, 2026-09-20, verbatim: *"'Stop' -- no readback or
        confirmation, just stop talking. That is exception to the normal
        read back/confirm rule. It's more of a debug tool than crew
        feature."*). Every other token this method's caller dispatches
        speaks a readback (`belief.speech`'s module docstring, "Templated,
        body-written" class); `stop_talking` deliberately does not --
        acknowledging a request for silence with speech would defeat the
        request. That is why this method returns nothing and is never
        routed through `_print`: there is no line to print, push to the
        overlay, or speak.

        `handle_command`'s Stage 3 revision to this method (the
        original had this return a short `"Copy."` acknowledgement, pushed
        urgent through `_print` -- see plan Stage 3's own entry for that
        history) replaced *that* with a real interrupt-only call:
        `speech_client.stop()` (`belief.audio_client.AudioAdapterClient.
        stop`, `POST /stop`) reaches audio-adapter's `AudioSink.interrupt`
        without synthesizing or delivering any audio -- for `--target
        aircraft-layer` that forwards to `collector.audio_sender.
        AudioPlaybackSender.interrupt` (`POST /audio/stop`), which clears
        the routine queue and stops in-flight playback exactly as
        `play_audio(..., urgent=True)` already did, just without the
        enqueue that used to carry the acknowledgement. Without
        `speech_client` configured (no `--speech-audio`), there is nothing
        to interrupt and this is a true no-op -- the same
        None-means-no-op posture every other `speech_client` use already
        has."""
        if self.speech_client is None:
            return
        try:
            self.speech_client.stop()
        except AudioAdapterError:
            logger.warning(
                "speech interrupt failed for stop_talking (continuing)",
                exc_info=True,
            )

    def handle_transcript(
        self,
        transcript: str,
        confidence: float,
        token: str | None,
        match_ratio: float,
        verb_anchored: bool,
        ambiguous: bool,
        now_sim: float,
        slots: dict[str, int | str] | None = None,
    ) -> list[str]:
        """`plans/inbound-speech/plan.md` Stage 2's voice-command entry
        point -- a sibling of `handle_line`/`handle_command`, per the
        module docstring's prediction of a third input surface. Called
        with the fields `audio_adapter.command_matcher.MatchResult` already
        resolved (Stage 3 wires the real HTTP poll; this stage is driven
        by tests and the `!voice` REPL harness, see `_handle_voice_test_
        command`). `slots` (`plans/watch-reporting/plan.md` Decision 2b-i,
        replacing the earlier single-purpose `bearing_degrees` parameter)
        is `MatchResult.slots` carried through unchanged -- populated only
        for tokens that take a parsed slot (`scan_bearing_deg`/
        `report_bearing_deg`'s `"bearing_degrees"`, `follow`'s
        `"descriptor"`/`"clock"`/`"range_km"`).

        **A pending confirm-band question, if any, is checked first** --
        `classify_yes_no` decides whether this transcript commits, discards,
        or (implicitly) abandons it. Any answer other than affirm/negative
        discards the pending question *silently* and falls through to treat
        this transcript as its own new input (Decision 4 Layer 3: "anything
        else, or the timeout, discards silently" -- read as discarding the
        stale question, not the player's new utterance). Affirm/negative
        are valid only inside this branch, i.e. only while a confirmation
        is pending -- outside it the same words are ordinary text and reach
        `belief.voice_commands.classify_response` like anything else.
        Committing (`affirm`) passes `pending.slots` through to
        `handle_command`, not this call's own `slots` -- the qualifiers
        belong to whichever transcript originally proposed the pending
        command, not to the (typically slot-less) "affirm" reply that
        commits it.

        **A yes/no word arriving just after the window is answered, not
        escalated** (`CONFIRM_LATE_ANSWER_GRACE_S`). It cannot commit
        anything -- the question and its slots are gone -- so it draws a
        "Say again?", which is what the 2026-09-26 sortie should have
        heard: the pilot's "yes" fell through to `_handle_utterance`
        instead, the decider found no command in the word itself, and
        Petrovich answered "Unable, no such command." That wording tells
        the pilot his *command* was rejected, when in fact his *answer*
        was late -- a materially wrong readback, and the reason this
        branch exists rather than leaving the fallthrough alone."""
        if self._pending_confirmation is not None:
            pending = self._pending_confirmation
            if now_sim - pending.pending_since_sim <= CONFIRM_WINDOW_S:
                answer = classify_yes_no(transcript, token is not None)
                self._pending_confirmation = None
                self._confirmation_expired_sim = None
                if answer == "affirm":
                    if pending.contact_pick is not None:
                        # `plans/brain-layer/plan.md` D4's "confirm the
                        # survivor" branch -- committing acts on the
                        # single candidate that survived revalidation,
                        # re-running the originally-escalated intent
                        # (`set_attention`/`describe_contact`) against it.
                        contact_id, parse = pending.contact_pick
                        return self._act(
                            replace(parse, referenced_contact_id=contact_id), now_sim
                        )
                    assert pending.token is not None
                    return self.handle_command(
                        pending.token, now_sim, slots=pending.slots
                    )
                if answer == "negative":
                    return []
                # else: falls through and this transcript is evaluated on
                # its own merits below.
            else:
                self._pending_confirmation = None
                self._confirmation_expired_sim = pending.pending_since_sim + (
                    CONFIRM_WINDOW_S
                )

        # A yes/no word arriving just *after* the window is a late answer,
        # not free speech. It cannot commit anything -- the question is
        # gone and its slots with it -- but it must not be escalated
        # either: the brain layer finds no command in "yes" and answers
        # "Unable, no such command.", which tells the pilot his command
        # was rejected when in fact his answer was late. "Say again?" is
        # the honest signal and prompts the retry that actually works.
        if (
            self._pending_confirmation is None
            and self._confirmation_expired_sim is not None
        ):
            since_expiry = now_sim - self._confirmation_expired_sim
            if (
                0.0 <= since_expiry <= CONFIRM_LATE_ANSWER_GRACE_S
                and classify_yes_no(transcript, token is not None) != "other"
            ):
                self._confirmation_expired_sim = None
                lines = [render_say_again().text]
                self._print(lines, now_sim)
                return lines

        decision = classify_response(
            token, match_ratio, confidence, verb_anchored, ambiguous
        )
        self._log_transcript(
            transcript=transcript,
            confidence=confidence,
            token=token,
            match_ratio=match_ratio,
            verb_anchored=verb_anchored,
            ambiguous=ambiguous,
            now_sim=now_sim,
            disposition=decision.disposition,
            acted_token=decision.token,
        )
        return self._act_on_voice_decision(decision, transcript, now_sim, slots)

    def _log_transcript(self, **row: object) -> None:
        """Write one row to `transcript_log`, if configured.

        Wrapped like every other optional sink: a logging failure must not
        cost the player the command they just spoke."""
        if self.transcript_log is None:
            return
        try:
            self.transcript_log(row)
        except Exception:  # noqa: BLE001 -- a debug sink, never load-bearing
            return

    def _act_on_voice_decision(
        self,
        decision: BandDecision,
        transcript: str,
        now_sim: float,
        slots: dict[str, int | str] | None = None,
    ) -> list[str]:
        if decision.disposition == "fallthrough":
            # `handle_line` re-strips/re-checks the `!`-prefixed harness
            # commands, which a real transcript never begins with -- safe
            # to route straight through it rather than duplicating
            # `_handle_utterance` + `_print` here.
            return self.handle_line(transcript, now_sim)
        if decision.disposition == "act":
            assert decision.token is not None
            return self.handle_command(decision.token, now_sim, slots=slots)
        if decision.disposition == "confirm":
            assert decision.token is not None
            description = _describe_token_for_confirm(decision.token, slots)
            self._pending_confirmation = PendingConfirmation(
                token=decision.token,
                description=description,
                pending_since_sim=now_sim,
                slots=slots,
            )
            # A fresh question supersedes any late-answer grace left over
            # from the previous one -- the pilot is answering this one now.
            self._confirmation_expired_sim = None
            lines = [render_confirm_request(description).text]
        else:  # "say_again"
            lines = [render_say_again().text]
        self._print(lines, now_sim)
        return lines

    def _parse_follow_slots_for_harness(
        self, transcript: str
    ) -> dict[str, int | str] | None:
        """A deliberately small, harness-only re-parse of `follow`'s three
        slots straight out of typed transcript text -- `!voice`'s own
        posture (module independence: body-layer cannot import
        `audio-adapter`'s real `parse_clock`/`parse_range_km`/
        `parse_descriptor`), extended to this one token so the resolver's
        weights can be tuned from the REPL without a redeploy (`plans/
        watch-reporting/plan.md` Decision 2b-iii: "exercisable from the
        `!voice` harness and the typed console before any redeploy").
        Narrower than the real parsers on purpose -- a dev aid, not a
        second production implementation."""
        words = transcript.lower().replace("'", "").replace("-", " ").split()
        slots: dict[str, int | str] = {}
        for word in words:
            if word in _FOLLOW_DESCRIPTOR_OP_CLASSES or word == "group":
                slots.setdefault("descriptor", word)
        for index, word in enumerate(words):
            if word in ("oclock", "o'clock") and index > 0:
                hour = _FOLLOW_HARNESS_CLOCK_WORDS.get(words[index - 1])
                if hour is not None:
                    slots["clock"] = hour
            if word in _FOLLOW_HARNESS_RANGE_UNIT_WORDS and index > 0:
                previous = words[index - 1]
                value = (
                    int(previous)
                    if previous.isdigit()
                    else _FOLLOW_HARNESS_RANGE_WORDS.get(previous)
                )
                if value is not None and 1 <= value <= 20:
                    slots["range_km"] = value
        return slots if slots else None

    def _handle_voice_test_command(self, line: str, now_sim: float) -> list[str]:
        """`!voice` -- a manually-typed test harness for `handle_transcript`,
        mirroring `!inject-urgent`'s "clearly-labelled test harness, not a
        production surface" posture. Body-layer cannot compute a real match
        itself (module independence: no import of `audio-adapter`'s
        `command_matcher`/`vocabulary`) -- this command instead takes the
        fields the adapter would have already produced as literal typed
        arguments, exactly the shape Stage 3's real `GET /transcripts/poll`
        will eventually deliver, so a developer can drive the full
        act/confirm/say-again pipeline from the REPL without audio, a
        running adapter, or DCS.

        `!voice <token|-> <match_ratio> <confidence> <verb_anchored:0|1>
        <ambiguous:0|1> <transcript...>` -- `-` for `token` means "no
        match" (`None`). `<transcript...>` accepts an **optional trailing
        degrees argument** (`plans/voice-command-completeness/plan.md`
        Stage 3, decision 3 item 6, now populating `slots["bearing_
        degrees"]` -- `plans/watch-reporting/plan.md` Decision 2b-i): if
        the transcript's last word is a bare integer, it is peeled off and
        the remaining words are the transcript, mirroring `MatchResult.
        slots`'s real shape (a parsed value attached to, but distinct from,
        the transcript text) without adding a new fixed positional argument
        that would break every existing `!voice` invocation. `!voice
        scan_bearing_deg 1.0 1.0 1 0 scan bearing three two zero 320` sets
        `slots={"bearing_degrees": 320}`; a transcript with no trailing
        integer (every pre-existing test/harness use) is unaffected."""
        usage = [
            (
                "usage: !voice <token|-> <match_ratio> <confidence> "
                "<verb_anchored:0|1> <ambiguous:0|1> <transcript...>"
            )
        ]
        parts = line.split(maxsplit=6)
        if len(parts) != 7:
            self._print(usage, now_sim)
            return usage
        _, token_arg, ratio_arg, confidence_arg, verb_arg, ambiguous_arg, transcript = (
            parts
        )
        try:
            match_ratio = float(ratio_arg)
            confidence = float(confidence_arg)
        except ValueError:
            self._print(usage, now_sim)
            return usage
        if verb_arg not in ("0", "1") or ambiguous_arg not in ("0", "1"):
            self._print(usage, now_sim)
            return usage
        token = None if token_arg == "-" else token_arg
        slots: dict[str, int | str] | None = None
        if token == "follow":
            slots = self._parse_follow_slots_for_harness(transcript)
        else:
            split_transcript = transcript.rsplit(maxsplit=1)
            if len(split_transcript) == 2 and split_transcript[1].lstrip("-").isdigit():
                transcript, degrees_word = split_transcript
                slots = {"bearing_degrees": int(degrees_word)}
        return self.handle_transcript(
            transcript,
            confidence,
            token,
            match_ratio,
            verb_arg == "1",
            ambiguous_arg == "1",
            now_sim,
            slots=slots,
        )

    def _new_utterance_id(self) -> str:
        self._next_utterance_number += 1
        return f"{_UTTERANCE_ID_PREFIX}_{self._next_utterance_number}"

    def _handle_utterance(self, transcript: str, now_sim: float) -> list[str]:
        # `plans/binocular-optic/plan.md` D4, narrowed by `plans/
        # sortie-2026-09-26-fixes/decisions.md` Decision 2: the player
        # asking for something *that was understood* is itself evidence
        # Petrovich's current optic activity matters less than what was
        # just asked -- unconditional across surfaces, not a per-command
        # special case, but only once there is something to prefer over
        # the current look. An utterance the free-text parser also fails to
        # understand (escalated to the brain layer, `disposition ==
        # "escalated"` below) is not a new task -- "say again" is not a
        # request to stop what he is doing, it is a recognition failure,
        # and lowering the binoculars there would destroy real work in
        # response to one. This is the one point both `handle_line` (typed
        # free text) and voice's `"fallthrough"` disposition (which itself
        # calls `handle_line` -- see `_act_on_voice_decision`) pass
        # through, so counting here (moved inside the `"handled"` branch,
        # not called unconditionally as it used to be) covers both without
        # double-counting `handle_command`'s own call for the token-dispatch
        # surface.
        parse = parse_utterance(self.store, transcript, now_sim)
        utterance = PlayerUtterance(
            id=self._new_utterance_id(),
            t_sim=now_sim,
            transcript=transcript,
            transcript_confidence=1.0,
            source="debug_console",
            parse=parse,
        )
        if parse.disposition == "handled":
            self._note_player_command()
            return self._act(parse, now_sim)
        # `plans/brain-layer/plan.md` -- tracked so `_handle_brain_reply`
        # knows what to act on if/when a reply lands (D4's table), and so
        # `_speak_stand_by_if_due` knows this question is outstanding
        # (D8). Recorded before `handle_player_utterance` posts, not
        # after -- the brain-layer client's own worker thread can in
        # principle complete faster than this method returns (an
        # artificial `delay_s=0` stub, say), and a reply for an
        # utterance_id not yet in `_pending_escalations` would otherwise
        # be silently dropped as untracked.
        self._pending_escalations[utterance.id] = (now_sim, parse, transcript)
        handle_player_utterance(
            self.store, utterance, self.brain_client, self.enrichment
        )
        return []

    def _act(self, parse: PartialParse, now_sim: float) -> list[str]:
        contact_id = parse.referenced_contact_id
        assert contact_id is not None  # guaranteed by disposition == "handled"
        if parse.matched_intent == "set_attention":
            assert parse.attention_level is not None
            found = set_attention(
                self.store, contact_id, parse.attention_level, source="player"
            )
            if not found:
                return [f"no such contact: {contact_id}"]
            return [render_readback(parse.attention_level, contact_id).text]
        if parse.matched_intent == "describe_contact":
            speech = render_contact_report(
                self.store, contact_id, now_sim, self.enrichment
            )
            if speech is None:
                return [f"no such contact: {contact_id}"]
            return [speech.text]
        return []

    def _handle_inject_urgent(
        self, line: str, now_sim: float
    ) -> tuple[list[str], bool]:
        parts = line.split(maxsplit=2)
        if len(parts) != 3:
            return ["usage: !inject-urgent <contact_id> <text>"], False
        _, contact_id, text = parts
        speech = route_event(
            self.store, UrgentCall(contact_id=contact_id, text=text), now_sim
        )
        if speech is None:
            return [], False
        # `route_event` always returns a non-`None` `OutgoingSpeech` for an
        # `UrgentCall` (see that function's own body), and always with
        # `bypass_gate=True` -- read straight off the result rather than
        # re-deriving it, so this stays the single source of truth.
        return [speech.text], speech.bypass_gate

    def _print(
        self, lines: list[str], now_sim: float, bypass_gate: bool = False
    ) -> None:
        """Prints each line to `output` (unchanged) and, when
        `overlay_client`/`speech_client` are configured, pushes the same
        line to the in-cockpit text overlay (`AircraftLayerClient.
        push_text_line`, `POST /text/push`) and/or the TTS audio pipeline
        (`AudioAdapterClient.push_speech`, `POST /speak` -- BL-10 first
        slice, `plans/tts-voice-output/plan.md`) -- the single funnel
        point every path that produces spoken text (`handle_line`,
        `drain_events`) already goes through, so neither sink needs a
        separate "what to push and when" logic to write or desync from
        what's printed. Each push is wrapped in its own
        `try/except`, mirroring `logger.ConsolePerceptionRunner.run_once`'s
        BL-2.5 push loop's degrade-on-failure shape: a failed push must not
        raise, must not stop the remaining lines in this batch from being
        printed/pushed/spoken, and must not stop the other sink's own push
        for the same line.

        `bypass_gate` (True only for an injected urgent call, per `plans/
        overlay-speech-callouts/plan.md`'s resolved decision) prepends
        `_URGENT_OVERLAY_PREFIX` to the *pushed* overlay line only -- the
        `output` print path stays exactly the text `belief.speech`
        produced, since this is an overlay-display concern, not a change
        to what was spoken/printed generally. For `speech_client`,
        `bypass_gate` is threaded straight through as `push_speech`'s
        `urgent` argument instead (plan Decision 3/4: no new signal
        invented -- an injected urgent call is the only line that ever
        sets it, and the aircraft-layer's `AudioPlaybackSender` is what
        actually preempts routine playback for it).

        `now_sim` (`plans/callout-scheduling/plan.md`) is needed for
        exactly one thing here: when `bypass_gate` is True, this call is an
        urgent line that just pre-empted whatever the scheduler thought was
        in flight (`AudioPlaybackSender.interrupt`, on the real audio path,
        clears the routine queue and kills in-flight playback) --
        `self.scheduler.note_urgent` resets `busy_until_sim` to the urgent
        line's own duration so the scheduler does not keep believing a
        routine line the audio layer has already destroyed is still
        playing. An urgent call is always exactly one line
        (`_handle_inject_urgent`'s only caller of this path), but this
        loops over `lines` rather than assuming that, so it degrades
        correctly if that ever changes."""
        for line in lines:
            if self.output is not None:
                print(line, file=self.output)
            if self.speech_log_sink is not None:
                try:
                    self.speech_log_sink(line, bypass_gate)
                except Exception:
                    # Deliberately broad: a debug log must never be the reason
                    # Petrovich stops talking.
                    logger.warning(
                        "speech log sink failed for crew-text line (continuing)",
                        exc_info=True,
                    )
            if self.overlay_client is not None:
                overlay_line = (
                    f"{_URGENT_OVERLAY_PREFIX}{line}" if bypass_gate else line
                )
                try:
                    self.overlay_client.push_text_line(overlay_line)
                except AircraftLayerError:
                    logger.warning(
                        "overlay push failed for crew-text line (continuing)",
                        exc_info=True,
                    )
            if self.speech_client is not None:
                try:
                    self.speech_client.push_speech(line, urgent=bypass_gate)
                except AudioAdapterError:
                    logger.warning(
                        "speech push failed for crew-text line (continuing)",
                        exc_info=True,
                    )
            if bypass_gate:
                self.scheduler.note_urgent(now_sim, line)
            else:
                # `plans/voice-command-completeness/plan.md` Decision 2 --
                # every reply (a readback or a report) claims the channel
                # for its own spoken duration, fixing a real latent defect:
                # every command readback has been unbudgeted since readbacks
                # existed, so a routine callout could queue immediately
                # behind one. `note_reply` extends (`max`), never preempts,
                # so a scheduler-drained callout line (already accounted
                # for by `CalloutScheduler.tick` itself) calling this again
                # is a harmless no-op, not a double-charge.
                self.scheduler.note_reply(now_sim, line)
