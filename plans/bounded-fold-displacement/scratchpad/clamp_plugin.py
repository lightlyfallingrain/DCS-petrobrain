"""A pytest plugin that installs the proposed bound into the real fold
branch for the whole session, so the existing suite can be run against it
without editing `src/`.

This is the measurement that says which pinned tests the bound moves.
`PB_CLAMP_K` selects the multiplier (default 1.0); `PB_CLAMP_K=off`
disables it, for a control run.

Run from `body-layer/`:
  PB_CLAMP_K=1 /Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python -m pytest \
      -p clamp_plugin -q tests/ \
      --rootdir . -p no:cacheprovider
with `PYTHONPATH` including this scratchpad directory.
"""

from __future__ import annotations

import dataclasses
import math
import os

from belief import contacts as C
from belief.association_over_time import contact_growth_rate_mps

_K = os.environ.get("PB_CLAMP_K", "1.0")
_ORIG_FOLD_TARGET = C.ContactStore._fold_target_for_ambiguous_candidates
_ORIG_RECORD = C.Contact.record
_PENDING: dict[str, str | None] = {}


def pytest_configure(config) -> None:  # noqa: ANN001, ARG001
    if _K == "off":
        return
    k = float(_K)

    def fold_target(self, passing, percept):  # noqa: ANN001, ANN202
        target = _ORIG_FOLD_TARGET(self, passing, percept)
        _PENDING["target"] = None if target is None else target.id
        return target

    def record(self, percept) -> None:  # noqa: ANN001
        is_fold = _PENDING.pop("target", None) == self.id
        prior = self.position
        _ORIG_RECORD(self, percept)
        if not is_fold:
            return
        dx = self.position.x - prior.x
        dz = self.position.z - prior.z
        moved = math.hypot(dx, dz)
        bound = (
            k
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
