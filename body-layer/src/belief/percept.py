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

from perception.source import Observation, OwnshipState, PositionUncertainty


@dataclass(frozen=True, slots=True)
class Percept:
    """One perceived report, stripped of every DCS truth field. Everything
    here is either what a crew member could plausibly have perceived
    (`classification_raw`, `classification_level`, `bearing_deg`,
    `range_m`) or bookkeeping about the report itself (`t_sim`, `source`,
    `ownship_at_observation`, `observation_id`) -- never a ground-truth
    position, object id, or coalition/type field lifted from
    `LoGetWorldObjects`.

    `classification_level` carries `perception.source.Observation`'s own
    field through unchanged (see that field's docstring) -- perceived
    metadata about how specific the claim is, not a truth field, so it
    belongs on this side of the boundary same as `classification_raw`
    itself.

    `continues_observation_id` carries `Observation`'s own field of the same
    name through unchanged, for the same reason `classification_level`
    does: it is perceived-report bookkeeping (an `observation_id`-shaped
    reference to an earlier report), never a DCS truth field -- see that
    field's docstring (`perception/source.py`) and `plans/
    contact-duplication-ambiguity-runaway/plan.md`'s Boundary reading
    section.

    `count_bucket` carries `Observation.count_bucket` through unchanged, for
    the same reason -- a channel's own honest statement of how many real
    objects this report stands for, `plans/group-contact-model/plan.md`
    Stage 2.

    `apparent_motion` carries `Observation.apparent_motion` through
    unchanged, for the same reason (`plans/movement-detection/plan.md`):
    `perception.motion.is_apparently_moving`'s tri-state verdict is
    perceived metadata, not a truth field -- the velocity vector it was
    computed from never reaches this side of the boundary at all.

    `position_uncertainty` carries `Observation.position_uncertainty`
    through unchanged (`plans/precise-position-belief/plan.md` Stage 1) --
    the channel's own declared error ellipse for `bearing_deg`/`range_m`,
    perceived metadata on the same footing as everything else on this
    dataclass, never a truth field.

    `live_los_clear` carries `Observation.live_los_clear` through unchanged
    (`plans/dcs-driven-los/plan.md`, X-B29) -- a DCS-driven *fact about
    physical space* (whether a sightline was clear), not an identity or
    position claim, so it crosses this boundary on the same footing as
    everything else here: the moment a naked-eye observation is admitted
    is itself proof the ray was clear (see the plan's own "why this is not
    a boundary violation" section). Belief remembers this value; it never
    re-derives it."""

    t_sim: float
    source: str
    classification_raw: str
    bearing_deg: float
    range_m: float
    ownship_at_observation: OwnshipState
    observation_id: str
    classification_level: int = 2
    continues_observation_id: str | None = None
    count_bucket: str | None = None
    apparent_motion: bool | None = None
    position_uncertainty: PositionUncertainty | None = None
    live_los_clear: bool | None = None


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
        classification_level=observation.classification_level,
        continues_observation_id=observation.continues_observation_id,
        count_bucket=observation.count_bucket,
        apparent_motion=observation.apparent_motion,
        position_uncertainty=observation.position_uncertainty,
        live_los_clear=observation.live_los_clear,
    )
