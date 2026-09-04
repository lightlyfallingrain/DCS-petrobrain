---
name: feedback_respect_instructed_caps_over_recomputed_margins
description: When a task instruction caps a parameter (e.g. "0 to +3km") but your own recomputation shows a wider safe margin, stay within the instructed cap and just record the discrepancy
metadata:
  type: feedback
---

M5 Stage 0 (2026-09-04): the plan estimated Jablah drops out of the Latakia region box beyond
roughly +3 km of eastward offset. Recomputing from `towns.lua`'s full-precision lat/lon (not the
plan's rounded values) showed the real threshold is closer to +5,941 m — the plan's number was
conservative. The task/checklist still capped the offset at 0–+3 km explicitly.

**Why:** the cap in checklist/plan.md is an instruction from the architect role, not a derived
safety limit that recomputation can supersede. Exploiting a wider margin discovered mid-task would
be silently reopening a locked decision layer (region/offset selection is called out as "closed,
zero open items" in the checklist header).

**How to apply:** when your own math shows more headroom than an instructed cap allows, take the
cap's maximum (here: +3,000 m, "trade the most sea for land within the mandated band") and record
the discrepancy in the research note/implementation log as a finding for a future session to
revisit — do not silently use the wider number, and do not silently stay conservative either
without explaining why you didn't take the full instructed allowance.
