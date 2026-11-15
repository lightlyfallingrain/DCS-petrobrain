"""BL-B111 architect probe: what the pilot hears today vs under the
expected-area look's verdict rules, on the honest harness
(tools/measure_same_group_fold.py draws, every draw resampled per trial).

The look itself is modelled, not built: it is "available" whenever A's
expected area fits one look (half-width <= 15 deg); terrain, towns and the
glass budget are not modelled (flat harness, one pair). "A observed" =
a binocular look at A's true place, attributed to A by continuity when the
gap is inside OBJECT_ID_MEMORY_S, else by "lies inside A's area" (gate).
"""

from __future__ import annotations

import copy
import math
import sys

sys.path.insert(0, "tools")
import measure_same_group_fold as h  # noqa: E402

from belief.association_over_time import (  # noqa: E402
    _contact_covariance,
    contacts_plausibly_same,
    passes_gate,
)
from belief.callouts import _is_merge_echo_of_earlier_contact  # noqa: E402
from belief.contacts import Contact, ContactStore  # noqa: E402
from belief.decay import OBJECT_ID_MEMORY_S, certainty_of  # noqa: E402
from belief.optic_policy import LOOK_SWEEP_SIGMA  # noqa: E402
from belief.percept import percept_of  # noqa: E402
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC  # noqa: E402

MAX_HW_DEG = 15.0
PAIRS = {
    "u_u": (UNAIDED_OPTIC, UNAIDED_OPTIC),
    "b_b": (BINOCULAR_OPTIC, BINOCULAR_OPTIC),
    "u_b": (UNAIDED_OPTIC, BINOCULAR_OPTIC),
    "b_u": (BINOCULAR_OPTIC, UNAIDED_OPTIC),
}


def bucket(x: float, z: float) -> float:
    return round(math.hypot(x, z) / 500.0) * 0.5


def trial(pair, za, zb, gap, cls, i, salt, alt, surface, same):
    o1, o2 = PAIRS[pair]
    h._fresh_realisation(f"{salt}-{i}")
    t1 = i * 1e-3
    t2 = t1 + gap
    store = ContactStore()
    store.ingest(
        [h._observation(observation_id=f"first-{i}", t_sim=t1, ownship=h._ownship(t1, alt),
                        group_z=za, bias_object_id=1, optic=o1, classification_raw=cls,
                        surface=surface)], t1)
    store.tick(t1)
    a0 = copy.deepcopy(store.contacts[0])
    ob = h._observation(observation_id=f"second-{i}", t_sim=t2, ownship=h._ownship(t2, alt),
                        group_z=zb, bias_object_id=2, optic=o2, classification_raw=cls,
                        surface=surface)
    pb = percept_of(ob)
    store.ingest([ob], t2)
    store.tick(t2)
    contacts = store.contacts
    folded = len(contacts) == 1
    if folded:
        b = Contact.from_percept("B", pb)
        echo = False
        lost = certainty_of(a0, t2) == "lost"
        plaus = True
    else:
        b = next(c for c in contacts if c.id != a0.id)
        a_now = next(c for c in contacts if c.id == a0.id)
        echo = _is_merge_echo_of_earlier_contact(b, store, t2)
        lost = certainty_of(a_now, t2) == "lost"
        plaus = contacts_plausibly_same(b, a_now, t2)
    today_heard = (not folded) and (not echo)
    trigger = folded or plaus
    cov = _contact_covariance(a0, max(0.0, t2 - a0.last_seen_sim))
    rng = math.hypot(a0.position.x, a0.position.z)
    hw = math.degrees(math.atan(LOOK_SWEEP_SIGMA * math.sqrt(max(cov.xx, 0.0)) / rng))
    can_look = hw <= MAX_HW_DEG
    t3 = t2 + 3.0
    ol = h._observation(observation_id=f"look-{i}", t_sim=t3, ownship=h._ownship(t3, alt),
                        group_z=za, bias_object_id=1, optic=BINOCULAR_OPTIC,
                        classification_raw=cls, surface=surface)
    in_a_area = passes_gate(percept_of(ol), a0, t3)
    if same:
        a_observed = False  # one cluster, B's own units (continuity onto B)
        naive_a_observed = in_a_area  # "something seen in A's area"
    else:
        a_observed = gap <= OBJECT_ID_MEMORY_S or in_a_area
        naive_a_observed = a_observed
    # relocation line: spoken range bucket before vs after folding B into A
    fused = copy.deepcopy(a0)
    fused.record(pb)
    moved_line = bucket(a0.position.x, a0.position.z) != bucket(fused.position.x, fused.position.z)
    moved_far = moved_line and abs(
        math.hypot(fused.position.x, fused.position.z) - math.hypot(a0.position.x, a0.position.z)
    ) >= 500.0
    if not trigger:
        new_heard = today_heard
        merged = False
    elif can_look and a_observed:
        new_heard = True
        merged = False
    elif can_look:
        new_heard = False
        merged = True
    else:  # cannot look
        merged = False
        if folded:
            new_heard = True  # Q3: B called new
        elif echo:
            new_heard = False  # BL-B114 keeps cannot-look
        else:
            new_heard = True
    return dict(folded=folded, echo=echo, lost=lost, trigger=trigger, can_look=can_look,
                hw=hw, today=today_heard, new=new_heard, merged=merged,
                moved=merged and moved_line, moved2=merged and moved_far, naive=trigger and can_look and naive_a_observed)


def cell(pair, za, zb, gap, cls, n, same, alt=500.0, surface=False):
    rs = [trial(pair, za, zb, gap, cls, i, f"{pair}{za}{zb}{gap}{cls}{same}", alt, surface, same)
          for i in range(n)]
    f = lambda k: 100.0 * sum(1 for r in rs if r[k]) / n  # noqa: E731
    return {k: f(k) for k in ("folded", "echo", "trigger", "can_look", "today", "new", "moved", "moved2", "naive")}


def main():
    n_diff = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    n_same = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    print("== DIFFERENT groups: % B announced (today -> with look); trig, canlook")
    for cls in ("s-125", "OP_ARMORED"):
        for gap in (6.0, 700.0):
            for pair in PAIRS:
                for far, near in ((4.5, 3.0), (5.0, 3.5), (3.0, 1.5)):
                    for label, za, zb in (("Bnear", -far * 1000, -near * 1000),
                                          ("Bfar", -near * 1000, -far * 1000)):
                        r = cell(pair, za, zb, gap, cls, n_diff, False)
                        print(f"{cls:10s} gap{gap:5.0f} {pair} {far}/{near} {label:5s} "
                              f"heard {r['today']:5.1f} -> {r['new']:5.1f}  "
                              f"trig {r['trigger']:5.1f} canlook {r['can_look']:5.1f}")
    print("== SAME group: % duplicate heard (today -> with look); moved line; naive-rule false 'different'")
    for cls in ("s-125", "OP_ARMORED"):
        for gap in (6.0, 700.0):
            for pair in PAIRS:
                for rk in (2.0, 3.0, 4.5):
                    r = cell(pair, -rk * 1000, -rk * 1000, gap, cls, n_same, True)
                    print(f"{cls:10s} gap{gap:5.0f} {pair} {rk} "
                          f"dup {r['today']:5.1f} -> {r['new']:5.1f}  moved {r['moved']:5.1f}/{r['moved2']:4.1f} "
                          f"naive {r['naive']:5.1f} trig {r['trigger']:5.1f} canlook {r['can_look']:5.1f}")
    print("== ground cells (100 m AGL, s-125)")
    for gap in (6.0, 700.0):
        for pair in ("u_u", "b_u"):
            r = cell(pair, -4500, -3000, gap, "s-125", n_diff, False, alt=100.0, surface=True)
            print(f"ground diff gap{gap:5.0f} {pair} 4.5/3.0 heard {r['today']:5.1f} -> {r['new']:5.1f}")
            r = cell(pair, -3000, -3000, gap, "s-125", n_same, True, alt=100.0, surface=True)
            print(f"ground same gap{gap:5.0f} {pair} 3.0 dup {r['today']:5.1f} -> {r['new']:5.1f} "
                  f"moved {r['moved']:5.1f}/{r['moved2']:4.1f} naive {r['naive']:5.1f}")
    h._restore_field_salt()


if __name__ == "__main__":
    main()
