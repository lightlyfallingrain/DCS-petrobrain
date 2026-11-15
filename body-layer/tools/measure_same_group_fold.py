"""`BL-B110`/`BL-B108` -- "measure first" (user direction, 2026-11-09,
`plans/expected-area-check/explore-notes.md`, "Same-optic fold finding:
measure first"): how often does the **same** group, re-sighted, fold back
into one contact once the harness resamples **every** noise draw per trial
-- not just `perception.estimation._FIELD_REALISATION_SALT` (the field),
but also the look-to-look draw `z_look` (keyed by `(optic, poll_key=t_sim)`)
and the per-look bearing draw (keyed by `observation_id`). Those two terms
are what `test_relative_distance_sweep.py`'s Stage 1b implementer pass
(`plans/expected-area-check/plan.md`, "Stage 1b implementer pass, STOPPED
2026-11-09") found frozen to one draw per cell in the cross-time helpers --
`.claude/agent-memory/architect/feedback_noise_field_sweeps_need_an_ensemble.md`
and `.claude/agent-memory/implementer/
feedback_harness_resampling_fix_can_falsify_an_existing_guarantee.md` both
name the mechanism this script resamples around.

**This is a measurement tool, not a test.** It changes no production code
and no committed test fence (per the Stage 1b stop's own gate: "if any
BL-B108 fence or assertion moves, stop and report both outputs; do not edit
the fence" -- this script does not touch
`tests/test_relative_distance_sweep.py` or `tests/
test_expected_area_trigger.py` at all). It lives in `tools/` rather than
`tests/` because this project has no `slow`/`skip`-by-default pytest marker
infrastructure (checked: no `[tool.pytest.ini_options.markers]` entry, no
`conftest.py`) to keep an `n=300`-per-cell sweep (several minutes) out of
the ordinary `pytest -q` run -- `tools/summarize_detection_trace.py` and
its siblings are the existing precedent for a dev-facing script that is not
part of the committed suite.

**What it measures, per cell** (optic pair x range x gap x class, plus a
handful of surface cells): the *honest* fold rate -- found through
`first_optic` at `t0`, re-seen through `second_optic` at `t0 + gap_s`, same
true position both times (a genuine reacquisition, not the different-
groups memory-only defect `BL-B110`'s own trigger work targets) -- via the
real `belief.contacts.ContactStore.ingest`/`tick`, the same path production
code runs. For every trial that does *not* fold, it also classifies
whether the second look's own reported range read nearer or farther than
the hypothesis range (observer -> the first look's believed position) --
the same direction signal Stage 1b's adopted one-sided trigger reads
(`plans/expected-area-check/plan.md`, Decision 12). For `u_u` (naked-eye
twice) specifically, it dumps a handful of individual non-fold trials'
gate arithmetic, decomposed into an approximate down-range/cross-range
split (rotating `dx`/`dz` and the gate's own covariance sum into the
look's bearing frame, then reading each axis's own diagonal term in
isolation -- an approximation, since the true 2D Mahalanobis test does not
decompose additively when the off-diagonal term is non-zero, but good
enough to say which axis a failing trial's offset mostly lies along) plus
the elapsed-time growth term, so a reader can see *which* gate term is
doing the rejecting on an actual failing draw rather than guessing from the
aggregate rate alone.

Usage (from `body-layer/`, same interpreter/`PYTHONPATH` requirement as
every other tool here -- the world-model seam pulls in `pyproj`):

    PYTHONPATH=src:../world-model/src .venv/bin/python \\
        tools/measure_same_group_fold.py [--n 300] [--smoke] [--out PATH]

`--smoke` drops every cell's `n` to 20 (a few seconds, not several
minutes) to check the script runs before committing to a full sweep --
numbers from a smoke run are not meant to be quoted anywhere but a test of
this script itself.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass, field

import perception.estimation as estimation_module
from belief.association_over_time import (
    GATE_SIGMA_THRESHOLD,
    _contact_covariance,
    percept_position_uncertainty,
)
from belief.contacts import Contact, ContactStore
from belief.percept import Percept, percept_of
from belief.position_belief import correlated_innovation, covariance_from_uncertainty
from perception.estimation import perturbed_bearing_range, stable_down_sigma_m
from perception.geometry import (
    GeoPosition,
    bearing_deg,
    horizontal_range_m,
    project_from_bearing_range,
)
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC, Optic
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    Observation,
    OwnshipState,
    PositionUncertainty,
)

_CLASSIFICATION_LEVEL = 2

#: Same two classification strings `test_expected_area_trigger.py` uses --
#: `OP_ARMORED` is a moving class (`plausible_speed_mps` returns 8.0 m/s,
#: `test_plausible_speed_mps_default_is_eight_not_the_old_flat_twenty`),
#: `s-125` is a real `_KEYWORD_PROFILES` match with `installation_
#: component=True` (`perception.object_model`), a zero-growth class.
_MOVING_CLASSIFICATION_RAW = "OP_ARMORED"
_STATIONARY_CLASSIFICATION_RAW = "s-125"

_CLASSES: tuple[tuple[str, str], ...] = (
    ("armour", _MOVING_CLASSIFICATION_RAW),
    ("installation", _STATIONARY_CLASSIFICATION_RAW),
)

_OPTIC_PAIRS: tuple[tuple[Optic, Optic, str], ...] = (
    (UNAIDED_OPTIC, UNAIDED_OPTIC, "u_u"),
    (BINOCULAR_OPTIC, BINOCULAR_OPTIC, "b_b"),
    (UNAIDED_OPTIC, BINOCULAR_OPTIC, "u_b"),
    (BINOCULAR_OPTIC, UNAIDED_OPTIC, "b_u"),
)

_RANGES_KM: tuple[float, ...] = (1.0, 2.0, 3.0, 4.5)
_GAPS_S: tuple[float, ...] = (2.0, 4.0, 6.0, 30.0, 120.0)

#: Surface (ground-unit) cells, `u_u` only, per the task's "at least" --
#: `AGL_M` is `ownship.alt_m` directly, since the surface branch places the
#: group at world altitude 0.0 (mirrors `test_relative_distance_sweep.
#: _observation`'s own surface convention).
_SURFACE_AGL_M: tuple[float, ...] = (100.0, 500.0)

_DEFAULT_N = 300
_DEFAULT_AIR_ALT_M = 500.0


def _ownship(t_sim: float, alt_m: float) -> OwnshipState:
    return OwnshipState(t_sim=t_sim, x=0.0, z=0.0, alt_m=alt_m, heading_true_deg=0.0)


def _observation(
    *,
    observation_id: str,
    t_sim: float,
    ownship: OwnshipState,
    group_z: float,
    bias_object_id: int,
    optic: Optic,
    classification_raw: str,
    surface: bool,
) -> Observation:
    """`test_relative_distance_sweep.py`'s own `_observation` shape,
    duplicated rather than imported (no test or tool in this project
    imports another test module's private helpers) -- air path unchanged,
    surface path mirrors that file's `surface=True` branch (ground unit at
    world altitude 0.0, `height_above_unit_m = ownship.alt_m`)."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    centroid_alt_m = ownship.alt_m if not surface else 0.0
    centroid = GeoPosition(x=0.0, z=group_z, alt_m=centroid_alt_m)
    true_bearing_deg = bearing_deg(observer, centroid)
    true_range_m = horizontal_range_m(observer, centroid)
    sigma_cross_m, sigma_down_m = estimation_module.look_sigma_m(true_range_m, optic)
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
        classification_raw=classification_raw,
        bearing_deg=estimated_bearing_deg,
        range_m=estimated_range_m,
        ownship_at_observation=ownship,
        derived_world_position=None,
        provenance="test",
        classification_level=_CLASSIFICATION_LEVEL,
        continues_observation_id=None,
        surface_alt_m=surface_alt_m,
        position_uncertainty=PositionUncertainty(
            sigma_cross_m=sigma_cross_m,
            sigma_down_m=sigma_down_m,
            sigma_down_stable_m=stable_down_sigma_m(sigma_down_m),
            optic_class=optic.name,
        ),
    )


def _fresh_realisation(salt: str) -> None:
    estimation_module._FIELD_REALISATION_SALT = salt
    estimation_module._field_frequencies.cache_clear()


def _restore_field_salt() -> None:
    estimation_module._FIELD_REALISATION_SALT = ""
    estimation_module._field_frequencies.cache_clear()


@dataclass
class _NonFoldSample:
    """One non-fold trial's raw numbers, kept for `u_u`'s mechanism dump."""

    trial: int
    dx: float
    dz: float
    elapsed_s: float
    hypothesis_bearing_deg: float
    hypothesis_range_m: float
    percept_range_m: float
    s_down: float
    s_cross: float
    d_down: float
    d_cross: float
    z_down: float
    z_cross: float
    total_mahalanobis_sq: float
    growth_contribution_m2: float


@dataclass
class _CellResult:
    label: str
    n: int
    fold_rate: float
    non_fold_count: int
    b_farther_count: int
    b_nearer_count: int
    non_fold_samples: list[_NonFoldSample] = field(default_factory=list)

    @property
    def b_farther_fraction_of_non_folds(self) -> float:
        return (
            self.b_farther_count / self.non_fold_count if self.non_fold_count else 0.0
        )

    @property
    def b_nearer_fraction_of_non_folds(self) -> float:
        return self.b_nearer_count / self.non_fold_count if self.non_fold_count else 0.0


def _gate_direction_and_diagnostics(
    percept_b: Percept, contact_a: Contact, now_sim: float, *, want_diagnostics: bool
) -> tuple[bool, _NonFoldSample | None]:
    """Replicates `association_over_time.passes_gate`'s own body (same
    reason `test_expected_area_trigger.py::_as_if_gate` duplicates it
    rather than importing a private function: this needs the intermediate
    numbers the real function does not return) to answer two things for
    one trial: did the hypothesis-range direction read nearer or farther
    (`percept_b.range_m < hypothesis_range_m`, Stage 1b's own Decision 12
    direction clause), and -- only when `want_diagnostics` -- the gate's
    own covariance decomposition for the mechanism dump.

    Returns `(b_reads_nearer, sample_or_none)`. This does not call the real
    `passes_gate` at all; it is read-only measurement against the same
    formula, never a production code path."""
    percept_position = GeoPosition(
        x=percept_b.ownship_at_observation.x,
        z=percept_b.ownship_at_observation.z,
        alt_m=percept_b.ownship_at_observation.alt_m,
    )
    implied = project_from_bearing_range(
        percept_position, percept_b.bearing_deg, percept_b.range_m
    )
    dx = implied.x - contact_a.last_position.x
    dz = implied.z - contact_a.last_position.z
    elapsed_s = max(0.0, now_sim - contact_a.last_seen_sim)
    percept_uncertainty = percept_position_uncertainty(percept_b)
    observer = percept_position
    hypothesis_bearing_deg = bearing_deg(observer, contact_a.last_position)
    hypothesis_range_m = horizontal_range_m(observer, contact_a.last_position)
    b_reads_nearer = percept_b.range_m < hypothesis_range_m

    if not want_diagnostics:
        return b_reads_nearer, None

    hypothesis_scale = (
        hypothesis_range_m / percept_b.range_m if percept_b.range_m > 0.0 else 1.0
    )
    hypothesis_uncertainty = PositionUncertainty(
        sigma_cross_m=percept_uncertainty.sigma_cross_m * hypothesis_scale,
        sigma_down_m=percept_uncertainty.sigma_down_m * hypothesis_scale,
        sigma_down_stable_m=percept_uncertainty.sigma_down_stable_m * hypothesis_scale,
        optic_class=percept_uncertainty.optic_class,
    )
    look_covariance = covariance_from_uncertainty(
        hypothesis_uncertainty, percept_b.bearing_deg
    )
    contact_covariance_raw = contact_a.position.covariance
    contact_covariance_inflated = _contact_covariance(contact_a, elapsed_s)
    growth_contribution_m2 = (
        contact_covariance_inflated.trace() - contact_covariance_raw.trace()
    )
    s, _c, _kappa = correlated_innovation(
        contact_a.position,
        contact_covariance_inflated,
        look_covariance,
        correlation_bearing_deg=hypothesis_bearing_deg,
        correlation_range_m=hypothesis_range_m,
        correlation_optic_class=hypothesis_uncertainty.optic_class,
        correlation_sigma_down_stable_m=hypothesis_uncertainty.sigma_down_stable_m,
    )
    total_mahalanobis_sq = s.mahalanobis_squared(dx, dz)

    # Approximate down/cross decomposition: rotate (dx, dz) and S into the
    # hypothesis bearing frame (down axis along the bearing, cross
    # perpendicular -- `position_belief.covariance_from_uncertainty`'s own
    # convention), then read each axis's diagonal term in isolation. This
    # is not an exact split of a 2D Mahalanobis test when S's off-diagonal
    # term is non-zero, but it is enough to say which axis a given
    # failing trial's offset mostly lies along.
    theta = math.radians(hypothesis_bearing_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    d_down = dx * cos_t + dz * sin_t
    d_cross = -dx * sin_t + dz * cos_t
    s_down = s.xx * cos_t * cos_t + 2.0 * s.xz * cos_t * sin_t + s.zz * sin_t * sin_t
    s_cross = s.xx * sin_t * sin_t - 2.0 * s.xz * cos_t * sin_t + s.zz * cos_t * cos_t
    z_down = (d_down * d_down) / s_down if s_down > 0.0 else math.inf
    z_cross = (d_cross * d_cross) / s_cross if s_cross > 0.0 else math.inf

    sample = _NonFoldSample(
        trial=-1,
        dx=dx,
        dz=dz,
        elapsed_s=elapsed_s,
        hypothesis_bearing_deg=hypothesis_bearing_deg,
        hypothesis_range_m=hypothesis_range_m,
        percept_range_m=percept_b.range_m,
        s_down=s_down,
        s_cross=s_cross,
        d_down=d_down,
        d_cross=d_cross,
        z_down=z_down,
        z_cross=z_cross,
        total_mahalanobis_sq=total_mahalanobis_sq,
        growth_contribution_m2=growth_contribution_m2,
    )
    return b_reads_nearer, sample


def _run_cell(
    *,
    label: str,
    first_optic: Optic,
    second_optic: Optic,
    range_km: float,
    gap_s: float,
    classification_raw: str,
    n: int,
    salt_prefix: str,
    air_alt_m: float | None,
    surface_agl_m: float | None,
    diagnostics_label: str | None,
    diagnostics_budget: int,
) -> _CellResult:
    """One grid cell -- `n` trials, **every** noise draw resampled per
    trial: the field salt (existing seam), the observation ids
    (`f"first-{trial}"`/`f"second-{trial}"`), and the time base
    (`t0 = trial * 1e-3`, second look at `t0 + gap_s`) -- the Stage 1b
    harness fix's own recipe, applied here to the honest fold rate itself
    rather than to the not-yet-built trigger.

    Exactly one of `air_alt_m`/`surface_agl_m` is set; the other is
    `None`. `diagnostics_label` gates the mechanism dump (only meaningful
    for `u_u`); `diagnostics_budget` caps how many non-fold trials are
    kept for it, across the whole run, not just this cell."""
    surface = surface_agl_m is not None
    alt_m = surface_agl_m if surface else air_alt_m
    assert alt_m is not None
    fold_count = 0
    non_fold_count = 0
    b_farther_count = 0
    b_nearer_count = 0
    samples: list[_NonFoldSample] = []
    group_z = -range_km * 1000.0
    for trial in range(n):
        _fresh_realisation(f"{salt_prefix}-{trial}")
        t0 = trial * 1e-3
        t_sim_first = t0
        t_sim_second = t0 + gap_s
        store = ContactStore()
        first = _observation(
            observation_id=f"first-{trial}",
            t_sim=t_sim_first,
            ownship=_ownship(t_sim_first, alt_m),
            group_z=group_z,
            bias_object_id=1,
            optic=first_optic,
            classification_raw=classification_raw,
            surface=surface,
        )
        store.ingest([first], t_sim_first)
        store.tick(t_sim_first)
        assert len(store.contacts) == 1
        contact_a = store.contacts[0]

        second = _observation(
            observation_id=f"second-{trial}",
            t_sim=t_sim_second,
            ownship=_ownship(t_sim_second, alt_m),
            group_z=group_z,
            bias_object_id=2,
            optic=second_optic,
            classification_raw=classification_raw,
            surface=surface,
        )
        percept_b = percept_of(second)
        want_diagnostics = (
            diagnostics_label == label and len(samples) < diagnostics_budget
        )
        b_reads_nearer, sample = _gate_direction_and_diagnostics(
            percept_b, contact_a, t_sim_second, want_diagnostics=want_diagnostics
        )

        store.ingest([second], t_sim_second)
        store.tick(t_sim_second)
        folded = len(store.contacts) == 1
        if folded:
            fold_count += 1
        else:
            non_fold_count += 1
            if b_reads_nearer:
                b_nearer_count += 1
            else:
                b_farther_count += 1
            if sample is not None:
                sample.trial = trial
                samples.append(sample)
    return _CellResult(
        label=label,
        n=n,
        fold_rate=fold_count / n,
        non_fold_count=non_fold_count,
        b_farther_count=b_farther_count,
        b_nearer_count=b_nearer_count,
        non_fold_samples=samples,
    )


def _mechanism_verdict(sample: _NonFoldSample) -> str:
    """One-line verdict for a single non-fold sample: which axis's
    approximate z-score (down/cross) dominates the total, and how large
    the elapsed-time growth contribution was relative to the un-inflated
    contact covariance -- read together, not a formal attribution."""
    dominant = "down-range" if sample.z_down >= sample.z_cross else "cross-range"
    axis_sum = sample.z_down + sample.z_cross
    threshold_sq = GATE_SIGMA_THRESHOLD**2
    correlation_note = (
        " (neither axis alone clears the threshold -- the correlated "
        "off-diagonal term is what pushes the real test over)"
        if sample.z_down < threshold_sq
        and sample.z_cross < threshold_sq
        and sample.total_mahalanobis_sq >= threshold_sq
        else ""
    )
    return (
        f"trial {sample.trial}: {dominant} dominates "
        f"(z_down^2={sample.z_down:.2f}, z_cross^2={sample.z_cross:.2f}, "
        f"axis sum={axis_sum:.2f}, real mahalanobis^2={sample.total_mahalanobis_sq:.2f}, "
        f"threshold^2={threshold_sq:.1f}){correlation_note}; "
        f"elapsed={sample.elapsed_s:.1f}s, growth contributed "
        f"{sample.growth_contribution_m2:.0f} m^2 to the contact's own "
        f"covariance; percept range {sample.percept_range_m:.0f} m vs "
        f"hypothesis range {sample.hypothesis_range_m:.0f} m "
        f"(dx={sample.dx:.0f}, dz={sample.dz:.0f})"
    )


def _format_table(results: list[_CellResult]) -> str:
    lines = [
        "| cell | n | fold rate | non-fold | B farther | B nearer |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.label} | {r.n} | {r.fold_rate:.1%} | {r.non_fold_count} | "
            f"{r.b_farther_fraction_of_non_folds:.0%} | "
            f"{r.b_nearer_fraction_of_non_folds:.0%} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=_DEFAULT_N)
    parser.add_argument("--smoke", action="store_true", help="n=20 per cell")
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument(
        "--diagnostics-budget",
        type=int,
        default=6,
        help="max u_u non-fold trials to dump gate arithmetic for",
    )
    args = parser.parse_args(argv)
    n = 20 if args.smoke else args.n

    results: list[_CellResult] = []
    t_start = time.time()
    try:
        for first_optic, second_optic, pair_label in _OPTIC_PAIRS:
            for range_km in _RANGES_KM:
                for gap_s in _GAPS_S:
                    for class_label, classification_raw in _CLASSES:
                        label = (
                            f"{pair_label} {range_km}km gap={gap_s:g}s {class_label}"
                        )
                        result = _run_cell(
                            label=label,
                            first_optic=first_optic,
                            second_optic=second_optic,
                            range_km=range_km,
                            gap_s=gap_s,
                            classification_raw=classification_raw,
                            n=n,
                            salt_prefix=f"fold-{pair_label}-{range_km}-{gap_s}-{class_label}",
                            air_alt_m=_DEFAULT_AIR_ALT_M,
                            surface_agl_m=None,
                            diagnostics_label=f"u_u {range_km}km gap={gap_s:g}s {class_label}"
                            if pair_label == "u_u"
                            else None,
                            diagnostics_budget=args.diagnostics_budget,
                        )
                        results.append(result)

        # Surface (ground-unit) cells, u_u only, both AGL bands, same
        # range/gap/class grid.
        for agl_m in _SURFACE_AGL_M:
            for range_km in _RANGES_KM:
                for gap_s in _GAPS_S:
                    for class_label, classification_raw in _CLASSES:
                        label = (
                            f"u_u surface {agl_m:g}m-AGL {range_km}km "
                            f"gap={gap_s:g}s {class_label}"
                        )
                        result = _run_cell(
                            label=label,
                            first_optic=UNAIDED_OPTIC,
                            second_optic=UNAIDED_OPTIC,
                            range_km=range_km,
                            gap_s=gap_s,
                            classification_raw=classification_raw,
                            n=n,
                            salt_prefix=f"fold-surface-{agl_m}-{range_km}-{gap_s}-{class_label}",
                            air_alt_m=None,
                            surface_agl_m=agl_m,
                            diagnostics_label=None,
                            diagnostics_budget=0,
                        )
                        results.append(result)
    finally:
        _restore_field_salt()

    elapsed = time.time() - t_start
    table = _format_table(results)
    mechanism_lines = []
    for r in results:
        if r.non_fold_samples:
            mechanism_lines.append(f"### {r.label}")
            for sample in r.non_fold_samples:
                mechanism_lines.append(f"- {_mechanism_verdict(sample)}")

    report = f"n={n} per cell, {len(results)} cells, {elapsed:.1f}s total\n\n{table}\n"
    if mechanism_lines:
        report += "\n## u_u non-fold mechanism dump\n\n" + "\n".join(mechanism_lines)

    print(report)
    if args.out:
        with open(args.out, "w") as f:
            f.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
