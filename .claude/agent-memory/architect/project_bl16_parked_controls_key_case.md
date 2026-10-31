---
name: project-bl16-parked-controls-key-case
description: BL-16's key case is Petrobrain overpowering ED's AI pilot in the parked-controls state (player on the 9K113); steering ED's AI is rejected; tests assert ±10% band convergence, never tight tracking
metadata:
  type: project
---

BL-16 (Petrovich flies) has two control states, both must-haves (user, 2026-10-31): **unparked**
(player's stick must be ignored) and **parked** (player in the copilot seat on the 9K113 with
"park controls" selected; DCS then hands the aircraft to ED's AI pilot, which must be overpowered).
The user's lead hypothesis is the 9K113 precedent: per-frame axis writes that win. **Steering ED's
AI (giving it a heading/altitude) is rejected outright** — *"DCS AI flies hoorribly. That is *the*
reason I want Petrobrain to replace it."* ED-AI commands are of interest only as off-switches.

Also from the same goal check: targets are held within about ±10%, always converging; smoothness
beats exactness. No test (offline or flight) asserts tight tracking.

**Why:** the first reading of "player in the copilot seat" planned around ignoring the front-seat
stick; the real mechanism (parking) came from the user only after the goal check, and would have
made the plan's central gate the wrong question.

**How to apply:** any plan touching flight control, the 9K113 while Petrovich flies, or seat
changes: ask which control state applies before designing; a parked-state failure is a blocker to
report, never a scope cut. Plan: `plans/flight-control/plan.md`, Decisions 16, 18, 20. Related:
[[project-petrovich-operates-opposite-seat]].
