"""BL-B59 probe 1: measure the eviction's two causes separately, then test
three candidate retention mechanisms against the same incident.

Reuses `plans/group-cohesion-admission-gate/scratchpad/probe_b58_second_
incident.py`'s geometry exactly (three infantry in a ~95 m knot at 1,000 m,
a continuously-observed ZSU-23-4 195 m away, infantry unobserved for 20 s,
two fresh infantry percepts fold on at t=20).

Run from `body-layer/`:
  ../../body-layer/.venv/bin/python \
      ../plans/group-retention-hysteresis/scratchpad/probe_b59_mechanism.py
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


def snapshot(store: ContactStore):  # noqa: ANN201
    contacts = list(store.contacts)
    ids = [c.id for c in contacts]
    pos = [(c.position.x, c.position.z) for c in contacts]
    profs = [G._profile_for_contact(c) for c in contacts]
    sizes = [G._representative_size_m(p) for p in profs]
    folds = [c.fold_displacement_m for c in contacts]
    n = len(ids)
    nn = [
        min(
            math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1])
            for j in range(n)
            if j != i
        )
        for i in range(n)
    ]
    rel = G.GROUP_PROXIMITY_GAP_RATIO * statistics.median(nn)
    rosters = [set(g.member_contact_ids) for g in store.groups]
    return ids, pos, profs, sizes, folds, rel, rosters


def report(label: str, store: ContactStore) -> None:
    ids, pos, profs, sizes, folds, rel, rosters = snapshot(store)
    n = len(ids)
    print(f"\n=== {label}   relative_threshold={rel:.1f}")
    print("  fold_displacement_m:", {ids[k]: round(folds[k], 1) for k in range(n)})
    for i, j in itertools.combinations(range(n), 2):
        gap = math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1])
        bs = G._pair_backstop_m(profs[i], profs[j], sizes[i], sizes[j])
        th = min(rel, bs)
        co = any(ids[i] in r and ids[j] in r for r in rosters)
        # candidate A: discount the fold budget off a prior co-member gap
        disc = max(0.0, gap - folds[i] - folds[j]) if co else gap
        print(
            f"  {ids[i] + '-' + ids[j]:<22}{gap:8.1f} gap  {bs:7.1f} bs  "
            f"{th:7.1f} th  co={str(co):<5} "
            f"ord={'LINK' if gap <= th else '. ':<4} "
            f"discounted={disc:7.1f} {'LINK' if disc <= th else '.'}"
        )
    print("  pos:", {ids[k]: (round(pos[k][0]), round(pos[k][1])) for k in range(n)})
    for g in store.groups:
        print(
            f"  GROUP {g.id} members={sorted(g.member_contact_ids)} "
            f"air_defence={sorted(dict(g.air_defence_composition).items())}"
        )


def build() -> ContactStore:
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
    return store, ing


def main() -> None:
    tc._enrichment_context(_MP())
    store, ing = build()
    report("t=20, before the fold", store)
    ing(
        [
            obs("OP_INFANTRY", 2, -260.0, 20.0, 20.0, 50000.0),
            obs("OP_INFANTRY", 2, -250.0, -20.0, 20.0, 60000.0),
        ],
        20.0,
    )
    report("t=20, after the fold", store)
    for t in (21.0, 22.0, 25.0, 30.0):
        store.ingest([obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, t, 40000.0)], now_sim=t)
        store.tick(now_sim=t)
    report("t=30, persistence check", store)


main()
