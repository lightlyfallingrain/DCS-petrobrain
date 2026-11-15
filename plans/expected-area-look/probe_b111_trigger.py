"""BL-B111 trigger precondition probe (architect amendment, 2026-11-11).

Run from body-layer/:  .venv/bin/python ../plans/expected-area-look/probe_b111_trigger.py [n_diff n_same]

Compares the plan's literal "A not seen this poll" precondition
(`a.last_seen_sim < now`) against the amended "A out of view" precondition
(`now - a.last_seen_sim > FOCUS_DWELL_S`), on:

  Part A -- the two existing `test_contacts.py` drift sequences (continuous
            gate-path tracking at 1 s polls): how many gate matches each
            predicate would make trigger-eligible. Must be 0 for the amended one.
  Part B -- every cell of `tools/measure_expected_area_look.py`'s grid: the
            harness's trigger rate (fold or plausibly-same), with each
            precondition applied to the A the trigger would actually see
            (A as it stood *before* B's percept was ingested). Must be
            identical, cell by cell, to the plan's model, including the
            merge-echo and lost-A subsets.
"""

from __future__ import annotations

import copy
import dataclasses
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BODY = os.path.normpath(os.path.join(HERE, "..", "..", "body-layer"))
for sub in ("../world-model/src", "src", "tools", "tests"):
    sys.path.insert(0, os.path.normpath(os.path.join(BODY, sub)))

import measure_expected_area_look as m  # noqa: E402
import measure_same_group_fold as h  # noqa: E402
from test_contacts import (  # noqa: E402
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    PositionUncertainty,
    _observation,
    _ownship,
)

from belief.association_over_time import contacts_plausibly_same, passes_gate  # noqa: E402
from belief.callouts import _is_merge_echo_of_earlier_contact  # noqa: E402
from belief.contacts import ContactStore  # noqa: E402
from belief.decay import certainty_of  # noqa: E402
from belief.percept import percept_of  # noqa: E402
from perception.gaze import FOCUS_DWELL_S  # noqa: E402


def literal(a, t):  # the plan as written
    return a.last_seen_sim < t


def amended(a, t):  # out of view: not seen within the current gaze dwell
    return (t - a.last_seen_sim) > FOCUS_DWELL_S


def part_a() -> None:
    print(f"== Part A: continuous gate-path tracking (FOCUS_DWELL_S={FOCUS_DWELL_S})")
    for label, bucket in (("drift test", None), ("runaway test", "OP_1UNIT")):
        unc = PositionUncertainty(sigma_cross_m=60.0, sigma_down_m=800.0)
        own = _ownship()
        store = ContactStore()
        bearing, rng = 0.0, 8000.0
        lit = amd = matches = 0

        def obs(i, b, r):
            o = _observation(
                obs_id=f"OBS_{i}",
                t_sim=float(i),
                bearing_deg=b,
                range_m=r,
                source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
                ownship=own,
                position_uncertainty=unc,
            )
            return dataclasses.replace(o, count_bucket=bucket) if bucket else o

        store.ingest([obs(0, bearing, rng)], now_sim=0.0)
        for i in range(1, 19):
            bearing += 0.3
            rng += 150.0
            o = obs(i, bearing, rng)
            p = percept_of(o)
            for c in store.contacts:
                if passes_gate(p, c, float(i)):
                    matches += 1
                    lit += literal(c, float(i))
                    amd += amended(c, float(i))
            store.ingest([o], now_sim=float(i))
        print(
            f"  {label:13s} gate matches {matches:2d}  eligible: literal {lit:2d}  amended {amd:2d}"
        )


def trial(pair, za, zb, gap, cls, i, salt, same):
    o1, o2 = m.PAIRS[pair]
    h._fresh_realisation(f"{salt}-{i}")
    t1 = i * 1e-3
    t2 = t1 + gap
    store = ContactStore()
    store.ingest(
        [
            h._observation(
                observation_id=f"first-{i}",
                t_sim=t1,
                ownship=h._ownship(t1, 500.0),
                group_z=za,
                bias_object_id=1,
                optic=o1,
                classification_raw=cls,
                surface=False,
            )
        ],
        t1,
    )
    store.tick(t1)
    a0 = copy.deepcopy(store.contacts[0])  # A as the trigger sees it, pre-B
    ob = h._observation(
        observation_id=f"second-{i}",
        t_sim=t2,
        ownship=h._ownship(t2, 500.0),
        group_z=zb,
        bias_object_id=2,
        optic=o2,
        classification_raw=cls,
        surface=False,
    )
    store.ingest([ob], t2)
    store.tick(t2)
    cs = store.contacts
    folded = len(cs) == 1
    if folded:
        echo, lost, plaus = False, certainty_of(a0, t2) == "lost", True
    else:
        b = next(c for c in cs if c.id != a0.id)
        a_now = next(c for c in cs if c.id == a0.id)
        echo = _is_merge_echo_of_earlier_contact(b, store, t2)
        lost = certainty_of(a_now, t2) == "lost"
        plaus = contacts_plausibly_same(b, a_now, t2)
    model = folded or plaus
    return {
        "model": model,
        "lit": model and literal(a0, t2),
        "amd": model and amended(a0, t2),
        "echo_model": model and echo,
        "echo_amd": model and echo and amended(a0, t2),
        "lost_model": model and lost,
        "lost_amd": model and lost and amended(a0, t2),
    }


def part_b(n_diff: int, n_same: int) -> None:
    print("== Part B: harness trigger rate per cell, model vs amended (%)")
    worst = 0.0
    cells = 0
    tot = {"echo_model": 0, "echo_amd": 0, "lost_model": 0, "lost_amd": 0}
    for cls in ("s-125", "OP_ARMORED"):
        for gap in (6.0, 700.0):
            for pair in m.PAIRS:
                specs = []
                for far, near in ((4.5, 3.0), (5.0, 3.5), (3.0, 1.5)):
                    specs.append((f"diff {far}/{near} Bnear", -far * 1e3, -near * 1e3, False, n_diff))
                    specs.append((f"diff {far}/{near} Bfar", -near * 1e3, -far * 1e3, False, n_diff))
                for rk in (2.0, 3.0, 4.5):
                    specs.append((f"same {rk}", -rk * 1e3, -rk * 1e3, True, n_same))
                for label, za, zb, same, n in specs:
                    salt = f"trig{pair}{za}{zb}{gap}{cls}{same}"
                    rs = [trial(pair, za, zb, gap, cls, i, salt, same) for i in range(n)]
                    pct = {k: 100.0 * sum(r[k] for r in rs) / n for k in rs[0]}
                    for k in tot:
                        tot[k] += sum(r[k] for r in rs)
                    d = abs(pct["model"] - pct["amd"])
                    worst = max(worst, d)
                    cells += 1
                    print(
                        f"  {cls:10s} gap{gap:4.0f} {pair} {label:20s} model {pct['model']:5.1f} "
                        f"literal {pct['lit']:5.1f} amended {pct['amd']:5.1f}"
                    )
    print(f"  cells {cells}; max |model - amended| = {worst:.1f} points")
    print(
        f"  merge-echo trials eligible: model {tot['echo_model']} amended {tot['echo_amd']}; "
        f"lost-A trials eligible: model {tot['lost_model']} amended {tot['lost_amd']}"
    )


if __name__ == "__main__":
    nd = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    ns = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    part_a()
    part_b(nd, ns)
    h._restore_field_salt()
