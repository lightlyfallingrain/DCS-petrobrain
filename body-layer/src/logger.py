"""PB-1's actual deliverable: a text-only perception logger.

Polls ownship telemetry from the aircraft layer plus whatever
`PerceptionSource` it is given, and prints each `Observation` as one flat
text line (`t_sim`, aircraft position, classification, `bearing_deg`,
`range_m`) -- no LLM, no contact memory, no association. That's BL-2/PB-2.

`PerceptionLogger` itself is written entirely against `perception.source.
PerceptionSource`, so it does not know or care which concrete tier is
behind it -- per `plans/pb1-perception-logger/plan.md` stage 5. `main()`
below is the one place that plugs in a concrete tier
(`perception.hybrid_source.HybridPerceptionSource`, the only concrete
`PerceptionSource` this project builds, per that plan's stage 6/"Single
implementation, not two" section) and drives the poll loop -- kept as thin
CLI wiring, separate from `PerceptionLogger`'s own tier-agnostic logic.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import TextIO

from aircraft_client import AircraftLayerClient
from perception.hybrid_source import HybridPerceptionSource
from perception.source import Observation, OwnshipState, PerceptionSource


def format_observation_line(ownship: OwnshipState, observation: Observation) -> str:
    """Render one `Observation` as PB-1's flat-text log line."""
    return (
        f"t_sim={observation.t_sim:.2f} "
        f"aircraft=({ownship.x:.1f}, {ownship.z:.1f}, {ownship.alt_m:.1f}) "
        f"classification={observation.classification_raw} "
        f"bearing_deg={observation.bearing_deg:.1f} "
        f"range_m={observation.range_m:.0f}"
    )


@dataclass
class PerceptionLogger:
    """Ties an `AircraftLayerClient` (for ownship state) and a
    `PerceptionSource` (for observations) into the PB-1 poll loop.

    `run_once` returns the formatted lines it printed rather than only
    printing them, so tests can assert on output without capturing stdout.
    """

    aircraft_client: AircraftLayerClient
    source: PerceptionSource
    output: TextIO | None = None

    def run_once(self) -> list[str]:
        """Poll ownship telemetry once, poll `source` for observations as of
        that telemetry's `t_sim`, and print/return one formatted line per
        observation. Returns an empty list (prints nothing) if the aircraft
        layer has no telemetry yet -- absence reported as absence, not a
        fabricated poll."""
        telemetry = self.aircraft_client.get_telemetry_latest()
        if telemetry is None:
            return []
        ownship = OwnshipState.from_telemetry_dict(telemetry)
        observations = self.source.poll(ownship.t_sim, ownship)
        lines = [format_observation_line(ownship, obs) for obs in observations]
        if self.output is not None:
            for line in lines:
                print(line, file=self.output)
        return lines


_DEFAULT_POLL_INTERVAL_S = 1.0


def main() -> None:
    """CLI entrypoint: `python -m logger --aircraft-layer-url ... --theatre
    ...` -- polls `PerceptionLogger.run_once()` on a fixed interval against
    a real `HybridPerceptionSource` until interrupted. Not exercised by
    automated tests (a live/replay-loop driver, same posture as
    `aircraft-layer/src/collector/__main__.py`'s own untested `main()`);
    `PerceptionLogger`'s and `HybridPerceptionSource`'s own logic is."""
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
        "--poll-interval-s",
        type=float,
        default=_DEFAULT_POLL_INTERVAL_S,
        help="seconds between poll ticks",
    )
    args = parser.parse_args()

    aircraft_client = AircraftLayerClient(base_url=args.aircraft_layer_url)
    source = HybridPerceptionSource(
        aircraft_client=aircraft_client, theatre=args.theatre
    )
    perception_logger = PerceptionLogger(
        aircraft_client=aircraft_client, source=source, output=sys.stdout
    )

    try:
        while True:
            perception_logger.run_once()
            time.sleep(args.poll_interval_s)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
