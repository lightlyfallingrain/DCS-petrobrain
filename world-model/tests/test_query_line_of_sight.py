"""Tests for `query.line_of_sight.line_of_sight_clear`.

Moved from body-layer's `test_geometry.py` (`plans/
world-model-los-generalization/plan.md`) along with the algorithm itself --
these four scenarios (flat terrain, blocked by a ridge, a ridge below the
sightline, missing elevation treated as non-blocking) are unchanged except
for the observer/target argument shape, which is now a bare
`(x, z, alt_m)` tuple instead of body-layer's `GeoPosition`.

`store.reader.sample_grid` is monkeypatched at this module's own import
site (`query.line_of_sight.sample_grid`) rather than exercised against a
real `.sqlite` store -- this module is about the LOS-sampling loop's own
logic (absence handling, blocking-vs-clear), not about the store's grid
internals, which are covered by `test_store_reader.py`.
"""

from __future__ import annotations

import sqlite3

import pytest

from query import line_of_sight

_FAKE_CONN = sqlite3.connect(":memory:")


def test_line_of_sight_clear_over_flat_terrain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(line_of_sight, "sample_grid", lambda conn, kind, x, z: 0.0)

    observer = (0.0, 0.0, 500.0)
    target = (10000.0, 0.0, 500.0)

    assert (
        line_of_sight.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target) is True
    )


def test_line_of_sight_blocked_by_ridge_between_observer_and_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_sample_grid(conn: object, kind: str, x: float, z: float) -> float:
        return 2000.0 if 4000.0 < x < 6000.0 else 0.0

    monkeypatch.setattr(line_of_sight, "sample_grid", fake_sample_grid)

    observer = (0.0, 0.0, 100.0)
    target = (10000.0, 0.0, 100.0)

    assert (
        line_of_sight.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target)
        is False
    )


def test_line_of_sight_clear_when_ridge_is_below_sightline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A hill exists but is well under the straight sightline between two
    # high-altitude endpoints -- must not be treated as blocking.
    def fake_sample_grid(conn: object, kind: str, x: float, z: float) -> float:
        return 200.0 if 4000.0 < x < 6000.0 else 0.0

    monkeypatch.setattr(line_of_sight, "sample_grid", fake_sample_grid)

    observer = (0.0, 0.0, 3000.0)
    target = (10000.0, 0.0, 3000.0)

    assert (
        line_of_sight.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target) is True
    )


def test_line_of_sight_treats_missing_elevation_as_non_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(line_of_sight, "sample_grid", lambda conn, kind, x, z: None)

    observer = (0.0, 0.0, 100.0)
    target = (10000.0, 0.0, 100.0)

    assert (
        line_of_sight.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target) is True
    )


def test_line_of_sight_clear_when_target_buried_by_grid_error_within_tolerance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the `plans/missed-aaa-detection/debug.md` reproduction: a target
    at DCS-truth altitude, sitting under a grid cell that overestimates
    ground height by roughly M7's own recorded SRTM stddev (11.52 m), must
    read as visible from a close, steep attack-pass geometry -- not
    permanently "underground" from every angle.

    The excess actually exercised at the deciding sample is much smaller
    than the nominal 11.5 m grid overestimate this test is framed around --
    not a test artifact, but the real mechanism the debug note reproduced.
    Observer/target altitudes differ (700.0 vs. 500.0), so `sightline_alt`
    interpolates between them and converges toward the target's own lower
    altitude near `t=1`; the sample nearest the target (`i=19`, `t=0.95`)
    sees `terrain_m=511.5` against `sightline_alt=700.0+(500.0-700.0)*0.95=
    510.0`, an excess of only `1.5` m, not `11.5`. This test therefore does
    not pin `_TERRAIN_TOLERANCE_M` at any particular value above ~1.5 m --
    see `test_line_of_sight_clear_when_terrain_excess_is_just_inside_
    tolerance` and its blocked counterpart below for the test that pins the
    actual 12.0 m boundary via an undiluted (equal-altitude) sightline.
    """
    target_x = 10000.0
    target_true_alt = 500.0
    grid_overestimate_m = 11.5  # M7's own recorded SRTM stddev, not a worst case

    def fake_sample_grid(conn: object, kind: str, x: float, z: float) -> float:
        return (
            target_true_alt + grid_overestimate_m if abs(x - target_x) < 500.0 else 0.0
        )

    monkeypatch.setattr(line_of_sight, "sample_grid", fake_sample_grid)

    # Close, steep attack-pass geometry -- the case the debug note shows
    # flipping to a false "blocked" verdict without the tolerance.
    observer = (9000.0, 0.0, 700.0)
    target = (target_x, 0.0, target_true_alt)

    assert (
        line_of_sight.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target) is True
    )


def test_line_of_sight_still_blocked_by_a_ridge_well_beyond_tolerance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A coarse omniscience-hole guard only: proves a ridge that clears the
    sightline by well more than `_TERRAIN_TOLERANCE_M` (12.0 m) still
    masks. It does **not** pin the boundary -- 50 m is >4x the 12.0 m
    tolerance, so this test passes identically for any
    `_TERRAIN_TOLERANCE_M` from 0 up to ~49 m and would not catch a
    miscalibration anywhere in that range (`plans/missed-aaa-detection/
    review.md`). The boundary itself -- excess just inside vs. just
    outside 12.0 m -- is pinned by
    `test_line_of_sight_clear_when_terrain_excess_is_just_inside_tolerance`
    and `test_line_of_sight_blocked_when_terrain_excess_is_just_outside_
    tolerance` below. Kept anyway: a ridge that towers over the tolerance
    and still fails to block would be a much larger break than a
    miscalibrated boundary, and this is a cheap, obviously-correct check
    for that.
    """

    def fake_sample_grid(conn: object, kind: str, x: float, z: float) -> float:
        return 150.0 if 4000.0 < x < 6000.0 else 0.0

    monkeypatch.setattr(line_of_sight, "sample_grid", fake_sample_grid)

    observer = (0.0, 0.0, 100.0)
    target = (10000.0, 0.0, 100.0)

    assert (
        line_of_sight.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target)
        is False
    )


def test_line_of_sight_clear_when_terrain_excess_is_just_inside_tolerance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the boundary itself, unlike the two guard tests above: observer
    and target share the same altitude, so `sightline_alt` is the constant
    `700.0` at every sample and the sightline-to-target interpolation
    dilution that shrinks the within-tolerance regression test's exercised
    excess to ~1.5 m (see that test's docstring) cannot occur here -- the
    terrain excess at every sample in the ridge band is exactly
    `terrain_m - sightline_alt = 711.9 - 700.0 = 11.9`, just inside
    `_TERRAIN_TOLERANCE_M` (12.0 m). A `_TERRAIN_TOLERANCE_M` lowered to
    anything below 11.9 m would flip this to blocked.
    """

    def fake_sample_grid(conn: object, kind: str, x: float, z: float) -> float:
        return 711.9 if 4000.0 < x < 6000.0 else 0.0

    monkeypatch.setattr(line_of_sight, "sample_grid", fake_sample_grid)

    observer = (0.0, 0.0, 700.0)
    target = (10000.0, 0.0, 700.0)

    assert (
        line_of_sight.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target) is True
    )


def test_line_of_sight_clear_is_reciprocal(monkeypatch: pytest.MonkeyPatch) -> None:
    """`plans/dcs-driven-los/plan.md` §3a: the offline primitive's own
    reciprocity, on its own terms -- `los(a, b) == los(b, a)` for a
    deterministic function of a symmetric sightline. This is a property
    of this function, not a claim about DCS: the live reciprocity the
    engagement term's justification rests on is a separate, unmeasured
    assumption (that plan's own Risks section), not what this test
    exercises."""

    def fake_sample_grid(conn: object, kind: str, x: float, z: float) -> float:
        return 2000.0 if 4000.0 < x < 6000.0 else 0.0

    monkeypatch.setattr(line_of_sight, "sample_grid", fake_sample_grid)

    a = (0.0, 0.0, 100.0)
    b = (10000.0, 0.0, 100.0)

    assert line_of_sight.line_of_sight_clear(
        _FAKE_CONN, "Syria", a, b
    ) == line_of_sight.line_of_sight_clear(_FAKE_CONN, "Syria", b, a)


def test_raising_the_observer_never_turns_clear_into_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`plans/dcs-driven-los/plan.md` §3a: monotonicity -- raising the
    observer's altitude, holding everything else fixed, can only ever
    straighten a grazing sightline over an obstruction, never introduce a
    new one. A clear verdict at the lower altitude must stay clear at the
    higher one."""

    def fake_sample_grid(conn: object, kind: str, x: float, z: float) -> float:
        return 150.0 if 4000.0 < x < 6000.0 else 0.0

    monkeypatch.setattr(line_of_sight, "sample_grid", fake_sample_grid)

    target = (10000.0, 0.0, 100.0)
    low_observer = (0.0, 0.0, 200.0)
    high_observer = (0.0, 0.0, 2000.0)

    assert (
        line_of_sight.line_of_sight_clear(_FAKE_CONN, "Syria", low_observer, target)
        is True
    )
    assert (
        line_of_sight.line_of_sight_clear(_FAKE_CONN, "Syria", high_observer, target)
        is True
    )


def test_line_of_sight_blocked_when_terrain_excess_is_just_outside_tolerance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other side of the same boundary as the test above, undiluted for
    the same reason (equal observer/target altitude, constant
    `sightline_alt = 700.0`): the terrain excess at every sample in the
    ridge band is exactly `712.1 - 700.0 = 12.1`, just outside
    `_TERRAIN_TOLERANCE_M` (12.0 m). A `_TERRAIN_TOLERANCE_M` raised to
    anything above 12.1 m would flip this to clear. Together with the test
    above, a meaningful change to the constant in either direction fails
    one of these two.
    """

    def fake_sample_grid(conn: object, kind: str, x: float, z: float) -> float:
        return 712.1 if 4000.0 < x < 6000.0 else 0.0

    monkeypatch.setattr(line_of_sight, "sample_grid", fake_sample_grid)

    observer = (0.0, 0.0, 700.0)
    target = (10000.0, 0.0, 700.0)

    assert (
        line_of_sight.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target)
        is False
    )
