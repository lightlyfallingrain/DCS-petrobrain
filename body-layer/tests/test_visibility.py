"""Tests for `perception.visibility.check_visibility`.

Hand-authored fixtures, mirroring `test_association.py`'s pattern --
`WorldObjectCandidate` instances are built directly with DCS-native x/z, no
`from_dict`/coordinate-conversion involved.

`visibility.line_of_sight_clear` (imported into `perception.visibility`'s
own namespace) is monkeypatched to always return `True` by an autouse
fixture, so these tests exercise the FOV/angular-radius-tier gates in
isolation without a real world-model `.sqlite`. `geometry.py`'s own LOS
sampling-loop logic is already covered by `test_geometry.py`; the dedicated
LOS test below only confirms `check_visibility` correctly gates on that
function's result, not the LOS math itself.
"""

from __future__ import annotations

import math
import sqlite3

import pytest

from perception import visibility
from perception.association import WorldObjectCandidate
from perception.source import OwnshipState
from perception.visibility import (
    NAKED_EYE_RANGE_CAP_M,
    NAKED_EYE_VISIBILITY_CONFIDENCE,
    check_visibility,
)

_FAKE_CONN = sqlite3.connect(":memory:")
_THEATRE = "Syria"


@pytest.fixture(autouse=True)
def clear_line_of_sight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(visibility, "line_of_sight_clear", lambda *a, **k: True)


def _ownship(*, heading_true_deg: float = 0.0) -> OwnshipState:
    return OwnshipState(
        t_sim=100.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=heading_true_deg
    )


def _candidate(
    object_type: str, *, x: float, z: float, alt_m: float = 500.0
) -> WorldObjectCandidate:
    return WorldObjectCandidate(
        object_id=1, object_type=object_type, x=x, z=z, alt_m=alt_m
    )


def test_infantry_just_inside_medres_tier_range_is_visible() -> None:
    # infantry: size 1.8 m, threshold = 1.8 / 0.008 * 4.0 = 900 m exactly
    # (plan's Proposed Defaults worked table).
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=899.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.range_m == pytest.approx(899.0)
    assert result.bearing_deg == pytest.approx(0.0)
    assert result.tier == "medres"
    assert result.confidence == NAKED_EYE_VISIBILITY_CONFIDENCE


def test_infantry_just_outside_medres_tier_range_is_not_visible() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=901.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is None


def test_ural_truck_range_cap_binds_before_the_uncapped_tier_threshold() -> None:
    # Ural truck: size 6 m, uncapped medres*4 threshold = 3000 m, but
    # NAKED_EYE_RANGE_CAP_M = 2500 m binds first -- the plan's target
    # behaviour ("truck ~3 km before the cap").
    ownship = _ownship(heading_true_deg=0.0)
    inside_cap = _candidate("Ural-4320", x=2400.0, z=0.0)
    beyond_cap = _candidate("Ural-4320", x=2600.0, z=0.0)

    assert check_visibility(ownship, inside_cap, _FAKE_CONN, _THEATRE) is not None
    assert check_visibility(ownship, beyond_cap, _FAKE_CONN, _THEATRE) is None


def test_candidate_at_exactly_the_range_cap_is_visible() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Ural-4320", x=NAKED_EYE_RANGE_CAP_M, z=0.0)

    assert check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE) is not None


def test_candidate_outside_fov_is_not_visible() -> None:
    # NAKED_EYE_FOV_HALF_WIDTH_DEG = 60 -- directly behind (bearing 180 deg
    # relative to heading 0) is well outside the arc.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=-500.0, z=0.0)

    assert check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE) is None


def test_candidate_at_edge_of_fov_is_visible() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    # Bearing 60 deg from origin, well within infantry's 900 m threshold.
    x = 500.0 * math.cos(math.radians(60.0))
    z = 500.0 * math.sin(math.radians(60.0))
    candidate = _candidate("Infantry", x=x, z=z)

    assert check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE) is not None


def test_candidate_just_outside_fov_is_not_visible() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    x = 500.0 * math.cos(math.radians(61.0))
    z = 500.0 * math.sin(math.radians(61.0))
    candidate = _candidate("Infantry", x=x, z=z)

    assert check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE) is None


def test_fov_window_is_relative_to_ownship_heading() -> None:
    ownship = _ownship(heading_true_deg=90.0)
    east_of_ownship = _candidate("Infantry", x=0.0, z=500.0)

    assert check_visibility(ownship, east_of_ownship, _FAKE_CONN, _THEATRE) is not None


def test_terrain_los_blocked_drops_an_otherwise_visible_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(visibility, "line_of_sight_clear", lambda *a, **k: False)
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=500.0, z=0.0)

    assert check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE) is None
