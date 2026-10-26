---
name: project-lua-loop-body-limits-split
description: BL-16 pattern: per-frame Lua loop owns gains; body-layer owns behaviour limits and sends them in each goal message; mode flags are decide() inputs, not OpticState fields
metadata:
  type: project
---

Two design moves from the BL-16 flight-control plan (`plans/flight-control/plan.md`, 2026-10-26)
worth reusing for any future per-frame Export.lua loop (9K113 servo is the precedent):

1. **Split constants by "what he does" vs "how the loop closes".** Behaviour limits (max bank,
   VS, floor AGL, min IAS) are body-layer `tuning.py` constants sent in every goal message, so
   X-T26 tuning still applies; loop gains/jerk limits/dither stay in one commented Lua block
   (no tuning mechanism outside body-layer). Lua bounds-checks received limits against its own
   hard ceilings.
2. **A mode that suppresses optics (flying, hands busy) is better as a `decide()` input derived
   per poll than as an `OpticState` field.** `OpticState` is constructed fresh at several sites
   (~2689, ~2768 in optic_policy.py) and fields silently fail to carry across those (BL-B71's
   miss). An input has no construction sites to drop it.

**Why:** both avoid the project's recurring "state that should carry and doesn't" defect
([[project_recurring_stale_state_on_transition]]) and keep one source of truth for behaviour.
**How to apply:** when a plan adds a Lua-side loop or a new optic-suppressing mode, state the
split and the derive-not-store choice explicitly in Affected Files and Co-moving Fields.
