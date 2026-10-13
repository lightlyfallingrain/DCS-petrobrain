"""BL-B58 option 2, probe 3: the discriminating case probe 1 and 2 cannot
decide -- a contact that **genuinely moves** while every look at it is
ambiguous.

Probe 2 measured residual 0.0 m for a bound of zero ("a fold never moves a
position"), which looks like the best possible answer. It is suspected to
be an artifact of a scene whose truth is that nothing moved. This probe
builds the opposite: two contacts ~200 m apart, both genuinely translating
at a constant speed, observed every tick. At the fixture's 300 m fallback
uncertainty every look has >=2 passing gate candidates, so every look is
an ambiguous fold -- the regime in which a zero bound freezes the belief.

Two speeds, both against the same `OP_INFANTRY` class bound of 2.0 m/s:
  - 2 m/s: exactly the plausible-speed bound. A correct bound should track.
  - 8 m/s: four times the class bound -- a unit moving faster than its
    believed class allows. Every variant must lag; the question is by how
    much, and whether the belief's own stated uncertainty covers the lag.

Run from `body-layer/`:
  /Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python \
      ../plans/bounded-fold-displacement/scratchpad/probe_o2_motion.py
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


def _install(kind: str, param: float = 0.0, hold: bool = False) -> None:
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
        growth = contact_growth_rate_mps(self)
        _ORIG_RECORD(self, percept)
        if not is_fold or kind in ("none", "nofold"):
            return
        dx = self.position.x - prior.x
        dz = self.position.z - prior.z
        moved = math.hypot(dx, dz)
        if kind == "speed":
            bound = growth * max(0.0, percept.t_sim - prior.fused_at_sim)
        elif kind == "absolute":
            bound = param
        else:  # pragma: no cover
            raise AssertionError(kind)
        if moved <= bound:
            return
        scale = bound / moved if moved > 0.0 else 0.0
        clamped = dataclasses.replace(
            self.position, x=prior.x + dx * scale, z=prior.z + dz * scale
        )
        if hold:
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


def run(label: str, kind: str, speed_mps: float, param: float = 0.0, hold: bool = False, ticks: int = 40):  # noqa: ANN201
    _uninstall()
    _install(kind, param, hold)
    store = ContactStore()
    # Two infantry 200 m apart in x, both translating at `speed_mps` in +x.
    # ownship_x drives position: position.x = ownship_x + 1000.
    rows = []
    for t in range(ticks + 1):
        base = speed_mps * t
        batch = [
            obs("OP_INFANTRY", 2, base, 0.0, float(t), 10000.0),
            obs("OP_INFANTRY", 2, base + 200.0, 0.0, float(t), 20000.0),
        ]
        store.ingest(batch, now_sim=float(t))
        store.tick(now_sim=float(t))
        if t in (0, 5, 10, 20, 40):
            truth = [(1000.0 + base, 0.0), (1200.0 + base, 0.0)]
            cs = [(c.id, c.position.x, c.position.z, c.position.radius_m()) for c in store.contacts]
            errs = []
            for tx, tz in truth:
                best = min(cs, key=lambda c: math.hypot(c[1] - tx, c[2] - tz))
                errs.append((round(math.hypot(best[1] - tx, best[2] - tz), 1), round(best[3], 0)))
            rows.append((t, len(cs), errs))
    print(f"\n### {label}   truth speed = {speed_mps} m/s (class bound 2.0)")
    for t, ncontacts, errs in rows:
        pretty = "  ".join(f"err={e:6.1f} m (radius {r:5.0f})" for e, r in errs)
        print(f"  t={t:<3} contacts={ncontacts:<3} {pretty}")


def main() -> None:
    tc._enrichment_context(_MP())
    for speed in (2.0, 8.0):
        run(f"baseline (unbounded fold), {speed} m/s", "none", speed)
        run(f"B1' speed x elapsed, {speed} m/s", "speed", speed)
        run(f"B5  bound 0, accept fused covariance, {speed} m/s", "absolute", speed, 0.0, hold=False)
        run(f"B5h bound 0, hold prior covariance, {speed} m/s", "absolute", speed, 0.0, hold=True)
        run(f"B6  found instead of fold, {speed} m/s", "nofold", speed)


main()
