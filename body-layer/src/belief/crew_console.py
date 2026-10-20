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
detector exists.

**`silence`.** (`plans/silence-command/plan.md`, user direction
2026-10-04.) "Make Petrovich not talk until my next command" -- **absolute**:
nothing is spoken while silenced, not even an urgent threat callout, a
deliberate choice made after showing the user the consequence in those
terms. One fixed word acknowledges the command (`speech.render_silence_ack`),
then nothing else until a real command -- F10/voice token, or a free-text
utterance the grammar actually resolves -- ends it; stray speech recognised
as nothing does not. See `_handle_silence`'s own docstring for the full
account, including why `self.silenced` gates `_print`'s `speech_client` push
alone, never `output`/`overlay_client`.

**On the ground, Petrovich does not scan** (`plans/radio-check/plan.md`,
`[[BL-B82]]`, user direction 2026-10-19, replacing the `plans/
spu8-intercom/plan.md` Stage 5 on-ground silence default above). The gate
itself lives in `logger.py`'s two poll loops (ownship AGL against
`ON_GROUND_AGL_THRESHOLD_M`, below), not here -- this class only answers
for it: `self.on_ground`, set every poll the same way `enrichment` is,
makes `handle_command` answer any `_LOOK_COMMAND_TOKENS` member with
"Unable, on the ground." (understood, not doable) rather than dispatching
it, while every other command -- including `radio_check`/`greeting`,
`[[BL-B81]]` -- is heard and answered normally."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Final, Literal, TextIO

import tuning
from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.attack_run import AttackRunState
from belief.attack_run import decide as decide_attack_run
from belief.attention import _SECTOR_CENTER_DEG, SECTORS, RelativeSector, Sector
from belief.audio_client import AudioAdapterClient, AudioAdapterError
from belief.brain_reply import validate_brain_reply
from belief.callouts import (
    CALLOUT_GROUP_CLOCK_SPAN_HOURS,
    CalloutScheduler,
    group_facts,
    report_priority,
)
from belief.classification import AIR_DEFENSE_OP_CLASSES, parent_class_of
from belief.contacts import ContactStore
from belief.decay import OBSERVED_WINDOW_S
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
    render_attack_run_off,
    render_cancel_readback,
    render_clear,
    render_confirm_request,
    render_contact_report,
    render_disambiguation,
    render_engage_readback,
    render_greeting,
    render_group_full_disclosure,
    render_group_report,
    render_lost_contact,
    render_no_contact,
    render_no_view,
    render_radio_check,
    render_readback,
    render_report,
    render_report_summary,
    render_say_again,
    render_scan_readback,
    render_silence_ack,
    render_stand_by,
    render_target_readback,
    render_unable,
    render_watch_group_readback,
    render_watch_nearest_readback,
    route_event,
)
from belief.tasks import PendingIntent, TaskKind, TaskStore
from belief.tools import (
    _find_contact,
    attack_target_task,
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
from perception.gaze import RELATIVE_SECTORS, SECTOR_WEDGE_DEG
from perception.geometry import GeoPosition, angular_delta_deg, signed_angular_delta_deg
from perception.optics import Optic
from perception.source import OwnshipState

#: Below this altitude AGL in metres, Petrovich is treated as on the
#: ground: perception stops and a look command is refused rather than
#: dispatched -- too high false-grounds him during genuine low-level/NOE
#: flight, too low lets him scan while the aircraft is still sitting on
#: the ramp. Used by `logger.py`'s two poll loops and by
#: `CrewConsole.on_ground`/`_LOOK_COMMAND_TOKENS` above. A guessed
#: placeholder pending live-flight calibration -- same
#: debt class as `mission_phase.WAYPOINT_CAPTURE_RADIUS_M` -- since no
#: weight-on-wheels signal exists anywhere in this codebase; this is
#: `alt_agl_m` against a placeholder value, not a real ground-contact
#: sensor. Do not treat as validated. Wired through `tuning.py` by
#: `[[BL-B82]]` (review, 2026-10-19): it now gates perception in two poll
#: loops plus look-command refusal, not just a one-shot silence default,
#: so it earns the mechanism per root `CLAUDE.md`'s rule even though its
#: own value is unchanged.
ON_GROUND_AGL_THRESHOLD_M: Final[float] = tuning.real(
    "belief.crew_console.ON_GROUND_AGL_THRESHOLD_M",
    10.0,
    lo=0.5,
    hi=50.0,
    status="uncalibrated",
)

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

#: `[[BL-B81]]`'s typed-crew-text recognition for "radio check" and the
#: four greetings -- checked in `handle_line` before it falls through to
#: `_handle_utterance`/`parse_utterance`'s grammar, the same way
#: `!inject-urgent`/`!voice` are special-cased just above that call.
#: `parse_utterance`'s `_PatternRow` table is shaped around extracting and
#: resolving a contact *reference* (every row has a `ref` group); neither
#: of these commands references a contact, so they don't fit that grammar
#: and are matched here instead, directly against the two tokens
#: `handle_command` dispatches (`radio_check`/`greeting`).
_RADIO_CHECK_PATTERN = re.compile(r"^radio\s+check\.?$", re.IGNORECASE)
_GREETING_PATTERN = re.compile(
    r"^good\s+(morning|day|evening|night)\s+petrovich\.?$", re.IGNORECASE
)

#: `greeting`'s closed slot vocabulary -- `_handle_greeting`'s valid-value
#: check and `handle_line`'s own match both key off this one set.
_GREETING_TIMES_OF_DAY: frozenset[str] = frozenset(
    {"morning", "day", "evening", "night"}
)


def _match_radio_check_or_greeting(
    stripped: str,
) -> tuple[str, dict[str, int | str] | None] | None:
    """Returns `(token, slots)` for a typed "radio check" or greeting
    line, `None` for anything else -- `handle_line`'s own literal/regex
    check, kept as a plain function (no `self` needed) for the same
    reason `_describe_token_for_confirm` is one."""
    if _RADIO_CHECK_PATTERN.match(stripped):
        return "radio_check", None
    greeting_match = _GREETING_PATTERN.match(stripped)
    if greeting_match is not None:
        time_of_day = greeting_match.group(1).lower()
        return "greeting", {"time_of_day": time_of_day}
    return None


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
#: A local `_AIR_DEFENCE_OP_CLASSES` was declared here until 2026-10-11 --
#: a hand-enumerated copy, British spelling -- and is now
#: `belief.classification.AIR_DEFENSE_OP_CLASSES`, the one copy
#: (`BL-B51`). Its `<=` drift guard moved with it, from
#: `tests/test_crew_console.py` to `tests/test_classification.py`, so this
#: module's own tests no longer carry the only mechanism that could notice
#: `object_model` growing.
#:
#: **The reason this copy existed is recorded because it still holds**:
#: "which classes a *crew command* treats as air defence" is a
#: command-vocabulary question and not a property of the object model, so
#: `object_model` was the wrong home for it. The lattice module is the
#: right one -- the set is resolved through `parent_class_of`, which lives
#: there. A future `watch armour` would still declare its own set rather
#: than reaching into `object_model`.
#:
#: **`OP_LRSAM` was missing from this copy until 2026-09-24**, so "watch
#: nearest air defence" silently could not select an S-300 -- the one
#: emitter the vision calibration found visible out to 8.89 km, i.e. the
#: single contact this command most needed to return. That is the drift
#: `BL-B51` is about: the copy was written when `object_model`'s profile
#: table genuinely had no long-range SAM entry, and a set enumerated by
#: hand against another module's contents has no mechanism to notice when
#: that module grows.

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

#: `[[BL-B82]]`'s "look commands" -- tokens whose job is to direct a new
#: visual search, refused with "Unable, on the ground." while
#: `CrewConsole.on_ground` (`handle_command`, below). Every scan token
#: (all four families above plus `scan_bearing_deg`) plus `watch_nearest`/
#: `watch_nearest_air_defence`/`follow` -- the user's own two named
#: examples ("watch", "scan forward") plus the one other token that shares
#: their job exactly: `follow` is the one command that immediately raises
#: binoculars onto a target (`logger.py`'s "any command lowers binoculars"
#: glue reads `CrewConsole.last_command_target_contact_id`, which only
#: `follow` sets). Deliberately **excludes** `select_target`/`engage`/
#: `step`/every `report*` token -- those only read *existing* belief
#: (attention/priority flags, attack-run slotting) rather than directing a
#: new look, and already degrade sensibly ("no such contact") when belief
#: is thin from not having scanned, so they need no special-casing here.
_LOOK_COMMAND_TOKENS: frozenset[str] = frozenset(
    set(_RELATIVE_SCAN_TOKENS)
    | set(_BEARING_SCAN_TOKENS)
    | set(_CLOCK_SCAN_TOKENS)
    | {
        "scan_bearing_deg",
        "watch_nearest",
        "watch_nearest_air_defence",
        "follow",
    }
)

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

#: `_SECTOR_SCAN_LABELS` inverted -- the compass *word* a slotted
#: `report`'s `sector` slot carries (`audio_adapter.vocabulary.
#: SECTOR_WORDS`, this seam's hand-synced mirror) back onto the `Sector`
#: literal everything here already speaks. Derived rather than written out
#: a second time, so the two cannot drift from each other on this side;
#: `test_crew_console.py` asserts its membership against the eight words
#: audio-adapter sends, which is what catches a drift across the seam
#: (`plans/crew-query-path/plan.md` Decision E).
_SECTOR_FOR_WORD: dict[str, Sector] = {
    word: sector for sector, word in _SECTOR_SCAN_LABELS.items()
}

#: The slotted query's `how far` slot -> `(lo, hi)` slant-range bounds in
#: metres, from decision 12's own numbers: *near* < 2 km, *medium* 2-5 km,
#: *far* 5 km+. The 2 000 / 5 000 boundaries are **the only two constants
#: this feature introduces** besides `speech.REPORT_SUMMARY_MAX_WORDS`
#: (`plans/crew-query-path/plan.md`'s constant inventory) -- everything else
#: reuses a table or bound that already existed.
#:
#: **The band filters, it does not merely sort** (Q1, user 2026-10-08:
#: *"filter"*). A tank at 2.1 km goes unmentioned to a pilot who asked
#: about *near*; he can ask a wider band, and shorter answers were the
#: point of the whole feature.
#:
#: Hand-synced mirror of `audio_adapter.vocabulary.BAND_WORDS`' three band
#: names (Decision E) -- the spoken synonyms live on that side, since a
#: recogniser has no business knowing metres, and the numbers live here,
#: since the adapter has no business knowing ranges. Each side tests its
#: own table's membership.
_REPORT_BAND_BOUNDS_M: dict[str, tuple[float, float]] = {
    "near": (0.0, 2000.0),
    "medium": (2000.0, 5000.0),
    "far": (5000.0, float("inf")),
}

#: The spoken form of each band, for `speech.render_report_summary`'s
#: `band_label` -- *"inside 2 kilometres"* for a bounded band, *"beyond 5
#: kilometres"* for the open one. **Derived from `_REPORT_BAND_BOUNDS_M`
#: rather than written out**, so the number the summary says and the
#: number the filter applies cannot drift apart: a retuned boundary
#: changes both or neither. `crew_console` picking the label and `speech`
#: only formatting it is the division of labour `render_clear`/
#: `render_no_view` already follow.
_REPORT_BAND_LABELS: dict[str, str] = {
    band: (
        f"beyond {int(lo_m / 1000)} kilometres"
        if hi_m == float("inf")
        else f"inside {int(hi_m / 1000)} kilometres"
    )
    for band, (lo_m, hi_m) in _REPORT_BAND_BOUNDS_M.items()
}

#: At most this many groups are spoken in one report, joined into one
#: utterance (`plans/voice-command-completeness/plan.md` Decision 1b) --
#: an uncalibrated placeholder pending a live sortie's judgment on whether
#: three groups is useful or too long to sit through (that plan's
#: "Decisions Requiring User Input" item 3), isolated here so retuning it
#: never touches `_handle_report`'s own logic.
REPORT_MAX_GROUPS: Final[int] = 3


@dataclass(frozen=True, slots=True)
class ReportScope:
    """What one report is *about* -- `CrewConsole._report_scope`'s result
    (`plans/crew-query-path/plan.md` Decision B/C).

    `facts` is the in-scope contacts' `belief.tools` fact dicts, in
    `get_contacts` order (most-recently-seen first). The other two answer
    the question an *empty* `facts` raises, which is not the same question:
    `direction_label` is the lowercase spoken phrase for the direction
    asked about (`None` for a query that named no direction), and
    `rear_hemisphere` says whether that direction is one the cockpit mask
    makes unseeable -- in which case the honest answer is `render_no_view`
    rather than `render_clear`. Absence of belief is not absence of
    things."""

    facts: list[dict[str, object]]
    direction_label: str | None
    rear_hemisphere: bool


@dataclass(frozen=True, slots=True)
class _PendingPositionalReply:
    """One positional readback deferred because the channel was modeled
    busy at command time (Stage 6, `plans/voice-latency-instrumentation/
    plan.md`) -- the F8 2026-10-20 sortie's "several seconds pass... but
    this is several seconds late" finding, extended per the user's own
    "all of them" to every command whose readback states current belief
    about a position: `select_target`, `mark_target`, `step`, `follow`,
    `watch_nearest`/`watch_nearest_air_defence`, and the `report` family.

    `render` is a closure built by the handler that deferred it, over
    whatever that handler alone knows how to re-derive (a contact id already
    resolved and acted on, a report's own clock/sector/descriptor/relative/
    band, a mark function) -- so this class and
    `CrewConsole.drain_pending_positional_replies` need not know the shape
    of any one command's readback, only that calling `render(now_sim)` at a
    later tick reproduces it against *that* tick's belief, never the
    original command's. Every command's own **immediate, unconditional**
    side effects (resolving a target, registering a task, writing a mission-
    memory mark) already happened at command time, exactly as before --
    only the *speaking* of the readback is deferred."""

    correlation_id: str | None
    queued_since_sim: float
    render: Callable[[float], list[str]]


#: `descriptor_verdict`'s three outcomes. Named rather than booleans
#: because the middle one is the whole point: an unclassified contact is
#: neither a match nor a mismatch, and collapsing it onto either is what
#: this verdict exists to stop.
DescriptorVerdict = Literal["match", "unclassified", "wrong"]


def descriptor_verdict(descriptor: str, facts: dict[str, object]) -> DescriptorVerdict:
    """Whether `facts` answers to the spoken `descriptor` -- the shared
    three-way verdict behind both `follow`'s scoring and the slotted
    query's filtering (`plans/crew-query-path/plan.md` Decision B).

    Extracted from `CrewConsole._descriptor_score`, which now maps this
    verdict onto its weights and nothing else. **Both callers must read one
    predicate**: `report <descriptor>` and `follow <descriptor>` are the
    same resolution problem one step along -- same descriptor vocabulary,
    same lattice walk -- differing only in filter-versus-score, and D10's
    structured-candidate work is meant to improve this function rather than
    `_resolve_follow_target`, so that it improves both at once instead of
    improving one and diverging from the other (that plan's second-order
    effect 1).

    - `"match"` -- the held classification resolves, through `belief.
      classification.parent_class_of`, into the `OP_*` set this descriptor
      names. `"group"` is not a classification at all and keeps its own
      meaning: `cardinality.lo > 1`.
    - `"unclassified"` -- presence-level or no classification claim held.
      Decision 2b-iii's judgement, which D13's graceful-degradation rule
      repeats: *"he is pointing at a thing he believes is armour --
      matching it is right"*. So `follow` penalises it only lightly and
      the report **includes** it, hedged in the wording.
    - `"wrong"` -- a different, *known* class. Only this verdict excludes.
    """
    if descriptor == "group":
        cardinality = facts.get("cardinality")
        if isinstance(cardinality, dict):
            lo = cardinality.get("lo")
            if isinstance(lo, int) and lo > 1:
                return "match"
        # Deliberately `"wrong"`, not `"unclassified"`: cardinality is
        # always held (the lattice's root stands in for "no claim"), so a
        # contact that is not plural is positively not a group rather than
        # merely unresolved.
        return "wrong"
    classification = facts.get("classification")
    if not isinstance(classification, dict):
        return "unclassified"
    level = classification.get("level")
    if not isinstance(level, str) or level not in _KNOWN_CLASS_LEVELS:
        return "unclassified"
    value = classification.get("value")
    if not isinstance(value, str):
        return "unclassified"
    if parent_class_of(value) in _FOLLOW_DESCRIPTOR_OP_CLASSES.get(
        descriptor, frozenset()
    ):
        return "match"
    return "wrong"


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
    if token == "report":
        # The slotted crew query's readback (`plans/crew-query-path/
        # plan.md`), modelled on the `follow` branch above: compose the
        # heard slots back into the phrase the pilot would recognise as
        # his own, in the order decision 12 gives them -- *what*, *where*,
        # *how far*. A slot this version does not yet filter on is still
        # read back, because the confirm prompt's job is to expose a
        # mishearing, and hiding a word Petrovich heard would defeat it.
        report_parts: list[str] = []
        for slot_name in ("descriptor", "clock", "sector", "relative", "band"):
            value = slots.get(slot_name) if slots is not None else None
            if slot_name == "clock":
                if isinstance(value, int) and value in _CLOCK_REPORT_LABELS:
                    report_parts.append(f"{_CLOCK_REPORT_LABELS[value]} o'clock")
            elif isinstance(value, str):
                report_parts.append(value)
        return f"report {' '.join(report_parts)}" if report_parts else "report"
    if token == "select_target":
        # `select target <what> <where>` (`plans/attack-run/plan.md`
        # Decision 14) -- same composition shape as the `report` branch
        # above, for the identical reason: the confirm prompt's job is to
        # expose a mishearing, so every slot heard is read back.
        select_parts: list[str] = []
        for slot_name in ("descriptor", "clock", "sector", "relative", "band"):
            value = slots.get(slot_name) if slots is not None else None
            if slot_name == "clock":
                if isinstance(value, int) and value in _CLOCK_REPORT_LABELS:
                    select_parts.append(f"{_CLOCK_REPORT_LABELS[value]} o'clock")
            elif isinstance(value, str):
                select_parts.append(value)
        return (
            f"select target {' '.join(select_parts)}"
            if select_parts
            else "select target"
        )
    if token == "drop_target":
        return "drop target"
    if token == "step":
        # `step [<count>] left/right/near/far` (Decision 6) -- read back
        # the heard direction and count, the same "expose a mishearing"
        # job the other slotted branches above serve.
        direction = slots.get("direction") if slots is not None else None
        count = slots.get("count") if slots is not None else None
        parts = []
        if isinstance(count, int) and count > 1:
            parts.append(str(count))
        if isinstance(direction, str):
            parts.append(direction)
        return f"step {' '.join(parts)}" if parts else "step"
    if token == "engage":
        # `engage [<what> <where>] [weapon]` (Decision 15) -- same
        # composition shape as `select_target` above; the weapon slot is
        # read back too (it is accepted even though nothing consumes it).
        engage_parts: list[str] = []
        for slot_name in ("descriptor", "clock", "sector", "relative", "band"):
            value = slots.get(slot_name) if slots is not None else None
            if slot_name == "clock":
                if isinstance(value, int) and value in _CLOCK_REPORT_LABELS:
                    engage_parts.append(f"{_CLOCK_REPORT_LABELS[value]} o'clock")
            elif isinstance(value, str):
                engage_parts.append(value)
        return f"engage {' '.join(engage_parts)}" if engage_parts else "engage"
    if token == "disengage":
        return "disengage"
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
#: method actually branches on, `stop_talking`/`silence` included (each a
#: documented, deliberate no-readback-via-return-value no-op, not a gap --
#: both speak by calling `_print` themselves, inside their own handler,
#: rather than through `handle_command`'s shared tail call; see
#: `_handle_stop_talking`'s and `_handle_silence`'s own docstrings).
#: Excludes `wake_petrovich`/`cancel_nevermind`/`say_again` (handled above
#: `handle_command` entirely, per the module docstring -- this method
#: never even sees those three tokens) and `scan_bearing_deg`/
#: `report_bearing_deg` are included even though a missing
#: `slots["bearing_degrees"]` degrades them to a "say again" line rather
#: than raising, matching every other graceful-degradation branch in this
#: class. `test_crew_console.py` asserts every member of this set either
#: returns a non-empty result from `handle_command`, or is one of the two
#: documented no-return exceptions.
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
        # The slotted crew query (`plans/crew-query-path/plan.md`). Like
        # `scan_bearing_deg`/`report_bearing_deg` above it is included even
        # though every slot is optional: a zero-slot `report` is a legal
        # whole-scene query, and audio-adapter resolves a bare "report" to
        # `report_all` anyway, so this token only ever arrives with slots.
        "report",
        "watch_nearest",
        "watch_nearest_air_defence",
        "follow",
        # BL-14's standing attack-run target selection (`plans/attack-run/
        # plan.md` Decisions 2/14) -- `select_target` always returns a
        # readback or a "say again"/"no such contact" line; `drop_target`
        # delegates to `_handle_cancel_task`, which always returns
        # something (`_NOTHING_TO_STOP` at worst), so neither needs the
        # no-return-value exemption.
        "select_target",
        "drop_target",
        # Stage 4/5 of the same plan -- `step` always returns a readback
        # or an `"say again"`/`render_unable` line; `engage` always
        # returns a readback or a "no target selected"/"no such contact"
        # line; `disengage` always returns `render_attack_run_off`'s one
        # line unconditionally. None needs the no-return-value exemption.
        "step",
        "engage",
        "disengage",
        # `BL-B64` Stage 2, direction §6 -- "Observ on"/"Observ off".
        # `_handle_observ_on`/`_handle_observ_off` always return a
        # one-line readback unconditionally, so neither needs the
        # no-return-value exemption.
        "observ_on",
        "observ_off",
        "cancel_task",
        "cancel_scan",
        "cancel_watch",
        "stop_talking",
        "silence",
        # BL-8 Stage 3 (`plans/bl8-mission-memory/plan.md` Decision 6) --
        # `_handle_mark_here` always returns a readback or a "no mission
        # memory configured" line; `_handle_mark_target` additionally
        # returns "no target selected"/"no such contact" for the two
        # missing-input cases. Neither needs the no-return-value
        # exemption.
        "mark_here",
        "mark_target",
        # `[[BL-B81]]` -- the radio check / greeting, an ordinary command
        # like any other: `_handle_radio_check` always returns one fixed
        # line, `_handle_greeting` a readback or a "say again" line for a
        # missing/unrecognised `time_of_day` slot. Neither needs the
        # no-return-value exemption.
        "radio_check",
        "greeting",
    }
)

#: `handle_command`'s "this token's call returns `[]`, by design, never a
#: silent dispatch gap" set -- `test_dispatched_command_tokens_all_return_
#: something`'s own exemption list, pulled out as a named constant so the
#: test and `handle_command`'s early-return branches read the same
#: definition rather than two independently-maintained lists of two.
NO_RETURN_VALUE_COMMAND_TOKENS: frozenset[str] = frozenset({"stop_talking", "silence"})


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

#: `BL-15` Stage 3 (`plans/bl15-mission-start/plan.md`, user direction
#: 2026-10-19: *"On error loud refusal is better."*) -- the fixed line
#: every player command gets while `CrewConsole.refused` is set, i.e.
#: while the live mission's theatre could not be resolved to a loaded
#: world-model store. Deliberately a single literal string, not a
#: template: the user's own wording, verbatim, so a pilot who hears it
#: twice (voice, text, overlay) hears exactly the same words each time.
WORLD_MODEL_NOT_LOADED_REFUSAL: Final[str] = "system error, world model not loaded"


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
    #: BL-8 Stage 3 (`plans/bl8-mission-memory/plan.md` Decision 6) -- the
    #: commanded-mark path, injected as plain closures rather than a
    #: `mission_memory.store.MissionMemory` field: Decision 1's import
    #: direction forbids any module in `belief/` (this one included) from
    #: importing `mission_memory` at all, so `logger.py` (which sits
    #: outside `belief/` and may import both) builds these two closures
    #: over the live `MissionMemory` instance its poll loop writes
    #: observed entries into, and this console only ever sees a plain
    #: `str` readback in return -- the same "inject a callable, the caller
    #: builds it" shape `transcript_log`/`speech_log_sink` already use
    #: above. `mark_here_fn` takes `now_sim`; `mark_target_fn` takes
    #: `(contact_id, now_sim)`. `None` (the default, for every surface
    #: that is not `--crew-text`) means both mark commands report "no
    #: mission memory configured" rather than raising.
    mark_here_fn: Callable[[float], str] | None = None
    mark_target_fn: Callable[[str, float], str] | None = None
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
    #: `engage`/`disengage`'s one-shot signal to `logger.py`'s poll loop
    #: (`plans/attack-run/plan.md` Decision 2, Stage 5's wiring) --
    #: `AttackRunState` itself lives on `logger.ConsolePerceptionRunner`
    #: (beside `optic_state`), not on this class, the same division
    #: `drain_attack_run`'s own docstring already states; this class has
    #: no way to replace that state directly, so it leaves a narrow
    #: instruction here instead. Reset to `None` at the top of every
    #: `handle_command` dispatch (the same convention `last_command_
    #: target_contact_id` follows), and consumed-and-cleared by the poll
    #: loop the moment it is applied, so a command that is never repeated
    #: does not re-fire every poll thereafter.
    attack_run_transition: Literal["engage", "disengage"] | None = None
    #: "Observ on"/"Observ off"'s one-shot signal to `logger.py`'s poll
    #: loop -- `BL-B64` Stage 2, direction §6 (`docs/concept/9K113.md`'s
    #: "Observ" glossary: *"Turn on OBSERV in guidance unit, tell pilot
    #: 'Observ on'"*). The same division `attack_run_transition` already
    #: states just above: `OpticState.home_phase` lives on `logger.
    #: ConsolePerceptionRunner`, not here, so this class leaves a narrow
    #: instruction instead of mutating state it cannot reach. Reset to
    #: `None` at the top of every `handle_command` dispatch, same
    #: convention as `last_command_target_contact_id`/`attack_run_
    #: transition`, and consumed-and-cleared by the poll loop the moment
    #: it is applied.
    observ_transition: Literal["on", "off"] | None = None
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
    #:
    #: **Third parameter (Stage 5, `plans/attack-run/plan.md`)** --
    #: `attack_run_fields`, a plain dict (`None` for every non-attack-run
    #: line) carrying the attack-run target's contact id, tier, and
    #: current azimuth/elevation error, so a sortie's guidance lines are
    #: triaged from the log instead of recalled. `drain_attack_run` is the
    #: only caller that ever supplies it, and always for a single-line
    #: `_print` call -- see that method's own call site.
    #:
    #: **Four more parameters (Stage 3, `plans/voice-latency-instrumentation/
    #: plan.md`)** -- `correlation_id` (the command/transcript that
    #: produced this line, `None` for F10/typed dispatch and every line
    #: with no voice origin) and the `push_speech` call's own
    #: `time.monotonic()` bracket (`push_sent_wall`/`push_acked_wall`/
    #: `push_duration_s`, all `None` when nothing was pushed to
    #: `speech_client` at all) -- `_print` is what measures these, this
    #: callback only carries them to `write_speech`.
    speech_log_sink: (
        Callable[
            [
                str,
                bool,
                dict[str, object] | None,
                str | None,
                float | None,
                float | None,
                float | None,
            ],
            None,
        ]
        | None
    ) = None
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
    #: Stage 6, `plans/voice-latency-instrumentation/plan.md` -- positional
    #: readbacks deferred because the channel was modeled busy at command
    #: time, drained once per poll by `drain_pending_positional_replies`.
    #: Not in `reset_for_new_mission`'s "survives" list, so a mission
    #: restart resets it to `[]` for free (`__init__`'s default applies) --
    #: a deferred readback from a mission that just ended has nothing left
    #: to be current about.
    _pending_positional_replies: list[_PendingPositionalReply] = field(
        default_factory=list, repr=False
    )
    #: Set by `_handle_silence` while `silence` is in effect; cleared the
    #: moment any *other* command reaches `handle_command` or `_act`
    #: (`plans/silence-command/plan.md`, user direction 2026-10-04:
    #: "any subsequent command will end silence"). While `True`, `_print`
    #: never pushes to `speech_client` -- **absolute silence, including an
    #: injected urgent call** (`bypass_gate=True`), per the user's explicit
    #: choice: he was shown the risk in those terms (silenced near a
    #: friendly airbase, a Shilka opens up and says nothing) and chose
    #: absolute over "urgent still gets through" anyway. `output`
    #: (printed/crew-text) and `overlay_client` are deliberately **not**
    #: gated on this flag -- the use case is audio ("during radio
    #: traffic"), so the text/overlay surfaces keep working; only spoken
    #: audio goes quiet. `self.scheduler` keeps ticking normally while
    #: this is `True` (`drain_events` is unconditional) so belief events
    #: are still chosen, rendered and consumed at the scheduler's own
    #: pace -- **suppressed, not deferred**: nothing is held back to be
    #: dumped the moment silence ends, it is simply never voiced.
    silenced: bool = field(default=False, repr=False)

    #: `BL-15` Stage 3 -- set by `logger._enter_refusal_mode` when a
    #: mission-start event's live theatre could not be resolved to a
    #: loaded world-model store (unknown theatre, missing/unbuilt store, a
    #: failed open, a mismatched built region, or no `--world-model-dir`
    #: to resolve one from at all). While `True`, every player command
    #: this class dispatches (`handle_command`, `handle_line`,
    #: `handle_transcript`) is answered with the fixed
    #: `WORLD_MODEL_NOT_LOADED_REFUSAL` line instead of being acted on --
    #: see `_refusal_response`. Cleared by `logger._maybe_switch_theatre`
    #: the next time a mission (re)start resolves its theatre
    #: successfully; never cleared by `reset_for_new_mission` passing it
    #: through (it resets to `False` with the rest of per-mission state,
    #: same as every other non-preserved field -- `_check_for_new_mission`
    #: re-evaluates it immediately afterward via `_maybe_switch_theatre`,
    #: which sets it right back to `True` if the *new* mission's own
    #: theatre still fails to resolve).
    refused: bool = field(default=False, repr=False)

    #: `[[BL-B82]]` -- refreshed every poll (`logger.py`, the same place
    #: `enrichment` is refreshed) from `ownship.alt_agl_m <=
    #: ON_GROUND_AGL_THRESHOLD_M`. Read by `handle_command` to refuse a
    #: `_LOOK_COMMAND_TOKENS` member with "Unable, on the ground." --
    #: perception itself is gated in `logger.py`'s poll loops, not here;
    #: this field only decides what `handle_command` answers. Defaults to
    #: `True` (reviewer, `plans/radio-check/review.md`, 2026-10-19): before
    #: the first telemetry poll resolves this from real `OwnshipState`,
    #: "on the ground" is the safe assumption to refuse look commands
    #: under, the same direction `alt_agl_m`'s own `0.0` default already
    #: takes.
    on_ground: bool = field(default=True, repr=False)

    def reset_for_new_mission(self) -> None:
        """Give a clean slate on a genuine DCS mission (re)start (`BL-15`
        Stage 1, `plans/bl15-mission-start/plan.md`). Re-invokes `__init__`
        on this same object, passing through only the fields that must
        survive the reset -- the shared `store`/`tasks` references (their
        own `reset_for_new_mission()` must already have run before this
        call, via `_reset_mission_state`'s explicit ordering, the same
        reasoning as `logger.ConsolePerceptionRunner.reset_for_new_
        mission`), the injected collaborators (`brain_client`, `output`,
        `aircraft_client`, `mark_here_fn`, `mark_target_fn`, `transcript_
        log`, `overlay_client`, `speech_client`, `speech_log_sink`), and
        `silenced` -- whether a pilot's deliberate mute should survive a
        mission restart is an open product question (see the plan's
        "Decisions Requiring User Input"); until decided, this preserves it
        (the conservative default: don't change behaviour the pilot
        explicitly asked for). Everything else (`scheduler`, `_pending_
        confirmation`, `_confirmation_expired_sim`, `_pending_escalations`,
        `_stand_by_spoken_for`, `commands_handled`, `last_command_target_
        contact_id`, `attack_run_transition`, `observ_transition`,
        `on_ground`, `enrichment`, `refused`) resets to its declared
        default -- see `refused`'s own field docstring for why resetting
        it here is correct even though a mission (re)start is exactly the
        event that might need to set it right back. `on_ground` resetting
        to `True` is harmless either way: `logger._check_for_new_mission`
        re-evaluates it from live telemetry the very next poll, same as
        `enrichment`."""
        self.__init__(  # type: ignore[misc]
            store=self.store,
            tasks=self.tasks,
            brain_client=self.brain_client,
            output=self.output,
            aircraft_client=self.aircraft_client,
            mark_here_fn=self.mark_here_fn,
            mark_target_fn=self.mark_target_fn,
            transcript_log=self.transcript_log,
            overlay_client=self.overlay_client,
            speech_client=self.speech_client,
            speech_log_sink=self.speech_log_sink,
            silenced=self.silenced,
        )

    def _refusal_response(
        self, now_sim: float, correlation_id: str | None = None
    ) -> list[str] | None:
        """`BL-15` Stage 3's loud-refusal mode. `None` while `self.refused`
        is `False` -- the overwhelmingly common case -- so every caller's
        own dispatch logic runs unchanged; a non-`None` result is the
        fixed `WORLD_MODEL_NOT_LOADED_REFUSAL` line, already printed/
        pushed via `_print`, for the caller to return immediately without
        doing anything else.

        **Checked at the top of all three of this class's production
        entry points** (`handle_command`, `handle_line`, `handle_
        transcript`) rather than at one shared call site, because there
        is no single generic dispatcher all three already funnel through:
        F10 selections and a committed voice "act" disposition reach
        `handle_command` directly; typed crew-text and voice's
        "fallthrough" disposition reach `handle_line` directly (the latter
        via `_act_on_voice_decision`, not through `handle_command` first);
        voice itself enters through `handle_transcript`, which may act,
        confirm, say-again, or fall through without ever calling the other
        two. The same check, the same fixed string, at each, is the
        actual single source of truth here -- not a single call site."""
        if not self.refused:
            return None
        lines = [WORLD_MODEL_NOT_LOADED_REFUSAL]
        self._print(lines, now_sim, correlation_id=correlation_id)
        return lines

    def handle_line(self, line: str, now_sim: float) -> list[str]:
        stripped = line.strip()
        if not stripped:
            return []
        refusal = self._refusal_response(now_sim)
        if refusal is not None:
            return refusal
        if stripped.startswith("!inject-urgent"):
            lines, bypass_gate = self._handle_inject_urgent(stripped, now_sim)
            self._print(lines, now_sim, bypass_gate=bypass_gate)
            return lines
        if stripped.startswith("!voice"):
            return self._handle_voice_test_command(stripped, now_sim)
        # `[[BL-B81]]`: typed "radio check" / greeting routes straight to
        # `handle_command` -- the single dispatcher -- same as voice's
        # "act" disposition already does, rather than through
        # `_handle_utterance`'s contact-reference grammar, which has no
        # row shaped for a reference-less command (see
        # `_match_radio_check_or_greeting`'s own docstring).
        radio_check_or_greeting = _match_radio_check_or_greeting(stripped)
        if radio_check_or_greeting is not None:
            token, slots = radio_check_or_greeting
            return self.handle_command(token, now_sim, slots=slots)
        lines = self._handle_utterance(stripped, now_sim)
        self._print(lines, now_sim, bypass_gate=False)
        return lines

    def drain_events(self, now_sim: float) -> list[str]:
        """Speak at most one currently-unacknowledged event, chosen and
        rendered fresh from current belief by `self.scheduler.tick`
        (`belief.callouts.CalloutScheduler`, see that module's docstring
        and `_print`'s docstring). Called once per poll from `logger.py`'s
        `--crew-text` loop, after `ContactStore.tick()`.

        Passes the current attack-run target's contact id, if any
        (`plans/attack-run/plan.md` Decision 5), so the scheduler can
        suppress `_WATCHED_ONLY_KINDS` events about that one contact --
        the struck range countdown chief among them -- for the run's
        duration, without this method needing to know why.

        **`BL-15` Stage 3 fix: no proactive speech while `self.refused`.**
        Today's call graph only ever reaches refusal mode immediately
        after a full reset (`ContactStore` empty, nothing to drain), which
        makes this guard currently incidental rather than load-bearing --
        see the review that required it (`plans/bl15-mission-start/
        review.md`, Batch 2 "(a)") for why that was not good enough on its
        own. `self.scheduler.tick` still runs (so any event does get
        consumed out of the store rather than piling up to be spoken
        stale once refusal clears), its result is just never reached by
        `_print` or returned to the caller -- drain and discard, not leave
        queued."""
        target_task = self._active_attack_target_task()
        attack_run_target_contact_id = (
            target_task.contact_id if target_task is not None else None
        )
        spoken = self.scheduler.tick(
            self.store,
            now_sim,
            self.enrichment,
            attack_run_target_contact_id=attack_run_target_contact_id,
        )
        if self.refused:
            return []
        # A scheduler-drained line never carries `bypass_gate=True` (only an
        # injected `UrgentCall`, routed through `handle_line`'s
        # `!inject-urgent` branch, does) -- see `_print`'s docstring.
        self._print(spoken, now_sim, bypass_gate=False)
        return spoken

    def _speak_or_defer(
        self,
        now_sim: float,
        correlation_id: str | None,
        render: Callable[[float], list[str]],
    ) -> list[str]:
        """Speak `render(now_sim)` now if the channel is modeled clear;
        otherwise defer it to `drain_pending_positional_replies`, to be
        re-rendered at *that* later tick's own `now_sim` (Stage 6, `plans/
        voice-latency-instrumentation/plan.md`) -- the one piece shared by
        every positional readback (`select_target`, `mark_target`, `step`,
        `follow`, `watch_nearest`/`watch_nearest_air_defence`, the `report`
        family), so each only has to say *how* to re-render itself, never
        *whether* to.

        Returns `render`'s own lines when spoken now (the caller's existing
        `_print` call, via `handle_command`'s tail, is what actually speaks
        them -- this method only decides timing), or `[]` when deferred --
        indistinguishable, from `handle_command`'s own perspective, from any
        other command whose readback happens to be empty."""
        if now_sim >= self.scheduler.busy_until_sim:
            return render(now_sim)
        self._pending_positional_replies.append(
            _PendingPositionalReply(
                correlation_id=correlation_id,
                queued_since_sim=now_sim,
                render=render,
            )
        )
        return []

    def drain_pending_positional_replies(self, now_sim: float) -> list[str]:
        """Speaks every deferred positional readback whose queueing
        command's channel-busy delay has now cleared (Stage 6, `plans/
        voice-latency-instrumentation/plan.md`) -- the F8 2026-10-20
        sortie's finding (*"current information, not old. Though the real
        problem here is the many second delay"*). Called once per poll from
        `logger.py`, alongside `drain_events`/`drain_brain`.

        Entries are checked in queued order, and a spoken entry's own
        `_print` call can itself re-claim the channel (`note_reply`) --
        checked fresh on every iteration, not cached from the top of this
        method, so a later entry in the same poll correctly finds the
        channel busy again and keeps waiting rather than being spoken out
        of turn. No attempt is made to force every pending entry out in one
        poll regardless of occupancy; that would defeat the mechanism this
        method exists to serve.

        **`BL-15` Stage 3's same posture as `drain_events`/`drain_brain`:
        no proactive speech while `self.refused`** -- every currently
        pending entry is dropped rather than held, since a readback about a
        world model that was just unloaded would be speech about nothing
        this console can still vouch for; a mission (re)start would have
        reset this list anyway."""
        if self.refused:
            self._pending_positional_replies = []
            return []
        still_pending: list[_PendingPositionalReply] = []
        spoken: list[str] = []
        for entry in self._pending_positional_replies:
            if now_sim < self.scheduler.busy_until_sim:
                still_pending.append(entry)
                continue
            lines = entry.render(now_sim)
            self._print(lines, now_sim, correlation_id=entry.correlation_id)
            spoken.extend(lines)
        self._pending_positional_replies = still_pending
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
        synchronous poll, like the other three).

        **`BL-15` Stage 3 fix: no proactive speech while `self.refused`.**
        `self.brain_client.poll_replies()` is still drained -- a reply
        left queued in the brain client here would otherwise surface
        later, once refusal clears, as speech about a world model it was
        never computed against -- but each reply is only popped from
        `_pending_escalations`/`_stand_by_spoken_for`, **not** run through
        `_handle_brain_reply`. That method calls `self._print`
        unconditionally and, via `_handle_brain_pick`/`_handle_brain_
        confirm`, can call `self._act` -- both real side effects discarding
        a return value does not undo, so it cannot be reused here without
        defeating the guard it is meant to enforce. `_speak_stand_by_if_
        due` is skipped entirely for the same reason (nothing is "overdue"
        worth announcing while refused). Drain and discard, matching
        `drain_events`'s identical choice -- see the review that required
        this (`plans/bl15-mission-start/review.md`, Batch 2 "(a)")."""
        if self.refused:
            try:
                replies = self.brain_client.poll_replies()
            except Exception:
                logger.warning("brain reply poll failed (continuing)", exc_info=True)
                return []
            for reply in replies:
                self._pending_escalations.pop(reply.utterance_id, None)
                self._stand_by_spoken_for.discard(reply.utterance_id)
            return []
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
        correlation_id: str | None = None,
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
        been heard at all.

        `correlation_id` (Stage 3, `plans/voice-latency-instrumentation/
        plan.md`) identifies which recognised transcript produced this
        dispatch -- `None` for F10/typed-console dispatch and a committed
        confirm-band answer alike, unchanged behaviour. Threaded to every
        positional-readback handler (Stage 6) so a readback deferred
        because the channel was modeled busy can still be joined back to
        the command that asked for it once it is actually spoken."""
        # `BL-15` Stage 3: checked first, before anything else this method
        # does -- while refused, nothing is dispatched, nothing counts
        # as a command for `commands_handled`/silence-ending purposes,
        # and no per-dispatch state (`last_command_target_contact_id`/
        # `attack_run_transition`/`observ_transition`) is touched. The
        # pilot gets exactly the fixed line and nothing else happens.
        refusal = self._refusal_response(now_sim, correlation_id=correlation_id)
        if refusal is not None:
            return refusal
        self._note_player_command()
        # Reset before dispatch -- see `last_command_target_contact_id`'s
        # own docstring for why a stale value from an earlier `follow`
        # must not leak into this command's evaluation.
        self.last_command_target_contact_id = None
        # Same reset, same reason -- `attack_run_transition`'s own
        # docstring -- so a stale `"engage"`/`"disengage"` from an earlier
        # dispatch this poll loop has not yet consumed cannot leak into an
        # unrelated later command's evaluation this same poll.
        self.attack_run_transition = None
        # Same reset, same reason, for OBSERV (`observ_transition`'s own
        # docstring).
        self.observ_transition = None
        if token == "silence":
            # Checked *before* the general `self.silenced = False` reset
            # below, and dispatched before it -- `_handle_silence` is the
            # one place that needs to see whether silence was already in
            # effect (its own no-op-when-already-silent rule).
            self._handle_silence(now_sim)
            return []
        # Any other recognised command ends silence (`plans/
        # silence-command/plan.md`, "any subsequent command will end
        # silence") -- including a token this method has no dispatch
        # behaviour for (the `else` branch below): the player still
        # issued *something* command-shaped, which is the distinction
        # that matters here, not whether this class happens to act on it.
        self.silenced = False
        # `[[BL-B82]]`: a look command on the ground is heard and
        # understood -- it already ended silence, above, like any other
        # command -- but not dispatched; perception is not running
        # (`logger.py`'s poll-loop gate), so a `scan`/`watch`/`follow`
        # here would register a task that can never be fulfilled. This is
        # the "unable", not "say again", half of that distinction: the
        # command was heard fine, it just cannot be done right now.
        if self.on_ground and token in _LOOK_COMMAND_TOKENS:
            lines = [render_unable("ON_GROUND").text]
            self._print(lines, now_sim, correlation_id=correlation_id)
            return lines
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
            lines = self._handle_watch_nearest(now_sim, correlation_id=correlation_id)
        elif token == "watch_nearest_air_defence":
            lines = self._handle_watch_nearest(
                now_sim, air_defence_only=True, correlation_id=correlation_id
            )
        elif token == "follow":
            lines = self._handle_follow(now_sim, slots, correlation_id=correlation_id)
        elif token == "select_target":
            lines = self._handle_select_target(
                now_sim, slots, correlation_id=correlation_id
            )
        elif token == "drop_target":
            lines = self._handle_drop_target()
        elif token == "step":
            lines = self._handle_step(now_sim, slots, correlation_id=correlation_id)
        elif token == "engage":
            lines = self._handle_engage(now_sim, slots)
        elif token == "disengage":
            lines = self._handle_disengage()
        elif token == "mark_here":
            lines = self._handle_mark_here(now_sim)
        elif token == "mark_target":
            lines = self._handle_mark_target(now_sim, correlation_id=correlation_id)
        elif token == "observ_on":
            lines = self._handle_observ_on()
        elif token == "observ_off":
            lines = self._handle_observ_off()
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
            lines = self._handle_report(now_sim, correlation_id=correlation_id)
        elif token in _CLOCK_REPORT_TOKENS:
            lines = self._handle_report(
                now_sim,
                clock=_CLOCK_REPORT_TOKENS[token],
                correlation_id=correlation_id,
            )
        elif token in _BEARING_REPORT_TOKENS:
            lines = self._handle_report(
                now_sim,
                sector=_BEARING_REPORT_TOKENS[token],
                correlation_id=correlation_id,
            )
        elif token == "report_bearing_deg":
            if bearing_degrees is None:
                lines = ["say again -- no bearing heard"]
            else:
                lines = self._handle_report(
                    now_sim,
                    sector=_nearest_sector(bearing_degrees),
                    correlation_id=correlation_id,
                )
        elif token == "report":
            lines = self._handle_slotted_report(
                now_sim, slots, correlation_id=correlation_id
            )
        elif token == "radio_check":
            lines = self._handle_radio_check()
        elif token == "greeting":
            lines = self._handle_greeting(slots)
        else:
            logger.warning("no dispatch behaviour for command token %r", token)
            return []
        self._print(lines, now_sim, correlation_id=correlation_id)
        return lines

    def _believed_air_defence(self, facts: dict[str, object]) -> bool:
        """Whether this contact is *believed* to be air defence -- the
        predicate behind the F10 "Watch -> Nearest Air Defence" item.

        **Reads the folded classification belief, never DCS ground truth**
        (this project's no-omniscience invariant, `belief.percept`'s module
        docstring). A contact is air defence here only if Petrovich's held
        claim has actually resolved that far: the claim's lattice level must
        be `class` or `type` (`_KNOWN_CLASS_LEVELS`), and its value must
        resolve through `belief.classification.parent_class_of` into that
        module's `AIR_DEFENSE_OP_CLASSES` (the one copy, `BL-B51`).

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
        return parent_class_of(value) in AIR_DEFENSE_OP_CLASSES

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

    def _mark_watched_with_group(
        self, now_sim: float, contact_id: str, *, source: str = "player"
    ) -> tuple[bool, int]:
        """Marks `contact_id` watched, and -- sortie 2026-10-05 debrief,
        Item 3 (*"follow/watch group <where> should tag all units in that
        group as watched"*) -- every other member of its `belief.groups.
        Group`, if it is part of one with more than one member. Shared by
        `_handle_watch_nearest` and `_handle_follow`: both already resolve
        to exactly one winning `contact_id` before this is called, so the
        group-tagging step is identical regardless of how that id was
        picked.

        **Static, one-time tag, not a standing "watched group" concept**
        (settled by the user, 2026-10-05: *"Tag once, static."*). Members
        at the moment of this call become watched; a unit that joins the
        group afterwards is not watched, one that leaves stays watched --
        no new state, no watch-to-group identity binding, nothing to
        maintain as `belief.groups.GroupStore` reconciles the group across
        later polls. This deliberately does **not** key off the F10/voice
        descriptor word `"group"` (`_descriptor_score`'s own `"group"`
        branch, a classification match on `cardinality.lo > 1`) -- that is
        a different concept (`belief.cardinality`, a single contact's own
        estimated unit count) from `belief.groups.Group` (a set of
        separately-tracked contacts). This keys off whichever contact the
        resolver actually picked, through `self.store.group_for_contact`,
        exactly as `render_report`'s existing group-disclosure roll-up
        already does (above, `self.store.group_for_contact(contact_id)`).

        Returns `(found, marked)`: `found` is whether the resolved
        `contact_id` itself was marked (the caller's existing "no such
        contact" check keys off this, unchanged); `marked` is the count of
        members **actually** marked -- not `len(member_ids)`, the intended
        count. `Group.member_contact_ids` is recomputed from the live
        `Contact` set by `belief.groups.GroupStore.reconcile`, so between a
        reconcile and this command a member id can stop resolving to a live
        contact; `set_attention`/`watch_contact_task` then return `False`
        for it, nothing is watched, and speaking `len(member_ids)` would
        assert a count the code never verified (security review,
        2026-10-05, finding 1 -- the pilot cannot observe it, because the
        un-tagged member simply never reports). Counting successes means a
        group that lost members since the last reconcile falls back to the
        single-contact readback rather than overstating, which is the rule
        `render_group_disclosure` already applies to the same group
        (`belief.speech`: `None` unless at least two members resolve)."""
        belief_group = self.store.group_for_contact(contact_id)
        member_ids: frozenset[str]
        if belief_group is not None and len(belief_group.member_contact_ids) > 1:
            member_ids = belief_group.member_contact_ids
        else:
            member_ids = frozenset({contact_id})
        found = False
        marked = 0
        for member_id in member_ids:
            if self.tasks is not None:
                task = watch_contact_task(
                    self.store, self.tasks, member_id, now_sim, source=source
                )
                ok = task is not None
            else:
                ok = set_attention(self.store, member_id, "watch", source=source)
            if ok:
                marked += 1
            if member_id == contact_id:
                found = ok
        return found, marked

    def _handle_watch_nearest(
        self,
        now_sim: float,
        *,
        air_defence_only: bool = False,
        correlation_id: str | None = None,
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
        cancellable.

        **Tags every member of the winning contact's `belief.groups.Group`
        watched, once, if it has more than one** (`_mark_watched_with_
        group`, sortie 2026-10-05 debrief, Item 3) -- the readback then
        names the group case distinctly (`render_watch_group_readback`)
        rather than the single-contact one.

        **The readback is deferred, not the selection** (Stage 6, `plans/
        voice-latency-instrumentation/plan.md`): `contact_id` is resolved
        and marked watched immediately and unconditionally, exactly as
        before; only the *speaking* of the readback waits for the channel
        if it is modeled busy, and is then re-rendered against belief at
        that later tick -- see `CrewConsole._speak_or_defer`."""
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
        found, marked = self._mark_watched_with_group(now_sim, contact_id)
        result = describe_contact(
            self.store, contact_id, now_sim, enrichment=self.enrichment
        )
        if not found or result is None:
            return [f"no such contact: {contact_id}"]

        def _render(render_now_sim: float) -> list[str]:
            if marked > 1:
                return [render_watch_group_readback(marked).text]
            redone = describe_contact(
                self.store, contact_id, render_now_sim, enrichment=self.enrichment
            )
            if redone is None:
                return [render_lost_contact().text]
            return [render_watch_nearest_readback(redone["facts"]).text]

        return self._speak_or_defer(now_sim, correlation_id, _render)

    def _descriptor_score(self, descriptor: str, facts: dict[str, object]) -> float:
        """The descriptor term of `_resolve_follow_target`'s score --
        `0.0` on an exact match, `W_FOLLOW_DESC_UNKNOWN` when the contact
        is presence-level/unclassified (Decision 2b-iii: "he is pointing
        at a thing he *believes* is armour -- matching it is right"),
        `W_FOLLOW_DESC_WRONG` when it is a *different*, known class.

        **The verdict itself now lives in the module-level `descriptor_
        verdict`**, shared with the slotted query's filter (`plans/
        crew-query-path/plan.md` Decision B) -- this method is the
        verdict-to-weight mapping and nothing else. Do not reintroduce the
        lattice walk here; see that function's docstring for why one
        predicate rather than two."""
        verdict = descriptor_verdict(descriptor, facts)
        if verdict == "match":
            return 0.0
        if verdict == "unclassified":
            return W_FOLLOW_DESC_UNKNOWN
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
        self,
        now_sim: float,
        slots: dict[str, int | str] | None,
        correlation_id: str | None = None,
    ) -> list[str]:
        """`follow [<descriptor>] [<clock> o'clock] [<n> km]` -- resolves
        via `_resolve_follow_target` and, on a win, watches exactly the
        same way `_handle_watch_nearest` does (`_mark_watched_with_group`:
        a cancellable task per member when `self.tasks` is configured, a
        bare `set_attention` per member otherwise; every member of the
        resolved contact's `belief.groups.Group` gets tagged watched, once,
        statically, if it has more than one -- sortie 2026-10-05 debrief,
        Item 3), with the identical readback shape
        (`render_watch_nearest_readback`/`render_watch_group_readback`) --
        the player named no id either way, so the two commands describe
        their winner identically.

        **The readback is deferred, not the resolution** (Stage 6, `plans/
        voice-latency-instrumentation/plan.md`) -- see `_handle_watch_
        nearest`'s identical note."""
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
        found, marked = self._mark_watched_with_group(now_sim, contact_id)
        result = describe_contact(
            self.store, contact_id, now_sim, enrichment=self.enrichment
        )
        if not found or result is None:
            return [f"no such contact: {contact_id}"]

        def _render(render_now_sim: float) -> list[str]:
            if marked > 1:
                return [render_watch_group_readback(marked).text]
            redone = describe_contact(
                self.store, contact_id, render_now_sim, enrichment=self.enrichment
            )
            if redone is None:
                return [render_lost_contact().text]
            return [render_watch_nearest_readback(redone["facts"]).text]

        return self._speak_or_defer(now_sim, correlation_id, _render)

    def _resolve_attack_target(
        self,
        now_sim: float,
        descriptor: str | None,
        clock: int | None,
        sector: Sector | None,
        relative: RelativeSector | None,
        band: str | None,
    ) -> tuple[str | None, list[str]]:
        """`select target <what> <where>`'s own tie-break (`plans/
        attack-run/plan.md` Decision 14): units matching `<what>`/
        `<where>`, **watched beats unwatched, then closest**.

        **Does not reuse `_resolve_follow_target`** -- that resolver's own
        docstring forbids it ("a stopgap... delete the resolver and these
        constants with it; do not tune them as if they modelled anything
        real"). Its weighted score plus `FOLLOW_SEPARATION` ambiguity
        refusal is a different rule from the spec's own tie-break. Candidate
        set and `<where>` filtering instead reuse `_report_scope` directly,
        exactly as `_handle_report` does -- the same five-slot schema
        (`descriptor`/`clock`/`sector`/`relative`/`band`) `BL-13` Stage 1
        already parses.

        Refusing as ambiguous (the `follow` family's own answer to a tie)
        would be wrong here: `step` is the spec's own correction mechanism,
        so picking one and letting the pilot step is strictly better than a
        "say again"."""
        if self.enrichment is None:
            return None, ["no world-model connection configured"]
        scope = self._report_scope(
            now_sim,
            clock=clock,
            sector=sector,
            descriptor=descriptor,
            relative=relative,
            band=band,
        )
        if not scope.facts:
            return None, [render_no_contact().text]

        def _range_m(facts: dict[str, object]) -> float:
            relative_now = facts.get("relative_now")
            assert isinstance(relative_now, dict)
            range_m = relative_now["range_m"]
            assert isinstance(range_m, float)
            return range_m

        def _is_watched(facts: dict[str, object]) -> bool:
            return facts.get("attention") in ("watch", "priority")

        winner = min(
            scope.facts, key=lambda facts: (not _is_watched(facts), _range_m(facts))
        )
        contact_id = winner["id"]
        assert isinstance(contact_id, str)
        return contact_id, []

    def _parse_target_slots(
        self, slots: dict[str, int | str] | None
    ) -> tuple[
        str | None, int | None, Sector | None, RelativeSector | None, str | None
    ]:
        """`select target <what> <where>`'s five slots, validated against
        the exact tables that own their values -- the identical validation
        `_handle_slotted_report` already performs for `report`'s own
        five-slot schema, duplicated rather than shared: the two commands'
        slot shapes happen to coincide today, but nothing ties them
        together, and sharing a private helper across two independent
        commands would make a future divergence between them silent."""
        descriptor: str | None = None
        clock: int | None = None
        sector: Sector | None = None
        relative: RelativeSector | None = None
        band: str | None = None
        if slots is not None:
            raw_descriptor = slots.get("descriptor")
            if isinstance(raw_descriptor, str) and (
                raw_descriptor in _FOLLOW_DESCRIPTOR_OP_CLASSES
                or raw_descriptor == "group"
            ):
                descriptor = raw_descriptor
            raw_clock = slots.get("clock")
            if isinstance(raw_clock, int) and raw_clock in _CLOCK_REPORT_LABELS:
                clock = raw_clock
            raw_sector = slots.get("sector")
            if isinstance(raw_sector, str):
                sector = _SECTOR_FOR_WORD.get(raw_sector)
            raw_relative = slots.get("relative")
            if isinstance(raw_relative, str) and raw_relative in RELATIVE_SECTORS:
                relative = raw_relative
            raw_band = slots.get("band")
            if isinstance(raw_band, str) and raw_band in _REPORT_BAND_BOUNDS_M:
                band = raw_band
        return descriptor, clock, sector, relative, band

    def _handle_select_target(
        self,
        now_sim: float,
        slots: dict[str, int | str] | None,
        correlation_id: str | None = None,
    ) -> list[str]:
        """`select|set target <what> <where>` (`plans/attack-run/plan.md`
        Decision 14) -- resolves via `_resolve_attack_target`, then sets
        the winner's own attention to `"priority"` and registers the
        standing `attack_target` task (`tools.attack_target_task`,
        Decision 2). Every *other* member of the winner's `belief.groups.
        Group`, if it has more than one, gets the ordinary one-time
        `"watch"` tag (Decision 5's own split: only the selected target
        itself reaches `"priority"` -- its group-mates get the same static
        tag a plain `watch` already gives a group, never overridden back to
        `"watch"` on the target itself, which is why this does not simply
        call `_mark_watched_with_group`).

        **The readback is deferred, not the selection** (Stage 6, `plans/
        voice-latency-instrumentation/plan.md` -- the F8 2026-10-20 sortie
        finding this stage exists to fix): resolving the target and
        registering the task above are unconditional, exactly as before;
        only the *speaking* of the readback waits for a modeled-busy
        channel and is then re-rendered against belief at that later tick."""
        descriptor, clock, sector, relative, band = self._parse_target_slots(slots)
        if (
            descriptor is None
            and clock is None
            and sector is None
            and relative is None
            and band is None
        ):
            return ["say again -- select target needs what and/or where"]
        if self.enrichment is None:
            return ["no world-model connection configured"]
        if self.tasks is None:
            return ["no task store configured"]

        contact_id, no_match_lines = self._resolve_attack_target(
            now_sim, descriptor, clock, sector, relative, band
        )
        if contact_id is None:
            return no_match_lines

        task = attack_target_task(
            self.store, self.tasks, contact_id, now_sim, descriptor=descriptor
        )
        if task is None:
            return [f"no such contact: {contact_id}"]

        belief_group = self.store.group_for_contact(contact_id)
        if belief_group is not None and len(belief_group.member_contact_ids) > 1:
            for member_id in belief_group.member_contact_ids:
                if member_id == contact_id:
                    continue
                watch_contact_task(
                    self.store, self.tasks, member_id, now_sim, source="attack_target"
                )

        result = describe_contact(
            self.store, contact_id, now_sim, enrichment=self.enrichment
        )
        if result is None:
            return [f"no such contact: {contact_id}"]

        def _render(render_now_sim: float) -> list[str]:
            redone = describe_contact(
                self.store, contact_id, render_now_sim, enrichment=self.enrichment
            )
            if redone is None:
                return [render_lost_contact().text]
            return [render_target_readback(redone["facts"]).text]

        return self._speak_or_defer(now_sim, correlation_id, _render)

    def _handle_drop_target(self) -> list[str]:
        """`drop target` (`plans/attack-run/plan.md` Decision 2) -- ends
        the run and deselects, scoped to the one `attack_target` task kind
        rather than `_handle_cancel_task`'s all-modes form. The existing
        cancel/stop path (`cancel_task`'s bare `kinds=None` form) also
        deselects, for free -- it cancels every active task of every kind,
        `attack_target` included."""
        return self._handle_cancel_task(kinds=("attack_target",))

    def _handle_mark_here(self, now_sim: float) -> list[str]:
        """`mark here` (`plans/bl8-mission-memory/plan.md` Decision 6) --
        mark ownship's current position. `self.mark_here_fn` is
        `logger.py`'s own closure over the live `mission_memory.store.
        MissionMemory`; this console never imports that package directly
        (`mark_here_fn`'s own field docstring)."""
        if self.mark_here_fn is None:
            return ["no mission memory configured"]
        return [self.mark_here_fn(now_sim)]

    def _handle_mark_target(
        self, now_sim: float, correlation_id: str | None = None
    ) -> list[str]:
        """`mark target` (`plans/bl8-mission-memory/plan.md` Decision 6) --
        mark the currently selected attack-run target's believed position,
        reusing `select_target`'s own notion of "the current target"
        (`_active_attack_target_task`). The "no target selected" failure
        is the exact wording every other target-keyed command already
        uses for the same missing input (`_handle_step`'s own check).

        **The mark itself is deferred when the channel is modeled busy**
        (Stage 6, `plans/voice-latency-instrumentation/plan.md`), not only
        its spoken acknowledgement -- unlike every other command in this
        family, the readback *is* the only record of "current information"
        here (`mark_target_fn`'s own text carries no position), so what
        actually needs to reflect the later tick's belief is the mark
        write itself: `_mark_target_fn`/`mission_memory.marks.mark_target`
        reads the contact's position **at the `now_sim` they are called
        with**, so deferring the call (not just rendering stale text around
        an already-made one) is what "current information, not old" means
        for this command specifically."""
        if self.mark_target_fn is None:
            return ["no mission memory configured"]
        mark_target_fn = self.mark_target_fn
        target_task = self._active_attack_target_task()
        if target_task is None or target_task.contact_id is None:
            return ["no target selected"]
        contact_id = target_task.contact_id

        def _render(render_now_sim: float) -> list[str]:
            return [mark_target_fn(contact_id, render_now_sim)]

        return self._speak_or_defer(now_sim, correlation_id, _render)

    def _active_attack_target_task(self) -> PendingIntent | None:
        """The currently active `attack_target` task, or `None` -- shared
        by `_handle_step`/`_handle_engage`/`drain_attack_run`/
        `drain_events`, every one of which needs "what the player has
        selected," not merely its id. `None` when `self.tasks` is unset
        (mirrors every other optional-task-store degradation in this
        class)."""
        if self.tasks is None:
            return None
        return next(
            (
                task
                for task in self.tasks.tasks
                if task.kind == "attack_target" and task.status != "cancelled"
            ),
            None,
        )

    def _step_candidates(
        self, now_sim: float, target_id: str, descriptor: str | None
    ) -> list[str]:
        """The candidate set `step` orders over (`plans/attack-run/
        plan.md` Decision 6) -- `target_id`'s own `belief.groups.Group`
        (`store.group_for_contact`), filtered by `descriptor` via the
        shared `descriptor_verdict`, dropping only `"wrong"` (an
        unclassified contact stays a candidate, the identical reasoning
        `_descriptor_score` already applies for `follow`). `[target_id]`
        alone when ungrouped or `descriptor is None` with no group --
        `_handle_step` is what turns "the only candidate is the current
        target itself" into `render_unable("NO_GROUP_MEMBERS")`, not this
        method, which only ever reports what exists."""
        belief_group = self.store.group_for_contact(target_id)
        if belief_group is None or len(belief_group.member_contact_ids) <= 1:
            return [target_id]
        if descriptor is None:
            return list(belief_group.member_contact_ids)
        candidates: list[str] = []
        for member_id in belief_group.member_contact_ids:
            result = describe_contact(
                self.store, member_id, now_sim, enrichment=self.enrichment
            )
            if result is None:
                continue
            if descriptor_verdict(descriptor, result["facts"]) != "wrong":
                candidates.append(member_id)
        return candidates

    def _handle_step(
        self,
        now_sim: float,
        slots: dict[str, int | str] | None,
        correlation_id: str | None = None,
    ) -> list[str]:
        """`step [<count>] left/right/near/far` (`plans/attack-run/
        plan.md` Decision 6) -- re-orders the current attack-run target's
        own group, **angularly around the bearing from ownship's present
        position to the current target, recomputed at every press** (for
        `left`/`right`), or by current range (for `near`/`far`); never a
        list fixed at selection time. The user's own words, direction
        document §3: *"it changes as/if we circle the contacts. Or the
        contacts move."* `step right` takes the smallest strictly-positive
        angular delta, `step left` the smallest-magnitude negative one,
        `step N <dir>` the Nth; `near`/`far` use the identical signed
        machinery keyed on `range_m` (a positive delta is farther, a
        negative one nearer -- no angular wraparound applies to range, so
        the sign convention is simpler but the ordering rule is the same).

        Reads the **world-anchored belief** bearing/range
        (`facts["relative_now"]`), not the tier-1 relative-direction
        channel -- Decision 6 explicitly routes `step` through the belief
        store, and that channel is Decision 16's single-consumer fence
        (`attack_run.py`/`percept.py` only) in the first place."""
        direction = slots.get("direction") if slots is not None else None
        if direction not in ("left", "right", "near", "far"):
            # Defensive, request-shape check -- unreachable from a real
            # `step` match (`_parse_step_slots` never returns a token
            # without a direction), the same posture `_handle_follow`'s
            # own "malformed/empty slots" check documents.
            return ["say again -- step needs a direction"]
        assert isinstance(direction, str)
        count_raw = slots.get("count") if slots is not None else None
        count = count_raw if isinstance(count_raw, int) and count_raw >= 1 else 1

        target_task = self._active_attack_target_task()
        if target_task is None or target_task.contact_id is None:
            return ["no target selected"]
        current_id = target_task.contact_id

        if self.enrichment is None:
            return ["no world-model connection configured"]

        candidate_ids = self._step_candidates(
            now_sim, current_id, target_task.descriptor
        )
        others = [cid for cid in candidate_ids if cid != current_id]
        if not others:
            return [render_unable("NO_GROUP_MEMBERS").text]

        def _bearing_and_range(contact_id: str) -> tuple[float, float] | None:
            """`facts["relative_now"]`'s `bearing_deg`/`range_m` for
            `contact_id`, or `None` when the contact does not resolve or
            carries no world-anchored geometry yet -- narrows `object` to
            `float` explicitly, since `facts` is a plain `dict[str,
            object]` and `mypy --strict` cannot follow the dict lookup
            otherwise."""
            result = describe_contact(
                self.store, contact_id, now_sim, enrichment=self.enrichment
            )
            if result is None:
                return None
            relative_now = result["facts"].get("relative_now")
            if not isinstance(relative_now, dict):
                return None
            bearing = relative_now.get("bearing_deg")
            range_m = relative_now.get("range_m")
            if not isinstance(bearing, float) or not isinstance(range_m, float):
                return None
            return bearing, range_m

        current_geometry = _bearing_and_range(current_id)
        if current_geometry is None:
            return [f"no such contact: {current_id}"]
        current_bearing_deg, current_range_m = current_geometry

        def _signed_delta(candidate_id: str) -> float | None:
            candidate_geometry = _bearing_and_range(candidate_id)
            if candidate_geometry is None:
                return None
            bearing_deg, range_m = candidate_geometry
            if direction in ("left", "right"):
                return signed_angular_delta_deg(current_bearing_deg, bearing_deg)
            return range_m - current_range_m

        scored: list[tuple[float, str]] = []
        for candidate_id in others:
            delta = _signed_delta(candidate_id)
            if delta is None:
                continue
            if direction in ("right", "far") and delta > 0:
                scored.append((delta, candidate_id))
            elif direction in ("left", "near") and delta < 0:
                scored.append((abs(delta), candidate_id))
        scored.sort(key=lambda item: item[0])

        if len(scored) < count:
            # End of the ordering: stop, and say so (Decision 6) --
            # wrapping would silently re-target a unit the pilot has just
            # stepped past, in the seconds before release.
            return [render_unable("LAST_IN_ORDER").text]
        next_id = scored[count - 1][1]

        set_attention(self.store, current_id, "watch", source="attack_target")
        set_attention(self.store, next_id, "priority", source="attack_target")
        target_task.contact_id = next_id

        result = describe_contact(
            self.store, next_id, now_sim, enrichment=self.enrichment
        )
        if result is None:
            return [f"no such contact: {next_id}"]

        # Deferred, not the re-ordering above (Stage 6, `plans/
        # voice-latency-instrumentation/plan.md`) -- `next_id` is already
        # fixed; only its readback waits for the channel and is re-rendered
        # against belief at that later tick.
        def _render(render_now_sim: float) -> list[str]:
            redone = describe_contact(
                self.store, next_id, render_now_sim, enrichment=self.enrichment
            )
            if redone is None:
                return [render_lost_contact().text]
            return [render_target_readback(redone["facts"]).text]

        return self._speak_or_defer(now_sim, correlation_id, _render)

    def _handle_engage(
        self, now_sim: float, slots: dict[str, int | str] | None
    ) -> list[str]:
        """`engage`/`engage target`/`attack`/`attack run`, with or without
        `<what> <where> [weapon]` (`plans/attack-run/plan.md` Decision 15,
        the spec's "engage/attack <what> <where>" grammar). When the slots
        carry a what/where descriptor, first selects a target exactly as
        `select target` does (Decision 14's tie-break, via `_resolve_
        attack_target`) and registers (or moves) the standing task, then
        starts the run on whichever contact ends up selected -- a bare
        `engage`/`engage target` with no slots instead starts the run on
        whatever is already selected. The weapon slot, if present, is
        accepted and discarded (Decision 15: "nothing reads it yet" --
        `_parse_target_slots` has no weapon field, so it is simply never
        read here either, the same "accepted into the grammar, never
        consumed" shape the plan describes)."""
        descriptor, clock, sector, relative, band = self._parse_target_slots(slots)
        if (
            descriptor is not None
            or clock is not None
            or sector is not None
            or relative is not None
            or band is not None
        ):
            if self.enrichment is None:
                return ["no world-model connection configured"]
            if self.tasks is None:
                return ["no task store configured"]
            contact_id, no_match_lines = self._resolve_attack_target(
                now_sim, descriptor, clock, sector, relative, band
            )
            if contact_id is None:
                return no_match_lines
            task = attack_target_task(
                self.store, self.tasks, contact_id, now_sim, descriptor=descriptor
            )
            if task is None:
                return [f"no such contact: {contact_id}"]
            belief_group = self.store.group_for_contact(contact_id)
            if belief_group is not None and len(belief_group.member_contact_ids) > 1:
                for member_id in belief_group.member_contact_ids:
                    if member_id == contact_id:
                        continue
                    watch_contact_task(
                        self.store,
                        self.tasks,
                        member_id,
                        now_sim,
                        source="attack_target",
                    )
        else:
            target_task = self._active_attack_target_task()
            if target_task is None or target_task.contact_id is None:
                return ["no target selected"]
            contact_id = target_task.contact_id

        result = describe_contact(
            self.store, contact_id, now_sim, enrichment=self.enrichment
        )
        if result is None:
            return [f"no such contact: {contact_id}"]
        self.attack_run_transition = "engage"
        return [render_engage_readback(result["facts"]).text]

    def _handle_disengage(self) -> list[str]:
        """`disengage`/`stop attack`/`abort` (`plans/attack-run/plan.md`
        Decision 2) -- ends the run's *phase* only (the `attack_run_
        transition` signal the poll loop applies onto `logger.
        ConsolePerceptionRunner.attack_run_state`, clearing it); the
        standing `attack_target` task, and therefore the selection, is left
        alone -- *"stop the run, keep the watch"* (the 2026-09-24 note),
        and `drop target`/the existing cancel path are the separate
        commands that end the selection too. Speaks unconditionally, even
        if no run was active -- harmless, and simpler than a check this
        class has no cheap way to make (the run's own phase lives on the
        caller, not here)."""
        self.attack_run_transition = "disengage"
        return [render_attack_run_off().text]

    def _handle_observ_on(self) -> list[str]:
        """ "Observ on" -- `BL-B64` Stage 2, direction §6: *"OBSERV ON only
        on pilot command."* Leaves `observ_transition` for the poll loop
        (`logger.py`, which owns `OpticState.home_phase`) rather than
        mutating state this class cannot reach -- see that field's own
        docstring. Entering OBSERV does not itself point the sight or
        change what Petrovich is looking through this instant: the phase
        cycle (`belief.optic_policy.decide`) only moves into `SIGHTING` at
        its own next phase boundary, the structural rule that makes
        abandoning a scan mid-sweep to glass up (or sight up) an
        inexpressible state. Speaks unconditionally, same posture as
        `_handle_disengage`."""
        self.observ_transition = "on"
        return ["Observ on."]

    def _handle_observ_off(self) -> list[str]:
        """ "Observ off" -- the pilot's own command to end OBSERV (direction
        §6), and also what a violent manoeuvre does automatically
        (`belief.optic_policy._force_observ_off`, direction §8) -- this
        handler is the pilot-commanded path only; the manoeuvre path never
        calls it. Speaks unconditionally, same posture as `_handle_
        disengage`."""
        self.observ_transition = "off"
        return ["Observ off."]

    def drain_attack_run(
        self,
        state: AttackRunState | None,
        now_sim: float,
        ownship: OwnshipState,
        *,
        resolving_optic: Optic | None = None,
    ) -> AttackRunState | None:
        """Pulls one tick of attack-run guidance and speaks it, if
        `belief.attack_run.decide` says to (`plans/attack-run/plan.md`
        Stage 3/5/6/7) -- modelled on `logger.decide_optic`'s own
        `(state_in, ...) -> state_out` shape, except the state lives on the
        *caller* (`logger.ConsolePerceptionRunner.attack_run_state`, Stage
        5's wiring) rather than on this class: this method is called with
        the current state and returns its replacement, the same contract
        `decide` itself has.

        `resolving_optic` (`BL-B71`'s review, required fix) is the optic
        that actually admitted this poll's percepts. **Not** the caller's
        `OpticState.guidance_optic` -- that is the ladder's own standing
        *grant*, which reads `None` through ordinary glassing with no
        guidance request at all, so testing against it mis-measures a
        live binocular look as the naked eye's own (narrower) range. User
        direction, 2026-10-16: "actual behavior must measure by used
        optic." The caller (`logger.py`'s poll loop) passes its own
        `runner.optic` -- the same value `logger._apply_active_gaze` just
        assigned onto `source.optic` for this poll, i.e. the optic
        `perception.visibility.check_visibility` actually resolved this
        tick's percepts against -- read *after* this same poll's
        `decide_optic` call (`logger.py`'s own ordering comment on
        `requested_optic`/`drain_attack_run`), passed straight through to
        `belief.attack_run.decide`'s own `resolving_optic`. `None` (its
        default) for a caller with no optic ladder, read by `decide` as
        `UNAIDED_OPTIC`.

        **Resolves the target's `belief.groups.Group` and passes it to
        `decide` as of Stage 7** -- tier 2's own projection input (Decision
        10's `Group.heading_deg`), `None` whenever the contact is
        ungrouped; tier 1 never reads it.

        **Wired into `_run_crew_text_poll_loop`, immediately before
        `drain_events`, as of Stage 5** -- the caller reads `self.
        scheduler.busy_until_sim` the same way `_print` does, so a
        deferred guidance line defers the scheduler's own candidates
        rather than the reverse (Decision 1).

        `None` in (not engaged), `None` out -- a true no-op. `state` is
        not `None` only once `engage` has set it, so a selected-but-not-
        engaged target produces no guidance at all, matching the spec.

        **Decision 13's end condition is handled here, not deferred to
        Stage 5's wiring as the Stage 3 docstring once said** -- if the
        target's own `Contact` no longer resolves (a merge abandoned its
        id with no successor recorded anywhere; `LOST_THRESHOLD_S`
        retirement does not do this, per `belief.contacts.ContactStore`'s
        "full memory, never pruned" posture), guidance has nothing left
        to guide on. The run ends and says so once (`render_lost_contact`)
        -- silently continuing against a vanished target is the one thing
        that would make §4's silence lie -- and the standing task is
        cancelled too (unlike `disengage`, there is no longer a selection
        left to keep)."""
        if state is None:
            return state
        target_task = self._active_attack_target_task()
        if target_task is None or target_task.contact_id is None:
            # The standing task is gone (cancelled by `drop target`, or the
            # generic all-kinds `cancel`/`stop` path) -- treat this exactly
            # like the vanished-contact branch below: the run's phase ends
            # and `None` propagates out to `runner.attack_run_state`, which
            # is what `_active_gaze`'s `attack_run_engaged` reads. Returning
            # the unchanged `state` here (the bug the Stage 4-5 review
            # found by reproduction) left the gaze claim stuck on after a
            # bare `drop target`, inherited by the next `select target`
            # that never called `engage` at all.
            return None
        contact = self.store.contact(target_task.contact_id)
        if contact is None:
            if self.tasks is not None:
                cancel_task(self.store, self.tasks, target_task.id)
            self._print([render_lost_contact().text], now_sim)
            return None
        group = self.store.group_for_contact(contact.id)
        new_state, speech = decide_attack_run(
            state,
            now_sim=now_sim,
            ownship=ownship,
            contact=contact,
            group=group,
            resolving_optic=resolving_optic,
        )
        if speech is None:
            return new_state
        if now_sim >= self.scheduler.busy_until_sim:
            self._print(
                [speech.text],
                now_sim,
                attack_run_fields={
                    "attack_run_target_contact_id": contact.id,
                    "attack_run_tier": new_state.last_spoken_tier,
                    # `plans/attack-run-sortie-fixes/plan.md` BL-B70 §1:
                    # `AttackRunState.last_spoken_azimuth_deg`/
                    # `last_spoken_elevation_deg` (the old cadence
                    # baseline) are removed -- `current_azimuth_deg`/
                    # `current_elevation_deg` are updated every tick
                    # regardless of emit, so they always read "this
                    # tick's" angles, which is exactly the tick that
                    # produced `speech.text` here.
                    "attack_run_azimuth_deg": new_state.current_azimuth_deg,
                    "attack_run_elevation_deg": new_state.current_elevation_deg,
                },
            )
            return new_state
        # Occupancy suppressed the print (Stage 4-5 review, required fix
        # 1): `new_state` already has `last_spoken_*` updated by `decide()`
        # as if the line had been spoken, which would make `_should_emit`
        # hold its baseline against a line nobody heard. Carry the
        # *previous* `state` forward instead, so the same change is
        # re-offered on the next tick the channel is free -- dropped, not
        # queued (no deferral machinery here; the reply lane does not
        # defer, Decision 1 scopes that to the push path), and safe to drop
        # because the baseline not having moved means the next evaluation
        # re-fires immediately once the geometry (or the now-unchanged
        # comparison) says to.
        return state

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

    def _handle_slotted_report(
        self,
        now_sim: float,
        slots: dict[str, int | str] | None,
        correlation_id: str | None = None,
    ) -> list[str]:
        """`report|describe [<what>] [<where>] [<how far>]` -- the slotted
        crew query's one dispatch branch (`plans/crew-query-path/plan.md`
        Decision A, user decision 12). Reads the slots audio-adapter parsed
        and calls `_handle_report`; the answer itself is that method's job,
        unchanged.

        **Every slot is validated, and an unrecognised value is dropped
        rather than refused.** Slots arrive as JSON over the HTTP seam
        (Decision E), so nothing here can assume a well-formed value --
        this is the same graceful-degradation posture `bearing_degrees`
        already takes in `handle_command`, and the honest failure for a
        query is a wider answer, never silence. Mutual exclusion between
        the three *where* slots is audio-adapter's (it returns a detected
        recognition error before body-layer ever sees the token), so this
        side only has to pick one if a non-adapter caller sends two: the
        order below is clock, then sector, then relative, matching the
        *where* precedence decision 12 states ("typically clock hand").

        Each slot is validated against the table that owns its values on
        this side -- `_FOLLOW_DESCRIPTOR_OP_CLASSES` (plus `"group"`, which
        is not a classification), `_CLOCK_REPORT_LABELS`' forward hours,
        `_SECTOR_FOR_WORD`, `RELATIVE_SECTORS`, `_REPORT_BAND_BOUNDS_M` --
        so a drift across the seam drops a slot and widens the answer
        rather than raising mid-query."""
        descriptor: str | None = None
        clock: int | None = None
        sector: Sector | None = None
        relative: RelativeSector | None = None
        band: str | None = None
        if slots is not None:
            raw_descriptor = slots.get("descriptor")
            if isinstance(raw_descriptor, str) and (
                raw_descriptor in _FOLLOW_DESCRIPTOR_OP_CLASSES
                or raw_descriptor == "group"
            ):
                descriptor = raw_descriptor
            raw_clock = slots.get("clock")
            if isinstance(raw_clock, int) and raw_clock in _CLOCK_REPORT_LABELS:
                clock = raw_clock
            raw_sector = slots.get("sector")
            if isinstance(raw_sector, str):
                sector = _SECTOR_FOR_WORD.get(raw_sector)
            raw_relative = slots.get("relative")
            if isinstance(raw_relative, str) and raw_relative in RELATIVE_SECTORS:
                # No `cast` needed and `mypy --strict` rejects one as
                # redundant: a membership test against a tuple of
                # `Literal`s narrows `str` to `RelativeSector` on its own.
                relative = raw_relative
            raw_band = slots.get("band")
            if isinstance(raw_band, str) and raw_band in _REPORT_BAND_BOUNDS_M:
                band = raw_band
        return self._handle_report(
            now_sim,
            clock=clock,
            sector=sector,
            descriptor=descriptor,
            relative=relative,
            band=band,
            correlation_id=correlation_id,
        )

    def _handle_radio_check(self) -> list[str]:
        """`[[BL-B81]]` -- "radio check" -> "Loud and clear." Reads
        nothing, touches no belief: this is a liveness check ("intercom is
        on, Petrobrain is up"), not a query, so it has no on-the-ground or
        no-belief failure mode -- it always answers the same fixed line
        (unless `handle_command`'s own refusal/on-ground checks, which run
        before any token-specific dispatch, already returned first)."""
        return [render_radio_check().text]

    def _handle_greeting(self, slots: dict[str, int | str] | None) -> list[str]:
        """`[[BL-B81]]` -- "good morning/day/evening/night Petrovich" ->
        "Good morning/day/evening/night, commander.", echoing the pilot's
        own word rather than reading the sim clock (user, 2026-10-19). The
        word is carried as `slots["time_of_day"]` by whichever surface
        recognised the phrase (`handle_line`'s own literal match for typed
        crew-text; `audio-adapter`'s `command_matcher` for voice, once
        wired there) -- this method only renders it. A missing or
        unrecognised value is the harness/caller's bug, not the pilot's
        mistake, but the graceful-degradation posture every other
        slot-reading branch in this class takes (`scan_bearing_deg`'s
        missing-bearing case, directly above) is to degrade rather than
        raise, so this does too."""
        time_of_day = slots.get("time_of_day") if slots is not None else None
        if time_of_day not in _GREETING_TIMES_OF_DAY:
            return ["say again -- no greeting heard"]
        assert isinstance(time_of_day, str)
        return [render_greeting(time_of_day).text]

    def _handle_report(
        self,
        now_sim: float,
        *,
        clock: int | None = None,
        sector: Sector | None = None,
        descriptor: str | None = None,
        relative: RelativeSector | None = None,
        band: str | None = None,
        correlation_id: str | None = None,
    ) -> list[str]:
        """`report_all`/`report_clock_<p>`/`report_bearing_<compass>`/
        `report_bearing_deg` (the last reduced to `sector` by
        `handle_command` before this is ever called), and the slotted
        `report|describe [<what>] [<where>] [<how far>]` query via
        `_handle_slotted_report` -- `plans/voice-command-completeness/
        plan.md` Decision 1: **a read of current belief and nothing else.**
        No `AttentionArea`, no `PendingIntent`, no gaze change, no
        `aircraft_client` call -- "report is always about current belief.
        Scan tells to go look" (user, 2026-09-23). At most one of
        `clock`/`sector`/`relative` is set (all three answer *where*);
        none set and no other slot means `report_all`.

        **The three slot filters** (`plans/crew-query-path/plan.md`
        Decision B), each reusing a table or bound that already existed:

        - `descriptor` -- the shared `descriptor_verdict`. **An
          unclassified contact is included**, which is the same judgement
          `_descriptor_score` already records: he is pointing at a thing
          he *believes* is armour, and matching it is right. Only a
          positively-wrong known class is excluded.
        - `relative` -- `perception.gaze.SECTOR_WEDGE_DEG`, imported
          directly from that module (there is no `belief.attention`
          re-export to go looking for). It is the public alias bound to
          the *same object* as the private
          `_RELATIVE_SECTOR_WEDGE_DEG` that
          `attention.project_relative_area` reads, so `report left` and
          `scan left` agree on what "left" means by construction --
          identity, not two tables kept in step.
        - `band` -- `_REPORT_BAND_BOUNDS_M` against `relative_now
          ["range_m"]`, which `relative_geometry` already returns.

        **The clock filter is a span, not an equality.** It was an exact
        hour; it is now +/- `callouts.CALLOUT_GROUP_CLOCK_SPAN_HOURS`,
        which is already documented as *"two reports whose clock positions
        are this close read as the same direction to a listener"* -- the
        project's existing answer to this exact question, so there is no
        second constant. A pilot saying "two o'clock" means *around* two,
        and D13's answer form speaks a bearing *span*. **This is a
        behaviour change to the shipped `report_clock_*` commands**, not
        purely additive: more contacts land in scope per query.

        **`contacts._callout_may_speak` is deliberately NOT applied here**
        (Decision D). That gate belongs to the *push* path and D11 extends
        it to every callout kind; applying it to a *pull* would answer
        "nothing there" about a contact Petrovich genuinely believes in,
        just because the aircraft has since turned away. Belief is already
        perception-bounded, so presence claims are safe regardless of
        where he is currently looking. The honest shape is **report it,
        qualified** ("last I saw"), never **withhold it**.

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
        turning away; only the *absence* claim is withheld.

        **Group+render (`plans/group-reporting/plan.md` Stage 4, section 6)**
        resolves each in-scope contact's `belief.groups.Group` first and
        speaks each distinct group once via `belief.speech.render_group_
        disclosure` -- the same renderer `CalloutScheduler.tick` uses for
        the push path, so a pushed callout and a pulled "report" describe
        one group identically. Contacts with no group still go through the
        pre-existing `group_facts`/`render_group_report` report-space
        bucketing.

        **Deferred as a whole, not merely re-rendered** (Stage 6, `plans/
        voice-latency-instrumentation/plan.md`): unlike the target-keyed
        commands above, a report resolves nothing at command time to hold
        onto -- it is a pure read, so there is nothing *to* make
        unconditional-and-immediate the way a selection is. When the
        channel is modeled busy, the whole scope-and-render below simply
        runs again at the later tick's own `now_sim`, via
        `_speak_or_defer`."""
        if self.enrichment is None:
            return ["no world-model connection configured"]

        def _render(render_now_sim: float) -> list[str]:
            # `self.enrichment` is re-checked here, not only above: this
            # closure may run on a later poll than the one that validated
            # it, and `--crew-text`'s own loud-refusal mode (`BL-15` Stage
            # 3) can null it out in between -- `_report_scope`'s own
            # `assert self.enrichment is not None` would otherwise fire on
            # a state this method's caller never actually saw.
            if self.enrichment is None:
                return ["no world-model connection configured"]
            scope = self._report_scope(
                render_now_sim,
                clock=clock,
                sector=sector,
                descriptor=descriptor,
                relative=relative,
                band=band,
            )
            facts_list = scope.facts

            if not facts_list:
                if scope.rear_hemisphere:
                    assert scope.direction_label is not None
                    return [render_no_view(scope.direction_label).text]
                return [render_clear(scope.direction_label).text]

            # Decision C: the answer is one summary utterance, not the
            # per-group enumeration -- *"B. I can also look myself, so a
            # summary is good, I then know where and what to look for."*
            #
            # **`_render_report_lines` and `render_report`/
            # `REPORT_MAX_GROUPS` stay in place, unused by this path,
            # deliberately** (that plan's Decision C): if the summary reads
            # too thin in the air, reverting is this one call site, and
            # that has to stay true until the user has flown it. Do not
            # delete them.
            #
            # **But a revert is not free, and this is the comment a
            # reverter reads first, so it says so here**: swapping back to
            # `_render_report_lines` reintroduces the group-roster leak
            # that Stage 3 closed -- a *filtered* query whose scope catches
            # one member of a cohered group speaks that group's
            # out-of-scope members too, because
            # `render_group_full_disclosure` names the full roster by
            # design. `_render_report_lines`' own docstring has the
            # measurement (`report two o'clock near` answering *"Armor,
            # truck and infantry"* for a 1/3/7 km group). So reverting is
            # one call site **and** either accepting that leak or filtering
            # the roster; it is not one line on its own.
            return [
                render_report_summary(
                    facts_list,
                    band_label=self._band_label_for(facts_list, band),
                    stale_window_s=OBSERVED_WINDOW_S,
                ).text
            ]

        return self._speak_or_defer(now_sim, correlation_id, _render)

    def _band_label_for(
        self, facts_list: list[dict[str, object]], band: str | None
    ) -> str:
        """The summary's distance clause.

        When the query named a band, that band's own label -- the pilot
        asked about *near*, so *"inside 2 kilometres"* is what bounds the
        answer. Otherwise it is bucketed from the **furthest** in-scope
        contact (`plans/crew-query-path/plan.md` Decision C's table), since
        the clause's job is to say how far out the pilot has to look: the
        near edge would under-state where things are."""
        if band is not None:
            return _REPORT_BAND_LABELS[band]
        max_range_m = 0.0
        for facts in facts_list:
            relative_now = facts.get("relative_now")
            if not isinstance(relative_now, dict):
                continue
            range_m = relative_now["range_m"]
            assert isinstance(range_m, float)
            max_range_m = max(max_range_m, range_m)
        for candidate, (lo_m, hi_m) in _REPORT_BAND_BOUNDS_M.items():
            if lo_m <= max_range_m < hi_m:
                return _REPORT_BAND_LABELS[candidate]
        # Unreachable: the three bands tile [0, inf). Kept as the honest
        # fallback rather than an assert, because a report must answer.
        return _REPORT_BAND_LABELS["far"]

    def _report_scope(
        self,
        now_sim: float,
        *,
        clock: int | None,
        sector: Sector | None,
        descriptor: str | None,
        relative: RelativeSector | None,
        band: str | None,
    ) -> ReportScope:
        """Which contacts a report is *about*, plus how to answer when that
        set is empty -- `_handle_report`'s filtering half, pulled out as a
        named seam (`plans/crew-query-path/plan.md` Decision B/C).

        Two reasons it is its own method rather than a block inside
        `_handle_report`. First, Decision C's summary is computed from
        **the in-scope facts, not from texts**, so the in-scope set has to
        be a thing a caller can hold. Second, it is the only honest way to
        test a filter: the spoken answer goes through
        `render_group_full_disclosure`, whose rule is to name a group's
        *full roster*, so an in-scope contact drags its out-of-scope
        group-mates into the text and a filter's effect is not readable
        off the sentence at all."""
        assert self.enrichment is not None
        heading = self.enrichment.ownship.heading_true_deg
        rear_cutoff_deg = COCKPIT_MASKS[STATION_CO_PILOT].rear_cutoff_deg
        direction_label: str | None = None
        rear_hemisphere = False
        # The *where* wedge, as `(absolute center, half-width)` in true
        # degrees, or `None` for a query that names no compass/relative
        # direction. `sector` keeps its existing +/-45; `relative` reads
        # the shared wedge table and projects it onto the current heading
        # exactly as `attention.project_relative_area` does, so the two
        # cannot disagree about where "left" is.
        wedge: tuple[float, float] | None = None
        if clock is not None:
            direction_label = f"{_CLOCK_REPORT_LABELS[clock]} o'clock"
        elif sector is not None:
            direction_label = _SECTOR_SCAN_LABELS[sector]
            center = _SECTOR_CENTER_DEG[sector]
            wedge = (center, 45.0)
            rear_hemisphere = angular_delta_deg(center, heading) >= rear_cutoff_deg
        elif relative is not None:
            direction_label = _RELATIVE_SCAN_LABELS[relative]
            relative_center, half_width = SECTOR_WEDGE_DEG[relative]
            center = (heading + relative_center) % 360.0
            wedge = (center, half_width)
            # `render_no_view` extended to `relative` (`plans/
            # crew-query-path/plan.md` Decision D) -- the absence claim is
            # withheld for a direction the cockpit mask makes impossible,
            # whichever frame named it.
            #
            # **Enumerated, because today it can never fire and that must
            # stay visible:** all four `RelativeSector`s are body-relative
            # and forward by construction -- `ahead` (0 +/- 30), `left`
            # (-60 +/- 30), `right` (+60 +/- 30), `full` (0 +/- 90) -- so
            # the widest reaches 90 degrees relative, well inside the
            # 130-degree `rear_cutoff_deg`. The check is applied anyway
            # rather than hardcoded `False`, so that widening the wedge
            # table (or offering a rear sector, which `gaze.py` currently
            # declines to) cannot silently start claiming "left, clear"
            # about something Petrovich cannot see. `test_crew_console.py`
            # pins both halves: the four sectors are inside the mask, and
            # a relative query answers `render_clear`.
            #
            # Compared on the wedge *center*, exactly as the `sector`
            # branch above does with its own +/-45 -- one rule for both
            # frames rather than a second, edge-based one here.
            rear_hemisphere = angular_delta_deg(center, heading) >= rear_cutoff_deg

        band_bounds = _REPORT_BAND_BOUNDS_M[band] if band is not None else None
        facts_list: list[dict[str, object]] = []
        for result in get_contacts(self.store, now_sim, enrichment=self.enrichment):
            facts = result["facts"]
            if facts.get("certainty") == "lost":
                continue
            relative_now = facts.get("relative_now")
            if not isinstance(relative_now, dict):
                continue
            if clock is not None:
                actual_clock = relative_now["clock_position"]
                assert isinstance(actual_clock, int)
                if _clock_delta(clock, actual_clock) > CALLOUT_GROUP_CLOCK_SPAN_HOURS:
                    continue
            if wedge is not None:
                bearing_deg = relative_now["bearing_deg"]
                assert isinstance(bearing_deg, float)
                center_deg, half_width_deg = wedge
                if angular_delta_deg(bearing_deg, center_deg) > half_width_deg:
                    continue
            if band_bounds is not None:
                range_m = relative_now["range_m"]
                assert isinstance(range_m, float)
                lo_m, hi_m = band_bounds
                if not lo_m <= range_m < hi_m:
                    continue
            if descriptor is not None and descriptor_verdict(descriptor, facts) == (
                "wrong"
            ):
                continue
            facts_list.append(facts)

        return ReportScope(
            facts=facts_list,
            direction_label=direction_label,
            rear_hemisphere=rear_hemisphere,
        )

    def _render_report_lines(
        self, facts_list: list[dict[str, object]], now_sim: float
    ) -> list[str]:
        """`_handle_report`'s rendering half -- the per-group enumeration
        this command has always spoken, unchanged.

        **Known limitation, closed by Stage 3** (`plans/crew-query-path/
        plan.md` Decision C): `render_group_full_disclosure` names a
        group's *full roster* by design, so a filtered query whose scope
        includes one member of a group has that group's out-of-scope
        members spoken too. Measured: three contacts at two o'clock at
        1/3/7 km cohere into one `Group`, and `report two o'clock near`
        then says *"Armor, truck and infantry"*. Correct for the
        unfiltered report this renderer was written for; wrong once there
        is a filter. Decision C's summary replaces it with aggregates over
        the in-scope facts, which cannot leak by construction."""
        assert self.enrichment is not None
        # `plans/group-reporting/plan.md` Stage 4 design, section 6: a
        # contact already in this report's scope may belong to a real,
        # persisted `belief.groups.Group` -- resolve those first and speak
        # each distinct group once via `render_group_full_disclosure`, so a
        # pushed callout and a pulled "report" describe the same group's
        # full composition (`plans/group-cohesion-redesign/plan.md` §4's
        # "report" roll-up example always names the full roster, never a
        # delta -- `render_group_disclosure`'s own taxonomy gate is
        # deliberately not used here, see that function's docstring).
        # Everything left over (no group at all) still goes through
        # `group_facts`/`render_group_report`'s report-space bucketing
        # exactly as before.
        grouped_by_id: dict[str, list[dict[str, object]]] = {}
        ungrouped_facts_list: list[dict[str, object]] = []
        for facts in facts_list:
            contact_id = facts["id"]
            assert isinstance(contact_id, str)
            belief_group = self.store.group_for_contact(contact_id)
            if belief_group is None:
                ungrouped_facts_list.append(facts)
                continue
            grouped_by_id.setdefault(belief_group.id, []).append(facts)

        report_entries: list[tuple[tuple[int, int, float], str]] = []
        for in_scope_member_facts in grouped_by_id.values():
            leading_id = in_scope_member_facts[0]["id"]
            assert isinstance(leading_id, str)
            belief_group = self.store.group_for_contact(leading_id)
            assert belief_group is not None
            # A report is pull-based, so it always speaks fresh -- no
            # `last_spoken_signature`/delta-taxonomy gate here, that exists
            # only to throttle the push (`CalloutScheduler`) path.
            speech = render_group_full_disclosure(
                self.store, belief_group, now_sim, self.enrichment
            )
            if speech is None:
                # Fewer than two members currently resolve to a live
                # `Contact` -- fall back to this report's own ungrouped
                # bucketing for the in-scope member(s) rather than
                # silently dropping them from the report.
                ungrouped_facts_list.extend(in_scope_member_facts)
                continue
            priority = min(report_priority(facts) for facts in in_scope_member_facts)
            report_entries.append((priority, speech.text))

        for bucket in group_facts(ungrouped_facts_list):
            priority = min(report_priority(facts) for facts in bucket)
            text = (
                _contact_report_text(bucket[0])
                if len(bucket) == 1
                else render_group_report(bucket).text
            )
            report_entries.append((priority, text))

        report_entries.sort(key=lambda item: item[0])
        texts = [text for _, text in report_entries[:REPORT_MAX_GROUPS]]
        truncated = len(report_entries) > REPORT_MAX_GROUPS
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
        if task.kind == "attack_target":
            # `plans/attack-run/plan.md` Decision 2 -- same "no ids in
            # speech" rule, same terse shape as `watch_contact`'s own
            # `"watch"` above.
            return "target"
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

    def _handle_silence(self, now_sim: float) -> None:
        """`silence` -- "make Petrovich not talk until my next command"
        (user direction, 2026-10-04, `plans/silence-command/plan.md`).

        **Already silenced -> a pure no-op**, not a toggle. A second
        `silence` while one is already in effect must not un-silence --
        the pilot has no reliable way to know he is silenced already
        (there is nothing to look at), so a toggle would make a repeated
        press ambiguous: did that just turn silence off? A no-op is the
        only reading that is always safe to repeat.

        **Speaks the one-word acknowledgement first, then sets
        `self.silenced`** -- in that order, deliberately. If the flag were
        set first, this method's own call to `_print` would suppress its
        own acknowledgement, which would make `silence` the one command
        whose confirmation the pilot never hears, on a speech-only setup
        where that confirmation is the only signal he gets that the
        command landed at all.

        Unlike every other token `handle_command` dispatches, this method
        returns nothing and its caller never reaches the shared
        `self._print(lines, now_sim)` tail call -- the acknowledgement
        has already gone out, from here, before `self.silenced` flips.
        `stop_talking` is this class's only other token with that
        shape, for an unrelated reason (see its own docstring); the two
        are tracked together as `NO_RETURN_VALUE_COMMAND_TOKENS`.

        **Does not touch `speech_client.stop()`.** `silence` and
        `stop_talking` answer different questions -- "stop talking right
        now" vs. "say nothing from here on" -- and the plan's own
        decisions treat them as independent: silencing does not imply an
        in-flight utterance needs interrupting (nothing may be playing),
        and ending silence does not resume anything it never stopped. A
        pilot who wants both says both."""
        if self.silenced:
            return
        self._print([render_silence_ack().text], now_sim)
        self.silenced = True

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
        correlation_id: str | None = None,
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
        branch exists rather than leaving the fallthrough alone.

        `correlation_id` (Stage 3, `plans/voice-latency-instrumentation/
        plan.md`) is the capture-side id for this transcript, if the
        recognised clip carried one -- threaded into `_log_transcript`'s
        row and on to `_act_on_voice_decision`/`handle_command` so a
        dispatched command's own readback (and any deferred positional one,
        Stage 6) can be joined back to this utterance."""
        # `BL-15` Stage 3: checked before any of the confirm-band/
        # late-answer/classify logic below -- while refused, a pending
        # confirmation (if any) is left exactly as it was rather than
        # being resolved by this transcript, since the pilot's spoken
        # words during a system error are not being acted on at all.
        refusal = self._refusal_response(now_sim, correlation_id=correlation_id)
        if refusal is not None:
            return refusal
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
                        pending.token,
                        now_sim,
                        slots=pending.slots,
                        correlation_id=correlation_id,
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
                self._print(lines, now_sim, correlation_id=correlation_id)
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
            correlation_id=correlation_id,
        )
        return self._act_on_voice_decision(
            decision, transcript, now_sim, slots, correlation_id=correlation_id
        )

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
        correlation_id: str | None = None,
    ) -> list[str]:
        if decision.disposition == "fallthrough":
            # `handle_line` re-strips/re-checks the `!`-prefixed harness
            # commands, which a real transcript never begins with -- safe
            # to route straight through it rather than duplicating
            # `_handle_utterance` + `_print` here. `handle_line` takes no
            # `correlation_id` (plan Stage 3: "F10/typed-console dispatch
            # paths pass no correlation id, unchanged behaviour") -- the
            # brain-layer free-text path this disposition is heading
            # towards gets its own instrumentation pass once it exists
            # (plan "Second-Order Effect"), not folded in here.
            return self.handle_line(transcript, now_sim)
        if decision.disposition == "act":
            assert decision.token is not None
            return self.handle_command(
                decision.token, now_sim, slots=slots, correlation_id=correlation_id
            )
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
        self._print(lines, now_sim, correlation_id=correlation_id)
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
            # A recognised free-text command ends silence too (`plans/
            # silence-command/plan.md`) -- the grammar resolved an actual
            # intent here, which is a real command, not the stray speech
            # an *unrecognised* utterance (the `escalated` branch below)
            # represents. `handle_command`'s own "silence" branch is the
            # only place this reset is skipped, and this path can never
            # reach it: `parse_utterance`'s grammar has no `silence`
            # intent, so this branch is never how silence itself begins.
            self.silenced = False
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
        self,
        lines: list[str],
        now_sim: float,
        bypass_gate: bool = False,
        attack_run_fields: dict[str, object] | None = None,
        correlation_id: str | None = None,
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
        correctly if that ever changes.

        **`self.silenced` gates `speech_client` only** (`plans/
        silence-command/plan.md`, user direction 2026-10-04) -- `output`
        and `overlay_client` are untouched by it, since the use case is
        audio specifically ("during radio traffic", "near a friendly
        airbase"); the crew-text/overlay surfaces keep working. The gate
        applies regardless of `bypass_gate`: an injected urgent call is
        suppressed exactly like a routine line while silenced -- this
        project's own chosen reading of "absolute silence," not an
        oversight (see `CrewConsole.silenced`'s own field docstring for
        the tradeoff the user was shown before choosing it).
        `speech_log_sink` and the scheduler bookkeeping
        (`note_urgent`/`note_reply`) below are **not** gated either: they
        record what Petrovich *decided* to say, independent of whether it
        was actually voiced, which is exactly the "suppressed, not
        deferred" behaviour `silenced`'s own docstring describes -- the
        scheduler keeps pacing choices as if each chosen line had been
        spoken, so nothing backs up to be dumped once silence ends.

        `attack_run_fields` (Stage 5, `plans/attack-run/plan.md`) is
        threaded straight through to `speech_log_sink` for every line in
        this call -- meaningful only for `drain_attack_run`'s own
        always-one-line call, `None` for every other caller.

        `correlation_id` (Stage 3, `plans/voice-latency-instrumentation/
        plan.md`) identifies which command/transcript produced this line --
        `None` for F10/typed dispatch and every push-lane line (callouts,
        attack-run guidance), which have no voice origin to correlate
        against. The `speech_client.push_speech` call below is wrapped in
        its own `time.monotonic()` bracket regardless of whether
        `correlation_id` is set, since the duration is useful on its own;
        `push_sent_wall`/`push_acked_wall` are ordinary wall-clock, kept for
        ordering/context only (this process and audio-adapter are not
        assumed to share a clock) -- `push_duration_s`, derived from the
        monotonic bracket, is the trustworthy number. All three stay `None`
        when nothing was pushed (`speech_client` unset, or `self.silenced`)."""
        for line in lines:
            if self.output is not None:
                print(line, file=self.output)
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
            push_sent_wall: float | None = None
            push_acked_wall: float | None = None
            push_duration_s: float | None = None
            if self.speech_client is not None and not self.silenced:
                push_sent_wall = time.time()
                t0 = time.monotonic()
                try:
                    self.speech_client.push_speech(
                        line, urgent=bypass_gate, correlation_id=correlation_id
                    )
                except AudioAdapterError:
                    logger.warning(
                        "speech push failed for crew-text line (continuing)",
                        exc_info=True,
                    )
                push_duration_s = time.monotonic() - t0
                push_acked_wall = time.time()
            if self.speech_log_sink is not None:
                try:
                    self.speech_log_sink(
                        line,
                        bypass_gate,
                        attack_run_fields,
                        correlation_id,
                        push_sent_wall,
                        push_acked_wall,
                        push_duration_s,
                    )
                except Exception:
                    # Deliberately broad: a debug log must never be the reason
                    # Petrovich stops talking.
                    logger.warning(
                        "speech log sink failed for crew-text line (continuing)",
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
