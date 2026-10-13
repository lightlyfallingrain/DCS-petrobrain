"""BL-B59 probe 2: run the real pipeline with each candidate retention
mechanism monkeypatched into `groups._cluster_contacts`, and compare
membership outcomes against the unpatched baseline.

`GroupStore.reconcile` calls `_cluster_contacts` by module-global name, so
rebinding `groups._cluster_contacts` swaps the mechanism for the real
pipeline -- not an isolated re-implementation of the predicate.

Candidates:
  baseline   -- shipped Stage 3.5 code, unchanged.
  A_discount -- prior co-members: effective_gap = max(0, gap - folds[i] -
                folds[j]). Dual-sign use of the SAME provenance field
                Stage 3.5 added. Zero new constants.
  B_factor   -- prior co-members: relative term multiplied by RETENTION
                (the `watch-reporting` §4e shape). One new constant.
  B_both     -- as B_factor but the backstop is loosened too (shown to
                establish that it must NOT be).

Run from `body-layer/`:
  ../../body-layer/.venv/bin/python \
      ../plans/group-retention-hysteresis/scratchpad/probe_b59_candidates.py
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
from belief.contacts import Contact, ContactStore  # noqa: E402

_ORIGINAL = G._cluster_contacts
RETENTION = 1.5  # watch-reporting §4e's factor, borrowed for the B variants


def make_variant(mode: str):  # noqa: ANN201, C901
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
        nn = []
        for i in range(n):
            nn.append(
                min(G._pairwise_distance(pos, i, j) for j in range(n) if j != i)
            )
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
                if co:
                    if mode == "A_discount":
                        eff = max(0.0, gap - folds[i] - folds[j])
                        th = min(rel, bs)
                    elif mode == "B_factor":
                        eff = gap
                        th = min(rel * RETENTION, bs)
                    else:  # B_both
                        eff = gap
                        th = min(rel * RETENTION, bs * RETENTION)
                else:
                    eff = gap + folds[i] + folds[j]
                    th = min(rel, bs)
                if eff <= th:
                    ra, rb = find(i), find(j)
                    if ra != rb:
                        parent[ra] = rb

        by_root: dict[int, list[str]] = {}
        for i in range(n):
            by_root.setdefault(find(i), []).append(ids[i])
        return [
            frozenset(m) for m in by_root.values() if len(m) >= min_members
        ]

    return _cluster


class _MP:
    def setattr(self, *a, **k):  # noqa: ANN002, ANN003
        import unittest.mock as m

        m.patch.object(*a, **k).start()


_seq = itertools.count(1)


def obs(cls: str, lvl: int, x: float, z: float, t: float, dwp: float):  # noqa: ANN201
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


def groups_line(store: ContactStore) -> str:
    out = []
    for g in store.groups:
        ad = sorted(dict(g.air_defence_composition).items())
        out.append(f"{g.id}={sorted(g.member_contact_ids)} ad={ad}")
    return "; ".join(out) or "(none)"


def scenario(store_ing) -> None:  # noqa: ANN001
    pass


def run(mode: str) -> None:
    global _seq
    _seq = itertools.count(1)
    G._cluster_contacts = make_variant(mode)
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
    print(f"\n--- {mode}")
    print(f"  t=20 before fold: {groups_line(store)}")
    ing(
        [
            obs("OP_INFANTRY", 2, -260.0, 20.0, 20.0, 50000.0),
            obs("OP_INFANTRY", 2, -250.0, -20.0, 20.0, 60000.0),
        ],
        20.0,
    )
    print(f"  t=20 after  fold: {groups_line(store)}")
    for t in (21.0, 22.0, 25.0, 30.0):
        store.ingest([obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, t, 40000.0)], now_sim=t)
        store.tick(now_sim=t)
    print(f"  t=30 persistence : {groups_line(store)}")
    folds = {c.id: round(c.fold_displacement_m, 1) for c in store.contacts}
    print(f"  fold budgets     : {folds}")
    G._cluster_contacts = _ORIGINAL


def main() -> None:
    tc._enrichment_context(_MP())
    for mode in ("baseline", "A_discount", "B_factor", "B_both"):
        run(mode)


main()
