"""`plans/same-optic-gate-indefinite/debug.md`'s second pass -- "measure
first" applied to the gate's own calibration, not just its fold rate.

`tools/measure_same_group_fold.py` answers "how often does the same
group, re-sighted through one optic, fold into one contact". This tool
answers the question underneath it: for a fixed same-optic, same-group
geometry, does `belief.position_belief.correlated_innovation`'s own `S`
(the covariance `association_over_time.passes_gate`/`contacts_plausibly_
same` run the Mahalanobis test against) actually match the covariance of
the *real* simulated innovation -- and if not, where does it diverge.

**What it measures, per cell:**

- The empirical covariance of the actual simulated innovation `(dx, dz)`
  over a resampled ensemble (same resampling recipe as `measure_same_
  group_fold.py`: field salt, observation ids, poll times all vary per
  trial), compared against the gate's own modelled `S`.
- The Mahalanobis^2 calibration: the fraction of trials with `S.
  mahalanobis_squared(dx, dz) > GATE_SIGMA_THRESHOLD**2` (9.0), which a
  correctly-sized gate should reject at about 1.1% (chi-square(2)'s own
  tail at that threshold) -- and the same fraction computed against the
  *empirical* covariance instead of the model `S`, as a sanity check
  that the test/threshold machinery itself is sound.
- `S`'s own `det(S)/trace(S)^2` ratio, to separate "near-singular `S`,
  floor-clamped on inversion" rejections from well-conditioned ones.
- Which cap (`per_axis_cap`/`psd_cap`) binds, and by how much, on each
  trial.
- A down/cross decomposition (approximate, like `measure_same_group_
  fold.py`'s own mechanism dump -- not an exact split when `S`'s
  off-diagonal term is non-zero) and a world-frame eigen comparison, to
  see whether a mismatch is in `S`'s overall magnitude (trace) or its
  shape (eigenvalue allocation/orientation).
- A **ground-truth probe** (`correlated_innovation_true_axis`, test-only,
  can never ship -- no-omniscience): rebuilds `C`'s correlation kernel
  and axis unit vectors from each look's *true* bearing/range instead of
  its *reported* (perturbed) one, to test whether `C`'s direction being
  built off a noisy reported bearing is what misaligns `S`'s shape.
- A direct true-vs-model correlation check (`measure_true_vs_model_
  correlation`): the empirical correlation between the two looks' own
  `perception.estimation._stable_fraction` draws at identical geometry,
  compared to the model's `effective_down_correlation`.

**Findings this tool produced (second pass, 2026-11-09), so a later
reader does not have to re-derive them from the numbers alone:**

1. The field-based stable-term correlation model is exact at matched
   geometry (measured ~0.96 true vs ~1.0 model's stable-part-only
   correlation, which match once the independent `z_look` share the
   model already excludes is accounted for) -- the leading hypothesis
   ("the simulation draws a different correlation than `C` assumes") is
   **not** the cause, for the field term.
2. Before this pass's fix, `S` could land close enough to the exact PSD
   boundary (the first pass's own cap) that `.inverse()`'s determinant
   floor clamped it on ~4-6% of same-optic short-gap gate evaluations,
   producing Mahalanobis values in the billions. `_MIN_S_DETERMINANT_
   RATIO` (`position_belief.py`) fixes that -- confirmed 0% near-singular
   after the fix. **This does not move the overall rejection rate**: the
   same trials still clear the 9.0 threshold at a finite, merely-large
   Mahalanobis value. It is numerical hygiene (and protects the fold's
   own gain computation from the same fragile regime), not a calibration
   fix.
3. The true-axis probe **refutes** the orientation-mismatch theory:
   rebuilding `C`'s axis from the true bearing/range does not reduce the
   rejection rate (if anything, slightly worse for `u_u`, about the same
   for `b_b`). The root cause of the remaining ~7-11%-vs-~1.1% residual
   over-rejection in well-conditioned cases was not identified in this
   pass.

This is a measurement tool, not a test (same posture as `measure_same_
group_fold.py`: no committed fence depends on it, and it changes no
production code of its own). Run from `body-layer/`:

    PYTHONPATH=src:../world-model/src .venv/bin/python \\
        tools/measure_gate_calibration.py [--n 2000] [--smoke]
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from dataclasses import dataclass

from measure_same_group_fold import (
    _fresh_realisation,
    _observation,
    _restore_field_salt,
)

import belief.position_belief as pb_module
from belief.association_over_time import (
    _contact_covariance,
    percept_position_uncertainty,
)
from belief.contacts import ContactStore
from belief.percept import percept_of
from belief.position_belief import (
    Covariance2D,
    PositionEstimate,
    _Matrix2D,
    correlated_innovation,
    covariance_from_uncertainty,
)
from perception.estimation import (
    _stable_fraction,
    effective_down_correlation,
    stable_range_correlation,
)
from perception.geometry import (
    GeoPosition,
    angular_delta_deg,
    bearing_deg,
    horizontal_range_m,
    project_from_bearing_range,
)
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC, Optic
from perception.source import OwnshipState, PositionUncertainty

_GATE_SIGMA_THRESHOLD_SQ = 9.0


def _ownship(t_sim: float, alt_m: float) -> OwnshipState:
    return OwnshipState(t_sim=t_sim, x=0.0, z=0.0, alt_m=alt_m, heading_true_deg=0.0)


def correlated_innovation_true_axis(
    prior: PositionEstimate,
    prior_covariance: Covariance2D,
    look_covariance: Covariance2D,
    *,
    correlation_sigma_down_stable_m: float,
    correlation_optic_class: str,
    true_anchor_bearing_deg: float,
    true_anchor_range_m: float,
    true_look_bearing_deg: float,
    true_look_range_m: float,
) -> Covariance2D:
    """Orientation-mismatch probe: `correlated_innovation`'s own cap/`C`
    arithmetic, except the correlation kernel (`d_bearing_deg`/`range_
    ratio_value`) and `C`'s own axis unit vectors are built from each
    look's TRUE bearing/range, never its reported (perturbed) one -- a
    ground-truth probe that can never ship (no-omniscience), used only
    to test whether `C`'s direction being built off a noisy reported
    bearing, rather than the true bearing the field correlation actually
    lives along, misaligns `S`'s shape. Module docstring finding 3: it
    does not -- rejection rate does not improve under this variant."""
    anchor = prior.anchor
    if anchor is None:
        return prior_covariance + look_covariance

    d_bearing_deg = angular_delta_deg(true_look_bearing_deg, true_anchor_bearing_deg)
    hi = max(true_look_range_m, true_anchor_range_m)
    lo = max(1.0, min(true_look_range_m, true_anchor_range_m))
    range_ratio_value = hi / lo
    rho_view, rho_near = stable_range_correlation(
        d_bearing_deg, range_ratio_value, anchor.optic_class, correlation_optic_class
    )
    rho_eff = effective_down_correlation(rho_view, rho_near)
    c_down = rho_eff * anchor.sigma_down_stable_m * correlation_sigma_down_stable_m

    anchor_x, anchor_z = pb_module._down_axis_unit(true_anchor_bearing_deg)
    look_x, look_z = pb_module._down_axis_unit(true_look_bearing_deg)
    sum_covariance = prior_covariance + look_covariance
    k_xx = 2.0 * anchor_x * look_x
    k_zz = 2.0 * anchor_z * look_z
    k_xz = anchor_x * look_z + anchor_z * look_x
    var_prior_along = pb_module._down_variance_along(
        prior_covariance, true_anchor_bearing_deg
    )
    var_look_along = pb_module._down_variance_along(
        look_covariance, true_look_bearing_deg
    )
    per_axis_cap = max(0.0, min(var_prior_along, var_look_along))
    psd_cap = pb_module._max_c_down_for_psd(sum_covariance, k_xx, k_zz, k_xz)
    max_c_down = min(per_axis_cap, psd_cap)
    c_down = max(0.0, min(max_c_down, c_down))

    c_matrix = _Matrix2D(
        xx=c_down * anchor_x * look_x,
        xz=c_down * anchor_x * look_z,
        zx=c_down * anchor_z * look_x,
        zz=c_down * anchor_z * look_z,
    )
    c_sym = c_matrix + c_matrix.transpose()
    return sum_covariance - c_sym.as_symmetric_covariance()


@dataclass
class _CapDiagnostics:
    c_down_raw: float
    c_down_capped: float
    per_axis_cap: float
    psd_cap: float
    binding: str
    rho_eff: float


def _cap_diagnostics(
    prior: PositionEstimate,
    prior_covariance: Covariance2D,
    look_covariance: Covariance2D,
    *,
    correlation_bearing_deg: float,
    correlation_range_m: float,
    correlation_optic_class: str,
    correlation_sigma_down_stable_m: float,
) -> _CapDiagnostics:
    """Replica of `correlated_innovation`'s cap arithmetic, exposing the
    raw (uncapped) `c_down` and which cap binds -- `correlated_
    innovation` itself does not return these intermediates."""
    anchor = prior.anchor
    d_bearing_deg = angular_delta_deg(correlation_bearing_deg, anchor.bearing_deg)
    hi = max(correlation_range_m, anchor.range_m)
    lo = max(1.0, min(correlation_range_m, anchor.range_m))
    range_ratio_value = hi / lo
    rho_view, rho_near = stable_range_correlation(
        d_bearing_deg, range_ratio_value, anchor.optic_class, correlation_optic_class
    )
    rho_eff = effective_down_correlation(rho_view, rho_near)
    c_down_raw = rho_eff * anchor.sigma_down_stable_m * correlation_sigma_down_stable_m

    anchor_x, anchor_z = pb_module._down_axis_unit(anchor.bearing_deg)
    look_x, look_z = pb_module._down_axis_unit(correlation_bearing_deg)
    sum_covariance = prior_covariance + look_covariance
    k_xx = 2.0 * anchor_x * look_x
    k_zz = 2.0 * anchor_z * look_z
    k_xz = anchor_x * look_z + anchor_z * look_x
    var_prior_along = pb_module._down_variance_along(
        prior_covariance, anchor.bearing_deg
    )
    var_look_along = pb_module._down_variance_along(
        look_covariance, correlation_bearing_deg
    )
    per_axis_cap = max(0.0, min(var_prior_along, var_look_along))
    psd_cap = pb_module._max_c_down_for_psd(sum_covariance, k_xx, k_zz, k_xz)
    max_c_down = min(per_axis_cap, psd_cap)
    c_down_capped = max(0.0, min(max_c_down, c_down_raw))
    binding = (
        "none"
        if c_down_capped >= c_down_raw - 1e-9
        else ("psd_cap" if psd_cap < per_axis_cap else "per_axis_cap")
    )
    return _CapDiagnostics(
        c_down_raw=c_down_raw,
        c_down_capped=c_down_capped,
        per_axis_cap=per_axis_cap,
        psd_cap=psd_cap,
        binding=binding,
        rho_eff=rho_eff,
    )


@dataclass
class _TrialSample:
    dx: float
    dz: float
    s: Covariance2D
    mahalanobis_sq: float
    hypothesis_bearing_deg: float
    det_ratio: float
    d_down: float
    d_cross: float
    s_down: float
    s_cross: float
    s_downcross: float
    cap_diag: _CapDiagnostics
    maha_true_axis: float


def gate_s_and_innovation(
    *,
    optic: Optic,
    range_km: float,
    gap_s: float,
    classification_raw: str,
    trial: int,
    salt_prefix: str,
    air_alt_m: float,
    same_bias_object_id: bool,
) -> _TrialSample:
    """One trial's worth of the gate's own `S`, the real simulated
    innovation `(dx, dz)`, and the diagnostics `run_cell` aggregates --
    see module docstring."""
    _fresh_realisation(f"{salt_prefix}-{trial}")
    t0 = trial * 1e-3
    t_sim_first = t0
    t_sim_second = t0 + gap_s
    group_z = -range_km * 1000.0

    store = ContactStore()
    first = _observation(
        observation_id=f"first-{trial}",
        t_sim=t_sim_first,
        ownship=_ownship(t_sim_first, air_alt_m),
        group_z=group_z,
        bias_object_id=1,
        optic=optic,
        classification_raw=classification_raw,
        surface=False,
    )
    store.ingest([first], t_sim_first)
    store.tick(t_sim_first)
    contact_a = store.contacts[0]

    second = _observation(
        observation_id=f"second-{trial}",
        t_sim=t_sim_second,
        ownship=_ownship(t_sim_second, air_alt_m),
        group_z=group_z,
        bias_object_id=1 if same_bias_object_id else 2,
        optic=optic,
        classification_raw=classification_raw,
        surface=False,
    )
    percept_b = percept_of(second)

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
    elapsed_s = max(0.0, t_sim_second - contact_a.last_seen_sim)

    percept_uncertainty = percept_position_uncertainty(percept_b)
    observer = percept_position
    hypothesis_bearing_deg = bearing_deg(observer, contact_a.last_position)
    hypothesis_range_m = horizontal_range_m(observer, contact_a.last_position)
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

    contact_cov = _contact_covariance(contact_a, elapsed_s)
    cap_diag = _cap_diagnostics(
        contact_a.position,
        contact_cov,
        look_covariance,
        correlation_bearing_deg=hypothesis_bearing_deg,
        correlation_range_m=hypothesis_range_m,
        correlation_optic_class=hypothesis_uncertainty.optic_class,
        correlation_sigma_down_stable_m=hypothesis_uncertainty.sigma_down_stable_m,
    )

    # True-geometry axis variant (ground-truth probe, test only): the
    # anchor's and look's true bearing/range are both the observer-at-
    # origin -> centroid geometry (identical here: stationary ownship
    # and group).
    observer_origin = GeoPosition(x=0.0, z=0.0, alt_m=air_alt_m)
    centroid = GeoPosition(x=0.0, z=group_z, alt_m=air_alt_m)
    true_bearing = bearing_deg(observer_origin, centroid)
    true_range = horizontal_range_m(observer_origin, centroid)
    s_true_axis = correlated_innovation_true_axis(
        contact_a.position,
        contact_cov,
        look_covariance,
        correlation_sigma_down_stable_m=hypothesis_uncertainty.sigma_down_stable_m,
        correlation_optic_class=hypothesis_uncertainty.optic_class,
        true_anchor_bearing_deg=true_bearing,
        true_anchor_range_m=true_range,
        true_look_bearing_deg=true_bearing,
        true_look_range_m=true_range,
    )
    maha_true_axis = s_true_axis.mahalanobis_squared(dx, dz)

    s, _c, _kappa_view = correlated_innovation(
        contact_a.position,
        contact_cov,
        look_covariance,
        correlation_bearing_deg=hypothesis_bearing_deg,
        correlation_range_m=hypothesis_range_m,
        correlation_optic_class=hypothesis_uncertainty.optic_class,
        correlation_sigma_down_stable_m=hypothesis_uncertainty.sigma_down_stable_m,
    )
    mahalanobis_sq = s.mahalanobis_squared(dx, dz)
    det_s = s.xx * s.zz - s.xz * s.xz
    trace_s = s.xx + s.zz
    det_ratio = det_s / (trace_s * trace_s) if trace_s > 0.0 else 0.0

    theta = math.radians(hypothesis_bearing_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    d_down = dx * cos_t + dz * sin_t
    d_cross = -dx * sin_t + dz * cos_t
    s_down = s.xx * cos_t * cos_t + 2.0 * s.xz * cos_t * sin_t + s.zz * sin_t * sin_t
    s_cross = s.xx * sin_t * sin_t - 2.0 * s.xz * cos_t * sin_t + s.zz * cos_t * cos_t
    s_downcross = cos_t * sin_t * (s.zz - s.xx) + (cos_t * cos_t - sin_t * sin_t) * s.xz

    return _TrialSample(
        dx=dx,
        dz=dz,
        s=s,
        mahalanobis_sq=mahalanobis_sq,
        hypothesis_bearing_deg=hypothesis_bearing_deg,
        det_ratio=det_ratio,
        d_down=d_down,
        d_cross=d_cross,
        s_down=s_down,
        s_cross=s_cross,
        s_downcross=s_downcross,
        cap_diag=cap_diag,
        maha_true_axis=maha_true_axis,
    )


def _eig(xx: float, zz: float, xz: float) -> tuple[float, float, float]:
    """Eigenvalues (`lam1 >= lam2`) and `lam1`'s own eigenvector angle,
    degrees from the x-axis -- for the world-frame shape comparison."""
    trace = xx + zz
    det = xx * zz - xz * xz
    disc = max(0.0, trace * trace - 4.0 * det)
    sq = math.sqrt(disc)
    lam1 = (trace + sq) / 2.0
    lam2 = (trace - sq) / 2.0
    if xz != 0.0:
        angle = math.degrees(math.atan2(lam1 - xx, xz))
    else:
        angle = 0.0 if xx >= zz else 90.0
    return lam1, lam2, angle


def run_cell(
    *,
    optic: Optic,
    label: str,
    range_km: float,
    gap_s: float,
    classification_raw: str,
    n: int,
    same_bias_object_id: bool,
) -> None:
    """One cell's worth of calibration diagnostics, printed -- see module
    docstring for what each line means."""
    samples: list[_TrialSample] = []
    try:
        for trial in range(n):
            samples.append(
                gate_s_and_innovation(
                    optic=optic,
                    range_km=range_km,
                    gap_s=gap_s,
                    classification_raw=classification_raw,
                    trial=trial,
                    salt_prefix=f"calib-{label}-{range_km}-{gap_s}",
                    air_alt_m=500.0,
                    same_bias_object_id=same_bias_object_id,
                )
            )
    finally:
        _restore_field_salt()

    n_f = float(n)
    dxs = [sample.dx for sample in samples]
    dzs = [sample.dz for sample in samples]
    mean_dx = statistics.fmean(dxs)
    mean_dz = statistics.fmean(dzs)
    emp_xx = sum((x - mean_dx) ** 2 for x in dxs) / n_f
    emp_zz = sum((z - mean_dz) ** 2 for z in dzs) / n_f
    emp_xz = sum((x - mean_dx) * (z - mean_dz) for x, z in zip(dxs, dzs)) / n_f

    mean_s_xx = statistics.fmean(sample.s.xx for sample in samples)
    mean_s_zz = statistics.fmean(sample.s.zz for sample in samples)
    mean_s_xz = statistics.fmean(sample.s.xz for sample in samples)

    maha_sqs = [sample.mahalanobis_sq for sample in samples]
    det_ratios = [sample.det_ratio for sample in samples]
    frac_over_9 = sum(1 for m in maha_sqs if m > _GATE_SIGMA_THRESHOLD_SQ) / n_f

    print(f"=== {label}: {range_km}km gap={gap_s}s n={n} ===")
    print(f"  mean offset: dx={mean_dx:.1f} dz={mean_dz:.1f}")
    print(
        f"  empirical Cov: xx={emp_xx:.1f} zz={emp_zz:.1f} xz={emp_xz:.1f}  "
        f"(trace={emp_xx + emp_zz:.1f})"
    )
    print(
        f"  model S (mean over trials): xx={mean_s_xx:.1f} zz={mean_s_zz:.1f} "
        f"xz={mean_s_xz:.1f}  (trace={mean_s_xx + mean_s_zz:.1f})"
    )
    print(
        f"  ratio empirical/model trace: "
        f"{(emp_xx + emp_zz) / (mean_s_xx + mean_s_zz):.3f}"
    )
    print(
        f"  Mahalanobis^2 > 9.0 (gate rejects): {frac_over_9:.1%} "
        f"(chi2(2) predicts ~1.1%)"
    )
    sorted_maha = sorted(maha_sqs)
    print(
        f"  Mahalanobis^2 percentiles: p50={statistics.median(maha_sqs):.2f} "
        f"p90={sorted_maha[int(0.9 * n)]:.2f} "
        f"p99={sorted_maha[int(0.99 * n)]:.2f} max={max(maha_sqs):.2f}"
    )

    near_singular = sum(1 for r in det_ratios if r < 1e-6) / n_f
    print(
        f"  det(S)/trace(S)^2 ratio: min={min(det_ratios):.3e} frac<1e-6={near_singular:.1%}"
    )
    rejected_near_singular = sum(
        1
        for m, r in zip(maha_sqs, det_ratios)
        if m > _GATE_SIGMA_THRESHOLD_SQ and r < 1e-6
    )
    rejected_total = sum(1 for m in maha_sqs if m > _GATE_SIGMA_THRESHOLD_SQ)
    if rejected_total:
        print(
            f"  of {rejected_total} rejected trials, {rejected_near_singular} "
            f"({rejected_near_singular / rejected_total:.0%}) have det(S)/trace^2 < 1e-6"
        )

    well_conditioned_maha = [m for m, r in zip(maha_sqs, det_ratios) if r >= 1e-6]
    if well_conditioned_maha:
        frac_wc_over_9 = sum(
            1 for m in well_conditioned_maha if m > _GATE_SIGMA_THRESHOLD_SQ
        ) / len(well_conditioned_maha)
        print(
            f"  excluding near-singular trials ({len(well_conditioned_maha)} left): "
            f"Mahalanobis^2>9.0 = {frac_wc_over_9:.1%} (chi2(2) predicts ~1.1%)"
        )

    maha_true_axis_sqs = [sample.maha_true_axis for sample in samples]
    frac_true_axis_over_9 = (
        sum(1 for m in maha_true_axis_sqs if m > _GATE_SIGMA_THRESHOLD_SQ) / n_f
    )
    print(
        f"  TRUE-AXIS PROBE (ground truth, test-only, never ships): rebuild C's "
        f"kernel/axis from the true bearing/range instead of the reported one, "
        f"keep all declared sigmas unchanged: Mahalanobis^2>9.0 = "
        f"{frac_true_axis_over_9:.1%} (chi2(2) predicts ~1.1%; current production "
        f"reported-axis rate was printed above)"
    )

    emp_cov = Covariance2D(xx=emp_xx, zz=emp_zz, xz=emp_xz)
    emp_maha = [
        emp_cov.mahalanobis_squared(x - mean_dx, z - mean_dz) for x, z in zip(dxs, dzs)
    ]
    frac_emp_over_9 = sum(1 for m in emp_maha if m > _GATE_SIGMA_THRESHOLD_SQ) / n_f
    print(
        f"  sanity check -- Mahalanobis^2 using the EMPIRICAL covariance "
        f"itself (not model S): >9.0 = {frac_emp_over_9:.1%} (should be ~1.1% "
        f"if the test/threshold itself is sound)"
    )

    d_downs = [sample.d_down for sample in samples]
    d_crosses = [sample.d_cross for sample in samples]
    mean_d_down = statistics.fmean(d_downs)
    mean_d_cross = statistics.fmean(d_crosses)
    emp_down_var = sum((d - mean_d_down) ** 2 for d in d_downs) / n_f
    emp_cross_var = sum((d - mean_d_cross) ** 2 for d in d_crosses) / n_f
    emp_downcross_cov = (
        sum((d - mean_d_down) * (c - mean_d_cross) for d, c in zip(d_downs, d_crosses))
        / n_f
    )
    mean_s_down = statistics.fmean(sample.s_down for sample in samples)
    mean_s_cross = statistics.fmean(sample.s_cross for sample in samples)
    mean_s_downcross = statistics.fmean(sample.s_downcross for sample in samples)
    print(
        f"  down-axis: empirical var={emp_down_var:.1f} model S_down={mean_s_down:.1f} "
        f"ratio={emp_down_var / mean_s_down:.3f}"
    )
    print(
        f"  cross-axis: empirical var={emp_cross_var:.1f} model S_cross={mean_s_cross:.1f} "
        f"ratio={emp_cross_var / mean_s_cross:.3f}"
    )
    print(
        f"  down-cross covariance: empirical={emp_downcross_cov:.1f} "
        f"model={mean_s_downcross:.1f}"
    )

    emp_l1, emp_l2, emp_ang = _eig(emp_xx, emp_zz, emp_xz)
    mod_l1, mod_l2, mod_ang = _eig(mean_s_xx, mean_s_zz, mean_s_xz)
    print(
        f"  eigen (world frame) empirical: lam1={emp_l1:.0f} lam2={emp_l2:.0f} "
        f"angle={emp_ang:.1f}deg"
    )
    print(
        f"  eigen (world frame) model S:   lam1={mod_l1:.0f} lam2={mod_l2:.0f} "
        f"angle={mod_ang:.1f}deg"
    )

    bindings = [sample.cap_diag.binding for sample in samples]
    n_psd = sum(1 for b in bindings if b == "psd_cap")
    n_axis = sum(1 for b in bindings if b == "per_axis_cap")
    n_none = sum(1 for b in bindings if b == "none")
    mean_reduction = statistics.fmean(
        (sample.cap_diag.c_down_raw - sample.cap_diag.c_down_capped)
        / sample.cap_diag.c_down_raw
        if sample.cap_diag.c_down_raw > 0.0
        else 0.0
        for sample in samples
    )
    print(
        f"  cap binding: none={n_none / n_f:.0%} psd_cap={n_psd / n_f:.0%} "
        f"per_axis_cap={n_axis / n_f:.0%}  mean c_down reduction when capped="
        f"{mean_reduction:.1%}"
    )
    print()


def measure_true_vs_model_correlation(
    *,
    optic: Optic,
    range_km: float,
    gap_s: float,
    classification_raw: str,
    n: int,
    salt_prefix: str,
    air_alt_m: float = 500.0,
) -> None:
    """Directly measure the TRUE correlation between two looks' own
    `perception.estimation._stable_fraction` draws at identical geometry
    (stationary observer and group), over a resampled ensemble, and
    compare it to the model's `effective_down_correlation` for the same
    geometry -- module docstring finding 1."""
    group_z = -range_km * 1000.0
    down_first: list[float] = []
    down_second: list[float] = []
    try:
        for trial in range(n):
            _fresh_realisation(f"{salt_prefix}-{trial}")
            t0 = trial * 1e-3
            observer = GeoPosition(x=0.0, z=0.0, alt_m=air_alt_m)
            centroid = GeoPosition(x=0.0, z=group_z, alt_m=air_alt_m)
            true_bearing = bearing_deg(observer, centroid)
            true_range = horizontal_range_m(observer, centroid)
            d1 = _stable_fraction(
                field_domain="range",
                true_bearing_deg=true_bearing,
                true_range_m=true_range,
                optic_class=optic.name,
                poll_key=t0,
            )
            d2 = _stable_fraction(
                field_domain="range",
                true_bearing_deg=true_bearing,
                true_range_m=true_range,
                optic_class=optic.name,
                poll_key=t0 + gap_s,
            )
            down_first.append(d1)
            down_second.append(d2)
    finally:
        _restore_field_salt()

    n_f = float(n)
    m1 = statistics.fmean(down_first)
    m2 = statistics.fmean(down_second)
    cov = sum((a - m1) * (b - m2) for a, b in zip(down_first, down_second)) / n_f
    var1 = sum((a - m1) ** 2 for a in down_first) / n_f
    var2 = sum((b - m2) ** 2 for b in down_second) / n_f
    true_corr = cov / math.sqrt(var1 * var2) if var1 > 0 and var2 > 0 else float("nan")

    rho_view, rho_near = stable_range_correlation(0.0, 1.0, optic.name, optic.name)
    rho_eff_model = effective_down_correlation(rho_view, rho_near)

    print(
        f"  TRUE vs MODEL down-range stable-fraction correlation "
        f"({optic.name}, {range_km}km, gap={gap_s}s, n={n}):"
    )
    print(f"    true (empirical) corr = {true_corr:.4f}")
    print(f"    model rho_eff         = {rho_eff_model:.4f}")
    print(f"    var1={var1:.4f} var2={var2:.4f} (should be ~1.0 each)")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--smoke", action="store_true", help="n=100 (a few seconds)")
    args = parser.parse_args(argv)
    n = 100 if args.smoke else args.n

    print("--- Production-faithful (same bias_object_id across both looks) ---\n")
    run_cell(
        optic=UNAIDED_OPTIC,
        label="u_u",
        range_km=2.0,
        gap_s=4.0,
        classification_raw="OP_ARMORED",
        n=n,
        same_bias_object_id=True,
    )
    run_cell(
        optic=UNAIDED_OPTIC,
        label="u_u",
        range_km=2.0,
        gap_s=30.0,
        classification_raw="OP_ARMORED",
        n=n,
        same_bias_object_id=True,
    )
    run_cell(
        optic=UNAIDED_OPTIC,
        label="u_u",
        range_km=4.5,
        gap_s=4.0,
        classification_raw="OP_ARMORED",
        n=n,
        same_bias_object_id=True,
    )
    run_cell(
        optic=BINOCULAR_OPTIC,
        label="b_b",
        range_km=2.0,
        gap_s=4.0,
        classification_raw="OP_ARMORED",
        n=n,
        same_bias_object_id=True,
    )
    print("--- Tool-harness artifact (different bias_object_id, for comparison) ---\n")
    run_cell(
        optic=UNAIDED_OPTIC,
        label="u_u",
        range_km=2.0,
        gap_s=4.0,
        classification_raw="OP_ARMORED",
        n=n,
        same_bias_object_id=False,
    )

    print("--- Direct true-vs-model down-range correlation ---\n")
    for optic, range_km, gap_s, tag in (
        (UNAIDED_OPTIC, 2.0, 4.0, "u_u-2-4"),
        (UNAIDED_OPTIC, 4.5, 4.0, "u_u-4.5-4"),
        (BINOCULAR_OPTIC, 2.0, 4.0, "b_b-2-4"),
        (UNAIDED_OPTIC, 2.0, 30.0, "u_u-2-30"),
    ):
        measure_true_vs_model_correlation(
            optic=optic,
            range_km=range_km,
            gap_s=gap_s,
            classification_raw="OP_ARMORED",
            n=max(n, 2000),
            salt_prefix=f"corr-{tag}",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
