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

**`!inject-urgent <contact_id> <text...>`.** Stage 5's manual bypass_gate
proof (the plan's accepted decision: no real threat-detection channel
exists yet, so this is a clearly-labelled test harness, not a production
intent or a detector). Constructs a `belief.speech.UrgentCall` and routes it
through the same `route_event` gate the proactive path uses, demonstrating
ordering/pre-emption without pretending a real missile-launch/tracer
detector exists."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TextIO

from aircraft_client import AircraftLayerClient
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
    route_event,
)
from belief.tools import set_attention
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
    _next_utterance_number: int = field(default=0, repr=False)

    def handle_line(self, line: str, now_sim: float) -> list[str]:
        stripped = line.strip()
        if not stripped:
            return []
        if stripped.startswith("!inject-urgent"):
            lines = self._handle_inject_urgent(stripped, now_sim)
        else:
            lines = self._handle_utterance(stripped, now_sim)
        self._print(lines)
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
        self._print(spoken)
        return spoken

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

    def _handle_inject_urgent(self, line: str, now_sim: float) -> list[str]:
        parts = line.split(maxsplit=2)
        if len(parts) != 3:
            return ["usage: !inject-urgent <contact_id> <text>"]
        _, contact_id, text = parts
        speech = route_event(
            self.store, UrgentCall(contact_id=contact_id, text=text), now_sim
        )
        return [speech.text] if speech is not None else []

    def _print(self, lines: list[str]) -> None:
        if self.output is not None:
            for line in lines:
                print(line, file=self.output)
