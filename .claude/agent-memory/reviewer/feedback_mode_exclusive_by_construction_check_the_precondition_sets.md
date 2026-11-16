---
name: mode-exclusive-by-construction-check-the-precondition-sets
description: a plan's "X and Y are mode-exclusive by construction, so no arbitration is needed" claim must be checked by diffing each command's own precondition set, not accepted on the strength of the underlying device having one mode at a time
metadata:
  type: feedback
---

BL-16 Stage P2's plan argued `AiPilotWheelGoal.active_param` (FLT/HVR heading/altitude/speed
goals) and `.hvrt_direction` (HVRT translate) are "mode-exclusive by construction (a wheel cannot
be in `HVRT` and `FLT`/`HVR` at once), so there is no collision to arbitrate between the two being
set at the same time." True of the underlying DCS device (one AI-pilot mode at a time) — false of
the two *command channels* built on top of it: `ai_pilot_goal_mode_ready` accepts `"FLT"` or
`"HVR"`, and the HVRT precondition (`crew_console._ai_pilot_hvrt_ready`) accepts `"HVR"` or
`"HVRT"`. `HVR` is in both sets. A player hovering can set an active FLT/HVR goal, then say an
HVRT bare word (or the reverse order) — both channels now have live state on the same
`AiPilotWheelGoal`, nothing clears either side, and their per-tick Lua presses can land on the
same physical button code (the mode-cycle tap and a translate hold both use `AI_WHEEL_LEFT`).

**Why this is easy to miss**: "mode-exclusive by construction" is true at the device level and
reads as a complete argument — the reviewer has to notice it is being used to justify a *command*-
level claim, which is a different, narrower statement that needs its own check. The underlying
device having one state at a time says nothing about whether the command surfaces built on top of
it have been given disjoint reachability conditions.

**How to apply**: whenever a plan or implementation argues two channels "can't both be active
because X is mode-exclusive," write out each channel's own precondition/gate set explicitly (grep
every `if ai_mode ==`/`in (...)` check feeding into it) and check the sets for overlap, rather than
trusting the device-level mode-exclusivity to carry over. An overlap in the *gates* means an
overlap in *reachability*, regardless of what the underlying device can represent at once. If an
overlap exists, check whether setting one side clears the other — if neither does, that is the
collision the plan claimed didn't exist.
