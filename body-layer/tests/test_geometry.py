"""Tests for `perception.geometry`'s bearing/range/LOS helpers.

World-model calls (`describe_position`, `sample_grid`) are monkeypatched
rather than exercised against a real `.sqlite` store -- this module is
about the geometry math and the LOS-sampling loop's own logic (absence
handling, blocking-vs-clear), not about world-model's store internals,
which are covered by that subproject's own tests.
"""

from __future__ import annotations

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


def test_line_of_sight_clear_over_flat_terrain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(geometry, "sample_grid", lambda conn, kind, x, z: 0.0)

    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    target = GeoPosition(x=10000.0, z=0.0, alt_m=500.0)

    assert geometry.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target) is True


def test_line_of_sight_blocked_by_ridge_between_observer_and_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_sample_grid(conn: object, kind: str, x: float, z: float) -> float:
        return 2000.0 if 4000.0 < x < 6000.0 else 0.0

    monkeypatch.setattr(geometry, "sample_grid", fake_sample_grid)

    observer = GeoPosition(x=0.0, z=0.0, alt_m=100.0)
    target = GeoPosition(x=10000.0, z=0.0, alt_m=100.0)

    assert geometry.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target) is False


def test_line_of_sight_clear_when_ridge_is_below_sightline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A hill exists but is well under the straight sightline between two
    # high-altitude endpoints -- must not be treated as blocking.
    def fake_sample_grid(conn: object, kind: str, x: float, z: float) -> float:
        return 200.0 if 4000.0 < x < 6000.0 else 0.0

    monkeypatch.setattr(geometry, "sample_grid", fake_sample_grid)

    observer = GeoPosition(x=0.0, z=0.0, alt_m=3000.0)
    target = GeoPosition(x=10000.0, z=0.0, alt_m=3000.0)

    assert geometry.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target) is True


def test_line_of_sight_treats_missing_elevation_as_non_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(geometry, "sample_grid", lambda conn, kind, x, z: None)

    observer = GeoPosition(x=0.0, z=0.0, alt_m=100.0)
    target = GeoPosition(x=10000.0, z=0.0, alt_m=100.0)

    assert geometry.line_of_sight_clear(_FAKE_CONN, "Syria", observer, target) is True
