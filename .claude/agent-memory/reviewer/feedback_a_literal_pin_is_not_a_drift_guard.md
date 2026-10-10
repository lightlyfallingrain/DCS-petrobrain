---
name: a-literal-pin-is-not-a-drift-guard
description: A test asserting a constant equals a literal is a change detector; it cannot notice the other module growing. Ask who guards the constant, not what it holds.
metadata:
  type: feedback
---

When a diff makes a hand-authored constant load-bearing for a new code path, do not check the
constant's membership — check what would fail if the *other* module grew.

**Why:** found 2026-10-10 on `BL-B47`. `belief.groups.AIR_DEFENSE_OP_CLASSES` is pinned by
`assert AIR_DEFENSE_OP_CLASSES == frozenset({...five literals...})`, which looks like coverage and
is a change detector: it goes red when *this* set changes and can never go red when
`perception.object_model` gains a new air-defence class. A sibling copy of the same set in
`crew_console.py` has the real guard — `air_defence_by_name <= _AIR_DEFENCE_OP_CLASSES`, derived
from both of `object_model`'s keyword tables by naming heuristic. Injecting a fake `OP_XLRSAM`
profile turns the `crew_console` test red and leaves the literal pin green. This is not academic:
the same drift silently cost `OP_LRSAM` months of coverage in the `crew_console` copy before that
guard existed, so "watch nearest air defence" could not select an S-300 — the one emitter the
vision calibration found visible to 8.89 km.

**How to apply:** whenever a review touches a hand-enumerated vocabulary set (op-class buckets,
descriptor words, keyword tables, exemption lists), find its test and classify it:

- `== frozenset({literals})` → change detector. Says nothing about drift from the source of truth.
- `derived_from_other_module <= THE_SET` → real guard.

Then mutate the *source* module, not the set, and confirm something goes red. If nothing does,
the set has no mechanism to notice the thing it was enumerated against growing — say so, and size
it by whether the diff increased what depends on the set. Multiple copies of one set are worth
flagging mainly because they can disagree about which of them is guarded.

Related: [[project_bl_b47_air_defence_class_level_review]].
