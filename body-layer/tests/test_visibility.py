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
    NAKED_EYE_PRESENCE_CONFIDENCE,
    NAKED_EYE_RANGE_CAP_M,
    NAKED_EYE_TYPE_CONFIDENCE,
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
        object_id=1, object_type=object_type, x=x, z=z, alt_m=alt_m, is_ownship=False
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


def test_infantry_well_inside_hires_tier_range_achieves_hires_tier() -> None:
    # infantry: size 1.8 m, hires threshold = 1.8 / 0.02 * 4.0 = 360 m
    # (`plans/classification-refinement/plan.md` Stage 6 worked table). The
    # gate itself stays at `medres` this stage, but a candidate this close
    # now resolves to the tighter achieved tier.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=350.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "hires"
    assert result.confidence == NAKED_EYE_TYPE_CONFIDENCE


def test_infantry_just_outside_hires_tier_range_achieves_medres_tier() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=361.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "medres"
    assert result.confidence == NAKED_EYE_VISIBILITY_CONFIDENCE


def test_infantry_just_inside_lowres_tier_range_is_visible() -> None:
    # `plans/classification-refinement/plan.md` Stage 7: the gate moved
    # from `medres` to `lowres`. Infantry: size 1.8 m, lowres*4 threshold =
    # 1.8 / 0.0043 * 4.0 = 1674.42 m -- well below NAKED_EYE_RANGE_CAP_M, so
    # the size curve (not the cap) still does the discriminating here. A
    # candidate this far out achieves only the `lowres` (presence) tier.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=1674.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "lowres"
    assert result.confidence == NAKED_EYE_PRESENCE_CONFIDENCE


def test_infantry_just_outside_lowres_tier_range_is_not_visible() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=1675.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is None


def test_ural_truck_gate_now_binds_at_the_range_cap_under_lowres() -> None:
    # Ural truck: size 6 m, lowres*4 threshold = 6 / 0.0043 * 4.0 =
    # 5581.4 m, which now exceeds NAKED_EYE_RANGE_CAP_M (5000 m) -- unlike
    # under the pre-Stage-7 `medres` gate (3000 m threshold, well below the
    # cap), the cap is now the binding constraint for a truck-sized object,
    # not the size curve. This is the flattened-size-curve risk the plan's
    # Risks section calls out for Stage 7, not a regression.
    ownship = _ownship(heading_true_deg=0.0)
    inside = _candidate("Ural-4320", x=NAKED_EYE_RANGE_CAP_M, z=0.0)
    beyond = _candidate("Ural-4320", x=NAKED_EYE_RANGE_CAP_M + 100.0, z=0.0)

    assert check_visibility(ownship, inside, _FAKE_CONN, _THEATRE) is not None
    assert check_visibility(ownship, beyond, _FAKE_CONN, _THEATRE) is None


def test_range_cap_binds_for_every_object_the_size_curve_would_let_run_away() -> None:
    # A ship (size 100 m) computes a lowres*4 threshold in the tens of km --
    # absurd -- NAKED_EYE_RANGE_CAP_M is the sanity bound that stops it, same
    # as trucks-and-up now that the gate is `lowres` (see the Ural test
    # above).
    ownship = _ownship(heading_true_deg=0.0)
    at_cap = _candidate("MOLNIYA", x=NAKED_EYE_RANGE_CAP_M, z=0.0)
    beyond_cap = _candidate("MOLNIYA", x=NAKED_EYE_RANGE_CAP_M + 100.0, z=0.0)

    assert check_visibility(ownship, at_cap, _FAKE_CONN, _THEATRE) is not None
    assert check_visibility(ownship, beyond_cap, _FAKE_CONN, _THEATRE) is None


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
