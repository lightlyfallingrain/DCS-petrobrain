"""2x2 covariance primitives and the fused position estimate -- `plans/
precise-position-belief/plan.md`.

**Runaway fusion, fixed by `plans/position-belief-runaway/debug.md`.** Two
independent defects, both live-flight-observed (2026-09-24): a fused mean
could land tens of kilometres from both of its own inputs, and separately
that fused mean was never checked against the physical envelope a look
could have been made from at all.

1. **Ill-conditioned triangulation (`_FUSION_SANITY_SIGMA`, inside
   `fold_position`).** Each look's covariance is a long thin ellipse.
   Intersecting two of them is real triangulation only when they cross at a
   real angle *and* actually agree; when they are near-parallel (or
   near-opposite, which is the same ellipse shape -- 180-periodic) and
   disagree even modestly along their shared imprecise (down-range)
   direction, the intersection point is arbitrarily sensitive to that
   disagreement and can land far from both inputs, exactly the mechanism
   that put a fused mean outside both of its own inputs in the live defect.
   **Bearing separation alone is not the right test** -- an earlier version
   of this guard gated on it directly and broke the ordinary, important case
   of repeated looks from the *same* bearing at the *same* place (residual
   zero), which must still tighten the estimate the same way averaging
   repeated measurements always does; near-parallel geometry is only
   dangerous in combination with disagreement, not on its own. So the guard
   instead checks the fused mean's own plausibility against **each input's
   own individual covariance** (not the combined/summed one
   `association_over_time.passes_gate` already gated the percept against
   before `fold_position` was ever called -- that sum is deliberately
   generous, since variances *add* under a sum, while intersecting them is
   what amplifies a modest disagreement into a wild mean; the two are
   different operations on the same numbers and a residual that easily
   passes the generous sum-gate can still be nonsense post-intersection):
   `min(mahalanobis(fused, prior.x/z; prior_covariance),
   mahalanobis(fused, x/z; look_covariance)) <= FUSION_SANITY_SIGMA`. A
   healthy fusion's own mean necessarily sits close (in Mahalanobis terms)
   to at least one of its two inputs, by construction -- when it does not,
   that is the observable signature of the ill-conditioning defect,
   independent of *why* the geometry went bad. When this guard fires, the
   new look is **not** fused into the mean or covariance at all; only the
   elapsed-time inflation still applies (the same "hold" policy
   `clamp_to_detection_envelope` below uses) -- a badly-conditioned pair of
   looks is not usable evidence for *where*, even though it may still be
   usable evidence for classification/cardinality/motion elsewhere in
   `Contact.record`. Verified against the live defect's own numbers, a
   repeated-identical-look case, a perpendicular-triangulation case, and a
   near-parallel case with a small (tens of metres) realistic residual that
   must still fuse -- see the debug report's worked examples.

2. **No detection-envelope gate on the believed position at all
   (`clamp_to_detection_envelope`).** Nothing previously stopped a fused
   mean from landing farther from an observer than that channel could ever
   have detected anything from -- a believed position beyond the envelope
   is an artifact of the fusion arithmetic, not a belief. This is a
   *caller-invoked* post-fusion check, not built into `fold_position`
   itself: unlike the ill-conditioning guard (a property of the two
   covariances alone), the envelope is a fact about a specific look's own
   observer position and the perception channel's own physical detection
   range (`perception.visibility.NAKED_EYE_RANGE_CAP_M` for the naked-eye
   channel, `perception.association.RANGE_CAP_M` for the scope/hybrid
   channel) -- neither of which `fold_position` receives or should have to,
   per this module's `(estimate, estimate) -> estimate` signature above
   (a future non-percept measurement, e.g. a pilot's written-down position,
   may have no detection envelope to check at all). `belief.contacts.
   Contact.record`/`from_percept` call it immediately after `fold_position`,
   supplying the new look's own `ownship_at_observation` as observer and a
   per-source cap. **Violating the envelope holds the prior** (unchanged
   mean, inflated for elapsed motion, same as the ill-conditioning guard's
   fallback) rather than clamping the mean onto the envelope boundary or
   discarding the look outright -- the plan's own reasoning: a look that
   implies an impossible position is evidence something about the fusion
   went wrong, not evidence of a position, so the prior (still the most
   recent trustworthy belief) is what should survive.

3. **No bound on how far a single *ambiguity fold* may move a fused
   position (`clamp_fold_displacement`, `plans/bounded-fold-displacement/
   plan.md`, `BL-B58`/`BL-B59`).** A Stage 3 within-group fold
   (`belief.contacts.ContactStore._fold_target_for_ambiguous_candidates`)
   folds a percept onto a contact the gate could not uniquely resolve --
   the fuse itself cannot distinguish that case from an ordinary
   unambiguous look, so an unlucky fold could move the mean farther than
   that contact's own class could plausibly have travelled, which then
   let a stale downstream cluster silently absorb or evict a real member
   (`BL-B58`/`BL-B59`). Like `clamp_to_detection_envelope`, this is a
   *caller-invoked* post-fusion check -- bounding inside `fold_position`
   would need an `is_fold` flag, making the fuse know about *association
   ambiguity*, a boundary this module's own fold-vs-look-covariance split
   above already draws. `belief.contacts.Contact.record` calls it last, on
   the result `clamp_to_detection_envelope` already returned, with a bound
   derived from the contact's own believed class rate and the elapsed time
   since its own last genuine fuse (never from any DCS ground-truth
   position or velocity) when `record`'s own `ambiguous_fold` keyword says
   this call is a fold; `None` otherwise, which is this function's
   identity branch. **The fold still happens and the clamped mean is still
   fused evidence** -- only the *distance the mean travels* is capped; the
   clamped remainder keeps the fuse's own covariance, never the prior's
   (plan §2c: holding the prior's covariance leaves its `fused_at_sim`
   behind, which grows every subsequent fold's own bound).

Kept out of `belief.contacts` deliberately, to hold that already-crowded
module's diff small (plan's Affected Modules). `Covariance2D`/
`covariance_from_uncertainty` are used two places: `belief.
association_over_time.passes_gate`'s 2D gate (Stage 3) budgets a look's
covariance against a contact's; `PositionEstimate`/`fold_position` is the
fused estimate `belief.contacts.Contact.position` holds (Stage 4).

**Refinement is covariance fusion, not a running mean.** Each look
contributes an elongated ellipse oriented along *that look's* line of
sight. When ownship moves, successive lines of sight cross, and the
intersection of two long thin ellipses is small in both axes -- real
triangulation, which a scalar running mean cannot express. `fold_position`
is the standard information-form update on 2x2 symmetric matrices:

    I_new = I_old + R_look^-1,   I . mu = I_old . mu_old + R_look^-1 . z_look

three floats of covariance state per contact (`xx`, `zz`, `xz`) plus the
two-float mean -- no library.

Between updates, `Covariance2D.inflated` grows the prior covariance by
elapsed motion, reusing `GATE_GROWTH_RATE_MPS` (declared here, not in
`belief.association_over_time` -- that module imports it from here, moved
so this module never has to import `association_over_time` and risk a
cycle with Stage 3's gate) -- the same physical statement `spatial_gate_
radius_m` used to make with its own elapsed term, now held on the contact
instead of recomputed at every gate call.

**Deliberately a plain serialisable value** (`PositionEstimate`) -- floats
only, no live reference into `ContactStore.observations`. This is what
`plans/precise-position-belief/plan.md`'s "BL-8, and what not to foreclose"
asks for: a kneeboard entry needs to persist a believed position on its
own. The fold's signature is `(estimate, estimate) -> estimate`, not
`(contact, percept) -> contact`, so a later non-percept measurement (a
pilot's written-down position) can fold in without special-casing.

No `perception.source` truth field is read here -- `PositionUncertainty`
is perceived metadata (see that dataclass's own docstring), and everything
else this module touches (`x`, `z`, `bearing_deg`) is either the gate's own
already-boundary-crossed `implied_position` or the fused mean this module
itself produces.

**Hold-recovery timing, fixed by `plans/position-belief-runaway/debug.md`'s
2026-09-25 security-review addendum.** Both "hold the prior" branches above
(the ill-conditioning guard inside `fold_position`, and
`clamp_to_detection_envelope`) used to reset `PositionEstimate.as_of_sim`
to the current poll's `t_sim` on every hold, and the *next* call's elapsed-
time inflation was computed against that reset timestamp. Under continuous
polling that composes `(GATE_GROWTH_RATE_MPS * dt) ** 2` once per poll
instead of `(GATE_GROWTH_RATE_MPS * T) ** 2` once per `T`-second gap --
summing `n` squared pieces of a fixed budget is always less than squaring
the whole budget, so recovery time scaled as roughly `1 / poll_interval_s`
and grew without bound as poll rate increased (measured: ~47s at
`body._DEFAULT_POLL_INTERVAL_S = 1.0`, ~934s at 0.05s), even though the
review that approved this branch's own guards had verified only a
single-gap ~20s recovery.

**The invariant, stated so it cannot regress silently: elapsed-time
inflation measures time since the last genuinely fused update, never time
since the last poll (whether or not that poll held).** `PositionEstimate`
therefore carries two timestamps with two different meanings --
`as_of_sim` ("this estimate is current as of this sim-time," bumped on
every poll including a hold, since the belief *is* still the best current
answer even when unchanged) and `fused_at_sim` ("real evidence last
changed this estimate's covariance," bumped only when `fold_position`
actually fuses a look, never by a hold). `fused_covariance` is the
covariance as computed at `fused_at_sim`, before any elapsed-time
inflation -- the true, non-compounding base every inflation calculation
recomputes fresh from, via `_inflated_since_last_fuse` below, rather than
inflating an already-inflated `covariance` field a second time."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from perception.estimation import (
    SYSTEMATIC_BIAS_FRACTION,
    effective_down_correlation,
    range_sigma_scale_for_optic,
    stable_range_correlation,
    stable_share,
    view_range_correlation,
)
from perception.geometry import GeoPosition, angular_delta_deg, bearing_deg, range_m
from perception.source import PositionUncertainty

#: How fast a contact could plausibly have moved since it was last
#: observed, metres/second -- a generic ground-vehicle order-of-magnitude
#: figure (72 km/h), not derived from any specific unit's real top speed.
#: Placeholder, revisit once real sessions show whether contacts are gated
#: too tightly or too loosely. Moved here from `belief.association_over_
#: time` by `plans/precise-position-belief/plan.md` Stage 3 -- see module
#: docstring for why the direction of the move avoids an import cycle.
GATE_GROWTH_RATE_MPS: Final[float] = 20.0


#: Stage 2b's calibration table (`plans/group-contact-identity/plan.md`
#: Stage 2) -- every row is a **stated assumption**, scaled by user
#: direction (D8: *"20 m/s is fast for most units... Expect slower"*),
#: none of it measured. Read via `plausible_speed_mps` below, never
#: directly -- that function is the one place `installation_component`
#: overrides the op_class lookup, and the one place a missing/unmapped
#: `op_class` (including `object_model.DEFAULT_OP_CLASS`,
#: `"OP_GROUPSOMETHING"`) falls back to `_DEFAULT_PLAUSIBLE_SPEED_MPS`.
_PLAUSIBLE_SPEED_MPS: Final[dict[str, float]] = {
    "OP_INFANTRY": 2.0,  # dismounted pace -- stated assumption.
    "OP_ARMORED": 8.0,  # ~29 km/h sustained, scaled from D8's "near full
    # speed" framing of 20 m/s for armour.
    "OP_SPAAG": 8.0,  # same band as armour -- stated assumption.
    "OP_ZU23": 8.0,
    "OP_SRSAM": 8.0,
    "OP_MRSAM": 8.0,
    "OP_LRSAM": 8.0,
    "OP_TRUCK": 15.0,  # road truck, deliberately below the old flat 20.
    "OP_SHIP": 10.0,  # stated assumption.
}

#: The table's own default row, including `object_model.DEFAULT_OP_CLASS`
#: ("OP_GROUPSOMETHING") and any `op_class` string the table does not
#: name. **Deliberately not `GATE_GROWTH_RATE_MPS` (20.0)** -- the old
#: value modelled the worst case for everything, which is exactly the
#: behaviour D8 overturns.
_DEFAULT_PLAUSIBLE_SPEED_MPS: Final[float] = 8.0


def plausible_speed_mps(
    op_class: str, *, installation_component: bool = False
) -> float:
    """How fast a contact of `op_class` could plausibly have moved,
    metres/second -- the one shared table `plans/group-contact-identity/
    plan.md` Stage 2 threads through both consumers that need a per-class
    growth rate: this module's own elapsed-motion inflation
    (`Covariance2D.inflated`, via `_inflated_since_last_fuse`/
    `fold_position`/`clamp_to_detection_envelope`) and `belief.groups.
    group_matches` test 5's displacement bound. One table, not two, per
    `BL-B51`'s own lesson about a set declared more than once drifting
    apart -- see that backlog item.

    **Stage 2b (this commit): the real, calibrated table.**
    `installation_component is True` always wins and returns `0.0`
    ("~0 for entrenched", D8) regardless of `op_class` -- structural,
    keyed on the existing profile field rather than an `op_class` list,
    for the same reason `group-cohesion-redesign` plan.md §1 rejected an
    `op_class`-keyed installation set (a real system's entrenchment is a
    property of that specific emplacement, not of its weapon class: the
    same `OP_SRSAM`/`OP_MRSAM` bucket covers both a dug-in SA-3 site and a
    mobile SA-13). Otherwise `_PLAUSIBLE_SPEED_MPS.get(op_class,
    _DEFAULT_PLAUSIBLE_SPEED_MPS)` -- every row a stated assumption, none
    measured; see that table's own docstring for the per-row provenance.

    Replaces Stage 2a's flat `GATE_GROWTH_RATE_MPS`-for-everything body --
    `tests/test_position_belief.py::
    test_plausible_speed_mps_stage_2a_is_flat_for_every_class` (that
    commit's own acceptance test, which this change necessarily falsifies)
    is deleted in this commit, replaced by this docstring's own calibration
    test.

    No-omniscience: takes a bare `op_class` string and a bool, resolved by
    each caller from `Contact.last_class_raw` (believed classification)
    via `object_model.profile_for` -- never a DCS `object_type`. This
    function itself holds no reference to `Contact` or any perception
    type, by design (see module docstring on why this module never
    imports `belief.association_over_time` or `perception.object_model`)."""
    if installation_component:
        return 0.0
    return _PLAUSIBLE_SPEED_MPS.get(op_class, _DEFAULT_PLAUSIBLE_SPEED_MPS)


#: Relative floor against a near-singular matrix when inverting, expressed
#: as a fraction of the matrix's own squared trace rather than an absolute
#: value -- `2026-09-25` addendum to `plans/position-belief-runaway/
#: debug.md`: `inverse()` is called on both covariance-scale matrices (real
#: declared sigmas, determinants ~1e7-1e12 m^4 for a naked-eye look) and
#: information-scale matrices (their inverse, determinants ~1e-8 to 1e-12),
#: so one absolute constant cannot be "near zero" for both regimes -- the
#: original `1e-9` was calibrated for the former and silently corrupted the
#: latter for any same-bearing repeated naked-eye look beyond ~2.7km
#: (reachable well inside the 10km naked-eye envelope, not a corner case;
#: see that addendum for the measured drift and guard-misfire it caused).
#:
#: `determinant / trace^2` is exactly `ab / (a+b)^2` for a matrix's own
#: eigenvalues `a, b` -- its minor-to-major-eigenvalue eccentricity -- and
#: this ratio is provably invariant under `inverse()` (inversion flips the
#: sign of both eigenvalues' exponents, leaving their ratio, and hence this
#: fraction, unchanged). One fraction therefore guards genuine
#: near-singularity (an axis whose variance has collapsed toward zero
#: relative to its own matrix's other axis) at any scale, covariance or
#: information form alike. An ordinary naked-eye look's own covariance
#: sits at ratio ~0.08 (confirmed numerically, same addendum) -- many
#: orders of magnitude above this floor, so it never fires on real data;
#: it exists purely so a genuinely degenerate matrix (one axis's variance
#: at or near exactly zero) cannot divide by zero.
_MIN_DETERMINANT_RATIO: Final[float] = 1e-9

#: Absolute backstop beneath `_MIN_DETERMINANT_RATIO` -- guards the fully
#: degenerate `trace == 0` case (both variances exactly zero), where a
#: floor computed relative to the matrix's own trace would itself be zero
#: and the division below would still fail.
_MIN_DETERMINANT_ABSOLUTE: Final[float] = 1e-300

#: `plans/same-optic-gate-indefinite/debug.md`'s second pass -- how far
#: `_max_c_down_for_psd` keeps `S`'s own `det/trace^2` ratio away from
#: `0`, not just non-negative. **Not a correlation/physics judgement call
#: (unlike `rho_eff` and everything it is built from) -- a numerical-
#: stability margin, the same role `_MIN_DETERMINANT_RATIO` above already
#: plays for `.inverse()` itself**, five orders of magnitude above that
#: floor so `S`'s own inversion never has to engage its floor at all for
#: a cap this function returns. Landing the cap exactly at `det(S) == 0`
#: (the pre-this-pass behaviour) is mathematically the tightest valid
#: cap, but measured (`tools/measure_gate_calibration.py`, second pass):
#: on a same-optic, 2km/4s-gap cell, 4.3% of `passes_gate` evaluations
#: landed within `_MIN_DETERMINANT_RATIO` of that boundary, where `.
#: inverse()`'s own floor then clamps the determinant to an
#: almost-arbitrary tiny value -- the resulting "precision matrix" is
#: not a meaningful inverse of anything, and the Mahalanobis test it
#: feeds explodes to values in the billions, rejecting the percept
#: regardless of its actual offset. Those trials accounted for 38-45% of
#: that cell's excess rejections (11.2% observed against the ~1.1% a
#: correctly-sized 3-sigma gate predicts). Kept away from the boundary
#: by this margin, `S` stays a well-conditioned covariance for every
#: caller, gate and fold alike -- `correlated_innovation` is their one
#: shared source, so this fixes both without either needing its own
#: ill-conditioning check (the fold already has one, `_is_valid_
#: covariance`'s "hold" branch; the gate has none at all, and never
#: needed one until the cap could land it in this regime).
_MIN_S_DETERMINANT_RATIO: Final[float] = 1e-4

#: `plans/position-belief-runaway/debug.md` -- `fold_position`'s
#: ill-conditioning guard: the fused mean must sit within this many "sigma"
#: (in the sense of `Covariance2D.mahalanobis_squared`) of *at least one* of
#: its two inputs, each judged against that input's own individual
#: covariance (not the sum). 5 is deliberately generous -- the live defect's
#: own numbers sat at ~14 sigma from both inputs; a small, realistic
#: residual (tens of metres at a near-parallel bearing) sits under 1; a
#: genuinely large but still-plausible disagreement (hundreds of metres)
#: still sits under 4 -- chosen so the guard only fires in the genuinely
#: degenerate regime, not on ordinary measurement noise.
FUSION_SANITY_SIGMA: Final[float] = 5.0


def _inflated_since_last_fuse(
    prior: PositionEstimate,
    t_sim: float,
    growth_rate_mps: float = GATE_GROWTH_RATE_MPS,
) -> Covariance2D:
    """`prior.fused_covariance`, inflated for elapsed motion since `prior.
    fused_at_sim` -- **always the last genuinely fused update, never the
    last poll** (module docstring's "Hold-recovery timing" invariant).
    Every place this module needs "the prior's covariance, brought up to
    date" -- fusing a new look against it, or holding it forward another
    poll -- goes through this one function, so inflation is computed fresh
    from the true base every time rather than compounding an
    already-inflated `prior.covariance` a second time across a chain of
    holds.

    `growth_rate_mps` (`plans/group-contact-identity/plan.md` Stage 2a) is
    the contact's own class-derived rate, resolved by the caller via
    `plausible_speed_mps` -- this function never resolves a classification
    itself (module docstring: `PositionEstimate` does not know its own
    classification and should not). Defaults to `GATE_GROWTH_RATE_MPS` so
    every pre-Stage-2 call site compiles and behaves unchanged."""
    elapsed_s = max(0.0, t_sim - prior.fused_at_sim)
    return prior.fused_covariance.inflated(elapsed_s, growth_rate_mps)


@dataclass(frozen=True, slots=True)
class Covariance2D:
    """A symmetric 2x2 covariance over world (x, z), in metres^2. `xz` is
    the off-diagonal (cross) term."""

    xx: float
    zz: float
    xz: float

    def __add__(self, other: Covariance2D) -> Covariance2D:
        return Covariance2D(
            xx=self.xx + other.xx, zz=self.zz + other.zz, xz=self.xz + other.xz
        )

    def __sub__(self, other: Covariance2D) -> Covariance2D:
        """`BL-B108` Stage 2 -- `correlated_innovation`'s `S = P_est +
        P_look - (C + C^T)` needs this; no caller before this stage ever
        subtracted two covariances."""
        return Covariance2D(
            xx=self.xx - other.xx, zz=self.zz - other.zz, xz=self.xz - other.xz
        )

    def scaled(self, factor: float) -> Covariance2D:
        return Covariance2D(
            xx=self.xx * factor, zz=self.zz * factor, xz=self.xz * factor
        )

    def apply(self, x: float, z: float) -> tuple[float, float]:
        """Matrix-vector product `self @ (x, z)`."""
        return (self.xx * x + self.xz * z, self.xz * x + self.zz * z)

    def inverse(self) -> Covariance2D:
        determinant = self.xx * self.zz - self.xz * self.xz
        trace = self.xx + self.zz
        floor = max(_MIN_DETERMINANT_RATIO * trace * trace, _MIN_DETERMINANT_ABSOLUTE)
        determinant = max(determinant, floor)
        return Covariance2D(
            xx=self.zz / determinant,
            zz=self.xx / determinant,
            xz=-self.xz / determinant,
        )

    def inflated(
        self, elapsed_s: float, growth_rate_mps: float = GATE_GROWTH_RATE_MPS
    ) -> Covariance2D:
        """Add isotropic process noise for `elapsed_s` of elapsed motion --
        see module docstring."""
        growth_m = growth_rate_mps * max(0.0, elapsed_s)
        growth_var = growth_m * growth_m
        return Covariance2D(
            xx=self.xx + growth_var, zz=self.zz + growth_var, xz=self.xz
        )

    def trace(self) -> float:
        return self.xx + self.zz

    def mahalanobis_squared(self, dx: float, dz: float) -> float:
        """`[dx dz] . self^-1 . [dx dz]^T` -- how many "sigmas" (in this
        covariance's own shape) the offset `(dx, dz)` sits at."""
        inv_x, inv_z = self.inverse().apply(dx, dz)
        return dx * inv_x + dz * inv_z


def covariance_from_uncertainty(
    uncertainty: PositionUncertainty, look_bearing_deg: float
) -> Covariance2D:
    """`PositionUncertainty`'s (cross, down) sigma pair, rotated from
    line-of-sight axes onto world x/z at `look_bearing_deg` (the look's own
    true bearing, `perception.geometry.bearing_deg`'s convention -- 0 along
    +x, sweeping toward +z)."""
    theta = math.radians(look_bearing_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    var_down = uncertainty.sigma_down_m**2
    var_cross = uncertainty.sigma_cross_m**2
    # Down-range axis is along (cos, sin); cross-range is the perpendicular
    # (-sin, cos).
    xx = var_down * cos_t * cos_t + var_cross * sin_t * sin_t
    zz = var_down * sin_t * sin_t + var_cross * cos_t * cos_t
    xz = (var_down - var_cross) * sin_t * cos_t
    return Covariance2D(xx=xx, zz=zz, xz=xz)


@dataclass(frozen=True, slots=True)
class LookAnchor:
    """The geometry and optic of the one look `PositionEstimate.anchor`
    remembers -- `plans/relative-distance-grouping/plan.md` (`BL-B108`)
    Stage 2. Founding sets it from the founding look; every genuine fuse
    sets it to the new look (module docstring's "Co-moving Fields" table
    -- every other `PositionEstimate` construction site carries the prior
    anchor through unchanged via `dataclasses.replace`).

    `bearing_deg`/`range_m` are that look's own true bearing/range from
    `observer_x`/`observer_z` -- the only two numbers `correlated_
    innovation` needs to say how correlated a *different* look's stable
    error plausibly is with this one (`perception.estimation.
    stable_range_correlation`'s own two inputs: bearing separation, range
    ratio). `observer_x`/`observer_z` are kept for completeness/future
    use (a consumer that needs to recompute this look's own geometry from
    scratch) -- `correlated_innovation` itself only reads `bearing_deg`/
    `range_m`/`optic_class`/`sigma_down_stable_m`.

    `optic_class` is the active optic's own `Optic.name`, and `sigma_
    down_stable_m` is `perception.estimation.stable_down_sigma_m` of that
    look's own `sigma_down_m` -- the one perceived quantity `correlated_
    innovation` needs beyond the correlation coefficient itself (module
    docstring: "the look's own anchor", singular, one anchor per estimate,
    not a history -- the plan's own stated "one-anchor approximation")."""

    observer_x: float
    observer_z: float
    bearing_deg: float
    range_m: float
    optic_class: str
    sigma_down_stable_m: float


@dataclass(frozen=True, slots=True)
class _Matrix2D:
    """A general (not necessarily symmetric) real 2x2 matrix -- used only
    for the correlated-fusion cross-covariance `C`/`C^T` in `fold_
    position`'s Bar-Shalom-Campo update (`correlated_innovation`'s own
    docstring). `Covariance2D` (3 independent components) is not enough
    here: `C`, the cross-covariance between two different looks' stable
    error terms each along its *own* line-of-sight axis, is generally
    asymmetric when the two axes differ -- only `C + C^T` (`S`'s own
    term) is guaranteed symmetric."""

    xx: float
    xz: float
    zx: float
    zz: float

    def transpose(self) -> _Matrix2D:
        return _Matrix2D(xx=self.xx, xz=self.zx, zx=self.xz, zz=self.zz)

    def __add__(self, other: _Matrix2D) -> _Matrix2D:
        return _Matrix2D(
            xx=self.xx + other.xx,
            xz=self.xz + other.xz,
            zx=self.zx + other.zx,
            zz=self.zz + other.zz,
        )

    def __sub__(self, other: _Matrix2D) -> _Matrix2D:
        return _Matrix2D(
            xx=self.xx - other.xx,
            xz=self.xz - other.xz,
            zx=self.zx - other.zx,
            zz=self.zz - other.zz,
        )

    def apply(self, x: float, z: float) -> tuple[float, float]:
        return (self.xx * x + self.xz * z, self.zx * x + self.zz * z)

    def matmul(self, other: _Matrix2D) -> _Matrix2D:
        return _Matrix2D(
            xx=self.xx * other.xx + self.xz * other.zx,
            xz=self.xx * other.xz + self.xz * other.zz,
            zx=self.zx * other.xx + self.zz * other.zx,
            zz=self.zx * other.xz + self.zz * other.zz,
        )

    def as_symmetric_covariance(self) -> Covariance2D:
        """Average `xz`/`zx` into one off-diagonal -- for a matrix the
        caller already knows is symmetric (up to floating-point residue),
        never for one that might genuinely not be."""
        return Covariance2D(xx=self.xx, zz=self.zz, xz=(self.xz + self.zx) / 2.0)

    @staticmethod
    def from_covariance(covariance: Covariance2D) -> _Matrix2D:
        return _Matrix2D(
            xx=covariance.xx, xz=covariance.xz, zx=covariance.xz, zz=covariance.zz
        )


def _down_axis_unit(bearing_deg_value: float) -> tuple[float, float]:
    theta = math.radians(bearing_deg_value)
    return math.cos(theta), math.sin(theta)


def _is_valid_covariance(covariance: Covariance2D) -> bool:
    """`False` for a 2x2 matrix that cannot be a real covariance -- a
    negative trace, or a negative determinant (one axis's variance
    gone negative even though the trace is still positive) -- `BL-B108`
    Stage 2's own found defect: the Bar-Shalom-Campo update's `P_est -
    K @ (P_est - C^T)` is **not** guaranteed positive-semidefinite by
    construction the way the old independent information-form sum was
    (that form's `info_sum.inverse()` can only ever produce a valid
    covariance) -- when the two sides are highly correlated and close in
    magnitude, `S` can be near-singular, and a near-singular `S^-1`
    amplified through `K` can push the result negative. `fold_position`'s
    existing `FUSION_SANITY_SIGMA` mean-residual check alone does not
    catch this (a wildly wrong but nonsensical covariance can still sit
    close to one input's own *mean*) -- found empirically, by a dwelled-
    look scenario whose covariance went negative (`xx = -74033`) after
    several highly-correlated same-geometry fuses, not by inspection.
    Checked here, folded into the same ill-conditioning "hold" branch
    `fold_position` already has, rather than as a second guard, since the
    remedy (discard this fuse, hold the prior) is identical."""
    trace = covariance.trace()
    if trace < 0.0:
        return False
    determinant = covariance.xx * covariance.zz - covariance.xz * covariance.xz
    return determinant >= 0.0


def _down_variance_along(covariance: Covariance2D, bearing_deg_value: float) -> float:
    """The down-range (along-line-of-sight) variance `covariance`
    projects onto the axis at `bearing_deg_value` -- `PositionEstimate.
    range_uncertainty_m`'s own projection, factored out so `correlated_
    innovation`'s per-axis cap (below) can read it for an arbitrary
    covariance/bearing pair, not only `self`'s own."""
    cos_t, sin_t = _down_axis_unit(bearing_deg_value)
    return (
        covariance.xx * cos_t * cos_t
        + 2.0 * covariance.xz * sin_t * cos_t
        + covariance.zz * sin_t * sin_t
    )


def _max_c_down_for_psd(
    sum_covariance: Covariance2D, k_xx: float, k_zz: float, k_xz: float
) -> float:
    """The largest `c >= 0` for which `sum_covariance - c * K` stays
    positive semi-definite, where `K = (xx=k_xx, zz=k_zz, xz=k_xz)` is the
    fixed symmetric "direction" matrix `correlated_innovation`'s cross-
    term `c_sym` is `c_down * K` of -- `plans/same-optic-gate-indefinite/
    debug.md` (fixing `BL-B108`'s original per-axis `min(var_prior_along,
    var_look_along)` cap, which is **not** tight enough: it bounds the
    cross-term's magnitude using each side's own along-axis variance, but
    `S = sum_covariance - c_sym` can still go indefinite from `sum_
    covariance`'s off-diagonal (cross-axis) structure alone, which that
    per-axis bound never sees -- measured on a real same-optic gate
    evaluation where the per-axis cap (109 036) left `S`'s determinant at
    -4.3e8; this exact cap (103 381) lands it at ~0).

    `sum_covariance` is always valid (a sum of two already-valid
    covariances), so `det(sum_covariance) >= 0` and `trace(sum_covariance)
    >= 0`. `K` is always `anchor_u (x) look_u + look_u (x) anchor_u` for
    two unit vectors (never computed by a different caller), so `det(K) =
    -(anchor_u x look_u)**2 <= 0` always (the two unit vectors' 2D cross
    product, squared) -- `f(c) = det(sum_covariance - c*K)` is therefore a
    downward-opening (or, at `det(K) == 0`, linear) function of `c` that
    starts at `f(0) = det(sum_covariance) >= 0`, so it has exactly one
    root on the positive side (or none, if `b <= 0` in the degenerate
    linear case) -- the smallest positive `c` where `S` first becomes
    singular. A second, independent cap comes from the trace: `trace(S) =
    trace(sum_covariance) - c * trace(K)` must also stay non-negative
    (a non-negative determinant alone permits two negative eigenvalues,
    not just two non-negative ones). The smaller of the two caps is
    returned; `prior.anchor is not None` is this function's only
    precondition (`correlated_innovation`'s own caller already checked
    it).

    **Second pass (`_MIN_S_DETERMINANT_RATIO`'s own docstring): the root
    solved for is `det(S) == _MIN_S_DETERMINANT_RATIO * trace(S)^2`, not
    `det(S) == 0`.** `trace(S)` is itself `trace_a - c*trace_k` (exact,
    not approximated at `trace_a`), so substituting the margin's target
    into `f(c) = det_a - b*c + det_k*c^2` and collecting terms in `c`
    gives a quadratic of the *same shape*, with adjusted coefficients
    `det_a' = det_a - margin*trace_a^2`, `b' = b - 2*margin*trace_a*
    trace_k`, `det_k' = det_k - margin*trace_k^2` -- `det_k' <= 0` still
    holds (subtracting a non-negative quantity from an already
    non-positive `det_k`), so the same root-finding below applies
    unchanged against the primed coefficients. At `margin = 0` this
    collapses to exactly the original derivation."""
    margin = _MIN_S_DETERMINANT_RATIO
    det_a_raw = max(0.0, sum_covariance.xx * sum_covariance.zz - sum_covariance.xz**2)
    trace_a = sum_covariance.xx + sum_covariance.zz
    trace_k = k_xx + k_zz
    det_k_raw = k_xx * k_zz - k_xz * k_xz
    b_raw = (
        sum_covariance.xx * k_zz
        + sum_covariance.zz * k_xx
        - 2.0 * sum_covariance.xz * k_xz
    )
    det_a = det_a_raw - margin * trace_a * trace_a
    b = b_raw - 2.0 * margin * trace_a * trace_k
    det_k = det_k_raw - margin * trace_k * trace_k

    if det_a <= 0.0:
        # Even an uncorrelated `c = 0` already sits inside the margin
        # (a highly eccentric `sum_covariance` on its own) -- no positive
        # `c` can satisfy the margin at all.
        return 0.0

    cap = math.inf
    if trace_k > 0.0:
        cap = trace_a / trace_k

    if abs(det_k) < 1e-12:
        if b > 0.0:
            cap = min(cap, det_a / b)
    else:
        discriminant = max(0.0, b * b - 4.0 * det_k * det_a)
        sqrt_discriminant = math.sqrt(discriminant)
        root_a = (b - sqrt_discriminant) / (2.0 * det_k)
        root_b = (b + sqrt_discriminant) / (2.0 * det_k)
        positive_root = max(root_a, root_b)
        cap = min(cap, positive_root)

    return max(0.0, cap)


def correlated_innovation(
    prior: PositionEstimate,
    prior_covariance: Covariance2D,
    look_covariance: Covariance2D,
    *,
    correlation_bearing_deg: float,
    correlation_range_m: float,
    correlation_optic_class: str,
    correlation_sigma_down_stable_m: float,
) -> tuple[Covariance2D, _Matrix2D, float]:
    """`(S, C, kappa_view)` for the correlated-fusion update, used by both
    `fold_position` (the fuse) and `belief.association_over_time.
    passes_gate`/`contacts_plausibly_same` (the gate) -- `plans/
    relative-distance-grouping/plan.md` Stage 2's one shared helper.
    `kappa_view` is `Z_view`'s own **geometric** kernel (`perception.
    estimation.view_range_correlation`), *not* scaled by the optic-ladder
    factor -- returned alongside `S`/`C` so a caller that also needs it
    (`fold_position`'s own floor) does not re-derive the same geometry a
    second time; the floor applies its own optic factor separately
    (`BL-B108` amendment, "Belief side" -- see `_apply_floor`).

    `prior_covariance`/`look_covariance` are each side's own ordinary,
    already-inflated declared covariance (`P_est`/`P_look`), computed
    exactly as before this stage -- what changes is `C`, the cross-
    covariance between the two sides' *stable* (geometry-correlated, not
    look-to-look) down-range error, which this function adds in.

    **The caller decides what `correlation_bearing_deg`/`correlation_
    range_m` mean, and that choice is the entire difference between the
    gate and the fold** (plan's Stage 2 text, "For the gate ... the
    hypothesis ... For the fold ... the look's own geometry"):

    - **Gate**: the bearing/range from the *current* observer to the
      contact's *believed* position (`prior.x`/`prior.z`) -- a hypothesis
      ("if this incoming look really were of this same contact, how
      correlated would its stable error be with the anchor's"), decoupled
      from the incoming look's own real, possibly very different,
      reported geometry. This is what makes the gate reject a look whose
      *implied position* disagrees by kilometres even though the
      hypothesis geometry alone would predict high correlation (the E1
      fold case) -- the correlation answers "how tightly should these
      agree", the Mahalanobis test below still compares against what the
      look actually said.
    - **Fold**: the incoming look's own real bearing/range, directly --
      by the time a fold happens the gate has already decided this look
      belongs to this contact, so there is no hypothesis left to test.

    `correlation_optic_class`/`correlation_sigma_down_stable_m` are always
    the incoming look's own real values (never a hypothesis value) --
    what correlates is the *actual* optic and sigma of the thing being
    compared against the anchor, regardless of which bearing/range mode
    above is in force.

    **The cap, revised (`plans/same-optic-gate-indefinite/debug.md`,
    fixing the `BL-B108` amendment "Belief side"'s original `for_fusion`-
    only cap)**: `C`'s down-range magnitude `c_down` is capped at `min(
    per_axis_cap, psd_cap)` -- **always applied now, for both callers**,
    where it used to apply only when `for_fusion` was set (`fold_
    position`'s own call). The original theory for not capping the
    gate's `S` was that the gate "tests the model correlation the noise
    really has" and never needs capping because any look it accepts sits
    inside the fold's own (larger) `S` by construction -- true for `S`
    being too *narrow*, false for `S` failing to be a valid covariance at
    all. `S` is built by *subtracting* a cross-term, which has no
    structural guarantee of staying positive semi-definite, and an
    uncapped `c_down` can exceed the bound a valid correlation permits
    when both looks share one optic and the hypothesis bearing matches
    the anchor closely (`rho_eff` near 1). Measured: on a same-optic
    (`u_u`), zero-growth, 2 km/4 s-gap cell, the gate's own uncapped `S`
    had a negative determinant on 7.0% of trials (`n=300`), which
    `Covariance2D.inverse()`'s determinant floor then clamped to a tiny
    positive value regardless of sign -- the resulting "inverse" is not a
    valid precision matrix, and the gate rejected those percepts almost
    regardless of their actual offset.

    **Two caps, not one, because each catches a failure the other
    misses:**

    - **`per_axis_cap` (the original `for_fusion` cap, `min(
      var_prior_along, var_look_along)`, each side's own along-axis
      variance projected independently)** is *not* tight enough on its
      own for the gate: it ignores `P_est + P_look`'s own off-diagonal
      (cross-axis) structure, which the subtracted cross-term also
      interacts with whenever the gate's hypothesis bearing differs from
      the look's own real bearing (the gate's `look_covariance` is built
      at the percept's own bearing but projected at the hypothesis
      bearing for this cap, unlike the fold, where the two always
      coincide) -- measured on the cell above, `per_axis_cap` alone
      (109 036) still left `S`'s determinant at -4.3e8.
    - **`psd_cap` (`_max_c_down_for_psd`, the exact closed-form PSD
      boundary)** fixes that -- capped there alone, the same cell's `S`
      lands at determinant ~0, nowhere lower. But landing *exactly* on
      the boundary is itself a problem for the **fold**: a repeated
      same-bearing dwell (`test_stage0a_armour_growth_bounded_by_prior_
      inflation_and_reaches_naked_grade_by_sixth_fuse`) regressed when
      `psd_cap` alone replaced the per-axis cap, because the Bar-Shalom-
      Campo fused-covariance formula (`P_est - gain @ (P_est - C^T)`,
      `gain` through `S^-1`) is exactly the numerically fragile case
      `_is_valid_covariance`'s own docstring already names ("a
      near-singular `S^-1` amplified through `K` can push the result
      negative") -- pushing `c_down` right up to where `det(S) == 0`
      pushes `S^-1` toward its own singularity, and the fused covariance
      can come out *larger*, not smaller, even though `S` itself stays
      nominally valid. `_is_valid_covariance`'s existing negative-
      determinant/negative-trace guard does not catch this, because the
      result it catches badly is still positive.

    **`min(per_axis_cap, psd_cap)`** is never looser than either cap
    alone: it keeps the fold on the same, already-proven-stable
    `per_axis_cap` everywhere that cap was already inside the true PSD
    region (every case this project has run the fold through before this
    fix), and only tightens further, to the exact boundary, in the cases
    `per_axis_cap` alone was not tight enough for -- exactly the gate's
    mismatched-hypothesis-bearing regime above, where `per_axis_cap`
    itself exceeded `psd_cap`. `for_fusion` is gone: one cap formula, one
    code path, correct for both callers.

    `prior.anchor is None` (the `speech.py` placeholder, module docstring
    "Co-moving Fields") makes `C` the zero matrix and `S` the ordinary
    independent sum -- the conservative, wider gate; never a *tighter*
    one from a missing anchor."""
    anchor = prior.anchor
    if anchor is None:
        return (
            prior_covariance + look_covariance,
            _Matrix2D(0.0, 0.0, 0.0, 0.0),
            0.0,
        )

    d_bearing_deg = angular_delta_deg(correlation_bearing_deg, anchor.bearing_deg)
    hi = max(correlation_range_m, anchor.range_m)
    lo = max(1.0, min(correlation_range_m, anchor.range_m))
    range_ratio_value = hi / lo
    kappa_view = view_range_correlation(d_bearing_deg, range_ratio_value)
    rho_view, rho_near = stable_range_correlation(
        d_bearing_deg, range_ratio_value, anchor.optic_class, correlation_optic_class
    )
    rho_eff = effective_down_correlation(rho_view, rho_near)
    c_down = rho_eff * anchor.sigma_down_stable_m * correlation_sigma_down_stable_m

    anchor_x, anchor_z = _down_axis_unit(anchor.bearing_deg)
    look_x, look_z = _down_axis_unit(correlation_bearing_deg)
    sum_covariance = prior_covariance + look_covariance
    k_xx = 2.0 * anchor_x * look_x
    k_zz = 2.0 * anchor_z * look_z
    k_xz = anchor_x * look_z + anchor_z * look_x
    var_prior_along = _down_variance_along(prior_covariance, anchor.bearing_deg)
    var_look_along = _down_variance_along(look_covariance, correlation_bearing_deg)
    per_axis_cap = max(0.0, min(var_prior_along, var_look_along))
    psd_cap = _max_c_down_for_psd(sum_covariance, k_xx, k_zz, k_xz)
    max_c_down = min(per_axis_cap, psd_cap)
    # Clamped to [0, max_c_down], not [-max_c_down, max_c_down]: behaviour-neutral, since
    # `effective_down_correlation` can only return a value in [0, 1] (`rho_view`/`rho_near` are
    # both non-negative by construction), so `c_down` was already non-negative in every real case.
    c_down = max(0.0, min(max_c_down, c_down))

    c_matrix = _Matrix2D(
        xx=c_down * anchor_x * look_x,
        xz=c_down * anchor_x * look_z,
        zx=c_down * anchor_z * look_x,
        zz=c_down * anchor_z * look_z,
    )
    c_sym = c_matrix + c_matrix.transpose()
    s = sum_covariance - c_sym.as_symmetric_covariance()
    return s, c_matrix, kappa_view


@dataclass(frozen=True, slots=True)
class PositionEstimate:
    """One contact's fused believed position: mean (x, z) plus its own 2x2
    covariance and the sim-time it is current as of. Plain floats, no live
    references -- see module docstring.

    `as_of_sim` and `fused_at_sim` carry deliberately different meanings
    (module docstring's "Hold-recovery timing" section): `as_of_sim` is
    "this is the current belief as of this sim-time" and moves on every
    poll, hold included; `fused_at_sim` is "real evidence last changed
    `fused_covariance`" and moves only when a look is genuinely fused.
    `fused_covariance` is `covariance` as it stood at `fused_at_sim`,
    before any elapsed-time inflation -- the base every hold recomputes
    fresh inflation from, so repeated holds never compound. On a freshly
    founded or genuinely fused estimate the two pairs are identical by
    construction (`as_of_sim == fused_at_sim`, `covariance ==
    fused_covariance`); they diverge only across one or more holds.

    `anchor` (`BL-B108` Stage 2) is the one look `correlated_innovation`
    reasons from -- `None` only for the `speech.py` placeholder `Contact`
    (module docstring's "Co-moving Fields" table), which has no real look
    behind it at all."""

    x: float
    z: float
    covariance: Covariance2D
    as_of_sim: float
    fused_at_sim: float
    fused_covariance: Covariance2D
    anchor: LookAnchor | None = None

    def radius_m(self) -> float:
        """Scalar reduction for every pre-existing caller that wants a
        single number -- `sqrt(trace)`, the RMS radius of the covariance's
        two principal variances (exact for a diagonal matrix; a reasonable
        isotropic stand-in otherwise, same spirit as the scalar `hypot`
        this replaces)."""
        return math.sqrt(max(0.0, self.covariance.trace()))

    def bearing_uncertainty_deg(self, observer: GeoPosition) -> float:
        """The cross-range component of this estimate's own uncertainty, as
        seen from `observer`, turned back into an angle -- what `belief.
        optic_policy.look_target_for` (Stage 5) needs: how wide a sweep
        must be to cover the belief's own uncertainty, not the down-range
        component, which is irrelevant to where to point."""
        target = GeoPosition(x=self.x, z=self.z, alt_m=observer.alt_m)
        slant_m = range_m(observer, target)
        if slant_m <= 0.0:
            return 0.0
        theta = math.radians(bearing_deg(observer, target))
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        # Cross-range variance is the covariance projected onto the
        # perpendicular (-sin, cos) axis.
        cross_var = (
            self.covariance.xx * sin_t * sin_t
            - 2.0 * self.covariance.xz * sin_t * cos_t
            + self.covariance.zz * cos_t * cos_t
        )
        sigma_cross_m = math.sqrt(max(0.0, cross_var))
        return math.degrees(math.atan2(sigma_cross_m, slant_m))

    def range_uncertainty_m(self, observer: GeoPosition) -> float:
        """`bearing_uncertainty_deg`'s exact down-range mirror -- the same
        covariance projected onto the observer->target bearing itself
        rather than its perpendicular, returned as a metres figure (there
        is no small-angle conversion to a range figure the way cross-range
        needs `atan2` to become degrees; a down-range sigma already *is* a
        distance). `plans/watch-reporting/plan.md` Decision 5a-i: the
        kilometre-crossing trigger's deadband is derived from this rather
        than a tuned constant, so a precise estimate re-arms almost
        immediately and a noisy one has to actually mean it."""
        target = GeoPosition(x=self.x, z=self.z, alt_m=observer.alt_m)
        theta = math.radians(bearing_deg(observer, target))
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        # Down-range variance is the covariance projected onto (cos, sin) --
        # `covariance_from_uncertainty`'s own axis convention, mirrored.
        down_var = (
            self.covariance.xx * cos_t * cos_t
            + 2.0 * self.covariance.xz * sin_t * cos_t
            + self.covariance.zz * sin_t * sin_t
        )
        return math.sqrt(max(0.0, down_var))


def estimate_from_look(
    x: float,
    z: float,
    uncertainty: PositionUncertainty,
    look_bearing_deg: float,
    look_range_m: float,
    t_sim: float,
    *,
    observer_x: float,
    observer_z: float,
) -> PositionEstimate:
    """A single look's own `PositionEstimate`, with no prior to fuse
    against -- `fold_position`'s founding case, factored out so a founding
    contact and a re-observed one build their look covariance identically.

    `look_range_m`/`observer_x`/`observer_z` (`BL-B108` Stage 2) are the
    three numbers `LookAnchor` needs beyond what `uncertainty` already
    carries (`optic_class`/`sigma_down_stable_m`) -- see that dataclass's
    own docstring."""
    covariance = covariance_from_uncertainty(uncertainty, look_bearing_deg)
    anchor = LookAnchor(
        observer_x=observer_x,
        observer_z=observer_z,
        bearing_deg=look_bearing_deg,
        range_m=look_range_m,
        optic_class=uncertainty.optic_class,
        sigma_down_stable_m=uncertainty.sigma_down_stable_m,
    )
    return PositionEstimate(
        x=x,
        z=z,
        covariance=covariance,
        as_of_sim=t_sim,
        fused_at_sim=t_sim,
        fused_covariance=covariance,
        anchor=anchor,
    )


def fold_position(
    prior: PositionEstimate | None,
    *,
    x: float,
    z: float,
    uncertainty: PositionUncertainty,
    look_bearing_deg: float,
    look_range_m: float,
    t_sim: float,
    observer_x: float,
    observer_z: float,
    growth_rate_mps: float = GATE_GROWTH_RATE_MPS,
) -> PositionEstimate:
    """Fuse one look `(x, z, uncertainty, look_bearing_deg, look_range_m)`
    into `prior` (`None` for a founding percept) -- see module docstring.
    **`BL-B108` Stage 2**: the fuse itself is now the standard Bar-Shalom-
    Campo update for two measurements with a known cross-correlation `C`
    (`correlated_innovation`), not a plain information-form sum of two
    *independent* covariances -- a contact's down-range error is now
    correlated across looks at a similar geometry (module docstring of
    `perception.estimation`), and fusing it as independent is exactly
    the bug this plan exists to fix (the gate budgets the stable error
    twice and the fold converges on it as if it genuinely averaged out).
    The result is floored so it can never claim more precision than the
    current geometry's own stable share would allow (`_apply_floor`,
    revised this stage).

    `growth_rate_mps` (`plans/group-contact-identity/plan.md` Stage 2a)
    is passed straight through to `_inflated_since_last_fuse` for the
    `prior is not None` branch's elapsed-motion inflation; it is never
    read when `prior is None` (a founding look has no elapsed motion to
    inflate). Defaults to `GATE_GROWTH_RATE_MPS`, unchanged for every
    pre-Stage-2 caller.

    **Ill-conditioning guard** (module docstring, defect 1), unchanged in
    spirit: when `prior` is not `None`, the fused mean is computed first,
    then checked against `FUSION_SANITY_SIGMA` -- if it does not sit
    within that many sigma of *either* input, judged against that input's
    own individual covariance, the fusion is treated as ill-conditioned
    and discarded: the look is not fused into the mean or covariance at
    all, only elapsed-time inflation is applied, exactly the "hold"
    outcome `clamp_to_detection_envelope` uses for the other defect.
    **`BL-B108` Stage 2 adds a second trigger for the same hold branch**:
    `_is_valid_covariance(fused_covariance)` -- the correlated update's
    own `S` can go near-singular when the two sides are highly
    correlated and similar in magnitude (repeated same-geometry looks,
    exactly the dwell case this plan's own E3/E4 care most about), and an
    ill-conditioned `S^-1` can push the resulting covariance negative
    even while the mean still looks plausible -- see that function's own
    docstring for the dwell scenario that found it."""
    look_covariance = covariance_from_uncertainty(uncertainty, look_bearing_deg)
    look_anchor = LookAnchor(
        observer_x=observer_x,
        observer_z=observer_z,
        bearing_deg=look_bearing_deg,
        range_m=look_range_m,
        optic_class=uncertainty.optic_class,
        sigma_down_stable_m=uncertainty.sigma_down_stable_m,
    )
    if prior is None:
        fused = PositionEstimate(
            x=x,
            z=z,
            covariance=look_covariance,
            as_of_sim=t_sim,
            fused_at_sim=t_sim,
            fused_covariance=look_covariance,
            anchor=look_anchor,
        )
        kappa_view_at_fuse = 1.0
        prior_optic_class: str | None = uncertainty.optic_class
    else:
        prior_covariance = _inflated_since_last_fuse(prior, t_sim, growth_rate_mps)
        s, c, kappa_view_at_fuse = correlated_innovation(
            prior,
            prior_covariance,
            look_covariance,
            correlation_bearing_deg=look_bearing_deg,
            correlation_range_m=look_range_m,
            correlation_optic_class=uncertainty.optic_class,
            correlation_sigma_down_stable_m=uncertainty.sigma_down_stable_m,
        )
        prior_optic_class = (
            prior.anchor.optic_class if prior.anchor is not None else None
        )
        s_inv_matrix = _Matrix2D.from_covariance(s.inverse())
        p_est_matrix = _Matrix2D.from_covariance(prior_covariance)
        gain = (p_est_matrix - c).matmul(s_inv_matrix)
        dx, dz = x - prior.x, z - prior.z
        correction_x, correction_z = gain.apply(dx, dz)
        fused_x, fused_z = prior.x + correction_x, prior.z + correction_z
        fused_covariance = (
            p_est_matrix - gain.matmul(p_est_matrix - c.transpose())
        ).as_symmetric_covariance()
        prior_residual_sigma_sq = prior_covariance.mahalanobis_squared(
            fused_x - prior.x, fused_z - prior.z
        )
        look_residual_sigma_sq = look_covariance.mahalanobis_squared(
            fused_x - x, fused_z - z
        )
        if min(
            prior_residual_sigma_sq, look_residual_sigma_sq
        ) > FUSION_SANITY_SIGMA**2 or not _is_valid_covariance(fused_covariance):
            # Hold: elapsed-time inflation still applies (`prior_covariance`
            # above already is that fresh, non-compounding inflation), but
            # `fused_at_sim`/`fused_covariance`/`anchor` carry straight
            # through unchanged -- no real evidence was fused this poll.
            return PositionEstimate(
                x=prior.x,
                z=prior.z,
                covariance=prior_covariance,
                as_of_sim=t_sim,
                fused_at_sim=prior.fused_at_sim,
                fused_covariance=prior.fused_covariance,
                anchor=prior.anchor,
            )
        fused = PositionEstimate(
            x=fused_x,
            z=fused_z,
            covariance=fused_covariance,
            as_of_sim=t_sim,
            fused_at_sim=t_sim,
            fused_covariance=fused_covariance,
            anchor=look_anchor,
        )
    prior_inflated_covariance = prior_covariance if prior is not None else None
    return _apply_floor(
        fused,
        uncertainty,
        kappa_view_at_fuse,
        prior_optic_class,
        prior_inflated_covariance,
    )


def clamp_to_detection_envelope(
    fused: PositionEstimate,
    prior: PositionEstimate | None,
    observer: GeoPosition,
    max_range_m: float,
    growth_rate_mps: float = GATE_GROWTH_RATE_MPS,
) -> PositionEstimate:
    """Module docstring's defect 2: a believed position farther from
    `observer` than `max_range_m` (the perception channel's own physical
    detection-range cap -- see the caller for which constant) is not a
    belief, it is a fusion artifact, since nothing could have been detected
    from `observer` out that far to produce it. Called by `belief.contacts.
    Contact.record`/`from_percept` immediately after `fold_position`, never
    from inside that function (see module docstring for why the envelope is
    a caller concern, not something `fold_position` itself should need to
    know).

    Passes `fused` through unchanged when it already satisfies the
    envelope -- the overwhelming common case, and a true no-op for it.
    Otherwise **holds the prior** (unchanged mean, covariance freshly
    inflated for elapsed motion since `prior.fused_at_sim` -- module
    docstring's "Hold-recovery timing" invariant, `_inflated_since_last_
    fuse` -- never compounded from `prior.covariance`, and never treated as
    a fuse: `fused_at_sim`/`fused_covariance` carry straight through from
    `prior` unchanged) rather than clamping the mean onto the envelope
    boundary or discarding the look outright: an implied position beyond
    the envelope is evidence the fusion (or an upstream look) went wrong,
    not evidence of where the target actually is, so the most recent
    trustworthy belief is what should survive. When there is no `prior` to
    hold (a founding look, `prior is None`), `fused` is passed through
    unchanged -- it is a single reported look, not a fusion artifact, and
    is this function's true no-op case by construction: in production the
    channel's own gate has already range-capped it before it could ever
    reach here, and this module has no fusion result of its own to prefer
    over it. (Test fixtures that construct an `Observation` directly, out
    of reach of any channel's own gate, may still carry an out-of-envelope
    founding range deliberately, to exercise downstream logic unrelated to
    this defect -- clamping here would silently rewrite the very state
    those tests are checking.)

    `growth_rate_mps` (`plans/group-contact-identity/plan.md` Stage 2a) is
    threaded through to the same `_inflated_since_last_fuse` call
    `fold_position` makes, so a held envelope violation inflates by the
    same per-class rate the fuse it is holding in place of would have
    used. Defaults to `GATE_GROWTH_RATE_MPS`, unchanged for every
    pre-Stage-2 caller.

    **Incidentally also holds `prior` when `fused`'s mean is non-finite**,
    because `range_m(...) <= max_range_m` is `False` for NaN in Python
    (any comparison with NaN is `False`, never raises) -- but this is not
    a guard this function was written to provide, nothing relies on it by
    design, and `clamp_fold_displacement` (the next clamp in the same call
    chain) does not get the same accidental protection and carries its own
    explicit `math.isfinite` guard instead (`plans/bounded-fold-
    displacement/security-review.md`). Do not read this fall-through as a
    documented NaN contract for this function."""
    if prior is None:
        return fused
    target = GeoPosition(x=fused.x, z=fused.z, alt_m=observer.alt_m)
    if range_m(observer, target) <= max_range_m:
        return fused
    return PositionEstimate(
        x=prior.x,
        z=prior.z,
        covariance=_inflated_since_last_fuse(prior, fused.as_of_sim, growth_rate_mps),
        as_of_sim=fused.as_of_sim,
        fused_at_sim=prior.fused_at_sim,
        fused_covariance=prior.fused_covariance,
        anchor=prior.anchor,
    )


def clamp_fold_displacement(
    fused: PositionEstimate,
    prior: PositionEstimate | None,
    max_displacement_m: float | None,
) -> PositionEstimate:
    """Module docstring's third caller-invoked clamp: cap how far `fused`'s
    mean may have moved from `prior`'s, structurally parallel to
    `clamp_to_detection_envelope` above but a distance bound rather than a
    range-from-observer one. `belief.contacts.Contact.record` calls this
    last, after `clamp_to_detection_envelope`, so the bound is measured
    against the position actually adopted -- when the envelope clamp has
    already held the prior mean, the displacement here is `0.0` and this
    clamp is a no-op by construction.

    **Identity when there is nothing to bound against**: `max_displacement_m
    is None` (the ordinary, non-fold case -- every pre-`BL-B58` call site)
    or `prior is None` (a founding look has no prior mean to have moved
    from, mirroring `clamp_to_detection_envelope`'s own founding-look
    no-op). Neither branch constructs a new `PositionEstimate`; both return
    `fused` itself unchanged.

    **Non-finite `fused` mean or non-finite `max_displacement_m`, by
    design, not by accident**: a NaN/inf `fused.x`/`fused.z`, *or* a
    NaN/inf `max_displacement_m` itself, holds the prior mean rather than
    being bounded -- this function has no `observer`/`growth_rate_mps` of
    its own to re-inflate `prior.covariance` with (unlike
    `clamp_to_detection_envelope`'s hold branch above), so holding the
    prior's mean and covariance exactly as given, while still bumping
    `as_of_sim` to the current poll (see below), is the whole of this
    guard. Without it, the displacement/scale arithmetic below would
    write the non-finite value into the adopted mean permanently -- `NaN
    * 0.0 == NaN` in IEEE 754, so the ordinary clamp branch does not
    sanitise it, and `max_displacement_m` reaches the identical
    corruption through `scale` (`max_displacement_m / displacement_m`)
    rather than through `dx`. This function's one real caller
    (`belief.contacts.Contact.record`) never reaches either case today:
    the `fused`-mean case, because it always calls
    `clamp_to_detection_envelope` first and that call's own `range_m(...)
    <= max_range_m` comparison happens to be `False` for NaN; the
    `max_displacement_m` case, because the one real caller resolves the
    bound from a table lookup (`contact_growth_rate_mps` ->
    `plausible_speed_mps`) that cannot currently produce NaN/inf --
    security review, `plans/bounded-fold-displacement/security-review.md`,
    and the reviewer's own follow-up round that found the second gap --
    but that is caller ordering, not a property of this function, so the
    guard is explicit here rather than borrowed. (The `max_displacement_m
    is None` check above already returns first, so testing
    `math.isfinite(max_displacement_m)` next is safe -- it is never
    reached with `None`.)

    **The held result still bumps `as_of_sim` to `fused.as_of_sim`**,
    matching `clamp_to_detection_envelope`'s own hold branch and the
    module docstring's "Hold-recovery timing" invariant (`as_of_sim`
    "bumped on every poll including a hold, since the belief is still
    the best current answer even when unchanged") -- this guard
    constructs a fresh `PositionEstimate` rather than returning `prior`
    by bare identity, carrying `prior`'s `x`/`z`/`covariance` and
    `fused_at_sim`/`fused_covariance` through unchanged (no re-fuse
    happened) but advancing `as_of_sim`, which needs no growth rate and
    is already a parameter in scope.

    Otherwise: if `fused`'s mean already sits within `max_displacement_m`
    of `prior`'s, `fused` passes through unchanged (the common case -- an
    ordinary fold whose own displacement never approached the bound).
    Past the bound, the mean is scaled back along the straight line from
    `prior` to `fused` so its displacement equals exactly
    `max_displacement_m` (`0.0` pulls it back onto `prior`'s own point,
    the `plans/bounded-fold-displacement/plan.md` §2c zero-elapsed case --
    physically correct: no elapsed time, no plausible travel). **The
    clamped remainder keeps `fused`'s own covariance and `fused_at_sim`**,
    never `prior`'s (that plan's §2c, measured: holding the prior's
    covariance leaves `fused_at_sim` behind, which only grows the *next*
    fold's own bound) -- this is still a genuine fuse, with only its mean
    repositioned, not a hold."""
    if max_displacement_m is None or prior is None:
        return fused
    if (
        not math.isfinite(fused.x)
        or not math.isfinite(fused.z)
        or not math.isfinite(max_displacement_m)
    ):
        return PositionEstimate(
            x=prior.x,
            z=prior.z,
            covariance=prior.covariance,
            as_of_sim=fused.as_of_sim,
            fused_at_sim=prior.fused_at_sim,
            fused_covariance=prior.fused_covariance,
            anchor=fused.anchor,
        )
    dx = fused.x - prior.x
    dz = fused.z - prior.z
    displacement_m = math.hypot(dx, dz)
    if displacement_m <= max_displacement_m:
        return fused
    scale = max_displacement_m / displacement_m if displacement_m > 0.0 else 0.0
    return PositionEstimate(
        x=prior.x + dx * scale,
        z=prior.z + dz * scale,
        covariance=fused.covariance,
        as_of_sim=fused.as_of_sim,
        fused_at_sim=fused.fused_at_sim,
        fused_covariance=fused.fused_covariance,
        anchor=fused.anchor,
    )


def _apply_floor(
    estimate: PositionEstimate,
    look_uncertainty: PositionUncertainty,
    kappa_view: float = 1.0,
    prior_optic_class: str | None = None,
    prior_inflated_covariance: Covariance2D | None = None,
) -> PositionEstimate:
    """Only ever called on a freshly founded or genuinely fused `estimate`
    (`fold_position`'s two non-hold branches), where `as_of_sim ==
    fused_at_sim` and `covariance == fused_covariance` hold by construction
    -- so the floored covariance becomes both the reported `covariance` and
    the new `fused_covariance` base, keeping that invariant intact.

    **`BL-B108` Stage 2: the down-range half of the floor is `kappa_view
    * stable_share() * sigma_down_m` of this look, not a flat fraction.**
    The cross-range half is unchanged (`SYSTEMATIC_BIAS_FRACTION`, bearing
    out of scope). `kappa_view` is the *geometric* correlation `correlated_
    innovation` just computed for this fuse (`1.0` for a founding look,
    which is trivially "the same geometry" as itself) -- the plan's own
    "it binds only at the same geometry": once ownship has turned or
    closed enough that `kappa_view` has decayed, the down-range floor
    decays with it, so the estimate is allowed to keep tightening via
    genuine triangulation rather than being held at a floor calibrated for
    a geometry that no longer applies.

    **`prior_optic_class` (`BL-B108` amendment, "Belief side")**: the
    floor is additionally scaled by `min(1, k_anchor / k_look)`, where
    `k_anchor`/`k_look` are `perception.estimation.range_sigma_scale_
    for_optic` of `prior_optic_class` (the fuse's prior anchor, before
    this fuse replaced it -- `None` for a founding look, treated as
    "no discount") and `look_uncertainty.optic_class` respectively.
    Staring through a worse optic (`k_look` larger) after a better one
    (`k_anchor` smaller) can never push the floor below the better
    optic's own stable floor; a better optic's own look is never
    discounted (the ratio is capped at `1.0`, never negative or amplified
    above it).

    **`prior_inflated_covariance` (`BL-B110` Stage 0a, Decision 7 (a))**: a
    second, independent cap on the floor -- never above `None` for a
    founding look (there is no prior to be less certain than). When given
    (the fuse's own elapsed-motion-inflated prior, `_inflated_since_last_
    fuse`, the same value the fuse just used as its measurement-update
    input), `floor_trace` is additionally capped at that covariance's own
    `trace()`. This answers the question `prior_optic_class` above does
    not: that scaling only ever discounts the *current look's own* floor
    relative to a better anchor optic, so a naked-eye fuse after a tight
    binocular fix still floors at the naked eye's own (scaled-down) share
    -- which can still be looser than the belief already was a moment
    earlier. The cap here instead compares against the belief's own prior
    state directly: a new look may never leave the belief less certain
    than it was just before the look, full stop. It is not a second
    anchor -- the prior's own optic-scaled floor is not read here, only
    its covariance trace, and growth from elapsed time at
    `plausible_speed_mps` still applies before this call ever sees the
    prior (it is baked into `prior_inflated_covariance` itself), so a
    *moving* class still loosens between looks."""
    k_look = range_sigma_scale_for_optic(look_uncertainty.optic_class)
    optic_factor = 1.0
    if prior_optic_class is not None and k_look > 0.0:
        k_anchor = range_sigma_scale_for_optic(prior_optic_class)
        optic_factor = min(1.0, k_anchor / k_look)
    down_floor_m = (
        kappa_view * stable_share() * look_uncertainty.sigma_down_m * optic_factor
    )
    floor_trace = (SYSTEMATIC_BIAS_FRACTION * look_uncertainty.sigma_cross_m) ** 2 + (
        down_floor_m**2
    )
    if prior_inflated_covariance is not None:
        floor_trace = min(floor_trace, prior_inflated_covariance.trace())
    current_trace = estimate.covariance.trace()
    if current_trace >= floor_trace:
        return estimate
    if current_trace <= 0.0:
        # Degenerate covariance (should not arise from any real declared
        # sigma) -- floor to an isotropic split rather than divide by zero.
        floored = Covariance2D(xx=floor_trace / 2.0, zz=floor_trace / 2.0, xz=0.0)
    else:
        floored = estimate.covariance.scaled(floor_trace / current_trace)
    return PositionEstimate(
        x=estimate.x,
        z=estimate.z,
        covariance=floored,
        as_of_sim=estimate.as_of_sim,
        fused_at_sim=estimate.fused_at_sim,
        fused_covariance=floored,
        anchor=estimate.anchor,
    )
