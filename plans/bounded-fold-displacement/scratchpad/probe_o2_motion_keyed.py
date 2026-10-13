"""BL-B58 option 2, probe 5: does the user's 2026-10-13 motion-keyed
uncertainty direction invalidate the bound this plan recommends?

Three measurements, all against the same incident:

1. **What `Contact.motion` actually is in this incident.** If it is `None`,
   a motion-keyed `plausible_speed_mps` falls back to the class rate and
   the bound is unchanged -- which is the whole question.
2. **Does a motion-keyed rate stop the fold firing at all?** Re-runs the
   incident with the infantry percepts carrying `apparent_motion=False`
   (observed stationary) and `contact_growth_rate_mps` returning 0.0 for a
   `"stopped"` contact, and counts whether any percept still has >=2
   passing gate candidates.
3. **`BL-B24`'s shape**: two contacts 17 m apart, both observed stationary,
   reacquired after 120 s -- does either still sit inside the other's
   inflated gate?

Run from `body-layer/`:
  /Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python \
      ../plans/bounded-fold-displacement/scratchpad/probe_o2_motion_keyed.py
"""

from __future__ import annotations

import itertools
import math
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "../world-model/src")
sys.path.insert(0, "tests")

import test_callouts as tc  # noqa: E402
from belief import association_over_time as A  # noqa: E402
from belief.contacts import ContactStore  # noqa: E402
from belief.decay import MOTION_STOP_CONFIRM_S  # noqa: E402
from belief.percept import percept_of  # noqa: E402


class _MP:
    def setattr(self, *a, **k):  # noqa: ANN002, ANN003
        import unittest.mock as m

        m.patch.object(*a, **k).start()


_seq = itertools.count(1)


def obs(cls, lvl, x, z, t, dwp, motion=None):  # noqa: ANN001, ANN201
    return tc._observation(
        obs_id=f"OBS_{next(_seq)}",
        t_sim=t,
        classification_raw=cls,
        classification_level=lvl,
        ownship_x=x,
        ownship_z=z,
        dwp_x=dwp,
        dwp_z=0.0,
        apparent_motion=motion,
    )


_ORIG_RATE = A.contact_growth_rate_mps


def _motion_keyed(contact):  # noqa: ANN001, ANN202
    """The user's direction, in its narrowest honest form: an observed-
    stationary contact grows at 0; `None` (never observed moving or still)
    falls back to the class rate, because `None` is not `"stopped"`."""
    motion = contact.motion
    if motion is not None and motion.state == "stopped":
        return 0.0
    return _ORIG_RATE(contact)


def incident(motion_flag, motion_keyed: bool):  # noqa: ANN001, ANN201
    A.contact_growth_rate_mps = _motion_keyed if motion_keyed else _ORIG_RATE
    # `contacts.py` imported the name directly, so rebind it there too.
    import belief.contacts as CM

    CM.contact_growth_rate_mps = A.contact_growth_rate_mps

    store = ContactStore()

    def ing(o, t):  # noqa: ANN001
        store.ingest(o, now_sim=t)
        store.tick(now_sim=t)

    ing(
        [
            obs("OP_INFANTRY", 2, 0.0, 0.0, 0.0, 10000.0, motion_flag),
            obs("OP_INFANTRY", 2, 60.0, 40.0, 0.0, 20000.0, motion_flag),
            obs("OP_INFANTRY", 2, 30.0, -50.0, 0.0, 30000.0, motion_flag),
            obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, 0.0, 40000.0, motion_flag),
        ],
        0.0,
    )
    # Hold the infantry long enough for a `False` motion claim to be
    # confirmed as "stopped" before they go unobserved.
    confirm = int(math.ceil(MOTION_STOP_CONFIRM_S)) + 1
    for t in range(1, confirm + 1):
        ing(
            [
                obs("OP_INFANTRY", 2, 0.0, 0.0, float(t), 10000.0, motion_flag),
                obs("OP_INFANTRY", 2, 60.0, 40.0, float(t), 20000.0, motion_flag),
                obs("OP_INFANTRY", 2, 30.0, -50.0, float(t), 30000.0, motion_flag),
                obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, float(t), 40000.0, motion_flag),
            ],
            float(t),
        )
    for t in range(confirm + 1, 21):
        ing([obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, float(t), 40000.0, motion_flag)], float(t))

    motions = {
        c.id: (None if c.motion is None else c.motion.state) for c in store.contacts
    }
    rates = {c.id: round(A.contact_growth_rate_mps(c), 2) for c in store.contacts}

    # How many passing gate candidates would the two fresh infantry
    # percepts have at t=20?
    fresh = [
        obs("OP_INFANTRY", 2, -260.0, 20.0, 20.0, 50000.0, motion_flag),
        obs("OP_INFANTRY", 2, -250.0, -20.0, 20.0, 60000.0, motion_flag),
    ]
    candidate_counts = []
    for o in fresh:
        p = percept_of(o)
        passing = [c.id for c in store.contacts if A.passes_gate(p, c, 20.0)]
        candidate_counts.append((o.id, passing))

    ing(fresh, 20.0)
    rosters = [sorted(g.member_contact_ids) for g in store.groups]
    folds = {c.id: round(c.fold_displacement_m, 1) for c in store.contacts}
    A.contact_growth_rate_mps = _ORIG_RATE
    CM.contact_growth_rate_mps = _ORIG_RATE
    return motions, rates, candidate_counts, rosters, folds, len(list(store.contacts))


def bl_b24(motion_flag, motion_keyed: bool, gap_m: float = 17.0, unseen_s: float = 120.0):  # noqa: ANN001, ANN201
    """Two contacts `gap_m` apart, observed (stationary or not), then
    reacquired after `unseen_s`. Does a fresh percept at one of them still
    pass the *other's* gate?"""
    A.contact_growth_rate_mps = _motion_keyed if motion_keyed else _ORIG_RATE
    import belief.contacts as CM

    CM.contact_growth_rate_mps = A.contact_growth_rate_mps
    store = ContactStore()
    confirm = int(math.ceil(MOTION_STOP_CONFIRM_S)) + 1
    for t in range(confirm + 1):
        store.ingest(
            [
                obs("OP_INFANTRY", 2, 0.0, 0.0, float(t), 10000.0, motion_flag),
                obs("OP_INFANTRY", 2, gap_m, 0.0, float(t), 90000.0, motion_flag),
            ],
            now_sim=float(t),
        )
        store.tick(now_sim=float(t))
    t_re = float(confirm) + unseen_s
    p = percept_of(obs("OP_INFANTRY", 2, 0.0, 0.0, t_re, 10000.0, motion_flag))
    passing = [c.id for c in store.contacts if A.passes_gate(p, c, t_re)]
    rates = {c.id: round(A.contact_growth_rate_mps(c), 2) for c in store.contacts}
    A.contact_growth_rate_mps = _ORIG_RATE
    CM.contact_growth_rate_mps = _ORIG_RATE
    return rates, passing, len(list(store.contacts))


def main() -> None:
    tc._enrichment_context(_MP())
    print(f"MOTION_STOP_CONFIRM_S = {MOTION_STOP_CONFIRM_S}\n")

    print("## 1-2. The incident, three motion regimes\n")
    for label, flag, keyed in (
        ("as shipped: apparent_motion=None, class rate", None, False),
        ("motion-keyed rate, but motion still None", None, True),
        ("percepts say apparent_motion=False, motion-keyed rate", False, True),
        ("percepts say apparent_motion=False, class rate (control)", False, False),
    ):
        motions, rates, cands, rosters, folds, n = incident(flag, keyed)
        print(f"### {label}")
        print(f"  Contact.motion      : {motions}")
        print(f"  growth rate (m/s)   : {rates}")
        for oid, passing in cands:
            print(f"  {oid} passing gate candidates: {len(passing)} {passing}")
        print(f"  rosters after t=20  : {rosters}")
        print(f"  fold_displacement_m : {folds}   contacts={n}\n")

    print("\n## 3. BL-B24's shape: two contacts 17 m apart, reacquired after 120 s\n")
    for label, flag, keyed in (
        ("as shipped (motion None, class rate)", None, False),
        ("observed stationary + motion-keyed rate", False, True),
        ("observed moving + motion-keyed rate", True, True),
    ):
        rates, passing, n = bl_b24(flag, keyed)
        print(f"  {label:<42} rates={rates}  passing={len(passing)} {passing}  contacts={n}")


main()
