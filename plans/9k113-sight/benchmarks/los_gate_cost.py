"""Microbenchmark for `plans/9k113-sight/performance-cone-gate.md`'s headline finding: what
`visibility.check_visibility`'s gate 4 (terrain LOS) actually costs today, post-`BL-11` Stage 4's
fail-closed rewrite -- replacing `plans/player-bubble/performance.md`'s stale 540 us/candidate
figure (measured against a sqlite `sample_grid` raycast that is no longer reachable from this gate).

Run from `body-layer/`, pinned venv (ruff==0.16.6, mypy==2.3.1, pytest==9.1.1, numpy==2.4.6,
pyproj==3.8.0):

    PYTHONPATH=src:../world-model/src .venv/bin/python3 ../plans/9k113-sight/benchmarks/los_gate_cost.py
"""

import sqlite3
import time

from perception.association import WorldObjectCandidate
from perception.detection_trace import DetectionTraceCollector
from perception.optics import UNAIDED_OPTIC
from perception.visibility import OwnshipState, check_visibility


def make_candidate(live_los_clear: bool | None) -> WorldObjectCandidate:
    return WorldObjectCandidate(
        object_id=1,
        object_type="T-55",
        x=2000.0,
        z=0.0,
        alt_m=500.0,
        is_ownship=False,
        heading_true_deg=0.0,
        live_los_clear=live_los_clear,
    )


def main() -> None:
    # `conn`/`theatre` are dead parameters as of BL-11 Stage 4 (visibility.py's own
    # docstring says so) -- passed as a real connection anyway so a future gate-order
    # change that revives one of them fails loudly here rather than silently.
    conn = sqlite3.connect(":memory:")
    theatre = "test"
    ownship = OwnshipState(
        t_sim=100.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0, pitch_deg=0.0, bank_deg=0.0
    )

    n = 200_000
    for label, live_los_clear in [("ADMITTED (live_los_clear=True)", True), ("TERRAIN_LOS reject (False)", False), ("TERRAIN_LOS reject, fail-closed (None)", None)]:
        candidate = make_candidate(live_los_clear)
        t0 = time.perf_counter()
        for _ in range(n):
            check_visibility(ownship, candidate, conn, theatre, optic=UNAIDED_OPTIC)
        t1 = time.perf_counter()
        print(f"{label}: {(t1 - t0) / n * 1e6:.3f} us/call (n={n})")

    # Can-this-fail probe: confirm the trace sink actually sees the outcomes this
    # benchmark's labels claim, so a silent gate-order regression doesn't make this
    # benchmark time the wrong code path without anyone noticing.
    trace = DetectionTraceCollector()
    for live_los_clear in (True, False, None):
        check_visibility(
            ownship, make_candidate(live_los_clear), conn, theatre, optic=UNAIDED_OPTIC, trace=trace
        )
    outcomes = [r.outcome.value for r in trace.records]
    assert outcomes == ["admitted", "terrain_los", "terrain_los"], outcomes
    print("PROBE: outcome assertions passed ->", outcomes)


if __name__ == "__main__":
    main()
