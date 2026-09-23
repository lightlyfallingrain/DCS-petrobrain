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

**Gaze steers the naked-eye channel (slice 2B, `plans/
detection-cones-slice2/plan.md`; the o'clock scan loop added by 2C)**:
`ConsolePerceptionRunner.run_once` resolves whichever ownship-relative
`scan_area` command is currently pending (`_active_gaze`) and assigns the
resulting `perception.gaze.ScanPlan` onto whichever of `self.sources` is a
`NakedEyePerceptionSource` (`_apply_active_gaze`), every poll, before the
sources are polled -- this is what makes an F10 "scan left" command change
what Petrovich can actually see, not just register a belief-level attention
area. No command pending means `perception.gaze.FREE_SCAN_PLAN` (2C's
default o'clock scan loop, not "no restriction" any more) -- see
`perception.gaze`'s own module docstring for the free-scan/commanded-scan
split this now resolves to. `ConsolePerceptionRunner.scan_plan` keeps that
same resolved value visible after `run_once` returns.

**Gaze is shown on the overlay, not just applied (cones 2C sortie finding,
"show where Petrovich is looking")**: `_run_console_poll_loop` and
`_run_crew_text_poll_loop` both call `_push_gaze_line` after every
`run_once()`, whenever their respective overlay client (`runner.
overlay_client` for `--console --overlay`, `crew_console.overlay_client` for
`--crew-text --overlay`) is set -- a read of `runner.scan_plan` via
`perception.gaze.gaze_at`, pushed only when the resolved o'clock cone
changes so it does not crowd out the overlay's real content on every poll.
A pure display of existing state, same posture as the lifecycle-event
mirror already on this hook point: it changes nothing about detection.

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
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TextIO

from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.audio_client import AudioAdapterClient, AudioAdapterError
from belief.console import HELP_TEXT, Console, format_event_for_overlay
from belief.contacts import ContactStore
from belief.crew_console import HELP_TEXT as CREW_TEXT_HELP_TEXT
from belief.crew_console import CrewConsole
from belief.enrichment import EnrichmentContext
from belief.escalation import BrainClient, DebugPrintBrainClient, NullBrainClient
from belief.mission_phase import MissionPhaseTracker, load_mission_understanding
from belief.optic_policy import (
    LookTarget,
    OpticDecision,
    OpticState,
    is_steady,
    look_target_for,
    lower_binoculars,
    search_pattern,
)
from belief.optic_policy import decide as decide_optic
from belief.tasks import TaskStore
from detection_trace_writer import DetectionTraceWriter
from perception.detection_trace import DetectionTraceCollector
from perception.gaze import (
    FREE_SCAN_PLAN,
    SCAN_CYCLE_PERIOD_S,
    SECTOR_WEDGE_DEG,
    Gaze,
    ScanPlan,
    gaze_at,
)
from perception.geometry import GeoPosition, open_world_model
from perception.hybrid_source import HybridPerceptionSource
from perception.naked_eye_source import NakedEyePerceptionSource
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC, Optic
from perception.source import Observation, OwnshipState, PerceptionSource
from speech_log import SpeechLogWriter

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
    #: The `perception.gaze.ScanPlan` this poll resolved (`_active_gaze`) --
    #: `FREE_SCAN_PLAN` until the first poll runs. A read, not new state:
    #: `run_once` already computes this every poll to hand it to
    #: `NakedEyePerceptionSource` (`_apply_active_gaze`); this field just
    #: keeps the same value visible to a poll loop that wants to show the
    #: pilot where Petrovich is currently looking (cones 2C sortie finding
    #: "show where Petrovich is looking") without recomputing it or reaching
    #: into `self.sources` to find the naked-eye one back out.
    scan_plan: ScanPlan = field(default_factory=lambda: FREE_SCAN_PLAN)

    #: The binocular cycle's own state (`plans/binocular-optic/plan.md`
    #: Stage 2), carried across polls because the cycle spans them -- a
    #: glass phase begins at the end of one scan and ends several polls
    #: later. Replaced wholesale each poll rather than mutated, so the
    #: decision stays a pure function and a replay reproduces it exactly.
    optic_state: OpticState = field(default_factory=OpticState)

    #: Recent `(t_sim, pitch, bank, heading)` samples, oldest first -- the
    #: steadiness gate's only input. Bounded because it is a *rate*
    #: estimate: a longer history would let a manoeuvre a minute ago still
    #: forbid a look, which is the opposite of what the gate is for.
    attitude_history: deque[tuple[float, float, float, float]] = field(
        default_factory=lambda: deque(maxlen=ATTITUDE_HISTORY_LEN)
    )

    #: What this poll resolved to look through, kept visible for the same
    #: reason `scan_plan` is: a poll loop showing the pilot where Petrovich
    #: is looking should be able to say *through what* without recomputing
    #: the decision.
    optic: Optic = UNAIDED_OPTIC

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
        # 2B: resolve whatever scan sector is currently commanded and hand
        # the naked-eye source a frozen Gaze before it polls (`_active_
        # gaze`'s own docstring) -- a no-op for every other source, and
        # when no scan command is pending.
        self.attitude_history.append(
            (
                ownship.t_sim,
                ownship.pitch_deg,
                ownship.bank_deg,
                ownship.heading_true_deg,
            )
        )
        self.scan_plan = _active_gaze(self.tasks)
        self.optic_state, optic_decision = decide_optic(
            self.optic_state,
            now_sim=ownship.t_sim,
            scan_cycle_period_s=SCAN_CYCLE_PERIOD_S,
            targets=_look_targets(self.store, ownship),
            steady=is_steady(list(self.attitude_history)),
            search=_search_sweep(self.scan_plan, ownship),
        )
        self.optic = optic_decision.optic
        _apply_active_gaze(
            self.sources, self.tasks, scan_plan=self.scan_plan, decision=optic_decision
        )
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


def _active_gaze(tasks: TaskStore) -> ScanPlan:
    """The `ScanPlan` implied by whatever ownship-relative scan sector is
    currently commanded (`plans/detection-cones-slice2/plan.md`'s 2B,
    closing `todo/todo.md`'s "Scan commands should drive naked-eye
    perception"; generalised from a static `Gaze` to a `ScanPlan` by 2C) --
    or `FREE_SCAN_PLAN` (the o'clock scan loop, `perception.gaze`'s own
    module docstring) when no such command is pending.

    Reads `PendingIntent.area.relative_sector`/`created_sim` directly,
    never the store's live re-projected `AttentionArea` (`ContactStore.
    reproject_relative_areas`) -- a relative sector's *direction* is
    body-relative and invariant under reprojection; only its absolute
    world-bearing projection changes with ownship heading, which this
    function has no use for. This also sidesteps `belief.tasks`'s own
    documented staleness caveat around `task.area` (its module docstring)
    entirely, since nothing here needs the live area at all.
    `task.created_sim` becomes `ScanPlan.command_t_sim` -- the sim time the
    scan was ordered, which is what a commanded scan's o'clock legs cycle
    from (`perception.gaze.gaze_at`'s own docstring).

    The most recently created still-active `scan_area` task wins when more
    than one is active -- a later scan command is what a player issuing
    "scan left" then "scan right" would expect to take effect.

    **Unaffected by `watch_contact` tasks** (`plans/watch-as-standing-mode/
    plan.md`) -- the `kind == "scan_area"` check above already excludes
    them, and a `watch_contact` task's `area` is `None` regardless (`belief.
    tasks.PendingIntent`'s own docstring), so gaze and watch can be
    commanded independently and coexist without this function needing to
    know a second kind exists.

    **Cones 2C sortie fix: honours any status except `"cancelled"`, not
    only `"pending"`.** `belief.tasks.TaskStore.tick` flips a `scan_area`
    task to `"succeeded"` the instant any contact is seen inside its area
    -- with the old `status == "pending"` check here, that meant a
    commanded scan silently reverted to free scan on first contact, which
    is what produced the sortie's "commanded scan left, still got reports
    from 12 o'clock" finding (free scan revisits 12 o'clock twice per
    cycle). A `scan_area` task is a standing *mode* (`belief.tasks.
    TaskStatus`'s own docstring, `docs/concept/STATE_TRANSITIONS.md`'s
    "Modes" section): finding something, or timing out
    (`DEFAULT_SCAN_DEADLINE_S`), is an event about what the search has
    (not) confirmed, never the end of the mode. Only an explicit cancel
    (`TaskStore.cancel`, also fixed by this same sortie finding to actually
    reach a resolved task) or a newer scan command (via this function's own
    "most recent" tie-break) ends it."""
    for task in reversed(tasks.tasks):
        if (
            task.kind == "scan_area"
            and task.status != "cancelled"
            and task.area is not None
            and task.area.relative_sector is not None
        ):
            return ScanPlan(
                commanded_sector=task.area.relative_sector,
                command_t_sim=task.created_sim,
            )
    return FREE_SCAN_PLAN


def _look_targets(store: ContactStore, ownship: OwnshipState) -> list[LookTarget]:
    """Every live contact, as the binocular policy needs to see it.

    **Uses the contact's *believed* type, not ground truth** -- which for a
    presence-level contact is no type at all, and `object_model.profile_for`
    degrades to its default profile there. That is the honest model rather
    than a shortcoming: deciding whether a mark is worth a closer look is a
    judgement made from the mark, and a Petrovich who sized the window by
    what the thing really is would be deciding with knowledge he does not
    have.
    """
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    return [
        look_target_for(
            contact.id,
            observer=observer,
            target_position=contact.last_position,
            heading_true_deg=ownship.heading_true_deg,
            object_type=contact.last_class_raw,
            current_level=contact.classification.level.name.lower(),
        )
        for contact in store.contacts
    ]


#: The band a binocular search sweeps: from where the naked eye runs out
#: to where the binoculars do, for a mid-sized vehicle. Sweeping nearer
#: re-covers ground the scan phase alternating with this one has already
#: covered; sweeping further covers ground the instrument cannot resolve
#: anyway. Stated as a constant rather than computed per contact because a
#: search has no contact yet -- that is what it is looking for.
_SEARCH_BAND_M: tuple[float, float] = (2_333.0, 5_647.0)


def _search_sweep(
    scan_plan: ScanPlan, ownship: OwnshipState
) -> list[tuple[float, float]]:
    """The binocular sweep for the currently-commanded sector, or empty.

    **Empty for a free scan, deliberately** (`plans/binocular-optic/
    plan.md` D6): searching is something the player asks for by naming a
    place to look. A free scan is Petrovich deciding where to look for
    himself, and turning that into a binocular sweep would spend most of
    every minute glassed for no one's reason.

    The band swept starts where the naked eye runs out and ends where the
    binoculars do -- sweeping nearer than that re-covers ground the scan
    phase alternating with this one has already covered.
    """
    if scan_plan.commanded_sector is None:
        return []
    _, half_width_deg = SECTOR_WEDGE_DEG[scan_plan.commanded_sector]
    near_m, far_m = _SEARCH_BAND_M
    fov_full_width_deg = (BINOCULAR_OPTIC.fov_half_angle_deg or 0.0) * 2.0
    if fov_full_width_deg <= 0.0:
        return []
    return search_pattern(
        sector_half_width_deg=half_width_deg,
        near_m=near_m,
        far_m=far_m,
        altitude_agl_m=max(ownship.alt_agl_m, 0.0),
        fov_full_width_deg=fov_full_width_deg,
    )


def _apply_active_gaze(
    sources: list[PerceptionSource],
    tasks: TaskStore,
    *,
    scan_plan: ScanPlan | None = None,
    decision: OpticDecision | None = None,
) -> None:
    """Assigns the resolved scan plan and optic onto whichever `sources`
    entry is a `NakedEyePerceptionSource` -- a true no-op for every other
    source, and for a `sources` list (e.g. in tests) that holds no
    naked-eye source at all. The same write-thread/single-assignment
    pattern `last_t_sim` already uses safely (`run_once`'s only caller).

    Both are applied here rather than in two places because they are one
    act -- *where he is looking and through what* -- and splitting the
    application would let a gaze and an optic from different polls be used
    for the same evaluation.

    `scan_plan`/`decision` default to `None` so the pre-binocular call
    shape (`_apply_active_gaze(sources, tasks)`) still works and still
    resolves the scan plan itself: several tests construct sources and call
    this directly, and none of them care about the optic.

    **A glass phase overrides the scan plan with a fixed look**
    (`plans/binocular-optic/plan.md` Stage 2). The look is a `ScanPlan`
    holding one direction rather than a special case in the source: the
    source already resolves `gaze_at(now_sim, scan_plan)` every poll, so a
    plan whose every leg is the same direction *is* a fixed stare, and no
    branch is needed anywhere downstream."""
    resolved_plan = scan_plan if scan_plan is not None else _active_gaze(tasks)
    optic = decision.optic if decision is not None else UNAIDED_OPTIC
    if (
        decision is not None
        and decision.look_azimuth_deg is not None
        and decision.look_elevation_deg is not None
    ):
        resolved_plan = ScanPlan.fixed_look_at(
            azimuth_deg=decision.look_azimuth_deg,
            elevation_deg=decision.look_elevation_deg,
        )
    for source in sources:
        if isinstance(source, NakedEyePerceptionSource):
            source.scan_plan = resolved_plan
            source.optic = optic


def _format_gaze_line(scan_plan: ScanPlan, gaze: Gaze) -> str:
    """One short overlay line naming where Petrovich is currently looking
    and whether that is free scan or a commanded sector (cones 2C sortie
    finding, "show where Petrovich is looking" -- the pilot could not judge
    the scan loop at all without this). `gaze.label` is always an o'clock
    hour under `gaze_at` (`"11_oclock"`, `perception.gaze.Gaze`'s own
    docstring: a label meant for exactly this kind of debug/trace display),
    reformatted here rather than branched on."""
    where = gaze.label.replace("_oclock", " o'clock")
    if scan_plan.commanded_sector is not None:
        return (
            f"Petrovich: looking {where} (commanded {scan_plan.commanded_sector} scan)"
        )
    return f"Petrovich: looking {where} (free scan)"


def _push_gaze_line(
    overlay_client: AircraftLayerClient,
    scan_plan: ScanPlan,
    t_sim: float,
    last_gaze_label: str | None,
) -> str | None:
    """Pushes one overlay line naming Petrovich's current gaze
    (`_format_gaze_line`) when it has changed since the last push, and
    returns the label to compare against next poll -- called from both
    `_run_console_poll_loop` and `_run_crew_text_poll_loop`. Deliberately
    only pushes on change: the focus cone holds for `perception.gaze.
    FOCUS_DWELL_S` (2 s), well above a typical 1 s poll interval, so pushing
    unconditionally would repeat the same line on most polls and crowd out
    the overlay's real content (lifecycle/contact-report lines, an
    `AutoScrollText` log, not a single-line display -- see
    `petrobrain-overlay-hook.lua`'s own docstring). Same per-push isolation
    as every other overlay push in this file: a failed push is logged and
    swallowed, never allowed to stop the poll loop."""
    gaze = gaze_at(t_sim, scan_plan)
    if gaze.label == last_gaze_label:
        return last_gaze_label
    try:
        overlay_client.push_text_line(_format_gaze_line(scan_plan, gaze))
    except AircraftLayerError:
        logger.warning("gaze overlay push failed (continuing)", exc_info=True)
    return gaze.label


def _build_sources(
    aircraft_client: AircraftLayerClient,
    theatre: str,
    world_model_conn: sqlite3.Connection,
    emit_mode: Literal["on_change", "every_poll"],
    trace_sink: DetectionTraceCollector | None = None,
) -> list[PerceptionSource]:
    """Construct both concrete tiers at a given `emit_mode` -- shared by
    `main()`'s plain-logger path (`"on_change"`) and `--console`/
    `--crew-text` paths (`"every_poll"`) so the two never drift apart on
    which tiers are wired in, only on their emission mode and what
    consumes their output.

    `trace_sink` (BL-9, `--detection-trace`) is additive, defaults to
    `None`, and is only ever wired into `NakedEyePerceptionSource` -- the
    scope/hybrid channel has no geometric gate chain to trace (plan
    Risks)."""
    return [
        HybridPerceptionSource(
            aircraft_client=aircraft_client, theatre=theatre, emit_mode=emit_mode
        ),
        NakedEyePerceptionSource(
            aircraft_client=aircraft_client,
            theatre=theatre,
            world_model_conn=world_model_conn,
            emit_mode=emit_mode,
            trace_sink=trace_sink,
        ),
    ]


#: How many attitude samples the steadiness gate looks back over. Three at
#: the default one-second poll interval is a few seconds of history: long
#: enough to catch a manoeuvre in progress, short enough that a bank a
#: minute ago cannot still forbid a look.
ATTITUDE_HISTORY_LEN = 3

_DEFAULT_POLL_INTERVAL_S = 1.0


def _run_console_poll_loop(
    runner: ConsolePerceptionRunner,
    aircraft_client: AircraftLayerClient,
    theatre: str,
    world_model_db: Path,
    poll_interval_s: float,
    stop_event: threading.Event,
    detection_trace_path: Path | None = None,
) -> None:
    """Stage 4's background poll thread, fixed in Stage 6: opens
    `world_model_conn` and builds `runner.sources` here, on this thread, then
    keeps calling `runner.run_once()` (which fills `runner.store` and updates
    `runner.last_t_sim`) until `stop_event` is set -- see module docstring's
    "Stage 6 fix" for why the connection can't be built by the caller and
    handed in. Closes the connection when the loop stops.

    `detection_trace_path` (BL-9, `--detection-trace`) is additive and
    defaults to `None` -- unset, this function's behavior is unchanged.
    When set, builds a `DetectionTraceCollector` and wires it into
    `_build_sources` (so `NakedEyePerceptionSource` records into it), then
    writes each poll's buffered records to `detection_trace_path` via
    `DetectionTraceWriter` immediately after `runner.run_once()` -- after
    `ingest`/`tick` have already run against this poll's `Observation`s, so
    the write can never influence what was ingested."""
    world_model_conn = open_world_model(world_model_db)
    trace_collector = (
        DetectionTraceCollector() if detection_trace_path is not None else None
    )
    trace_writer = (
        DetectionTraceWriter(detection_trace_path)
        if detection_trace_path is not None
        else None
    )
    try:
        runner.sources = _build_sources(
            aircraft_client,
            theatre,
            world_model_conn,
            emit_mode="every_poll",
            trace_sink=trace_collector,
        )
        # BL-3: same thread-affinity reasoning as `sources` above -- the
        # `EnrichmentContext` `run_once` lazily builds needs this same
        # connection, so it must be handed the connection, not build its own.
        runner.world_model_conn = world_model_conn
        runner.theatre = theatre
        last_gaze_label: str | None = None
        while not stop_event.is_set():
            runner.run_once()
            if trace_writer is not None and trace_collector is not None:
                trace_writer.write_poll(trace_collector, runner.store)
            if runner.overlay_client is not None and runner.last_t_sim is not None:
                last_gaze_label = _push_gaze_line(
                    runner.overlay_client,
                    runner.scan_plan,
                    runner.last_t_sim,
                    last_gaze_label,
                )
            stop_event.wait(poll_interval_s)
    finally:
        if trace_writer is not None:
            trace_writer.close()
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


def _poll_transcripts(
    audio_client: AudioAdapterClient, crew_console: CrewConsole, now_sim: float
) -> None:
    """Drains pending recognised-speech transcripts (`plans/inbound-speech/
    plan.md` Stage 3) and dispatches each through `CrewConsole.
    handle_transcript` -- the same per-poll dispatch shape `_poll_f10_
    commands` already uses for its own drain-on-GET endpoint. Wrapped in
    its own `try`/`except AudioAdapterError` (log-and-continue), so one
    failed poll never stops the loop.

    Each item is validated field-by-field against `transcript_queue.
    TranscriptEvent.to_dict`'s seven-field shape before dispatch -- a
    malformed/partial item (a schema mismatch, not an expected runtime
    state) is skipped rather than raising, the same defensive posture
    `_poll_f10_commands`'s `isinstance` check already takes on its own,
    simpler payload. `t_wall` (wall-clock time the adapter recognised the
    clip) is intentionally not threaded into `handle_transcript` --
    `now_sim` is this poll's own DCS sim time, the same clock every other
    dispatch path in this loop already uses."""
    try:
        transcripts = audio_client.get_transcripts()
    except AudioAdapterError:
        logger.warning("transcript poll failed (continuing)", exc_info=True)
        return
    for item in transcripts:
        transcript = item.get("transcript")
        confidence = item.get("confidence")
        token = item.get("token")
        match_ratio = item.get("match_ratio")
        verb_anchored = item.get("verb_anchored")
        ambiguous = item.get("ambiguous")
        if not isinstance(transcript, str):
            continue
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            continue
        if token is not None and not isinstance(token, str):
            continue
        if not isinstance(match_ratio, (int, float)) or isinstance(match_ratio, bool):
            continue
        if not isinstance(verb_anchored, bool):
            continue
        if not isinstance(ambiguous, bool):
            continue
        crew_console.handle_transcript(
            transcript,
            float(confidence),
            token,
            float(match_ratio),
            verb_anchored,
            ambiguous,
            now_sim,
        )


def _run_crew_text_poll_loop(
    runner: ConsolePerceptionRunner,
    crew_console: CrewConsole,
    aircraft_client: AircraftLayerClient,
    theatre: str,
    world_model_db: Path,
    poll_interval_s: float,
    stop_event: threading.Event,
    f10_commands_enabled: bool = False,
    speech_client: AudioAdapterClient | None = None,
    speech_input_enabled: bool = False,
    detection_trace_path: Path | None = None,
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
    off, a true no-op when unset. `speech_input_enabled` (`--speech-input`,
    `plans/inbound-speech/plan.md` Stage 3) is the same additive-no-op-when-
    unset shape, polling `speech_client.get_transcripts()` via `_poll_
    transcripts` -- `speech_client` is only ever non-`None` here when
    `speech_input_enabled` is set (`main()`'s own wiring), but both are
    still checked so this function has no implicit dependency on how its
    caller constructs them. `detection_trace_path` (BL-9, `--detection-
    trace`) mirrors `_run_console_poll_loop`'s own wiring exactly -- see
    that function's docstring."""
    world_model_conn = open_world_model(world_model_db)
    trace_collector = (
        DetectionTraceCollector() if detection_trace_path is not None else None
    )
    trace_writer = (
        DetectionTraceWriter(detection_trace_path)
        if detection_trace_path is not None
        else None
    )
    try:
        runner.sources = _build_sources(
            aircraft_client,
            theatre,
            world_model_conn,
            emit_mode="every_poll",
            trace_sink=trace_collector,
        )
        runner.world_model_conn = world_model_conn
        runner.theatre = theatre
        last_gaze_label: str | None = None
        while not stop_event.is_set():
            runner.run_once()
            if trace_writer is not None and trace_collector is not None:
                trace_writer.write_poll(trace_collector, runner.store)
            if runner.last_t_sim is not None:
                crew_console.enrichment = runner.enrichment
                crew_console.drain_events(runner.last_t_sim)
                commands_before = crew_console.commands_handled
                if f10_commands_enabled:
                    _poll_f10_commands(aircraft_client, crew_console, runner.last_t_sim)
                if speech_input_enabled and speech_client is not None:
                    _poll_transcripts(speech_client, crew_console, runner.last_t_sim)
                if crew_console.commands_handled != commands_before:
                    # Any command lowers the binoculars (`plans/
                    # binocular-optic/plan.md` D4) -- not per command type:
                    # the pilot asking for something is itself evidence
                    # that what Petrovich is doing matters less than what
                    # was just asked for. Counted rather than inspected so
                    # this stays true for a command surface added later.
                    runner.optic_state = lower_binoculars(
                        runner.optic_state, runner.last_t_sim
                    )
                if crew_console.overlay_client is not None:
                    last_gaze_label = _push_gaze_line(
                        crew_console.overlay_client,
                        runner.scan_plan,
                        runner.last_t_sim,
                        last_gaze_label,
                    )
            stop_event.wait(poll_interval_s)
    finally:
        if trace_writer is not None:
            trace_writer.close()
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
        "--speech-input",
        action="store_true",
        help=(
            "poll and dispatch recognised speech transcripts via "
            "audio-adapter's GET /transcripts/poll -- Stage 3, plans/"
            "inbound-speech/plan.md. Only meaningful with --crew-text; "
            "defaults off, a true no-op when absent. Requires "
            "--audio-adapter-url. Independent of --speech-audio (audio "
            "out) -- pass both to hear Petrovich act on and read back a "
            "spoken command end to end."
        ),
    )
    parser.add_argument(
        "--audio-adapter-url",
        default=None,
        help=(
            "audio-adapter base URL, e.g. http://127.0.0.1:7795 -- required "
            "together with --speech-audio and/or --speech-input, unused "
            "otherwise"
        ),
    )
    parser.add_argument(
        "--speech-log",
        type=Path,
        default=None,
        help=(
            "write one JSON line per recognised transcript to this path -- "
            "what was heard, the seven recognition fields, and what was done "
            "about it (act/confirm/say_again/fallthrough). The answer to "
            "'why did nothing happen when I said that': an utterance matching "
            "no command otherwise reaches only the brain-layer stand-in, "
            "which does nothing. Only meaningful with --crew-text "
            "--speech-input; defaults off, a true no-op when absent."
        ),
    )
    parser.add_argument(
        "--detection-trace",
        type=Path,
        default=None,
        help=(
            "write a per-poll, per-object naked-eye visibility gate trace "
            "(JSONL) to this path -- BL-9, plans/bl9-debug-visualization/"
            "plan.md. Answers 'why did Petrovich not see that' after a "
            "flight: reduce it with body-layer/tools/"
            "summarize_detection_trace.py. Only meaningful with --console "
            "or --crew-text (there is nothing to join against belief "
            "without one of those poll loops); defaults off, a true no-op "
            "when absent."
        ),
    )
    args = parser.parse_args()

    if args.crew_text and args.console:
        parser.error("--crew-text is mutually exclusive with --console")
    if args.speech_audio and args.audio_adapter_url is None:
        parser.error("--speech-audio requires --audio-adapter-url")
    if args.speech_input and args.audio_adapter_url is None:
        parser.error("--speech-input requires --audio-adapter-url")
    if args.speech_log is not None and not (args.crew_text and args.speech_input):
        parser.error(
            "--speech-log requires --crew-text --speech-input (there are no "
            "transcripts to log without them)"
        )
    if args.detection_trace is not None and not (args.console or args.crew_text):
        parser.error("--detection-trace requires --console or --crew-text")

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
        # One AudioAdapterClient instance, shared by whichever of --speech-
        # audio (push_speech, outbound) / --speech-input (get_transcripts,
        # inbound) are set -- both hit the same audio-adapter process at
        # the same --audio-adapter-url, so there is no reason to construct
        # two. CrewConsole.speech_client only takes it when --speech-audio
        # is actually set (audio *output* is its own concern, independent
        # of whether speech input is also wired).
        audio_adapter_client = (
            AudioAdapterClient(base_url=args.audio_adapter_url)
            if (args.speech_audio or args.speech_input)
            else None
        )
        crew_console = CrewConsole(
            store=crew_runner.store,
            brain_client=brain_client,
            output=sys.stdout,
            aircraft_client=aircraft_client,
            tasks=crew_runner.tasks,
            overlay_client=aircraft_client if args.overlay else None,
            speech_client=audio_adapter_client if args.speech_audio else None,
            transcript_log=(
                SpeechLogWriter(args.speech_log).write
                if args.speech_log is not None
                else None
            ),
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
                audio_adapter_client if args.speech_input else None,
                args.speech_input,
                args.detection_trace,
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
                args.detection_trace,
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
