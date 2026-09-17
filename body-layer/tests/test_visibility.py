"""Tests for `perception.visibility.check_visibility`.

Hand-authored fixtures, mirroring `test_association.py`'s pattern --
`WorldObjectCandidate` instances are built directly with DCS-native x/z, no
`from_dict`/coordinate-conversion involved.

`visibility.line_of_sight_clear` (imported into `perception.visibility`'s
own namespace) is monkeypatched to always return `True` by an autouse
fixture, so these tests exercise the cockpit-mask/angular-radius-tier gates
in isolation without a real world-model `.sqlite`. `geometry.py`'s own LOS
sampling-loop logic is already covered by `test_geometry.py`; the dedicated
LOS test below only confirms `check_visibility` correctly gates on that
function's result, not the LOS math itself.

The cockpit-mask integration tests below (`plans/cockpit-visibility/
plan.md`) exercise `check_visibility`'s wiring against the real, shipped
`COCKPIT_MASKS[STATION_CO_PILOT]` -- unlike `test_cockpit_mask.py`'s pure
mechanism tests, they cannot be fully number-agnostic (this is the one
place that shipped table actually gets exercised end-to-end). They are
written to hold under both commit 1's placeholder table and commit 2's
derived one by using depression/azimuth combinations well clear of either
table's plausible boundary values -- near-zero depression near the nose
(trivially visible under any reasonable table), a steep depression well
abeam (trivially rejected), a rear-hemisphere azimuth no plausible
`rear_cutoff_deg` would admit, and a bank delta large enough to swing a
straight-down contact from `azimuth=0`/deep depression to `azimuth=90`/near
level, not tied to any specific number in the table itself.
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


def _ownship(
    *,
    heading_true_deg: float = 0.0,
    pitch_deg: float = 0.0,
    bank_deg: float = 0.0,
    alt_m: float = 500.0,
) -> OwnshipState:
    return OwnshipState(
        t_sim=100.0,
        x=0.0,
        z=0.0,
        alt_m=alt_m,
        heading_true_deg=heading_true_deg,
        pitch_deg=pitch_deg,
        bank_deg=bank_deg,
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


def test_forward_and_below_candidate_at_a_mild_depression_is_visible() -> None:
    # Dead ahead (body azimuth 0), a mild 10 deg depression -- comfortably
    # under any plausible "steep ahead" allowance (see module docstring).
    ownship = _ownship(heading_true_deg=0.0)
    horizontal_range = 1000.0
    depression_deg = 10.0
    candidate = _candidate(
        "Infantry",
        x=horizontal_range,
        z=0.0,
        alt_m=ownship.alt_m - horizontal_range * math.tan(math.radians(depression_deg)),
    )

    assert check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE) is not None


def test_same_depression_abeam_is_rejected() -> None:
    # Same geometry as the forward test above, only rotated to directly
    # abeam (body azimuth 90) with a much steeper 40 deg depression -- well
    # past any plausible "abeam" allowance, which this project's screenshot
    # evidence (plan D7) puts in the shallow single digits to low teens.
    ownship = _ownship(heading_true_deg=0.0)
    horizontal_range = 1000.0
    depression_deg = 40.0
    candidate = _candidate(
        "Infantry",
        x=0.0,
        z=horizontal_range,
        alt_m=ownship.alt_m - horizontal_range * math.tan(math.radians(depression_deg)),
    )

    assert check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE) is None


def test_rear_hemisphere_candidate_is_blocked_regardless_of_elevation() -> None:
    # Body azimuth 150 -- past any plausible rear_cutoff_deg -- level with
    # ownship (elevation 0, i.e. not even a steep look), still blocked
    # entirely per "no visibility to rear hemisphere"
    # (docs/concept/state-transitions.jpg).
    ownship = _ownship(heading_true_deg=0.0)
    bearing_rad = math.radians(150.0)
    candidate = _candidate(
        "Infantry",
        x=500.0 * math.cos(bearing_rad),
        z=500.0 * math.sin(bearing_rad),
    )

    assert check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE) is None


def test_candidate_rejected_level_becomes_visible_when_banked_toward_it() -> None:
    # A contact directly below ownship is deep in the "straight down"
    # depression (~90 deg) when level -- rejected under any plausible
    # nose-ahead allowance. Rolling 90 deg right rotates that same contact
    # to body azimuth ~90/elevation ~0 (`test_geometry.py`'s
    # `test_body_relative_direction_bank_rotates_elevation_into_azimuth`
    # derives this exactly) -- a near-level abeam look, which any table
    # shaped like this plan's D2 admits. This is the whole reason bank is
    # read from telemetry at all (module docstring / plan feasibility
    # section): a heading-only cone could never produce this transition.
    candidate = _candidate("Infantry", x=0.0, z=0.0, alt_m=0.0)

    level = _ownship(heading_true_deg=0.0, bank_deg=0.0, alt_m=1000.0)
    banked_right = _ownship(heading_true_deg=0.0, bank_deg=90.0, alt_m=1000.0)

    assert check_visibility(level, candidate, _FAKE_CONN, _THEATRE) is None
    assert check_visibility(banked_right, candidate, _FAKE_CONN, _THEATRE) is not None


def test_terrain_los_blocked_drops_an_otherwise_visible_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(visibility, "line_of_sight_clear", lambda *a, **k: False)
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=500.0, z=0.0)

    assert check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE) is None


def test_steep_depression_inside_the_old_cone_is_now_rejected() -> None:
    """The case that discriminates this mask from the azimuth cone it
    replaced.

    Review (2026-09-17) found three of the four mask integration tests sat
    in regions where the old `_within_fov` and the new mask agree -- the
    abeam and rear cases are outside the old +/-60 deg cone, so the old code
    rejected them too. A test that cannot fail against the pre-change code
    does not demonstrate the change.

    Body azimuth 30 deg is *inside* the old cone, so the old gate passed it
    regardless of elevation. The measured mask allows 22 deg of depression
    flat across 0-60 deg, so the two candidates below -- same azimuth, same
    horizontal range, differing only in depression -- straddle that limit.

    Discriminating on elevation rather than azimuth is deliberate: the
    measured forward allowance is *constant* out to 60 deg, so azimuth alone
    separates nothing inside the old cone. Elevation is precisely what the
    old gate lacked.
    """
    ownship = _ownship(heading_true_deg=0.0)
    horizontal_range = 600.0
    azimuth_deg = 30.0
    x = horizontal_range * math.cos(math.radians(azimuth_deg))
    z = horizontal_range * math.sin(math.radians(azimuth_deg))

    shallow = _candidate(
        "Infantry",
        x=x,
        z=z,
        alt_m=ownship.alt_m - horizontal_range * math.tan(math.radians(12.0)),
    )
    assert check_visibility(ownship, shallow, _FAKE_CONN, _THEATRE) is not None

    steep = _candidate(
        "Infantry",
        x=x,
        z=z,
        alt_m=ownship.alt_m - horizontal_range * math.tan(math.radians(32.0)),
    )
    assert check_visibility(ownship, steep, _FAKE_CONN, _THEATRE) is None
