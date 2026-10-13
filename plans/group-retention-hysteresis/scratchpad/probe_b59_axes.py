"""BL-B59 probe 0: which observation axis drives `Contact.position`, and
which drives gate matching -- established by experiment rather than read
off a docstring, because probe 3's first draft founded a new contact every
tick and the two axes are easy to confuse.

Run from `body-layer/`:
  ../../body-layer/.venv/bin/python \
      ../plans/group-retention-hysteresis/scratchpad/probe_b59_axes.py
"""

from __future__ import annotations

import itertools
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "../world-model/src")
sys.path.insert(0, "tests")

import test_callouts as tc  # noqa: E402
from belief.contacts import ContactStore  # noqa: E402


class _MP:
    def setattr(self, *a, **k):  # noqa: ANN002, ANN003
        import unittest.mock as m

        m.patch.object(*a, **k).start()


_seq = itertools.count(1)


def obs(x, z, t, dwp_x, dwp_z=0.0):  # noqa: ANN001, ANN201
    return tc._observation(
        obs_id=f"OBS_{next(_seq)}",
        t_sim=t,
        classification_raw="BTR-70",
        classification_level=3,
        ownship_x=x,
        ownship_z=z,
        dwp_x=dwp_x,
        dwp_z=dwp_z,
    )


def show(store, label):  # noqa: ANN001, ANN201
    print(f"  {label}")
    for c in store.contacts:
        print(
            f"    {c.id}: position=({c.position.x:.1f}, {c.position.z:.1f}) "
            f"fold={c.fold_displacement_m:.1f}"
        )


def main() -> None:
    tc._enrichment_context(_MP())

    print("A) move ownship_x only, dwp_x fixed at 10000:")
    s = ContactStore()
    for t in (0.0, 1.0, 2.0):
        s.ingest([obs(100.0 * t, 0.0, t, 10000.0)], now_sim=t)
        s.tick(now_sim=t)
        show(s, f"t={t}  ownship_x={100.0 * t}")

    print("\nB) move dwp_x only, ownship_x fixed at 0:")
    s = ContactStore()
    for t in (0.0, 1.0, 2.0):
        s.ingest([obs(0.0, 0.0, t, 10000.0 + 100.0 * t)], now_sim=t)
        s.tick(now_sim=t)
        show(s, f"t={t}  dwp_x={10000.0 + 100.0 * t}")

    print("\nC) two tracks, same dwp_z lane, 200 m apart in ownship_x:")
    s = ContactStore()
    for t in (0.0, 1.0, 2.0):
        s.ingest(
            [obs(0.0, 0.0, t, 10000.0), obs(200.0, 0.0, t, 20000.0)], now_sim=t
        )
        s.tick(now_sim=t)
        show(s, f"t={t}")


main()
