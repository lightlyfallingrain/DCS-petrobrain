"""BL-B59 probe 4: the two questions probe 3 failed to answer cleanly --

  L1 budget lifetime -- does `fold_displacement_m` actually retire in this
     geometry, or does candidate A's discount persist indefinitely? Drives
     the BL-B59 incident on for 60 further ticks under each candidate,
     logging every budget and every membership change.

  L2 oscillation     -- counts membership transitions over the same 60
     ticks for baseline / A_discount / B_factor. A retention term that
     alternated with the Stage 3.5 admission gate would show up here as a
     transition count that does not settle.

Measured axes (probe 0, `probe_b59_axes.py`): `ownship_x` drives
`Contact.position` (identity `project_terrain_aware`: position.x =
ownship_x + 1000); `dwp_x`/`dwp_z` drive gate matching only and do NOT
move the fused position -- `_observation`'s own docstring claim that dwp
drives `last_position` is stale.

Run from `body-layer/`:
  ../../body-layer/.venv/bin/python \
      ../plans/group-retention-hysteresis/scratchpad/probe_b59_lifetime.py
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
        " | ".join(
            f"{g.id}:{sorted(int(m.split('_')[1]) for m in g.member_contact_ids)}"
            for g in sorted(store.groups, key=lambda g: g.id)
        )
        or "(none)"
    )


def run(mode: str, extra_ticks: int = 60) -> None:
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

    # Keep observing: the ZSU every tick, and the infantry knot every 5th
    # tick (ordinary re-acquisition after a masked spell).
    seq = []
    budget_log = []
    for k in range(1, extra_ticks + 1):
        t = 20.0 + k
        batch = [obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, t, 40000.0)]
        if k % 5 == 0:
            batch += [
                obs("OP_INFANTRY", 2, -250.0, 10.0, t, 50000.0),
                obs("OP_INFANTRY", 2, -240.0, -15.0, t, 60000.0),
            ]
        ing(batch, t)
        seq.append(gline(store))
        budget_log.append(
            (t, {c.id: round(c.fold_displacement_m, 1) for c in store.contacts})
        )

    transitions = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    print(f"\n--- {mode}")
    print(f"  t=20 before fold : {before}")
    print(f"  t=20 after  fold : {after}")
    print(f"  {extra_ticks} further ticks: {len(set(seq))} distinct states, "
          f"{transitions} transitions")
    last = None
    for (t, _), s in zip(budget_log, seq):
        if s != last:
            print(f"    t={t:<6.0f} {s}")
            last = s
    print("  budget trace (every 5th tick):")
    for t, b in budget_log:
        if int(t) % 5 == 0:
            nz = {k: v for k, v in b.items() if v}
            print(f"    t={t:<6.0f} nonzero folds: {nz or '{}'}")
    G._cluster_contacts = _ORIGINAL


def main() -> None:
    tc._enrichment_context(_MP())
    for mode in ("baseline", "A_discount", "B_factor"):
        run(mode)


main()
