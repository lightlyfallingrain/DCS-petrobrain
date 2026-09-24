"""Tests for `perception.estimation` -- the error model and perturbation
`plans/precise-position-belief/plan.md` Stages 1-2 introduced.

**Gap found while verifying this plan's own test-impact list** (Stage 3's
task brief): the plan's Stage 2 "Verify" section calls for a
`test_estimation.py` pinning determinism, unbiasedness, and the sigma
ratio, and `tests/test_naked_eye_source.py` (around its "Bearing/range
quantisation ... was deleted" comment) already refers to this file by name
as though it existed -- but no such file was ever created by the Stage 1-2
work this session recovered. Added here rather than left as a silent gap,
since Stage 3/4's gate and fusion math both depend on this module's
guarantees (determinism, an unbiased mean, the stated sigma ratio) holding."""

from __future__ import annotations

import math
import statistics

from perception.estimation import (
    BEARING_SIGMA_DEG,
    RANGE_FRACTIONAL_SIGMA,
    SYSTEMATIC_BIAS_FRACTION,
    naked_eye_sigma_m,
    perturbed_bearing_range,
    systematic_bias_m,
)


def test_naked_eye_sigma_scales_with_range() -> None:
    sigma_cross_1k, sigma_down_1k = naked_eye_sigma_m(1000.0)
    sigma_cross_3k, sigma_down_3k = naked_eye_sigma_m(3000.0)

    assert math.isclose(sigma_cross_1k, math.radians(BEARING_SIGMA_DEG) * 1000.0)
    assert math.isclose(sigma_down_1k, RANGE_FRACTIONAL_SIGMA * 1000.0)
    # Both scale linearly with range -- tripling range triples both sigmas.
    assert math.isclose(sigma_cross_3k, sigma_cross_1k * 3.0)
    assert math.isclose(sigma_down_3k, sigma_down_1k * 3.0)


def test_down_range_sigma_dominates_cross_range_sigma() -> None:
    """The plan's central claim: a human points at a thing far better than
    he judges its distance -- cross-range error must be several times
    *smaller* than down-range error, the reverse of the old (deleted)
    quantisation-derived model."""
    sigma_cross_m, sigma_down_m = naked_eye_sigma_m(3000.0)

    assert sigma_cross_m < sigma_down_m
    assert sigma_down_m / sigma_cross_m > 3.0


def test_perturbed_bearing_range_is_deterministic_per_observation_id() -> None:
    sigma_cross_m, sigma_down_m = naked_eye_sigma_m(1000.0)
    kwargs = {
        "object_id": 1,
        "true_bearing_deg": 45.0,
        "true_range_m": 1000.0,
        "sigma_cross_m": sigma_cross_m,
        "sigma_down_m": sigma_down_m,
    }

    first = perturbed_bearing_range(observation_id="OBS_1", **kwargs)  # type: ignore[arg-type]
    second = perturbed_bearing_range(observation_id="OBS_1", **kwargs)  # type: ignore[arg-type]
    different = perturbed_bearing_range(observation_id="OBS_2", **kwargs)  # type: ignore[arg-type]

    assert first == second
    assert first != different


def test_perturbed_bearing_range_mean_offset_is_unbiased() -> None:
    """Unlike the deleted `_quantise_range_m` (which snapped to the
    bucket's *upper bound*, biasing every range long), the perturbation's
    mean offset over many independent looks *at many different objects*
    must be close to zero -- both for bearing and for range. Varying
    `object_id` alongside `observation_id` is deliberate: a *single*
    object's own never-redrawn systematic bias is not zero-mean by design
    (see `test_systematic_bias_never_redrawn_for_the_same_object_id`) --
    unbiasedness is a population-level property of the per-look draw plus
    the per-object draw together, not a promise about any one object."""
    sigma_cross_m, sigma_down_m = naked_eye_sigma_m(1000.0)
    true_bearing_deg = 30.0
    true_range_m = 1000.0

    bearing_offsets = []
    range_offsets = []
    for i in range(3000):
        bearing_deg, range_m = perturbed_bearing_range(
            observation_id=f"OBS_{i}",
            object_id=i,
            true_bearing_deg=true_bearing_deg,
            true_range_m=true_range_m,
            sigma_cross_m=sigma_cross_m,
            sigma_down_m=sigma_down_m,
        )
        bearing_offsets.append(bearing_deg - true_bearing_deg)
        range_offsets.append(range_m - true_range_m)

    # Total per-axis standard deviation includes both the per-look and the
    # per-object terms: sigma * sqrt(1 + SYSTEMATIC_BIAS_FRACTION ** 2).
    # The mean over 3000 independent draws should land within a handful of
    # standard errors (sigma / sqrt(n)) of zero -- a generous multiple
    # (10x) avoids test flakiness while still catching a real directional
    # bias the size of the old bucket-upper-bound snap.
    total_sigma_down = sigma_down_m * math.sqrt(1.0 + SYSTEMATIC_BIAS_FRACTION**2)
    total_sigma_cross = sigma_cross_m * math.sqrt(1.0 + SYSTEMATIC_BIAS_FRACTION**2)
    standard_error_down = total_sigma_down / math.sqrt(len(range_offsets))
    standard_error_cross_m = total_sigma_cross / math.sqrt(len(bearing_offsets))

    mean_range_offset = statistics.fmean(range_offsets)
    assert abs(mean_range_offset) < 10.0 * standard_error_down

    mean_bearing_offset_m = (
        math.radians(statistics.fmean(bearing_offsets)) * true_range_m
    )
    assert abs(mean_bearing_offset_m) < 10.0 * standard_error_cross_m


def test_perturbed_range_is_floored_at_zero() -> None:
    _bearing_deg, range_m = perturbed_bearing_range(
        observation_id="OBS_CLOSE",
        object_id=1,
        true_bearing_deg=0.0,
        true_range_m=1.0,
        sigma_cross_m=100.0,
        sigma_down_m=10000.0,
    )

    assert range_m >= 0.0


def test_systematic_bias_never_redrawn_for_the_same_object_id() -> None:
    sigma_cross_m, sigma_down_m = naked_eye_sigma_m(1000.0)

    first = systematic_bias_m(42, sigma_cross_m, sigma_down_m)
    second = systematic_bias_m(42, sigma_cross_m, sigma_down_m)
    other_object = systematic_bias_m(43, sigma_cross_m, sigma_down_m)

    assert first == second
    assert first != other_object


def test_systematic_bias_scaled_to_declared_fraction_of_single_look_sigma() -> None:
    """Not a statistical claim -- a single deterministic draw is scaled
    linearly by `SYSTEMATIC_BIAS_FRACTION`, so doubling the input sigma
    must exactly double the resulting bias."""
    cross_1x, down_1x = systematic_bias_m(7, 100.0, 200.0)
    cross_2x, down_2x = systematic_bias_m(7, 200.0, 400.0)

    assert math.isclose(cross_2x, cross_1x * 2.0)
    assert math.isclose(down_2x, down_1x * 2.0)
