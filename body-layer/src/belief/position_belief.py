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
`logger._DEFAULT_POLL_INTERVAL_S = 1.0`, ~934s at 0.05s), even though the
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

from perception.estimation import SYSTEMATIC_BIAS_FRACTION
from perception.geometry import GeoPosition, bearing_deg, range_m
from perception.source import PositionUncertainty

#: How fast a contact could plausibly have moved since it was last
#: observed, metres/second -- a generic ground-vehicle order-of-magnitude
#: figure (72 km/h), not derived from any specific unit's real top speed.
#: Placeholder, revisit once real sessions show whether contacts are gated
#: too tightly or too loosely. Moved here from `belief.association_over_
#: time` by `plans/precise-position-belief/plan.md` Stage 3 -- see module
#: docstring for why the direction of the move avoids an import cycle.
GATE_GROWTH_RATE_MPS: Final[float] = 20.0

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


def _inflated_since_last_fuse(prior: PositionEstimate, t_sim: float) -> Covariance2D:
    """`prior.fused_covariance`, inflated for elapsed motion since `prior.
    fused_at_sim` -- **always the last genuinely fused update, never the
    last poll** (module docstring's "Hold-recovery timing" invariant).
    Every place this module needs "the prior's covariance, brought up to
    date" -- fusing a new look against it, or holding it forward another
    poll -- goes through this one function, so inflation is computed fresh
    from the true base every time rather than compounding an
    already-inflated `prior.covariance` a second time across a chain of
    holds."""
    elapsed_s = max(0.0, t_sim - prior.fused_at_sim)
    return prior.fused_covariance.inflated(elapsed_s)


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
    fused_covariance`); they diverge only across one or more holds."""

    x: float
    z: float
    covariance: Covariance2D
    as_of_sim: float
    fused_at_sim: float
    fused_covariance: Covariance2D

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
    t_sim: float,
) -> PositionEstimate:
    """A single look's own `PositionEstimate`, with no prior to fuse
    against -- `fold_position`'s founding case, factored out so a founding
    contact and a re-observed one build their look covariance identically."""
    covariance = covariance_from_uncertainty(uncertainty, look_bearing_deg)
    return PositionEstimate(
        x=x,
        z=z,
        covariance=covariance,
        as_of_sim=t_sim,
        fused_at_sim=t_sim,
        fused_covariance=covariance,
    )


def fold_position(
    prior: PositionEstimate | None,
    *,
    x: float,
    z: float,
    uncertainty: PositionUncertainty,
    look_bearing_deg: float,
    t_sim: float,
) -> PositionEstimate:
    """Fuse one look `(x, z, uncertainty, look_bearing_deg)` into `prior`
    (`None` for a founding percept) via the information-form covariance
    update -- see module docstring. The result is floored so it can never
    claim more precision than `SYSTEMATIC_BIAS_FRACTION` of this look's own
    single-look sigma would allow (the plan's "the uncertainty floor
    follows for free" -- the systematic bias never averages out, so the
    fused estimate must never claim to have averaged it away).

    **Ill-conditioning guard** (module docstring, defect 1): when `prior` is
    not `None`, the ordinary information-form fused mean is computed first,
    then checked against `FUSION_SANITY_SIGMA` -- if it does not sit within
    that many sigma of *either* input, judged against that input's own
    individual covariance, the fusion is treated as ill-conditioned and
    discarded: the look is not fused into the mean or covariance at all,
    only elapsed-time inflation is applied, exactly the "hold" outcome
    `clamp_to_detection_envelope` uses for the other defect."""
    look_covariance = covariance_from_uncertainty(uncertainty, look_bearing_deg)
    if prior is None:
        fused = PositionEstimate(
            x=x,
            z=z,
            covariance=look_covariance,
            as_of_sim=t_sim,
            fused_at_sim=t_sim,
            fused_covariance=look_covariance,
        )
    else:
        prior_covariance = _inflated_since_last_fuse(prior, t_sim)
        info_prior = prior_covariance.inverse()
        info_look = look_covariance.inverse()
        info_sum = info_prior + info_look
        prior_iv_x, prior_iv_z = info_prior.apply(prior.x, prior.z)
        look_iv_x, look_iv_z = info_look.apply(x, z)
        fused_covariance = info_sum.inverse()
        fused_x, fused_z = fused_covariance.apply(
            prior_iv_x + look_iv_x, prior_iv_z + look_iv_z
        )
        prior_residual_sigma_sq = prior_covariance.mahalanobis_squared(
            fused_x - prior.x, fused_z - prior.z
        )
        look_residual_sigma_sq = look_covariance.mahalanobis_squared(
            fused_x - x, fused_z - z
        )
        if (
            min(prior_residual_sigma_sq, look_residual_sigma_sq)
            > FUSION_SANITY_SIGMA**2
        ):
            # Hold: elapsed-time inflation still applies (`prior_covariance`
            # above already is that fresh, non-compounding inflation), but
            # `fused_at_sim`/`fused_covariance` carry straight through
            # unchanged -- no real evidence was fused this poll.
            return PositionEstimate(
                x=prior.x,
                z=prior.z,
                covariance=prior_covariance,
                as_of_sim=t_sim,
                fused_at_sim=prior.fused_at_sim,
                fused_covariance=prior.fused_covariance,
            )
        fused = PositionEstimate(
            x=fused_x,
            z=fused_z,
            covariance=fused_covariance,
            as_of_sim=t_sim,
            fused_at_sim=t_sim,
            fused_covariance=fused_covariance,
        )
    return _apply_floor(fused, uncertainty)


def clamp_to_detection_envelope(
    fused: PositionEstimate,
    prior: PositionEstimate | None,
    observer: GeoPosition,
    max_range_m: float,
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
    those tests are checking.)"""
    if prior is None:
        return fused
    target = GeoPosition(x=fused.x, z=fused.z, alt_m=observer.alt_m)
    if range_m(observer, target) <= max_range_m:
        return fused
    return PositionEstimate(
        x=prior.x,
        z=prior.z,
        covariance=_inflated_since_last_fuse(prior, fused.as_of_sim),
        as_of_sim=fused.as_of_sim,
        fused_at_sim=prior.fused_at_sim,
        fused_covariance=prior.fused_covariance,
    )


def _apply_floor(
    estimate: PositionEstimate, look_uncertainty: PositionUncertainty
) -> PositionEstimate:
    """Only ever called on a freshly founded or genuinely fused `estimate`
    (`fold_position`'s two non-hold branches), where `as_of_sim ==
    fused_at_sim` and `covariance == fused_covariance` hold by construction
    -- so the floored covariance becomes both the reported `covariance` and
    the new `fused_covariance` base, keeping that invariant intact."""
    floor_trace = (SYSTEMATIC_BIAS_FRACTION * look_uncertainty.sigma_cross_m) ** 2 + (
        SYSTEMATIC_BIAS_FRACTION * look_uncertainty.sigma_down_m
    ) ** 2
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
    )
