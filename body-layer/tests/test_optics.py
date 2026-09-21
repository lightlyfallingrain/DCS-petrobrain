"""Tests for `perception.optics.within_optic_fov` and the two named optics
(`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`) -- `plans/detection-cones-slice1/
plan.md`.

Pure mechanism tests, mirroring `test_cockpit_mask.py`'s posture: exercised
against small synthetic `Optic` instances, not the shipped table, so a
future change to `BINOCULAR_OPTIC`'s own numbers can't break the mechanism
tests here. `test_visibility.py`'s own `test_default_optic_is_naked_eye`
is where `check_visibility`'s default-optic choice is pinned -- this file
only tests the two `Optic` values and the FOV mechanism themselves.
"""

from __future__ import annotations

import pytest

from perception.optics import (
    BINOCULAR_OPTIC,
    UNAIDED_OPTIC,
    Optic,
    within_optic_fov,
)


def _optic(
    fov_half_angle_deg: float | None, boresight_azimuth_deg: float = 0.0
) -> Optic:
    """A synthetic test `Optic` -- the per-tier multipliers are irrelevant
    to `within_optic_fov` (a pure geometry test), so they're pinned at 1.0
    here rather than repeated at every call site."""
    return Optic(
        name="test",
        presence_range_mult=1.0,
        class_range_mult=1.0,
        type_range_mult=1.0,
        fov_half_angle_deg=fov_half_angle_deg,
        boresight_azimuth_deg=boresight_azimuth_deg,
    )


def test_none_fov_half_angle_always_passes() -> None:
    unrestricted = _optic(fov_half_angle_deg=None)

    assert within_optic_fov(unrestricted, azimuth_deg=0.0, elevation_deg=0.0)
    # Far off-boresight in every axis -- still no restriction.
    assert within_optic_fov(unrestricted, azimuth_deg=179.0, elevation_deg=89.0)


def test_boundary_case_exactly_at_the_half_angle_passes() -> None:
    optic = _optic(fov_half_angle_deg=10.0)

    # Pure azimuth offset of exactly the half-angle, zero elevation --
    # angular separation is exactly 10 deg.
    assert within_optic_fov(optic, azimuth_deg=10.0, elevation_deg=0.0)


def test_just_outside_the_half_angle_fails() -> None:
    optic = _optic(fov_half_angle_deg=10.0)

    assert not within_optic_fov(optic, azimuth_deg=10.001, elevation_deg=0.0)


def test_off_boresight_azimuth_case() -> None:
    """A non-zero `boresight_azimuth_deg` shifts the cone's centre --
    confirms `within_optic_fov` measures separation from the optic's own
    boresight, not from world azimuth 0."""
    optic = _optic(fov_half_angle_deg=5.0, boresight_azimuth_deg=45.0)

    assert within_optic_fov(optic, azimuth_deg=45.0, elevation_deg=0.0)
    assert within_optic_fov(optic, azimuth_deg=48.0, elevation_deg=0.0)
    assert not within_optic_fov(optic, azimuth_deg=0.0, elevation_deg=0.0)


def test_elevation_offset_alone_can_fail_the_gate() -> None:
    """A separation test, not an independent azimuth-box-and-elevation-box
    check -- pure elevation offset at zero azimuth must fail once it
    exceeds the half-angle, exactly as a pure azimuth offset does."""
    optic = _optic(fov_half_angle_deg=10.0)

    assert within_optic_fov(optic, azimuth_deg=0.0, elevation_deg=9.0)
    assert not within_optic_fov(optic, azimuth_deg=0.0, elevation_deg=11.0)


def test_unaided_optic_has_no_fov_restriction() -> None:
    assert UNAIDED_OPTIC.presence_range_mult == pytest.approx(1.0)
    assert UNAIDED_OPTIC.class_range_mult == pytest.approx(1.0)
    assert UNAIDED_OPTIC.type_range_mult == pytest.approx(1.0)
    assert UNAIDED_OPTIC.fov_half_angle_deg is None


def test_binocular_optic_has_the_btr_60_derived_per_tier_multipliers() -> None:
    """`BINOCULAR_OPTIC`'s per-tier multipliers (slice 2A, `plans/
    detection-cones-slice2/plan.md` decision 1) -- replacing the old flat
    `magnification=4.0` (`BINOCULAR_RANGE_MULTIPLIER`, retired) with three
    independently-measured, BTR-60-derived figures. Presence buys less than
    the old flat figure implied (2.42), class almost as much (3.50), type a
    little less again (3.00) -- `optics.py`'s own docstring has the
    reasoning (glass buys recognition more than it buys detection)."""
    assert BINOCULAR_OPTIC.presence_range_mult == pytest.approx(2.42)
    assert BINOCULAR_OPTIC.class_range_mult == pytest.approx(3.50)
    assert BINOCULAR_OPTIC.type_range_mult == pytest.approx(3.00)


def test_binocular_optic_has_a_real_field_of_view() -> None:
    """As of 2026-09-20's final scope change, `BINOCULAR_OPTIC` is no
    longer FOV-unrestricted -- the first optic in this table to carry a
    real `fov_half_angle_deg` value, half of a Б-6 6x30's ~8.5 deg true
    field. Safe to set now specifically because binoculars are no longer
    the default optic (see `test_visibility.py`'s `test_default_optic_is_
    naked_eye`): nothing calls `check_visibility` with this optic in the
    live path yet, so this value cannot misfire a gate today -- it exists
    for slice 2's mode selection to enforce."""
    assert BINOCULAR_OPTIC.fov_half_angle_deg == pytest.approx(4.25)


def test_binocular_optic_field_of_view_rejects_an_off_boresight_candidate() -> None:
    """The FOV value above is not just data -- confirms `within_optic_fov`
    actually enforces it for the shipped `BINOCULAR_OPTIC`, not only for
    synthetic test optics."""
    assert within_optic_fov(BINOCULAR_OPTIC, azimuth_deg=0.0, elevation_deg=0.0)
    assert not within_optic_fov(BINOCULAR_OPTIC, azimuth_deg=10.0, elevation_deg=0.0)
