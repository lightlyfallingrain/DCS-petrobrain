---
name: project_bl26_dual_field_pattern
description: Contact carries both last_class_raw (gate input, unconditional overwrite) and classification (folded best claim, user-facing) — intentional dual field, not drift
metadata:
  type: project
---

BL-2.6 (2026-09-09, `plans/classification-refinement/plan.md` §3) deliberately kept two fields on
`Contact` that look redundant: `last_class_raw` (most recent percept's raw string, unconditionally
overwritten every `record()`, feeds only `association_over_time`'s gate) and `classification`
(the folded, monotone-non-decreasing best claim, everything user-facing reads this —
`tools.py`/`console.py`/events). The plan itself flags this as "a real readability cost" in both
modules' docstrings, not an oversight.

**Why:** feeding the gate the folded/held value instead of the raw value would make the gate
progressively stricter over a contact's life and could start rejecting genuine re-observations of
a contact whose type was refined once.

**How to apply when reviewing future stages that touch `Contact`:** if a stage's diff makes
`tools.py`/`console.py`/events read `last_class_raw` again, or makes the association gate read
`classification`, that is scope drift/a regression, not a refactor — flag it. If a new field is
added that also looks like it duplicates `last_class_raw`'s job, check whether it's actually a
third distinct concern before calling it duplication.

See also [[project_pb2_stage5_fusion_finding]] — the last-writer-wins finding this milestone closes
for `classification` (but not for `last_class_raw`, which is *supposed* to stay last-writer-wins).
