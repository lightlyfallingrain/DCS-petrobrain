---
name: project_bl_b80_ready_callout_not_an_edge
description: Merged BL-B80 v2 speaks "Guidance unit ready" on the first lit 960 sample (once per mission), not on an observed off->on edge -- so it speaks at an air start, contrary to BL-B80 decision 2. Found 2026-10-23 while re-planning BL-B90.
metadata:
  type: project
---

At `147a057d` (2026-10-23), `logger.py` calls `crew_console.drain_guidance_unit_ready(ready=sight_ready(state), announced=...)`, which speaks whenever `ready and not announced`. `ready_observed` goes None -> True on an air start's first `cockpit_switch` sample, so he says it at spawn. The latch never re-arms, so power-down/re-power never re-announces. BL-B80 plan decision 2 (user: *"only on change"*) wanted silent air starts. No test covers the air-start case.

**Why:** a plan or brief said "spoken on the off->on edge", and that was the intent, not the code. Same failure class as [[feedback_verify_state_not_the_account_of_it]].

**How to apply:** before planning around any "spoken on edge / once" claim, read the drain function and its caller, and check whether a None->True first sample counts as an edge. BL-B90 plan D4 makes it a true edge (prior observed False). If you are revisiting either feature, check whether that fix has landed.
