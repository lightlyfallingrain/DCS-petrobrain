"""BL-B59 probe 7: the membership trace for the bounded discount at
f = 0.25 / 0.5 / 1.0 and unbounded, to separate "the retention persists"
from "12 transitions of downstream contact-id churn".

Run from `body-layer/`:
  ../../body-layer/.venv/bin/python \
      ../plans/group-retention-hysteresis/scratchpad/probe_b59_trace.py
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
from belief.contacts import ContactStore  # noqa: E402

_ORIGINAL = G._cluster_contacts
TRACE: list[str] = []


def make_variant(frac):  # noqa: ANN001, ANN201
    def _cluster(contacts, gap_ratio, min_members, prior_rosters):  # noqa: ANN001, ANN202
        if frac is None:
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
        for r in prior_rosters:
            for cid in r:
                roster_of[cid] = r
        nn = [
            min(G._pairwise_distance(pos, i, j) for j in range(n) if j != i)
            for i in range(n)
        ]
        rel = gap_ratio * statistics.median(nn)
        parent = list(range(n))

        def find(x):  # noqa: ANN001, ANN202
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i in range(n):
            for j in range(i + 1, n):
                bs = G._pair_backstop_m(profs[i], profs[j], sizes[i], sizes[j])
                gap = G._pairwise_distance(pos, i, j)
                th = min(rel, bs)
                ri = roster_of.get(ids[i])
                co = ri is not None and ri == roster_of.get(ids[j])
                if co:
                    cap = math.inf if frac == "inf" else frac * th
                    disc = min(folds[i] + folds[j], cap)
                    eff = max(0.0, gap - disc)
                    if {ids[i], ids[j]} == {"CONTACT_1", "CONTACT_2"}:
                        TRACE.append(
                            f"      C1-C2 gap={gap:6.1f} th={th:6.1f} "
                            f"folds={folds[i]:.1f}+{folds[j]:.1f} "
                            f"cap={cap if cap == math.inf else round(cap, 1)} "
                            f"disc={disc:6.1f} eff={eff:6.1f} "
                            f"{'LINK' if eff <= th else 'EVICT'}"
                        )
                else:
                    eff = gap + folds[i] + folds[j]
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


def g1(store):  # noqa: ANN001, ANN201
    for g in store.groups:
        ids = {int(m.split("_")[1]) for m in g.member_contact_ids}
        if 1 in ids:
            return tuple(sorted(ids))
    return ()


def run(frac):  # noqa: ANN001, ANN201
    global _seq
    _seq = itertools.count(1)
    TRACE.clear()
    G._cluster_contacts = make_variant(frac)
    store = ContactStore()

    def ing(o, t):  # noqa: ANN001
        store.ingest(o, now_sim=t)
        store.tick(now_sim=t)

    ing(
        [
            obs("OP_INFANTRY", 2, 0.0, 0.0, 0.0, 10000.0),
            obs("OP_INFANTRY", 2, 60.0, 40.0, 0.0, 20000.0),
            obs("OP_INFANTRY", 2, 30.0, -50.0, 0.0, 30000.0),
            obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, 0.0, 40000.0),
        ],
        0.0,
    )
    for t in range(1, 21):
        ing([obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, float(t), 40000.0)], float(t))
    ing(
        [
            obs("OP_INFANTRY", 2, -260.0, 20.0, 20.0, 50000.0),
            obs("OP_INFANTRY", 2, -250.0, -20.0, 20.0, 60000.0),
        ],
        20.0,
    )
    print(f"\n--- f={frac}")
    print(f"  t=20 fold tick: CONTACT_1's group = {g1(store)}")
    for line in TRACE[-1:]:
        print(line)
    states = []
    for k in range(1, 61):
        t = 20.0 + k
        batch = [obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, t, 40000.0)]
        if k % 5 == 0:
            batch += [
                obs("OP_INFANTRY", 2, -250.0, 10.0, t, 50000.0),
                obs("OP_INFANTRY", 2, -240.0, -15.0, t, 60000.0),
            ]
        ing(batch, t)
        states.append((t, g1(store)))
    changes = [
        (t, s) for (t, s), (_, p) in zip(states, [(0, None)] + states) if s != p
    ]
    print("  CONTACT_1's group over the next 60 ticks (changes only):")
    for t, s in changes:
        print(f"    t={t:<5.0f} {s}")
    print(f"  ticks with CONTACT_2 present: {sum(1 for _, s in states if 2 in s)}/60")
    G._cluster_contacts = _ORIGINAL


def main() -> None:
    tc._enrichment_context(_MP())
    for frac in (None, 0.25, 0.5, 1.0, "inf"):
        run(frac)


main()
