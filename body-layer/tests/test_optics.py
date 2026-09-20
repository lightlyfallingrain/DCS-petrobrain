"""Tests for `perception.optics.within_optic_fov` and the two named optics
(`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`) -- `plans/detection-cones-slice1/
plan.md`.

Pure mechanism tests, mirroring `test_cockpit_mask.py`'s posture: exercised
against small synthetic `Optic` instances, not the shipped table, so a
future change to `BINOCULAR_OPTIC`'s own numbers can't break the mechanism
tests here.
"""

from __future__ import annotations

import pytest

from perception.optics import (
    BINOCULAR_OPTIC,
    UNAIDED_OPTIC,
    Optic,
    within_optic_fov,
)
from perception.visibility import BINOCULAR_RANGE_MULTIPLIER


def test_none_fov_half_angle_always_passes() -> None:
    unrestricted = Optic(name="test", magnification=1.0, fov_half_angle_deg=None)

    assert within_optic_fov(unrestricted, azimuth_deg=0.0, elevation_deg=0.0)
    # Far off-boresight in every axis -- still no restriction.
    assert within_optic_fov(unrestricted, azimuth_deg=179.0, elevation_deg=89.0)


def test_boundary_case_exactly_at_the_half_angle_passes() -> None:
    optic = Optic(name="test", magnification=1.0, fov_half_angle_deg=10.0)

    # Pure azimuth offset of exactly the half-angle, zero elevation --
    # angular separation is exactly 10 deg.
    assert within_optic_fov(optic, azimuth_deg=10.0, elevation_deg=0.0)


def test_just_outside_the_half_angle_fails() -> None:
    optic = Optic(name="test", magnification=1.0, fov_half_angle_deg=10.0)

    assert not within_optic_fov(optic, azimuth_deg=10.001, elevation_deg=0.0)


def test_off_boresight_azimuth_case() -> None:
    """A non-zero `boresight_azimuth_deg` shifts the cone's centre --
    confirms `within_optic_fov` measures separation from the optic's own
    boresight, not from world azimuth 0."""
    optic = Optic(
        name="test",
        magnification=1.0,
        fov_half_angle_deg=5.0,
        boresight_azimuth_deg=45.0,
    )

    assert within_optic_fov(optic, azimuth_deg=45.0, elevation_deg=0.0)
    assert within_optic_fov(optic, azimuth_deg=48.0, elevation_deg=0.0)
    assert not within_optic_fov(optic, azimuth_deg=0.0, elevation_deg=0.0)


def test_elevation_offset_alone_can_fail_the_gate() -> None:
    """A separation test, not an independent azimuth-box-and-elevation-box
    check -- pure elevation offset at zero azimuth must fail once it
    exceeds the half-angle, exactly as a pure azimuth offset does."""
    optic = Optic(name="test", magnification=1.0, fov_half_angle_deg=10.0)

    assert within_optic_fov(optic, azimuth_deg=0.0, elevation_deg=9.0)
    assert not within_optic_fov(optic, azimuth_deg=0.0, elevation_deg=11.0)


def test_unaided_optic_has_no_fov_restriction() -> None:
    assert UNAIDED_OPTIC.magnification == pytest.approx(1.0)
    assert UNAIDED_OPTIC.fov_half_angle_deg is None


def test_unaided_optic_derating_leaves_effective_magnification_unchanged() -> None:
    """`handheld_effectiveness` defaults to `1.0` -- `UNAIDED_OPTIC` is
    unaffected by the binocular derating concept (`plans/
    detection-cones-slice1/plan.md`, 2026-09-20 magnification split)."""
    assert UNAIDED_OPTIC.handheld_effectiveness == pytest.approx(1.0)
    assert UNAIDED_OPTIC.effective_magnification == pytest.approx(1.0)


def test_binocular_optic_effective_magnification_matches_the_calibrated_constant() -> (
    None
):
    """`BINOCULAR_OPTIC.effective_magnification` (real 8x magnification
    times the named handheld/vibration derating factor) must track
    `visibility.BINOCULAR_RANGE_MULTIPLIER` exactly, so the two can never
    silently drift apart -- this is the behaviour-preservation guarantee
    for the 2026-09-20 magnification/derating split (raw `magnification`
    changed from 4.0 to a realistic 8.0; only the *effective* figure,
    which is what `visibility.py` actually consumes, is required to stay
    at 4.0)."""
    assert BINOCULAR_OPTIC.effective_magnification == pytest.approx(
        BINOCULAR_RANGE_MULTIPLIER
    )
    assert BINOCULAR_OPTIC.fov_half_angle_deg is None
