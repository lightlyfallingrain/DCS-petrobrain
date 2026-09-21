"""Tests for `perception.gaze` -- `Gaze`, `within_gaze`, `gaze_for`,
`gaze_from_relative_sector` (`plans/detection-cones-slice2/plan.md`'s 2B).

Pure mechanism tests, mirroring `test_optics.py`/`test_cockpit_mask.py`'s
posture -- no telemetry, no `check_visibility`. `test_visibility.py` covers
the gate-chain integration (ordering, trace attribution, the boresight-
follows-gaze wiring); `test_attention.py` covers `RelativeSector`'s own
belief-level wedge table, now re-imported from this module rather than
defined in `belief.attention`.
"""

from __future__ import annotations

import pytest

from perception.gaze import (
    FULL_GAZE,
    Gaze,
    gaze_for,
    gaze_from_relative_sector,
    within_gaze,
)
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC, Optic


def test_full_gaze_matches_the_relative_sector_full_wedge() -> None:
    assert FULL_GAZE == Gaze(center_azimuth_deg=0.0, half_width_deg=90.0, label="full")


def test_within_gaze_boundary_case_exactly_at_the_half_width_passes() -> None:
    gaze = Gaze(center_azimuth_deg=0.0, half_width_deg=30.0, label="ahead")

    assert within_gaze(gaze, azimuth_deg=30.0)
    assert not within_gaze(gaze, azimuth_deg=30.001)


def test_within_gaze_at_a_non_axis_aligned_angle() -> None:
    """A gaze centred and tested off any multiple of 45/90 degrees -- the
    milestone's own standing constraint (a prior bug in this milestone hid
    behind an axis-aligned-only test suite)."""
    gaze = Gaze(center_azimuth_deg=37.0, half_width_deg=42.0, label="test")

    # 37 + 42 = 79: exactly on the boundary.
    assert within_gaze(gaze, azimuth_deg=79.0)
    assert not within_gaze(gaze, azimuth_deg=79.5)
    # 37 - 42 = -5: exactly on the boundary the other side.
    assert within_gaze(gaze, azimuth_deg=-5.0)


def test_within_gaze_wraps_across_the_180_seam() -> None:
    """A gaze centred near +/-180 deg must not be fooled by the raw
    numeric gap between e.g. 170 and -170 -- exercised at 135 deg offsets,
    per the milestone's non-axis-aligned-angle rule."""
    gaze = Gaze(center_azimuth_deg=170.0, half_width_deg=40.0, label="test")

    # True separation from 170 to -170 (== 190) is 20 deg, well inside.
    assert within_gaze(gaze, azimuth_deg=-170.0)
    # 170 - 135 = 35: far outside a 40 deg half-width measured the short
    # way around (separation 135 deg), not the raw 190-degree gap.
    assert not within_gaze(gaze, azimuth_deg=35.0)


def test_gaze_for_returns_gaze_unchanged_for_a_non_stimulus_candidate() -> None:
    gaze = Gaze(center_azimuth_deg=0.0, half_width_deg=30.0, label="ahead")

    assert gaze_for(1, gaze, frozenset({2}), UNAIDED_OPTIC) is gaze


def test_gaze_for_returns_none_when_no_gaze_is_active() -> None:
    assert gaze_for(1, None, frozenset(), UNAIDED_OPTIC) is None


def test_gaze_for_bypasses_the_gate_for_a_peripheral_stimulus_under_unaided_optic() -> (
    None
):
    """The bypass seam's one live rule (hard parts 2a/4): a stimulus
    clears the gaze gate under an optic that still has peripheral vision
    -- `UNAIDED_OPTIC.peripheral is True`."""
    gaze = Gaze(center_azimuth_deg=0.0, half_width_deg=10.0, label="ahead")

    assert gaze_for(1, gaze, frozenset({1}), UNAIDED_OPTIC) is None


def test_gaze_for_does_not_bypass_under_binocular_optic() -> None:
    """The binocular's real cost, made executable: raising binoculars
    (`BINOCULAR_OPTIC.peripheral is False`) means there is no peripheral
    channel to catch a stimulus, so it does *not* bypass the gate."""
    gaze = Gaze(center_azimuth_deg=0.0, half_width_deg=10.0, label="ahead")

    assert gaze_for(1, gaze, frozenset({1}), BINOCULAR_OPTIC) is gaze


def test_gaze_for_synthetic_non_peripheral_optic_also_does_not_bypass() -> None:
    """Confirms the rule reads `optic.peripheral`, not a hardcoded check
    against `BINOCULAR_OPTIC` specifically."""
    no_peripheral_optic = Optic(
        name="test_no_peripheral",
        presence_range_mult=1.0,
        class_range_mult=1.0,
        type_range_mult=1.0,
        fov_half_angle_deg=None,
        peripheral=False,
    )
    gaze = Gaze(center_azimuth_deg=0.0, half_width_deg=10.0, label="ahead")

    assert gaze_for(1, gaze, frozenset({1}), no_peripheral_optic) is gaze


@pytest.mark.parametrize(
    ("sector", "expected_center", "expected_half_width"),
    [
        ("ahead", 0.0, 30.0),
        ("left", -60.0, 30.0),
        ("right", 60.0, 30.0),
        ("full", 0.0, 90.0),
    ],
)
def test_gaze_from_relative_sector_matches_the_wedge_table(
    sector: str, expected_center: float, expected_half_width: float
) -> None:
    gaze = gaze_from_relative_sector(sector)  # type: ignore[arg-type]

    assert gaze.center_azimuth_deg == pytest.approx(expected_center)
    assert gaze.half_width_deg == pytest.approx(expected_half_width)
    assert gaze.label == sector
