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

**Spatial gate -- a 2D covariance (Mahalanobis) test, as of
`plans/precise-position-belief/plan.md` Stage 3.** The percept's implied
position is `geometry.project_from_bearing_range(observer,
percept.bearing_deg, percept.range_m)`, using the percept's own
`ownship_at_observation` as the observer -- flat, no terrain, per that
function's own documented limitation. A candidate contact passes the
spatial gate when this implied position's offset from the contact's
last-known perceived position sits within `GATE_SIGMA_THRESHOLD` (3,
"generous", per the plan) sigma of the **sum** of both sides' own
covariance, using `belief.position_belief.Covariance2D`'s Mahalanobis
reduction:

    covariance = percept_covariance + contact_covariance.inflated(elapsed_s)
    passes iff covariance.mahalanobis_squared(dx, dz) <= GATE_SIGMA_THRESHOLD ** 2

This promotes the pre-Stage-3 scalar-radius formula (`uncertainty_radius_m(
percept) + contact.last_position_uncertainty_m + GATE_GROWTH_RATE_MPS *
elapsed_s`, tested against plain Euclidean distance) from a scalar to a full
2x2 covariance, budgeted symmetrically on both sides for the same reason the
scalar formula summed both radii: `contact.last_position` is itself only
known to within *its own* founding/most-recent percept's uncertainty, not
exactly, so gating on the incoming percept's uncertainty alone silently
assumes the stored position is exact. It is not -- a single missed match
from under-budgeting the stored side spawns a duplicate contact, and because
that duplicate itself then counts as a second candidate for every subsequent
percept near the same real object, the two-or-more-candidates ambiguity rule
above turns one missed match into a permanent one-new-contact-per-poll
runaway for the rest of the contact's session (confirmed live 2026-09-09,
see `plans/classification-refinement/debug.md` -- the scalar-era version of
exactly this failure mode).

`percept_covariance` is `belief.position_belief.covariance_from_uncertainty`
applied to `percept_position_uncertainty(percept)` (the declared value, or
an isotropic fallback for the rare percept missing one -- see that
function's own docstring) rotated onto world x/z at the percept's own true
`bearing_deg` -- the elongated look ellipse `plans/precise-position-belief/
plan.md`'s error model describes, oriented along that look's own line of
sight, not a scalar radius collapsing the anisotropy away. **`contact_
covariance` is `Contact.position.covariance`, the real fused covariance**
(`plans/precise-position-belief/plan.md` Stage 4 -- `belief.contacts.
Contact.record`/`from_percept` build and refine it via `belief.
position_belief.fold_position` on every merge), inflated for elapsed motion
the same way the scalar formula's `GATE_GROWTH_RATE_MPS * elapsed_s` term
did. Stage 3 (which landed first, as its own commit) read an isotropic
proxy here instead, built from the scalar `last_position_uncertainty_m`,
because `Contact` did not yet hold a real 2x2 covariance -- see this
module's own history below for why a shared-formula shortcut between two
different questions has bitten this gate before, which is also why that
upgrade was its own later, separate diff rather than bundled into Stage 3.

**Why this is not simply "the old scalar formula with squares"**: summing
covariances (variances add) is not the same arithmetic as summing radii
(a scalar sum), so a handful of `tests/test_contacts.py` fixtures whose
exact geometry was tuned against the old linear formula needed re-deriving
against the new one -- the *behaviour* under test (ambiguity still produces
a visible duplicate, a genuinely overlapping gate still does not runaway)
is unchanged, only the specific separations that exercise it.

**Why anisotropy is safe here, unlike Stage 3b-i's reverted attempt (see
below).** The reverted mistake was budgeting a *quantised report's* jitter
(up to a full clock bucket) against an *acuity*-derived radius (~1-7 m) --
two different error sources, a ~700:1 mismatch. Here, the covariance comes
from `perception.estimation`'s own declared error model for exactly the
number being gated (the percept's own perturbed bearing/range), and the
quantisation that used to jitter independently of that budget is deleted
(Stage 2 of this same plan) -- the thing being budgeted and the thing that
can jitter are, for the first time, the same model.

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

**This paragraph describes the gate as of Stage 3b-i rev.2 -- `plans/
precise-position-belief/plan.md` Stage 3 (above) is a later, distinct
reintroduction of anisotropy.** It is not a re-run of the Stage 3b-i
mistake: see "Why anisotropy is safe here" above for the precise
distinction (a shared *formula* with a different question's error source,
vs. this module's own declared error model applied to its own gated
number).

`elapsed_s` is the time since *that contact's* last observation (not the
percept's own age), so a contact that has not been seen in a while gets a
wider, more forgiving gate -- it could plausibly have moved further. Distance
is 2D (x/z only): both channels report ground contacts and neither carries a
perceived-altitude field precise enough to gate on independently of the
horizontal position it was derived alongside.

**`uncertainty_radius_m` is source-declared, not derived here at all, as of
`plans/precise-position-belief/plan.md` Stage 1.** Every percept carries its
own `position_uncertainty` (`perception.source.PositionUncertainty`), an
honest (cross-range, down-range) sigma pair each concrete source computes
from its own error model -- `perception.estimation.naked_eye_sigma_m` for
the naked-eye channel (range-fractional down-range error, a declared
bearing-sigma constant for cross-range), a fixed isotropic pair declared in
`hybrid_source.py` for the scope/hybrid channel. This module used to hold a
private, duplicated copy of naked-eye's reporting-quantisation bucket table
purely to re-derive this figure from a channel's *output* -- that
duplication (and the category error it invited, see the "why this gate is
isotropic" paragraph above) is gone: `uncertainty_radius_m` is now just
`hypot` of whatever the source already declared. See `_FALLBACK_
UNCERTAINTY_RADIUS_M`'s own docstring for the one remaining case (a percept
missing a declared uncertainty) this module still derives a number for
itself.

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
from belief.position_belief import Covariance2D, covariance_from_uncertainty
from perception.geometry import GeoPosition, project_from_bearing_range
from perception.source import PositionUncertainty

if TYPE_CHECKING:
    from belief.contacts import Contact

#: How many sigma (in the summed covariance's own shape) an incoming
#: percept's implied position may sit from a contact's last-known position
#: and still pass the gate -- `plans/precise-position-belief/plan.md` Stage
#: 3's "keep the threshold generous" instruction. Squared once here rather
#: than at every call site (`passes_gate` compares `mahalanobis_squared`
#: directly against `GATE_SIGMA_THRESHOLD ** 2`).
GATE_SIGMA_THRESHOLD: Final[float] = 3.0

#: Isotropic fallback radius for a percept somehow missing a declared
#: `position_uncertainty` (`plans/precise-position-belief/plan.md` Stage 1)
#: -- should not happen in production as of that plan, since both concrete
#: sources (`perception.naked_eye_source`, `perception.hybrid_source`)
#: declare one unconditionally. Kept as a defensive fallback, not a real
#: derivation, and set to the same value the scope/hybrid channel used to
#: declare directly here (`SCOPE_UNCERTAINTY_M`, now moved into that
#: source module).
_FALLBACK_UNCERTAINTY_RADIUS_M: Final[float] = 300.0


def uncertainty_radius_m(percept: Percept) -> float:
    """Perceived-position uncertainty for `percept`, as a scalar radius --
    `hypot` of `percept.position_uncertainty`'s declared (cross, down) sigma
    pair (`plans/precise-position-belief/plan.md` Stage 1: each source now
    declares its own honest error ellipse, rather than this module
    re-deriving one from a duplicated copy of a reporting-quantisation
    table). Falls back to `_FALLBACK_UNCERTAINTY_RADIUS_M` when a percept
    carries no declared uncertainty at all -- see that constant's own
    docstring."""
    if percept.position_uncertainty is not None:
        return math.hypot(
            percept.position_uncertainty.sigma_cross_m,
            percept.position_uncertainty.sigma_down_m,
        )
    return _FALLBACK_UNCERTAINTY_RADIUS_M


def implied_position(percept: Percept) -> GeoPosition:
    """The ground position `percept`'s bearing/range implies, from the
    observer position it was actually observed from."""
    observer = GeoPosition(
        x=percept.ownship_at_observation.x,
        z=percept.ownship_at_observation.z,
        alt_m=percept.ownship_at_observation.alt_m,
    )
    return project_from_bearing_range(observer, percept.bearing_deg, percept.range_m)


#: The isotropic-equivalent `PositionUncertainty` for
#: `_FALLBACK_UNCERTAINTY_RADIUS_M` -- `sigma_cross_m == sigma_down_m ==
#: radius / sqrt(2)`, chosen so `covariance_from_uncertainty` on this value
#: (at any bearing, since it is isotropic) has trace `radius ** 2`, i.e.
#: `PositionEstimate.radius_m()`-style `sqrt(trace) == radius`
#: (`hypot(sigma, sigma) == radius`). Declared once so `percept_position_
#: uncertainty` below needs no special-case branch of its own.
_FALLBACK_POSITION_UNCERTAINTY: Final = PositionUncertainty(
    sigma_cross_m=_FALLBACK_UNCERTAINTY_RADIUS_M / math.sqrt(2.0),
    sigma_down_m=_FALLBACK_UNCERTAINTY_RADIUS_M / math.sqrt(2.0),
)


def percept_position_uncertainty(percept: Percept) -> PositionUncertainty:
    """`percept.position_uncertainty` if declared, else the isotropic
    `_FALLBACK_POSITION_UNCERTAINTY` -- the single place both this module's
    own `_percept_covariance` (the gate) and `belief.contacts.Contact.
    record`/`from_percept` (the fusion, `plans/precise-position-belief/
    plan.md` Stage 4) resolve "what uncertainty does this percept declare,
    really" from, so the gate and the fused estimate can never silently
    disagree about a percept missing one."""
    if percept.position_uncertainty is not None:
        return percept.position_uncertainty
    return _FALLBACK_POSITION_UNCERTAINTY


def _percept_covariance(percept: Percept) -> Covariance2D:
    """The look's own elongated error ellipse, rotated onto world x/z at
    its own true `bearing_deg` -- via `percept_position_uncertainty` above,
    so a percept missing a declared uncertainty gets the same isotropic
    fallback the fused estimate would use for the identical look."""
    return covariance_from_uncertainty(
        percept_position_uncertainty(percept), percept.bearing_deg
    )


def _contact_covariance(contact: Contact, elapsed_s: float) -> Covariance2D:
    """The contact side of the gate's covariance sum: `Contact.position`'s
    own real, fused, anisotropic covariance (`plans/precise-position-belief/
    plan.md` Stage 4), inflated for elapsed motion since `contact.
    last_seen_sim`. Pre-Stage-4 this read an isotropic proxy built from the
    scalar `last_position_uncertainty_m` -- now that `Contact` holds a real
    2x2 covariance, that proxy is gone; this function reads it directly."""
    return contact.position.covariance.inflated(elapsed_s)


def passes_gate(percept: Percept, contact: Contact, now_sim: float) -> bool:
    """Whether `percept` may be merged into `contact` -- the spatial gate and
    the class-compatibility gate must both pass. See module docstring's
    "Spatial gate" section for the 2D covariance test."""
    if class_compatibility(percept.classification_raw, contact.last_class_raw) == (
        "incompatible"
    ):
        return False

    percept_position = implied_position(percept)
    dx = percept_position.x - contact.last_position.x
    dz = percept_position.z - contact.last_position.z
    elapsed_s = max(0.0, now_sim - contact.last_seen_sim)
    covariance = _percept_covariance(percept) + _contact_covariance(contact, elapsed_s)
    return covariance.mahalanobis_squared(dx, dz) <= GATE_SIGMA_THRESHOLD**2


def contacts_plausibly_same(a: Contact, b: Contact, now_sim: float) -> bool:
    """Whether two already-founded `Contact`s could plausibly be one real
    thing -- `plans/contact-report-flood/plan.md` Stage 1. Generalises
    `passes_gate` above (class compatibility, then a Mahalanobis test
    against the **sum** of both sides' own covariances, each inflated by
    its own elapsed time since its own `last_seen_sim`) from percept-vs-
    contact to contact-vs-contact, reusing `GATE_SIGMA_THRESHOLD` unchanged
    -- no new constant, no new radius. This is the same calibrated gate
    `ingest`'s ambiguity rule already trusts to mean "plausibly one real
    thing," applied symmetrically to two contacts instead of a percept and
    a contact.

    **Built to answer one specific question: is a freshly-founded contact
    a merge-echo of another contact's just-abandoned identity** (`belief.
    callouts.CalloutScheduler`'s `CONTACT_DETECTED` suppression check), not
    a general "are these the same" oracle. It is structurally unable to
    distinguish that merge-echo from a genuine split producing two
    plausibly-close contacts -- see `plans/contact-report-flood/plan.md`,
    "The honest cost of the chosen fix, stated plainly," for why that
    cost is accepted rather than fixed, and do not strengthen this
    function to try to tell the two apart; the ambiguity is structural,
    not a bug in this gate.

    Order of `a`/`b` does not matter -- the covariance sum and the
    class-compatibility check are both symmetric."""
    if class_compatibility(a.last_class_raw, b.last_class_raw) == "incompatible":
        return False

    dx = a.last_position.x - b.last_position.x
    dz = a.last_position.z - b.last_position.z
    elapsed_a = max(0.0, now_sim - a.last_seen_sim)
    elapsed_b = max(0.0, now_sim - b.last_seen_sim)
    covariance = _contact_covariance(a, elapsed_a) + _contact_covariance(b, elapsed_b)
    return covariance.mahalanobis_squared(dx, dz) <= GATE_SIGMA_THRESHOLD**2
