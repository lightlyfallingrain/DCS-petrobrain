"""`BL-B111` Stage 3c -- the production-mode fences from
`plans/expected-area-look/plan.md`'s "Acceptance (Stage 3c, production
mode)" table, run against `tools/measure_expected_area_look.py
--production`'s own functions (the real `ContactStore`/`resolve_checks`,
stub probe answers) rather than the modelled harness `test_contacts.py`
already covers.

**At n = 300, per the plan's "Remaining build" instruction** ("Add the
fences to `test_expected_area_look_sweep.py` at n = 300"), not the
Acceptance table's own n = 200 for "different groups" -- the plan states
300 explicitly for this file, so every cell below runs at 300 even where
the architect-time grid used 200.

**A representative subset of the full grid, not all ~190 cells.** Each
cell below is the worst (or a characteristic) cell for its own fence,
read off a full production run at n = 200/300 (`plans/expected-area-look/
implementation.md`, "Pass 3"), not an arbitrary pick -- re-running the
entire grid at n = 300 in this suite would cost several minutes per test
run for no more confidence than the worst cell already gives (this
module's own cells take ~2s each at n = 300; `test_relative_distance_
sweep.py` already runs ~30s of exactly this kind of statistical sweep in
this test suite, so that budget is an accepted precedent, not a new one).

**If any assertion below fails, that is the plan's own instruction**
("If a fence fails in production, stop and report rather than retune") --
do not widen a bound to make this file pass; report the new number and
let the Reviewer/user decide what the plan's own acceptance table should
say instead."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from measure_expected_area_look import production_cell

N = 300


class TestDifferentGroupsAnnouncedFence:
    """Acceptance row 1: "Different groups, B announced, every cell where
    A's area fits one look" -- fence >= 85%. The worst-measured cells
    (b->u, 700 s gap, the 4.5-5 km far/near pairs) from the full
    production grid; `OP_ARMORED` at 700 s is excluded here because its
    area does not fit one look at all (Decision 1 -- see
    `TestArmourNoCheckFence` below), so it is not a cell this fence
    covers."""

    def test_s125_b_u_700s_far_near_worst_measured_cell(self) -> None:
        r = production_cell("b_u", -5000.0, -3500.0, 700.0, "s-125", N, False)
        assert r["new"] >= 85.0

    def test_s125_b_u_700s_near_far_worst_measured_cell(self) -> None:
        r = production_cell("b_u", -3500.0, -5000.0, 700.0, "s-125", N, False)
        assert r["new"] >= 85.0

    def test_s125_b_u_700s_4_5_3_0_bfar(self) -> None:
        r = production_cell("b_u", -4500.0, -3000.0, 700.0, "s-125", N, False)
        assert r["new"] >= 85.0

    def test_op_armored_6s_u_u_3_0_1_5_bfar(self) -> None:
        r = production_cell("u_u", -3000.0, -1500.0, 6.0, "OP_ARMORED", N, False)
        assert r["new"] >= 85.0


class TestSameGroupDuplicateDeltaFence:
    """Acceptance row 2: duplicate heard must not rise by more than +4
    points at the 6 s (harness-only) gap, or +1 point at 700 s (the
    flight case)."""

    def test_op_armored_b_u_6s_delta_within_4_points(self) -> None:
        r = production_cell("b_u", -3000.0, -3000.0, 6.0, "OP_ARMORED", N, True)
        assert r["new"] - r["today"] <= 4.0

    def test_s125_u_b_6s_delta_within_4_points(self) -> None:
        r = production_cell("u_b", -3000.0, -3000.0, 6.0, "s-125", N, True)
        assert r["new"] - r["today"] <= 4.0

    def test_op_armored_b_u_700s_delta_within_1_point(self) -> None:
        r = production_cell("b_u", -3000.0, -3000.0, 700.0, "OP_ARMORED", N, True)
        assert r["new"] - r["today"] <= 1.0

    def test_s125_u_b_700s_delta_within_1_point(self) -> None:
        r = production_cell("u_b", -3000.0, -3000.0, 700.0, "s-125", N, True)
        assert r["new"] - r["today"] <= 1.0

    def test_s125_u_u_700s_delta_within_1_point(self) -> None:
        r = production_cell("u_u", -2000.0, -2000.0, 700.0, "s-125", N, True)
        assert r["new"] - r["today"] <= 1.0


class TestArmourNoCheckFence:
    """Acceptance row 3: armour, 700 s (its believed area has grown past
    one binocular sweep by then, Decision 1) -- no check opens, so
    today's behaviour must stand exactly unchanged, for both a different-
    group and a same-group pair."""

    def test_armour_700s_different_groups_unchanged(self) -> None:
        r = production_cell("u_u", -4500.0, -3000.0, 700.0, "OP_ARMORED", N, False)
        assert r["trigger"] == 0.0
        assert r["new"] == r["today"]

    def test_armour_700s_same_group_unchanged(self) -> None:
        r = production_cell("u_u", -3000.0, -3000.0, 700.0, "OP_ARMORED", N, True)
        assert r["trigger"] == 0.0
        assert r["new"] == r["today"]


class TestRelocationSameOpticFence:
    """Acceptance row 4: `CONTACT_RELOCATED` ("that group, now ...") must
    stay <= 5% same-optic (eye->eye or bino->bino) -- the cross-optic
    rate (12-35%, a real range correction) is characterised, not
    fenced."""

    def test_s125_u_u_4_5km_same_optic_relocation_within_5_points(self) -> None:
        r = production_cell("u_u", -4500.0, -4500.0, 6.0, "s-125", N, True)
        assert r["relocation"] <= 5.0

    def test_op_armored_u_u_4_5km_same_optic_relocation_within_5_points(self) -> None:
        r = production_cell("u_u", -4500.0, -4500.0, 6.0, "OP_ARMORED", N, True)
        assert r["relocation"] <= 5.0

    def test_s125_b_b_4_5km_same_optic_relocation_within_5_points(self) -> None:
        r = production_cell("b_b", -4500.0, -4500.0, 6.0, "s-125", N, True)
        assert r["relocation"] <= 5.0


class TestSamVignetteFence:
    """Acceptance row 5: the SAM vignette (same group, 700 s gap) must
    not be called "different" more than 2% of the time -- the "A
    observed" rule (only A's own objects count, never B's) is what keeps
    this near 0% against the naive rule's 91-99% (see `naive` vs.
    `verdict_different` in `production_trial`'s own docstring)."""

    def test_s125_u_u_3km_700s_verdict_different_within_2_points(self) -> None:
        r = production_cell("u_u", -3000.0, -3000.0, 700.0, "s-125", N, True)
        assert r["verdict_different"] <= 2.0

    def test_s125_u_b_3km_700s_verdict_different_within_2_points(self) -> None:
        r = production_cell("u_b", -3000.0, -3000.0, 700.0, "s-125", N, True)
        assert r["verdict_different"] <= 2.0

    def test_s125_b_u_4_5km_700s_verdict_different_within_2_points(self) -> None:
        r = production_cell("b_u", -4500.0, -4500.0, 700.0, "s-125", N, True)
        assert r["verdict_different"] <= 2.0
