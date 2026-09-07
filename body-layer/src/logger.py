"""PB-1's actual deliverable: a text-only perception logger.

Polls ownship telemetry from the aircraft layer plus whatever
`PerceptionSource` it is given, and prints each `Observation` as one flat
text line (`t_sim`, aircraft position, classification, `bearing_deg`,
`range_m`) -- no LLM, no contact memory, no association. That's BL-2/PB-2.

Written entirely against `perception.source.PerceptionSource`, so it does
not know or care which concrete tier is behind it -- per
`plans/pb1-perception-logger/plan.md` stage 5. No concrete tier exists yet
(stage 1's live spike, and stage 4's tier branch it gates, are both out of
this plan's scope), so there is deliberately no `__main__`/CLI entrypoint
here yet: constructing a real `PerceptionLogger` needs a real
`PerceptionSource` to pass in, which does not exist until stage 4 picks a
tier. `PerceptionLogger` itself is fully built and tested (against a fake
`PerceptionSource`) so that stage 4+ only has to plug a concrete source in
and add the entrypoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TextIO

from aircraft_client import AircraftLayerClient
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
