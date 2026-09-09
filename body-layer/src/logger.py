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
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TextIO

from aircraft_client import AircraftLayerClient
from belief.console import HELP_TEXT, Console
from belief.contacts import ContactStore
from perception.geometry import open_world_model
from perception.hybrid_source import HybridPerceptionSource
from perception.naked_eye_source import NakedEyePerceptionSource
from perception.source import Observation, OwnshipState, PerceptionSource


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
    output: TextIO | None = None
    last_t_sim: float | None = None

    def run_once(self) -> list[Observation]:
        """Poll ownship telemetry once, poll every source for observations
        as of that telemetry's `t_sim`, ingest+tick them into `store`, and
        print one minimal contact/observation-count line. Returns an empty
        list (prints nothing) if the aircraft layer has no telemetry yet,
        mirroring `PerceptionLogger.run_once`.

        `last_t_sim` is updated on every successful poll (Stage 4) -- the
        REPL loop in `main()` reads it as the `now_sim` for whatever console
        command the operator just typed, since the REPL has no telemetry
        feed of its own."""
        telemetry = self.aircraft_client.get_telemetry_latest()
        if telemetry is None:
            return []
        ownship = OwnshipState.from_telemetry_dict(telemetry)
        observations = [
            observation
            for source in self.sources
            for observation in source.poll(ownship.t_sim, ownship)
        ]
        self.store.ingest(observations, now_sim=ownship.t_sim)
        self.store.tick(ownship.t_sim)
        self.last_t_sim = ownship.t_sim
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
        while not stop_event.is_set():
            runner.run_once()
            stop_event.wait(poll_interval_s)
    finally:
        world_model_conn.close()


def _run_console_repl(runner: ConsolePerceptionRunner, console: Console) -> None:
    """Stage 4's foreground REPL: reads one command per line from stdin and
    dispatches it into `console`, using `runner.last_t_sim` (set by the
    background poll thread) as `now_sim`. Before the first successful poll,
    `last_t_sim` is `None` and commands run against `now_sim=0.0` -- an
    empty store either way, so this only affects how an immediately-typed
    command's (nonexistent) elapsed-time fields would read, not correctness.
    Exits on EOF (e.g. Ctrl-D) or `KeyboardInterrupt`."""
    try:
        for line in sys.stdin:
            now_sim = runner.last_t_sim if runner.last_t_sim is not None else 0.0
            console.handle_line(line, now_sim=now_sim)
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
    args = parser.parse_args()

    aircraft_client = AircraftLayerClient(base_url=args.aircraft_layer_url)

    if args.console:
        # Stage 6 fix: no world_model_conn opened here -- the poll thread
        # opens its own (see _run_console_poll_loop / module docstring's
        # "Stage 6 fix"), since sqlite3 connections are thread-affine and
        # this runner's sources are consumed only on that thread.
        console_runner = ConsolePerceptionRunner(
            aircraft_client=aircraft_client,
            output=None,
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
        console = Console(store=console_runner.store, output=sys.stdout)
        print(HELP_TEXT, file=sys.stdout)
        try:
            _run_console_repl(console_runner, console)
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
