"""Tests for `belief.position_belief` -- the 2x2 covariance primitives and
fused position estimate `plans/precise-position-belief/plan.md` Stages 3-4
consume.

**Gap found while verifying this plan's own test-impact list**: this
module was fully written (and used, from Stage 3 onward) with no dedicated
test file of its own -- see `tests/test_estimation.py`'s own docstring for
the sibling gap. Added here since Stage 4's convergence claims (`Contact.
position` strictly tightens across looks, floors at the systematic-bias
fraction, never converges exactly on truth) rest on this module's own
arithmetic being right."""

from __future__ import annotations

import math

import pytest

from belief.position_belief import (
    FUSION_SANITY_SIGMA,
    GATE_GROWTH_RATE_MPS,
    Covariance2D,
    PositionEstimate,
    clamp_to_detection_envelope,
    covariance_from_uncertainty,
    estimate_from_look,
    fold_position,
)
from perception.geometry import GeoPosition
from perception.source import PositionUncertainty


def test_covariance_from_uncertainty_at_bearing_zero_is_axis_aligned() -> None:
    """At `bearing_deg=0.0` (pointing along +x), the down-range axis is x
    and the cross-range axis is z -- `xx` should hold the down variance,
    `zz` the cross variance, with no correlation."""
    uncertainty = PositionUncertainty(sigma_cross_m=50.0, sigma_down_m=500.0)

    covariance = covariance_from_uncertainty(uncertainty, look_bearing_deg=0.0)

    assert math.isclose(covariance.xx, 500.0**2)
    assert math.isclose(covariance.zz, 50.0**2)
    assert math.isclose(covariance.xz, 0.0, abs_tol=1e-9)


def test_covariance_from_uncertainty_trace_is_bearing_invariant() -> None:
    """Rotation preserves trace -- the sum of the two variances (and
    therefore `PositionEstimate.radius_m`) must be the same regardless of
    which way the look is pointed."""
    uncertainty = PositionUncertainty(sigma_cross_m=50.0, sigma_down_m=500.0)
    expected_trace = 50.0**2 + 500.0**2

    for bearing in (0.0, 37.0, 90.0, 145.0, 270.0):
        covariance = covariance_from_uncertainty(uncertainty, look_bearing_deg=bearing)
        assert math.isclose(covariance.trace(), expected_trace, rel_tol=1e-9)


def test_covariance_from_uncertainty_isotropic_case_has_no_correlation() -> None:
    """Equal sigmas on both axes must produce an isotropic covariance
    (zero off-diagonal, equal diagonal) at any bearing -- there is no
    orientation to a circle."""
    uncertainty = PositionUncertainty(sigma_cross_m=100.0, sigma_down_m=100.0)

    for bearing in (0.0, 45.0, 123.0):
        covariance = covariance_from_uncertainty(uncertainty, look_bearing_deg=bearing)
        assert math.isclose(covariance.xx, covariance.zz)
        assert math.isclose(covariance.xz, 0.0, abs_tol=1e-9)


def test_covariance2d_inverse_round_trips() -> None:
    covariance = Covariance2D(xx=90000.0, zz=2500.0, xz=1200.0)

    identity_x, identity_z = covariance.apply(*covariance.inverse().apply(1.0, 0.0))
    assert math.isclose(identity_x, 1.0, rel_tol=1e-6)
    assert math.isclose(identity_z, 0.0, abs_tol=1e-6)


def test_covariance2d_inflated_grows_isotropically_with_elapsed_time() -> None:
    covariance = Covariance2D(xx=100.0, zz=400.0, xz=50.0)

    inflated = covariance.inflated(10.0, growth_rate_mps=20.0)

    growth_var = (20.0 * 10.0) ** 2
    assert math.isclose(inflated.xx, 100.0 + growth_var)
    assert math.isclose(inflated.zz, 400.0 + growth_var)
    # The off-diagonal (correlation) term is untouched by isotropic growth.
    assert math.isclose(inflated.xz, 50.0)


def test_covariance2d_inflated_defaults_to_module_growth_rate() -> None:
    covariance = Covariance2D(xx=0.0, zz=0.0, xz=0.0)

    default_growth = covariance.inflated(5.0)
    explicit_growth = covariance.inflated(5.0, growth_rate_mps=GATE_GROWTH_RATE_MPS)

    assert default_growth == explicit_growth


def test_covariance2d_mahalanobis_squared_isotropic_matches_scaled_distance() -> None:
    covariance = Covariance2D(xx=100.0, zz=100.0, xz=0.0)

    # For an isotropic covariance with variance v, mahalanobis^2 of an
    # offset (dx, dz) is exactly (dx^2 + dz^2) / v.
    assert math.isclose(covariance.mahalanobis_squared(10.0, 0.0), 100.0 / 100.0)
    assert math.isclose(covariance.mahalanobis_squared(0.0, 20.0), 400.0 / 100.0)


def test_estimate_from_look_has_no_prior_to_fuse_against() -> None:
    uncertainty = PositionUncertainty(sigma_cross_m=50.0, sigma_down_m=500.0)

    estimate = estimate_from_look(
        x=1000.0, z=0.0, uncertainty=uncertainty, look_bearing_deg=0.0, t_sim=0.0
    )

    assert estimate.x == 1000.0
    assert estimate.z == 0.0
    assert estimate.as_of_sim == 0.0
    assert math.isclose(estimate.covariance.xx, 500.0**2)


def test_fold_position_founding_call_matches_estimate_from_look() -> None:
    """`fold_position(None, ...)` is the founding case, factored out so a
    founding contact and a re-observed one build their first covariance
    identically -- the module docstring's own claim, pinned directly."""
    uncertainty = PositionUncertainty(sigma_cross_m=50.0, sigma_down_m=500.0)
    kwargs = {
        "x": 1000.0,
        "z": 0.0,
        "uncertainty": uncertainty,
        "look_bearing_deg": 0.0,
        "t_sim": 0.0,
    }

    founded = fold_position(None, **kwargs)  # type: ignore[arg-type]
    direct = estimate_from_look(**kwargs)  # type: ignore[arg-type]

    assert founded.x == direct.x
    assert founded.z == direct.z
    assert founded.covariance == direct.covariance


def test_fold_position_from_two_crossing_looks_triangulates_tighter_than_either() -> (
    None
):
    """Two looks at the same true position from two different, roughly
    perpendicular bearings must fuse to an estimate whose own uncertainty
    (`radius_m`) is strictly smaller than either look's own -- real
    triangulation, the plan's central claim about why fusion is covariance
    fusion and not a running mean."""
    uncertainty = PositionUncertainty(sigma_cross_m=50.0, sigma_down_m=500.0)

    first = fold_position(
        None,
        x=1000.0,
        z=0.0,
        uncertainty=uncertainty,
        look_bearing_deg=0.0,
        t_sim=0.0,
    )
    fused = fold_position(
        first,
        x=1000.0,
        z=0.0,
        uncertainty=uncertainty,
        look_bearing_deg=90.0,
        t_sim=0.0,
    )

    assert fused.radius_m() < first.radius_m()


def test_fold_position_converges_toward_truth_plus_systematic_bias_not_truth() -> None:
    """Many repeated looks at the *same* true position, from slightly
    different bearings (so the covariance keeps tightening rather than
    staying degenerate along one axis), must converge the fused mean
    toward a *fixed offset* from truth (the systematic bias a real
    `perception.estimation.perturbed_bearing_range` caller would supply),
    never exactly onto truth -- pinned here directly against `fold_
    position`'s own arithmetic, independent of `perception.estimation`."""
    true_x, true_z = 1000.0, 0.0
    bias_x, bias_z = 40.0, -15.0  # a fixed, never-redrawn systematic offset
    uncertainty = PositionUncertainty(sigma_cross_m=50.0, sigma_down_m=500.0)

    estimate = None
    for i in range(30):
        bearing = 30.0 + i * 4.0  # sweep bearings so both axes tighten
        estimate = fold_position(
            estimate,
            x=true_x + bias_x,
            z=true_z + bias_z,
            uncertainty=uncertainty,
            look_bearing_deg=bearing,
            t_sim=float(i),
        )

    assert estimate is not None
    assert math.isclose(estimate.x, true_x + bias_x, abs_tol=1.0)
    assert math.isclose(estimate.z, true_z + bias_z, abs_tol=1.0)
    # Emphatically not converged onto bare truth.
    assert abs(estimate.x - true_x) > 10.0


def test_fold_position_never_claims_more_precision_than_the_floor() -> None:
    """However many looks are fused, `radius_m()` must never drop below
    `SYSTEMATIC_BIAS_FRACTION` of a single look's own sigma -- the "the
    uncertainty floor follows for free" claim, pinned directly by fusing
    far more looks than would be needed to reach it otherwise."""
    uncertainty = PositionUncertainty(sigma_cross_m=50.0, sigma_down_m=500.0)
    floor = math.sqrt((0.4 * 50.0) ** 2 + (0.4 * 500.0) ** 2)

    estimate = None
    for i in range(200):
        bearing = float(i % 360)
        estimate = fold_position(
            estimate,
            x=1000.0,
            z=0.0,
            uncertainty=uncertainty,
            look_bearing_deg=bearing,
            t_sim=float(i),
        )

    assert estimate is not None
    assert estimate.radius_m() >= floor - 1e-6


def test_bearing_uncertainty_deg_reads_only_the_cross_range_component() -> None:
    """`bearing_uncertainty_deg` is what `optic_policy.look_target_for`
    (Stage 5) needs: how wide a sweep must be to cover the belief's own
    *cross-range* uncertainty, not the down-range component. A highly
    elongated estimate (wide down-range, tight cross-range) observed from
    directly down its own down-range axis must therefore report a small
    bearing uncertainty."""
    from perception.geometry import GeoPosition

    estimate = estimate_from_look(
        x=1000.0,
        z=0.0,
        uncertainty=PositionUncertainty(sigma_cross_m=10.0, sigma_down_m=1000.0),
        look_bearing_deg=0.0,  # elongated along x
        t_sim=0.0,
    )
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)  # looking along +x too

    bearing_uncertainty_deg = estimate.bearing_uncertainty_deg(observer)

    # sigma_cross=10 at range=1000 -> ~0.57 degrees; certainly under 2.
    assert bearing_uncertainty_deg < 2.0
    assert bearing_uncertainty_deg > 0.0


def test_bearing_uncertainty_deg_at_zero_range_is_zero() -> None:
    from perception.geometry import GeoPosition

    estimate = estimate_from_look(
        x=0.0,
        z=0.0,
        uncertainty=PositionUncertainty(sigma_cross_m=10.0, sigma_down_m=10.0),
        look_bearing_deg=0.0,
        t_sim=0.0,
    )
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)

    assert estimate.bearing_uncertainty_deg(observer) == 0.0


def test_range_uncertainty_m_reads_only_the_down_range_component() -> None:
    """`range_uncertainty_m` (`plans/watch-reporting/plan.md` Decision
    5a-i) is `bearing_uncertainty_deg`'s exact mirror: a highly elongated
    estimate (wide down-range, tight cross-range) observed from directly
    down its own down-range axis must report a *large* range uncertainty --
    the opposite of the cross-range test above."""
    from perception.geometry import GeoPosition

    estimate = estimate_from_look(
        x=1000.0,
        z=0.0,
        uncertainty=PositionUncertainty(sigma_cross_m=10.0, sigma_down_m=1000.0),
        look_bearing_deg=0.0,  # elongated along x
        t_sim=0.0,
    )
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)  # looking along +x too

    range_uncertainty_m = estimate.range_uncertainty_m(observer)

    assert range_uncertainty_m > 500.0


def test_range_uncertainty_m_small_for_a_tight_down_range_estimate() -> None:
    from perception.geometry import GeoPosition

    estimate = estimate_from_look(
        x=1000.0,
        z=0.0,
        uncertainty=PositionUncertainty(sigma_cross_m=1000.0, sigma_down_m=10.0),
        look_bearing_deg=0.0,
        t_sim=0.0,
    )
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)

    range_uncertainty_m = estimate.range_uncertainty_m(observer)

    assert range_uncertainty_m < 50.0


def test_radius_m_is_sqrt_of_trace() -> None:
    estimate = estimate_from_look(
        x=0.0,
        z=0.0,
        uncertainty=PositionUncertainty(sigma_cross_m=30.0, sigma_down_m=40.0),
        look_bearing_deg=0.0,
        t_sim=0.0,
    )

    assert estimate.radius_m() == pytest.approx(math.sqrt(30.0**2 + 40.0**2))


# --- position-belief runaway (plans/position-belief-runaway/debug.md) -----


def test_fold_position_near_parallel_disagreeing_looks_holds_prior_not_runaway() -> (
    None
):
    """The live defect's own numeric reproduction. Two naked-eye-shaped
    looks (tight cross-range, loose down-range) 5 degrees apart, whose
    implied positions disagree by 350m cross / 2000m down-range: before
    the fix, `fold_position` put the fused mean at
    `(-5308.1, 3790.7)` -- range ~6523m from the origin, outside both
    inputs' own ranges (3000m and ~5012m). The fix must hold the prior
    (unchanged mean) instead."""
    uncertainty = PositionUncertainty(sigma_cross_m=60.0, sigma_down_m=800.0)

    prior = fold_position(
        None, x=0.0, z=3000.0, uncertainty=uncertainty, look_bearing_deg=0.0, t_sim=0.0
    )
    fused = fold_position(
        prior,
        x=350.0,
        z=5000.0,
        uncertainty=uncertainty,
        look_bearing_deg=5.0,
        t_sim=1.0,
    )

    assert fused.x == prior.x
    assert fused.z == prior.z
    fused_range = math.hypot(fused.x, fused.z)
    # Before the fix this was ~6523m -- well outside either input's own
    # range (3000m, ~5012m).
    assert fused_range < 5100.0


def test_fold_position_perpendicular_looks_still_triangulate_unchanged() -> None:
    """The well-conditioned case must be bit-for-bit unaffected by the
    guard -- pins the exact pre-fix numbers so a future change to the
    guard's threshold cannot silently start holding this case too."""
    uncertainty = PositionUncertainty(sigma_cross_m=60.0, sigma_down_m=800.0)

    prior = fold_position(
        None, x=0.0, z=3000.0, uncertainty=uncertainty, look_bearing_deg=0.0, t_sim=0.0
    )
    fused = fold_position(
        prior,
        x=3000.0,
        z=3000.0,
        uncertainty=uncertainty,
        look_bearing_deg=90.0,
        t_sim=1.0,
    )

    assert math.isclose(fused.x, 2983.15625, rel_tol=1e-4)
    assert math.isclose(fused.z, 3000.0, rel_tol=1e-4)
    # Real triangulation -- tighter than either single look's own radius.
    assert fused.radius_m() < prior.radius_m()


def test_fold_position_repeated_identical_look_still_tightens() -> None:
    """The failure mode a bearing-only guard would have introduced (caught
    live by `tests/test_optic_policy.py`'s pre-existing calibration test):
    fusing the *same* look, from the *same* bearing, repeatedly, must keep
    tightening the estimate -- ordinary repeated-measurement averaging, not
    ill-conditioned triangulation, even though every pair of looks here is
    maximally near-parallel (bearing separation zero). Uses the same
    (60, 800) sigma pair as this file's other new tests -- a different
    pair, (157.08, 510.0), was tried first and exposed a separate,
    pre-existing latent bug in `Covariance2D.inverse`'s `_MIN_DETERMINANT`
    floor (calibrated for covariance-scale determinants, ~1e9, but an
    information-matrix determinant after only one doubling can legitimately
    be ~1e-10, below the floor, silently corrupting the result) -- reported
    in `plans/position-belief-runaway/debug.md` as a separate finding, out
    of this defect's scope, not fixed here."""
    uncertainty = PositionUncertainty(sigma_cross_m=60.0, sigma_down_m=800.0)

    estimate = None
    for _ in range(5):
        estimate = fold_position(
            estimate,
            x=3000.0,
            z=0.0,
            uncertainty=uncertainty,
            look_bearing_deg=0.0,
            t_sim=0.0,
        )
    assert estimate is not None
    assert estimate.x == pytest.approx(3000.0)
    assert estimate.z == pytest.approx(0.0)
    single_look_radius = estimate_from_look(
        x=3000.0, z=0.0, uncertainty=uncertainty, look_bearing_deg=0.0, t_sim=0.0
    ).radius_m()
    assert estimate.radius_m() < single_look_radius


def test_fold_position_moderate_near_parallel_residual_still_fuses() -> None:
    """A small, realistic disagreement (100m) at a near-parallel bearing
    must still fuse (not hold) -- the guard should only fire on the
    genuinely degenerate, large-residual case, not on ordinary measurement
    noise between consecutive polls."""
    uncertainty = PositionUncertainty(sigma_cross_m=60.0, sigma_down_m=800.0)

    prior = fold_position(
        None, x=0.0, z=3000.0, uncertainty=uncertainty, look_bearing_deg=0.0, t_sim=0.0
    )
    fused = fold_position(
        prior,
        x=30.0,
        z=3100.0,
        uncertainty=uncertainty,
        look_bearing_deg=5.0,
        t_sim=1.0,
    )

    assert (fused.x, fused.z) != (prior.x, prior.z)
    assert math.hypot(fused.x, fused.z) < 3300.0


def test_clamp_to_detection_envelope_is_a_no_op_within_range() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    fused = estimate_from_look(
        x=3000.0,
        z=0.0,
        uncertainty=PositionUncertainty(sigma_cross_m=60.0, sigma_down_m=800.0),
        look_bearing_deg=0.0,
        t_sim=0.0,
    )

    result = clamp_to_detection_envelope(fused, None, observer, max_range_m=10000.0)

    assert result is fused


def test_clamp_to_detection_envelope_holds_prior_when_fused_exceeds_cap() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    covariance = covariance_from_uncertainty(
        PositionUncertainty(sigma_cross_m=60.0, sigma_down_m=800.0), 0.0
    )
    prior = PositionEstimate(x=3000.0, z=0.0, covariance=covariance, as_of_sim=0.0)
    fused = PositionEstimate(x=15000.0, z=0.0, covariance=covariance, as_of_sim=1.0)

    result = clamp_to_detection_envelope(fused, prior, observer, max_range_m=10000.0)

    assert result.x == prior.x
    assert result.z == prior.z
    assert result.as_of_sim == fused.as_of_sim
    # Elapsed-motion inflation still applies even though the look itself
    # is rejected.
    assert result.covariance.trace() > prior.covariance.trace()


def test_clamp_to_detection_envelope_founding_look_passes_through_unchanged() -> None:
    """No `prior` to hold -- a founding look is a single reported look, not
    a fusion artifact, and this function's true no-op case (module
    docstring: in production the channel's own gate has already
    range-capped it before it could reach here; test fixtures that
    deliberately construct an out-of-envelope founding look for unrelated
    reasons must not have it silently rewritten)."""
    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    fused = estimate_from_look(
        x=15000.0,
        z=0.0,
        uncertainty=PositionUncertainty(sigma_cross_m=60.0, sigma_down_m=800.0),
        look_bearing_deg=0.0,
        t_sim=0.0,
    )

    result = clamp_to_detection_envelope(fused, None, observer, max_range_m=10000.0)

    assert result is fused


def test_fusion_sanity_sigma_is_positive_and_generous() -> None:
    """Documents the chosen threshold's own sanity, not just its value --
    a regression here is a deliberate policy change, not an accident."""
    assert FUSION_SANITY_SIGMA >= 3.0
