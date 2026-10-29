---
name: project-urgent-path-and-fov-channels
description: "Urgent passes" in a plan must name event kinds — bypass_gate=True has no live producer (only !inject-urgent); and the HelperAI hybrid channel is the one perception path NOT gaze/FOV-gated
metadata:
  type: project
---

Two facts checked 2026-10-29 for BL-B67's in-flight silence (`plans/bl-b67-atgm-run/plan.md`,
"Silence while the missile flies"), both of which an earlier pass of that same plan got wrong:

1. **`bypass_gate=True` / `UrgentCall` has no live producer.** The only construction is
   `crew_console._handle_inject_urgent` (the `!inject-urgent` test harness). Real threats ("Taking
   fire", "Something firing") are ordinary `CONTACT_FIRING_SEEN` events ranked by
   `callouts._FIRING_TARGETS_OWNSHIP_THREAT_BAND`/`_FIRING_THREAT_BAND`.
   **Why:** the first BL-B67 plan said "urgent threat callouts (`bypass_gate`) still pass" — a
   rule that would have let nothing real through.
   **How to apply:** whenever a plan holds speech and lets "urgent" through, define the pass set by
   event kind (+ `targets_ownship`), and grep `UrgentCall(` before citing `bypass_gate`.

2. **Which channels respect the current optic's FOV.** `check_visibility`'s emitter bypass lifts
   only gates 3 (range/size) and 5 (forest); gaze, cockpit mask, optic FOV and terrain LOS always
   apply — so firing/burning emitters are FOV-gated. **`HybridPerceptionSource` (HelperAI
   `list_indication`) is not gaze- or FOV-gated at all** (forward hemisphere, ≤5 km), and it runs
   every poll beside the naked-eye source.
   **Why:** the user's rule (2026-10-29) is that on the sight Petrovich only sees what the sight's
   field admits; the hybrid channel is the standing exception, pre-existing, raised as BL-B67
   Decision N3.
   **How to apply:** any plan that reasons "he can only see X while looking through Y" must say what
   it does about the hybrid channel.
