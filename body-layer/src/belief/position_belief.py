"""2x2 covariance primitives and the fused position estimate -- `plans/
precise-position-belief/plan.md`.

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
itself produces."""

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

#: Minimum fraction of a *guard* against a degenerate (near-singular)
#: covariance when inverting -- should never arise from any real declared
#: sigma, but a defensive floor is cheaper than a `ZeroDivisionError` deep
#: in a fold.
_MIN_DETERMINANT: Final[float] = 1e-9


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
        determinant = max(determinant, _MIN_DETERMINANT)
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
    references -- see module docstring."""

    x: float
    z: float
    covariance: Covariance2D
    as_of_sim: float

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
    return PositionEstimate(
        x=x,
        z=z,
        covariance=covariance_from_uncertainty(uncertainty, look_bearing_deg),
        as_of_sim=t_sim,
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
    fused estimate must never claim to have averaged it away)."""
    look_covariance = covariance_from_uncertainty(uncertainty, look_bearing_deg)
    if prior is None:
        fused = PositionEstimate(x=x, z=z, covariance=look_covariance, as_of_sim=t_sim)
    else:
        elapsed_s = max(0.0, t_sim - prior.as_of_sim)
        prior_covariance = prior.covariance.inflated(elapsed_s)
        info_prior = prior_covariance.inverse()
        info_look = look_covariance.inverse()
        info_sum = info_prior + info_look
        prior_iv_x, prior_iv_z = info_prior.apply(prior.x, prior.z)
        look_iv_x, look_iv_z = info_look.apply(x, z)
        fused_covariance = info_sum.inverse()
        fused_x, fused_z = fused_covariance.apply(
            prior_iv_x + look_iv_x, prior_iv_z + look_iv_z
        )
        fused = PositionEstimate(
            x=fused_x, z=fused_z, covariance=fused_covariance, as_of_sim=t_sim
        )
    return _apply_floor(fused, uncertainty)


def _apply_floor(
    estimate: PositionEstimate, look_uncertainty: PositionUncertainty
) -> PositionEstimate:
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
        x=estimate.x, z=estimate.z, covariance=floored, as_of_sim=estimate.as_of_sim
    )
