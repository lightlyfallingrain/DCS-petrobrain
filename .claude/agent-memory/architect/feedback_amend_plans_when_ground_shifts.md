---
name: amend-plans-when-ground-shifts
description: When a merged milestone invalidates an assumption in an unimplemented plan, amend that plan in place and say what forced the amendment
metadata:
  type: feedback
---

When a merged change invalidates an assumption an *unimplemented* plan rests on, amend that plan in
place — and record, in the amendment itself, that it was forced by the other change rather than by
a review of the plan's own reasoning.

**Why:** plans in this repo are a decision log read months later. An amendment with no cause
attached reads as the original author having been careless; with the cause attached it reads as the
system working. The concrete case (2026-09-24): `precise-position-belief` merged and turned
`Contact.last_position` from ~500 m quantised buckets into a continuously fused estimate with
per-look noise, which invalidated `plans/watch-reporting/plan.md` Decision 5's bare
`floor(range / 1000)` kilometre trigger.

**How to apply:**

- Amend in place with a numbered sub-decision (`5a`) that explicitly supersedes the bullet it
  replaces, rather than rewriting the original — the superseded text is evidence.
- Update the affected **stage** and **risk** bullets too, not only the decision. A risk entry that
  now describes designed-in behaviour should say "superseded by <n>", not be deleted.
- **Look for an existing pattern on the branch before designing a damper.** This repo already has
  two and wants no third: Decision 4e's Schmitt trigger (1.5× enter/leave deadband) and
  `belief.motion.fold_motion`'s asymmetric confirm-window (`MOTION_STOP_CONFIRM_S` +
  `pending_*_since_sim`).
- **Prefer a deadband derived from the belief's own uncertainty over a tuned constant.** For the
  kilometre trigger the deadband became `PositionEstimate.range_uncertainty_m` (the down-range
  mirror of the existing `bearing_uncertainty_deg`), floored and ceilinged. No calibration sortie,
  and it tracks the position model's own constants automatically.
