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

from perception import object_model, visibility
from perception.association import WorldObjectCandidate
from perception.object_model import ObjectTypeProfile
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

#: A generous, unrestricted stand-in optic for tests whose purpose is the
#: cockpit-mask/geometry gates, not range or field-of-view magnitude --
#: `plans/detection-cones-slice1/plan.md`'s final scope change moved the
#: default optic to `UNAIDED_OPTIC` (magnification 1.0, a much tighter
#: range gate than the binocular default these tests were originally
#: written against), so a mask-focused test that happens to place its
#: candidate beyond the new default's range threshold would silently
#: start testing the range gate instead of the mask -- passing this optic
#: explicitly keeps those tests isolated to the gate they name.
_MASK_ONLY_OPTIC = Optic(
    name="test_mask_only", magnification=100.0, fov_half_angle_deg=None
)


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
    object_type: str,
    *,
    x: float,
    z: float,
    alt_m: float = 500.0,
    heading_true_deg: float | None = None,
) -> WorldObjectCandidate:
    return WorldObjectCandidate(
        object_id=1,
        object_type=object_type,
        x=x,
        z=z,
        alt_m=alt_m,
        is_ownship=False,
        heading_true_deg=heading_true_deg,
    )


def test_infantry_just_inside_medres_tier_range_is_visible() -> None:
    # infantry: size 1.8 m, medres threshold = 1.8 / 0.014 * 1.0 = 128.57 m.
    # **RECOMPUTED FOR THE DEFAULT-OPTIC CHANGE (2026-09-20)**: the default
    # optic is now UNAIDED_OPTIC (M=1.0), not BINOCULAR_OPTIC -- this
    # value went 513 m (M=4.0) -> 1027 m (a same-session M=8.0 excursion)
    # -> 128 m now, tracking the default multiplier's own round trip (see
    # visibility.py's BINOCULAR_RANGE_MULTIPLIER docstring). Formula and
    # angular-radius constants unchanged throughout -- only the default
    # optic's magnification moved.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=128.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.range_m == pytest.approx(128.0)
    assert result.bearing_deg == pytest.approx(0.0)
    assert result.tier == "medres"
    assert result.confidence == NAKED_EYE_VISIBILITY_CONFIDENCE


def test_infantry_well_inside_hires_tier_range_achieves_hires_tier() -> None:
    # infantry: size 1.8 m, hires threshold = 1.8 / 0.028 * 1.0 = 64.29 m
    # (default optic is now UNAIDED_OPTIC, M=1.0 -- see the medres test
    # above for the full round-trip note). A candidate inside it resolves
    # to the tighter achieved tier regardless of where the gate itself
    # sits.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=50.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "hires"
    assert result.confidence == NAKED_EYE_TYPE_CONFIDENCE


def test_infantry_just_outside_hires_tier_range_achieves_medres_tier() -> None:
    # Just beyond the default optic's (UNAIDED_OPTIC, M=1.0) hires
    # threshold of 64.29 m, still inside its medres threshold (128.57 m).
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=66.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "medres"
    assert result.confidence == NAKED_EYE_VISIBILITY_CONFIDENCE


def test_infantry_just_inside_lowres_tier_range_is_visible() -> None:
    # `plans/classification-refinement/plan.md` Stage 7: the gate moved
    # from `medres` to `lowres`. Infantry: size 1.8 m, lowres threshold at
    # the default optic (UNAIDED_OPTIC, M=1.0) = 1.8 / 0.003 * 1.0 = 600 m
    # -- well below NAKED_EYE_RANGE_CAP_M, so the size curve (not the cap)
    # still does the discriminating here for an object this small. A
    # candidate this far out achieves only the `lowres` (presence) tier.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=599.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "lowres"
    assert result.confidence == NAKED_EYE_PRESENCE_CONFIDENCE


def test_infantry_just_outside_lowres_tier_range_is_not_visible() -> None:
    # Just beyond the default optic's (UNAIDED_OPTIC, M=1.0) lowres
    # threshold of 600 m.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=601.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is None


def test_ural_truck_gate_is_bound_by_the_size_curve_not_the_range_cap() -> None:
    """History, since this test's own name and premise have now flipped
    twice in the same session (`plans/detection-cones-slice1/plan.md`):

    - At the original `BINOCULAR_RANGE_MULTIPLIER = 4.0` (binocular
      default): lowres threshold `6 / 0.003 * 4.0 = 8000 m`, inside the
      10000 m cap -- size curve discriminates. This test's original name
      and form.
    - At the same-session `M = 8.0` excursion (still binocular default):
      `6 / 0.003 * 8.0 = 16000 m`, past the cap -- the cap discriminates
      instead. The test was renamed and rewritten to match.
    - **Now (2026-09-20, final scope change)**: the *default* optic moved
      to `UNAIDED_OPTIC` (M=1.0), not the multiplier. At M=1.0,
      `6 / 0.003 * 1.0 = 2000 m`, again well inside the cap -- the size
      curve discriminates again, for the default path. Renamed back to
      its original name because that is, once more, an accurate
      description of what it demonstrates -- though the reason (a
      different default optic, not a restored multiplier) differs from
      the original.

    `BINOCULAR_OPTIC` (M=4.0, no longer the default) still produces the
    16000 m/no-cap-relief result the M=8.0 excursion found, at a smaller
    magnitude -- `6 / 0.003 * 4.0 = 8000 m`, back inside the cap. So
    unlike the M=8.0 episode, no optic in the current table pushes a Ural
    truck's threshold past the cap any more; that finding does not
    survive into the final state.
    """
    ownship = _ownship(heading_true_deg=0.0)
    inside = _candidate("Ural-4320", x=1999.0, z=0.0)
    beyond = _candidate("Ural-4320", x=2001.0, z=0.0)

    assert check_visibility(ownship, inside, _FAKE_CONN, _THEATRE) is not None
    assert check_visibility(ownship, beyond, _FAKE_CONN, _THEATRE) is None


def test_armored_vehicle_is_visible_at_the_farthest_photographed_range() -> None:
    # The calibration ladder's outer datapoint: a row of 6-7 m ground
    # vehicles was plainly visible through binoculars at 8.89 km. The
    # pre-calibration constants rejected that outright (a 7 m object gated
    # at 6511 m, and the 5000 m cap cut it shorter still), which is a
    # no-omniscience violation in the direction that gets overlooked --
    # Petrovich failing to see what the player can plainly see.
    #
    # **Explicit optic=BINOCULAR_OPTIC as of 2026-09-20**: this candidate
    # is specifically the calibration ladder's *binocular* column ground
    # truth, and the default optic is no longer binoculars (`UNAIDED_OPTIC`
    # is now the default -- see visibility.py's module docstring). Dead
    # ahead (azimuth 0), so BINOCULAR_OPTIC's new field-of-view value
    # (4.25 deg half-angle) does not affect this candidate.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("T-72B", x=8890.0, z=0.0)

    result = check_visibility(
        ownship, candidate, _FAKE_CONN, _THEATRE, optic=BINOCULAR_OPTIC
    )

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

    assert (
        check_visibility(
            ownship, candidate, _FAKE_CONN, _THEATRE, optic=_MASK_ONLY_OPTIC
        )
        is not None
    )


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

    assert (
        check_visibility(
            ownship, candidate, _FAKE_CONN, _THEATRE, optic=_MASK_ONLY_OPTIC
        )
        is None
    )


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

    assert (
        check_visibility(level, candidate, _FAKE_CONN, _THEATRE, optic=_MASK_ONLY_OPTIC)
        is None
    )
    assert (
        check_visibility(
            banked_right, candidate, _FAKE_CONN, _THEATRE, optic=_MASK_ONLY_OPTIC
        )
        is not None
    )


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
    assert (
        check_visibility(ownship, shallow, _FAKE_CONN, _THEATRE, optic=_MASK_ONLY_OPTIC)
        is not None
    )

    steep = _candidate(
        "Infantry",
        x=x,
        z=z,
        alt_m=ownship.alt_m - horizontal_range * math.tan(math.radians(32.0)),
    )
    assert (
        check_visibility(ownship, steep, _FAKE_CONN, _THEATRE, optic=_MASK_ONLY_OPTIC)
        is None
    )


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

    assert (
        check_visibility(level, candidate, _FAKE_CONN, _THEATRE, optic=_MASK_ONLY_OPTIC)
        is None
    )
    assert (
        check_visibility(
            banked_right, candidate, _FAKE_CONN, _THEATRE, optic=_MASK_ONLY_OPTIC
        )
        is not None
    )
    assert (
        check_visibility(
            banked_left, candidate, _FAKE_CONN, _THEATRE, optic=_MASK_ONLY_OPTIC
        )
        is None
    )


# --- detection-cones slice 1 (`plans/detection-cones-slice1/plan.md`) ---
#
# `check_visibility` gained a keyword-only `optic` parameter. Its default
# has moved twice in this one design slice: `BINOCULAR_OPTIC` (the
# original, implicit pre-slice behaviour, M=4.0) -> `BINOCULAR_OPTIC`
# again at an excursion M=8.0 -> **`UNAIDED_OPTIC` (M=1.0), final,
# 2026-09-20.** The final move is not a magnitude tweak but a change of
# *which optic* is the default at all: modelling Petrovich as permanently
# glassed-up -- binocular magnification across the whole cockpit-mask
# envelope, with no field-of-view cost -- was the single biggest source of
# over-detection in this channel (user, 2026-09-20). Real observation is
# naked-eye by default; binoculars are a deliberate, narrower, raised act.
# The test below pins the **current** default explicitly, with a worked
# before/after example dated and reasoned in its own docstring, per this
# change's own instruction not to weaken or silently drop the guard.


def test_default_optic_is_naked_eye() -> None:
    """Pins two things about `check_visibility`'s default `optic`, dated
    2026-09-20 (final scope change of this slice):

    1. **The default is `UNAIDED_OPTIC`, not `BINOCULAR_OPTIC`** -- an
       explicit `optic=UNAIDED_OPTIC` call must produce byte-identical
       results to the no-argument call, for every case below.
    2. **Default detection range shrinks sharply now that the default
       optic is naked-eye (M=1.0), not binoculars** -- demonstrated with
       an Infantry candidate at 300 m. Under `BINOCULAR_OPTIC` at M=4.0
       (this slice's *original* default, before either of this session's
       changes) this range resolved to `medres` (medres threshold
       514.29 m, hires 257.14 m -- 300 m falls between them). Under the
       *current* default, `UNAIDED_OPTIC` (M=1.0), the same geometry
       drops a full tier to `lowres` -- naked-eye's medres threshold at
       this magnification is only 128.57 m, well inside 300 m, while its
       lowres threshold (600 m) still admits it. A candidate picked to be
       genuinely beyond the naked eye's reach (a 601 m case is in
       `test_infantry_just_outside_lowres_tier_range_is_not_visible`,
       above) shows the sharper case -- full loss of detectability, not
       just a tier downgrade. A `hires`-tier case (50 m, still resolves
       under the naked eye) and the hard `NAKED_EYE_RANGE_CAP_M`
       out-of-range case (10001 m, unaffected by any optic) are pinned
       alongside the tier-downgrade case so this test covers the same
       three-case shape the superseded binocular-default guards did.
    """
    ownship = _ownship(heading_true_deg=0.0)

    hires_candidate = _candidate("Infantry", x=50.0, z=0.0)
    downgraded_tier_candidate = _candidate("Infantry", x=300.0, z=0.0)
    out_of_range_candidate = _candidate("Infantry", x=10_001.0, z=0.0)

    hires_result = check_visibility(ownship, hires_candidate, _FAKE_CONN, _THEATRE)
    assert hires_result is not None
    assert hires_result.tier == "hires"
    assert hires_result.confidence == NAKED_EYE_TYPE_CONFIDENCE
    assert hires_result.range_m == pytest.approx(50.0)
    assert hires_result.bearing_deg == pytest.approx(0.0)

    downgraded_result = check_visibility(
        ownship, downgraded_tier_candidate, _FAKE_CONN, _THEATRE
    )
    assert downgraded_result is not None
    assert downgraded_result.tier == "lowres"
    assert downgraded_result.confidence == NAKED_EYE_PRESENCE_CONFIDENCE

    assert (
        check_visibility(ownship, out_of_range_candidate, _FAKE_CONN, _THEATRE) is None
    )

    # Explicitly passing UNAIDED_OPTIC must match every no-argument call
    # exactly -- pinning that the default really is UNAIDED_OPTIC, not
    # merely something that happens to behave like it today.
    for candidate, no_arg_result in (
        (hires_candidate, hires_result),
        (downgraded_tier_candidate, downgraded_result),
    ):
        explicit_result = check_visibility(
            ownship, candidate, _FAKE_CONN, _THEATRE, optic=UNAIDED_OPTIC
        )
        assert explicit_result == no_arg_result
    assert (
        check_visibility(
            ownship,
            out_of_range_candidate,
            _FAKE_CONN,
            _THEATRE,
            optic=UNAIDED_OPTIC,
        )
        is None
    )


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
    with magnification. `UNAIDED_OPTIC` (M=1.0, now the default -- see
    `test_default_optic_is_naked_eye` above) is used here as the reference
    point against `BINOCULAR_OPTIC` (M=4.0 as of 2026-09-20's final
    scope change -- see `visibility.BINOCULAR_RANGE_MULTIPLIER`'s own
    "round trip" docstring): a candidate beyond the unaided gate's outer
    (`lowres`) threshold but within the binocular gate's own `lowres`
    threshold is admitted under one and rejected under the other at the
    exact same range. Dead ahead (azimuth 0), so `BINOCULAR_OPTIC`'s field
    of view (4.25 deg half-angle) does not affect this candidate."""
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


# --- Aspect-aware apparent extent (`plans/aspect-aware-profiles/plan.md`) --


#: A synthetic dimensioned profile (`length_m=10 != width_m=4`), monkeypatched
#: in for a private test-only object_type below so these tests are
#: independent of the real S-300 keyword table -- exercising
#: `check_visibility`'s aspect wiring directly rather than its accidental
#: interaction with real sourced dimensions.
_ASPECT_TEST_OBJECT_TYPE = "AspectTestDimensionedObject"
_ASPECT_TEST_PROFILE = ObjectTypeProfile(
    size_m=10.0, op_class="OP_TEST", length_m=10.0, width_m=4.0, height_m=6.0
)

#: A synthetic tall-mast profile mirroring the real S-300 bug shape:
#: `size_m=5.0` is the old generic-fallback figure a mast used to collapse
#: to before this pass, `height_m=24.0` its real measured height -- kept
#: separate from the real "S-300PS 40B6M tr" keyword row so this test pins
#: the fix mechanically, not by relying on this pass's own dimension
#: sourcing being correct.
_TALL_MAST_TEST_OBJECT_TYPE = "AspectTestTallMast"
_TALL_MAST_TEST_PROFILE = ObjectTypeProfile(
    size_m=5.0, op_class="OP_TEST", length_m=10.0, width_m=3.0, height_m=24.0
)


@pytest.fixture
def dimensioned_profile_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    real_profile_for = object_model.profile_for

    def _fake_profile_for(object_type: str) -> ObjectTypeProfile:
        if object_type == _ASPECT_TEST_OBJECT_TYPE:
            return _ASPECT_TEST_PROFILE
        if object_type == _TALL_MAST_TEST_OBJECT_TYPE:
            return _TALL_MAST_TEST_PROFILE
        return real_profile_for(object_type)

    monkeypatch.setattr(object_model, "profile_for", _fake_profile_for)


def test_broadside_and_nose_on_headings_resolve_to_different_visibility(
    dimensioned_profile_lookup: None,
) -> None:
    # Ownship at the origin heading north; candidate dead ahead (bearing 0
    # deg from the observer) at a fixed range in between the nose-on and
    # broadside lowres thresholds this profile implies:
    #   nose-on (aspect 0):  apparent extent = max(width=4, height=6) = 6,
    #                        lowres threshold = 6 / 0.003 * 1.0 = 2000 m.
    #   broadside (aspect 90): apparent extent = max(length=10, height=6)
    #                        = 10, lowres threshold = 10 / 0.003 * 1.0
    #                        = 3333.3 m.
    # A candidate at 2500 m is beyond the nose-on threshold but within the
    # broadside one -- admitted only when presented broadside.
    ownship = _ownship(heading_true_deg=0.0)
    nose_on = _candidate(
        _ASPECT_TEST_OBJECT_TYPE, x=2500.0, z=0.0, heading_true_deg=180.0
    )
    broadside = _candidate(
        _ASPECT_TEST_OBJECT_TYPE, x=2500.0, z=0.0, heading_true_deg=90.0
    )

    assert check_visibility(ownship, nose_on, _FAKE_CONN, _THEATRE) is None
    broadside_result = check_visibility(ownship, broadside, _FAKE_CONN, _THEATRE)
    assert broadside_result is not None
    assert broadside_result.tier == "lowres"


def test_unknown_heading_reproduces_the_pre_aspect_scalar_behaviour(
    dimensioned_profile_lookup: None,
) -> None:
    # Regression guard (mirrors cones-slice-1's own "must not change the
    # default" pattern): with heading_true_deg=None, apparent_extent_m
    # falls back to plain profile.size_m (10.0) regardless of geometry --
    # exactly what this gate computed before aspect existed. lowres
    # threshold = 10 / 0.003 * 1.0 = 3333.3 m, so a candidate at 2500 m
    # (which the nose-on aspect above rejects) is admitted here.
    ownship = _ownship(heading_true_deg=0.0)
    unknown_heading = _candidate(
        _ASPECT_TEST_OBJECT_TYPE, x=2500.0, z=0.0, heading_true_deg=None
    )

    result = check_visibility(ownship, unknown_heading, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "lowres"


def test_tall_mast_shaped_profile_is_visible_past_its_old_scalar_threshold(
    dimensioned_profile_lookup: None,
) -> None:
    # Pins the S-300 tall-mast fix directly, independent of real sourced
    # dimensions (`_TALL_MAST_TEST_PROFILE` above): under the old,
    # aspect-blind behaviour this object would gate on its size_m=5.0
    # generic-fallback figure (lowres threshold 5/0.003*1=1666.7 m); with
    # real height_m=24.0 wired through apparent_extent_m, the mast's
    # threshold becomes height-dominated at every aspect
    # (max(projected_width, 24.0) >= 24.0), lowres threshold
    # 24/0.003*1=8000 m. A candidate at 3000 m -- past the old threshold,
    # well inside the new one -- is exactly the bug this plan fixes.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate(
        _TALL_MAST_TEST_OBJECT_TYPE, x=3000.0, z=0.0, heading_true_deg=180.0
    )

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "lowres"
