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
`--overlay` already uses (after each `ContactStore.tick()`), it runs every
currently-unacknowledged event through `belief.speech.route_event`. Reading
`store.unacknowledged_events` rather than tracking a separate high-water
mark works because `route_event` itself acknowledges any event it renders
a template for -- so a handled kind naturally drops out of this list on the
next call, and a kind with no template (`CONTACT_ATTENTION_CHANGED`, see
`speech.py`) is harmlessly re-checked and re-skipped every poll rather than
needing its own suppression bookkeeping here.

**`handle_f10_command`.** `plans/f10-crew-commands/plan.md`'s second,
non-text input surface: `logger.py`'s `--crew-text --f10-commands` poll
loop drains player-selected DCS F10 radio-menu tokens
(`aircraft_client.get_f10_commands`) and dispatches each one here, through
the same `_print` funnel `handle_line`/`drain_events` already use --
`CrewConsole` has no separate "what F10 says" path to keep in sync with
what typed/spoken output produces.

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
from dataclasses import dataclass, field
from typing import TextIO

from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.attention import RelativeSector, Sector
from belief.audio_client import AudioAdapterClient, AudioAdapterError
from belief.classification import parent_class_of
from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext
from belief.escalation import (
    BrainClient,
    DebugPrintBrainClient,
    handle_player_utterance,
)
from belief.speech import (
    UrgentCall,
    render_cancel_readback,
    render_confirm_request,
    render_contact_report,
    render_readback,
    render_say_again,
    render_scan_readback,
    render_watch_nearest_readback,
    route_event,
)
from belief.tasks import PendingIntent, TaskStore
from belief.tools import (
    cancel_task,
    describe_contact,
    get_contacts,
    scan_area,
    set_attention,
)
from belief.utterance import PartialParse, PlayerUtterance, parse_utterance
from belief.voice_commands import (
    CONFIRM_WINDOW_S,
    BandDecision,
    PendingConfirmation,
    classify_response,
    classify_yes_no,
)
from perception.geometry import GeoPosition

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
_RELATIVE_SCAN_LABELS: dict[RelativeSector, str] = {
    "ahead": "ahead",
    "left": "to the left",
    "right": "to the right",
    "full": "the full forward arc",
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
_AIR_DEFENCE_OP_CLASSES: frozenset[str] = frozenset(
    {"OP_SPAAG", "OP_ZU23", "OP_SRSAM", "OP_MRSAM"}
)

#: The classification lattice levels at which an air-defence claim is
#: actually *known* rather than guessed -- `belief.classification.
#: SpecificityLevel`'s `CLASS` and `TYPE`, lowercased as
#: `tools._classification_facts` reports them.
_KNOWN_CLASS_LEVELS: frozenset[str] = frozenset({"class", "type"})


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
_F10_SCAN_REASON = "F10 scan command"

#: Plain human phrase per non-scan legacy token, for `_describe_token_for_
#: confirm`'s fallback table -- `render_confirm_request`'s `description`
#: argument (`"watch nearest, confirm?"`). Scan tokens instead reuse
#: `_RELATIVE_SCAN_LABELS`/`_SECTOR_SCAN_LABELS` directly (see that
#: function), since those already carry the exact spoken sector phrase.
_TOKEN_DESCRIPTIONS: dict[str, str] = {
    "watch_nearest": "watch nearest",
    "watch_nearest_air_defence": "watch nearest air defence",
    "cancel_task": "cancel the task",
}


def _describe_token_for_confirm(token: str) -> str:
    """A plain human phrase for `token`, for `belief.speech.
    render_confirm_request`'s `description` argument (Stage 2,
    `plans/inbound-speech/plan.md`). Reuses `handle_f10_command`'s own
    token->label tables for the 15-token legacy vocabulary it can already
    dispatch (`_describe_task_for_speech`'s sibling, same "one table, two
    readers" idea); anything outside that set (a voice-only token this
    milestone does not yet act on -- see `handle_f10_command`'s own
    defensive `else` branch) falls back to the token name with
    underscores turned to spaces, which is honest rather than polished:
    there is no dispatch behind it yet for the confirm to be about."""
    if token in _RELATIVE_SCAN_TOKENS:
        return f"scan {_RELATIVE_SCAN_LABELS[_RELATIVE_SCAN_TOKENS[token]]}"
    if token in _BEARING_SCAN_TOKENS:
        return f"scan {_SECTOR_SCAN_LABELS[_BEARING_SCAN_TOKENS[token]]}"
    return _TOKEN_DESCRIPTIONS.get(token, token.replace("_", " "))


logger = logging.getLogger(__name__)


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
    _next_utterance_number: int = field(default=0, repr=False)
    #: Stage 2 of `plans/inbound-speech/plan.md`'s confirm-band state --
    #: set by `handle_transcript` when a matched command lands in the
    #: confirm band (or is ambiguous), cleared on the next call once it is
    #: answered, discarded, or expired (`CONFIRM_WINDOW_S`). `None` means
    #: no question is currently open.
    _pending_confirmation: PendingConfirmation | None = field(default=None, repr=False)

    def handle_line(self, line: str, now_sim: float) -> list[str]:
        stripped = line.strip()
        if not stripped:
            return []
        if stripped.startswith("!inject-urgent"):
            lines, bypass_gate = self._handle_inject_urgent(stripped, now_sim)
            self._print(lines, bypass_gate=bypass_gate)
            return lines
        if stripped.startswith("!voice"):
            return self._handle_voice_test_command(stripped, now_sim)
        lines = self._handle_utterance(stripped, now_sim)
        self._print(lines, bypass_gate=False)
        return lines

    def drain_events(self, now_sim: float) -> list[str]:
        """Speak every currently-unacknowledged event that has a template
        (see module docstring). Called once per poll from `logger.py`'s
        `--crew-text` loop, after `ContactStore.tick()`."""
        spoken: list[str] = []
        for event in self.store.unacknowledged_events:
            speech = route_event(self.store, event, now_sim, self.enrichment)
            if speech is not None:
                spoken.append(speech.text)
        # A lifecycle/classification `Event` never carries `bypass_gate=True`
        # (only an injected `UrgentCall`, routed through `handle_line`'s
        # `!inject-urgent` branch, does) -- see `_print`'s docstring.
        self._print(spoken, bypass_gate=False)
        return spoken

    def handle_f10_command(self, token: str, now_sim: float) -> list[str]:
        """Dispatches one player-selected F10 radio-menu token (`plans/
        f10-command-vocabulary/plan.md`) -- `logger.py`'s `--crew-text
        --f10-commands` poll loop calls this once per token drained from
        `aircraft_client.get_f10_commands`, the same post-`drain_events`
        hook point as every other spoken-output path. The 14-token
        vocabulary (`aircraft-layer`'s `F10CommandReceiver.ALLOWED_COMMANDS`)
        is dispatched via two lookup tables (`_RELATIVE_SCAN_TOKENS`,
        `_BEARING_SCAN_TOKENS`) rather than a 14-branch if/elif, matching
        `belief.utterance`'s own ordered-table idiom for a fixed, closed
        vocabulary. An unrecognized token returns `[]` without printing
        anything -- aircraft-layer's `F10CommandReceiver` already filters to
        its own `ALLOWED_COMMANDS`, so this branch is defensive, not a real
        path in practice."""
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
        elif token == "watch_nearest":
            lines = self._handle_watch_nearest(now_sim)
        elif token == "watch_nearest_air_defence":
            lines = self._handle_watch_nearest(now_sim, air_defence_only=True)
        elif token == "cancel_task":
            lines = self._handle_cancel_task()
        elif token == "stop_talking":
            # No readback, no `_print` call at all -- `stop_talking` is a
            # stated exception to every other token's "dispatch, then
            # readback" shape (see `_handle_stop_talking`'s own docstring).
            self._handle_stop_talking()
            return []
        else:
            return []
        self._print(lines)
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
        after it -- `set_attention`, the readback -- is shared, since what
        "watch this" *means* does not change with how the contact was
        picked. The empty-result wording does differ: "no air defence
        contact" is a materially different statement from "no contact",
        and collapsing them would let the crew hear the wrong one."""
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
    ) -> list[str]:
        """Registers a real `belief.tasks.PendingIntent` via `belief.tools.
        scan_area`, with `center`/`radius_m`/`reason` all fixed (ownship's
        own position, `None` (unbounded), `_F10_SCAN_REASON`) rather than
        player-supplied, since an F10 button carries no bearing/range/
        free-text the way a typed `scan-area` command does. `radius_m=None`
        is a deliberate choice, not a missing value: an F10 sector scan
        should get everything visible within its wedge, per `todo/todo.md`'s
        "Scan geometry: drop the invented radius" -- the area's own
        `radius_m` field documents the reasoning in full. Exactly one of
        `sector`/`relative_sector` is set by the caller
        (`handle_f10_command`'s two lookup tables), never both --
        `scan_area`/`ContactStore.add_area` would raise `ValueError` if
        they were.

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
            _F10_SCAN_REASON,
            now_sim,
            sector=sector,
            relative_sector=relative_sector,
        )
        return [render_scan_readback(sector_label).text]

    def _describe_task_for_speech(self, task: PendingIntent) -> str | None:
        """A plain human phrase for `task`, for `speech.render_cancel_
        readback` -- `"the scan to the left"`, `"the scan north"` -- or
        `None` when the task's shape yields nothing better than "whatever
        you last asked for".

        Reads the frame fields (`relative_sector`/`sector`) straight off the
        task's captured `area`. Unlike the geometry fields, those two are
        never rewritten by `ContactStore.reproject_relative_areas` -- it
        replaces `center`/`wedge_deg` only -- so the captured reference is
        safe to read here, and going through `store.get_area` would return
        the same frame anyway. (`TaskStore.tick` *does* have to resolve the
        live area; see its own docstring for why the two differ.)"""
        if task.kind != "scan_area":
            return None
        area = task.area
        if area.relative_sector is not None:
            return f"the scan {_RELATIVE_SCAN_LABELS[area.relative_sector]}"
        if area.sector is not None:
            return f"the scan {_SECTOR_SCAN_LABELS[area.sector]}"
        return "the scan"

    def _handle_cancel_task(self) -> list[str]:
        """Cancels the most-recently-created still-`pending` task in
        `self.tasks`, regardless of source (plan Decision 3). Every
        `scan_*` token registers a real task via `_handle_scan` above (D5,
        `plans/f10-command-vocabulary/plan.md`), so this is no longer the
        always-"no pending task" dead path it was before that fix -- a scan
        followed by "Cancel Task" genuinely cancels it.

        The readback names *what* was cancelled, never the task id
        (live-test finding 2026-09-16: the player heard `"cancelled task
        TASK_4"`). See `speech.render_cancel_readback` for why -- the same
        no-ids-in-speech rule this codebase already applies to contacts."""
        # Both no-store and nothing-pending say the same thing, and it is
        # deliberately *not* `render_cancel_readback` -- that template says
        # "Copy, stopping", which would claim to have stopped something
        # when nothing was cancelled at all.
        if self.tasks is None:
            return [_NOTHING_TO_STOP]
        pending = [task for task in self.tasks.tasks if task.status == "pending"]
        if not pending:
            return [_NOTHING_TO_STOP]
        task = pending[-1]  # most recently created (TaskStore.tasks is insertion order)
        description = self._describe_task_for_speech(task)
        cancel_task(self.store, self.tasks, task.id)
        return [render_cancel_readback(description).text]

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

        `handle_f10_command`'s Stage 3 revision to this method (the
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
    ) -> list[str]:
        """`plans/inbound-speech/plan.md` Stage 2's voice-command entry
        point -- a sibling of `handle_line`/`handle_f10_command`, per the
        module docstring's prediction of a third input surface. Called
        with the fields `audio_adapter.command_matcher.MatchResult` already
        resolved (Stage 3 wires the real HTTP poll; this stage is driven
        by tests and the `!voice` REPL harness, see `_handle_voice_test_
        command`).

        **A pending confirm-band question, if any, is checked first** --
        `classify_yes_no` decides whether this transcript commits, discards,
        or (implicitly) abandons it. Any answer other than affirm/negative
        discards the pending question *silently* and falls through to treat
        this transcript as its own new input (Decision 4 Layer 3: "anything
        else, or the timeout, discards silently" -- read as discarding the
        stale question, not the player's new utterance). Affirm/negative
        are valid only inside this branch, i.e. only while a confirmation
        is pending -- outside it the same words are ordinary text and reach
        `belief.voice_commands.classify_response` like anything else."""
        if self._pending_confirmation is not None:
            pending = self._pending_confirmation
            if now_sim - pending.pending_since_sim <= CONFIRM_WINDOW_S:
                answer = classify_yes_no(transcript)
                self._pending_confirmation = None
                if answer == "affirm":
                    return self.handle_f10_command(pending.token, now_sim)
                if answer == "negative":
                    return []
                # else: falls through and this transcript is evaluated on
                # its own merits below.
            else:
                self._pending_confirmation = None

        decision = classify_response(
            token, match_ratio, confidence, verb_anchored, ambiguous
        )
        return self._act_on_voice_decision(decision, transcript, now_sim)

    def _act_on_voice_decision(
        self, decision: BandDecision, transcript: str, now_sim: float
    ) -> list[str]:
        if decision.disposition == "fallthrough":
            # `handle_line` re-strips/re-checks the `!`-prefixed harness
            # commands, which a real transcript never begins with -- safe
            # to route straight through it rather than duplicating
            # `_handle_utterance` + `_print` here.
            return self.handle_line(transcript, now_sim)
        if decision.disposition == "act":
            assert decision.token is not None
            return self.handle_f10_command(decision.token, now_sim)
        if decision.disposition == "confirm":
            assert decision.token is not None
            description = _describe_token_for_confirm(decision.token)
            self._pending_confirmation = PendingConfirmation(
                token=decision.token, description=description, pending_since_sim=now_sim
            )
            lines = [render_confirm_request(description).text]
        else:  # "say_again"
            lines = [render_say_again().text]
        self._print(lines)
        return lines

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
        match" (`None`)."""
        usage = [
            (
                "usage: !voice <token|-> <match_ratio> <confidence> "
                "<verb_anchored:0|1> <ambiguous:0|1> <transcript...>"
            )
        ]
        parts = line.split(maxsplit=6)
        if len(parts) != 7:
            self._print(usage)
            return usage
        _, token_arg, ratio_arg, confidence_arg, verb_arg, ambiguous_arg, transcript = (
            parts
        )
        try:
            match_ratio = float(ratio_arg)
            confidence = float(confidence_arg)
        except ValueError:
            self._print(usage)
            return usage
        if verb_arg not in ("0", "1") or ambiguous_arg not in ("0", "1"):
            self._print(usage)
            return usage
        token = None if token_arg == "-" else token_arg
        return self.handle_transcript(
            transcript,
            confidence,
            token,
            match_ratio,
            verb_arg == "1",
            ambiguous_arg == "1",
            now_sim,
        )

    def _new_utterance_id(self) -> str:
        self._next_utterance_number += 1
        return f"{_UTTERANCE_ID_PREFIX}_{self._next_utterance_number}"

    def _handle_utterance(self, transcript: str, now_sim: float) -> list[str]:
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
            return self._act(parse, now_sim)
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

    def _print(self, lines: list[str], bypass_gate: bool = False) -> None:
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
        actually preempts routine playback for it)."""
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
            if self.speech_client is not None:
                try:
                    self.speech_client.push_speech(line, urgent=bypass_gate)
                except AudioAdapterError:
                    logger.warning(
                        "speech push failed for crew-text line (continuing)",
                        exc_info=True,
                    )
