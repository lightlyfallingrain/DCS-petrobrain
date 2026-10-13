"""BL-B58 option 2, probe 2: **position accuracy as the acceptance
criterion** (user direction, 2026-10-13: *"Attack run does need individual
unit positions. That is the whole premise of attack run."*).

Same incident as probe 1, but scored against *every real unit in the
scene*, not only the three that already have a contact:

  U1 infantry  (1000,   0)  -- original knot, contact CONTACT_1
  U2 infantry  (1060,  40)  -- original knot, contact CONTACT_2
  U3 infantry  (1030, -50)  -- original knot, contact CONTACT_3
  U4 ZSU-23-4  ( 805,   0)  -- continuously observed, contact CONTACT_4
  U5 infantry  ( 740,  20)  -- arrives at t=20, the percept that folds
  U6 infantry  ( 750, -20)  -- arrives at t=20, the percept that folds

For each variant it reports, per real unit, the distance to the nearest
believed contact position and whether any contact is *dedicated* to it
(nearest-contact assignment is injective). An unmatched real unit is a
target the pilot would never be told about -- which no displacement bound
can fix.

Variants include **B6, "found instead of fold"**: `_fold_target_for_
ambiguous_candidates` forced to return `None`, which is exactly the
reversal of `D5`'s contact-grain continuity preference. Measured so the
user can see what the fold itself costs, independent of its magnitude.

Run from `body-layer/`:
  /Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python \
      ../plans/bounded-fold-displacement/scratchpad/probe_o2_accuracy.py
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
from belief.association_over_time import contact_growth_rate_mps  # noqa: E402
from belief.contacts import ContactStore  # noqa: E402
from perception.estimation import BEARING_SIGMA_DEG  # noqa: E402

TRUTH = {
    "U1 inf  ": (1000.0, 0.0),
    "U2 inf  ": (1060.0, 40.0),
    "U3 inf  ": (1030.0, -50.0),
    "U4 ZSU  ": (805.0, 0.0),
    "U5 inf* ": (740.0, 20.0),
    "U6 inf* ": (750.0, -20.0),
}
OWNSHIP = (0.0, 0.0)


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
_PENDING: dict[str, str | None] = {}


def _install(kind: str, param: float = 0.0) -> None:
    def fold_target(self, passing, percept):  # noqa: ANN001, ANN202
        if kind == "nofold":
            _PENDING["target"] = None
            return None
        target = _ORIG_FOLD_TARGET(self, passing, percept)
        _PENDING["target"] = None if target is None else target.id
        return target

    def record(self, percept) -> None:  # noqa: ANN001
        is_fold = _PENDING.pop("target", None) == self.id
        prior = self.position
        _ORIG_RECORD(self, percept)
        if not is_fold or kind in ("none", "nofold"):
            return
        dx = self.position.x - prior.x
        dz = self.position.z - prior.z
        moved = math.hypot(dx, dz)
        if kind == "speed":
            bound = contact_growth_rate_mps(self) * max(
                0.0, percept.t_sim - prior.fused_at_sim
            )
        elif kind == "absolute":
            bound = param
        else:  # pragma: no cover
            raise AssertionError(kind)
        if moved <= bound:
            return
        scale = bound / moved if moved > 0.0 else 0.0
        self.position = dataclasses.replace(
            self.position, x=prior.x + dx * scale, z=prior.z + dz * scale
        )

    C.ContactStore._fold_target_for_ambiguous_candidates = fold_target
    C.Contact.record = record


def _uninstall() -> None:
    C.ContactStore._fold_target_for_ambiguous_candidates = _ORIG_FOLD_TARGET
    C.Contact.record = _ORIG_RECORD
    _PENDING.clear()


def build():  # noqa: ANN201
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


def score(label: str, store) -> None:  # noqa: ANN001
    contacts = [(c.id, c.position.x, c.position.z, c.position.radius_m()) for c in store.contacts]
    print(f"\n### {label}   contacts={len(contacts)} for {len(TRUTH)} real units")
    used: set[str] = set()
    for name, (tx, tz) in TRUTH.items():
        best, bestd, bestr = None, math.inf, 0.0
        for cid, cx, cz, rad in contacts:
            d = math.hypot(cx - tx, cz - tz)
            if d < bestd:
                best, bestd, bestr = cid, d, rad
        rng = math.hypot(tx - OWNSHIP[0], tz - OWNSHIP[1])
        bearing_err_deg = math.degrees(math.atan2(bestd, rng))
        dedicated = best not in used
        used.add(best)  # type: ignore[arg-type]
        print(
            f"  {name} truth=({tx:6.0f},{tz:5.0f})  nearest={best:<11} "
            f"err={bestd:7.1f} m  ({bearing_err_deg:5.2f} deg at {rng:.0f} m)  "
            f"belief_radius={bestr:6.1f}  {'' if dedicated else '** SHARED RECORD **'}"
        )
    unmatched = [n for n in TRUTH if True] and len(TRUTH) - len(used)
    print(f"  distinct contacts used: {len(used)}  -> {unmatched} real unit(s) with no dedicated record")
    print(f"  (naked-eye BEARING_SIGMA_DEG = {BEARING_SIGMA_DEG})")
    for g in store.groups:
        print(f"  GROUP {g.id} members={sorted(g.member_contact_ids)}")


def run(label: str, kind: str, param: float = 0.0, ticks: int = 0) -> None:
    _uninstall()
    _install(kind, param)
    store, ing = build()
    ing(
        [
            obs("OP_INFANTRY", 2, -260.0, 20.0, 20.0, 50000.0),
            obs("OP_INFANTRY", 2, -250.0, -20.0, 20.0, 60000.0),
        ],
        20.0,
    )
    score(f"{label}  @ t=20 (the fold tick)", store)
    if ticks:
        for t in range(21, 21 + ticks):
            batch = [obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, float(t), 40000.0)]
            if t % 5 == 0:
                batch.append(obs("OP_INFANTRY", 2, -260.0, 20.0, float(t), 70000.0))
            ing(batch, float(t))
        score(f"{label}  @ t={20 + ticks} (after repeat folds)", store)


def main() -> None:
    tc._enrichment_context(_MP())
    run("baseline (merged behaviour, unbounded fold)", "none", ticks=60)
    run("B1' bound = plausible_speed x elapsed", "speed", ticks=60)
    run("B4a bound = 50 m absolute", "absolute", 50.0, ticks=60)
    run("B5  bound = 0 (fold never moves a position)", "absolute", 0.0, ticks=60)
    run("B6  found instead of fold (reverses D5 at contact grain)", "nofold", ticks=60)


main()
