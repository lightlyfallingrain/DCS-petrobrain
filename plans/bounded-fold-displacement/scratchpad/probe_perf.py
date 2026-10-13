"""Performance-review probe for `BL-B58` option 2 / `BL-B59` (bounded fold
displacement), merged at `078232b`. Measures the delta this feature adds
against BL-11's 12.6 ms/poll baseline and BL-12's own full-reconcile numbers.

Run: cd body-layer && <venv>/bin/python ../plans/bounded-fold-displacement/scratchpad/probe_perf.py

Can-this-harness-fail probe: before any timing is trusted, assert that a
deliberately broken variant (clamp_fold_displacement forced to always
rebuild a PositionEstimate, i.e. skip its early-return identity branches)
measures slower than the shipped version -- if it does not, the harness is
not sensitive enough to report anything.
"""

from __future__ import annotations

import statistics
import sys
import time

sys.path.insert(0, "src")
sys.path.insert(0, "../world-model/src")

from belief.classification import SpecificityLevel, new_classification_belief  # noqa: E402
from belief.contacts import Contact, Observation  # noqa: E402
from belief.percept import percept_of  # noqa: E402
from belief.position_belief import (  # noqa: E402
    Covariance2D,
    PositionEstimate,
    PositionUncertainty,
    clamp_fold_displacement,
)
from belief.motion import MotionBelief  # noqa: E402
from perception.source import DerivedWorldPosition, OwnshipState  # noqa: E402

N = 20000


def time_it(fn, n: int = N) -> tuple[float, float]:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1e6)  # microseconds
    return statistics.median(samples), max(samples)


def make_estimate(x: float, z: float, as_of_sim: float, fused_at_sim: float) -> PositionEstimate:
    cov = Covariance2D(xx=100.0, zz=100.0, xz=0.0)
    return PositionEstimate(
        x=x, z=z, covariance=cov, as_of_sim=as_of_sim, fused_at_sim=fused_at_sim, fused_covariance=cov
    )


def make_contact(cid: str, x: float, z: float) -> Contact:
    return Contact(
        id=cid,
        position=make_estimate(x, z, 0.0, 0.0),
        last_alt_m=0.0,
        last_class_raw="OP_TRUCK",
        classification=new_classification_belief(
            value="OP_TRUCK", level=SpecificityLevel.CLASS, established_sim=0.0
        ),
        motion=MotionBelief(state="moving", confidence=0.5, established_sim=0.0),
    )


def main() -> None:
    print("=== can-this-harness-fail probe ===")
    prior = make_estimate(0.0, 0.0, 0.0, 0.0)
    fused_within_bound = make_estimate(10.0, 0.0, 20.0, 20.0)
    fused_past_bound = make_estimate(500.0, 0.0, 20.0, 20.0)

    def shipped_within_bound():
        clamp_fold_displacement(fused_within_bound, prior, 150.0)

    def shipped_past_bound():
        clamp_fold_displacement(fused_past_bound, prior, 150.0)

    def broken_always_rebuild():
        # Emulates a version that always reconstructs a PositionEstimate
        # instead of taking either identity branch -- deliberately slower,
        # to prove the harness can detect a real cost difference.
        for _ in range(50):
            PositionEstimate(
                x=fused_within_bound.x,
                z=fused_within_bound.z,
                covariance=fused_within_bound.covariance,
                as_of_sim=fused_within_bound.as_of_sim,
                fused_at_sim=fused_within_bound.fused_at_sim,
                fused_covariance=fused_within_bound.fused_covariance,
            )

    s_med, _ = time_it(shipped_within_bound, n=5000)
    b_med, _ = time_it(broken_always_rebuild, n=5000)
    print(f"shipped clamp_fold_displacement (within bound, no-op path): {s_med:.4f} us")
    print(f"deliberately-slower 50x-rebuild shape: {b_med:.4f} us")
    assert b_med > s_med * 10, "harness is not sensitive enough -- stop, do not trust timings below"
    print("(harness sensitivity confirmed)")
    print()

    print("=== clamp_fold_displacement: per-call cost ===")
    none_med, _ = time_it(lambda: clamp_fold_displacement(fused_within_bound, prior, None))
    within_med, _ = time_it(shipped_within_bound)
    past_med, _ = time_it(shipped_past_bound)
    print(f"identity (max_displacement_m=None): median={none_med:.4f} us")
    print(f"within bound (no-op, hypot only): median={within_med:.4f} us")
    print(f"past bound (hypot + rebuild): median={past_med:.4f} us")
    print()

    print("=== Contact.record: unambiguous vs ambiguous_fold=True ===")
    contact_a = make_contact("C1", 0.0, 0.0)
    contact_b = make_contact("C2", 0.0, 0.0)

    def make_percept(t_sim: float, obs_id: str):
        observation = Observation(
            id=obs_id,
            contact_id=None,
            t_sim=t_sim,
            t_wall=t_sim,
            source="naked_eye_visual_filtered",
            classification_raw="OP_TRUCK",
            bearing_deg=0.0,
            range_m=500.0,
            ownship_at_observation=OwnshipState(
                t_sim=t_sim, x=-500.0, z=0.0, alt_m=500.0, heading_true_deg=0.0
            ),
            derived_world_position=DerivedWorldPosition(
                x=99999.0, z=99999.0, confidence=0.9, method="test_fixture"
            ),
            provenance="test_fixture",
            position_uncertainty=PositionUncertainty(sigma_cross_m=20.0, sigma_down_m=30.0),
        )
        return percept_of(observation)

    percept_a = make_percept(5.0, "OBS_A")
    percept_b = make_percept(5.0, "OBS_B")

    def record_unambiguous():
        contact_a.record(percept_a)

    def record_ambiguous_fold():
        contact_b.record(percept_b, ambiguous_fold=True)

    u_med, _ = time_it(record_unambiguous, n=5000)
    f_med, _ = time_it(record_ambiguous_fold, n=5000)
    print(f"record(percept)                         median={u_med:.4f} us")
    print(f"record(percept, ambiguous_fold=True)     median={f_med:.4f} us")
    print(f"delta attributable to ambiguous_fold:     {f_med - u_med:.4f} us")


if __name__ == "__main__":
    main()
