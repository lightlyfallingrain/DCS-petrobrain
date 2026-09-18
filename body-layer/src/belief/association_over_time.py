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
`uncertainty_radius_m` as the cluster radius -- see that module's
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

**Spatial gate.** The percept's implied position is `geometry.
project_from_bearing_range(observer, percept.bearing_deg, percept.range_m)`,
using the percept's own `ownship_at_observation` as the observer -- flat, no
terrain, per that function's own documented limitation. A candidate contact
passes the spatial gate when this implied position is within `gate_radius_m`
of the contact's last-known perceived position:

    gate_radius_m = uncertainty_radius_m(percept)
        + contact.last_position_uncertainty_m
        + GATE_GROWTH_RATE_MPS * elapsed_s

Both sides' uncertainty are summed -- `contact.last_position` is itself only
known to within *its own* founding/most-recent percept's uncertainty, not
exactly, so gating on the incoming percept's uncertainty alone silently
assumes the stored position is exact. It is not: naked-eye's bucket
quantisation in particular re-derives a fresh (bearing, range) pair from
scratch every poll (the buckets are anchored to the *current* heading -- see
`naked_eye_source._quantise_bearing`), so two consecutive, genuinely
identical real positions can legitimately quantise to different buckets and
imply positions up to roughly a full bucket-width apart, not just the
half-bucket-width `uncertainty_radius_m` models for a single reading. Only
budgeting the incoming side under-sizes the gate by up to 2x for exactly
this case -- confirmed live 2026-09-09: a single missed match from this
under-sizing spawns a duplicate contact, and because that duplicate itself
then counts as a second candidate for every subsequent percept near the same
real object, the two-or-more-candidates ambiguity rule above turns one
missed match into a permanent one-new-contact-per-poll runaway for the rest
of the contact's session (see `plans/classification-refinement/debug.md`).
Summing both sides' uncertainty is the minimal correction: it restores the
gate to the symmetric, standard-radar-fusion shape (both estimates carry
error, not just the newer one) without touching the ambiguity policy itself.

`elapsed_s` is the time since *that contact's* last observation (not the
percept's own age), so a contact that has not been seen in a while gets a
wider, more forgiving gate -- it could plausibly have moved further. Distance
is 2D (x/z only): both channels report ground contacts and neither carries a
perceived-altitude field precise enough to gate on independently of the
horizontal position it was derived alongside.

`uncertainty_radius_m` is source-derived, not a single tuned constant:

- **Naked-eye** (`perception.naked_eye_source.SOURCE_NAKED_EYE_VISUAL_
  FILTERED`): `perception.clustering.naked_eye_cluster_radius_m`, derived
  from that channel's own output quantisation (cross-range error ~=
  `range_m * sin(half the 30 deg clock bucket)`, down-range error = the
  width of the `OP_D*` range bucket, combined with `math.hypot`). **Moved
  to `perception/clustering.py`, not duplicated** (`plans/
  group-contact-model/plan.md` Stage 2): that module's own cluster radius
  and this gate's per-percept uncertainty are the same number by
  construction, so there is exactly one implementation -- see that
  module's docstring for the full derivation and the import-direction
  reasoning (`perception/` may not import `belief/`, so the shared
  function lives on the `perception/` side and this module imports it,
  same direction as this module's existing `naked_eye_source` imports).
- **Everything else** (the scope/hybrid channel): a single fixed constant,
  `SCOPE_UNCERTAINTY_M`. This channel does not quantise its geometry the same
  way (see `hybrid_source.py`), so there is no bucket width to derive an
  honest figure from. Per the plan: "use a reasonable fixed uncertainty and
  say so plainly in a comment -- don't overthink it, this gets revisited."
  This is exactly that placeholder, not a calibrated value.

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

import math
from typing import TYPE_CHECKING, Final

from belief.classification import class_compatibility
from belief.percept import Percept
from perception.clustering import naked_eye_cluster_radius_m
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


def uncertainty_radius_m(percept: Percept) -> float:
    """Perceived-position uncertainty for `percept`, source-derived. See
    module docstring."""
    if percept.source == SOURCE_NAKED_EYE_VISUAL_FILTERED:
        return naked_eye_cluster_radius_m(percept.range_m)
    return SCOPE_UNCERTAINTY_M


def implied_position(percept: Percept) -> GeoPosition:
    """The ground position `percept`'s bearing/range implies, from the
    observer position it was actually observed from."""
    observer = GeoPosition(
        x=percept.ownship_at_observation.x,
        z=percept.ownship_at_observation.z,
        alt_m=percept.ownship_at_observation.alt_m,
    )
    return project_from_bearing_range(observer, percept.bearing_deg, percept.range_m)


def spatial_gate_radius_m(percept: Percept, contact: Contact, now_sim: float) -> float:
    """The spatial gate radius for `percept` against `contact` at `now_sim`.
    See module docstring's formula -- both the incoming percept's own
    uncertainty and the contact's stored `last_position_uncertainty_m` are
    budgeted, not just the former."""
    elapsed_s = max(0.0, now_sim - contact.last_seen_sim)
    return (
        uncertainty_radius_m(percept)
        + contact.last_position_uncertainty_m
        + GATE_GROWTH_RATE_MPS * elapsed_s
    )


def passes_gate(percept: Percept, contact: Contact, now_sim: float) -> bool:
    """Whether `percept` may be merged into `contact` -- the spatial gate and
    the class-compatibility gate must both pass. See module docstring."""
    if class_compatibility(percept.classification_raw, contact.last_class_raw) == (
        "incompatible"
    ):
        return False

    percept_position = implied_position(percept)
    dx = percept_position.x - contact.last_position.x
    dz = percept_position.z - contact.last_position.z
    distance_m = math.hypot(dx, dz)
    return distance_m <= spatial_gate_radius_m(percept, contact, now_sim)
