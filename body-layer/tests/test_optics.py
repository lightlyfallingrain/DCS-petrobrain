"""Tests for `perception.optics.within_optic_fov` and the two named optics
(`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`) -- `plans/detection-cones-slice1/
plan.md`, updated by slice 2B (`plans/detection-cones-slice2/plan.md`) for
`within_optic_fov`'s new boresight parameter and `Optic.peripheral`, and by
`BL-B64` Stage 1 (`plans/9k113-sight/plan.md`, direction §14) for
`UNAIDED_OPTIC.fov_half_angle_deg`'s `None` -> `90.0` change, and by the
`BL-B64` security fix (`plans/9k113-sight/security.md`) for
`within_field_of_regard`, the mechanism that enforces the sight optics'
field-of-regard data. The sight optics' per-tier multipliers themselves
(`SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`) are not otherwise tested here --
`test_naked_eye_source.py` and `test_estimation.py` are where those numbers
get exercised; `test_optic_policy.py` is where `within_field_of_regard`'s
effect on target *selection* is pinned, since that is a `belief` decision,
not a `perception` one.

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
    SIGHT_WIDE_OPTIC,
    UNAIDED_OPTIC,
    Optic,
    within_field_of_regard,
    within_optic_fov,
)


def _optic(fov_half_angle_deg: float | None, peripheral: bool = True) -> Optic:
    """A synthetic test `Optic` -- the per-tier multipliers are irrelevant
    to `within_optic_fov` (a pure geometry test), so they're pinned at 1.0
    here rather than repeated at every call site."""
    return Optic(
        name="test",
        presence_range_mult=1.0,
        class_range_mult=1.0,
        type_range_mult=1.0,
        fov_half_angle_deg=fov_half_angle_deg,
        peripheral=peripheral,
    )


def test_none_fov_half_angle_always_passes() -> None:
    unrestricted = _optic(fov_half_angle_deg=None)

    assert within_optic_fov(
        unrestricted, boresight_azimuth_deg=0.0, azimuth_deg=0.0, elevation_deg=0.0
    )
    # Far off-boresight in every axis -- still no restriction.
    assert within_optic_fov(
        unrestricted,
        boresight_azimuth_deg=0.0,
        azimuth_deg=179.0,
        elevation_deg=89.0,
    )


def test_boundary_case_exactly_at_the_half_angle_passes() -> None:
    optic = _optic(fov_half_angle_deg=10.0)

    # Pure azimuth offset of exactly the half-angle, zero elevation --
    # angular separation is exactly 10 deg.
    assert within_optic_fov(
        optic, boresight_azimuth_deg=0.0, azimuth_deg=10.0, elevation_deg=0.0
    )


def test_just_outside_the_half_angle_fails() -> None:
    optic = _optic(fov_half_angle_deg=10.0)

    assert not within_optic_fov(
        optic, boresight_azimuth_deg=0.0, azimuth_deg=10.001, elevation_deg=0.0
    )


def test_off_boresight_azimuth_case() -> None:
    """A non-zero `boresight_azimuth_deg` shifts the cone's centre --
    confirms `within_optic_fov` measures separation from the supplied
    boresight, not from world azimuth 0. Slice 2B moved this from an
    `Optic` field to a call-time parameter (`optics.py`'s "an optic is
    pointed by the head" note) -- the geometry it tests is unchanged."""
    optic = _optic(fov_half_angle_deg=5.0)

    assert within_optic_fov(
        optic, boresight_azimuth_deg=45.0, azimuth_deg=45.0, elevation_deg=0.0
    )
    assert within_optic_fov(
        optic, boresight_azimuth_deg=45.0, azimuth_deg=48.0, elevation_deg=0.0
    )
    assert not within_optic_fov(
        optic, boresight_azimuth_deg=45.0, azimuth_deg=0.0, elevation_deg=0.0
    )


def test_elevation_offset_alone_can_fail_the_gate() -> None:
    """A separation test, not an independent azimuth-box-and-elevation-box
    check -- pure elevation offset at zero azimuth must fail once it
    exceeds the half-angle, exactly as a pure azimuth offset does."""
    optic = _optic(fov_half_angle_deg=10.0)

    assert within_optic_fov(
        optic, boresight_azimuth_deg=0.0, azimuth_deg=0.0, elevation_deg=9.0
    )
    assert not within_optic_fov(
        optic, boresight_azimuth_deg=0.0, azimuth_deg=0.0, elevation_deg=11.0
    )


def test_unaided_optic_has_a_90_degree_half_angle() -> None:
    """`BL-B64` Stage 1, direction §14: `UNAIDED_OPTIC.fov_half_angle_deg`
    moved from `None` to `90.0` -- "a fairly sane 180 degree naked eye max
    FOV" (peripheral vision, not focus). No optic in this table carries
    `None` any more; see `within_optic_fov`'s own docstring for why that
    branch is kept anyway."""
    assert UNAIDED_OPTIC.presence_range_mult == pytest.approx(1.0)
    assert UNAIDED_OPTIC.class_range_mult == pytest.approx(1.0)
    assert UNAIDED_OPTIC.type_range_mult == pytest.approx(1.0)
    assert UNAIDED_OPTIC.fov_half_angle_deg == pytest.approx(90.0)


def test_unaided_optic_field_of_view_still_admits_anything_within_90_degrees() -> None:
    """The naked eye's own 90-degree half-angle is wide enough that an
    ordinary off-boresight candidate -- not near the 90-degree edge -- is
    unaffected by the `None` -> `90.0` change."""
    assert within_optic_fov(
        UNAIDED_OPTIC, boresight_azimuth_deg=0.0, azimuth_deg=80.0, elevation_deg=10.0
    )


def test_unaided_optic_field_of_view_now_rejects_past_90_degrees_true_separation() -> (
    None
):
    """The one real behavioural difference the direction document calls
    out: a candidate whose true angular separation from the boresight
    exceeds 90 degrees (not just its azimuth) is now rejected, where the
    old `None` half-angle admitted everything regardless of elevation.
    `boresight_azimuth_deg=0.0, boresight_elevation_deg=30.0`, candidate at
    `azimuth_deg=80.0, elevation_deg=-40.0` -- separation computes to
    ~102 degrees, past the new 90-degree half-angle."""
    assert not within_optic_fov(
        UNAIDED_OPTIC,
        boresight_azimuth_deg=0.0,
        azimuth_deg=80.0,
        elevation_deg=-40.0,
        boresight_elevation_deg=30.0,
    )


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
    assert within_optic_fov(
        BINOCULAR_OPTIC, boresight_azimuth_deg=0.0, azimuth_deg=0.0, elevation_deg=0.0
    )
    assert not within_optic_fov(
        BINOCULAR_OPTIC, boresight_azimuth_deg=0.0, azimuth_deg=10.0, elevation_deg=0.0
    )


# -- Optic.peripheral (slice 2B, plans/detection-cones-slice2/plan.md) ------


def test_unaided_optic_has_peripheral_vision() -> None:
    assert UNAIDED_OPTIC.peripheral is True


def test_binocular_optic_has_no_peripheral_vision() -> None:
    """The binocular's real cost is more than a narrow field of view --
    raising it trades away the wide, change-detecting peripheral channel
    entirely (hard part 2a, `plans/detection-cones-slice2/plan.md`)."""
    assert BINOCULAR_OPTIC.peripheral is False


class TestBoresightElevation:
    """`plans/binocular-optic/plan.md` Stage 2. A level boresight makes a
    narrow optic useless at exactly the ranges it exists for: you point
    binoculars *at* a thing, including downwards."""

    def test_a_close_ground_contact_is_outside_a_level_boresight(self) -> None:
        """The measurement that forced this: 1 km slant from 120 m AGL is
        ~6.9 degrees down, against a 4.25-degree half-angle."""
        assert not within_optic_fov(
            BINOCULAR_OPTIC,
            boresight_azimuth_deg=0.0,
            azimuth_deg=0.0,
            elevation_deg=-6.9,
        )

    def test_the_same_contact_is_inside_when_aimed_at(self) -> None:
        assert within_optic_fov(
            BINOCULAR_OPTIC,
            boresight_azimuth_deg=0.0,
            azimuth_deg=0.0,
            elevation_deg=-6.9,
            boresight_elevation_deg=-6.9,
        )

    def test_aiming_down_moves_the_whole_cone_not_just_its_edge(self) -> None:
        """The horizon leaves the field of view when the look is depressed
        far enough -- the cost of aiming, and the thing that makes a
        narrow optic a real trade rather than a free upgrade."""
        assert not within_optic_fov(
            BINOCULAR_OPTIC,
            boresight_azimuth_deg=0.0,
            azimuth_deg=0.0,
            elevation_deg=0.0,
            boresight_elevation_deg=-10.0,
        )

    def test_the_default_stays_level(self) -> None:
        """Every existing caller passes no elevation and must be
        unaffected."""
        assert within_optic_fov(
            BINOCULAR_OPTIC,
            boresight_azimuth_deg=0.0,
            azimuth_deg=0.0,
            elevation_deg=0.0,
        )

    # This class's original `test_the_unaided_eye_ignores_the_boresight_
    # entirely` asserted this exact (boresight, candidate) pair passed,
    # true only while `UNAIDED_OPTIC.fov_half_angle_deg` was `None`.
    # `BL-B64` Stage 1 (direction §14) gave it a real 90-degree half-angle,
    # and this pair's true separation is ~102 degrees -- past it. Moved to
    # `test_unaided_optic_field_of_view_now_rejects_past_90_degrees_true_
    # separation` above (now asserting the opposite), where it sits next
    # to the companion case that still passes, rather than left here
    # asserting something that is no longer true.


# -- within_field_of_regard (BL-B64 security fix, plans/9k113-sight/
# security.md) ---------------------------------------------------------


def test_an_optic_with_no_regard_data_is_always_unrestricted() -> None:
    """`None` means "pointed by the head" (`UNAIDED_OPTIC`/
    `BINOCULAR_OPTIC`) -- a true no-op, matching `within_optic_fov`'s own
    `None`-means-unrestricted convention."""
    assert within_field_of_regard(UNAIDED_OPTIC, azimuth_deg=0.0, elevation_deg=0.0)
    assert within_field_of_regard(
        BINOCULAR_OPTIC, azimuth_deg=175.0, elevation_deg=85.0
    )


def test_the_security_agents_own_reproduction_is_rejected() -> None:
    """The exact scenario from `plans/9k113-sight/security.md`: a contact
    at 85 deg body-relative azimuth, 25 deg past `SIGHT_WIDE_OPTIC`'s own
    60 deg limit."""
    assert not within_field_of_regard(
        SIGHT_WIDE_OPTIC, azimuth_deg=85.0, elevation_deg=0.0
    )


def test_azimuth_is_symmetric_about_zero() -> None:
    assert within_field_of_regard(SIGHT_WIDE_OPTIC, azimuth_deg=60.0, elevation_deg=0.0)
    assert within_field_of_regard(
        SIGHT_WIDE_OPTIC, azimuth_deg=-60.0, elevation_deg=0.0
    )
    assert not within_field_of_regard(
        SIGHT_WIDE_OPTIC, azimuth_deg=60.001, elevation_deg=0.0
    )
    assert not within_field_of_regard(
        SIGHT_WIDE_OPTIC, azimuth_deg=-60.001, elevation_deg=0.0
    )


def test_elevation_is_not_symmetric() -> None:
    """+20/-15 -- a symmetric +-15 or +-20 implementation would get one of
    these two pairs wrong."""
    assert within_field_of_regard(SIGHT_WIDE_OPTIC, azimuth_deg=0.0, elevation_deg=20.0)
    assert not within_field_of_regard(
        SIGHT_WIDE_OPTIC, azimuth_deg=0.0, elevation_deg=20.001
    )
    assert within_field_of_regard(
        SIGHT_WIDE_OPTIC, azimuth_deg=0.0, elevation_deg=-15.0
    )
    assert not within_field_of_regard(
        SIGHT_WIDE_OPTIC, azimuth_deg=0.0, elevation_deg=-15.001
    )
    # The asymmetry itself: +18 is inside the up limit but would be
    # outside a symmetric +-15, and -18 is outside the down limit but
    # would be inside a symmetric +-20 -- either swap would misjudge one
    # of these two.
    assert within_field_of_regard(SIGHT_WIDE_OPTIC, azimuth_deg=0.0, elevation_deg=18.0)
    assert not within_field_of_regard(
        SIGHT_WIDE_OPTIC, azimuth_deg=0.0, elevation_deg=-18.0
    )


def test_a_field_with_only_one_bound_set_restricts_only_that_bound() -> None:
    """Each of the three fields is read independently -- a future optic
    that restricts only azimuth is not assumed to also restrict
    elevation."""
    azimuth_only = Optic(
        name="test",
        presence_range_mult=1.0,
        class_range_mult=1.0,
        type_range_mult=1.0,
        fov_half_angle_deg=None,
        regard_azimuth_half_deg=30.0,
    )
    assert within_field_of_regard(azimuth_only, azimuth_deg=0.0, elevation_deg=89.0)
    assert not within_field_of_regard(azimuth_only, azimuth_deg=31.0, elevation_deg=0.0)
