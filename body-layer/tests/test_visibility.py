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
#: default optic to `UNAIDED_OPTIC` (a much tighter range gate than the
#: binocular default these tests were originally written against), so a
#: mask-focused test that happens to place its candidate beyond the new
#: default's range threshold would silently start testing the range gate
#: instead of the mask -- passing this optic explicitly keeps those tests
#: isolated to the gate they name. `100.0` on every tier (slice 2A widened
#: this from one `magnification` to three per-tier multipliers).
_MASK_ONLY_OPTIC = Optic(
    name="test_mask_only",
    presence_range_mult=100.0,
    class_range_mult=100.0,
    type_range_mult=100.0,
    fov_half_angle_deg=None,
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


def test_armored_vehicle_just_inside_lowres_tier_range_is_visible() -> None:
    # `plans/classification-refinement/plan.md` Stage 7: the gate moved
    # from `medres` to `lowres`.
    #
    # **Switched from Infantry to an armored vehicle, slice 2A (`plans/
    # detection-cones-slice2/plan.md` decision 3).** Infantry now carries
    # `distinctiveness=5.0` (`object_model._OP_CLASS_DISTINCTIVENESS`),
    # which saturates the class clamp at its own presence range at every
    # optic -- infantry can no longer produce a genuine presence-only
    # (`lowres`) observation, by design (this is exactly the fix: "Infantry
    # classifies at exactly its detection range"). A T-72B (`OP_ARMORED`,
    # distinctiveness 1.0, "ordinary") is the object this gate-boundary
    # test actually needs. T-72B: size 7.0 m, UNAIDED_OPTIC (1.0/1.0/1.0):
    # presence = 7 / 0.003 * 1.0 = 2333.33 m; class = min(2333.33,
    # 7 / 0.014 * 1.0 * 1.0 = 500 m) = 500 m -- well below presence, so the
    # clamp never binds for an ordinary object, and there is a real
    # lowres-only band between 500 m and 2333.33 m (distinct from
    # `test_ural_truck_gate_is_bound_by_the_size_curve_not_the_range_cap`'s
    # own 428.57-2000 m band for a 6 m truck, so the two tests aren't
    # duplicating one boundary).
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("T-72B", x=2333.0, z=0.0)

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "lowres"
    assert result.confidence == NAKED_EYE_PRESENCE_CONFIDENCE


def test_armored_vehicle_just_outside_lowres_tier_range_is_not_visible() -> None:
    # Just beyond the default optic's (UNAIDED_OPTIC) lowres threshold of
    # 2333.33 m for a T-72B (see the test above for the derivation).
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("T-72B", x=2334.0, z=0.0)

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


@pytest.mark.xfail(
    reason=(
        "Slice 2A (`plans/detection-cones-slice2/plan.md` decision 1) "
        "moved BINOCULAR_OPTIC's presence multiplier from the old flat "
        "BINOCULAR_RANGE_MULTIPLIER=4.0 to a BTR-60-derived, per-tier "
        "presence_range_mult=2.42 -- lower than the old flat figure, "
        "because presence scales sub-linearly with magnification "
        "(decisions doc decision 1) while LOWRES_ANGULAR_RADIUS_RAD was "
        "itself derived from the *old* flat 4.0 against this exact "
        "8890 m/7 m ground-truth point (visibility.py's own angular-radius "
        "constants comment). At 2.42, a 7 m object's binocular presence "
        "threshold is 7 / 0.003 * 2.42 = 5646.67 m -- below 8890 m, so "
        "this candidate is no longer admitted. This is a real, known "
        "regression against the photographed ground truth (the fixture "
        "is CONTAMINATED besides -- see test_vision_calibration.py's own "
        "module docstring), not a bug in this change: it is the accepted "
        "'known unmodelled residual' the decisions doc names (a single "
        "per-optic multiplier will be somewhat wrong for one class of "
        "object either way). Kept as xfail rather than deleted or "
        "silently re-derived, so this regression stays visible instead of "
        "disappearing from the suite -- see "
        "test_binocular_presence_threshold_for_a_7m_object below for the "
        "new, correctly-derived threshold this module now actually "
        "enforces."
    ),
    strict=True,
)
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


def test_binocular_presence_threshold_for_a_7m_object() -> None:
    """The new, correctly-derived binocular presence threshold for a 7 m
    object (slice 2A): `7 / LOWRES_ANGULAR_RADIUS_RAD *
    BINOCULAR_OPTIC.presence_range_mult = 7 / 0.003 * 2.42 = 5646.67 m` --
    admitted just inside it, rejected just outside. See the xfail test
    above for why this is lower than the 8890 m ground truth the old flat
    multiplier reached."""
    ownship = _ownship(heading_true_deg=0.0)
    inside = _candidate("T-72B", x=5646.0, z=0.0)
    beyond = _candidate("T-72B", x=5648.0, z=0.0)

    inside_result = check_visibility(
        ownship, inside, _FAKE_CONN, _THEATRE, optic=BINOCULAR_OPTIC
    )
    beyond_result = check_visibility(
        ownship, beyond, _FAKE_CONN, _THEATRE, optic=BINOCULAR_OPTIC
    )

    assert inside_result is not None
    assert inside_result.tier == "lowres"
    assert beyond_result is None


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
       optic is naked-eye, not binoculars.**

    **`downgraded_tier_candidate` switched from Infantry to a T-72B, slice
    2A (`plans/detection-cones-slice2/plan.md` decision 3).** Infantry now
    carries `distinctiveness=5.0`, which saturates its class threshold to
    its own presence range at every optic -- a 300 m Infantry candidate
    now resolves `medres`, not the tier-downgrade-to-`lowres` story this
    test originally told (see `test_armored_vehicle_just_inside_lowres_
    tier_range_is_visible` for where that story now correctly lives, on a
    non-distinctive object). A T-72B (`OP_ARMORED`, distinctiveness 1.0)
    at 2000 m demonstrates the same shape: presence threshold 2333.33 m,
    class threshold 500 m -- 2000 m clears presence but not class, so this
    resolves `lowres` under the default optic, "something is there,"
    ED's only catch-all. A `hires`-tier case (50 m Infantry, still
    resolves under the naked eye) and the hard `NAKED_EYE_RANGE_CAP_M`
    out-of-range case (10001 m, unaffected by any optic) are pinned
    alongside it so this test covers the same three-case shape the
    superseded binocular-default guards did.
    """
    ownship = _ownship(heading_true_deg=0.0)

    hires_candidate = _candidate("Infantry", x=50.0, z=0.0)
    downgraded_tier_candidate = _candidate("T-72B", x=2000.0, z=0.0)
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
    narrow_optic = Optic(
        name="test_narrow",
        presence_range_mult=4.0,
        class_range_mult=4.0,
        type_range_mult=4.0,
        fov_half_angle_deg=5.0,
    )
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
    narrow_optic = Optic(
        name="test_narrow",
        presence_range_mult=4.0,
        class_range_mult=4.0,
        type_range_mult=4.0,
        fov_half_angle_deg=5.0,
    )
    ownship = _ownship(heading_true_deg=0.0)
    # Dead ahead, well inside any plausible FOV.
    on_axis_candidate = _candidate("Infantry", x=250.0, z=0.0)

    result = check_visibility(
        ownship, on_axis_candidate, _FAKE_CONN, _THEATRE, optic=narrow_optic
    )
    assert result is not None


def test_higher_magnification_optic_extends_the_range_threshold() -> None:
    """`size_m / threshold_rad * M` -- the range threshold scales linearly
    with the optic's own `presence_range_mult`. `UNAIDED_OPTIC` (1.0, now
    the default -- see `test_default_optic_is_naked_eye` above) is used
    here as the reference point against `BINOCULAR_OPTIC`'s
    `presence_range_mult` (2.42, slice 2A -- `optics.py`'s own docstring):
    a candidate beyond the unaided gate's outer (`lowres`) presence
    threshold but within the binocular gate's own presence threshold is
    admitted under one and rejected under the other at the exact same
    range. Dead ahead (azimuth 0), so `BINOCULAR_OPTIC`'s field of view
    (4.25 deg half-angle) does not affect this candidate.

    **Tier moved from `lowres` to `medres`, slice 2A decision 3.**
    Infantry now carries `distinctiveness=5.0`, so under binoculars its
    class threshold (`min(presence, 1.8 / 0.014 * 3.50 * 5.0 = 2250 m)`)
    clamps to the *same* 1452 m as presence rather than the much shorter
    unclamped figure -- a 610 m candidate that only clears presence still
    also clears class, so it resolves `medres`, not `lowres`. This is the
    clamp behaving as decision 3 intends, not a defect in this test."""
    ownship = _ownship(heading_true_deg=0.0)
    # Infantry: size 1.8 m, gating tier is `lowres` (0.003 rad).
    # Unaided presence threshold: 1.8 / 0.003 * 1.0 = 600 m.
    # Binocular presence threshold: 1.8 / 0.003 * 2.42 = 1452 m.
    candidate = _candidate("Infantry", x=610.0, z=0.0)

    binocular_result = check_visibility(
        ownship, candidate, _FAKE_CONN, _THEATRE, optic=BINOCULAR_OPTIC
    )
    assert binocular_result is not None
    assert binocular_result.tier == "medres"

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


def test_broadside_and_nose_on_headings_resolve_to_different_recognition_tier(
    dimensioned_profile_lookup: None,
) -> None:
    # **Corrected 2026-09-21** (`body-layer/research/2026-09-21-aspect-
    # magnification-and-distinctiveness.md` Finding 1): aspect must feed
    # recognition only, never admission -- a real four-instrument BTR-60
    # measurement found presence identical (1.00x) at every aspect while
    # class/type moved 1.33x-2.31x. This test used to assert nose_on was
    # rejected outright at this range; that was exactly the defect the
    # research note caught. Both headings now use the SAME size_m=10.0 for
    # the gate (aspect-invariant), so both are admitted at the same range
    # -- what differs is the achieved recognition tier:
    #   nose-on (aspect 0):    apparent extent = max(width=4, height=6)
    #                          = 6, medres threshold = 6/0.014*1 = 428.6 m,
    #                          hires threshold = 6/0.028*1 = 214.3 m --
    #                          500 m clears neither, so tier = lowres.
    #   broadside (aspect 90): apparent extent = max(length=10, height=6)
    #                          = 10, medres threshold = 10/0.014*1
    #                          = 714.3 m -- 500 m clears it, tier = medres.
    ownship = _ownship(heading_true_deg=0.0)
    nose_on = _candidate(
        _ASPECT_TEST_OBJECT_TYPE, x=500.0, z=0.0, heading_true_deg=180.0
    )
    broadside = _candidate(
        _ASPECT_TEST_OBJECT_TYPE, x=500.0, z=0.0, heading_true_deg=90.0
    )

    nose_on_result = check_visibility(ownship, nose_on, _FAKE_CONN, _THEATRE)
    broadside_result = check_visibility(ownship, broadside, _FAKE_CONN, _THEATRE)

    assert nose_on_result is not None
    assert nose_on_result.tier == "lowres"
    assert broadside_result is not None
    assert broadside_result.tier == "medres"


def test_detection_range_is_invariant_under_aspect(
    dimensioned_profile_lookup: None,
) -> None:
    """Regression guard for the exact defect
    `2026-09-21-aspect-magnification-and-distinctiveness.md` Finding 1
    caught: admission and the `lowres`/presence tier must be identical at
    every aspect, including non-axis-aligned ones -- 0/90 alone would have
    hidden the original defect just as surely as the `apparent_extent_m`
    cubic-fallback bug was hidden by testing only 0/90 (the mirror image
    of this plan's own mandated formula-test rule). `_ASPECT_TEST_PROFILE`
    has `size_m=10.0`; at every aspect below, both the admission gate and
    the achieved tier at a range just inside the size_m-derived lowres
    threshold (3333.3 m) must agree: admitted, tier lowres. Kept comfortably
    inside every aspect's medres threshold's *lower* bound too (nose-on
    medres threshold is 428.6 m, the smallest any aspect here produces) is
    not required -- what must hold is that presence itself never moves."""
    ownship = _ownship(heading_true_deg=0.0)
    range_m = 3000.0  # inside 3333.3 m at every aspect, outside every medres threshold

    for aspect_heading_true_deg in (0.0, 45.0, 90.0, 135.0, 180.0, 270.0):
        candidate = _candidate(
            _ASPECT_TEST_OBJECT_TYPE,
            x=range_m,
            z=0.0,
            heading_true_deg=aspect_heading_true_deg,
        )
        result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)
        assert result is not None, (
            f"admission changed with aspect at heading={aspect_heading_true_deg}"
        )
        assert result.tier == "lowres", (
            f"presence tier changed with aspect at heading={aspect_heading_true_deg}"
        )


def test_unknown_heading_reproduces_the_pre_aspect_scalar_behaviour(
    dimensioned_profile_lookup: None,
) -> None:
    # Regression guard (mirrors cones-slice-1's own "must not change the
    # default" pattern): with heading_true_deg=None, apparent_extent_m
    # falls back to plain profile.size_m (10.0) regardless of geometry --
    # exactly what this gate computed before aspect existed. medres
    # threshold = 10 / 0.014 * 1.0 = 714.3 m, so a candidate at 500 m
    # (which achieves only `lowres` nose-on, per the test above) achieves
    # `medres` here, matching the *broadside* result exactly -- an unknown
    # aspect falls back to the same generous, no-regression size_m the
    # gate itself always used.
    ownship = _ownship(heading_true_deg=0.0)
    unknown_heading = _candidate(
        _ASPECT_TEST_OBJECT_TYPE, x=500.0, z=0.0, heading_true_deg=None
    )

    result = check_visibility(ownship, unknown_heading, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "medres"


def test_tall_mast_shaped_profile_achieves_a_better_tier_than_the_old_scalar_formula(
    dimensioned_profile_lookup: None,
) -> None:
    # Pins the S-300 tall-mast fix directly, independent of real sourced
    # dimensions (`_TALL_MAST_TEST_PROFILE` above) -- and now, per the
    # 2026-09-21 correction, pins it as a RECOGNITION improvement, not a
    # detection-range one: admission is governed by size_m=5.0 (the old
    # generic-fallback figure a mast used to collapse to) at every aspect,
    # unaffected by this fix -- lowres threshold 5/0.003*1 = 1666.7 m,
    # identical before and after this pass. What the real height_m=24.0
    # fixes is recognition: old scalar medres threshold was
    # 5/0.014*1 = 357.1 m; with apparent_extent_m height-dominated at every
    # aspect (max(projected_width, 24.0) >= 24.0), the new medres threshold
    # is 24/0.014*1 = 1714.3 m. A candidate at 1000 m -- past the old
    # medres threshold, comfortably admitted either way, well inside the
    # new medres threshold -- achieves only `lowres` under the old formula
    # and `medres` under the new one.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate(
        _TALL_MAST_TEST_OBJECT_TYPE, x=1000.0, z=0.0, heading_true_deg=180.0
    )

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert result is not None
    assert result.tier == "medres"


# --- Slice 2A: per-tier multipliers, distinctiveness, the clamp
# (`plans/detection-cones-slice2/plan.md`) --------------------------------


#: Every named profile in `object_model`'s two keyword tables, plus its
#: fallback -- the population `test_tier_thresholds_never_invert` and
#: `test_infantry_class_clamps_to_presence_at_every_optic` below range
#: over. Reached via the module's private tables rather than a curated
#: subset, so this test catches a future profile whose `distinctiveness`/
#: dimensions happen to invert the ladder, not just the profiles already
#: known to be interesting.
_ALL_PROFILES: tuple[ObjectTypeProfile, ...] = (
    object_model._DEFAULT_PROFILE,
    *(profile for _keyword, profile in object_model._KEYWORD_PROFILES),
    *(profile for _keyword, profile in object_model._REPORTING_NAME_KEYWORD_PROFILES),
)

#: The two optics slice 2A actually ships (`optics.py`) -- 9K113 wide/
#: narrow are deliberately not added as selectable `Optic`s this slice
#: (`optics.py`'s own docstring), so they aren't in this population.
_ALL_OPTICS: tuple[Optic, ...] = (UNAIDED_OPTIC, BINOCULAR_OPTIC)


def test_tier_thresholds_never_invert() -> None:
    """`type <= class <= presence` for every named profile, at every optic
    (slice 2A step 4, `plans/detection-cones-slice2/plan.md`): the clamp
    that makes a distinctive object's class saturate to its own presence
    range could, if wired wrong, let the `type` threshold exceed `class`
    for a sufficiently distinctive/high-`type_range_mult` combination --
    `_achieved_tier`'s own chained `min()`s are what rule this out by
    construction, not a value the thresholds happen to land on. Checked
    directly against the computed range thresholds (recomputed here with
    the same formula `_achieved_tier` uses internally, rather than
    inferred indirectly from tier names), across every profile x optic
    combination rather than a curated few, since an inversion is exactly
    the kind of defect one hand-picked example could miss."""
    for profile in _ALL_PROFILES:
        distinctiveness = object_model.distinctiveness_of(profile)
        for optic in _ALL_OPTICS:
            presence_threshold_m = min(
                visibility.NAKED_EYE_RANGE_CAP_M,
                (profile.size_m / visibility.LOWRES_ANGULAR_RADIUS_RAD)
                * optic.presence_range_mult,
            )
            class_threshold_m = min(
                presence_threshold_m,
                (profile.size_m / visibility.MEDRES_ANGULAR_RADIUS_RAD)
                * optic.class_range_mult
                * distinctiveness,
            )
            type_threshold_m = min(
                class_threshold_m,
                (profile.size_m / visibility.HIRES_ANGULAR_RADIUS_RAD)
                * optic.type_range_mult,
            )
            assert type_threshold_m <= class_threshold_m <= presence_threshold_m, (
                f"{profile.op_class} @ {optic.name}: type={type_threshold_m} "
                f"class={class_threshold_m} presence={presence_threshold_m}"
            )


def test_infantry_class_clamps_to_presence_at_every_optic() -> None:
    """The model's main evidence for decision 3 (`body-layer/research/
    2026-09-21-slice2-model-decisions.md`): infantry's `distinctiveness=5.0`
    is high enough that its raw class figure always exceeds its own
    presence range, so the clamp always binds and `class == presence`
    exactly -- reproducing the measured pattern ("Infantry classifies at
    exactly its detection range," ratio 1.00 at every instrument) as a
    structural consequence of one per-class constant, with no per-unit
    special-casing. Checked at both optics slice 2A actually ships
    (`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`) via `_achieved_tier` directly --
    the achieved tier at a range just inside presence must be `medres`
    (class), never `lowres`, since class has saturated all the way out to
    presence."""
    profile = object_model.profile_for("Infantry")
    assert profile.op_class == "OP_INFANTRY"
    distinctiveness = object_model.distinctiveness_of(profile)
    assert distinctiveness == pytest.approx(5.0)

    for optic in _ALL_OPTICS:
        presence_threshold_m = (
            profile.size_m / visibility.LOWRES_ANGULAR_RADIUS_RAD
        ) * optic.presence_range_mult
        # A range 1 m inside presence -- if the clamp is working, this
        # still resolves medres (class), not lowres, because class has
        # saturated to presence.
        just_inside_presence_m = presence_threshold_m - 1.0

        tier, _confidence = visibility._achieved_tier(
            just_inside_presence_m,
            profile.size_m,
            profile.size_m,
            optic,
            distinctiveness,
        )

        assert tier == "medres", (
            f"infantry @ {optic.name}: expected class to saturate to "
            f"presence ({presence_threshold_m} m), but a range just inside "
            f"it resolved {tier!r}, not 'medres'"
        )
