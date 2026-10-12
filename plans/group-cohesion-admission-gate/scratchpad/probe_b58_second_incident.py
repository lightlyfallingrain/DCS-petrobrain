"""BL-B58 probe 2: a clean SECOND incident, independent of the 2C fixture,
with an air-defence contact as the absorbed member.

Positions: with `_enrichment_context`'s identity `project_terrain_aware`,
a contact's fused position is `(ownship_x + 1000, ownship_z)` (measured in
probe 1), so ownship_x/z place contacts exactly.
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


def dump(label: str, store: ContactStore) -> None:
    contacts = list(store.contacts)
    ids = [c.id for c in contacts]
    pos = [(c.position.x, c.position.z) for c in contacts]
    profs = [G._profile_for_contact(c) for c in contacts]
    sizes = [G._representative_size_m(p) for p in profs]
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
    print(f"\n=== {label}   relative_threshold={rel:.1f}")
    for i, j in itertools.combinations(range(n), 2):
        d = math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1])
        bs = G._pair_backstop_m(profs[i], profs[j], sizes[i], sizes[j])
        th = min(rel, bs)
        print(
            f"  {ids[i]+'-'+ids[j]:<22}{d:9.1f} gap  {bs:8.1f} backstop  "
            f"{th:8.1f} thresh  {'LINK' if d <= th else '.'}"
        )
    print(
        "  pos:",
        {ids[k]: (round(pos[k][0]), round(pos[k][1])) for k in range(n)},
    )
    print("  cls:", {ids[k]: contacts[k].last_class_raw for k in range(n)})
    for g in store.groups:
        print(
            f"  GROUP {g.id} members={sorted(g.member_contact_ids)} "
            f"air_defence={sorted(dict(g.air_defence_composition).items())}"
        )


def main() -> None:
    tc._enrichment_context(_MP())
    store = ContactStore()

    def ing(o, t):  # noqa: ANN001
        store.ingest(o, now_sim=t)
        store.tick(now_sim=t)

    # t=0: three infantry in a tight knot, and a ZSU-23-4 (air defence)
    # 230 m away -- outside the infantry/ZSU pair backstop, so no bridge.
    ing(
        [
            obs("OP_INFANTRY", 2, 0.0, 0.0, 0.0, 10000.0),
            obs("OP_INFANTRY", 2, 60.0, 40.0, 0.0, 20000.0),
            obs("OP_INFANTRY", 2, 30.0, -50.0, 0.0, 30000.0),
            obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, 0.0, 40000.0),
        ],
        0.0,
    )
    # Keep the ZSU continuously observed (its position stays tight); the
    # infantry are NOT re-observed, so their covariance inflates.
    for t in range(1, 21):
        ing([obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, float(t), 40000.0)], float(t))

    dump("t=20, before the fold", store)

    # t=20: two fresh infantry percepts 260 m toward the ZSU. They pass the
    # inflated gate against all three remembered infantry, which are all in
    # one Group -> Stage 3 branch 2 folds them on instead of founding.
    ing(
        [
            obs("OP_INFANTRY", 2, -260.0, 20.0, 20.0, 50000.0),
            obs("OP_INFANTRY", 2, -250.0, -20.0, 20.0, 60000.0),
        ],
        20.0,
    )
    dump("t=20, after the fold", store)
    for t in (21.0, 22.0, 25.0, 30.0):
        store.ingest([obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, t, 40000.0)], now_sim=t)
        store.tick(now_sim=t)
    dump("t=30, persistence check", store)


main()
