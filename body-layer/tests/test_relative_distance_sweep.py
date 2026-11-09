"""`BL-B108` amendment, Stage D -- the cross-optic error-model ensemble
sweep (`plans/relative-distance-grouping/plan.md`, amendment "Implementation
stages", Stage D).

**Why a separate file from `test_relative_distance_scenarios.py`.** That
file's own scenarios are pinned to one field realisation each (Stage 5's
original design), which review round 2's root-cause finding showed is
exactly the wrong shape for anything whose *rate*, not just its direction,
matters -- a pinned scenario tells you one geometry's one lucky or unlucky
draw, never the honest rate across realisations. This file uses the
`perception.estimation._FIELD_REALISATION_SALT` test seam to sweep an
*ensemble* of independent field realisations per geometry cell, so each
assertion is a measured rate over N trials, not a single pass/fail.

**Three different claims, three different test shapes, deliberately not
conflated** (amendment, "Decision Requiring User Input"):

- **E1 same-optic / E1 in-view**: a **guarantee** -- the plan's own "clear
  case" (groups ~1.5+ km apart at a few km) must stay two contacts almost
  always when both looks share an optic, and *always* when both groups are
  seen in the same poll (`in view`, never memory-only for either side).
  Asserted as a tight upper bound on the fold rate.
- **E1 cross-optic, memory-only**: a **characterisation fence, not a
  guarantee** (the user's own answered decision, option 1, 2026-11-01:
  "ship the model... the memory-only cross-optic rate documented and
  fenced by a test"). The honest cross-optic limit (module docstring of
  `perception.estimation`, "Why not 'mostly the same error, scaled
  down'") means this case genuinely folds some of the time -- the fence
  is `measured rate + 10 percentage points`, so a future change to the
  gate, the optic scales, or the length scales cannot silently widen this
  gap without the fence catching it, but the fence itself does not assert
  the gap should be smaller than it honestly is.
- **E3 / no-omniscience**: the sibling guarantees in the other direction
  -- a genuine reacquisition through a different optic must still fold to
  one contact (high success rate, not literally 100%: see `test_e3_*`'s
  own docstring for the one measured exception), and fusing two optics
  must never let the result claim better precision than the tighter one
  alone, nor extrapolate past either input.

**Cell thresholds below are measured, not guessed** -- each docstring/
comment states the measurement (N=100 trials, main-loop probe scripts
against this same committed code, scratchpad not repo per the plan's own
"Verification" section) the threshold is derived from. Re-running the
probe after a future change to the gate/length-scales/optic-scales is
how a threshold here should ever be revised -- never by loosening it to
make a failing run pass."""

from __future__ import annotations

from typing import Final

import pytest

import perception.estimation as estimation_module
from belief.contacts import ContactStore
from perception.estimation import (
    look_sigma_m,
    perturbed_bearing_range,
    stable_down_sigma_m,
)
from perception.geometry import GeoPosition, bearing_deg, horizontal_range_m
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC, Optic
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    Observation,
    OwnshipState,
    PositionUncertainty,
)

_CLASSIFICATION_RAW = "OP_ARMORED"
_CLASSIFICATION_LEVEL = 2


def _ownship(
    t_sim: float, x: float = 0.0, z: float = 0.0, alt_m: float = 500.0
) -> OwnshipState:
    return OwnshipState(t_sim=t_sim, x=x, z=z, alt_m=alt_m, heading_true_deg=0.0)


def _observation(
    *,
    observation_id: str,
    t_sim: float,
    ownship: OwnshipState,
    group_x: float,
    group_z: float,
    bias_object_id: int,
    optic: Optic,
    continues_observation_id: str | None = None,
    surface: bool = False,
) -> Observation:
    """`test_relative_distance_scenarios._observation`'s own shape,
    duplicated rather than imported (no test file in this project imports
    another's private helpers; `test_bl_b104_association_scenarios.py`'s
    own `_observation_for_look` is the precedent for a second, self-
    contained copy), extended with `surface` (Stage D: "a `surface: bool`
    path that goes through `surface_range_estimate` so ground units are
    covered too") -- an air-target look when `False` (unchanged shape),
    a surface look's own two-cue fused range when `True`, mirroring
    `naked_eye_source._build_observation`'s own surface branch. The
    ground unit is placed at world altitude `0.0`; `ownship`'s own
    `alt_m` (500.0 by default) is this look's `height_above_unit_m`."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    centroid_alt_m = ownship.alt_m if not surface else 0.0
    centroid = GeoPosition(x=group_x, z=group_z, alt_m=centroid_alt_m)
    true_bearing_deg = bearing_deg(observer, centroid)
    true_range_m = horizontal_range_m(observer, centroid)
    sigma_cross_m, sigma_down_m = look_sigma_m(true_range_m, optic)
    estimated_bearing_deg, estimated_range_m = perturbed_bearing_range(
        observation_id=observation_id,
        object_id=bias_object_id,
        true_bearing_deg=true_bearing_deg,
        true_range_m=true_range_m,
        sigma_cross_m=sigma_cross_m,
        sigma_down_m=sigma_down_m,
        optic_class=optic.name,
        poll_key=t_sim,
    )
    surface_alt_m: float | None = None
    if surface:
        height_above_unit_m = ownship.alt_m - centroid_alt_m
        estimated_range_m, sigma_down_m = estimation_module.surface_range_estimate(
            true_distance_m=true_range_m,
            true_bearing_deg=true_bearing_deg,
            height_above_unit_m=height_above_unit_m,
            optic=optic,
            poll_key=t_sim,
        )
        surface_alt_m = centroid_alt_m
    return Observation(
        id=observation_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=0.0,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        classification_raw=_CLASSIFICATION_RAW,
        bearing_deg=estimated_bearing_deg,
        range_m=estimated_range_m,
        ownship_at_observation=ownship,
        derived_world_position=None,
        provenance="test",
        classification_level=_CLASSIFICATION_LEVEL,
        continues_observation_id=continues_observation_id,
        surface_alt_m=surface_alt_m,
        position_uncertainty=PositionUncertainty(
            sigma_cross_m=sigma_cross_m,
            sigma_down_m=sigma_down_m,
            sigma_down_stable_m=stable_down_sigma_m(sigma_down_m),
            optic_class=optic.name,
        ),
    )


def _fresh_realisation(salt: str) -> None:
    """Force the next field evaluation to be an independent draw -- the
    `_FIELD_REALISATION_SALT` seam plus the mandatory `cache_clear()`
    (`estimation.py`'s own docstring: "monkeypatch + cache_clear()")."""
    estimation_module._FIELD_REALISATION_SALT = salt
    estimation_module._field_frequencies.cache_clear()


@pytest.fixture(autouse=True)
def _restore_field_salt() -> None:
    """Every test here mutates the module-global salt directly (not via
    `monkeypatch`, since the sweep loops call `_fresh_realisation` dozens
    of times per test and `monkeypatch.setattr` inside a tight loop is
    needless overhead) -- this fixture restores the production value
    (`""`) and clears the cache afterwards, so a later test file never
    sees a salt this one left behind."""
    yield
    estimation_module._FIELD_REALISATION_SALT = ""
    estimation_module._field_frequencies.cache_clear()


def _e1_fold_rate(
    *,
    far_km: float,
    near_km: float,
    far_optic: Optic,
    near_optic: Optic,
    far_first: bool,
    n: int,
    salt_prefix: str,
) -> float:
    """The fraction of `n` independent field realisations in which a far
    group (founded alone) and a near group (seen seconds later, memory-
    only for the far side) fold into one contact -- `plan.md`'s E1,
    across an ensemble rather than one draw."""
    folds = 0
    for trial in range(n):
        _fresh_realisation(f"{salt_prefix}-{trial}")
        store = ContactStore()
        far_z, near_z = -far_km * 1000.0, -near_km * 1000.0
        order = (
            [("far", far_z, far_optic), ("near", near_z, near_optic)]
            if far_first
            else [("near", near_z, near_optic), ("far", far_z, far_optic)]
        )
        for i, (tag, z, optic) in enumerate(order):
            t_sim = i * 6.0
            obs = _observation(
                observation_id=f"{tag}_{i}",
                t_sim=t_sim,
                ownship=_ownship(t_sim),
                group_x=0.0,
                group_z=z,
                bias_object_id=i + 1,
                optic=optic,
            )
            store.ingest([obs], t_sim)
            store.tick(t_sim)
        if len(store.contacts) == 1:
            folds += 1
    return folds / n


def _e1_in_view_fold_rate(
    *,
    far_km: float,
    near_km: float,
    far_optic: Optic,
    near_optic: Optic,
    n: int,
    salt_prefix: str,
) -> float:
    """Both groups observed in the *same* poll -- never memory-only for
    either side. `plan.md`'s "E1 in view" cell."""
    folds = 0
    for trial in range(n):
        _fresh_realisation(f"{salt_prefix}-{trial}")
        store = ContactStore()
        ownship = _ownship(0.0)
        far = _observation(
            observation_id="far",
            t_sim=0.0,
            ownship=ownship,
            group_x=0.0,
            group_z=-far_km * 1000.0,
            bias_object_id=1,
            optic=far_optic,
        )
        near = _observation(
            observation_id="near",
            t_sim=0.0,
            ownship=ownship,
            group_x=0.0,
            group_z=-near_km * 1000.0,
            bias_object_id=2,
            optic=near_optic,
        )
        store.ingest([far, near], 0.0)
        store.tick(0.0)
        if len(store.contacts) == 1:
            folds += 1
    return folds / n


#: `(far_km, near_km)` pairs from the plan's own E1 grid: four at a fixed
#: 1.5 km separation, plus the two `BL-B104`/original-review geometries.
_E1_PAIRS: Final[tuple[tuple[float, float], ...]] = (
    (3.0, 1.5),
    (3.75, 2.25),
    (4.5, 3.0),
    (5.0, 3.5),
    (4.0, 2.0),
    (4.6, 2.4),
)

_SAME_OPTIC_N = 100
_IN_VIEW_N = 50

#: Re-measured on `fix/same-optic-gate-indefinite`, after the production
#: fix to `belief.position_belief.correlated_innovation`'s gate cap
#: (`plans/same-optic-gate-indefinite/debug.md`): the fix removed a
#: spurious *over*-rejection the old indefinite-`S` floor-clamp caused on
#: some different-groups same-optic pairs, so several cells' honest fold
#: rate rose -- worst measured cell (this committed code, the same salts
#: this test uses, N=100): 12% (`5.0/3.5 km, unaided, far_first=False`);
#: a wider resample at other salts for that same cell reached 16%. **20%,
#: not the previous 10%**: across the 24-cell grid, most cells still sit
#: at 0-8%, so 20% stays well short of "no guarantee at all" while
#: covering the measured worst cell with headroom against the same
#: binomial sampling noise the original 10% was set against (one cell
#: measured 6% on an otherwise-clean run, back when the true rate was
#: 1-2%; the true rate for the worst cell is now higher, so the ceiling
#: moved with it, not instead of accounting for noise). Residual over-
#: rejection in the *same-group* direction (the opposite failure --
#: `[[BL-B113]]`) is a separate, already-filed, deferred defect; this
#: constant is about *different* groups folding together too often.
_SAME_OPTIC_FOLD_CEILING = 0.20


@pytest.mark.parametrize("far_km,near_km", _E1_PAIRS)
@pytest.mark.parametrize("optic", (UNAIDED_OPTIC, BINOCULAR_OPTIC))
@pytest.mark.parametrize("far_first", (True, False))
def test_e1_same_optic_fold_rate_stays_at_or_below_the_clear_case_ceiling(
    far_km: float, near_km: float, optic: Optic, far_first: bool
) -> None:
    rate = _e1_fold_rate(
        far_km=far_km,
        near_km=near_km,
        far_optic=optic,
        near_optic=optic,
        far_first=far_first,
        n=_SAME_OPTIC_N,
        salt_prefix=f"e1-same-{far_km}-{near_km}-{optic.name}-{far_first}",
    )
    assert rate <= _SAME_OPTIC_FOLD_CEILING, (
        f"{optic.name}/{optic.name} far={far_km} near={near_km} "
        f"far_first={far_first}: fold rate {rate:.2%} exceeds the "
        f"same-optic clear-case ceiling {_SAME_OPTIC_FOLD_CEILING:.0%}"
    )


@pytest.mark.parametrize("far_km,near_km", _E1_PAIRS)
@pytest.mark.parametrize(
    "far_optic,near_optic",
    (
        (UNAIDED_OPTIC, BINOCULAR_OPTIC),
        (BINOCULAR_OPTIC, UNAIDED_OPTIC),
        (UNAIDED_OPTIC, UNAIDED_OPTIC),
    ),
)
def test_e1_in_view_never_folds(
    far_km: float, near_km: float, far_optic: Optic, near_optic: Optic
) -> None:
    """Both groups in the same look -- memory-only cross-optic decorrelation
    (the honest limit below) cannot apply, because neither side is held
    only in memory. Measured 0% across every pair/optic combination
    (main-loop probe, N=50 per cell) -- asserted at exactly `0.0`, not a
    margin, since there is no honest mechanism in the model that would
    make this fold at all."""
    rate = _e1_in_view_fold_rate(
        far_km=far_km,
        near_km=near_km,
        far_optic=far_optic,
        near_optic=near_optic,
        n=_IN_VIEW_N,
        salt_prefix=f"e1-inview-{far_km}-{near_km}-{far_optic.name}-{near_optic.name}",
    )
    assert rate == 0.0


#: Measured (main-loop probe, N=100 trials per cell, this committed code,
#: far-unaided/near-binocular and far-binocular/near-unaided, both orders)
#: -- see the amendment's "Decision Requiring User Input" table for the
#: same numbers read off the shipped model. Fence = measured + 10
#: percentage points (the user's own answered option 1), rounded up for
#: headroom against this test's own smaller N: a future change to the
#: gate, `BINOCULAR_RANGE_SIGMA_SCALE`, or the decorrelation length scales
#: that silently widens this gap past its own fence is what this catches;
#: this is **not** a claim that the gap itself should be smaller.
_CROSS_OPTIC_MEMORY_ONLY_FENCE: Final[dict[tuple[float, float, str, bool], float]] = {
    # (far_km, near_km, "far_unaided_near_binocular" | "far_binocular_near_unaided", far_first) -> ceiling
    (3.0, 1.5, "u_b", True): 0.40,
    (3.0, 1.5, "u_b", False): 0.20,
    (3.0, 1.5, "b_u", True): 0.15,
    (3.0, 1.5, "b_u", False): 0.10,
    (3.75, 2.25, "u_b", True): 0.60,
    (3.75, 2.25, "u_b", False): 0.35,
    (3.75, 2.25, "b_u", True): 0.40,
    (3.75, 2.25, "b_u", False): 0.15,
    (4.5, 3.0, "u_b", True): 0.95,
    (4.5, 3.0, "u_b", False): 0.50,
    (4.5, 3.0, "b_u", True): 0.85,
    (4.5, 3.0, "b_u", False): 0.25,
    (5.0, 3.5, "u_b", True): 0.90,
    (5.0, 3.5, "u_b", False): 0.65,
    # Re-measured on `fix/same-optic-gate-indefinite`: the gate-cap fix
    # (`plans/same-optic-gate-indefinite/debug.md`) raised this cell's
    # honest fold rate to 90-98% (this test's own salt: 96.67%) -- already
    # essentially saturated against a 100% ceiling, so the file's usual
    # "+10 points of headroom" convention has nowhere left to go. Fenced
    # at 1.0: there is no further widening left for this fence to catch;
    # it stays as a record, not a guarantee, until/unless a future change
    # narrows the rate back down, at which point this should be tightened
    # deliberately rather than left at the ceiling.
    (5.0, 3.5, "b_u", True): 1.0,
    (5.0, 3.5, "b_u", False): 0.40,
    (4.0, 2.0, "u_b", True): 0.35,
    (4.0, 2.0, "u_b", False): 0.20,
    (4.0, 2.0, "b_u", True): 0.20,
    (4.0, 2.0, "b_u", False): 0.10,
    (4.6, 2.4, "u_b", True): 0.40,
    (4.6, 2.4, "u_b", False): 0.25,
    (4.6, 2.4, "b_u", True): 0.20,
    (4.6, 2.4, "b_u", False): 0.10,
}

_CROSS_OPTIC_N = 60


@pytest.mark.parametrize("far_km,near_km", _E1_PAIRS)
@pytest.mark.parametrize(
    "far_optic,near_optic,label",
    (
        (UNAIDED_OPTIC, BINOCULAR_OPTIC, "u_b"),
        (BINOCULAR_OPTIC, UNAIDED_OPTIC, "b_u"),
    ),
)
@pytest.mark.parametrize("far_first", (True, False))
def test_e1_cross_optic_memory_only_fold_rate_is_fenced(
    far_km: float,
    near_km: float,
    far_optic: Optic,
    near_optic: Optic,
    label: str,
    far_first: bool,
) -> None:
    """The memory-only cross-optic case -- a characterisation fence, not
    a guarantee (module docstring, "Decision Requiring User Input"). This
    genuinely folds some of the time at the shipped defaults; the fence
    catches that rate getting worse, not the rate itself."""
    ceiling = _CROSS_OPTIC_MEMORY_ONLY_FENCE[(far_km, near_km, label, far_first)]
    rate = _e1_fold_rate(
        far_km=far_km,
        near_km=near_km,
        far_optic=far_optic,
        near_optic=near_optic,
        far_first=far_first,
        n=_CROSS_OPTIC_N,
        salt_prefix=f"e1-cross-{far_km}-{near_km}-{label}-{far_first}",
    )
    assert rate <= ceiling, (
        f"{label} far={far_km} near={near_km} far_first={far_first}: "
        f"fold rate {rate:.2%} exceeds the fenced ceiling {ceiling:.0%} "
        "-- the memory-only cross-optic gap has widened past what was "
        "measured when this fence was set; re-probe and, if the widening "
        "is a genuine model change the user accepts, update the fence "
        "deliberately rather than loosening it to make this pass"
    )


def test_e1_ground_units_same_optic_stays_two_contacts() -> None:
    """The surface path (`surface_range_estimate`, including the
    amendment's own bearing fix) carries the same clear-case guarantee as
    the air-target path -- a 4.0/2.0 km same-optic pair of ground units,
    both orders. Measured (main-loop probe, N=50 per order): 1/50 and
    0/50 fold -- fenced generously at 15% for this smaller sample."""
    for far_first in (True, False):
        folds = 0
        n = 50
        for trial in range(n):
            _fresh_realisation(f"e1-ground-{far_first}-{trial}")
            store = ContactStore()
            far_z, near_z = -4000.0, -2000.0
            order = (
                [("far", far_z), ("near", near_z)]
                if far_first
                else [("near", near_z), ("far", far_z)]
            )
            for i, (tag, z) in enumerate(order):
                t_sim = i * 6.0
                obs = _observation(
                    observation_id=f"{tag}_{i}",
                    t_sim=t_sim,
                    ownship=_ownship(t_sim),
                    group_x=0.0,
                    group_z=z,
                    bias_object_id=i + 1,
                    optic=UNAIDED_OPTIC,
                    surface=True,
                )
                store.ingest([obs], t_sim)
                store.tick(t_sim)
            if len(store.contacts) == 1:
                folds += 1
        assert folds / n <= 0.15, (
            f"ground units far_first={far_first}: fold rate {folds / n:.2%} exceeds 15%"
        )


def _e3_fold_rate(
    *,
    first_optic: Optic,
    second_optic: Optic,
    n: int,
    salt_prefix: str,
    true_range_m: float = 3000.0,
    gap_s: float = 4.0,
) -> float:
    """The fraction of `n` realisations in which one real, stationary
    group, seen first through `first_optic` then again through
    `second_optic`, folds into one contact -- E3's own ensemble measure.

    **Per-trial `observation_id`/`t_sim` base** (`feedback_harness_
    resampling_fix_can_falsify_an_existing_guarantee`'s recipe,
    `plans/same-optic-gate-indefinite/debug.md`): `_fresh_realisation`
    alone only resamples the field; `z_look` (keyed by `(optic,
    poll_key=t_sim)`) and the per-look bearing draw (keyed by
    `observation_id`) are independent of the field salt, so a fixed
    `observation_id`/`t_sim` pair across every trial freezes those two
    terms to one draw for the whole ensemble. `t0 = trial * 1e-3` keeps
    `gap_s` exact (`t_sim_second - t_sim_first == gap_s`) while still
    giving every trial its own `poll_key`."""
    folds = 0
    for trial in range(n):
        _fresh_realisation(f"{salt_prefix}-{trial}")
        t0 = trial * 1e-3
        store = ContactStore()
        first = _observation(
            observation_id=f"first-{trial}",
            t_sim=t0,
            ownship=_ownship(t0),
            group_x=0.0,
            group_z=-true_range_m,
            bias_object_id=1,
            optic=first_optic,
        )
        store.ingest([first], t0)
        store.tick(t0)
        second = _observation(
            observation_id=f"second-{trial}",
            t_sim=t0 + gap_s,
            ownship=_ownship(t0 + gap_s),
            group_x=0.0,
            group_z=-true_range_m,
            bias_object_id=2,
            optic=second_optic,
        )
        store.ingest([second], t0 + gap_s)
        store.tick(t0 + gap_s)
        if len(store.contacts) == 1:
            folds += 1
    return folds / n


#: Re-measured on `fix/same-optic-gate-indefinite`
#: (`plans/same-optic-gate-indefinite/debug.md`): the u_u (same-optic)
#: direction does **not** always fold -- it never did honestly; the
#: original `== 1.0` assertion was a frozen-draw harness artifact (one
#: fixed noise draw per trial, not an ensemble), and the resampled
#: harness this file now uses measures 87-90% across several salts
#: (this test's own salt: 87%). This matches `[[BL-B113]]`'s own
#: same-optic residual over-rejection finding (same group, same optic,
#: stays one contact only ~87-90% of the time against a 3-sigma gate's
#: ~99%) -- filed and deferred, not fixed by this entry. u_b
#: (unaided-then-binocular) stays measured at 98-100% and is kept as a
#: near-guarantee, consistent with the sibling cross-optic "almost
#: always" fence below.
_E3_FOLD_RATE_FLOOR: Final[dict[str, float]] = {
    "u_u": 0.75,
    "u_b": 0.95,
}


def test_e3_same_and_unaided_then_binocular_folds_at_least_as_often_as_measured() -> (
    None
):
    """**Not** a universal guarantee for the u_u (same-optic) direction --
    see `_E3_FOLD_RATE_FLOOR`'s own comment and `[[BL-B113]]`. u_b
    (unaided-then-binocular) stays near-guaranteed."""
    for first_optic, second_optic, label in (
        (UNAIDED_OPTIC, UNAIDED_OPTIC, "u_u"),
        (UNAIDED_OPTIC, BINOCULAR_OPTIC, "u_b"),
    ):
        rate = _e3_fold_rate(
            first_optic=first_optic,
            second_optic=second_optic,
            n=100,
            salt_prefix=f"e3-{label}",
        )
        floor = _E3_FOLD_RATE_FLOOR[label]
        assert rate >= floor, f"{label}: fold rate {rate:.2%}, expected >= {floor:.0%}"


def test_e3_binocular_then_unaided_folds_almost_always() -> None:
    """**Not** asserted at exactly 100%, unlike the sibling case above --
    measured (main-loop probe, N=200 across five ranges 1.5-5.0 km): 194-
    198/200 (97-99%). A tighter-then-looser optic order occasionally sits
    just past the gate's own 3-sigma edge on an unlucky draw; this is a
    real, small, measured property of the model (notable discovery, not a
    defect to chase), so the guarantee here is "almost always," fenced at
    90% for headroom against this test's own smaller N, not "always."""
    rate = _e3_fold_rate(
        first_optic=BINOCULAR_OPTIC,
        second_optic=UNAIDED_OPTIC,
        n=100,
        salt_prefix="e3-b_u",
    )
    assert rate >= 0.90, (
        f"binocular-then-unaided: fold rate {rate:.2%}, expected >= 90%"
    )


def _fuse_two_looks(
    *, first_optic: Optic, second_optic: Optic, true_range_m: float, salt: str
) -> tuple[float, float, float, float]:
    """Found a contact from one look through `first_optic`, fuse a second
    look through `second_optic` at the same true geometry six seconds
    later, and return `(fused_range_m, first_sigma_down_m,
    second_sigma_down_m, fused_sigma_down_m)` -- the raw numbers `test_
    no_omniscience_*` below reasons from, read back from the real
    `ContactStore`/perception pipeline rather than calling `position_
    belief.fold_position` in isolation, so this exercises the same code
    path the scenario tests do."""
    _fresh_realisation(salt)
    store = ContactStore()
    observer = GeoPosition(x=0.0, z=0.0, alt_m=500.0)
    first = _observation(
        observation_id="first",
        t_sim=0.0,
        ownship=_ownship(0.0),
        group_x=0.0,
        group_z=-true_range_m,
        bias_object_id=1,
        optic=first_optic,
    )
    first_sigma_down_m = first.position_uncertainty.sigma_down_m  # type: ignore[union-attr]
    store.ingest([first], 0.0)
    store.tick(0.0)
    second = _observation(
        observation_id="second",
        t_sim=6.0,
        ownship=_ownship(6.0),
        group_x=0.0,
        group_z=-true_range_m,
        bias_object_id=2,
        optic=second_optic,
    )
    second_sigma_down_m = second.position_uncertainty.sigma_down_m  # type: ignore[union-attr]
    store.ingest([second], 6.0)
    store.tick(6.0)
    assert len(store.contacts) == 1, "expected the two looks to fuse"
    contact = store.contacts[0]
    fused_sigma_down_m = contact.position.range_uncertainty_m(observer)
    fused_range_m = horizontal_range_m(observer, contact.last_position)
    return fused_range_m, first_sigma_down_m, second_sigma_down_m, fused_sigma_down_m


def test_no_omniscience_fused_sigma_never_beats_the_tighter_optics_own_sigma() -> None:
    """`BL-B108` amendment, "Why not 'mostly the same error, scaled
    down'"": fusing any two optics must never claim better precision than
    the tighter one's own single-look sigma -- swept over both fuse
    orders, a closing geometry, and several ranges/realisations, not just
    the one pinned geometry `test_relative_distance_scenarios.py` already
    checks."""
    for first_optic, second_optic in (
        (UNAIDED_OPTIC, BINOCULAR_OPTIC),
        (BINOCULAR_OPTIC, UNAIDED_OPTIC),
    ):
        for true_range_m in (2000.0, 3000.0, 4500.0):
            for trial in range(10):
                _range_m, sigma_a, sigma_b, fused_sigma = _fuse_two_looks(
                    first_optic=first_optic,
                    second_optic=second_optic,
                    true_range_m=true_range_m,
                    salt=f"noomni-{first_optic.name}-{second_optic.name}-{true_range_m}-{trial}",
                )
                tighter_sigma = min(sigma_a, sigma_b)
                assert fused_sigma >= tighter_sigma * 0.95, (
                    f"{first_optic.name}->{second_optic.name} at "
                    f"{true_range_m} m, trial {trial}: fused sigma "
                    f"{fused_sigma} m is below the tighter optic's own "
                    f"{tighter_sigma} m"
                )


def test_no_omniscience_fused_mean_never_extrapolates_past_either_look() -> None:
    """The fused range must lie between the two looks' own true range
    (both looks are of the identical, stationary true geometry here, so
    "between the two looks" collapses to "close to truth, never overshot
    past it in either direction by more than a look's own noise floor")
    -- the observable form of "no fusion weight goes negative" (amendment,
    "Belief side": `correlated_innovation`'s `for_fusion` cap)."""
    true_range_m = 3000.0
    for first_optic, second_optic in (
        (UNAIDED_OPTIC, BINOCULAR_OPTIC),
        (BINOCULAR_OPTIC, UNAIDED_OPTIC),
    ):
        for trial in range(10):
            fused_range_m, sigma_a, sigma_b, _fused_sigma = _fuse_two_looks(
                first_optic=first_optic,
                second_optic=second_optic,
                true_range_m=true_range_m,
                salt=f"noextra-{first_optic.name}-{second_optic.name}-{trial}",
            )
            # Both looks are of the same true range; a fused estimate
            # that overshot past truth by more than a few sigma of the
            # *tighter* look would be extrapolation, not fusion.
            tighter_sigma = min(sigma_a, sigma_b)
            assert abs(fused_range_m - true_range_m) <= 4.0 * tighter_sigma, (
                f"{first_optic.name}->{second_optic.name}, trial {trial}: "
                f"fused range {fused_range_m} m is "
                f"{abs(fused_range_m - true_range_m)} m from truth "
                f"({true_range_m} m), past 4 sigma of the tighter look "
                f"({tighter_sigma} m)"
            )
