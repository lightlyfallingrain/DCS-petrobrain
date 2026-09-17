"""Tests for `perception.cockpit_mask` -- the pure mechanism (interpolation,
rear cutoff, symmetric mirroring) behind the naked-eye channel's body-frame
occlusion gate (`plans/cockpit-visibility/plan.md`).

Deliberately built entirely against a small hand-authored synthetic mask,
never against `COCKPIT_MASKS`'s shipped values -- that is the point of the
plan's D3 mechanism/calibration split: this file must still pass unchanged
once the shipped mask's placeholder numbers are replaced with real derived
angles.
"""

from __future__ import annotations

import pytest

from perception.cockpit_mask import OcclusionMask, is_visible

# Round, easy-to-reason-about synthetic mask: 30 deg allowed straight ahead,
# tapering linearly to 10 deg at 90 deg (abeam), then a rear cutoff at 120.
_TEST_MASK = OcclusionMask(
    breakpoints=(
        (0.0, 30.0),
        (90.0, 10.0),
        (120.0, 0.0),
    ),
    rear_cutoff_deg=120.0,
)


def test_max_depression_at_breakpoint_returns_exact_value() -> None:
    assert _TEST_MASK.max_depression_deg(0.0) == pytest.approx(30.0)
    assert _TEST_MASK.max_depression_deg(90.0) == pytest.approx(10.0)


def test_max_depression_interpolates_linearly_between_breakpoints() -> None:
    # Halfway between (0, 30) and (90, 10) -> 20.
    assert _TEST_MASK.max_depression_deg(45.0) == pytest.approx(20.0)


def test_max_depression_none_at_and_beyond_rear_cutoff() -> None:
    assert _TEST_MASK.max_depression_deg(120.0) is None
    assert _TEST_MASK.max_depression_deg(170.0) is None


def test_is_visible_nose_contact_within_allowed_depression() -> None:
    # Dead ahead (azimuth 0), 20 deg below boresight -- under the 30 deg
    # allowed straight ahead.
    assert is_visible(_TEST_MASK, azimuth_deg=0.0, elevation_deg=-20.0) is True


def test_is_visible_nose_contact_beyond_allowed_depression_is_rejected() -> None:
    assert is_visible(_TEST_MASK, azimuth_deg=0.0, elevation_deg=-35.0) is False


def test_is_visible_abeam_contact_rejected_at_a_depression_the_nose_allows() -> None:
    # Same 20 deg depression as the nose test above, but out at 90 deg
    # (abeam), where the mask only allows 10 -- exercises the whole point
    # of a depression-per-azimuth table over a flat azimuth cone.
    assert is_visible(_TEST_MASK, azimuth_deg=90.0, elevation_deg=-20.0) is False


def test_is_visible_rear_contact_blocked_even_above_boresight() -> None:
    # Rear cutoff blocks everything back there, including something above
    # the horizon -- there is no "upward exception" to the rear cutoff.
    assert is_visible(_TEST_MASK, azimuth_deg=150.0, elevation_deg=30.0) is False


def test_is_visible_above_boresight_always_passes_depression_check() -> None:
    # Upward visibility is deliberately not modelled (module docstring):
    # an above-boresight contact (negative depression) trivially clears
    # any positive max_depression_deg, as long as azimuth is admissible.
    assert is_visible(_TEST_MASK, azimuth_deg=45.0, elevation_deg=60.0) is True


def test_is_visible_mask_is_symmetric_across_centreline() -> None:
    left = is_visible(_TEST_MASK, azimuth_deg=-70.0, elevation_deg=-5.0)
    right = is_visible(_TEST_MASK, azimuth_deg=70.0, elevation_deg=-5.0)

    assert left is True
    assert right is True
    assert left == right


def test_max_depression_holds_flat_past_last_breakpoint_before_cutoff() -> None:
    mask = OcclusionMask(breakpoints=((0.0, 30.0),), rear_cutoff_deg=120.0)

    assert mask.max_depression_deg(45.0) == pytest.approx(30.0)
    assert mask.max_depression_deg(119.0) == pytest.approx(30.0)
