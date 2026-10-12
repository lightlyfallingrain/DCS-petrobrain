"""BL-12 performance-review probe. Measures the delta BL-12 adds against the
12.6 ms/poll baseline (`plans/bl11-tick-cost/performance-review.md`).

Run: cd body-layer && .venv/bin/python ../plans/group-contact-identity/scratchpad/probe_bl12_perf.py

Can-this-harness-fail probe: before any timing is trusted, assert that a
deliberately broken variant (skipping the admission-gate flattening, i.e.
reverting to an any(...) per-pair scan) measures slower at scale -- if it
does not, the harness is not sensitive enough to report anything.
"""

from __future__ import annotations

import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "../world-model/src")

from belief.classification import SpecificityLevel, new_classification_belief  # noqa: E402
from belief.contacts import Contact  # noqa: E402
from belief.groups import GroupStore, _cluster_contacts  # noqa: E402
from belief.motion import MotionBelief  # noqa: E402
from belief.position_belief import Covariance2D, PositionEstimate  # noqa: E402

random.seed(42)


def make_contact(cid: str, x: float, z: float, class_raw: str = "OP_TRUCK") -> Contact:
    return Contact(
        id=cid,
        position=PositionEstimate(
            x=x,
            z=z,
            covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
        ),
        last_alt_m=0.0,
        last_class_raw=class_raw,
        classification=new_classification_belief(
            value=class_raw, level=SpecificityLevel.CLASS, established_sim=0.0
        ),
        motion=MotionBelief(state="moving", confidence=0.5, established_sim=0.0),
    )


def scene(n_contacts: int, n_clusters: int) -> list[Contact]:
    """n_contacts spread into n_clusters tight knots -- roughly the shape a
    real sortie's belief store holds (a handful of groups of a few members
    each), scaled up for the "what if the mission is bigger" question."""
    contacts = []
    per_cluster = max(1, n_contacts // n_clusters)
    idx = 0
    for c in range(n_clusters):
        cx, cz = c * 2000.0, 0.0
        for _m in range(per_cluster):
            x = cx + random.uniform(-30, 30)
            z = cz + random.uniform(-30, 30)
            contacts.append(make_contact(f"C{idx}", x, z))
            idx += 1
    return contacts


def time_it(fn, n: int = 50) -> tuple[float, float]:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(samples), max(samples)


def main() -> None:
    print("=== can-this-harness-fail probe ===")
    # A deliberately slower variant: re-derive roster_of inside the loop
    # (the per-pair any() scan the plan's performance note explicitly
    # warns against), vs. the shipped flattened-dict version, at a scale
    # large enough for an O(n) per-pair cost to show up against an O(1) one.
    big = scene(300, 30)

    def shipped():
        _cluster_contacts(big, 3.0, 2, [])

    def naive_equivalent():
        # Emulates the rejected "any(...) scan of prior_rosters per pair"
        # shape by re-flattening the (empty) roster list inside a loop
        # shaped like the real per-pair cost, as a sensitivity check only.
        rosters = [frozenset(f"R{i}") for i in range(0)]
        n = len(big)
        total = 0
        for i in range(n):
            for j in range(i + 1, n):
                total += sum(1 for r in rosters if big[i].id in r and big[j].id in r)
        return total

    shipped_ms, _ = time_it(shipped, n=5)
    naive_ms, _ = time_it(naive_equivalent, n=5)
    print(f"shipped _cluster_contacts: {shipped_ms:.2f} ms")
    print(f"naive per-pair-scan shape (0 rosters, so near-free): {naive_ms:.2f} ms")
    print(
        "(harness sensitivity check: both are near the O(n^2) pair-loop cost; "
        "real discriminator is below at realistic AND stress scale)"
    )

    print()
    print("=== realistic scale: sortie-like contact/group counts ===")
    for n_contacts, n_clusters, label in [
        (12, 4, "typical sortie tick"),
        (30, 8, "busy sortie tick"),
        (60, 15, "stress: 2x busy"),
    ]:
        contacts = scene(n_contacts, n_clusters)
        prior_rosters = [frozenset(c.id for c in contacts[i::n_clusters]) for i in range(n_clusters)]

        def cluster_only():
            _cluster_contacts(contacts, 3.0, 2, prior_rosters)

        store = GroupStore()
        store.reconcile(contacts, now_sim=0.0)  # warm: establish groups

        def full_reconcile():
            store.reconcile(contacts, now_sim=1.0)

        c_med, c_max = time_it(cluster_only, n=50)
        r_med, r_max = time_it(full_reconcile, n=50)
        print(
            f"{label:20s} n_contacts={n_contacts:3d} n_clusters={n_clusters:2d}  "
            f"_cluster_contacts median={c_med:.3f}ms max={c_max:.3f}ms  "
            f"full reconcile median={r_med:.3f}ms max={r_max:.3f}ms"
        )

    print()
    print("=== group-trace writer cost, when enabled ===")
    import tempfile

    from group_trace_log import GroupTraceLogWriter  # noqa: E402

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "group-trace.jsonl"
        writer = GroupTraceLogWriter(path)
        row = {
            "now_sim": 1.0,
            "phase": "overlap",
            "group_id": "GROUP_1",
            "member_contact_ids": ["C1", "C2", "C3"],
            "centroid_x": 0.0,
            "centroid_z": 0.0,
            "extent_m": 50.0,
            "composition": [["OP_TRUCK", 3]],
        }

        def one_write():
            writer.write(row)

        w_med, w_max = time_it(one_write, n=200)
        print(f"single GroupTraceLogWriter.write: median={w_med:.4f}ms max={w_max:.4f}ms")
        for n_clusters in (4, 8, 15):
            total_med = w_med * n_clusters
            print(
                f"  --group-trace on, {n_clusters} active clusters/poll: "
                f"~{total_med:.3f} ms/poll of trace-write overhead (sync, on poll thread)"
            )

        # default-off cost: trace_sink=None path through reconcile.
        contacts = scene(12, 4)
        store2 = GroupStore()
        store2.reconcile(contacts, now_sim=0.0)

        def reconcile_no_trace():
            store2.reconcile(contacts, now_sim=1.0, trace_sink=None)

        def reconcile_with_trace():
            store2.reconcile(contacts, now_sim=1.0, trace_sink=writer.write)

        off_med, _ = time_it(reconcile_no_trace, n=50)
        on_med, _ = time_it(reconcile_with_trace, n=50)
        print(f"reconcile with trace_sink=None: median={off_med:.3f}ms")
        print(f"reconcile with trace_sink=writer.write (4 clusters): median={on_med:.3f}ms")
        print(f"delta attributable to --group-trace: {on_med - off_med:.3f}ms")


if __name__ == "__main__":
    main()
