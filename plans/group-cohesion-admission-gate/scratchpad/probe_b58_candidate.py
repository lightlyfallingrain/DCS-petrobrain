"""BL-B58 probe 3: the candidate admission gate, run beside the current
rule on both reproduced incidents plus three invariant rows.

Candidate rule (reimplements only the *predicate*; every threshold comes
from the real module):

    for each candidate link (i, j):
        if i and j were co-members of the SAME prior group:
            ordinary rule, unchanged            # no eviction gating
        else:
            effective_gap = gap + fold_budget_i + fold_budget_j
            link iff effective_gap <= min(relative, pair_backstop)

`fold_budget` = metres of fused-position displacement attributable to an
ambiguity fold since the contact was last recorded from an unambiguous
percept. 0.0 for every contact in the invariant rows.
"""

from __future__ import annotations

import itertools
import math
import statistics
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "../world-model/src")
sys.path.insert(0, "tests")

import test_callouts as tc  # noqa: E402
from belief import groups as G  # noqa: E402


def _clusters(
    positions: dict[str, tuple[float, float]],
    classes: dict[str, str],
    prior_rosters: list[frozenset[str]],
    fold_budget: dict[str, float],
    *,
    candidate: bool,
) -> list[frozenset[str]]:
    """The real thresholds, only the predicate varied."""
    ids = sorted(positions)
    pos = [positions[i] for i in ids]
    n = len(ids)
    profs = [G.object_model.profile_for(classes[i]) for i in ids]
    sizes = [G._representative_size_m(p) for p in profs]
    nn = [
        min(
            math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1])
            for j in range(n)
            if j != i
        )
        for i in range(n)
    ]
    rel = G.GROUP_PROXIMITY_GAP_RATIO * statistics.median(nn)

    def prior_comembers(a: str, b: str) -> bool:
        return any(a in r and b in r for r in prior_rosters)

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    rows = []
    for i, j in itertools.combinations(range(n), 2):
        gap = math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1])
        th = min(rel, G._pair_backstop_m(profs[i], profs[j], sizes[i], sizes[j]))
        if candidate and not prior_comembers(ids[i], ids[j]):
            eff = gap + fold_budget.get(ids[i], 0.0) + fold_budget.get(ids[j], 0.0)
            why = "admission"
        else:
            eff = gap
            why = "ordinary"
        linked = eff <= th
        rows.append((ids[i], ids[j], gap, eff, th, why, linked))
        if linked:
            ra, rb = find(i), find(j)
            if ra != rb:
                parent[ra] = rb

    by_root: dict[int, list[str]] = {}
    for i in range(n):
        by_root.setdefault(find(i), []).append(ids[i])
    out = [
        frozenset(m) for m in by_root.values() if len(m) >= G.GROUP_REPORTING_MIN_MEMBERS
    ]
    return out, rows, rel  # type: ignore[return-value]


def scene(
    label: str,
    positions,  # noqa: ANN001
    classes,  # noqa: ANN001
    prior_rosters,  # noqa: ANN001
    fold_budget,  # noqa: ANN001
    expect_invariant: bool,
) -> None:
    cur, rows_c, rel = _clusters(
        positions, classes, prior_rosters, fold_budget, candidate=False
    )
    new, rows_n, _ = _clusters(
        positions, classes, prior_rosters, fold_budget, candidate=True
    )
    print(f"\n### {label}   relative_threshold={rel:.1f}")
    print(f"{'pair':<24}{'gap':>8}{'eff':>8}{'thresh':>9}  rule        cur -> new")
    for (a, b, gap, _e, th, _w, lc), (_, _, _, eff, _, why, ln) in zip(
        rows_c, rows_n, strict=True
    ):
        flag = "  <== CHANGED" if lc != ln else ""
        print(
            f"{a+'-'+b:<24}{gap:8.1f}{eff:8.1f}{th:9.1f}  {why:<11} "
            f"{'LINK' if lc else '.':>4} -> {'LINK' if ln else '.':<4}{flag}"
        )
    print(f"  current  : {sorted(sorted(c) for c in cur)}")
    print(f"  candidate: {sorted(sorted(c) for c in new)}")
    if expect_invariant:
        same = sorted(sorted(c) for c in cur) == sorted(sorted(c) for c in new)
        print(f"  INVARIANT ROW: {'IDENTICAL' if same else '*** CHANGED ***'}")


# --- Row A: the 2C incident, positions and budgets read off probe 1 ---------
scene(
    "A  2C incident (t=12, after the fold)",
    {
        "CONTACT_1": (1324.1, 131.3),
        "CONTACT_2": (1290.8, 254.6),
        "CONTACT_3": (1500.0, 0.0),
        "CONTACT_4": (1242.4, 140.1),
        "CONTACT_5": (1290.0, 0.0),
    },
    {
        "CONTACT_1": "OP_INFANTRY",
        "CONTACT_2": "OP_INFANTRY",
        "CONTACT_3": "OP_INFANTRY",
        "CONTACT_4": "BTR-70",
        "CONTACT_5": "OP_TRUCK",
    },
    [frozenset({"CONTACT_1", "CONTACT_2", "CONTACT_3"})],
    {"CONTACT_1": 219.4, "CONTACT_2": 142.4},
    expect_invariant=False,
)

# --- Row B: incident 2, air-defence absorbed member -------------------------
scene(
    "B  incident 2 (t=20, after the fold) -- ZSU-23-4 absorbed",
    {
        "CONTACT_1": (868.0, 10.0),
        "CONTACT_2": (1060.0, 40.0),
        "CONTACT_3": (888.0, -35.0),
        "CONTACT_4": (805.0, 0.0),
    },
    {
        "CONTACT_1": "OP_INFANTRY",
        "CONTACT_2": "OP_INFANTRY",
        "CONTACT_3": "OP_INFANTRY",
        "CONTACT_4": "ZSU-23-4 Shilka",
    },
    [frozenset({"CONTACT_1", "CONTACT_2", "CONTACT_3"})],
    {"CONTACT_1": 132.4, "CONTACT_3": 145.8},
    expect_invariant=False,
)

# --- Row C (invariant): the pinned chained infantry line, no prior group ----
scene(
    "C  INVARIANT  eager cap chains a 1,200 m infantry line (first formation)",
    {
        "I1": (0.0, 0.0),
        "I2": (400.0, 0.0),
        "I3": (800.0, 0.0),
        "I4": (1200.0, 0.0),
    },
    dict.fromkeys(["I1", "I2", "I3", "I4"], "Infantry AK"),
    [],
    {},
    expect_invariant=True,
)

# --- Row D (invariant): three infantry at 30 m, Stage 0a's identical row ----
scene(
    "D  INVARIANT  three infantry at 30 m spacing",
    {"I1": (0.0, 0.0), "I2": (30.0, 0.0), "I3": (60.0, 0.0)},
    dict.fromkeys(["I1", "I2", "I3"], "Infantry AK"),
    [frozenset({"I1", "I2", "I3"})],
    {},
    expect_invariant=True,
)

# --- Row E (invariant): a genuine new joiner, no fold anywhere in the scene -
scene(
    "E  INVARIANT  an un-folded armour contact genuinely joins an armour pair",
    {"A1": (0.0, 0.0), "A2": (100.0, 0.0), "A3": (200.0, 0.0)},
    dict.fromkeys(["A1", "A2", "A3"], "T-72B"),
    [frozenset({"A1", "A2"})],
    {},
    expect_invariant=True,
)

# --- Row F: the same scene as E but A1 carries a fold budget ----------------
scene(
    "F  a fold-displaced member may not admit a new one (A1 budget 130 m)",
    {"A1": (0.0, 0.0), "A2": (100.0, 0.0), "A3": (200.0, 0.0)},
    dict.fromkeys(["A1", "A2", "A3"], "T-72B"),
    [frozenset({"A1", "A2"})],
    {"A1": 130.0},
    expect_invariant=False,
)
