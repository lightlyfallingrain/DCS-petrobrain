"""Tests for `perception.geometry`'s bearing/range/LOS helpers.

World-model calls (`describe_position`, `sample_grid`) are monkeypatched
rather than exercised against a real `.sqlite` store -- this module is
about the geometry math and the LOS-sampling loop's own logic (absence
handling, blocking-vs-clear), not about world-model's store internals,
which are covered by that subproject's own tests.
"""

from __future__ import annotations

import math
import sqlite3

import pytest

from perception import geometry
from perception.geometry import GeoPosition

_FAKE_CONN = sqlite3.connect(":memory:")


def test_bearing_deg_north() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    target = GeoPosition(x=100.0, z=0.0, alt_m=0.0)

    assert geometry.bearing_deg(observer, target) == pytest.approx(0.0)


def test_bearing_deg_east() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    target = GeoPosition(x=0.0, z=100.0, alt_m=0.0)

    assert geometry.bearing_deg(observer, target) == pytest.approx(90.0)


def test_bearing_deg_south() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    target = GeoPosition(x=-100.0, z=0.0, alt_m=0.0)

    assert geometry.bearing_deg(observer, target) == pytest.approx(180.0)


def test_bearing_deg_west_wraps_to_positive() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    target = GeoPosition(x=0.0, z=-100.0, alt_m=0.0)

    assert geometry.bearing_deg(observer, target) == pytest.approx(270.0)


def test_range_m_ground_only() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    target = GeoPosition(x=3000.0, z=4000.0, alt_m=0.0)

    assert geometry.range_m(observer, target) == pytest.approx(5000.0)


def test_range_m_includes_altitude_component() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    target = GeoPosition(x=0.0, z=0.0, alt_m=100.0)

    assert geometry.range_m(observer, target) == pytest.approx(100.0)


def test_elevation_at_delegates_to_describe_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class _FakeElevation:
        dcs_m = 123.4

    class _FakeDescription:
        elevation = _FakeElevation()

    def fake_describe_position(
        conn: object, theatre: str, x: float, z: float
    ) -> object:
        calls.append((theatre, x, z))
        return _FakeDescription()

    monkeypatch.setattr(geometry, "describe_position", fake_describe_position)

    result = geometry.elevation_at(_FAKE_CONN, "Syria", 10.0, 20.0)

    assert result == 123.4
    assert calls == [("Syria", 10.0, 20.0)]


def test_line_of_sight_clear_delegates_to_world_model_primitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`geometry.line_of_sight_clear` is a thin wrapper around `query.
    line_of_sight.line_of_sight_clear` (`plans/world-model-los-
    generalization/plan.md`) -- the LOS scenario coverage (flat terrain,
    blocked by a ridge, ridge below the sightline, missing elevation) now
    lives against that primitive directly in world-model's
    `test_query_line_of_sight.py`. This test only checks the delegation:
    `GeoPosition` -> `(x, z, alt_m)` tuple conversion, argument pass-through,
    and the return value coming back unchanged -- mirroring how
    `test_elevation_at_delegates_to_describe_position` above tests
    `elevation_at`'s own delegation to `describe_position`."""
    calls = []

    def fake_wm_line_of_sight_clear(
        conn: object,
        theatre: str,
        observer: tuple[float, float, float],
        target: tuple[float, float, float],
        *,
        samples: int,
    ) -> bool:
        calls.append((theatre, observer, target, samples))
        return False

    monkeypatch.setattr(
        geometry, "_wm_line_of_sight_clear", fake_wm_line_of_sight_clear
    )

    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    target = GeoPosition(x=10000.0, z=0.0, alt_m=500.0)

    result = geometry.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target)

    assert result is False
    assert calls == [
        ("Syria", (0.0, 0.0, 500.0), (10000.0, 0.0, 500.0), 20),
    ]


def test_project_terrain_aware_over_flat_terrain_matches_flat_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flat terrain (elevation == observer altitude everywhere) is a
    fixed point on the first iteration -- both single-shot and iterative
    calls should land on the same horizontal position as the flat
    projection."""
    monkeypatch.setattr(geometry, "sample_grid", lambda conn, kind, x, z: 500.0)

    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    flat = geometry.project_from_bearing_range(observer, 90.0, 1000.0)

    for max_iterations in (1, 5):
        result = geometry.project_terrain_aware(
            _FAKE_CONN,
            "Syria",
            observer,
            90.0,
            1000.0,
            max_iterations=max_iterations,
        )
        assert result.x == pytest.approx(flat.x)
        assert result.z == pytest.approx(flat.z)
        assert result.alt_m == pytest.approx(500.0)


def test_project_terrain_aware_converges_on_a_known_slope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A target on rising ground ends up horizontally closer to the observer
    than the flat projection places it, once more than one iteration has
    run (more of the slant range is "spent" climbing). A single iteration
    only corrects the altitude estimate at the flat horizontal position --
    the fixed-point re-solve for the horizontal position itself only shows
    up from the second iteration on."""

    # A uniform slope along the bearing-0 (north/x) axis: terrain elevation
    # rises 0.5m per metre of x, so a larger implied horizontal_x means a
    # higher target altitude, which in turn shortens the horizontal range a
    # fixed slant range allows -- a real fixed-point problem, not a trivial
    # one-shot case.
    def sloped_elevation(conn: object, kind: str, x: float, z: float) -> float:
        return 0.5 * x

    monkeypatch.setattr(geometry, "sample_grid", sloped_elevation)

    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    flat = geometry.project_from_bearing_range(observer, 0.0, 1000.0)

    one_shot = geometry.project_terrain_aware(
        _FAKE_CONN, "Syria", observer, 0.0, 1000.0, max_iterations=1
    )
    converged = geometry.project_terrain_aware(
        _FAKE_CONN, "Syria", observer, 0.0, 1000.0, max_iterations=5
    )

    # One iteration samples terrain at the flat horizontal position, so it
    # matches the flat projection's horizontal position exactly and only
    # differs in the altitude it reports.
    assert one_shot.x == pytest.approx(flat.x)
    assert one_shot.alt_m == pytest.approx(500.0)

    # Climbing ground shortens the horizontal component of a fixed slant
    # range once the fixed-point solve actually iterates, so five
    # iterations must land closer to the observer than both the flat
    # projection and the one-shot result.
    assert converged.x < flat.x
    assert converged.x < one_shot.x
    # The converged result is consistent with the terrain sampled there.
    assert converged.alt_m == pytest.approx(0.5 * converged.x)


def test_project_terrain_aware_falls_back_to_flat_when_elevation_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(geometry, "sample_grid", lambda conn, kind, x, z: None)

    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    flat = geometry.project_from_bearing_range(observer, 45.0, 2000.0)

    result = geometry.project_terrain_aware(
        _FAKE_CONN, "Syria", observer, 45.0, 2000.0, max_iterations=5
    )

    assert result == flat


# --- body_relative_direction (plans/cockpit-visibility/plan.md D1) ---


def test_body_relative_direction_level_unbanked_matches_world_frame() -> None:
    # Heading/pitch/bank all zero: body frame == world frame, so this must
    # reduce to plain bearing/elevation.
    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    target = GeoPosition(x=1000.0, z=1000.0, alt_m=500.0)

    result = geometry.body_relative_direction(
        observer, target, heading_true_deg=0.0, pitch_deg=0.0, bank_deg=0.0
    )

    assert result.azimuth_deg == pytest.approx(45.0)
    assert result.elevation_deg == pytest.approx(0.0)


def test_body_relative_direction_removes_heading() -> None:
    # A target dead ahead of a heading-90 (east-pointed) aircraft should
    # resolve to azimuth 0, whatever its world bearing is.
    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    target = GeoPosition(x=0.0, z=1000.0, alt_m=500.0)  # world bearing: east (90)

    result = geometry.body_relative_direction(
        observer, target, heading_true_deg=90.0, pitch_deg=0.0, bank_deg=0.0
    )

    assert result.azimuth_deg == pytest.approx(0.0)
    assert result.elevation_deg == pytest.approx(0.0)


def test_body_relative_direction_target_along_pitched_nose_is_dead_ahead() -> None:
    # A target exactly along the nose of a nose-up-pitched aircraft (i.e.
    # its world elevation equals the pitch angle) must resolve to
    # elevation 0 in the body frame -- this is the case the module
    # docstring's derivation walkthrough calls out directly.
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    pitch_deg = 20.0
    horizontal_range = 1000.0
    target = GeoPosition(
        x=horizontal_range,
        z=0.0,
        alt_m=horizontal_range * math.tan(math.radians(pitch_deg)),
    )

    result = geometry.body_relative_direction(
        observer, target, heading_true_deg=0.0, pitch_deg=pitch_deg, bank_deg=0.0
    )

    assert result.azimuth_deg == pytest.approx(0.0)
    assert result.elevation_deg == pytest.approx(0.0, abs=1e-6)


def test_body_relative_direction_below_horizon_is_negative_elevation() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    target = GeoPosition(x=1000.0, z=0.0, alt_m=0.0)

    result = geometry.body_relative_direction(
        observer, target, heading_true_deg=0.0, pitch_deg=0.0, bank_deg=0.0
    )

    assert result.elevation_deg < 0.0


def test_body_relative_direction_bank_rotates_elevation_into_azimuth() -> None:
    # A target dead below the aircraft (world elevation -90) has no
    # meaningful azimuth when level -- but roll 90 deg right and that same
    # target should resolve to straight out the right side, elevation ~0:
    # this is the plan's whole justification for reading bank at all (a
    # banking helicopter is exactly when a heading-only cone is most
    # wrong).
    observer = GeoPosition(x=0.0, z=0.0, alt_m=1000.0)
    target = GeoPosition(x=0.0, z=0.0, alt_m=0.0)

    level = geometry.body_relative_direction(
        observer, target, heading_true_deg=0.0, pitch_deg=0.0, bank_deg=0.0
    )
    banked_right = geometry.body_relative_direction(
        observer, target, heading_true_deg=0.0, pitch_deg=0.0, bank_deg=90.0
    )

    assert level.elevation_deg == pytest.approx(-90.0)
    assert banked_right.azimuth_deg == pytest.approx(90.0)
    assert banked_right.elevation_deg == pytest.approx(0.0, abs=1e-6)


def test_body_relative_direction_rear_hemisphere() -> None:
    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    target = GeoPosition(x=-1000.0, z=0.0, alt_m=500.0)

    result = geometry.body_relative_direction(
        observer, target, heading_true_deg=0.0, pitch_deg=0.0, bank_deg=0.0
    )

    assert abs(result.azimuth_deg) == pytest.approx(180.0)


# -- plans/attack-run/plan.md Decisions 3/6 -------------------------------


def test_signed_angular_delta_deg_right_is_positive() -> None:
    assert geometry.signed_angular_delta_deg(0.0, 10.0) == pytest.approx(10.0)


def test_signed_angular_delta_deg_left_is_negative() -> None:
    assert geometry.signed_angular_delta_deg(0.0, 350.0) == pytest.approx(-10.0)


def test_signed_angular_delta_deg_at_the_boundary_is_positive_180() -> None:
    # (-180, 180] -- the boundary itself belongs to +180, not -180.
    assert geometry.signed_angular_delta_deg(0.0, 180.0) == pytest.approx(180.0)


def test_signed_angular_delta_deg_zero() -> None:
    assert geometry.signed_angular_delta_deg(45.0, 45.0) == pytest.approx(0.0)


def test_alignment_direction_forces_bank_to_zero() -> None:
    # Decision 3's whole point: the same target, same heading/pitch, but
    # a heavily banked observer -- `alignment_direction` must agree with
    # `body_relative_direction(..., bank_deg=0.0)` regardless of the
    # observer's real bank, since it never reads it at all.
    observer = GeoPosition(x=0.0, z=0.0, alt_m=1000.0)
    target = GeoPosition(x=1000.0, z=500.0, alt_m=800.0)

    result = geometry.alignment_direction(
        observer, target, heading_true_deg=20.0, pitch_deg=5.0
    )
    expected = geometry.body_relative_direction(
        observer, target, heading_true_deg=20.0, pitch_deg=5.0, bank_deg=0.0
    )

    assert result.azimuth_deg == pytest.approx(expected.azimuth_deg)
    assert result.elevation_deg == pytest.approx(expected.elevation_deg)


def test_alignment_direction_oblique_heading_and_banked_observer_agree() -> None:
    # The bank-stabilisation claim is a trig no-regression claim and
    # axis-aligned angles cannot prove it (plan Stage 3) -- an oblique
    # heading/pitch combined with a heavily banked real attitude must
    # still produce the *same* alignment as the unbanked case, because
    # `alignment_direction` never reads bank at all.
    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    target = GeoPosition(x=2000.0, z=-750.0, alt_m=300.0)

    unbanked = geometry.alignment_direction(
        observer, target, heading_true_deg=37.0, pitch_deg=-8.0
    )
    # `alignment_direction` ignores bank by construction, so calling it
    # again cannot differ -- the real regression this guards is a future
    # edit that accidentally threads a real `bank_deg` through.
    still_unbanked = geometry.alignment_direction(
        observer, target, heading_true_deg=37.0, pitch_deg=-8.0
    )

    assert unbanked.azimuth_deg == pytest.approx(still_unbanked.azimuth_deg)
    assert unbanked.elevation_deg == pytest.approx(still_unbanked.elevation_deg)
    # And it must genuinely differ from the full, bank-mixed frame at a
    # real bank angle, or this test would not be exercising anything.
    full_frame = geometry.body_relative_direction(
        observer, target, heading_true_deg=37.0, pitch_deg=-8.0, bank_deg=60.0
    )
    assert unbanked.azimuth_deg != pytest.approx(full_frame.azimuth_deg)


# -- F5 (docs/acceptance/2026-10-20-sortie-feedback.md), plans/
# 9k113-narrow-search/plan.md: heading_relative_to_body_relative ----------


def test_heading_relative_to_body_relative_is_identity_when_level_unbanked() -> None:
    # Pitch/bank/heading all zero: the conversion must be a true pass-
    # through, since a heading-relative step already equals its own
    # body-relative direction at wings-level, unbanked flight.
    result = geometry.heading_relative_to_body_relative(
        -23.0, -7.5, heading_true_deg=0.0, pitch_deg=0.0, bank_deg=0.0
    )
    assert result.azimuth_deg == pytest.approx(-23.0)
    assert result.elevation_deg == pytest.approx(-7.5)


def test_heading_relative_to_body_relative_cancels_heading_exactly() -> None:
    # The inverse-yaw construction (docstring: "the yaw cancels exactly")
    # must hold regardless of which heading is flown -- fix pitch/bank at
    # real, non-zero values and vary only heading_true_deg; a broken
    # inverse would leak heading into the result the moment pitch or bank
    # is non-zero (at pitch=bank=0 this would pass trivially, which is why
    # both are non-zero here).
    first = geometry.heading_relative_to_body_relative(
        20.0, -10.0, heading_true_deg=0.0, pitch_deg=15.0, bank_deg=-25.0
    )
    second = geometry.heading_relative_to_body_relative(
        20.0, -10.0, heading_true_deg=137.0, pitch_deg=15.0, bank_deg=-25.0
    )
    assert first.azimuth_deg == pytest.approx(second.azimuth_deg)
    assert first.elevation_deg == pytest.approx(second.elevation_deg)


def test_heading_relative_to_body_relative_nose_down_reduces_depression() -> None:
    # F5's own worked example: a 1000 m AGL / 2333 m near-edge depression
    # (23.2 deg, well past the 9K113's -15 deg down limit at level flight)
    # is brought back to -13.2 deg -- inside the limit -- by 10 deg of
    # nose-down pitch alone, altitude and range unchanged.
    depression_deg = math.degrees(math.atan2(1000.0, 2333.0))
    level = geometry.heading_relative_to_body_relative(
        0.0, -depression_deg, heading_true_deg=0.0, pitch_deg=0.0, bank_deg=0.0
    )
    nose_down = geometry.heading_relative_to_body_relative(
        0.0, -depression_deg, heading_true_deg=0.0, pitch_deg=-10.0, bank_deg=0.0
    )
    assert level.elevation_deg == pytest.approx(-23.2, abs=0.05)
    assert nose_down.elevation_deg == pytest.approx(-13.2, abs=0.05)


def test_heading_relative_to_body_relative_nose_up_increases_depression() -> None:
    # The other half of the same example -- "nose high at low alt would
    # limit near scan": a step well clear of the down limit at level
    # flight (-10 deg) is pushed 10 deg further down by 10 deg of nose-up
    # pitch, landing just past the -15 deg limit.
    level = geometry.heading_relative_to_body_relative(
        0.0, -10.0, heading_true_deg=0.0, pitch_deg=0.0, bank_deg=0.0
    )
    nose_up = geometry.heading_relative_to_body_relative(
        0.0, -10.0, heading_true_deg=0.0, pitch_deg=10.0, bank_deg=0.0
    )
    assert level.elevation_deg == pytest.approx(-10.0)
    assert nose_up.elevation_deg == pytest.approx(-20.0, abs=1e-6)


def test_heading_relative_to_body_relative_bank_rotates_elevation_into_azimuth() -> (
    None
):
    # A step 2 deg past the down limit at wings-level (-17 deg, dead ahead)
    # is carried by 30 deg of bank into a shallower, off-centre direction
    # -- the same "roll opens up ground to one side" effect `perception.
    # geometry.body_relative_direction`'s own bank test pins, here shown to
    # apply to a heading-relative step too, not only to a real target.
    level = geometry.heading_relative_to_body_relative(
        0.0, -17.0, heading_true_deg=0.0, pitch_deg=0.0, bank_deg=0.0
    )
    banked = geometry.heading_relative_to_body_relative(
        0.0, -17.0, heading_true_deg=0.0, pitch_deg=0.0, bank_deg=30.0
    )
    assert level.azimuth_deg == pytest.approx(0.0)
    assert level.elevation_deg == pytest.approx(-17.0)
    assert banked.azimuth_deg == pytest.approx(8.69, abs=0.01)
    assert banked.elevation_deg == pytest.approx(-14.67, abs=0.01)
