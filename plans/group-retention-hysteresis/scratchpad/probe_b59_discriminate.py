"""BL-B59 probe 3: the cases that DISCRIMINATE between candidate A
(fold-budget discount, zero new constants) and candidate B (a 1.5x
retention factor on the relative term).

Probe 2 showed all candidates fix the BL-B59 incident, so the incident is
not a basis for choosing. These three are:

  D1 genuine departure -- a real, continuously re-observed group member
     drives away. Correct behaviour is eviction. Candidate A must be
     byte-identical to baseline here (its budget is 0.0 for an observed
     contact); candidate B must delay the eviction.

  D2 oscillation       -- can a retention term that keeps one member in,
     while the Stage 3.5 admission gate keeps another out, alternate?
     Driven for 40 ticks with a contact hovering at the boundary.

  D3 no-fold identity  -- across a randomised sweep of scenes with no
     ambiguous fold anywhere, how many pairwise verdicts does each
     candidate change relative to baseline?

Run from `body-layer/`:
  ../../body-layer/.venv/bin/python \
      ../plans/group-retention-hysteresis/scratchpad/probe_b59_discriminate.py
"""

from __future__ import annotations

import itertools
import math
import random
import statistics
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "../world-model/src")
sys.path.insert(0, "tests")

import test_callouts as tc  # noqa: E402
from belief import groups as G  # noqa: E402
from belief.contacts import ContactStore  # noqa: E402

_ORIGINAL = G._cluster_contacts
RETENTION = 1.5


def make_variant(mode: str):  # noqa: ANN201
    def _cluster(contacts, gap_ratio, min_members, prior_rosters):  # noqa: ANN001, ANN202
        if mode == "baseline":
            return _ORIGINAL(contacts, gap_ratio, min_members, prior_rosters)
        if len(contacts) < min_members:
            return []
        ids = [c.id for c in contacts]
        pos = [(c.position.x, c.position.z) for c in contacts]
        profs = [G._profile_for_contact(c) for c in contacts]
        sizes = [G._representative_size_m(p) for p in profs]
        folds = [c.fold_displacement_m for c in contacts]
        n = len(ids)
        roster_of: dict[str, frozenset[str]] = {}
        for roster in prior_rosters:
            for cid in roster:
                roster_of[cid] = roster
        nn = [
            min(G._pairwise_distance(pos, i, j) for j in range(n) if j != i)
            for i in range(n)
        ]
        rel = gap_ratio * statistics.median(nn)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i in range(n):
            for j in range(i + 1, n):
                bs = G._pair_backstop_m(profs[i], profs[j], sizes[i], sizes[j])
                gap = G._pairwise_distance(pos, i, j)
                ri = roster_of.get(ids[i])
                co = ri is not None and ri == roster_of.get(ids[j])
                if co and mode == "A_discount":
                    eff, th = max(0.0, gap - folds[i] - folds[j]), min(rel, bs)
                elif co and mode == "B_factor":
                    eff, th = gap, min(rel * RETENTION, bs)
                else:
                    eff, th = gap + folds[i] + folds[j], min(rel, bs)
                if eff <= th:
                    ra, rb = find(i), find(j)
                    if ra != rb:
                        parent[ra] = rb
        by_root: dict[int, list[str]] = {}
        for i in range(n):
            by_root.setdefault(find(i), []).append(ids[i])
        return [frozenset(m) for m in by_root.values() if len(m) >= min_members]

    return _cluster


class _MP:
    def setattr(self, *a, **k):  # noqa: ANN002, ANN003
        import unittest.mock as m

        m.patch.object(*a, **k).start()


_seq = itertools.count(1)


def obs(cls, lvl, x, z, t, dwp):  # noqa: ANN001, ANN201
    return tc._observation(
        obs_id=f"OBS_{next(_seq)}",
        t_sim=t,
        classification_raw=cls,
        classification_level=lvl,
        ownship_x=x,
        ownship_z=z,
        dwp_x=dwp,
        dwp_z=0.0,
    )


def gline(store):  # noqa: ANN001, ANN201
    return (
        "; ".join(
            f"{g.id}={sorted(int(m.split('_')[1]) for m in g.member_contact_ids)}"
            for g in store.groups
        )
        or "(none)"
    )


# --- D1: a genuine departure -------------------------------------------
def d1(mode: str) -> None:
    global _seq
    _seq = itertools.count(1)
    G._cluster_contacts = make_variant(mode)
    store = ContactStore()

    def ing(o, t):  # noqa: ANN001
        store.ingest(o, now_sim=t)
        store.tick(now_sim=t)

    # Three BTR-70s (STRICT, ~7 m, backstop ~140 m) in a 60 m knot.
    base = [(0.0, 0.0), (50.0, 30.0), (30.0, -40.0)]
    ing(
        [
            obs("BTR-70", 3, x, z, 0.0, 10000.0 * (k + 1))
            for k, (x, z) in enumerate(base)
        ],
        0.0,
    )
    rows = []
    # Contact 3 drives away, 15 m/s, continuously re-observed by all three.
    for t in range(1, 26):
        drift = -15.0 * t
        ing(
            [
                obs("BTR-70", 3, base[0][0], base[0][1], float(t), 10000.0),
                obs("BTR-70", 3, base[1][0], base[1][1], float(t), 20000.0),
                obs("BTR-70", 3, base[2][0] + drift, base[2][1], float(t), 30000.0),
            ],
            float(t),
        )
        members = {g.id: len(g.member_contact_ids) for g in store.groups}
        rows.append((t, abs(drift), gline(store), max(members.values(), default=0)))
    print(f"\n--- D1 genuine departure [{mode}]")
    last = None
    for t, d, g, mx in rows:
        if g != last:
            print(f"   t={t:<3} true offset={d:6.0f} m   {g}")
            last = g
    folds = {c.id: round(c.fold_displacement_m, 1) for c in store.contacts}
    print(f"   final fold budgets: {folds}")
    G._cluster_contacts = _ORIGINAL


# --- D2: oscillation ----------------------------------------------------
def d2(mode: str) -> None:
    global _seq
    _seq = itertools.count(1)
    G._cluster_contacts = make_variant(mode)
    store = ContactStore()

    def ing(o, t):  # noqa: ANN001
        store.ingest(o, now_sim=t)
        store.tick(now_sim=t)

    # Three infantry knot + a 4th infantry that is re-observed only every
    # other tick, hovering near the eager cap boundary -- the shape that
    # produces alternating membership if anything does.
    ing(
        [
            obs("OP_INFANTRY", 2, 0.0, 0.0, 0.0, 10000.0),
            obs("OP_INFANTRY", 2, 60.0, 40.0, 0.0, 20000.0),
            obs("OP_INFANTRY", 2, 30.0, -50.0, 0.0, 30000.0),
            obs("OP_INFANTRY", 2, -470.0, 0.0, 0.0, 40000.0),
        ],
        0.0,
    )
    seen = []
    for t in range(1, 41):
        batch = [
            obs("OP_INFANTRY", 2, 0.0, 0.0, float(t), 10000.0),
            obs("OP_INFANTRY", 2, 60.0, 40.0, float(t), 20000.0),
        ]
        if t % 2 == 0:
            # a pair of ambiguous percepts drifting in -- fold fodder
            batch.append(obs("OP_INFANTRY", 2, -200.0, 10.0, float(t), 50000.0))
            batch.append(obs("OP_INFANTRY", 2, -210.0, -10.0, float(t), 60000.0))
        ing(batch, float(t))
        seen.append(gline(store))
    print(f"\n--- D2 oscillation over 40 ticks [{mode}]")
    transitions = sum(1 for a, b in zip(seen, seen[1:]) if a != b)
    print(f"   distinct membership strings: {len(set(seen))}, transitions: {transitions}")
    for s in dict.fromkeys(seen):
        print(f"     {seen.count(s):3d} ticks  {s}")
    G._cluster_contacts = _ORIGINAL


# --- D3: no-fold identity sweep ----------------------------------------
def d3() -> None:
    """Pairwise-verdict deltas vs baseline across random fold-free scenes,
    computed on the predicate directly (no store needed): every contact has
    fold_displacement_m == 0.0, which is the state of every scene in the
    existing test suite that has never folded."""
    rng = random.Random(20261013)
    print("\n--- D3 no-fold identity sweep (1000 random scenes, folds all 0.0)")
    deltas = {"A_discount": 0, "B_factor": 0}
    total = 0
    for _ in range(1000):
        n = rng.randint(3, 9)
        pos = [(rng.uniform(-800, 800), rng.uniform(-800, 800)) for _ in range(n)]
        sizes = [rng.choice([1.8, 7.0, 12.0]) for _ in range(n)]
        nn = [
            min(
                math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1])
                for j in range(n)
                if j != i
            )
            for i in range(n)
        ]
        rel = G.GROUP_PROXIMITY_GAP_RATIO * statistics.median(nn)
        # a prior roster covering a random subset -- the retention case
        roster = frozenset(
            f"C{k}" for k in rng.sample(range(n), rng.randint(2, n))
        )
        for i, j in itertools.combinations(range(n), 2):
            gap = math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1])
            bs = G.GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS * (
                (sizes[i] + sizes[j]) / 2.0
            )
            co = f"C{i}" in roster and f"C{j}" in roster
            baseline = gap <= min(rel, bs)
            a = (max(0.0, gap - 0.0 - 0.0) <= min(rel, bs)) if co else baseline
            b = (gap <= min(rel * RETENTION, bs)) if co else baseline
            total += 1
            deltas["A_discount"] += a != baseline
            deltas["B_factor"] += b != baseline
    print(f"   {total} pairwise verdicts compared")
    for k, v in deltas.items():
        print(f"     {k:<12} changed {v:6d}  ({100.0 * v / total:.2f}%)")


def main() -> None:
    tc._enrichment_context(_MP())
    for mode in ("baseline", "A_discount", "B_factor"):
        d1(mode)
    for mode in ("baseline", "A_discount", "B_factor"):
        d2(mode)
    d3()


main()
