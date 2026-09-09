"""`Percept` -- the mechanical enforcement of "belief may only see what was
perceived" (`plans/pb2-contact-memory/plan.md`'s Interface confirmation gap
3, and the Decision section's identity invariant).

`perception.source.Observation` carries `derived_world_position` (DCS
ground truth x/z) alongside the perceived bearing/range on both concrete
tiers -- convenient for `logger.py`'s text output and for future
world-enrichment work (BL-3), but exactly the field belief code must never
read. Rather than rely on every future `belief/` function remembering not
to touch `observation.derived_world_position` or `observation.id`-as-DCS-
truth, `Percept` is a *structurally* narrower type: it has no field that
could carry a truth value, so a downstream function literally cannot reach
one by accident, only by explicitly bypassing this projection and importing
`perception.source.Observation` itself. `belief.contacts` and
`belief.association_over_time` therefore only ever see `Percept`s.

`observation_id` is kept (it identifies *which perceived report* this is,
for provenance/history -- `plans/body-layer/plan.md` §3.4's per-contact
observation history), not a truth field: it is not derived from any DCS
object id, only from the per-source counter `perception.source`'s id-prefix
constants keep collision-free across channels.
"""

from __future__ import annotations

from dataclasses import dataclass

from perception.source import Observation, OwnshipState


@dataclass(frozen=True, slots=True)
class Percept:
    """One perceived report, stripped of every DCS truth field. Everything
    here is either what a crew member could plausibly have perceived
    (`classification_raw`, `bearing_deg`, `range_m`) or bookkeeping about
    the report itself (`t_sim`, `source`, `ownship_at_observation`,
    `observation_id`) -- never a ground-truth position, object id, or
    coalition/type field lifted from `LoGetWorldObjects`."""

    t_sim: float
    source: str
    classification_raw: str
    bearing_deg: float
    range_m: float
    ownship_at_observation: OwnshipState
    observation_id: str


def percept_of(observation: Observation) -> Percept:
    """Project one `Observation` down to its `Percept`. The only place in
    this codebase that reads `Observation.derived_world_position` or
    `Observation.id`-as-a-truth-key and then *discards* them -- every other
    function in `belief/` receives a `Percept`, never the `Observation`
    itself."""
    return Percept(
        t_sim=observation.t_sim,
        source=observation.source,
        classification_raw=observation.classification_raw,
        bearing_deg=observation.bearing_deg,
        range_m=observation.range_m,
        ownship_at_observation=observation.ownship_at_observation,
        observation_id=observation.id,
    )
