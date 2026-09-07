"""The `PerceptionSource` interface: the seam every concrete perception tier
(Tier 1 real Petrovich feed, Tier 3 ground-truth proxy) implements, built
*before* either tier so which one wins `plans/pb1-perception-logger/plan.md`
stage 1's live spike is a config choice, not a rewrite trigger.

`poll()` deliberately takes only `(now_sim, ownship_state)` — a concrete
source is responsible for fetching whatever tier-specific data it needs on
its own (a Petrovich `list_indication` feed, or the aircraft layer's
`world_objects` endpoint via `aircraft_client.AircraftLayerClient`), usually
through an injected client a test can swap for a fixture-backed fake. This
keeps `replay.py`'s harness generic: it only has to drive the ownship half
of the loop, never any one tier's payload shape.

`Observation` here is the tier-independent subset of
`plans/body-layer/plan.md` §5's `observation:` schema — the fields every
tier can fill in without knowing about contact association, which is BL-1+
work this plan does not build. `contact_id` is always `None` from a
`PerceptionSource.poll()` call; association happens downstream, later.

`source` is a plain `str`, not a closed `Literal`/enum: the two plans this
package was built against enumerate different candidate values
(`petrovich_detection`/`inferred`/`player_report` in `plans/body-layer/
plan.md` §5, `proxy_heuristic` added in `plans/pb1-perception-logger/
plan.md`'s Affected Modules section) and neither concrete tier exists yet to
settle which values are actually needed -- closing the type now would either
under-cover or bake in a guess. Revisit once a concrete `PerceptionSource`
ships.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class OwnshipState:
    """Ownship kinematic state at one instant, in the units `perception`
    works in throughout: DCS x/z metres, altitude metres, true heading in
    **degrees** (not the aircraft-layer wire format's radians -- see
    `from_telemetry_dict`)."""

    t_sim: float
    x: float
    z: float
    alt_m: float
    heading_true_deg: float

    @staticmethod
    def from_telemetry_dict(data: dict[str, Any]) -> OwnshipState:
        """Convert one aircraft-layer `GET /telemetry/latest` JSON object
        (`aircraft-layer/src/schema/__init__.py`'s `TelemetrySample.to_dict`
        shape) into an `OwnshipState`. Mirrors `TelemetrySample.from_dict`'s
        own naming, on the consuming side of the seam.

        Raises `KeyError`/`TypeError` on a malformed dict -- callers that
        read straight from the network (`logger.py`) are expected to treat
        those as a dropped/skipped poll, the same way
        `collector.server._handle_line` drops a malformed telemetry line
        rather than crashing the export loop.
        """
        return OwnshipState(
            t_sim=float(data["dcs_model_time_s"]),
            x=float(data["position_x_m"]),
            z=float(data["position_z_m"]),
            alt_m=float(data["altitude_msl_m"]),
            heading_true_deg=math.degrees(float(data["heading_true_rad"])) % 360.0,
        )


@dataclass(frozen=True, slots=True)
class DerivedWorldPosition:
    """A target position derived from bearing/range rather than read
    directly off ground truth -- `plans/body-layer/plan.md` §5's
    `observation.derived_world_position`. `None` on an `Observation` until a
    concrete source's geometry step has actually computed one."""

    x: float
    z: float
    confidence: float
    method: str


@dataclass(frozen=True, slots=True)
class Observation:
    """One tier-independent perception observation -- the return type of
    `PerceptionSource.poll()`. See the module docstring for `contact_id` and
    `source`'s scope at this stage."""

    id: str
    contact_id: str | None
    t_sim: float
    t_wall: float
    source: str
    classification_raw: str
    bearing_deg: float
    range_m: float
    ownship_at_observation: OwnshipState
    derived_world_position: DerivedWorldPosition | None
    provenance: str


@runtime_checkable
class PerceptionSource(Protocol):
    """A tier-independent producer of `Observation`s. See the module
    docstring for why `poll()`'s signature is this narrow."""

    def poll(self, now_sim: float, ownship_state: OwnshipState) -> list[Observation]:
        """Return zero or more new `Observation`s as of `now_sim`. Must not
        block indefinitely -- a live-tier implementation is responsible for
        its own network/IO timeouts."""
        ...
