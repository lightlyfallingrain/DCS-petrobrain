---
name: overlay-clock-range-summary
description: Threading relative_now into _contact_summary; float rounding gotcha for km display
metadata:
  type: project
---

Implemented (2026-09-10, `plans/overlay-clock-range-summary/plan.md`): `_contact_summary` gained
an optional `relative_now: dict[str, object] | None` param, appending `", <clock> o'clock,
<range> km."` after the existing classification/certainty/recency/watched text. `_contact_result`
now builds `facts` first, then passes `facts.get("relative_now")` in — reuses the one
`relative_geometry()` call `_add_enrichment_facts` already made, no second computation.
`console.format_event_for_overlay` needed zero code change (confirmed with a real integration
test, not just trusted prose) since it already reads `summary` verbatim — this is the "one
summary field" seam paying off exactly as designed.

**Float rounding gotcha**: `3050.0 / 1000 == 3.0499999999999998` in IEEE-754, so
`f"{...:.1f}"` rounds *down* to `"3.0 km"` not up — don't pick round-number-times-50 values for
km-rounding test assertions, use unambiguous ones (e.g. 3040/3060).
