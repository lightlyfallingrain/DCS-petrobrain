"""Percept -> contact gating -- `plans/pb2-contact-memory/plan.md` Stage 1.

Deliberately named differently from `perception.association` (detection <->
world-object resolution, *within one poll*, against `LoGetWorldObjects`
ground truth). This module resolves a `belief.percept.Percept` against
*existing contacts*, across time, using only what was perceived -- never a
truth field. Do not import between the two modules; they answer different
questions and neither should stand in for the other.

Gate = spatial (hard) **and** class-not-incompatible (hard). Both must pass
for a percept to be a *candidate* merge target; the caller (`belief.
contacts.ContactStore.ingest`) then applies the plan's Stage 1 decision
rule: exactly one candidate passing every gate -> merge; zero -> new
contact; **two or more -> new contact** (ambiguity must produce a visible
duplicate, never a guessed merge -- no best-match/highest-score tiebreak
exists in this module, by design).

**The presence-tier veto that used to live here is gone**
(`plans/group-contact-model/plan.md` Stage 2). It was an interim fix
(`plans/contact-merge-undercount/debug.md`, landed as its own branch) for
the false-merge defect a presence-tier percept's structural class-blindness
caused: with naked-eye still emitting one `Observation` per object, letting
a zero-class-evidence percept merge on spatial proximity alone let
genuinely different real objects collapse into one contact. That defect's
actual cause was never this gate -- it was `perception.naked_eye_source`
reporting per-object at a range where the channel cannot resolve
per-object identity at all. Stage 2 fixes the cause: `naked_eye_source.py`
now clusters at its own honest resolution limit
(`perception.clustering.cluster_candidates`, using this module's own
`uncertainty_radii_m` as the cluster ellipse -- see that module's
docstring) and emits one presence-or-better-tier `Observation` per
*cluster*, carrying a `count_bucket`. That report must be allowed to fold
onto its cluster's existing contact (a cardinality *refine*/*hold*, or a
*contradiction* if the count genuinely disagrees) the same way any other
percept does -- a blanket veto would instead found a fresh contact every
poll for any cluster whose continuity happens to miss, strictly worse than
before. What survives the interim fix's reasoning, not its mechanism: a
report carrying zero class evidence must never make a confident 1:1
identity claim on its own -- Stage 2 honours that by never emitting a
1:1 per-object claim in the first place, not by refusing to merge one.

**This gate is now the exception path, not the common case**
(`plans/contact-duplication-ambiguity-runaway/plan.md`): `ContactStore.
ingest`'s primary contact-identity mechanism, for any re-observation of a
previously-seen object on either perception channel, is object-permanence
correlation via `Percept.continues_observation_id` -- this module's gate is
only ever reached for a founding observation, or a reacquisition where that
correlation didn't resolve or has expired (`belief.decay.
object_id_continuity_valid`). Nothing in this module's own formulas
changed for that fix; only how often they get called did.

**Spatial gate -- anisotropic since Stage 3b-i** (`plans/
group-contact-model/plan.md` Decision 7). The percept's implied position is
`geometry.project_from_bearing_range(observer, percept.bearing_deg,
percept.range_m)`, using the percept's own `ownship_at_observation` as the
observer -- flat, no terrain, per that function's own documented limitation.
A candidate contact passes the spatial gate when the vector from the
contact's last-known perceived position to this implied position,
decomposed into cross-range/down-range components against *that same
observer's* line of sight (`perception.clustering.los_components_m`), falls
inside the ellipse whose per-axis radius is:

    cross_budget_m = uncertainty_radii_m(percept).cross_range_m
        + contact.last_position_uncertainty_m
        + GATE_GROWTH_RATE_MPS * elapsed_s
    down_budget_m = uncertainty_radii_m(percept).down_range_m
        + contact.last_position_uncertainty_m
        + GATE_GROWTH_RATE_MPS * elapsed_s

This is the gate's own instance of the plan's central by-construction
identity: `perception.clustering.cluster_candidates` and this gate test the
*same* ellipse, because a cluster radius that is anisotropic while the gate
that re-tests a split child against its parent stays circular reopens
exactly the dead zone Stage 3a closed (a circular gate's `sum >= max`
degenerately re-absorbs any split sitting near the ellipse's own boundary,
regardless of which axis the split happened on). `contact.last_position_
uncertainty_m` stays the scalar it always was (see `Contact`'s own
docstring) -- the observer position that produced it is not stored, so
there is no LOS frame recoverable for *that* reading's own ellipse. It is
applied to **both** axes of the current gate as a single conservative pad
(always the larger of that reading's own two axes, see `uncertainty_
radius_m` below), which only ever widens the gate relative to a
hypothetical narrower true value, never narrows it -- an approximation
accepted explicitly rather than adding a second stored field, per the
plan's "no new plumbing" finding (`Percept.ownship_at_observation` and
`OwnshipState` were already in scope at both call sites; nothing new is
threaded through).

For a scope-channel percept, whose own ellipse is a circle
(`cross_range_m == down_range_m == SCOPE_UNCERTAINTY_M`), this reduces
identically to the old isotropic test -- `cross_budget_m == down_budget_m`
makes the ellipse a circle again, and `(cross/r)**2 + (down/r)**2 <= 1` is
algebraically `hypot(cross, down) <= r`, which is exactly `distance_m <=
r` since cross/down are an orthonormal rotation of the raw (dx, dz) vector.
Every scope-channel gate test predates this stage and is unaffected by it.

The prior "both sides' uncertainty must be summed, not just the incoming
side's" fix (2026-09-09, `plans/classification-refinement/debug.md`) is
preserved exactly -- `contact.last_position_uncertainty_m` is still added
on top of the incoming percept's own budget on every axis; only the shape
of what "distance" and "radius" mean changed, not whether both sides pay
into it.

`elapsed_s` is the time since *that contact's* last observation (not the
percept's own age), so a contact that has not been seen in a while gets a
wider, more forgiving gate -- it could plausibly have moved further. Both
axes' growth term is isotropic (a contact could have moved in any
direction while unobserved, not preferentially along the old LOS).
Distance is 2D (x/z only): both channels report ground contacts and
neither carries a perceived-altitude field precise enough to gate on
independently of the horizontal position it was derived alongside.

`uncertainty_radii_m` is source-derived, not a single tuned constant:

- **Naked-eye** (`perception.naked_eye_source.SOURCE_NAKED_EYE_VISUAL_
  FILTERED`): `perception.clustering.naked_eye_ellipse_radii_m`, derived
  from that channel's own honest resolving power (cross-range: apparent-
  angle acuity; down-range: the `OP_D*` range bucket's width, kept as a
  depth-discrimination stand-in -- see that module's docstring for the full
  Stage 3b-i derivation, including why the two axes are no longer combined
  with `math.hypot`). **Moved to `perception/clustering.py`, not
  duplicated** (`plans/group-contact-model/plan.md` Stage 2, reworked
  Stage 3b-i): that module's own cluster ellipse and this gate's
  per-percept uncertainty are the same numbers by construction, so there
  is exactly one implementation -- see that module's docstring for the
  full derivation and the import-direction reasoning (`perception/` may
  not import `belief/`, so the shared function lives on the `perception/`
  side and this module imports it, same direction as this module's
  existing `naked_eye_source` imports).
- **Everything else** (the scope/hybrid channel): a single fixed constant,
  `SCOPE_UNCERTAINTY_M`, on both axes (an isotropic circle -- see above).
  This channel does not quantise its geometry the same way (see
  `hybrid_source.py`), so there is no bucket structure to derive an honest
  anisotropic figure from. Per the plan: "use a reasonable fixed
  uncertainty and say so plainly in a comment -- don't overthink it, this
  gets revisited." This is exactly that placeholder, not a calibrated
  value.

`uncertainty_radius_m` (singular, scalar) still exists as a conservative
legacy figure -- the larger of `uncertainty_radii_m`'s two axes -- for
`Contact.last_position_uncertainty_m`'s own storage (see above on why that
field stays scalar) and any other caller that only needs one honest,
never-under-sized number rather than the full ellipse.

**Class-compatibility gate.** Three-valued (`compatible` / `unknown` /
`incompatible`) because the two channels speak different vocabularies:
naked-eye's `classification_raw` is already one of `object_model.py`'s
`OP_*` bucket strings; the scope/hybrid channel's is free descriptive text
(`"Ural truck"`, `"SA-3 launcher"`). `_op_class_of` resolves either shape to
an `OP_*` bucket or `None`:

- A `classification_raw` that already looks like a bucket (starts with
  `"OP_"` and isn't the fallback bucket) is used as-is -- this is exactly
  what naked-eye emits.
- Otherwise, it is run through `object_model.profile_for` the same way a raw
  `object_type` string would be -- that lookup is substring-based, so it
  often also matches free descriptive text (`"Ural truck"` contains `"ural"`
  -> `OP_TRUCK`). If that lookup falls back to `object_model.DEFAULT_OP_
  CLASS` (ED's own "unclassified" bucket), the class is treated as unknown,
  not as a real "unclassified" class value -- `DEFAULT_OP_CLASS` means "no
  match found," which is exactly what "unknown" means here.

`None` on either side (or both) means `unknown`: neither confirms nor blocks
a merge. Two resolved, differing classes mean `incompatible` and block the
merge outright. This is deliberately weak on the scope channel (`"Slava
cruiser"` will not resolve through `object_model`'s keyword table) -- the
plan accepts this as a known risk (under-merging into duplicate contacts,
never a bad merge) rather than building a second keyword table here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from belief.classification import class_compatibility
from belief.percept import Percept
from perception.clustering import (
    EllipseRadii,
    los_components_m,
    naked_eye_ellipse_radii_m,
    within_ellipse,
)
from perception.geometry import GeoPosition, project_from_bearing_range
from perception.source import SOURCE_NAKED_EYE_VISUAL_FILTERED

if TYPE_CHECKING:
    from belief.contacts import Contact

#: Placeholder fixed uncertainty for the scope/hybrid channel -- see module
#: docstring. Not range-derived: this channel has no bucket structure to
#: derive an honest figure from, and the plan explicitly says not to
#: overthink this now.
SCOPE_UNCERTAINTY_M: Final[float] = 300.0

#: How fast a contact could plausibly have moved since it was last observed,
#: for the spatial gate's elapsed-time growth term -- a generic ground-vehicle
#: order-of-magnitude figure (72 km/h), not derived from any specific unit's
#: real top speed. Placeholder, like `SCOPE_UNCERTAINTY_M` -- revisit once
#: real sessions show whether contacts are gated too tightly or too loosely.
GATE_GROWTH_RATE_MPS: Final[float] = 20.0


def uncertainty_radii_m(percept: Percept) -> EllipseRadii:
    """Perceived-position uncertainty ellipse for `percept`, source-derived.
    See module docstring."""
    if percept.source == SOURCE_NAKED_EYE_VISUAL_FILTERED:
        return naked_eye_ellipse_radii_m(percept.range_m)
    return EllipseRadii(
        cross_range_m=SCOPE_UNCERTAINTY_M, down_range_m=SCOPE_UNCERTAINTY_M
    )


def uncertainty_radius_m(percept: Percept) -> float:
    """Conservative scalar uncertainty for `percept` -- the larger of its
    ellipse's two axes. See module docstring's note on why `Contact.
    last_position_uncertainty_m` stays scalar and why `max` (never
    under-sized) is the right reduction."""
    radii = uncertainty_radii_m(percept)
    return max(radii.cross_range_m, radii.down_range_m)


def implied_position(percept: Percept) -> GeoPosition:
    """The ground position `percept`'s bearing/range implies, from the
    observer position it was actually observed from."""
    observer = GeoPosition(
        x=percept.ownship_at_observation.x,
        z=percept.ownship_at_observation.z,
        alt_m=percept.ownship_at_observation.alt_m,
    )
    return project_from_bearing_range(observer, percept.bearing_deg, percept.range_m)


def passes_gate(percept: Percept, contact: Contact, now_sim: float) -> bool:
    """Whether `percept` may be merged into `contact` -- the spatial gate and
    the class-compatibility gate must both pass. See module docstring."""
    if class_compatibility(percept.classification_raw, contact.last_class_raw) == (
        "incompatible"
    ):
        return False

    percept_position = implied_position(percept)
    observer = percept.ownship_at_observation
    cross_range_m, down_range_m = los_components_m(
        observer.x,
        observer.z,
        contact.last_position.x,
        contact.last_position.z,
        percept_position.x,
        percept_position.z,
    )

    percept_radii = uncertainty_radii_m(percept)
    elapsed_s = max(0.0, now_sim - contact.last_seen_sim)
    growth_m = GATE_GROWTH_RATE_MPS * elapsed_s
    cross_budget_m = (
        percept_radii.cross_range_m + contact.last_position_uncertainty_m + growth_m
    )
    down_budget_m = (
        percept_radii.down_range_m + contact.last_position_uncertainty_m + growth_m
    )

    return within_ellipse(cross_range_m, down_range_m, cross_budget_m, down_budget_m)
