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
    render_contact_report,
    render_readback,
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
from perception.geometry import GeoPosition

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

Anything else is escalated (there is no brain to answer it yet).
"""

_UTTERANCE_ID_PREFIX = "UTTERANCE"

#: Prepended to the overlay-pushed copy of an urgent (`bypass_gate=True`)
#: line only -- see `CrewConsole._print`'s docstring and `plans/
#: overlay-speech-callouts/plan.md`'s resolved "Urgent-call visual
#: prominence" decision. `TextOverlaySender` has no color/bold mechanism,
#: so a plain text prefix is the only available distinction.
_URGENT_OVERLAY_PREFIX = "!! "

#: The radius (meters) an F10 scan command's `AttentionArea`/`PendingIntent`
#: is registered with (`plans/f10-command-vocabulary/plan.md` Stage 6). An
#: F10 button carries no player-supplied geometry the way a typed
#: `scan-area <bearing> <range> <radius> <reason>` command does (`console.py`'s
#: `_handle_scan_area`), so this is an uncalibrated placeholder pending live
#: sortie feedback -- same debt class as `belief.tools.
#: DEFAULT_SCAN_DEADLINE_S` and `perception.visibility.py`'s tier constants,
#: not a derived or justified figure.
F10_SCAN_RADIUS_M: float = 3000.0

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
    _next_utterance_number: int = field(default=0, repr=False)

    def handle_line(self, line: str, now_sim: float) -> list[str]:
        stripped = line.strip()
        if not stripped:
            return []
        if stripped.startswith("!inject-urgent"):
            lines, bypass_gate = self._handle_inject_urgent(stripped, now_sim)
        else:
            lines = self._handle_utterance(stripped, now_sim)
            bypass_gate = False
        self._print(lines, bypass_gate=bypass_gate)
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
        """D5's register-then-trigger contract: registers a real
        `belief.tasks.PendingIntent` via `belief.tools.scan_area` first,
        *then* fires the live effector (`aircraft_client.
        trigger_petrovich_search`), wrapped so a failed trigger still
        leaves the task registered -- mirrors `console.py`'s
        `_handle_scan_area` handler exactly (see that function), just with
        `center`/`radius_m`/`reason` all fixed (ownship's own position,
        `F10_SCAN_RADIUS_M`, `_F10_SCAN_REASON`) instead of player-supplied,
        since an F10 button carries no bearing/range/free-text the way a
        typed `scan-area` command does. Exactly one of `sector`/
        `relative_sector` is set by the caller (`handle_f10_command`'s two
        lookup tables), never both -- `scan_area`/`ContactStore.add_area`
        would raise `ValueError` if they were.

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
        task: PendingIntent = scan_area(
            self.store,
            self.tasks,
            center,
            F10_SCAN_RADIUS_M,
            _F10_SCAN_REASON,
            now_sim,
            sector=sector,
            relative_sector=relative_sector,
        )
        lines = [render_scan_readback(sector_label).text]
        if self.aircraft_client is not None:
            try:
                self.aircraft_client.trigger_petrovich_search("forward")
            except AircraftLayerError:
                logger.warning(
                    "F10 scan trigger failed (continuing, task %s still registered)",
                    task.id,
                    exc_info=True,
                )
        return lines

    def _handle_cancel_task(self) -> list[str]:
        """Cancels the most-recently-created still-`pending` task in
        `self.tasks`, regardless of source (plan Decision 3). Every
        `scan_*` token now registers a real task via `_handle_scan` above
        (D5, `plans/f10-command-vocabulary/plan.md`), so this is no longer
        the always-"no pending task" dead path it was before that fix --
        a scan followed by "Cancel Task" genuinely cancels it."""
        if self.tasks is None:
            return ["no pending task"]
        pending = [task for task in self.tasks.tasks if task.status == "pending"]
        if not pending:
            return ["no pending task"]
        task = pending[-1]  # most recently created (TaskStore.tasks is insertion order)
        cancel_task(self.store, self.tasks, task.id)
        return [f"cancelled task {task.id}"]

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
        `overlay_client` is configured, pushes the same line to the
        in-cockpit text overlay (`AircraftLayerClient.push_text_line`,
        `POST /text/push`) -- the single funnel point every path that
        produces spoken text (`handle_line`, `drain_events`) already goes
        through, so overlay push needs no separate "what to push and when"
        logic to write or desync from what's printed. Each push is wrapped
        in its own `try/except AircraftLayerError`, mirroring `logger.
        ConsolePerceptionRunner.run_once`'s BL-2.5 push loop's degrade-on-
        failure shape: a failed push must not raise, must not stop the
        remaining lines in this batch from being printed/pushed.

        `bypass_gate` (True only for an injected urgent call, per `plans/
        overlay-speech-callouts/plan.md`'s resolved decision) prepends
        `_URGENT_OVERLAY_PREFIX` to the *pushed* overlay line only -- the
        `output` print path stays exactly the text `belief.speech`
        produced, since this is an overlay-display concern, not a change
        to what was spoken/printed generally."""
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
