---
name: pb2-stage1-belief-core
description: PB-2 Stage 1 (belief/association_over_time.py, belief/contacts.py) design choices and a circular-import/fixture-geometry gotcha for Stage 2+.
metadata:
  type: project
---

PB-2 Stage 1 (`plans/pb2-contact-memory/plan.md`) added `belief/association_over_time.py`
(percept->contact gating) and `belief/contacts.py` (`Contact`/`SightingSpan`/`ContactStore`).

**Circular import between the two belief modules.** `association_over_time.py` needs `Contact`
for type hints; `contacts.py` needs `association_over_time`'s gate functions at runtime. Broken
with `if TYPE_CHECKING: from belief.contacts import Contact` in `association_over_time.py`,
relying on `from __future__ import annotations` (already this codebase's convention) so the
forward reference never resolves at import time. Any future `belief/` module pair with a similar
mutual dependency should use the same pattern rather than merging the modules.

**Reused `perception.naked_eye_source`'s private `_CLOCK_BUCKET_DEG`/`_RANGE_BUCKETS_M`
directly** (underscore-prefixed, module-private by convention) instead of duplicating the
numbers — the plan explicitly says "reuse those, don't invent new numbers," and duplicating
would create silent-drift risk if the tables ever diverge. Also reused `object_model.profile_for`
(substring match against `classification_raw`) for cross-channel class resolution instead of a
second keyword table — deliberately weak on unmatched free text (resolves to `unknown`, not a
guess), contained by the three-valued gate.

**Fixture-geometry gotcha for ambiguous-merge tests.** To prove "two candidates both pass the
gate -> new contact, never a merge," the two existing contacts must be far enough apart that the
*second* doesn't merge into the *first* when both are created in the same `ingest()` call
(processed sequentially), but close enough that a later percept between them falls within both
gates. Got this wrong once with 50m separation (well inside the 300m fixed scope-channel gate)
before widening to 400m apart / 200m from each. Relevant to [[decouple_fixtures_from_tuned_defaults]]
territory — the gate radius has real-ish tuned constants (`SCOPE_UNCERTAINTY_M=300.0`,
`GATE_GROWTH_RATE_MPS=20.0`), and fixture geometry must be built with margin against them, not
just barely inside/outside.

Placeholder constants explicitly flagged for later tuning (per the plan, not a TODO to chase now):
`SCOPE_UNCERTAINTY_M = 300.0` (flat, range-independent — scope channel has no bucket structure),
`GATE_GROWTH_RATE_MPS = 20.0` (72 km/h generic ground-vehicle order-of-magnitude guess).
