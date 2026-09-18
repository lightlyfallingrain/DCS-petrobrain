"""Percept -> contact gating -- `plans/pb2-contact-memory/plan.md` Stage 1.

Deliberately named differently from `perception.association` (detection <->
world-object resolution, *within one poll*, against `LoGetWorldObjects`
ground truth). This module resolves a `belief.percept.Percept` against
*existing contacts*, across time, using only what was perceived -- never a
truth field. Do not import between the two modules; they answer different
questions and neither should stand in for the other.

Gate = spatial (hard) **and** class-not-incompatible (hard) **and**
not-presence-tier (hard, see "Presence-tier veto" below). All three must
pass for a percept to be a *candidate* merge target; the caller
(`belief.contacts.ContactStore.ingest`) then applies the plan's Stage 1
decision rule: exactly one candidate passing every gate -> merge; zero ->
new contact; **two or more -> new contact** (ambiguity must produce a
visible duplicate, never a guessed merge -- no best-match/highest-score
tiebreak exists in this module, by design).

**Presence-tier veto** (fix for the 2026-09-17/18 false-merge defect,
`plans/contact-merge-undercount/debug.md`): a percept at `belief.
classification.SpecificityLevel.PRESENCE` (naked-eye's `lowres` tier,
`classification_level == 1`) never passes this gate -- it always founds a
new contact (subject to the usual object-permanence shortcut in `belief.
contacts.ContactStore._resolve_continuity`, which is unconditional on tier
and still applies once a contact exists to correlate back onto). This is
not a spatial-radius change and does not touch `uncertainty_radius_m`'s
formulas or BL-2.6's symmetric-budgeting fix -- both stay exactly as
tuned. The reason is the class-compatibility gate's own documented
"`unknown` means neutral, never blocks a merge" posture: that posture is
safe for the scope channel's rare unresolvable free text (`"Slava
cruiser"`), but naked-eye's `lowres` tier is *systematically* class-blind
by construction (`classification_raw` is always `PRESENCE_CLASS`
/`object_model.DEFAULT_OP_CLASS`, which `_op_class_of` always resolves to
`None` -- see `belief.classification`'s module docstring on
`PRESENCE_CLASS`). Letting a percept that structurally carries zero class
evidence merge into an existing contact purely on the strength of an
honestly-coarse spatial gate is what let two genuinely different real
objects (a truck and, 400 m away, an infantryman) collapse into one
contact at first sighting -- confirmed live with a twelve-object
calibration cluster collapsing into roughly five contacts the same way.
Declining to merge a presence-tier percept costs only the rare case where
the *same* real object is reacquired via the gate (not continuity) while
still at `lowres` tier after `belief.decay.OBJECT_ID_MEMORY_S` has
expired -- an accepted, documented degradation (an extra duplicate
contact, never a bad merge), the same trade the class-compatibility gate's
own `unknown` posture already accepts elsewhere in this module.

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
  FILTERED`): derived from that channel's own output quantisation, reusing
  its real bucket constants rather than inventing new numbers (per the plan).
  Cross-range error ~= `range_m * sin(half the 30 deg clock bucket)` (the
  observation's bearing could be anywhere within +/-15 deg of the reported
  clock position); down-range error = the width of the `OP_D*` range bucket
  the observation fell into (the observation's true range could be anywhere
  within that bucket). The two are combined with `math.hypot` -- a
  conservative circular radius over two roughly-orthogonal error axes,
  smaller than summing them and larger than taking either alone.
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

from belief.classification import SpecificityLevel, class_compatibility
from belief.percept import Percept
from perception.geometry import GeoPosition, project_from_bearing_range
from perception.naked_eye_source import _CLOCK_BUCKET_DEG, _RANGE_BUCKETS_M
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

#: Half of naked-eye's 30 deg clock bucket -- the bearing could be anywhere
#: within +/- this many degrees of the reported clock position.
_HALF_CLOCK_BUCKET_RAD: Final[float] = math.radians(_CLOCK_BUCKET_DEG / 2.0)


def _build_bucket_widths_m() -> tuple[float, ...]:
    """Precompute each `_RANGE_BUCKETS_M` bucket's width (upper bound minus
    the previous bucket's upper bound; the first bucket's implicit lower
    bound is 0). The last bucket (`OP_D10k`, upper bound `math.inf`) is given
    the second-to-last bucket's width instead of an infinite one -- a
    documented fallback, not a real derivation, since an open-ended bucket
    has no true width."""
    widths: list[float] = []
    previous_bound_m = 0.0
    for _name, upper_bound_m in _RANGE_BUCKETS_M:
        if math.isinf(upper_bound_m):
            widths.append(widths[-1] if widths else previous_bound_m)
        else:
            widths.append(upper_bound_m - previous_bound_m)
        previous_bound_m = upper_bound_m
    return tuple(widths)


_RANGE_BUCKET_WIDTHS_M: Final[tuple[float, ...]] = _build_bucket_widths_m()


def _range_bucket_width_m(range_m: float) -> float:
    """Width of the `OP_D*` bucket `range_m` falls into."""
    for index, (_name, upper_bound_m) in enumerate(_RANGE_BUCKETS_M):
        if range_m <= upper_bound_m:
            return _RANGE_BUCKET_WIDTHS_M[index]
    return _RANGE_BUCKET_WIDTHS_M[-1]  # unreachable: last bound is inf


def _naked_eye_uncertainty_m(range_m: float) -> float:
    """Cross-range + down-range uncertainty implied by naked-eye's own
    bearing/range quantisation, combined via `math.hypot`. See module
    docstring."""
    cross_range_m = range_m * math.sin(_HALF_CLOCK_BUCKET_RAD)
    down_range_m = _range_bucket_width_m(range_m)
    return math.hypot(cross_range_m, down_range_m)


def uncertainty_radius_m(percept: Percept) -> float:
    """Perceived-position uncertainty for `percept`, source-derived. See
    module docstring."""
    if percept.source == SOURCE_NAKED_EYE_VISUAL_FILTERED:
        return _naked_eye_uncertainty_m(percept.range_m)
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
    """Whether `percept` may be merged into `contact` -- the spatial gate,
    the class-compatibility gate, and the presence-tier veto must all pass.
    See module docstring."""
    if percept.classification_level <= SpecificityLevel.PRESENCE:
        return False

    if class_compatibility(percept.classification_raw, contact.last_class_raw) == (
        "incompatible"
    ):
        return False

    percept_position = implied_position(percept)
    dx = percept_position.x - contact.last_position.x
    dz = percept_position.z - contact.last_position.z
    distance_m = math.hypot(dx, dz)
    return distance_m <= spatial_gate_radius_m(percept, contact, now_sim)
