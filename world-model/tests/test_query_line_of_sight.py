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
