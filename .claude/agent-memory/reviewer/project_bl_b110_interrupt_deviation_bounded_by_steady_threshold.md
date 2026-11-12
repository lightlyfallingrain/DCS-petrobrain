---
name: bl-b110-interrupt-deviation-bounded-by-steady-threshold
description: how to judge a "deviation from the Co-moving Fields table" claim -- check the actual gating threshold, not just the stated trigger name
metadata:
  type: project
---

`BL-B110`'s Stage 1 implementation (`plans/expected-area-check/plan.md`, `optic_policy.py`) stated
a deviation: interrupting `GLASSING` (via `lower_binoculars` or `not steady`) does not advance the
sector or roll the glass-budget window, unlike the plan's Co-moving Fields table. The implementer's
own framing called this "pilot-driven and rare" — but `not steady` is airframe-dynamics-driven, not
pilot-command-driven, so that framing undersold one of the two triggers.

**How this was actually judged safe**: `is_steady`'s threshold (`STEADY_RATE_LIMIT_DEG_S` = 12°/s)
was checked against the plan's own stated body-rotation rates for the normal flight profile the
feature targets (0.5–3°/s for circling/sidestepping at ~28 m/s). The gap between those numbers (12
vs. 0.5–3) is what makes the deviation genuinely rare in practice, not the "pilot-driven" framing.
**Lesson: when a deviation note says a trigger is "rare" or "pilot-driven," check the actual
threshold constant against the plan's own stated normal-operating numbers before accepting the
claim** — the two can disagree even when the deviation is, in the end, still acceptable.

See `plans/expected-area-check/review.md` finding 1 for the full writeup.
