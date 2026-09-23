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
(`perception.clustering.cluster_candidates`) and emits one
presence-or-better-tier `Observation` per *cluster*, carrying a
`count_bucket`. That report must be allowed to fold onto its cluster's
existing contact (a cardinality *refine*/*hold*, or a *contradiction* if the
count genuinely disagrees) the same way any other percept does -- a blanket
veto would instead found a fresh contact every poll for any cluster whose
continuity happens to miss, strictly worse than before. What survives the
interim fix's reasoning, not its mechanism: a report carrying zero class
evidence must never make a confident 1:1 identity claim on its own --
Stage 2 honours that by never emitting a 1:1 per-object claim in the first
place, not by refusing to merge one.

**This gate is now the exception path, not the common case**
(`plans/contact-duplication-ambiguity-runaway/plan.md`): `ContactStore.
ingest`'s primary contact-identity mechanism, for any re-observation of a
previously-seen object on either perception channel, is object-permanence
correlation via `Percept.continues_observation_id` -- this module's gate is
only ever reached for a founding observation, or a reacquisition where that
correlation didn't resolve or has expired (`belief.decay.
object_id_continuity_valid`). Nothing in this module's own formulas
changed for that fix; only how often they get called did.

**Spatial gate -- isotropic, quantisation-derived** (reverted 2026-09-18 by
"Stage 3b-i rev.2" of `plans/group-contact-model/plan.md`, §3 -- see below
for why). The percept's implied position is `geometry.
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

**Why this gate is isotropic and quantisation-derived again, not the
anisotropic acuity-derived ellipse Stage 3b-i built.** Stage 3b-i's Decision
7 attached this gate's shape to `perception.clustering`'s own cluster
ellipse on the premise that leaving the gate isotropic would reopen the
Stage 3a dead zone -- that premise does not hold. Stage 3a closes the dead
zone with a same-source/same-poll candidate exclusion in `ContactStore.
ingest` (see that module's docstring), which is **radius-independent**: two
`Observation`s from one source in one poll can never resolve to the same
contact, whatever this gate's width. Once that stopped being the gate's job,
sharing a formula with clustering was revealed as the real defect, not the
fix: **the cluster predicate and this gate answer different questions about
different things.** The cluster predicate asks whether Petrovich can tell
two *live* candidates apart, in one instant, from one observer position --
its correct magnitude is optical resolving power, about one target width.
This gate asks whether a quantised *report* plausibly refers to a
remembered thing -- its correct magnitude is the channel's own reporting
vocabulary (the 30 deg clock bucket, the `OP_D*` range bucket) plus elapsed
motion, not optical acuity. Budgeting a quantised report against an acuity
figure was a category error: it shrank this gate's cross-range budget
~100x (clock-bucket-derived, ~300-650 m at typical ranges, down to
acuity-derived, ~1-7 m) while bearing-bucket requantisation jitter stayed
exactly what it always was (up to a full clock bucket, unchanged by the
representation), producing a ~700:1 jitter-to-budget mismatch at every
range and the duplicate-contact regression `test_contacts.
test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` was
`xfail`ed for. Reverting this gate to its pre-Stage-3b-i, quantisation-
derived form fixes that regression directly, by budgeting the thing that is
actually jittering -- see that test's own (now-passing) assertion.

`elapsed_s` is the time since *that contact's* last observation (not the
percept's own age), so a contact that has not been seen in a while gets a
wider, more forgiving gate -- it could plausibly have moved further. Distance
is 2D (x/z only): both channels report ground contacts and neither carries a
perceived-altitude field precise enough to gate on independently of the
horizontal position it was derived alongside.

`uncertainty_radius_m` is source-derived, not a single tuned constant:

- **Naked-eye** (`perception.naked_eye_source.SOURCE_NAKED_EYE_VISUAL_
  FILTERED`): `_naked_eye_uncertainty_m`, derived from that channel's own
  output quantisation (cross-range error ~= `range_m * sin(half the 30 deg
  clock bucket)`, down-range error = the width of the `OP_D*` range bucket,
  combined with `math.hypot`). This function and the range-bucket table it
  depends on live here, in `belief/` -- their pre-Stage-3b-i home -- since
  `perception.clustering` no longer has any use for a reporting
  quantisation of its own (see that module's docstring).
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

#: The width of naked-eye's own clock-position reporting bucket. Moved back
#: here from `perception.clustering` by Stage 3b-i rev.2 (see module
#: docstring) -- this is a reporting-quantisation figure, not a clustering
#: one. **Public as of Stage 3b of `plans/binocular-optic/plan.md`**: a
#: binocular look's own sweep width is half this figure, for the same
#: reason the spatial gate's bearing-uncertainty term is -- both are
#: honest derivations from the one fact "the clock bucket is 30 deg wide",
#: not two independently-tuned numbers that happen to agree
#: (`plans/binocular-optic/stage3b.md` D1).
CLOCK_BUCKET_DEG: Final[float] = 30.0
_HALF_CLOCK_BUCKET_RAD: Final[float] = math.radians(CLOCK_BUCKET_DEG / 2.0)

#: The 24 ED range-bucket upper bounds -- moved back here from `perception.
#: clustering` by Stage 3b-i rev.2 (originally copied from `perception.
#: naked_eye_source._RANGE_BUCKETS_M` -- kept as an independent literal
#: copy here rather than importing that module, to avoid this module
#: depending on `naked_eye_source`).
_RANGE_BUCKETS_M: Final[tuple[tuple[str, float], ...]] = (
    ("OP_D100M", 100.0),
    ("OP_D200M", 200.0),
    ("OP_D300M", 300.0),
    ("OP_D400M", 400.0),
    ("OP_D500M", 500.0),
    ("OP_D600M", 600.0),
    ("OP_D700M", 700.0),
    ("OP_D800M", 800.0),
    ("OP_D900M", 900.0),
    ("OP_D1000M", 1000.0),
    ("OP_D1_1p5k", 1500.0),
    ("OP_D1p5_2k", 2000.0),
    ("OP_D2_2p5k", 2500.0),
    ("OP_D2p5_3k", 3000.0),
    ("OP_D3_3p5k", 3500.0),
    ("OP_D3p5_4k", 4000.0),
    ("OP_D4_4p5k", 4500.0),
    ("OP_D4p5_5k", 5000.0),
    ("OP_D5_6k", 6000.0),
    ("OP_D6_7k", 7000.0),
    ("OP_D7_8k", 8000.0),
    ("OP_D8_9k", 9000.0),
    ("OP_D9_10k", 10000.0),
    ("OP_D10k", math.inf),
)


def _build_bucket_widths_m() -> tuple[float, ...]:
    """Precompute each `_RANGE_BUCKETS_M` bucket's width. The last bucket is
    open-ended (`math.inf` upper bound) and has no true width -- falls back
    to the previous bucket's width rather than `inf`, which would make the
    gate radius infinite for anything in the last bucket."""
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
    """The naked-eye channel's own honest position-uncertainty radius at
    `range_m`, combining cross-range and down-range error via `math.hypot`
    -- this gate's private figure again as of Stage 3b-i rev.2 (module
    docstring): no longer shared with `perception.clustering`, which now
    tests true angular separability instead of a reporting quantisation."""
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
