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
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC, Optic
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
    # infantry: size 1.8 m, medres threshold = 1.8 / 0.014 * 4.0 = 514.29 m
    # (recalibrated 2026-09-17 from the screenshot ladder; was 900 m under
    # the old 0.008 constant).
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=513.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.range_m == pytest.approx(513.0)
    assert result.bearing_deg == pytest.approx(0.0)
    assert result.tier == "medres"
    assert result.confidence == NAKED_EYE_VISIBILITY_CONFIDENCE


def test_infantry_well_inside_hires_tier_range_achieves_hires_tier() -> None:
    # infantry: size 1.8 m, hires threshold = 1.8 / 0.028 * 4.0 = 257.14 m
    # (recalibrated 2026-09-17; was 360 m under the old 0.02 constant). A
    # candidate inside it resolves to the tighter achieved tier regardless
    # of where the gate itself sits.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=250.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "hires"
    assert result.confidence == NAKED_EYE_TYPE_CONFIDENCE


def test_infantry_just_outside_hires_tier_range_achieves_medres_tier() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=258.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "medres"
    assert result.confidence == NAKED_EYE_VISIBILITY_CONFIDENCE


def test_infantry_just_inside_lowres_tier_range_is_visible() -> None:
    # `plans/classification-refinement/plan.md` Stage 7: the gate moved
    # from `medres` to `lowres`. Infantry: size 1.8 m, lowres*4 threshold =
    # 1.8 / 0.003 * 4.0 = 2400 m (recalibrated 2026-09-17; was 1674.42 m)
    # -- well below NAKED_EYE_RANGE_CAP_M, so the size curve (not the cap)
    # still does the discriminating here. A
    # candidate this far out achieves only the `lowres` (presence) tier.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=1674.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "lowres"
    assert result.confidence == NAKED_EYE_PRESENCE_CONFIDENCE


def test_infantry_just_outside_lowres_tier_range_is_not_visible() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=2401.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is None


def test_ural_truck_gate_is_bound_by_the_size_curve_not_the_range_cap() -> None:
    # Ural truck: size 6 m, lowres*4 threshold = 6 / 0.003 * 4.0 = 8000 m,
    # comfortably inside NAKED_EYE_RANGE_CAP_M (10000 m since the
    # 2026-09-17 calibration). Under the old constants this was the
    # opposite -- a 5581 m threshold against a 5000 m cap, so the cap bound
    # a truck-sized object and flattened the size curve. Raising the cap
    # and loosening `lowres` together handed the discriminating back to the
    # size curve for everything up to ship-sized (see the ship test below,
    # where the cap still binds and should).
    ownship = _ownship(heading_true_deg=0.0)
    inside = _candidate("Ural-4320", x=7999.0, z=0.0)
    beyond = _candidate("Ural-4320", x=8001.0, z=0.0)

    assert check_visibility(ownship, inside, _FAKE_CONN, _THEATRE) is not None
    assert check_visibility(ownship, beyond, _FAKE_CONN, _THEATRE) is None


def test_armored_vehicle_is_visible_at_the_farthest_photographed_range() -> None:
    # The calibration ladder's outer datapoint: a row of 6-7 m ground
    # vehicles was plainly visible through binoculars at 8.89 km. The
    # pre-calibration constants rejected that outright (a 7 m object gated
    # at 6511 m, and the 5000 m cap cut it shorter still), which is a
    # no-omniscience violation in the direction that gets overlooked --
    # Petrovich failing to see what the player can plainly see.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("T-72B", x=8890.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "lowres"


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


def test_banking_right_lifts_a_right_side_contact_but_banking_left_does_not() -> None:
    """Pins the bank *direction* at the visibility-gate level.

    The sign is already pinned once, in `test_geometry.py`'s
    `test_body_relative_direction_bank_rotates_elevation_into_azimuth`,
    which asserts a signed azimuth of +90 and does fail if the rotation's
    bank sign is inverted (verified by mutation, 2026-09-17). What was *not*
    covered is this gate: the sibling test here,
    `test_candidate_rejected_level_becomes_visible_when_banked_toward_it`,
    uses a contact directly below ownship, which rotates to azimuth ~90
    under a roll of either sign -- and `is_visible` folds azimuth through
    `abs()` (D5), so it passes identically with the sign inverted. It proves
    bank is *read*, not that it is read the right way round.

    This one is asymmetric: the contact sits abeam to the **right** and
    below, too steep for the abeam allowance when level. Rolling right must
    lift it into view; rolling left must bury it further. Both the rotation
    and the mask have to agree on handedness for that to hold.

    The convention itself -- positive bank = right bank -- is the user's,
    confirmed against DCS on 2026-09-17 (`OwnshipState`). No test can verify
    that wire contract, which is exactly why the confirmation was needed;
    these tests only hold the code consistent with it.
    """
    # 600 m abeam right, 200 m below: ~18.4 deg depression, past the ~10 deg
    # the measured table allows at azimuth 90.
    candidate = _candidate("Infantry", x=0.0, z=600.0, alt_m=300.0)

    level = _ownship(heading_true_deg=0.0, bank_deg=0.0, alt_m=500.0)
    banked_right = _ownship(heading_true_deg=0.0, bank_deg=30.0, alt_m=500.0)
    banked_left = _ownship(heading_true_deg=0.0, bank_deg=-30.0, alt_m=500.0)

    assert check_visibility(level, candidate, _FAKE_CONN, _THEATRE) is None
    assert check_visibility(banked_right, candidate, _FAKE_CONN, _THEATRE) is not None
    assert check_visibility(banked_left, candidate, _FAKE_CONN, _THEATRE) is None


# --- detection-cones slice 1 (`plans/detection-cones-slice1/plan.md`) ---
#
# `check_visibility` gained a keyword-only `optic` parameter defaulting to
# `BINOCULAR_OPTIC`. The regression test immediately below is the one that
# actually enforces "must not change today's default detection" -- a
# calibration sortie is flying and pre/post-slice-1 data must stay
# comparable (plan's "Context this plan builds on").


def test_default_optic_argument_matches_pre_slice1_behaviour() -> None:
    """`check_visibility(...)` called with no `optic` argument must produce
    byte-identical results to before this slice existed, across a handful
    of the fixture cases already exercised above -- a `hires`-tier case, a
    `medres`-tier case, and an out-of-range case. This is the regression
    guard the plan calls for explicitly, not just documentation of intent:
    it fails if the default ever silently stops being `BINOCULAR_OPTIC`, or
    if the new FOV gate ever rejects a boresight-forward candidate it must
    not."""
    ownship = _ownship(heading_true_deg=0.0)

    hires_candidate = _candidate("Infantry", x=250.0, z=0.0)
    medres_candidate = _candidate("Infantry", x=513.0, z=0.0)
    out_of_range_candidate = _candidate("Infantry", x=10_001.0, z=0.0)

    hires_result = check_visibility(ownship, hires_candidate, _FAKE_CONN, _THEATRE)
    assert hires_result is not None
    assert hires_result.tier == "hires"
    assert hires_result.confidence == NAKED_EYE_TYPE_CONFIDENCE
    assert hires_result.range_m == pytest.approx(250.0)
    assert hires_result.bearing_deg == pytest.approx(0.0)

    medres_result = check_visibility(ownship, medres_candidate, _FAKE_CONN, _THEATRE)
    assert medres_result is not None
    assert medres_result.tier == "medres"
    assert medres_result.confidence == NAKED_EYE_VISIBILITY_CONFIDENCE

    assert (
        check_visibility(ownship, out_of_range_candidate, _FAKE_CONN, _THEATRE) is None
    )

    # Explicitly passing BINOCULAR_OPTIC must match the no-argument call
    # exactly -- pinning that the default really is BINOCULAR_OPTIC, not
    # merely something that happens to behave like it today.
    explicit_result = check_visibility(
        ownship, hires_candidate, _FAKE_CONN, _THEATRE, optic=BINOCULAR_OPTIC
    )
    assert explicit_result == hires_result


def test_synthetic_narrow_fov_optic_rejects_candidate_outside_its_cone() -> None:
    narrow_optic = Optic(name="test_narrow", magnification=4.0, fov_half_angle_deg=5.0)
    ownship = _ownship(heading_true_deg=0.0)
    # 30 deg off boresight, well outside a 5 deg half-angle FOV, but well
    # within the cockpit mask (near-zero depression near the nose).
    off_axis_candidate = _candidate("Infantry", x=100.0, z=57.735)

    assert (
        check_visibility(
            ownship, off_axis_candidate, _FAKE_CONN, _THEATRE, optic=narrow_optic
        )
        is None
    )
    # The same candidate is admitted under the default (unrestricted) optic
    # -- confirms the rejection above is the FOV gate, not some other gate
    # coincidentally firing.
    assert (
        check_visibility(ownship, off_axis_candidate, _FAKE_CONN, _THEATRE) is not None
    )


def test_synthetic_narrow_fov_optic_admits_candidate_inside_its_cone() -> None:
    narrow_optic = Optic(name="test_narrow", magnification=4.0, fov_half_angle_deg=5.0)
    ownship = _ownship(heading_true_deg=0.0)
    # Dead ahead, well inside any plausible FOV.
    on_axis_candidate = _candidate("Infantry", x=250.0, z=0.0)

    result = check_visibility(
        ownship, on_axis_candidate, _FAKE_CONN, _THEATRE, optic=narrow_optic
    )
    assert result is not None


def test_higher_magnification_optic_extends_the_range_threshold() -> None:
    """`size_m / threshold_rad * M` -- the range threshold scales linearly
    with magnification. `UNAIDED_OPTIC` (M=1.0) is used here as the "no
    optic" reference point against `BINOCULAR_OPTIC` (M=4.0): a candidate
    within the binocular gate's own outer (`lowres`) threshold but beyond
    the unaided gate's threshold is admitted under one and rejected under
    the other at the exact same range."""
    ownship = _ownship(heading_true_deg=0.0)
    # Infantry: size 1.8 m, gating tier is `lowres` (0.003 rad).
    # Unaided (M=1.0) lowres threshold: 1.8 / 0.003 * 1 = 600 m.
    # Binocular (M=4.0) lowres threshold: 1.8 / 0.003 * 4 = 2400 m.
    candidate = _candidate("Infantry", x=610.0, z=0.0)

    binocular_result = check_visibility(
        ownship, candidate, _FAKE_CONN, _THEATRE, optic=BINOCULAR_OPTIC
    )
    assert binocular_result is not None
    assert binocular_result.tier == "lowres"

    unaided_result = check_visibility(
        ownship, candidate, _FAKE_CONN, _THEATRE, optic=UNAIDED_OPTIC
    )
    assert unaided_result is None
