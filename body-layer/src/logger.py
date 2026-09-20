"""PB-1's actual deliverable: a text-only perception logger. PB-2 Stage 3
(`plans/pb2-contact-memory/plan.md`) adds a second, belief-consuming mode
behind `--console`.

Polls ownship telemetry from the aircraft layer plus whatever
`PerceptionSource`s it is given, and prints each `Observation` as one flat
text line (`t_sim`, aircraft position, `source`, classification,
`bearing_deg`, `range_m`) -- no LLM, no contact memory, no association.
That's BL-2/PB-2.

`PerceptionLogger` itself is written entirely against `perception.source.
PerceptionSource`, so it does not know or care which concrete tier(s) are
behind it -- per `plans/pb1-perception-logger/plan.md` stage 5. `main()`
below is the one place that plugs in concrete tiers
(`perception.hybrid_source.HybridPerceptionSource` and, per
`plans/pb1.5-naked-eye-detection/plan.md` stage 3,
`perception.naked_eye_source.NakedEyePerceptionSource`) and drives the poll
loop -- kept as thin CLI wiring, separate from `PerceptionLogger`'s own
tier-agnostic logic.

**Two sources, no `CompositePerceptionSource`** (PB-1.5 plan's Affected
Modules section, a local/reversible decision): `PerceptionLogger` holds a
plain `list[PerceptionSource]`, polls each every tick, and concatenates the
returned `Observation`s before formatting/printing --
`PerceptionSource.poll()` already returns `list[Observation]`, so no new
type is needed to combine multiple sources' output. Revisit only if a third
source or real fusion logic (that plan's Decision #3) makes a composite
class earn its keep.

**`--console` (PB-2 Stage 3, extended by Stage 4)**: the plain text-logger
path above is unchanged and stays the default -- both sources still built at
their `emit_mode="on_change"` default. `--console` instead builds both
sources at `emit_mode="every_poll"` (Stage 3's fix for the Interface
confirmation section's gap 2: source-level debounce starves the belief layer
of the continuity `belief.decay`'s certainty ladder needs) and drives
`ConsolePerceptionRunner`, which ingests+ticks a `belief.contacts.
ContactStore` each poll instead of formatting text lines, printing a
periodic contact/observation-count line.

Stage 4 adds the real `belief.console.Console` REPL on top of that poll
loop: `main()` runs `ConsolePerceptionRunner.run_once()` on a background
daemon thread (`_run_console_poll_loop`) while the foreground thread reads
commands from stdin and dispatches them into `Console.handle_line`, against
the same `ContactStore` the poll loop is filling. `ConsolePerceptionRunner.
last_t_sim` is the seam between the two: the poll thread updates it every
poll, the REPL thread reads it as `now_sim` for whatever command the user
just typed. This is deliberately the simplest wiring that lets a live
operator type `contacts`/`show <id>`/etc. while telemetry keeps flowing --
not a claim of hardened concurrency, appropriate for a single-user debug
console over an in-memory store.

**Stage 6 fix (live acceptance testing finding, `plans/pb2-contact-memory/
implementation.md` "Stage 6 findings")**: `_run_console_poll_loop` opens its
own `world_model_conn` (via `open_world_model`) and builds its own `sources`
(via `_build_sources`) *on the poll thread itself*, rather than receiving a
`ConsolePerceptionRunner` whose `sources` already hold a connection opened
on `main()`'s thread. `sqlite3.Connection`s are thread-affine by default
(`check_same_thread=True`, and `open_world_model` never overrides that) --
a connection opened on one thread and queried from another raises
`sqlite3.ProgrammingError` on first use. The plain (non-`--console`) path
never hit this because connection-open, `_build_sources`, and the poll loop
all stay on the single main thread there; only `--console`'s background
poll thread crosses a thread boundary with the connection. `main()` still
constructs `ConsolePerceptionRunner` up front with an empty `sources` list
-- its `store`/`output`/`last_t_sim` fields are safe to share across
threads (Stage 4 reviewer-confirmed), only `sources` (and the connection it
holds) needed to move.

**REPL-thread enrichment fix (BL-5 live acceptance testing finding,
`plans/bl5-tool-api/debug.md`)**: BL-3 re-introduced the same thread-affinity
bug Stage 6 fixed above, in a second field Stage 6 didn't cover.
`ConsolePerceptionRunner.enrichment` is built on the poll thread and holds
*that thread's* `world_model_conn`; `_run_console_repl` used to copy it
straight into `console.enrichment`, so any enrichment-aware command
(`situation`/`position`/`place`/`show`/`contacts`/`find`) run from the REPL
thread queried the poll thread's connection and raised
`sqlite3.ProgrammingError`. `_run_console_repl` now lazily builds its own
REPL-thread-local `sqlite3.Connection`/`EnrichmentContext` (mirroring Stage
6's "build it on the thread that uses it" precedent) instead of reading
`runner.enrichment` at all -- see that function's own docstring for the
full reasoning, including the accepted cost of a second connection/cache.

**`--overlay` (BL-2.5, `plans/dcs-text-panel-output/plan.md`; extended by
`plans/overlay-speech-callouts/plan.md`)**: only meaningful alongside
`--console` or `--crew-text`. With `--console`, `main()` passes the same
`AircraftLayerClient` instance as `ConsolePerceptionRunner.overlay_client`,
so every newly materialised lifecycle event
(`CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED`) is mirrored to the
in-cockpit text overlay via `POST /text/push`. With `--crew-text`, `main()`
instead passes it as `CrewConsole.overlay_client`, so every line
`CrewConsole` speaks (readbacks, contact reports, drained lifecycle events,
and injected urgent calls prefixed `"!! "`) is pushed verbatim -- a radio-
callout feed, not the lifecycle-event mirror `--console --overlay` carries.
Defaults off -- a true no-op when absent, since the relevant
`overlay_client` field stays `None` and neither path touches the
aircraft-layer client for this purpose. `PerceptionLogger`'s plain
(non-`--console`/`--crew-text`) per-`Observation` stream deliberately does
not get this wiring (line-noise vs. signal tradeoff, see the BL-2.5 plan's
"Deliberately not modified" section).

**`--mission-understanding PATH` (BL-7, `plans/bl7-mission-phase-relevance/
plan.md`)**: optional. When given, `main()` calls `belief.mission_phase.
load_mission_understanding(path)` once at startup (a mission-interpreter
`--emit-compact` JSON artifact -- a plain file read/JSON parse, never a
Python import of mission-interpreter's own code, per root `CLAUDE.md`'s
module-independence rule) and constructs one `belief.mission_phase.
MissionPhaseTracker`, held alongside (not inside) `EnrichmentContext` --
mission phase isn't world-model/ownship-shaped state, it has its own
lifecycle. The *same* tracker instance is threaded into whichever
`ConsolePerceptionRunner` is built (`--console` or `--crew-text`) and, for
`--console`, into `Console` too. `ConsolePerceptionRunner.run_once` is the
only place that ever mutates it (`.update()`, poll thread); `Console`'s
`situation` command only ever reads it (`.current_phase()`, REPL thread) --
the same write-thread/read-thread split `EnrichmentContext.ownship`
already uses, deliberately, to avoid reproducing this codebase's recurring
sqlite thread-affinity defect class (BL-2 Stage 6, BL-5) in a new field.
Omitted (default `None`): a true no-op, `get_situation`'s `mission_phase`
fact is absent entirely, same as before this milestone. Only meaningful
with `--console` (`get_situation`'s only caller); harmless but otherwise
unused with `--crew-text` or the plain logger path.

**`--crew-text` (BL-5a, `plans/bl5a-text-mode-crew-interaction/plan.md`;
`--overlay` combination added by `plans/overlay-speech-callouts/plan.md`)**:
runs `belief.crew_console.CrewConsole` -- the player-facing text channel --
instead of `--console`'s developer debug REPL. Reuses the exact same
`ConsolePerceptionRunner` poll-loop machinery Stage 4/6 already built
(`_run_crew_text_poll_loop` mirrors `_run_console_poll_loop` byte-for-byte
except for one extra call: after each `runner.run_once()`, it calls
`crew_console.drain_events(runner.last_t_sim)` so newly ticked lifecycle
events get spoken through `belief.speech.route_event`, the same hook point
`--console --overlay` uses for its own mirroring). **Mutually exclusive
with `--console` only** (`--overlay` is valid alongside either) -- running
the debug console and the crew session against the same `ContactStore`
concurrently is not a validated interaction. `--brain-client debug|null`
selects which `belief.escalation.BrainClient` stand-in handles escalated
utterances (`debug`, the default, prints escalations to stderr for session
visibility; `null` is silent) -- neither produces spoken output, since no
real brain exists yet.

**`--speech-audio` (BL-10 first slice, `plans/tts-voice-output/plan.md`)**:
only meaningful alongside `--crew-text` (a true no-op otherwise, same
additive posture as `--overlay`/`--f10-commands`). When set, `main()`
builds a `belief.audio_client.AudioAdapterClient` from `--audio-adapter-url`
(required together with `--speech-audio`) and passes it as `CrewConsole.
speech_client`, so every line `CrewConsole` speaks is also synthesized and
made audible via `audio-adapter`'s `POST /speak` -- the same lines
`--crew-text --overlay` mirrors to the in-cockpit text overlay, pushed
through the identical `_print` funnel, just to a different sink and a
different process (`audio-adapter`, not the aircraft layer). `--overlay` and
`--speech-audio` are independent and combine freely.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TextIO

from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.console import HELP_TEXT, Console, format_event_for_overlay
from belief.contacts import ContactStore
from belief.crew_console import HELP_TEXT as CREW_TEXT_HELP_TEXT
from belief.crew_console import CrewConsole
from belief.enrichment import EnrichmentContext
from belief.escalation import BrainClient, DebugPrintBrainClient, NullBrainClient
from belief.mission_phase import MissionPhaseTracker, load_mission_understanding
from belief.audio_client import AudioAdapterClient
from belief.tasks import TaskStore
from perception.geometry import GeoPosition, open_world_model
from perception.hybrid_source import HybridPerceptionSource
from perception.naked_eye_source import NakedEyePerceptionSource
from perception.source import Observation, OwnshipState, PerceptionSource

logger = logging.getLogger(__name__)


def format_observation_line(ownship: OwnshipState, observation: Observation) -> str:
    """Render one `Observation` as PB-1's flat-text log line. `source` is
    included (PB-1.5) so a reader can tell which channel -- Hybrid's real
    HelperAI-gated detection or the naked-eye visibility filter -- produced
    a given line, now that more than one `PerceptionSource` can be polled
    per tick."""
    return (
        f"t_sim={observation.t_sim:.2f} "
        f"aircraft=({ownship.x:.1f}, {ownship.z:.1f}, {ownship.alt_m:.1f}) "
        f"source={observation.source} "
        f"classification={observation.classification_raw} "
        f"bearing_deg={observation.bearing_deg:.1f} "
        f"range_m={observation.range_m:.0f}"
    )


@dataclass
class PerceptionLogger:
    """Ties an `AircraftLayerClient` (for ownship state) and one or more
    `PerceptionSource`s (for observations) into the PB-1 poll loop.

    `run_once` returns the formatted lines it printed rather than only
    printing them, so tests can assert on output without capturing stdout.
    """

    aircraft_client: AircraftLayerClient
    sources: list[PerceptionSource]
    output: TextIO | None = None

    def run_once(self) -> list[str]:
        """Poll ownship telemetry once, poll every source in `sources` for
        observations as of that telemetry's `t_sim`, and print/return one
        formatted line per observation (concatenated across sources, in
        `sources` order). Returns an empty list (prints nothing) if the
        aircraft layer has no telemetry yet -- absence reported as absence,
        not a fabricated poll."""
        telemetry = self.aircraft_client.get_telemetry_latest()
        if telemetry is None:
            return []
        ownship = OwnshipState.from_telemetry_dict(telemetry)
        observations = [
            observation
            for source in self.sources
            for observation in source.poll(ownship.t_sim, ownship)
        ]
        lines = [format_observation_line(ownship, obs) for obs in observations]
        if self.output is not None:
            for line in lines:
                print(line, file=self.output)
        return lines


@dataclass
class ConsolePerceptionRunner:
    """PB-2 Stage 3's belief-consuming poll loop, mirroring
    `PerceptionLogger`'s own split between testable core logic and `main()`'s
    thin CLI wiring. `sources` are expected to already be constructed at
    `emit_mode="every_poll"` (`main()`'s job, not this class's) -- unlike
    `PerceptionLogger`, this class does not care what emission mode its
    sources use, it only ingests+ticks whatever they return.

    Stage 4 replaces this class's caller with the real `belief.console`
    REPL; `run_once` returns the poll's `Observation`s (mirroring
    `PerceptionLogger.run_once`'s return-what-was-produced shape) so a
    future console can drive the same loop without re-deriving it.
    """

    aircraft_client: AircraftLayerClient
    #: Defaults to empty -- Stage 6's `--console` wiring constructs this
    #: runner on the main thread before `sources` (and the sqlite connection
    #: they hold) exist, then has the poll thread populate this field with
    #: its own thread-local sources once it starts (see module docstring's
    #: "Stage 6 fix"). Tests that don't care about thread-affinity still pass
    #: `sources` explicitly, same as before.
    sources: list[PerceptionSource] = field(default_factory=list)
    store: ContactStore = field(default_factory=ContactStore)
    #: BL-6's `belief.tasks.TaskStore` (`plans/bl6-commands-inspect-adapt/
    #: plan.md`) -- ticked alongside `store` every poll (see `run_once`),
    #: the same hook point `ContactStore.tick` already runs from. Shared
    #: with whichever `Console`/`CrewConsole` instance `main()` builds on
    #: top of this runner's `store`, since `scan-area`'s handler needs the
    #: same `TaskStore` the poll loop is ticking.
    tasks: TaskStore = field(default_factory=TaskStore)
    output: TextIO | None = None
    last_t_sim: float | None = None
    #: In-cockpit text overlay mirror (BL-2.5, `--overlay`), mirroring
    #: `output`'s optional-sink pattern exactly. `None` (the default) is a
    #: true no-op -- `run_once` never touches the aircraft-layer client for
    #: this purpose unless it is set. When set, `main()` passes the *same*
    #: `AircraftLayerClient` instance already used for telemetry -- there is
    #: no separate URL/CLI argument, `POST /text/push` lives on the exact
    #: aircraft-layer instance `--aircraft-layer-url` already points at.
    overlay_client: AircraftLayerClient | None = None
    #: BL-3's world-model connection/theatre (`plans/bl3-world-enrichment/
    #: plan.md` step 6), set once by `_run_console_poll_loop` at the same
    #: point it already builds `sources` -- both need the same thread-local
    #: `sqlite3.Connection` (see the Stage 6 fix above), so `enrichment`
    #: cannot be constructed by `main()` on the main thread either.
    world_model_conn: sqlite3.Connection | None = None
    theatre: str | None = None
    #: Updated every poll (mirrors `last_t_sim`) -- not otherwise consumed
    #: by this class (`enrichment.ownship` below is the field
    #: `belief.enrichment.relative_geometry` actually reads), kept for
    #: parity with `last_t_sim`'s "latest telemetry snapshot" role and any
    #: future non-enrichment consumer.
    last_ownship_state: OwnshipState | None = None
    #: Built lazily on the first poll that has both real telemetry and a
    #: `world_model_conn`/`theatre` (i.e. always, once `_run_console_poll_
    #: loop` has set those two), then updated in place every poll after --
    #: `EnrichmentContext.ownship` is mutable specifically so the same
    #: `WorldEnrichmentCache` persists across polls (see that dataclass's
    #: own docstring). `_run_console_repl` reads this field fresh before
    #: every console command.
    enrichment: EnrichmentContext | None = None
    #: BL-7's mission-phase tracker (`plans/bl7-mission-phase-relevance/
    #: plan.md`), built once by `main()` (a plain JSON file load, not a
    #: sqlite connection -- no thread-affinity concern, unlike `sources`/
    #: `world_model_conn`/`enrichment` above) and shared as the *same*
    #: instance across the poll thread and the REPL/crew-text thread.
    #: `run_once` below is the only place that ever calls `.update()` on
    #: it (poll thread, write); `_run_console_repl`/`Console` only ever
    #: call `.current_phase()` on it (REPL thread, read) -- the same
    #: write-thread/read-thread split `last_t_sim`/`last_ownship_state`
    #: already use, chosen deliberately to avoid reproducing the sqlite
    #: thread-affinity defect class this codebase has hit twice (BL-2
    #: Stage 6, BL-5's REPL-thread enrichment fix above). `None` (the
    #: default, when `--mission-understanding` is omitted) is a true
    #: no-op: `run_once` never touches this field, `get_situation` reports
    #: no phase data, unchanged from before this milestone.
    mission_phase_tracker: MissionPhaseTracker | None = None

    def run_once(self) -> list[Observation]:
        """Poll ownship telemetry once, poll every source for observations
        as of that telemetry's `t_sim`, ingest+tick them into `store`, and
        print one minimal contact/observation-count line. Returns an empty
        list (prints nothing) if the aircraft layer has no telemetry yet,
        mirroring `PerceptionLogger.run_once`.

        `last_t_sim` is updated on every successful poll (Stage 4) -- the
        REPL loop in `main()` reads it as the `now_sim` for whatever console
        command the operator just typed, since the REPL has no telemetry
        feed of its own.

        `self.tasks.tick(self.store, ...)` (BL-6) runs immediately after
        `self.store.tick(...)`, the same poll-loop hook point -- a
        `scan_area` task's success check reads `self.store`'s freshly
        ticked contacts, so it must run after that tick, not before or
        independently scheduled.

        If `overlay_client` is set (BL-2.5), every lifecycle event newly
        appended by this call's `tick()` is formatted
        (`belief.console.format_event_for_overlay`) and pushed
        (`AircraftLayerClient.push_text_line`) to the in-cockpit overlay,
        one push per event. Each push is wrapped in its own try/except --
        this is the one place a defensive try/except is load-bearing rather
        than cosmetic (`plans/dcs-text-panel-output/plan.md` Risks &
        Unknowns): a failed push (DCS not running, network hiccup) must
        degrade to "no overlay line for this event," never stop the poll
        loop, drop the observations already collected this poll, or skip
        pushing the remaining events in the same batch."""
        telemetry = self.aircraft_client.get_telemetry_latest()
        if telemetry is None:
            return []
        ownship = OwnshipState.from_telemetry_dict(telemetry)
        self.last_ownship_state = ownship
        # Ownship-anchored attention areas track the nose, and they must be
        # re-projected *before* this tick's `ingest`/`tick` so the contacts
        # ingested below are judged against this tick's heading rather than
        # the previous one (`plans/f10-command-vocabulary/plan.md` D2). A
        # no-op (returns 0, touches nothing) when no relative area is
        # registered, which is the usual case.
        self.store.reproject_relative_areas(
            GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m),
            ownship.heading_true_deg,
        )
        if self.mission_phase_tracker is not None:
            self.mission_phase_tracker.update(
                GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
            )
        if self.world_model_conn is not None and self.theatre is not None:
            if self.enrichment is None:
                self.enrichment = EnrichmentContext(
                    conn=self.world_model_conn, theatre=self.theatre, ownship=ownship
                )
            else:
                self.enrichment.ownship = ownship
        observations = [
            observation
            for source in self.sources
            for observation in source.poll(ownship.t_sim, ownship)
        ]
        self.store.ingest(observations, now_sim=ownship.t_sim)
        events_before = len(self.store.events)
        self.store.tick(ownship.t_sim)
        self.tasks.tick(self.store, ownship.t_sim)
        self.last_t_sim = ownship.t_sim
        if self.overlay_client is not None:
            new_events = self.store.events[events_before:]
            for event in new_events:
                text = format_event_for_overlay(
                    self.store, event, ownship.t_sim, self.enrichment
                )
                try:
                    self.overlay_client.push_text_line(text)
                except AircraftLayerError:
                    logger.warning(
                        "overlay push failed for event %s (continuing)",
                        event.id,
                        exc_info=True,
                    )
        if self.output is not None:
            print(
                f"t_sim={ownship.t_sim:.2f} "
                f"contacts={len(self.store.contacts)} "
                f"observations={len(self.store.observations)}",
                file=self.output,
            )
        return observations


def _build_sources(
    aircraft_client: AircraftLayerClient,
    theatre: str,
    world_model_conn: sqlite3.Connection,
    emit_mode: Literal["on_change", "every_poll"],
) -> list[PerceptionSource]:
    """Construct both concrete tiers at a given `emit_mode` -- shared by
    `main()`'s plain-logger path (`"on_change"`) and `--console` path
    (`"every_poll"`) so the two never drift apart on which tiers are wired
    in, only on their emission mode and what consumes their output."""
    return [
        HybridPerceptionSource(
            aircraft_client=aircraft_client, theatre=theatre, emit_mode=emit_mode
        ),
        NakedEyePerceptionSource(
            aircraft_client=aircraft_client,
            theatre=theatre,
            world_model_conn=world_model_conn,
            emit_mode=emit_mode,
        ),
    ]


_DEFAULT_POLL_INTERVAL_S = 1.0


def _run_console_poll_loop(
    runner: ConsolePerceptionRunner,
    aircraft_client: AircraftLayerClient,
    theatre: str,
    world_model_db: Path,
    poll_interval_s: float,
    stop_event: threading.Event,
) -> None:
    """Stage 4's background poll thread, fixed in Stage 6: opens
    `world_model_conn` and builds `runner.sources` here, on this thread, then
    keeps calling `runner.run_once()` (which fills `runner.store` and updates
    `runner.last_t_sim`) until `stop_event` is set -- see module docstring's
    "Stage 6 fix" for why the connection can't be built by the caller and
    handed in. Closes the connection when the loop stops."""
    world_model_conn = open_world_model(world_model_db)
    try:
        runner.sources = _build_sources(
            aircraft_client, theatre, world_model_conn, emit_mode="every_poll"
        )
        # BL-3: same thread-affinity reasoning as `sources` above -- the
        # `EnrichmentContext` `run_once` lazily builds needs this same
        # connection, so it must be handed the connection, not build its own.
        runner.world_model_conn = world_model_conn
        runner.theatre = theatre
        while not stop_event.is_set():
            runner.run_once()
            stop_event.wait(poll_interval_s)
    finally:
        world_model_conn.close()


def _run_console_repl(
    runner: ConsolePerceptionRunner,
    console: Console,
    world_model_db: Path,
    theatre: str,
) -> None:
    """Stage 4's foreground REPL: reads one command per line from stdin and
    dispatches it into `console`, using `runner.last_t_sim` (set by the
    background poll thread) as `now_sim`. Before the first successful poll,
    `last_t_sim` is `None` and commands run against `now_sim=0.0` -- an
    empty store either way, so this only affects how an immediately-typed
    command's (nonexistent) elapsed-time fields would read, not correctness.

    **BL-5 live-acceptance fix**: this used to sync `console.enrichment`
    straight from `runner.enrichment` (BL-3's field, built by the poll
    thread and holding *that thread's* `sqlite3.Connection`). Any
    enrichment-aware command (`situation`/`position`/`place`, or `show`/
    `contacts`/`find` once BL-3 landed) then ran a query against that
    connection from this thread -- `sqlite3.Connection` is thread-affine
    (see the module docstring's "Stage 6 fix" for the same bug class on
    `sources`), so this raised `sqlite3.ProgrammingError` the first time a
    user actually typed one of those commands. BL-3 shipped after Stage 6's
    fix and re-introduced the same class of bug in a second field the
    Stage 6 fix didn't cover.

    The fix mirrors Stage 6's own precedent exactly: build the resource on
    the thread that uses it. This function now opens its own
    `sqlite3.Connection` (`repl_conn`) and `EnrichmentContext`
    (`repl_enrichment`), lazily, the first time `runner.last_ownship_state`
    is available (mirroring `ConsolePerceptionRunner.run_once`'s own lazy
    build of `runner.enrichment`) -- `console.enrichment` is populated from
    this REPL-thread-local context, never from `runner.enrichment`.
    `repl_enrichment.ownship` is refreshed from `runner.last_ownship_state`
    before every command, the same "read a plain attribute across the
    thread boundary" pattern `last_t_sim` above already uses safely (only
    `sqlite3.Connection`s are thread-affine, not ordinary attribute reads).

    This does mean two separate `sqlite3.Connection`s and two separate
    `belief.enrichment.WorldEnrichmentCache`s (poll thread's and REPL
    thread's) rather than one shared connection/cache -- a real but
    accepted cost: each cache recomputes independently on its own thread's
    first touch of a given contact, never produces incorrect results.
    Routing REPL-thread enrichment reads through the poll thread instead
    (a single shared connection/cache) was considered and rejected as
    disproportionate complexity (a lock/queue-based cross-thread call) for
    a single-user debug console.

    Exits on EOF (e.g. Ctrl-D) or `KeyboardInterrupt`. Closes `repl_conn`
    (if ever opened) on exit."""
    repl_conn: sqlite3.Connection | None = None
    repl_enrichment: EnrichmentContext | None = None
    try:
        for line in sys.stdin:
            now_sim = runner.last_t_sim if runner.last_t_sim is not None else 0.0
            if runner.last_ownship_state is not None:
                if repl_conn is None:
                    repl_conn = open_world_model(world_model_db)
                if repl_enrichment is None:
                    repl_enrichment = EnrichmentContext(
                        conn=repl_conn,
                        theatre=theatre,
                        ownship=runner.last_ownship_state,
                    )
                else:
                    repl_enrichment.ownship = runner.last_ownship_state
            console.enrichment = repl_enrichment
            console.handle_line(line, now_sim=now_sim)
    except KeyboardInterrupt:
        pass
    finally:
        if repl_conn is not None:
            repl_conn.close()


def _poll_f10_commands(
    aircraft_client: AircraftLayerClient, crew_console: CrewConsole, now_sim: float
) -> None:
    """Drains pending F10 radio-menu selections (`plans/f10-crew-commands/
    plan.md`) and dispatches each through `CrewConsole.handle_f10_command`
    -- the same post-`tick()` hook point `drain_events` already uses.
    Wrapped in its own `try`/`except AircraftLayerError` (log-and-continue),
    the same per-call isolation shape the BL-2.5 overlay-push loop already
    uses, so one failed poll never stops the loop."""
    try:
        commands = aircraft_client.get_f10_commands()
    except AircraftLayerError:
        logger.warning("F10 command poll failed (continuing)", exc_info=True)
        return
    for command in commands:
        token = command.get("command")
        if isinstance(token, str):
            crew_console.handle_f10_command(token, now_sim)


def _run_crew_text_poll_loop(
    runner: ConsolePerceptionRunner,
    crew_console: CrewConsole,
    aircraft_client: AircraftLayerClient,
    theatre: str,
    world_model_db: Path,
    poll_interval_s: float,
    stop_event: threading.Event,
    f10_commands_enabled: bool = False,
) -> None:
    """`--crew-text`'s background poll thread -- identical to
    `_run_console_poll_loop` (same reasons: thread-affine `sqlite3.
    Connection`, see that function's docstring / module docstring's "Stage 6
    fix"), plus one extra call per poll: `crew_console.drain_events` speaks
    whatever lifecycle events this poll's `tick()` newly surfaced, the same
    hook point `--overlay`'s mirroring uses in `ConsolePerceptionRunner.
    run_once` itself. `f10_commands_enabled` (`--f10-commands`, `plans/
    f10-crew-commands/plan.md`) additionally polls/dispatches pending F10
    radio-menu selections each cycle via `_poll_f10_commands` -- defaults
    off, a true no-op when unset."""
    world_model_conn = open_world_model(world_model_db)
    try:
        runner.sources = _build_sources(
            aircraft_client, theatre, world_model_conn, emit_mode="every_poll"
        )
        runner.world_model_conn = world_model_conn
        runner.theatre = theatre
        while not stop_event.is_set():
            runner.run_once()
            if runner.last_t_sim is not None:
                crew_console.enrichment = runner.enrichment
                crew_console.drain_events(runner.last_t_sim)
                if f10_commands_enabled:
                    _poll_f10_commands(aircraft_client, crew_console, runner.last_t_sim)
            stop_event.wait(poll_interval_s)
    finally:
        world_model_conn.close()


def _run_crew_text_repl(
    runner: ConsolePerceptionRunner, crew_console: CrewConsole
) -> None:
    """`--crew-text`'s foreground REPL -- identical shape to
    `_run_console_repl`, dispatching into `CrewConsole.handle_line` instead
    of `belief.console.Console.handle_line`."""
    try:
        for line in sys.stdin:
            now_sim = runner.last_t_sim if runner.last_t_sim is not None else 0.0
            crew_console.enrichment = runner.enrichment
            crew_console.handle_line(line, now_sim=now_sim)
    except KeyboardInterrupt:
        pass


def main() -> None:
    """CLI entrypoint: `python -m logger --aircraft-layer-url ... --theatre
    ... --world-model-db ...` -- polls `PerceptionLogger.run_once()` on a
    fixed interval against a real `HybridPerceptionSource` and (PB-1.5)
    `NakedEyePerceptionSource` until interrupted. Not exercised by automated
    tests (a live/replay-loop driver, same posture as
    `aircraft-layer/src/collector/__main__.py`'s own untested `main()`);
    `PerceptionLogger`'s, `HybridPerceptionSource`'s, and
    `NakedEyePerceptionSource`'s own logic is."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--aircraft-layer-url",
        required=True,
        help="aircraft-layer LAN API base URL, e.g. http://192.168.1.50:7791",
    )
    parser.add_argument(
        "--theatre",
        required=True,
        help="DCS theatre name for world-object lat/lon -> DCS x/z conversion, e.g. Syria",
    )
    parser.add_argument(
        "--world-model-db",
        required=True,
        type=Path,
        help=(
            "path to a built world-model region .sqlite (see body-layer/CLAUDE.md's "
            "world-model seam note) -- NakedEyePerceptionSource's visibility filter "
            "needs it for the terrain line-of-sight gate"
        ),
    )
    parser.add_argument(
        "--poll-interval-s",
        type=float,
        default=_DEFAULT_POLL_INTERVAL_S,
        help="seconds between poll ticks",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help=(
            "run the belief-consuming pipeline (both sources at "
            "emit_mode='every_poll', ingested+ticked into a belief.contacts."
            "ContactStore) and an interactive belief.console REPL over "
            "stdin instead of the plain on_change text logger -- PB-2 "
            "Stage 3/4"
        ),
    )
    parser.add_argument(
        "--overlay",
        action="store_true",
        help=(
            "mirror text to the in-cockpit text overlay via the aircraft "
            "layer's POST /text/push -- BL-2.5, extended by overlay-speech-"
            "callouts. With --console, mirrors belief lifecycle events "
            "(CONTACT_DETECTED/LOST/REACQUIRED). With --crew-text, mirrors "
            "every line CrewConsole speaks (readbacks, contact reports, "
            "lifecycle lines, urgent calls prefixed '!! ') -- a radio-"
            "callout feed, not the lifecycle-event mirror. Meaningless "
            "without --console or --crew-text; defaults off, a true no-op "
            "when absent. Reuses the same --aircraft-layer-url instance, "
            "no separate URL needed."
        ),
    )
    parser.add_argument(
        "--crew-text",
        action="store_true",
        help=(
            "run the player-facing crew session (belief.crew_console."
            "CrewConsole) instead of the plain on_change text logger -- "
            "BL-5a. Mutually exclusive with --console; combine with "
            "--overlay to also mirror spoken crew text to the in-cockpit "
            "overlay (overlay-speech-callouts)."
        ),
    )
    parser.add_argument(
        "--mission-understanding",
        type=Path,
        default=None,
        help=(
            "path to a mission-interpreter --emit-compact JSON artifact "
            "(BL-7, plans/bl7-mission-phase-relevance/plan.md) -- when "
            "given, loaded once at startup and used to track live mission "
            "phase against ownship position, surfaced via get_situation's "
            "'situation' command. Omitted (default): no phase data, "
            "unchanged from before this milestone. Only meaningful with "
            "--console."
        ),
    )
    parser.add_argument(
        "--f10-commands",
        action="store_true",
        help=(
            "poll and dispatch player-selected DCS F10 radio-menu commands "
            "(watch nearest / scan forward / cancel task) through "
            "CrewConsole.handle_f10_command -- plans/f10-crew-commands/"
            "plan.md. Only meaningful with --crew-text; defaults off, a "
            "true no-op when absent. Reuses the same --aircraft-layer-url "
            "instance, no separate URL needed."
        ),
    )
    parser.add_argument(
        "--brain-client",
        choices=("debug", "null"),
        default="debug",
        help=(
            "which belief.escalation.BrainClient stand-in handles escalated "
            "utterances under --crew-text -- 'debug' (default) prints "
            "escalations to stderr, 'null' is silent. Neither speaks, since "
            "no real brain exists yet."
        ),
    )
    parser.add_argument(
        "--speech-audio",
        action="store_true",
        help=(
            "synthesize and play every line CrewConsole speaks via "
            "audio-adapter's POST /speak -- BL-10 first slice, plans/"
            "tts-voice-output/plan.md. Only meaningful with --crew-text; "
            "defaults off, a true no-op when absent. Requires "
            "--audio-adapter-url."
        ),
    )
    parser.add_argument(
        "--audio-adapter-url",
        default=None,
        help=(
            "audio-adapter base URL, e.g. http://127.0.0.1:7795 -- required "
            "together with --speech-audio, unused otherwise"
        ),
    )
    args = parser.parse_args()

    if args.crew_text and args.console:
        parser.error("--crew-text is mutually exclusive with --console")
    if args.speech_audio and args.audio_adapter_url is None:
        parser.error("--speech-audio requires --audio-adapter-url")

    aircraft_client = AircraftLayerClient(base_url=args.aircraft_layer_url)

    # BL-7: a plain JSON file load, not a sqlite connection -- built once,
    # here, on the main thread, before either poll thread starts, and
    # shared as the same MissionPhaseTracker instance across threads (see
    # ConsolePerceptionRunner.mission_phase_tracker's own docstring for the
    # write-thread/read-thread split this relies on).
    mission_phase_tracker: MissionPhaseTracker | None = None
    if args.mission_understanding is not None:
        mission_data = load_mission_understanding(args.mission_understanding)
        mission_phase_tracker = MissionPhaseTracker(data=mission_data)

    if args.crew_text:
        brain_client: BrainClient = (
            DebugPrintBrainClient()
            if args.brain_client == "debug"
            else NullBrainClient()
        )
        crew_runner = ConsolePerceptionRunner(
            aircraft_client=aircraft_client,
            output=None,
            mission_phase_tracker=mission_phase_tracker,
        )
        speech_client = (
            AudioAdapterClient(base_url=args.audio_adapter_url)
            if args.speech_audio
            else None
        )
        crew_console = CrewConsole(
            store=crew_runner.store,
            brain_client=brain_client,
            output=sys.stdout,
            aircraft_client=aircraft_client,
            tasks=crew_runner.tasks,
            overlay_client=aircraft_client if args.overlay else None,
            speech_client=speech_client,
        )
        stop_event = threading.Event()
        poll_thread = threading.Thread(
            target=_run_crew_text_poll_loop,
            args=(
                crew_runner,
                crew_console,
                aircraft_client,
                args.theatre,
                args.world_model_db,
                args.poll_interval_s,
                stop_event,
                args.f10_commands,
            ),
            daemon=True,
        )
        poll_thread.start()
        print(CREW_TEXT_HELP_TEXT, file=sys.stdout)
        try:
            _run_crew_text_repl(crew_runner, crew_console)
        finally:
            stop_event.set()
            poll_thread.join()
    elif args.console:
        # Stage 6 fix: no world_model_conn opened here -- the poll thread
        # opens its own (see _run_console_poll_loop / module docstring's
        # "Stage 6 fix"), since sqlite3 connections are thread-affine and
        # this runner's sources are consumed only on that thread.
        console_runner = ConsolePerceptionRunner(
            aircraft_client=aircraft_client,
            output=None,
            overlay_client=aircraft_client if args.overlay else None,
            mission_phase_tracker=mission_phase_tracker,
        )
        stop_event = threading.Event()
        poll_thread = threading.Thread(
            target=_run_console_poll_loop,
            args=(
                console_runner,
                aircraft_client,
                args.theatre,
                args.world_model_db,
                args.poll_interval_s,
                stop_event,
            ),
            daemon=True,
        )
        poll_thread.start()
        console = Console(
            store=console_runner.store,
            tasks=console_runner.tasks,
            output=sys.stdout,
            aircraft_client=aircraft_client,
            mission_phase_tracker=mission_phase_tracker,
        )
        print(HELP_TEXT, file=sys.stdout)
        try:
            _run_console_repl(
                console_runner, console, args.world_model_db, args.theatre
            )
        finally:
            stop_event.set()
            poll_thread.join()
    else:
        world_model_conn = open_world_model(args.world_model_db)
        try:
            perception_logger = PerceptionLogger(
                aircraft_client=aircraft_client,
                sources=_build_sources(
                    aircraft_client,
                    args.theatre,
                    world_model_conn,
                    emit_mode="on_change",
                ),
                output=sys.stdout,
            )
            while True:
                perception_logger.run_once()
                time.sleep(args.poll_interval_s)
        except KeyboardInterrupt:
            pass
        finally:
            world_model_conn.close()


if __name__ == "__main__":
    main()
