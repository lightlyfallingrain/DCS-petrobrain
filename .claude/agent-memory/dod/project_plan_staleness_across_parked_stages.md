---
name: plan-staleness-across-parked-stages
description: A plan's later stages can go stale when an earlier stage's mechanism is redesigned while those later stages sit parked
metadata:
  type: project
---

`terrain-feature-probing` (DoD'd 2026-10-05, Stages 3a-5, Revision 3): Stages 3-5's original
design assumed basin adjacency "comes free" from Stage 1-2's marker-controlled watershed detector.
That detector was abandoned for geomorphons (`WM-B6`) before Stages 3-5 were ever built —
geomorphons produces traced lines, not basins — so the parked design was silently wrong by the time
anyone picked it back up. Caught by the Architect/plan-author rechecking the dependency before
resuming, not by Reviewer or DoD.

**Not yet called "recurring"** — this is the first instance of this specific shape (stale
dependency across a parked later stage) in this memory, distinct from
[[project_recurring_approved_plan_wrong_on_real_data]] (which is "design correct-as-written, wrong
against real data/scale," not "design assumes a mechanism that no longer exists"). Worth watching:
if a second plan is found resting on a since-replaced earlier-stage mechanism, that is a signal for
Architect to check a parked plan's dependencies before un-parking it, not just re-read the plan
text.

See NOTES.md's `terrain-feature-probing` entry (added 2026-10-05) for the worked example.
