"""BL-B59 probe 5: probe 4 showed the unbounded fold-budget discount is
stable but never retires (132.7 -> 239.0 m over 60 ticks, combined 498.8 m
by t=80, exceeding the 500 m eager cap). This probe measures BOUNDED forms
of the same discount, and logs `position.radius_m()` to establish whether
covariance supplies a retiring bound without a new constant.

Variants:
  A_unbounded   -- probe 4's candidate A, for reference.
  A_cap_radius  -- per-side discount capped at that contact's own
                   `position.radius_m()`. No new constant; retires if and
                   when covariance tightens on re-observation.
  A_cap_halfbs  -- per-side discount capped at half the pair's own
                   backstop. No new constant beyond an arithmetic halving,
                   but no retiring event either.

Run from `body-layer/`:
  ../../body-layer/.venv/bin/python \
      ../plans/group-retention-hysteresis/scratchpad/probe_b59_bounded.py
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
        radii = [c.position.radius_m() for c in contacts]
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
                    if mode == "A_unbounded":
                        di, dj = folds[i], folds[j]
                    elif mode == "A_cap_radius":
                        di = min(folds[i], radii[i])
                        dj = min(folds[j], radii[j])
                    else:  # A_cap_halfbs
                        di = min(folds[i], bs / 2.0)
                        dj = min(folds[j], bs / 2.0)
                    eff = max(0.0, gap - di - dj)
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


def gline(store):  # noqa: ANN001, ANN201
    return (
        " | ".join(
            f"{g.id}:{sorted(int(m.split('_')[1]) for m in g.member_contact_ids)}"
            for g in sorted(store.groups, key=lambda g: g.id)
        )
        or "(none)"
    )


def run(mode: str, extra: int = 60) -> None:
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
    before = gline(store)
    ing(
        [
            obs("OP_INFANTRY", 2, -260.0, 20.0, 20.0, 50000.0),
            obs("OP_INFANTRY", 2, -250.0, -20.0, 20.0, 60000.0),
        ],
        20.0,
    )
    after = gline(store)
    seq, log = [], []
    for k in range(1, extra + 1):
        t = 20.0 + k
        batch = [obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, t, 40000.0)]
        if k % 5 == 0:
            batch += [
                obs("OP_INFANTRY", 2, -250.0, 10.0, t, 50000.0),
                obs("OP_INFANTRY", 2, -240.0, -15.0, t, 60000.0),
            ]
        ing(batch, t)
        seq.append(gline(store))
        log.append(
            (
                t,
                {
                    c.id: (
                        round(c.fold_displacement_m, 1),
                        round(c.position.radius_m(), 1),
                    )
                    for c in store.contacts
                    if c.fold_displacement_m
                },
            )
        )
    trans = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    print(f"\n--- {mode}")
    print(f"  before fold: {before}")
    print(f"  after  fold: {after}")
    print(f"  {extra} ticks: {len(set(seq))} states, {trans} transitions")
    last = None
    for (t, _), s in zip(log, seq):
        if s != last:
            print(f"    t={t:<5.0f} {s}")
            last = s
    print("  (fold_m, radius_m) every 10th tick:")
    for t, d in log:
        if int(t) % 10 == 0:
            print(f"    t={t:<5.0f} {d}")
    G._cluster_contacts = _ORIGINAL


def main() -> None:
    tc._enrichment_context(_MP())
    for mode in ("A_unbounded", "A_cap_radius", "A_cap_halfbs"):
        run(mode)


main()
