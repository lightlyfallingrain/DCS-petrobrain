"""BL-B58 option 2, probe 4: **re-measure Stage 3.5's six-row table under
the bound**, and sweep the bound's multiplier.

Two questions, both asked by the dispatching brief:

1. Does Stage 3.5's admission gate still do any work once the fold's
   displacement is bounded at source? Answered by running the real
   incident with the bound installed, twice -- once with the real
   `_cluster_contacts` and once with its admission term neutralised
   (every pair treated as a prior co-member, i.e. `effective_gap = gap`).
   If both give the same roster, the gate is a no-op in that row.
2. What does a multiplier on the bound cost and buy? `k * plausible_speed
   * elapsed`, k in {1, 2, 3}, against the incident and against the
   8 m/s misclassified-unit case probe 3 found.

Rows C-F of Stage 3.5's table feed `_cluster_contacts` synthetic positions
and hand-set fold budgets directly, so a change confined to
`contacts.py`'s fold branch cannot alter them -- they are identical by
construction and are not re-run here (stated, not measured, and the
reason is given).

Run from `body-layer/`:
  /Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python \
      ../plans/bounded-fold-displacement/scratchpad/probe_o2_stage35.py
"""

from __future__ import annotations

import dataclasses
import itertools
import math
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "../world-model/src")
sys.path.insert(0, "tests")

import test_callouts as tc  # noqa: E402
from belief import contacts as C  # noqa: E402
from belief import groups as G  # noqa: E402
from belief.association_over_time import contact_growth_rate_mps  # noqa: E402
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


_ORIG_FOLD_TARGET = C.ContactStore._fold_target_for_ambiguous_candidates
_ORIG_RECORD = C.Contact.record
_ORIG_CLUSTER = G._cluster_contacts
_PENDING: dict[str, str | None] = {}


def _install(multiplier: float | None, gate: bool) -> None:
    def fold_target(self, passing, percept):  # noqa: ANN001, ANN202
        target = _ORIG_FOLD_TARGET(self, passing, percept)
        _PENDING["target"] = None if target is None else target.id
        return target

    def record(self, percept) -> None:  # noqa: ANN001
        is_fold = _PENDING.pop("target", None) == self.id
        prior = self.position
        _ORIG_RECORD(self, percept)
        if not is_fold or multiplier is None:
            return
        dx = self.position.x - prior.x
        dz = self.position.z - prior.z
        moved = math.hypot(dx, dz)
        bound = (
            multiplier
            * contact_growth_rate_mps(self)
            * max(0.0, percept.t_sim - prior.fused_at_sim)
        )
        if moved <= bound:
            return
        scale = bound / moved if moved > 0.0 else 0.0
        self.position = dataclasses.replace(
            self.position, x=prior.x + dx * scale, z=prior.z + dz * scale
        )

    C.ContactStore._fold_target_for_ambiguous_candidates = fold_target
    C.Contact.record = record

    if gate:
        G._cluster_contacts = _ORIG_CLUSTER
    else:
        # Neutralise the admission term: tell the clusterer every contact
        # shares one prior roster, so every pair takes the ordinary rule.
        def no_gate(contacts, *a, **k):  # noqa: ANN001, ANN002, ANN003
            everyone = [frozenset(c.id for c in contacts)]
            if "prior_rosters" in k:
                k = dict(k)
                k["prior_rosters"] = everyone
                return _ORIG_CLUSTER(contacts, *a, **k)
            # `reconcile` passes it positionally, as the last argument.
            return _ORIG_CLUSTER(contacts, *a[:-1], everyone, **k)

        G._cluster_contacts = no_gate


def _uninstall() -> None:
    C.ContactStore._fold_target_for_ambiguous_candidates = _ORIG_FOLD_TARGET
    C.Contact.record = _ORIG_RECORD
    G._cluster_contacts = _ORIG_CLUSTER
    _PENDING.clear()


def rosters(store):  # noqa: ANN001
    return sorted(
        (sorted(g.member_contact_ids), sorted(dict(g.air_defence_composition).items()))
        for g in store.groups
    )


def incident2(multiplier: float | None, gate: bool):  # noqa: ANN201
    """Stage 3.5 row B: three infantry knot + continuously observed
    ZSU-23-4; two fresh infantry percepts fold on at t=20."""
    _uninstall()
    _install(multiplier, gate)
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
    pos = {c.id: (round(c.position.x), round(c.position.z)) for c in store.contacts}
    folds = {c.id: round(c.fold_displacement_m, 1) for c in store.contacts}
    return rosters(store), pos, folds


def main() -> None:
    tc._enrichment_context(_MP())

    print("## Row B (incident 2) -- is Stage 3.5's gate still load-bearing?\n")
    print(f"{'bound':<28}{'gate ON':<46}{'gate OFF (neutralised)'}")
    for label, mult in (
        ("none (merged behaviour)", None),
        ("k=1 x speed x elapsed", 1.0),
        ("k=2 x speed x elapsed", 2.0),
        ("k=3 x speed x elapsed", 3.0),
    ):
        on, pos_on, folds_on = incident2(mult, gate=True)
        off, _, _ = incident2(mult, gate=False)
        same = "  (gate is a NO-OP here)" if on == off else "  (gate CHANGES the answer)"
        print(f"{label:<28}{str([r[0] for r in on]):<46}{[r[0] for r in off]}{same}")
        print(f"{'':<28}air_defence ON={[r[1] for r in on]}  OFF={[r[1] for r in off]}")
        print(f"{'':<28}pos={pos_on}")
        print(f"{'':<28}fold_displacement_m={folds_on}\n")

    print("\n## The absorbing edge, measured directly (why the gate goes quiet)\n")
    for label, mult in (("none", None), ("k=1", 1.0), ("k=2", 2.0), ("k=3", 3.0)):
        _, pos, _ = incident2(mult, gate=True)
        if "CONTACT_1" not in pos or "CONTACT_4" not in pos:
            continue
        c1, c4 = pos["CONTACT_1"], pos["CONTACT_4"]
        gap = math.hypot(c1[0] - c4[0], c1[1] - c4[1])
        print(f"  bound={label:<6} CONTACT_1={c1}  CONTACT_4(ZSU)={c4}  gap={gap:6.1f} m  (Stage 3.5's measured backstop for this pair = 78.0 m)")

    _uninstall()


main()
