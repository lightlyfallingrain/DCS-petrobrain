"""BL-B59 probe 6: the recommended mechanism, and the bound sweep behind
its one constant.

  A_cap_frac(f) -- prior co-members only, and only where a fold budget is
                   actually non-zero:
                     discount = min(folds[i] + folds[j], f * pair_threshold)
                     effective_gap = max(0.0, gap - discount)
                   so a retained pair can never link beyond
                   (1 + f) * pair_threshold. At f = 0.5 that ceiling is
                   1.5x -- numerically the same hysteresis band
                   `plans/watch-reporting/plan.md` 4e already established,
                   reached as a bounded gap discount rather than a
                   threshold multiplier.

Sweeps f over 0.0 .. 1.0 and reports, for each: whether the BL-B59
incident is fixed, membership transitions over 60 further ticks, and the
worst-case retained-pair ceiling in metres.

Run from `body-layer/`:
  ../../body-layer/.venv/bin/python \
      ../plans/group-retention-hysteresis/scratchpad/probe_b59_recommended.py
"""

from __future__ import annotations

import itertools
import statistics
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "../world-model/src")
sys.path.insert(0, "tests")

import test_callouts as tc  # noqa: E402
from belief import groups as G  # noqa: E402
from belief.contacts import ContactStore  # noqa: E402

_ORIGINAL = G._cluster_contacts


def make_variant(frac: float | None):  # noqa: ANN201
    """`frac is None` -> shipped baseline."""

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
                th = min(rel, bs)
                ri = roster_of.get(ids[i])
                co = ri is not None and ri == roster_of.get(ids[j])
                if co:
                    # retention: bounded discount of the fold-attributable
                    # part of the gap. Zero budgets -> max(0, gap) == gap,
                    # i.e. algebraically the shipped rule.
                    disc = min(folds[i] + folds[j], frac * th)
                    eff = max(0.0, gap - disc)
                else:
                    eff = gap + folds[i] + folds[j]  # Stage 3.5 admission
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


def members(store):  # noqa: ANN001, ANN201
    return {
        g.id: tuple(sorted(int(m.split("_")[1]) for m in g.member_contact_ids))
        for g in sorted(store.groups, key=lambda g: g.id)
    }


def run(frac, extra=60):  # noqa: ANN001, ANN201
    global _seq
    _seq = itertools.count(1)
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
    after = members(store)
    seq = []
    for k in range(1, extra + 1):
        t = 20.0 + k
        batch = [obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, t, 40000.0)]
        if k % 5 == 0:
            batch += [
                obs("OP_INFANTRY", 2, -250.0, 10.0, t, 50000.0),
                obs("OP_INFANTRY", 2, -240.0, -15.0, t, 60000.0),
            ]
        ing(batch, t)
        seq.append(repr(members(store)))
    trans = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    retained = any(
        set(v) >= {1, 2, 3} for v in after.values()
    )
    G._cluster_contacts = _ORIGINAL
    return retained, trans, after


def main() -> None:
    tc._enrichment_context(_MP())
    print("f      CONTACT_2 retained?   transitions/60   GROUP_1 after fold")
    print("-" * 78)
    r, t, a = run(None)
    print(f"{'base':<7}{str(r):<22}{t:<17}{a}")
    for f in (0.0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.75, 1.0):
        r, t, a = run(f)
        print(f"{f:<7}{str(r):<22}{t:<17}{a}")
    print()
    print("Retained-pair ceiling, as a multiple of the pair's own threshold:")
    for f in (0.25, 0.5, 1.0):
        print(f"  f={f}: ceiling = {1 + f}x threshold")
    print()
    print("In metres for the two pair kinds this module actually has:")
    for f in (0.25, 0.5):
        print(
            f"  f={f}: eager infantry pair (bs 500 m) -> {(1 + f) * 500:.0f} m; "
            f"BTR-70 pair (bs 140 m) -> {(1 + f) * 140:.0f} m"
        )


main()
