"""Tests for `perception.gaze` -- `Gaze`, `within_gaze`, `gaze_for`
(`plans/detection-cones-slice2/plan.md`'s 2B), `ScanPlan`/`gaze_at` (2C's
o'clock scan loop).

Pure mechanism tests, mirroring `test_optics.py`/`test_cockpit_mask.py`'s
posture -- no telemetry, no `check_visibility`. `test_visibility.py` covers
the gate-chain integration (ordering, trace attribution, the boresight-
follows-gaze wiring); `test_attention.py` covers `RelativeSector`'s own
belief-level wedge table, now re-imported from this module rather than
defined in `belief.attention`; `test_naked_eye_source.py` covers the
end-to-end scan-loop integration (a flank contact only detected on the
cycles when its cone is gazed).
"""

from __future__ import annotations

import pytest

from perception.gaze import (
    FOCUS_CONE_HALF_WIDTH_DEG,
    FOCUS_DWELL_S,
    FREE_SCAN_PLAN,
    FULL_GAZE,
    SCAN_CYCLE_PERIOD_S,
    SCAN_PLAN,
    Gaze,
    ScanPlan,
    gaze_at,
    gaze_for,
    legs_within_wedge,
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


# -- ScanPlan / gaze_at (2C, plans/detection-cones-slice2/plan.md) ----------


def test_scan_plan_rejects_a_commanded_sector_with_no_command_time() -> None:
    with pytest.raises(ValueError, match="command_t_sim"):
        ScanPlan(commanded_sector="left", command_t_sim=None)


def test_scan_plan_rejects_a_command_time_with_no_commanded_sector() -> None:
    with pytest.raises(ValueError, match="command_t_sim"):
        ScanPlan(commanded_sector=None, command_t_sim=0.0)


def test_free_scan_plan_is_the_uncommanded_default() -> None:
    assert FREE_SCAN_PLAN == ScanPlan(commanded_sector=None, command_t_sim=None)


def test_scan_cycle_period_is_derived_from_the_table_and_dwell() -> None:
    # 8 slots (12, 11, 10, 9, 12, 1, 2, 3) x 2.0 s -- hard part 8's "Adopt A".
    assert len(SCAN_PLAN) == 8
    assert SCAN_CYCLE_PERIOD_S == pytest.approx(len(SCAN_PLAN) * FOCUS_DWELL_S)
    assert SCAN_CYCLE_PERIOD_S == pytest.approx(16.0)
    assert FOCUS_DWELL_S == pytest.approx(2.0)
    assert FOCUS_CONE_HALF_WIDTH_DEG == pytest.approx(15.0)


@pytest.mark.parametrize(
    ("t_sim", "expected_center", "expected_label"),
    [
        (0.0, 0.0, "12_oclock"),  # index 0: 12 o'clock, dead ahead
        (1.999, 0.0, "12_oclock"),  # still inside the first dwell
        (2.0, -30.0, "11_oclock"),  # index 1: 11 o'clock
        (4.0, -60.0, "10_oclock"),  # index 2: 10 o'clock
        (6.0, -90.0, "9_oclock"),  # index 3: 9 o'clock
        (8.0, 0.0, "12_oclock"),  # index 4: back to 12 (visited twice/cycle)
        (10.0, 30.0, "1_oclock"),  # index 5: 1 o'clock
        (12.0, 60.0, "2_oclock"),  # index 6: 2 o'clock
        (14.0, 90.0, "3_oclock"),  # index 7: 3 o'clock
        (16.0, 0.0, "12_oclock"),  # wraps: one full SCAN_CYCLE_PERIOD_S later
    ],
)
def test_free_scan_steps_through_the_oclock_table_by_sim_time(
    t_sim: float, expected_center: float, expected_label: str
) -> None:
    gaze = gaze_at(t_sim, FREE_SCAN_PLAN)

    assert gaze.center_azimuth_deg == pytest.approx(expected_center)
    assert gaze.half_width_deg == pytest.approx(FOCUS_CONE_HALF_WIDTH_DEG)
    assert gaze.label == expected_label


def test_free_scan_is_a_pure_function_of_sim_time_not_a_state_machine() -> None:
    """Determinism (hard part 1/9): calling `gaze_at` out of order, or
    repeatedly at the same `t_sim`, must never change its answer -- there
    is no internal counter to advance."""
    assert gaze_at(14.0, FREE_SCAN_PLAN) == gaze_at(14.0, FREE_SCAN_PLAN)
    first_pass = [gaze_at(t, FREE_SCAN_PLAN) for t in (0.0, 6.0, 12.0)]
    second_pass = [gaze_at(t, FREE_SCAN_PLAN) for t in (12.0, 0.0, 6.0)]
    assert first_pass == [second_pass[1], second_pass[2], second_pass[0]]


def test_commanded_ahead_is_a_static_single_cone_regardless_of_elapsed_time() -> None:
    # `_SECTOR_LEGS["ahead"] == (12,)` -- a single-leg sector degenerates to
    # a static gaze by construction (module docstring): every elapsed time
    # maps to index 0.
    plan = ScanPlan(commanded_sector="ahead", command_t_sim=5.0)

    for t_sim in (5.0, 5.5, 6.9, 100.0):
        gaze = gaze_at(t_sim, plan)
        assert gaze.center_azimuth_deg == pytest.approx(0.0)
        assert gaze.half_width_deg == pytest.approx(FOCUS_CONE_HALF_WIDTH_DEG)


def test_commanded_left_cycles_its_own_three_oclock_legs_from_command_time() -> None:
    # User, 2026-09-21 (hard part 2a): "within a sector it is itself a
    # smaller cone moving in a scan pattern" -- a commanded "left" steps
    # 11 -> 10 -> 9 -> 11 ..., 2 s each, timed from when the command was
    # issued (not from absolute sim time, unlike free scan).
    plan = ScanPlan(commanded_sector="left", command_t_sim=10.0)

    assert gaze_at(10.0, plan).label == "11_oclock"
    assert gaze_at(11.999, plan).label == "11_oclock"
    assert gaze_at(12.0, plan).label == "10_oclock"
    assert gaze_at(14.0, plan).label == "9_oclock"
    assert gaze_at(16.0, plan).label == "11_oclock"  # wraps after 6 s


def test_commanded_right_cycles_its_own_three_oclock_legs() -> None:
    plan = ScanPlan(commanded_sector="right", command_t_sim=0.0)

    assert gaze_at(0.0, plan).label == "1_oclock"
    assert gaze_at(2.0, plan).label == "2_oclock"
    assert gaze_at(4.0, plan).label == "3_oclock"
    assert gaze_at(6.0, plan).label == "1_oclock"


def test_commanded_full_matches_free_scans_own_table() -> None:
    # `_SECTOR_LEGS["full"] is SCAN_PLAN` -- "scan the whole 9-3 span" reuses
    # the free-scan table verbatim, just re-timed from the command.
    plan = ScanPlan(commanded_sector="full", command_t_sim=0.0)

    for t_sim in (0.0, 3.7, 9.9, 15.0):
        assert gaze_at(t_sim, plan) == gaze_at(t_sim, FREE_SCAN_PLAN)


def test_commanded_scan_is_relative_to_command_time_not_absolute_sim_time() -> None:
    # The same o'clock at the same offset-from-command, issued at two
    # different sim times, must return the same relative leg -- proving
    # `gaze_at` reads `t_sim - plan.command_t_sim`, not `t_sim` directly.
    early = ScanPlan(commanded_sector="left", command_t_sim=0.0)
    late = ScanPlan(commanded_sector="left", command_t_sim=100.0)

    assert gaze_at(3.0, early).label == gaze_at(103.0, late).label


# -- commanded_legs / legs_within_wedge (Stage 5, plans/
# voice-command-completeness/plan.md Decision 5) --------------------------


def test_scan_plan_rejects_both_commanded_sector_and_commanded_legs() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        ScanPlan(commanded_sector="left", command_t_sim=0.0, commanded_legs=(1,))


def test_scan_plan_rejects_commanded_legs_with_no_command_time() -> None:
    with pytest.raises(ValueError, match="command_t_sim"):
        ScanPlan(commanded_sector=None, command_t_sim=None, commanded_legs=(1,))


def test_scan_plan_rejects_a_command_time_with_no_commanded_legs_or_sector() -> None:
    with pytest.raises(ValueError, match="command_t_sim"):
        ScanPlan(commanded_sector=None, command_t_sim=0.0, commanded_legs=None)


def test_scan_plan_rejects_empty_commanded_legs() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        ScanPlan(commanded_sector=None, command_t_sim=0.0, commanded_legs=())


def test_commanded_legs_single_hour_is_a_static_gaze_like_a_one_leg_sector() -> None:
    # An o'clock command (`scan_clock_1`) is a one-leg plan, exactly as
    # `ahead` already degenerates to one leg under `commanded_sector`
    # (`ScanPlan`'s own module docstring, Stage 5's whole point).
    plan = ScanPlan(commanded_sector=None, command_t_sim=5.0, commanded_legs=(1,))

    for t_sim in (5.0, 5.5, 6.9, 100.0):
        gaze = gaze_at(t_sim, plan)
        assert gaze.label == "1_oclock"
        assert gaze.center_azimuth_deg == pytest.approx(30.0)


def test_commanded_legs_multi_hour_cycles_from_command_time() -> None:
    # Same three legs `commanded_sector="left"` would use, expressed
    # directly as `commanded_legs` -- must cycle identically.
    via_legs = ScanPlan(
        commanded_sector=None, command_t_sim=10.0, commanded_legs=(11, 10, 9)
    )
    via_sector = ScanPlan(commanded_sector="left", command_t_sim=10.0)

    for t_sim in (10.0, 11.999, 12.0, 14.0, 16.0):
        assert gaze_at(t_sim, via_legs) == gaze_at(t_sim, via_sector)


def test_commanded_legs_is_a_pure_function_of_sim_time() -> None:
    plan = ScanPlan(commanded_sector=None, command_t_sim=0.0, commanded_legs=(3,))
    assert gaze_at(7.0, plan) == gaze_at(7.0, plan)


def test_fixed_look_wins_over_commanded_legs() -> None:
    plan = ScanPlan(
        commanded_sector=None,
        command_t_sim=0.0,
        commanded_legs=(1,),
        fixed_look=Gaze(
            center_azimuth_deg=45.0, half_width_deg=4.25, label="fixed_look"
        ),
    )
    assert gaze_at(0.0, plan).label == "fixed_look"


def test_legs_within_wedge_matches_the_left_sectors_own_legs_as_a_set() -> None:
    # Cross-check: `_RELATIVE_SECTOR_WEDGE_DEG["left"] == (-60.0, 30.0)`
    # admits exactly the same three o'clock hours `_SECTOR_LEGS["left"]`
    # names -- as a *set*, not necessarily the same sweep order.
    # `legs_within_wedge` orders left-to-right by ascending signed offset
    # (its own docstring), which for this wedge is (9, 10, 11) -- the
    # numeric mirror of `_SECTOR_LEGS`'s own near-center-first (11, 10, 9)
    # sweep. The two tables serve different callers (a commanded named
    # sector vs. a converted absolute one) and are not required to agree
    # on sweep order, only on which hours qualify.
    assert set(legs_within_wedge(-60.0, 30.0)) == {9, 10, 11}
    assert legs_within_wedge(-60.0, 30.0) == (9, 10, 11)


def test_legs_within_wedge_around_dead_ahead() -> None:
    # A 90-degree-wide compass sector centered on dead ahead admits three
    # hours either side of 12, ordered left (11) to right (1).
    assert legs_within_wedge(0.0, 45.0) == (11, 12, 1)


def test_legs_within_wedge_handles_the_rear_wraparound() -> None:
    # Centered dead astern (180 degrees) -- exercises the +-180 wraparound
    # in both the admission test and the ordering offset.
    assert legs_within_wedge(180.0, 45.0) == (5, 6, 7)


def test_legs_within_wedge_never_empty_for_a_real_compass_sector_half_width() -> None:
    # Every one of the eight compass sectors' 45-degree half-width, at every
    # possible relative center, must resolve to at least one leg -- an empty
    # result here would silently degrade `logger._active_gaze`'s compass
    # conversion into an invalid zero-leg `ScanPlan`.
    for degrees in range(0, 360, 5):
        assert len(legs_within_wedge(float(degrees), 45.0)) > 0, degrees
