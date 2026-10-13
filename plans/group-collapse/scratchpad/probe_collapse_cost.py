"""Probe 1 -- what does a `collapse(group, depth)` actually cost per call?

Open question 1 from `docs/acceptance/2026-10-13-group-model-and-attention-tiers.md`
Part 4: *"`collapse`'s actual per-call cost at realistic member counts. Cheap in
principle -- but 'cheap in principle' is what the 552 m no-op bound and the 300 m
`radius_m()` floor both looked like, and both were wrong when measured."*

Measures a prototype collapse that reads ONLY `Contact.last_class_raw` /
`.classification` / `.cardinality` through `belief.classification`'s lattice --
no `describe_contact`, no enrichment, no world-model. Then prices the same walk
done through `tools.describe_contact` for contrast, because that is the
alternative shape a naive implementation would reach for and it is the one
`BL-B49` measured at 63.25 ms per contact.

Run:
    /Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python3 \
        plans/group-collapse/scratchpad/probe_collapse_cost.py
with cwd at the repo root of this worktree.
"""

from __future__ import annotations

import math
import statistics
import sys
import timeit
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
# body-layer imports world-model's `query`/`coordinates` in-process -- the one
# sanctioned cross-subproject import (root CLAUDE.md, "Module independence").
# `pyproject.toml`'s `pythonpath = ["src", "../world-model/src"]` is pytest-only,
# so a bare script has to reproduce it.
sys.path.insert(0, str(_ROOT / "world-model" / "src"))
sys.path.insert(0, str(_ROOT / "body-layer" / "src"))

from belief import classification  # noqa: E402
from belief.classification import SpecificityLevel, new_classification_belief  # noqa: E402
from belief.contacts import Contact  # noqa: E402
from belief.position_belief import Covariance2D, PositionEstimate  # noqa: E402
from perception import object_model  # noqa: E402

# A realistic spread of believed classification strings: some held at CLASS
# level (the `OP_*` string itself, which is what a contact holds at range --
# most of the time), some at TYPE level (a real DCS type name from
# `object_model`'s own keyword table), some at PRESENCE (no claim).
_CLASS_LEVEL = ["OP_ARMORED", "OP_TRUCK", "OP_INFANTRY", "OP_SPAAG", "OP_LRSAM"]
_TYPE_LEVEL = ["T-72B", "Ural-375", "ZSU-23-4 Shilka", "BMP-2"]
_PRESENCE = [object_model.DEFAULT_OP_CLASS]


def _contact(index: int) -> Contact:
    """Mirrors `body-layer/tests/test_groups.py`'s own `_contact` helper --
    same `PositionEstimate`/`Covariance2D` construction, so the probe is not
    measuring a fixture shape the real code never sees."""
    raw = (_CLASS_LEVEL + _TYPE_LEVEL + _PRESENCE)[
        index % (len(_CLASS_LEVEL) + len(_TYPE_LEVEL) + len(_PRESENCE))
    ]
    level = (
        SpecificityLevel.PRESENCE
        if raw == object_model.DEFAULT_OP_CLASS
        else (
            SpecificityLevel.CLASS if raw.startswith("OP_") else SpecificityLevel.TYPE
        )
    )
    half_variance = 0.5 * 40.0 * 40.0
    cov = Covariance2D(xx=half_variance, zz=half_variance, xz=0.0)
    return Contact(
        id=f"C{index}",
        position=PositionEstimate(
            x=1000.0 + 17.0 * index,
            z=2000.0 + 13.0 * index,
            covariance=cov,
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=cov,
        ),
        last_alt_m=0.0,
        last_class_raw=raw,
        classification=new_classification_belief(
            value=raw, level=level, established_sim=0.0
        ),
    )


# --------------------------------------------------------------------------
# The prototype. Depth is a level on the user's own ladder, Part 2:
#   0 group -> 1 class -> 2 sub-class -> 3 type -> 4 contact
# Level 1 ("armor" / "air defense") has no vocabulary in code today; the only
# such grouping that exists is `classification.AIR_DEFENSE_OP_CLASSES`, so the
# prototype folds every non-air-defence `OP_*` to itself at level 1. That is
# the gap the plan names, not a flaw in the measurement -- the walk is the same
# shape either way.
# --------------------------------------------------------------------------

_AD = classification.AIR_DEFENSE_OP_CLASSES


def _class_label(op_class: str | None) -> str:
    if op_class is None:
        return "unknown"
    if op_class in _AD:
        return "air defense"
    return op_class


def collapse(members: list[Contact], depth: int) -> dict[str, object]:
    """Prototype. Deliberately plain: one pass over members, a lattice walk
    per member, a `Counter` per level. No caching, no memoisation -- the
    pessimistic shape, so the number is an upper bound."""
    count_lo = 0
    count_hi = 0.0
    for member in members:
        count_lo += member.cardinality.lo
        count_hi += member.cardinality.hi
    node: dict[str, object] = {
        "contacts": len(members),
        "units_lo": count_lo,
        "units_hi": count_hi,
    }
    if depth <= 0:
        return node
    by_class: dict[str, list[Contact]] = {}
    for member in members:
        op_class = classification.parent_class_of(member.last_class_raw)
        by_class.setdefault(_class_label(op_class), []).append(member)
    if depth == 1:
        node["branches"] = {
            label: {"contacts": len(bucket)} for label, bucket in by_class.items()
        }
        return node
    branches: dict[str, object] = {}
    for label, bucket in by_class.items():
        sub: Counter[str] = Counter(
            classification.parent_class_of(m.last_class_raw) or "unknown"
            for m in bucket
        )
        if depth == 2:
            branches[label] = dict(sub)
            continue
        types: dict[str, object] = {}
        for sub_label in sub:
            same = [
                m
                for m in bucket
                if (classification.parent_class_of(m.last_class_raw) or "unknown")
                == sub_label
            ]
            if depth == 3:
                types[sub_label] = dict(
                    Counter(
                        m.classification.value or "unknown"
                        for m in same
                        if m.classification.level >= SpecificityLevel.TYPE
                    )
                )
            else:
                types[sub_label] = [
                    {
                        "contact_id": m.id,
                        "x": m.position.x,
                        "z": m.position.z,
                        "radius_m": m.position.radius_m(),
                        "class_raw": m.last_class_raw,
                    }
                    for m in same
                ]
        branches[label] = types
    node["branches"] = branches
    return node


def main() -> None:
    print("probe 1 -- collapse() per-call cost, lattice-only, no enrichment")
    print(f"python: {sys.version.split()[0]}")
    print()
    print("  n  depth    us/call      per-member us")
    print("  -  -----    -------      -------------")
    worst: dict[int, float] = {}
    for n in (2, 4, 6, 10, 20, 52):
        members = [_contact(i) for i in range(n)]
        for depth in (0, 1, 2, 3, 4):
            reps = 2000 if n <= 20 else 500
            secs = timeit.timeit(lambda: collapse(members, depth), number=reps) / reps
            us = secs * 1e6
            worst[depth] = max(worst.get(depth, 0.0), us)
            print(f"  {n:>2}  {depth:>5}   {us:>8.2f}      {us / n:>8.3f}")
        print()

    print("deepest collapse, worst measured n:", f"{worst[4]:.2f} us")
    print()

    # The contrast case: the same roster priced the way the existing push path
    # already prices it, through `tools.describe_contact`. BL-B49 measured
    # 63.25 ms per contact for the enrichment term alone, against the real
    # 738 MB syria-full.sqlite. We cannot reach that store here, so this is the
    # *floor* -- describe_contact with enrichment=None, i.e. the cheapest that
    # call can ever be.
    from belief.contacts import ContactStore  # noqa: PLC0415
    from belief.tools import describe_contact  # noqa: PLC0415

    store = ContactStore()
    members = [_contact(i) for i in range(10)]
    for member in members:
        store._contacts[member.id] = member  # noqa: SLF001

    def _facts_walk() -> None:
        for member in members:
            describe_contact(store, member.id, 100.0, enrichment=None)

    reps = 200
    secs = timeit.timeit(_facts_walk, number=reps) / reps
    print(
        "describe_contact walk over the same 10 members, enrichment=None "
        f"(the FLOOR, not the sortie cost): {secs * 1e6:.1f} us "
        f"= {secs * 1e6 / 10:.1f} us/member"
    )
    members10 = members
    secs_collapse = (
        timeit.timeit(lambda: collapse(members10, 4), number=2000) / 2000
    )
    print(
        f"collapse(depth=4) over the same 10 members: {secs_collapse * 1e6:.1f} us"
    )
    print(f"ratio describe_contact / collapse: {secs / secs_collapse:.1f}x")
    print()
    print(
        "BL-B49's measured enrichment term is 63.25 ms per contact cold / "
        "6.77 ms per contact for the never-cached terrain_divide_qualifier. "
        "Compare that to the collapse figure above."
    )
    print()
    print("sanity: deepest collapse over 6 members")
    import json  # noqa: PLC0415

    print(json.dumps(collapse([_contact(i) for i in range(6)], 4), indent=2)[:1200])

    assert not math.isnan(worst[4])
    assert statistics.fmean([worst[d] for d in (0, 1, 2, 3, 4)]) > 0.0


if __name__ == "__main__":
    main()
