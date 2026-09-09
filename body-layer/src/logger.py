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

**`--console` (PB-2 Stage 3)**: the plain text-logger path above is
unchanged and stays the default -- both sources still built at their
`emit_mode="on_change"` default. `--console` instead builds both sources at
`emit_mode="every_poll"` (Stage 3's fix for the Interface confirmation
section's gap 2: source-level debounce starves the belief layer of the
continuity `belief.decay`'s certainty ladder needs) and drives
`ConsolePerceptionRunner`, which ingests+ticks a `belief.contacts.
ContactStore` each poll instead of formatting text lines. Its only
observable output for this stage is a periodic contact/observation-count
line -- Stage 4 replaces that with the real `belief.console` REPL; building
that REPL is explicitly out of scope here.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TextIO

from aircraft_client import AircraftLayerClient
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
    sources: list[PerceptionSource]
    store: ContactStore = field(default_factory=ContactStore)
    output: TextIO | None = None

    def run_once(self) -> list[Observation]:
        """Poll ownship telemetry once, poll every source for observations
        as of that telemetry's `t_sim`, ingest+tick them into `store`, and
        print one minimal contact/observation-count line. Returns an empty
        list (prints nothing) if the aircraft layer has no telemetry yet,
        mirroring `PerceptionLogger.run_once`."""
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
            "ContactStore) instead of the plain on_change text logger -- "
            "PB-2 Stage 3; prints a periodic contact/observation-count line "
            "only, the real console REPL is Stage 4"
        ),
    )
    args = parser.parse_args()

    aircraft_client = AircraftLayerClient(base_url=args.aircraft_layer_url)
    world_model_conn = open_world_model(args.world_model_db)

    try:
        if args.console:
            console_runner = ConsolePerceptionRunner(
                aircraft_client=aircraft_client,
                sources=_build_sources(
                    aircraft_client,
                    args.theatre,
                    world_model_conn,
                    emit_mode="every_poll",
                ),
                output=sys.stdout,
            )
            while True:
                console_runner.run_once()
                time.sleep(args.poll_interval_s)
        else:
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


if __name__ == "__main__":
    main()
