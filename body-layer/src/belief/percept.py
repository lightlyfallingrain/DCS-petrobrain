"""`Percept` -- the mechanical enforcement of "belief may only see what was
perceived" (`plans/pb2-contact-memory/plan.md`'s Interface confirmation gap
3, and the Decision section's identity invariant).

`perception.source.Observation` carries `derived_world_position` (DCS
ground truth x/z) alongside the perceived bearing/range on both concrete
tiers -- convenient for `body.py`'s text output and for future
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

**How to add a new signal from the perception side, and why not the
obvious way.** When `BL-B72` needed `Contact.is_burning`, the first
implementation let `Observation.provenance` -- a free-form `str` -- cross
into `Percept` wholesale, and removed `"provenance"` from
`test_percept.py`'s forbidden set to match. Reviewer rejected it: every
value that field holds *today* is channel self-description, but its
**type** is unconstrained, `perception.hybrid_source` already puts internal
pipeline detail in it, and once a field is known to cross freely nothing
stops a future producer putting something truth-derived there. The
discipline would have become a comment in a test file rather than a guard.

**So: add a closed, purpose-named field, populated through an explicit
mapping** -- `emitter_kind` and `_EMITTER_KIND_BY_PROVENANCE` below are the
pattern. An unregistered producer maps to `None` rather than crossing, so
widening the boundary takes a deliberate edit here instead of happening by
default somewhere else. `BL-B73` followed the same pattern for
`targets_ownship`/`_TARGETS_OWNSHIP_PROVENANCE` below, rather than
widening `emitter_kind` itself into something richer than "which kind";
`BL-B74` is expected to do the same for whatever signal its frozen-
position seam needs. Follow the mapping rather than widening a free-form
field, and keep `test_percept.py`'s forbidden set intact.
"""

from __future__ import annotations

from dataclasses import dataclass

from perception.emitters import EmitterKind
from perception.naked_eye_source import (
    PROVENANCE_EMITTER_BURNING,
    PROVENANCE_EMITTER_FIRING,
    PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP,
    PROVENANCE_EMITTER_FIRING_VISIBLE,
)
from perception.source import (
    Observation,
    OwnshipState,
    PositionUncertainty,
    RelativeDirection,
)

#: `plans/emitter-visibility/plan.md` review (Stage A, 2026-10-15) --
#: `percept_of` must not let `Observation.provenance` (a free-form `str`,
#: see that field's own docstring) cross into `Percept` wholesale: nothing
#: would then stop a future producer folding something truth-derived into
#: it, with `test_percept.py::test_percept_has_no_truth_carrying_field`'s
#: forbidden-set check never seeing it happen. Instead `Percept` exposes
#: only a *closed*, purpose-built signal -- `emitter_kind`, one of
#: `perception.emitters.EmitterKind`'s values or `None` -- derived from
#: `observation.provenance` through this mapping. A `provenance` value not
#: listed here (including every non-emitter value) maps to `None` via
#: `dict.get`, so adding a new `PROVENANCE_*` constant elsewhere can never
#: silently start producing a new `Percept.emitter_kind` value; it has to
#: be added here first. Only `BURNING` exists today (`BL-B73`/`BL-B74` add
#: `FIRING`/`LAUNCH_SMOKE`, per `perception.emitters.EmitterKind`'s own
#: docstring).
_EMITTER_KIND_BY_PROVENANCE: dict[str, str] = {
    PROVENANCE_EMITTER_BURNING: EmitterKind.BURNING.value,
    # `plans/emitter-visibility/plan.md` Stage B (`BL-B73`), extended by
    # `plans/taking-fire-visible-shooter/debug.md`'s second half -- all
    # three of `naked_eye_source.py`'s `FIRING` provenance values map to
    # the same `EmitterKind`, since `Percept.emitter_kind` only ever needs
    # to answer "which kind", not "aimed at us" or "already visible
    # unaided" -- those two further bits cross through their own closed
    # mappings, `_TARGETS_OWNSHIP_PROVENANCE`/`_VISIBLE_FIRING_PROVENANCE`
    # below, for the same reason this one exists: a free-form string must
    # not cross this boundary on its own say-so.
    PROVENANCE_EMITTER_FIRING: EmitterKind.FIRING.value,
    PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP: EmitterKind.FIRING.value,
    PROVENANCE_EMITTER_FIRING_VISIBLE: EmitterKind.FIRING.value,
}

#: `plans/emitter-visibility/plan.md` Stage B (`BL-B73`) -- the one
#: `PROVENANCE_*` value whose presence means "and the event named ownship
#: as its target", closed the same way `_EMITTER_KIND_BY_PROVENANCE` is:
#: `Percept.targets_ownship` is `observation.provenance in` this set, never
#: a passthrough of `Observation.provenance` itself. A `frozenset`, not a
#: `dict`, because there is only one bit to carry (unlike `EmitterKind`'s
#: several values) -- membership is the whole answer.
_TARGETS_OWNSHIP_PROVENANCE: frozenset[str] = frozenset(
    {PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP}
)

#: `plans/taking-fire-visible-shooter/debug.md` (second half, F6 follow-up
#: "visible unit firing at others") -- `_TARGETS_OWNSHIP_PROVENANCE`'s
#: direct sibling: the one `PROVENANCE_*` value whose presence means "this
#: is a firing report, and the unit was admitted without the emitter
#: bypass, so its classification is real and should be spoken" rather than
#: the bypass-needed, presence-only "something firing... far" case. Same
#: `frozenset`-membership shape, same reason: `Percept.firing_visible`
#: must not be a passthrough of the free-form `provenance` string itself.
_VISIBLE_FIRING_PROVENANCE: frozenset[str] = frozenset(
    {PROVENANCE_EMITTER_FIRING_VISIBLE}
)


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
    re-derives it.

    `relative_direction` carries `Observation.relative_direction` through
    unchanged (`plans/attack-run/plan.md` Decision 16) -- a genuine
    ownship-relative *perception*, bounded by the look (see that field's
    own docstring on `perception.source.RelativeDirection`), not a map
    read. **Its only sanctioned reader outside this module is `belief.
    attack_run`** -- a grep test (`test_attack_run.py`) fences every other
    file under `belief/` from even mentioning the name, mirroring
    `belief.contacts`' own `derived_world_position` fence. This is a
    narrower boundary than every other field on this class: those are
    perceived metadata with no path back to a world position; this one
    carries true relative geometry that, combined with ownship's own
    exact telemetry, is convertible to one -- see Decision 16 item 4 for
    the full argument.

    `aim_unit_direction` carries `Observation.aim_unit_direction` through
    unchanged (`plans/bl-b67-atgm-run/plan.md` Stage 2, "Single unit,
    never a cluster") -- the *one cluster member* direction, not the
    centroid `relative_direction` carries, set only for a sight-tier
    look. **Its only sanctioned reader outside this module is `belief.
    attack_run`**, the exact same fence `relative_direction` itself is
    under (`test_attack_run.py`): this is a second field on the same
    narrow boundary, not a second exception.

    `emitter_kind` (`plans/emitter-visibility/plan.md`, `BL-B72` Stage A,
    narrowed per that plan's review) is which `perception.emitters.
    EmitterKind` value (if any) made `Observation.provenance` an emitter
    provenance this look -- `percept_of` derives it through
    `_EMITTER_KIND_BY_PROVENANCE` rather than letting the free-form
    `provenance` string itself cross this boundary, so it is a *closed*
    signal, not a passthrough: `"provenance"` stays in `test_percept.py`'s
    forbidden-field set, and this field is the one and only sanctioned
    channel for the kind of thing `provenance` carries to reach `belief/`.
    `belief.contacts.Contact.record` reads this to decide `is_burning`/
    `is_firing` (`belief.events.burning_event_kind`/`firing_event_kind`'s
    input); nothing else in `belief/` needs it yet. `None` is the default
    -- every pre-existing construction site (test fixtures included)
    keeps compiling, and it is also what every non-emitter `provenance`
    value maps to.

    `targets_ownship` (`plans/emitter-visibility/plan.md` Stage B,
    `BL-B73`) is the same closed-mapping treatment one level deeper --
    `_TARGETS_OWNSHIP_PROVENANCE`'s own docstring -- and is only ever
    meaningful alongside `emitter_kind == EmitterKind.FIRING.value`;
    `False` is the default and is also what every other `emitter_kind`
    (including `BURNING`, which carries no notion of a target at all)
    resolves to.

    `firing_visible` (`plans/taking-fire-visible-shooter/debug.md`, second
    half, F6 follow-up) is `targets_ownship`'s sibling, through its own
    closed mapping (`_VISIBLE_FIRING_PROVENANCE`): `True` means this firing
    report was admitted *without* the emitter bypass, so the classification
    it carries is real (whatever tier the ordinary admission earned) and
    should be spoken, rather than the bypass-needed case's presence-only
    "something firing... far". Mutually exclusive with `targets_ownship` by
    construction (`naked_eye_source._build_observation`'s fold resolves
    `targets_ownship` first), but not enforced as an invariant here --
    both default to `False`, same as every other `emitter_kind`."""

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
    relative_direction: RelativeDirection | None = None
    aim_unit_direction: RelativeDirection | None = None
    emitter_kind: str | None = None
    targets_ownship: bool = False
    firing_visible: bool = False


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
        relative_direction=observation.relative_direction,
        aim_unit_direction=observation.aim_unit_direction,
        emitter_kind=_EMITTER_KIND_BY_PROVENANCE.get(observation.provenance),
        targets_ownship=observation.provenance in _TARGETS_OWNSHIP_PROVENANCE,
        firing_visible=observation.provenance in _VISIBLE_FIRING_PROVENANCE,
    )
