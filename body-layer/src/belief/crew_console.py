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
from dataclasses import dataclass, field
from typing import TextIO

from aircraft_client import AircraftLayerClient, AircraftLayerError
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
    render_watch_nearest_readback,
    route_event,
)
from belief.tasks import TaskStore
from belief.tools import cancel_task, describe_contact, get_contacts, set_attention
from belief.utterance import PartialParse, PlayerUtterance, parse_utterance

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
    #: own wiring. **Reserved, not yet consumed by any command here** -- no
    #: player-facing `scan_area`-equivalent utterance exists this
    #: milestone (`belief.console.Console`'s `scan-area`/`task-status`/
    #: `cancel-task` are debug-console-only), so this field currently has
    #: no reader. Kept as a `None`-default optional field anyway, matching
    #: `enrichment`'s own None-means-unchanged pattern, so a future
    #: player-facing scan command has a client to reach for without a
    #: second wiring pass through `logger.py`.
    aircraft_client: AircraftLayerClient | None = None
    #: BL-6's `belief.tasks.TaskStore` (`plans/f10-crew-commands/plan.md`,
    #: mirroring `aircraft_client`'s own reserved-field pattern above) --
    #: `handle_f10_command`'s `cancel_task` handler is this field's first
    #: reader. `logger.py`'s `--crew-text` branch wires this to the same
    #: `ConsolePerceptionRunner.tasks` instance its poll loop already
    #: ticks (`TaskStore.tick`), the same store `--console`'s `Console.
    #: tasks` reads/mutates. `None` (the default) means the F10 "Cancel
    #: Task" item always reports "no pending task" rather than raising.
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
        f10-crew-commands/plan.md`) -- `logger.py`'s `--crew-text
        --f10-commands` poll loop calls this once per token drained from
        `aircraft_client.get_f10_commands`, the same post-`drain_events`
        hook point as every other spoken-output path. A fixed dispatch
        table of three verbs; an unrecognized token returns `[]` without
        printing anything -- aircraft-layer's `F10CommandReceiver` already
        filters to its own `ALLOWED_COMMANDS`, so this branch is
        defensive, not a real path in practice."""
        if token == "watch_nearest":
            lines = self._handle_watch_nearest(now_sim)
        elif token == "scan_forward":
            lines = self._handle_scan_forward()
        elif token == "cancel_task":
            lines = self._handle_cancel_task()
        else:
            return []
        self._print(lines)
        return lines

    def _nearest_contact_id(self, now_sim: float) -> str | None:
        """The currently-nearest contact by range, for the F10 "Watch
        Nearest" item. New glue logic, not a rediscovery of existing
        selection logic -- `belief.tools`/`belief.attention` have no
        "nearest by range" helper today, only `_highest_attention_contact`'s
        attention-tier-then-phase selection, a different question. Requires
        `self.enrichment` (range comes from `facts["relative_now"]
        ["range_m"]`, BL-3) -- returns `None` when it is unset or no
        contact has a resolvable range."""
        if self.enrichment is None:
            return None
        nearest_id: str | None = None
        nearest_range_m: float | None = None
        for result in get_contacts(self.store, now_sim, enrichment=self.enrichment):
            relative_now = result["facts"].get("relative_now")
            if not isinstance(relative_now, dict):
                continue
            range_m = relative_now.get("range_m")
            if not isinstance(range_m, float):
                continue
            if nearest_range_m is None or range_m < nearest_range_m:
                contact_id = result["facts"]["id"]
                assert isinstance(contact_id, str)
                nearest_range_m = range_m
                nearest_id = contact_id
        return nearest_id

    def _handle_watch_nearest(self, now_sim: float) -> list[str]:
        contact_id = self._nearest_contact_id(now_sim)
        if contact_id is None:
            return ["no contact to watch"]
        found = set_attention(self.store, contact_id, "watch", source="player")
        result = describe_contact(
            self.store, contact_id, now_sim, enrichment=self.enrichment
        )
        if not found or result is None:
            return [f"no such contact: {contact_id}"]
        return [render_watch_nearest_readback(result["facts"]).text]

    def _handle_scan_forward(self) -> list[str]:
        """The bare AI-Wheel trigger (`aircraft_client.
        trigger_petrovich_search("forward")`), not `belief.tools.
        scan_area` -- `scan_area`'s full form needs real geometry and a
        real justification an F10 button cannot supply (plan Decision 3);
        fabricating placeholder values for those fields would be exactly
        the kind of invented-not-derived body behavior this project's
        brief warns against."""
        if self.aircraft_client is None:
            return ["no aircraft-layer connection configured"]
        try:
            self.aircraft_client.trigger_petrovich_search("forward")
            return ["scanning forward"]
        except AircraftLayerError:
            logger.warning(
                "F10 scan-forward trigger failed (continuing)", exc_info=True
            )
            return ["scan trigger failed"]

    def _handle_cancel_task(self) -> list[str]:
        """Cancels the most-recently-created still-`pending` task in
        `self.tasks`, regardless of source (plan Decision 3) -- since
        `_handle_scan_forward` above deliberately never creates a
        `PendingIntent`, and `--crew-text` mode has no other command path
        that creates one either, this currently always reports "no
        pending task" in practice; kept anyway since it becomes real the
        moment any future command path creates one while running in
        `--crew-text` mode (see the plan's Risks note)."""
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
