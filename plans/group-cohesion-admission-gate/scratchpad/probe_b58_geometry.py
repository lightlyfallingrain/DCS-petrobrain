"""BL-B58 probe 1: replay the 2C fixture and dump the clustering geometry
at the tick where CONTACT_4 is absorbed.

Run with cwd = <worktree>/body-layer:
  ../../../body-layer/.venv/bin/python ... (see command in the plan)
"""

from __future__ import annotations

import itertools
import math
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "../world-model/src")
sys.path.insert(0, "tests")

import statistics

import test_callouts as tc  # noqa: E402
from belief import groups as G  # noqa: E402
from belief.contacts import ContactStore  # noqa: E402


class _FakeMonkeypatch:
    def setattr(self, *a, **k):  # noqa: ANN002, ANN003
        import unittest.mock as m

        p = m.patch.object(*a, **k) if len(a) >= 2 else None
        if p is not None:
            p.start()


def dump(label: str, store: ContactStore) -> None:
    contacts = list(store.contacts)
    ids = [c.id for c in contacts]
    pos = [(c.position.x, c.position.z) for c in contacts]
    profs = [G._profile_for_contact(c) for c in contacts]
    sizes = [G._representative_size_m(p) for p in profs]
    n = len(ids)
    if n < 2:
        print(f"{label}: {n} contacts")
        return
    nn = []
    for i in range(n):
        nn.append(min(math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1])
                      for j in range(n) if j != i))
    med = statistics.median(nn)
    rel = G.GROUP_PROXIMITY_GAP_RATIO * med
    print(f"\n=== {label}  n={n}  median_nn={med:.1f}  relative_threshold={rel:.1f}")
    print(f"{'pair':<22}{'gap':>9}{'backstop':>11}{'thresh':>9}  verdict")
    for i, j in itertools.combinations(range(n), 2):
        d = math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1])
        bs = G._pair_backstop_m(profs[i], profs[j], sizes[i], sizes[j])
        th = min(rel, bs)
        print(f"{ids[i]+'-'+ids[j]:<22}{d:9.1f}{bs:11.1f}{th:9.1f}  "
              f"{'LINK' if d <= th else '.'}")
    print("  positions:", {ids[k]: (round(pos[k][0]), round(pos[k][1])) for k in range(n)})
    print("  classes:", {ids[k]: contacts[k].last_class_raw for k in range(n)})
    print("  unc_m:", {ids[k]: round(contacts[k].position.radius_m()) for k in range(n)})
    # `_cluster_contacts` gained `prior_rosters` in commit 2 of
    # plans/group-cohesion-admission-gate/plan.md -- `[]` here reproduces
    # this probe's original purpose (the raw geometry table above, and the
    # no-gate cluster/extent dump), not the live gate; see implementation.md
    # for the gate re-run against the real pipeline (probe 2).
    cl = G._cluster_contacts(contacts, G.GROUP_PROXIMITY_GAP_RATIO,
                             G.GROUP_REPORTING_MIN_MEMBERS, [])
    for c in cl:
        mem = sorted(c)
        members = [contacts[ids.index(m)] for m in mem]
        print(f"  cluster {mem} extent={G._extent_of(members):.1f}")


def main() -> None:
    mp = _FakeMonkeypatch()
    tc._enrichment_context(mp)
    store = ContactStore()

    def ing(obs, t):  # noqa: ANN001
        store.ingest(obs, now_sim=t)
        store.tick(now_sim=t)

    x1, z1 = tc._xz_for_clock(12, 500.0)
    x2, z2 = tc._xz_for_clock(1, 500.0)
    x3, z3 = tc._xz_for_clock(12, 500.0)
    ing([
        tc._observation(obs_id="OBS_1", t_sim=0.0, classification_raw="OP_INFANTRY",
                        classification_level=2, ownship_x=x1, ownship_z=z1,
                        dwp_x=100000.0, dwp_z=0.0),
        tc._observation(obs_id="OBS_2", t_sim=0.0, classification_raw="OP_INFANTRY",
                        classification_level=2, ownship_x=x2, ownship_z=z2,
                        dwp_x=110000.0, dwp_z=0.0),
        tc._observation(obs_id="OBS_3", t_sim=0.0, classification_raw="OP_INFANTRY",
                        classification_level=2, ownship_x=x3, ownship_z=z3,
                        dwp_x=120000.0, dwp_z=0.0),
    ], 0.0)

    xd, zd = tc._xz_for_clock(1, 280.0)
    ing([tc._observation(obs_id="OBS_D0", t_sim=-100.0, classification_raw="OP_ARMORED",
                         classification_level=2, ownship_x=xd, ownship_z=zd,
                         dwp_x=130000.0, dwp_z=0.0)], -100.0)
    ing([tc._observation(obs_id="OBS_D1", t_sim=4.0, classification_raw="BTR-70",
                         classification_level=3, ownship_x=xd, ownship_z=zd,
                         dwp_x=130000.0, dwp_z=0.0)], 4.0)

    xg, zg = tc._xz_for_clock(12, 290.0)
    ing([tc._observation(obs_id="OBS_G0", t_sim=-100.0,
                         classification_raw=tc.PRESENCE_CLASS,
                         classification_level=1, ownship_x=xg, ownship_z=zg,
                         dwp_x=140000.0, dwp_z=0.0)], -100.0)
    ing([tc._observation(obs_id="OBS_G1", t_sim=8.0, classification_raw="OP_TRUCK",
                         classification_level=2, ownship_x=xg, ownship_z=zg,
                         dwp_x=140000.0, dwp_z=0.0)], 8.0)

    dump("t=8, before the fold", store)

    x5, z5 = tc._xz_for_clock(2, 300.0)
    x6, z6 = tc._xz_for_clock(2, 300.0)
    ing([
        tc._observation(obs_id="OBS_5", t_sim=12.0, classification_raw="OP_INFANTRY",
                        classification_level=2, ownship_x=x5, ownship_z=z5,
                        dwp_x=150000.0, dwp_z=0.0),
        tc._observation(obs_id="OBS_6", t_sim=12.0, classification_raw="OP_INFANTRY",
                        classification_level=2, ownship_x=x6, ownship_z=z6,
                        dwp_x=160000.0, dwp_z=0.0),
    ], 12.0)

    dump("t=12, after the fold (absorption tick)", store)

    for t in (13.0, 14.0, 15.0):
        store.tick(now_sim=t)
    dump("t=15", store)


main()
