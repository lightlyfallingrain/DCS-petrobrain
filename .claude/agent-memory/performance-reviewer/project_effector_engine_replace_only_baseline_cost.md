---
name: effector-engine-replace-only-baseline-cost
description: BL-B119 (2026-11-16) — effector_engine.advance already rebuilds 4+ containers and a new frozen EffectorRunState every poll (idle or not); a small added field there is marginal, not a new cost class.
metadata:
  type: project
---

`belief/effector_engine.py::advance` is called unconditionally once per poll by `body.py`
(`advance_effectors`), at body-layer's ~1 Hz default poll rate
([[body-layer-poll-loop-diagnosis]]). It already copies `runs`/`pending`/`commanded_values`/
`assumed_writes` into fresh dicts and returns a brand-new `EffectorRunState` via `dataclasses.
replace(...)` on **every single call**, including the fully-idle case (no trigger running) — this
is the module's own documented discipline ("the same `replace()`-only discipline as every other
field here"), not something any one feature adds.

**Why this matters for review:** when a plan adds one more small field to `EffectorRunState`
(BL-B119 added `spoken: tuple[str, ...]`, a per-poll completed-row-lines list), the marginal cost
is one small list + its `tuple()` conversion — negligible against the four dict copies and dataclass
rebuild that already happen every poll regardless. Don't flag the container rebuild itself as new
risk introduced by the feature under review; it is baseline cost for this module, established by
`BL-B90`. Only flag growth that scales with something unbounded (sequence row count growing large,
e.g.), not the fixed per-poll rebuild.

**How to apply:** before calling a per-poll allocation in `effector_engine.py`/`crew_console.py`'s
`drain_*` methods a regression, check whether the surrounding function already rebuilds comparable
containers every poll unconditionally — if so, the new allocation is marginal, not a new hot-path
class, and the verdict is MONITOR rather than NOW.
