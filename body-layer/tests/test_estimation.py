"""Tests for `perception.estimation` -- the error model and perturbation
`plans/precise-position-belief/plan.md` Stages 1-2 introduced, extended by
`BL-B64` Stage 1b, and restructured by `plans/relative-distance-grouping/
plan.md` (`BL-B108`) Stage 1.

**`BL-B108`: the exact-offset pins on the down-range axis are gone,
replaced by statistical property tests** (plan escalation item 1, user
answer "ok", 2026-10-31) -- the down-range draw is now a correlated
three-part model (module docstring), not a single deterministic-per-
observation-id offset, so a pinned exact value would pin one arbitrary
realisation of a random field rather than a property of the model. Bearing
(cross-range) keeps its own per-observation, per-object-bias structure
unchanged, so its tests stay pinned where that is still the right shape."""

from __future__ import annotations

import ast
import inspect
import math
import statistics

import perception.estimation as estimation_module
from perception.estimation import (
    BEARING_SIGMA_DEG,
    BINOCULAR_RANGE_SIGMA_SCALE,
    RANGE_FRACTIONAL_SIGMA,
    RANGE_LOOK_SHARE,
    RANGE_RELATIVE_SHARE,
    RELATIVE_DIRECTION_SIGMA_DEG,
    SIGHT_NARROW_RANGE_SIGMA_SCALE,
    SIGHT_WIDE_RANGE_SIGMA_SCALE,
    look_sigma_m,
    perturbed_bearing_range,
    perturbed_relative_direction,
    stable_down_sigma_m,
    stable_range_correlation,
    surface_range_estimate,
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


def test_binocular_optic_gets_its_own_declared_range_scale() -> None:
    """`BL-B108` Q3 (user, 2026-10-31): binoculars now get a tighter
    absolute down-range sigma than naked eye, `BINOCULAR_RANGE_SIGMA_
    SCALE` (0.7) of it -- closing the live asymmetry `BL-B55`'s roadmap
    entry once flagged. Cross-range is unaffected (binoculars are not a
    sight optic, so `_SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC` does not apply
    to it)."""
    cross_eye, down_eye = look_sigma_m(3000.0, UNAIDED_OPTIC)
    cross_binocular, down_binocular = look_sigma_m(3000.0, BINOCULAR_OPTIC)

    assert math.isclose(down_binocular, down_eye * BINOCULAR_RANGE_SIGMA_SCALE)
    assert down_binocular < down_eye
    assert math.isclose(cross_binocular, cross_eye)


def test_sight_optics_get_a_smaller_down_range_sigma_than_the_naked_eye() -> None:
    """Direction §11/§14: the stadiametric aid makes the sight's range
    estimate better than the naked eye's, though still not exact -- the
    down-range sigma must shrink for both sight optics, and narrow (finer
    stadiametric resolution) must shrink it further than wide, and both
    tighter than binoculars (`BL-B108`)."""
    _cross_eye, down_eye = look_sigma_m(3000.0, UNAIDED_OPTIC)
    _cross_bino, down_bino = look_sigma_m(3000.0, BINOCULAR_OPTIC)
    _cross_wide, down_wide = look_sigma_m(3000.0, SIGHT_WIDE_OPTIC)
    _cross_narrow, down_narrow = look_sigma_m(3000.0, SIGHT_NARROW_OPTIC)

    assert down_wide == RANGE_FRACTIONAL_SIGMA * SIGHT_WIDE_RANGE_SIGMA_SCALE * 3000.0
    assert (
        down_narrow == RANGE_FRACTIONAL_SIGMA * SIGHT_NARROW_RANGE_SIGMA_SCALE * 3000.0
    )
    assert down_narrow < down_wide < down_bino < down_eye


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
        "optic_class": "unaided",
        "poll_key": 5.0,
    }

    first = perturbed_bearing_range(observation_id="OBS_1", **kwargs)  # type: ignore[arg-type]
    second = perturbed_bearing_range(observation_id="OBS_1", **kwargs)  # type: ignore[arg-type]
    different = perturbed_bearing_range(observation_id="OBS_2", **kwargs)  # type: ignore[arg-type]

    assert first == second
    # Bearing differs (per-observation draw); range does not -- the
    # down-range draw is keyed by (optic_class, poll_key), not by
    # observation_id, so two observations in the same poll share it
    # (module docstring: "shared within that poll").
    assert first[0] != different[0]
    assert first[1] == different[1]


def test_perturbed_range_is_floored_at_zero() -> None:
    _bearing_deg, range_m = perturbed_bearing_range(
        observation_id="OBS_CLOSE",
        object_id=1,
        true_bearing_deg=0.0,
        true_range_m=1.0,
        sigma_cross_m=100.0,
        sigma_down_m=10000.0,
        optic_class="unaided",
        poll_key=1.0,
    )

    assert range_m >= 0.0


def test_systematic_bias_never_redrawn_for_the_same_object_id() -> None:
    """`BL-B108`: the down-range half of the per-object systematic bias is
    retired (module docstring) -- `systematic_bias_m` now returns a single
    cross-range (bearing) float."""
    sigma_cross_m, _sigma_down_m = look_sigma_m(1000.0, UNAIDED_OPTIC)

    first = systematic_bias_m(42, sigma_cross_m)
    second = systematic_bias_m(42, sigma_cross_m)
    other_object = systematic_bias_m(43, sigma_cross_m)

    assert first == second
    assert first != other_object


def test_systematic_bias_scaled_to_declared_fraction_of_single_look_sigma() -> None:
    """Not a statistical claim -- a single deterministic draw is scaled
    linearly by `SYSTEMATIC_BIAS_FRACTION`, so doubling the input sigma
    must exactly double the resulting bias."""
    cross_1x = systematic_bias_m(7, 100.0)
    cross_2x = systematic_bias_m(7, 200.0)

    assert math.isclose(cross_2x, cross_1x * 2.0)


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


# -- BL-B108 Stage 1: the correlated three-part down-range model --------


def test_absolute_down_range_rms_matches_fractional_sigma() -> None:
    """E4: "the spoken range keeps today's size of error" -- the RMS of
    the perturbed range's error, across many independent geometries and
    objects, must land within the plan's own declared +/-10% of the
    declared `sigma_down_m`."""
    errors_over_sigma = []
    for i in range(1200):
        bearing_deg = (i * 37.0) % 360.0
        true_range_m = 500.0 + (i * 53.0) % 9500.0
        sigma_cross_m, sigma_down_m = look_sigma_m(true_range_m, UNAIDED_OPTIC)
        _bearing, range_m = perturbed_bearing_range(
            observation_id=f"OBS_{i}",
            object_id=i,
            true_bearing_deg=bearing_deg,
            true_range_m=true_range_m,
            sigma_cross_m=sigma_cross_m,
            sigma_down_m=sigma_down_m,
            optic_class="unaided",
            poll_key=float(i),
        )
        errors_over_sigma.append((range_m - true_range_m) / sigma_down_m)

    rms = math.sqrt(statistics.fmean(x * x for x in errors_over_sigma))
    assert 0.9 <= rms <= 1.1


def test_repeat_look_from_same_geometry_spread_matches_look_share() -> None:
    """E4: "repeated looks from the same place give the same number, not a
    value that jitters between looks" -- the look-to-look standard
    deviation of repeated draws at one fixed (bearing, range, optic)
    across many different poll keys must be close to `RANGE_LOOK_SHARE *
    sigma_down_m`, the `a` term's own declared share -- far smaller than
    `sigma_down_m` itself."""
    true_range_m = 4000.0
    sigma_cross_m, sigma_down_m = look_sigma_m(true_range_m, UNAIDED_OPTIC)
    ranges = [
        perturbed_bearing_range(
            observation_id=f"OBS_{i}",
            object_id=1,
            true_bearing_deg=10.0,
            true_range_m=true_range_m,
            sigma_cross_m=sigma_cross_m,
            sigma_down_m=sigma_down_m,
            optic_class="unaided",
            poll_key=float(i),
        )[1]
        for i in range(400)
    ]
    spread = statistics.pstdev(ranges)
    expected = RANGE_LOOK_SHARE * sigma_down_m
    # Generous band (the finite random-Fourier-feature field's own z_look
    # term is an exact per-poll draw with no approximation, so this is
    # tighter than the field-realisation properties below).
    assert 0.5 * expected <= spread <= 1.8 * expected
    assert spread < 0.5 * sigma_down_m


def test_two_things_at_the_same_distance_in_one_look_differ_far_less_than_absolute() -> (
    None
):
    """E1/E3 in combination: two different objects at *about* the same
    distance on one bearing (range ratio close to 1.0) must differ by far
    less than the absolute single-look error -- this is what keeps one
    real group's members from being split by range noise."""
    true_range_m = 3000.0
    sigma_cross_m, sigma_down_m = look_sigma_m(true_range_m, UNAIDED_OPTIC)
    diffs = []
    for i in range(300):
        bearing_deg = (i * 11.0) % 20.0  # roughly one bearing
        r1, r2 = (
            perturbed_bearing_range(
                observation_id=f"OBS_{i}_{suffix}",
                object_id=object_id,
                true_bearing_deg=bearing_deg,
                true_range_m=true_range_m,
                sigma_cross_m=sigma_cross_m,
                sigma_down_m=sigma_down_m,
                optic_class="unaided",
                poll_key=float(i),
            )[1]
            for suffix, object_id in (("a", 100 + i), ("b", 200 + i))
        )
        diffs.append(r1 - r2)
    diff_rms = math.sqrt(statistics.fmean(d * d for d in diffs))
    assert diff_rms < sigma_down_m  # far tighter than the absolute error


def test_two_things_at_a_large_range_ratio_differ_about_as_much_as_absolute() -> None:
    """E1/E2's clear case: two things at a range ratio well past both
    decorrelation ratios must differ by *about* as much as two
    independent absolute errors -- the mechanism that keeps two real
    groups kilometres apart from reading as one."""
    sigma_cross_m = 100.0
    near_m, far_m = 2000.0, 8000.0  # ratio 4.0, past both decorrelation ratios
    _c1, sigma_near_m = look_sigma_m(near_m, UNAIDED_OPTIC)
    _c2, sigma_far_m = look_sigma_m(far_m, UNAIDED_OPTIC)
    diffs = []
    for i in range(300):
        bearing_deg = (i * 11.0) % 20.0
        r_near = perturbed_bearing_range(
            observation_id=f"OBS_near_{i}",
            object_id=100 + i,
            true_bearing_deg=bearing_deg,
            true_range_m=near_m,
            sigma_cross_m=sigma_cross_m,
            sigma_down_m=sigma_near_m,
            optic_class="unaided",
            poll_key=float(i),
        )[1]
        r_far = perturbed_bearing_range(
            observation_id=f"OBS_far_{i}",
            object_id=200 + i,
            true_bearing_deg=bearing_deg,
            true_range_m=far_m,
            sigma_cross_m=sigma_cross_m,
            sigma_down_m=sigma_far_m,
            optic_class="unaided",
            poll_key=float(i),
        )[1]
        diffs.append((r_near - near_m) - (r_far - far_m))
    diff_rms = math.sqrt(statistics.fmean(d * d for d in diffs))
    # The shared `z_look` term (weight `a`) never decorrelates by
    # construction (module docstring: shared by every cluster in a poll),
    # so even full view/near decorrelation cannot reach the full
    # independent-error bound `hypot(sigma_near, sigma_far)` -- only
    # `sqrt(1 - a^2)` of it. The finite random-Fourier-feature
    # approximation (`_FIELD_FOURIER_K`) adds its own slack on top, so
    # this checks the *direction* (clearly decorrelated, not the near-
    # identical-distance case's tight coupling) rather than a tight
    # fraction of the theoretical bound.
    independent_bound = math.hypot(sigma_near_m, sigma_far_m)
    assert diff_rms > 0.3 * independent_bound


def test_stable_range_correlation_falls_to_about_one_over_e_at_the_stated_rotation() -> (
    None
):
    """`stable_range_correlation`'s closed form: holding range ratio at
    1.0, the view correlation must fall to `1/e` at exactly `RANGE_
    DECORRELATION_BEARING_DEG` of bearing separation -- this is the
    deterministic kernel belief reads, not a field realisation, so this
    is an exact algebraic check, not a statistical one."""
    rho_view, _rho_near = stable_range_correlation(
        estimation_module.RANGE_DECORRELATION_BEARING_DEG, 1.0, True
    )
    assert math.isclose(rho_view, math.exp(-1.0), rel_tol=1e-6)


def test_stable_range_correlation_falls_to_about_one_over_e_at_the_stated_range_ratio() -> (
    None
):
    rho_view, _rho_near = stable_range_correlation(
        0.0, estimation_module.RANGE_DECORRELATION_RANGE_RATIO, True
    )
    assert math.isclose(rho_view, math.exp(-1.0), rel_tol=1e-6)

    _rho_view, rho_near = stable_range_correlation(
        0.0, estimation_module.RANGE_NEAR_DECORRELATION_RANGE_RATIO, True
    )
    assert math.isclose(rho_near, math.exp(-1.0), rel_tol=1e-6)


def test_stable_range_correlation_is_zero_for_a_different_optic() -> None:
    """A different optic class is an independent look by construction
    (module docstring) -- both correlations collapse to zero regardless
    of geometry."""
    rho_view, rho_near = stable_range_correlation(0.0, 1.0, False)
    assert rho_view == 0.0
    assert rho_near == 0.0


def test_stable_range_correlation_is_one_at_identical_geometry() -> None:
    rho_view, rho_near = stable_range_correlation(0.0, 1.0, True)
    assert math.isclose(rho_view, 1.0)
    assert math.isclose(rho_near, 1.0)


def test_stable_down_sigma_m_is_the_s_and_f_parts_combined() -> None:
    sigma_down_m = 700.0
    s = math.sqrt(max(0.0, 1.0 - RANGE_RELATIVE_SHARE**2 - RANGE_LOOK_SHARE**2))
    expected = math.sqrt(RANGE_RELATIVE_SHARE**2 + s**2) * sigma_down_m
    assert math.isclose(stable_down_sigma_m(sigma_down_m), expected)
    # Strictly less than the total sigma -- it excludes the `a` share.
    assert stable_down_sigma_m(sigma_down_m) < sigma_down_m


# -- plans/bl-b104-ground-contacts-on-ground/plan.md Stage 3, restructured
# by BL-B108 Stage 1 --------------------------------------------------


def test_surface_range_estimate_cue_b_absent_at_level_look_matches_cue_a() -> None:
    """`height_above_unit_m == 0.0` (a perfectly level look) must disable
    cue B entirely and reproduce cue A's own down-range draw exactly --
    the same `field_domain="range"` draw `perturbed_bearing_range`'s own
    down component uses."""
    true_range_m = 2000.0
    sigma_cross_m, sigma_down_m = look_sigma_m(true_range_m, UNAIDED_OPTIC)
    _bearing, expected_range_m = perturbed_bearing_range(
        observation_id="OBS_1",
        object_id=42,
        true_bearing_deg=0.0,
        true_range_m=true_range_m,
        sigma_cross_m=sigma_cross_m,
        sigma_down_m=sigma_down_m,
        optic_class="unaided",
        poll_key=7.0,
    )

    range_m, result_sigma_down_m = surface_range_estimate(
        true_distance_m=true_range_m,
        height_above_unit_m=0.0,
        optic=UNAIDED_OPTIC,
        poll_key=7.0,
    )

    assert math.isclose(range_m, expected_range_m)
    assert math.isclose(result_sigma_down_m, sigma_down_m)


def test_surface_range_estimate_cue_b_absent_when_wrong_sign() -> None:
    """A unit below the observer (`height_above_unit_m > 0`) whose
    perceived depression is pushed to or past level/upward by noise must
    fall back to cue A alone, never a nonsensical negative-distance cue
    B -- explore-notes Q2's "range then ... from unit angular size"."""
    true_range_m = 5000.0
    height_above_unit_m = 1.0  # true depression ~0.011 deg, easily flipped
    sigma_cross_m, sigma_down_m = look_sigma_m(true_range_m, UNAIDED_OPTIC)
    found_absent = False
    for i in range(80):
        poll_key = float(i)
        range_m, _sigma_down_m = surface_range_estimate(
            true_distance_m=true_range_m,
            height_above_unit_m=height_above_unit_m,
            optic=UNAIDED_OPTIC,
            poll_key=poll_key,
        )
        _bearing, cue_a_range_m = perturbed_bearing_range(
            observation_id="OBS_X",
            object_id=1,
            true_bearing_deg=0.0,
            true_range_m=true_range_m,
            sigma_cross_m=sigma_cross_m,
            sigma_down_m=sigma_down_m,
            optic_class="unaided",
            poll_key=poll_key,
        )
        if math.isclose(range_m, cue_a_range_m):
            found_absent = True
            break
    assert found_absent


def test_surface_range_estimate_is_deterministic() -> None:
    args = {
        "true_distance_m": 3000.0,
        "height_above_unit_m": 300.0,
        "optic": UNAIDED_OPTIC,
        "poll_key": 7.0,
    }
    assert surface_range_estimate(**args) == surface_range_estimate(**args)  # type: ignore[arg-type]


def test_surface_range_estimate_never_returns_negative_or_nan() -> None:
    for agl_m in (50.0, 150.0, 300.0, 500.0, 800.0):
        for distance_m in (500.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0):
            for i in range(20):
                range_m, sigma_down_m = surface_range_estimate(
                    true_distance_m=distance_m,
                    height_above_unit_m=agl_m,
                    optic=UNAIDED_OPTIC,
                    poll_key=float(i),
                )
                assert range_m >= 0.0
                assert not math.isnan(range_m)
                assert sigma_down_m >= 0.0


def test_surface_range_estimate_unit_above_observer_uses_upward_ray() -> None:
    """A SAM on a ridge above the helicopter (`height_above_unit_m < 0`,
    alignment finding 5's vignette) must resolve through cue B the same
    way a unit below does, via the signed convention -- not treated as
    "wrong sign" just because the number is negative."""
    range_m, sigma_down_m = surface_range_estimate(
        true_distance_m=3000.0,
        height_above_unit_m=-200.0,
        optic=UNAIDED_OPTIC,
        poll_key=1.0,
    )
    assert range_m > 0.0
    assert sigma_down_m > 0.0


def test_surface_range_estimate_firms_up_at_steep_geometry() -> None:
    """At a close, steep geometry the fused sigma must be tighter than
    cue A alone (E3's "firms up close") -- 300 m AGL / 1 km, depression
    ~17 deg."""
    true_range_m = 1000.0
    height_above_unit_m = 300.0
    _unused_range_m, sigma_a_m = look_sigma_m(true_range_m, UNAIDED_OPTIC)
    _unused_range_m2, fused_sigma_down_m = surface_range_estimate(
        true_distance_m=true_range_m,
        height_above_unit_m=height_above_unit_m,
        optic=UNAIDED_OPTIC,
        poll_key=1.0,
    )
    assert fused_sigma_down_m < sigma_a_m


def test_surface_range_estimate_never_worse_than_cue_a_alone() -> None:
    """E3's "no worse than today" as a property of the fusion arithmetic:
    the fused sigma must never exceed cue A's own sigma, at any geometry
    in the Mi-24 envelope."""
    for agl_m in (50.0, 150.0, 300.0, 500.0, 800.0):
        for distance_m in (500.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0):
            _unused_range_m, sigma_a_m = look_sigma_m(distance_m, UNAIDED_OPTIC)
            _unused_range_m2, fused_sigma_down_m = surface_range_estimate(
                true_distance_m=distance_m,
                height_above_unit_m=agl_m,
                optic=UNAIDED_OPTIC,
                poll_key=1.0,
            )
            assert fused_sigma_down_m <= sigma_a_m * 1.0001  # fp slack


def test_surface_range_estimate_narrow_sight_tighter_than_naked_eye() -> None:
    _unused_range_m, naked_eye_sigma_m = surface_range_estimate(
        true_distance_m=2000.0,
        height_above_unit_m=300.0,
        optic=UNAIDED_OPTIC,
        poll_key=1.0,
    )
    _unused_range_m2, narrow_sigma_m = surface_range_estimate(
        true_distance_m=2000.0,
        height_above_unit_m=300.0,
        optic=SIGHT_NARROW_OPTIC,
        poll_key=1.0,
    )
    assert narrow_sigma_m < naked_eye_sigma_m


def test_surface_range_estimate_never_references_relative_direction_channel() -> None:
    """The no-omniscience fence, made testable (E7): the perceived
    depression must never be derived from `RelativeDirection`/
    `RELATIVE_DIRECTION_SIGMA_DEG` -- grep the function's own *executable
    code*, excluding its docstring (which legitimately mentions both names
    in prose, explaining the fence itself) and excluding the module as a
    whole (which legitimately defines both for `perturbed_relative_
    direction`, a different function)."""
    tree = ast.parse(inspect.getsource(estimation_module.surface_range_estimate))
    (func,) = tree.body
    assert isinstance(func, ast.FunctionDef)
    body_without_docstring = func.body[1:] if ast.get_docstring(func) else func.body
    code = "\n".join(ast.unparse(stmt) for stmt in body_without_docstring)
    assert "relative_direction" not in code.lower()
    assert "RELATIVE_DIRECTION_SIGMA_DEG" not in code


def test_surface_range_estimate_cue_b_uses_an_independent_field_from_cue_a() -> None:
    """`BL-B108`: cue B's depression draw must be keyed on its own seed
    domain (`field_domain="depression"`), not share cue A's realisation --
    across many poll keys at a fixed steep geometry (cue B present
    throughout), the fused result must not just track cue A's own draw one
    for one."""
    true_range_m = 2000.0
    height_above_unit_m = 300.0
    _c, sigma_a_m = look_sigma_m(true_range_m, UNAIDED_OPTIC)
    fused_values = []
    cue_a_values = []
    for i in range(60):
        poll_key = float(i)
        fused_range_m, _s = surface_range_estimate(
            true_distance_m=true_range_m,
            height_above_unit_m=height_above_unit_m,
            optic=UNAIDED_OPTIC,
            poll_key=poll_key,
        )
        _bearing, cue_a_range_m = perturbed_bearing_range(
            observation_id="OBS_X",
            object_id=1,
            true_bearing_deg=0.0,
            true_range_m=true_range_m,
            sigma_cross_m=100.0,
            sigma_down_m=sigma_a_m,
            optic_class="unaided",
            poll_key=poll_key,
        )
        fused_values.append(fused_range_m)
        cue_a_values.append(cue_a_range_m)
    # If cue B merely echoed cue A, every pair would match exactly (cue B
    # absent) or move in lockstep; across 60 independent poll keys with
    # cue B genuinely present (steep geometry), at least some must differ
    # meaningfully.
    distinct_deltas = {
        round(f - a, 3) for f, a in zip(fused_values, cue_a_values, strict=True)
    }
    assert len(distinct_deltas) > 5


def test_surface_range_estimate_converges_to_a_stable_value_not_truth() -> None:
    """Repeated looks from the *same* geometry (poll key varying only the
    small `a`-weighted term) must converge toward the geometry's own
    stable draw, not toward truth (E4: dwell does not make range exact) --
    the `BL-B108` replacement for the retired per-object bias's own
    convergence test."""
    true_distance_m = 2000.0
    height_above_unit_m = 300.0
    samples = [
        surface_range_estimate(
            true_distance_m=true_distance_m,
            height_above_unit_m=height_above_unit_m,
            optic=UNAIDED_OPTIC,
            poll_key=float(i),
        )[0]
        for i in range(200)
    ]
    mean_range_m = statistics.fmean(samples)
    assert not math.isclose(mean_range_m, true_distance_m, abs_tol=1.0)
    # And the repeated-look spread must be small relative to the absolute
    # sigma -- dwell narrows the reported *spread*, never the bias away.
    _c, sigma_a_m = look_sigma_m(true_distance_m, UNAIDED_OPTIC)
    assert statistics.pstdev(samples) < 0.5 * sigma_a_m
