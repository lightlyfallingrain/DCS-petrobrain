"""Probe 1b -- is the prototype's nested re-filter a real risk, or noise?

`probe_collapse_cost.py`'s prototype re-filters the class bucket once per
sub-class (`same = [m for m in bucket if parent_class_of(...) == sub_label]`),
which is O(members_in_bucket x subclasses_in_bucket) and calls `parent_class_of`
again per member per sub-class. The measured table does not separate that from
the rest, because the fixture spreads members across 6 labels.

This probe isolates it: every member in ONE class bucket (the worst case for the
re-filter), at increasing n, against a single-pass variant that groups once.
The question the plan needs answered is not "is it fast" but "does the obvious
implementation have a shape that degrades" -- because the plan has to tell the
Implementer which shape to write.
"""

from __future__ import annotations

import sys
import timeit
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "world-model" / "src"))
sys.path.insert(0, str(_ROOT / "body-layer" / "src"))

from belief import classification  # noqa: E402
from belief.classification import SpecificityLevel, new_classification_belief  # noqa: E402
from belief.contacts import Contact  # noqa: E402
from belief.position_belief import Covariance2D, PositionEstimate  # noqa: E402

_AD_TYPES = ["OP_SRSAM", "OP_MRSAM", "OP_LRSAM", "OP_SPAAG", "OP_ZU23"]


def _contact(index: int, raw: str) -> Contact:
    half = 0.5 * 40.0 * 40.0
    cov = Covariance2D(xx=half, zz=half, xz=0.0)
    return Contact(
        id=f"C{index}",
        position=PositionEstimate(
            x=float(index),
            z=float(index),
            covariance=cov,
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=cov,
        ),
        last_alt_m=0.0,
        last_class_raw=raw,
        classification=new_classification_belief(
            value=raw, level=SpecificityLevel.CLASS, established_sim=0.0
        ),
    )


def naive_depth3(members: list[Contact]) -> dict[str, object]:
    """The re-filtering shape -- `parent_class_of` called once in the outer
    pass and again once per member per sub-class."""
    by_class: dict[str, list[Contact]] = {}
    for m in members:
        op = classification.parent_class_of(m.last_class_raw)
        label = "air defense" if op in classification.AIR_DEFENSE_OP_CLASSES else "other"
        by_class.setdefault(label, []).append(m)
    out: dict[str, object] = {}
    for label, bucket in by_class.items():
        subs = Counter(
            classification.parent_class_of(m.last_class_raw) or "unknown" for m in bucket
        )
        node: dict[str, object] = {}
        for sub in subs:
            same = [
                m
                for m in bucket
                if (classification.parent_class_of(m.last_class_raw) or "unknown") == sub
            ]
            node[sub] = [m.id for m in same]
        out[label] = node
    return out


def single_pass_depth3(members: list[Contact]) -> dict[str, object]:
    """One pass. `parent_class_of` is called exactly once per member, and the
    (class, sub-class) bucket is built on the way down."""
    buckets: dict[tuple[str, str], list[Contact]] = defaultdict(list)
    for m in members:
        op = classification.parent_class_of(m.last_class_raw) or "unknown"
        label = "air defense" if op in classification.AIR_DEFENSE_OP_CLASSES else "other"
        buckets[(label, op)].append(m)
    out: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for (label, sub), bucket in buckets.items():
        out[label][sub] = [m.id for m in bucket]
    return dict(out)


def main() -> None:
    print("probe 1b -- nested re-filter vs single pass, ALL members in one class")
    print()
    print("    n   naive us  single us   ratio   parent_class_of calls (naive/single)")
    print("    -   --------  ---------   -----   ----------------------------------")
    for n in (6, 20, 52, 150, 400):
        members = [_contact(i, _AD_TYPES[i % len(_AD_TYPES)]) for i in range(n)]
        assert naive_depth3(members) == single_pass_depth3(members), (
            "the two shapes must agree before their costs are comparable"
        )
        reps = 2000 if n <= 52 else 200
        a = timeit.timeit(lambda: naive_depth3(members), number=reps) / reps * 1e6
        b = timeit.timeit(lambda: single_pass_depth3(members), number=reps) / reps * 1e6
        # naive: n (outer) + n (Counter) + n * subclasses (re-filter)
        subs = len({_AD_TYPES[i % len(_AD_TYPES)] for i in range(n)})
        print(
            f"  {n:>3}   {a:>8.2f}  {b:>9.2f}   {a / b:>5.2f}x"
            f"   {2 * n + n * subs} / {n}"
        )
    print()
    print(
        "Realistic group sizes are single digits (GROUP_REPORTING_MIN_MEMBERS=2; "
        "the 2026-09-28 sortie tracked 52 contacts across the whole scene, not "
        "one group), so both shapes are far inside budget. The single-pass form "
        "is still what the plan should specify: same output, fewer lattice calls, "
        "and it cannot degrade if a future cohesion change makes one group large."
    )


if __name__ == "__main__":
    main()
