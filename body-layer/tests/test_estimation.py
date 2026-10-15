"""Tests for `perception.estimation` -- the error model and perturbation
`plans/precise-position-belief/plan.md` Stages 1-2 introduced, extended by
`BL-B64` Stage 1b (`plans/9k113-sight/plan.md` §14, `naked_eye_sigma_m`
renamed to `look_sigma_m` and given an `optic` parameter).

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
    RELATIVE_DIRECTION_SIGMA_DEG,
    SIGHT_NARROW_RANGE_SIGMA_SCALE,
    SIGHT_WIDE_RANGE_SIGMA_SCALE,
    SYSTEMATIC_BIAS_FRACTION,
    look_sigma_m,
    perturbed_bearing_range,
    perturbed_relative_direction,
    systematic_bias_m,
)
from perception.optics import (
    BINOCULAR_OPTIC,
    SIGHT_NARROW_OPTIC,
    SIGHT_WIDE_OPTIC,
    UNAIDED_OPTIC,
)


def test_naked_eye_sigma_scales_with_range() -> None:
    sigma_cross_1k, sigma_down_1k = look_sigma_m(1000.0, UNAIDED_OPTIC)
    sigma_cross_3k, sigma_down_3k = look_sigma_m(3000.0, UNAIDED_OPTIC)

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
    sigma_cross_m, sigma_down_m = look_sigma_m(3000.0, UNAIDED_OPTIC)

    assert sigma_cross_m < sigma_down_m
    assert sigma_down_m / sigma_cross_m > 3.0


def test_binocular_optic_gets_the_same_sigma_as_the_naked_eye() -> None:
    """`BL-B64` Stage 1b fixes the 9K113's own two optics only --
    `BINOCULAR_OPTIC` is deliberately untouched (module docstring), so a
    binocular look must produce *exactly* the naked-eye-grade sigma, not a
    new value, until a sourced figure exists for it."""
    naked_eye = look_sigma_m(3000.0, UNAIDED_OPTIC)
    binocular = look_sigma_m(3000.0, BINOCULAR_OPTIC)

    assert binocular == naked_eye


def test_sight_optics_get_a_smaller_down_range_sigma_than_the_naked_eye() -> None:
    """Direction §11/§14: the stadiametric aid makes the sight's range
    estimate better than the naked eye's, though still not exact -- the
    down-range sigma must shrink for both sight optics, and narrow (finer
    stadiametric resolution) must shrink it further than wide."""
    _cross_eye, down_eye = look_sigma_m(3000.0, UNAIDED_OPTIC)
    _cross_wide, down_wide = look_sigma_m(3000.0, SIGHT_WIDE_OPTIC)
    _cross_narrow, down_narrow = look_sigma_m(3000.0, SIGHT_NARROW_OPTIC)

    assert down_wide == RANGE_FRACTIONAL_SIGMA * SIGHT_WIDE_RANGE_SIGMA_SCALE * 3000.0
    assert (
        down_narrow == RANGE_FRACTIONAL_SIGMA * SIGHT_NARROW_RANGE_SIGMA_SCALE * 3000.0
    )
    assert down_narrow < down_wide < down_eye


def test_sight_cross_range_sigma_is_derived_from_the_fov_ratio() -> None:
    """Direction §11: "a narrower field is a tighter bearing read" -- the
    cross-range scale is the active optic's own `fov_half_angle_deg`
    divided by `BINOCULAR_OPTIC`'s (the regime `BEARING_SIGMA_DEG` is
    already calibrated against), not an independent judgement constant.
    Narrow's field (3.0 deg) is tighter than binoculars' (4.25 deg), so
    narrow's cross-range sigma must be smaller than a binocular look's;
    wide's field (5.75 deg) is wider than binoculars', so wide's must be
    larger."""
    cross_binocular, _down_binocular = look_sigma_m(3000.0, BINOCULAR_OPTIC)
    cross_wide, _down_wide = look_sigma_m(3000.0, SIGHT_WIDE_OPTIC)
    cross_narrow, _down_narrow = look_sigma_m(3000.0, SIGHT_NARROW_OPTIC)

    assert cross_narrow < cross_binocular < cross_wide


def test_perturbed_bearing_range_is_deterministic_per_observation_id() -> None:
    sigma_cross_m, sigma_down_m = look_sigma_m(1000.0, UNAIDED_OPTIC)
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
    sigma_cross_m, sigma_down_m = look_sigma_m(1000.0, UNAIDED_OPTIC)
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
    sigma_cross_m, sigma_down_m = look_sigma_m(1000.0, UNAIDED_OPTIC)

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


# -- plans/attack-run/plan.md Decision 16 item 5 / Decision 11 REVISED ---


def test_relative_direction_sigma_is_zero_as_settled_by_the_user() -> None:
    """Settled by §20, 2026-10-14 -- *"Relative direction while he's
    looking at it -> exact."*"""
    assert RELATIVE_DIRECTION_SIGMA_DEG == 0.0


def test_perturbed_relative_direction_is_identity_at_zero_sigma() -> None:
    """At `RELATIVE_DIRECTION_SIGMA_DEG == 0.0` the perturbation must be a
    true identity function, not merely a draw scaled to zero -- so §18's
    "exact while the look holds" is a parameter, not a structural
    property that happens to read zero (Decision 11 REVISED)."""
    forward_m, right_m, up_m = perturbed_relative_direction(
        observation_id="OBS_1", forward_m=950.0, right_m=120.0, up_m=-40.0
    )

    assert forward_m == 950.0
    assert right_m == 120.0
    assert up_m == -40.0


def test_perturbed_relative_direction_identity_holds_for_degenerate_offset() -> None:
    """A zero-length offset must not raise (the division-by-zero case the
    angular reconstruction would otherwise hit) -- the identity short-
    circuit at `RELATIVE_DIRECTION_SIGMA_DEG == 0.0` skips the trig
    entirely, so this is safe regardless."""
    forward_m, right_m, up_m = perturbed_relative_direction(
        observation_id="OBS_1", forward_m=0.0, right_m=0.0, up_m=0.0
    )

    assert (forward_m, right_m, up_m) == (0.0, 0.0, 0.0)
