"""BL-B58 option 2, probe 1: evaluate every candidate bound on how far a
single fold-driven `Contact.record` may move a fused position, against the
same incident `plans/group-retention-hysteresis/plan.md` §2 measured.

Geometry is probe 2's, unchanged (three infantry in a ~95 m knot at
1,000 m, a continuously-observed ZSU-23-4 195 m away, infantry unobserved
for 20 s, two fresh infantry percepts fold on at t=20). Truth: the three
infantry never move, so `CONTACT_1`'s true position stays x=1000 and
`CONTACT_3`'s stays x=1030 -- that is what "residual error" is measured
against.

The clamp is installed at the seam the plan recommends: a one-shot flag set
by `_fold_target_for_ambiguous_candidates` and consumed by the very next
`Contact.record`, which is exactly `ingest`'s own fold branch
(`contacts.py:1090-1105`) and nothing else.

Run from `body-layer/`:
  /Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python \
      ../plans/bounded-fold-displacement/scratchpad/probe_o2_bound.py
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
from belief.position_belief import _inflated_since_last_fuse  # noqa: E402

TRUTH = {"CONTACT_1": (1000.0, 0.0), "CONTACT_2": (1060.0, 40.0), "CONTACT_3": (1030.0, -50.0)}


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


# ---------------------------------------------------------------- the clamp

_ORIG_FOLD_TARGET = C.ContactStore._fold_target_for_ambiguous_candidates
_ORIG_RECORD = C.Contact.record

_PENDING: dict[str, str | None] = {}
_LOG: list[tuple[str, float, float, float, float]] = []


def _bound_speed_elapsed(contact, prior, percept, *, slack: bool) -> float:  # noqa: ANN001
    """`plausible_speed_mps(class) * elapsed`, optionally plus the
    `groups.group_matches` test-5 slack analogue (prior radius + percept
    radius)."""
    speed = contact_growth_rate_mps(contact)
    elapsed = max(0.0, percept.t_sim - prior.fused_at_sim)
    bound = speed * elapsed
    if slack:
        bound += prior.radius_m() + C.percept_position_uncertainty(percept).sigma_cross_m
    return bound


def _install(kind: str, param: float = 0.0, hold_covariance: bool = True) -> None:
    def fold_target(self, passing, percept):  # noqa: ANN001, ANN202
        target = _ORIG_FOLD_TARGET(self, passing, percept)
        _PENDING["target"] = None if target is None else target.id
        return target

    def record(self, percept) -> None:  # noqa: ANN001
        is_fold = _PENDING.pop("target", None) == self.id
        prior = self.position
        growth = contact_growth_rate_mps(self)
        _ORIG_RECORD(self, percept)
        if not is_fold or kind == "none":
            return
        dx = self.position.x - prior.x
        dz = self.position.z - prior.z
        moved = math.hypot(dx, dz)
        if kind == "speed":
            bound = _bound_speed_elapsed(self, prior, percept, slack=False)
        elif kind == "speed_slack":
            bound = _bound_speed_elapsed(self, prior, percept, slack=True)
        elif kind == "radius":
            bound = param * prior.radius_m()
        elif kind == "absolute":
            bound = param
        elif kind == "refuse":
            bound = 0.0
        else:  # pragma: no cover
            raise AssertionError(kind)
        _LOG.append((self.id, percept.t_sim, moved, bound, min(moved, bound)))
        if moved <= bound:
            return
        scale = bound / moved if moved > 0.0 else 0.0
        clamped = dataclasses.replace(
            self.position, x=prior.x + dx * scale, z=prior.z + dz * scale
        )
        if hold_covariance:
            clamped = dataclasses.replace(
                clamped,
                covariance=_inflated_since_last_fuse(prior, percept.t_sim, growth),
                fused_at_sim=prior.fused_at_sim,
                fused_covariance=prior.fused_covariance,
            )
        self.position = clamped

    C.ContactStore._fold_target_for_ambiguous_candidates = fold_target
    C.Contact.record = record


def _uninstall() -> None:
    C.ContactStore._fold_target_for_ambiguous_candidates = _ORIG_FOLD_TARGET
    C.Contact.record = _ORIG_RECORD
    _PENDING.clear()
    _LOG.clear()


# ---------------------------------------------------------------- the scene


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


def rosters(store):  # noqa: ANN001
    return sorted(
        (sorted(g.member_contact_ids), sorted(dict(g.air_defence_composition).items()))
        for g in store.groups
    )


def residual(store):  # noqa: ANN001
    out = {}
    for c in store.contacts:
        if c.id in TRUTH:
            tx, tz = TRUTH[c.id]
            out[c.id] = round(math.hypot(c.position.x - tx, c.position.z - tz), 1)
    return out


def run(label: str, kind: str, param: float = 0.0, hold: bool = True, ticks: int = 60):  # noqa: ANN201
    _uninstall()
    _install(kind, param, hold)
    store, ing = build()
    pre = rosters(store)
    ing(
        [
            obs("OP_INFANTRY", 2, -260.0, 20.0, 20.0, 50000.0),
            obs("OP_INFANTRY", 2, -250.0, -20.0, 20.0, 60000.0),
        ],
        20.0,
    )
    at_fold = rosters(store)
    res_fold = residual(store)
    folds_fold = {c.id: round(c.fold_displacement_m, 1) for c in store.contacts}
    clamp_log = list(_LOG)
    transitions = 0
    last = at_fold
    for t in range(21, 21 + ticks):
        obs_batch = [obs("ZSU-23-4 Shilka", 3, -195.0, 0.0, float(t), 40000.0)]
        # every 5th tick, a fresh ambiguous infantry look: the repeat-fold
        # driver `probe_b59_lifetime.py` used.
        if t % 5 == 0:
            obs_batch.append(obs("OP_INFANTRY", 2, -260.0, 20.0, float(t), 70000.0))
        ing(obs_batch, float(t))
        now = rosters(store)
        if now != last:
            transitions += 1
            last = now
    print(f"\n### {label}")
    print(f"  pre-fold rosters      : {pre}")
    print(f"  at fold tick t=20     : {at_fold}")
    print(f"  residual error @t=20  : {res_fold}")
    print(f"  fold_displacement_m   : {folds_fold}")
    print(f"  after {ticks} ticks       : {rosters(store)}")
    print(f"  residual error @end   : {residual(store)}")
    print(f"  fold_displacement_m   : {{{', '.join(f'{c.id}: {c.fold_displacement_m:.1f}' for c in store.contacts)}}}")
    print(f"  membership transitions: {transitions}")
    if clamp_log:
        print("  clamp at the fold tick (contact, t, moved_m, bound_m, applied_m):")
        for row in clamp_log:
            print(f"    {row[0]:<10} t={row[1]:<5.0f} moved={row[2]:7.1f} bound={row[3]:7.1f} applied={row[4]:7.1f}")


def main() -> None:
    tc._enrichment_context(_MP())
    run("baseline (no bound, merged behaviour)", "none")
    run("B1  speed x elapsed, hold covariance", "speed")
    run("B1' speed x elapsed, accept fused covariance", "speed", hold=False)
    run("B2  speed x elapsed + test-5 slack", "speed_slack")
    run("B3a 1.0 x prior radius_m()", "radius", 1.0)
    run("B3b 0.5 x prior radius_m()", "radius", 0.5)
    run("B4a absolute 50 m", "absolute", 50.0)
    run("B4b absolute 25 m", "absolute", 25.0)
    run("B5  refuse the displacement outright (bound 0)", "refuse")


main()
