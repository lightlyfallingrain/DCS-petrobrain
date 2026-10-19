---
name: project_plan_named_doc_step_can_be_dropped_silently
description: a plan's own numbered Implementation Plan step naming a documentation deliverable (a WORKFLOW.md deploy section) can be silently absent from the implemented diff even after three Reviewer-approved batches -- check the plan's own step list against what actually landed, don't rely on Reviewer having done it
metadata:
  type: project
---

`plans/bl15-mission-start/plan.md`'s Implementation Plan step 4 named, explicitly, "update
`aircraft-layer/WORKFLOW.md`" (the new Hook script's deploy section) as part of that stage. Three
Reviewer passes (`review.md`, Batches 1-3) all APPROVED the implementation, and none of them
flagged that this specific sentence of step 4 was never done — Reviewer's own scope was the code
and tests each batch actually touched, not a line-by-line diff against the plan's own numbered
steps. `grep -n "mission-start\|mission_start" aircraft-layer/WORKFLOW.md` before this DoD pass
returned nothing.

**Why this is a DoD-shaped check, not a Reviewer-shaped one**: Reviewer reviews what was built
against the plan's *design* (does the code do what the plan says); it is not naturally scoped to
re-read the plan's own step list and confirm every named deliverable has a corresponding file
change, especially a purely-documentation one with no code to review. Three clean Reviewer passes
is exactly the condition under which this kind of gap survives unnoticed — nobody's job was "diff
the plan's own checklist against `git diff --name-only`."

**How to apply**: before writing the DoD report, re-read the plan's own "Implementation Plan"
section as a checklist, not just its headline decisions, and grep for each named deliverable
(a doc section, a CLI flag, a specific file) in the actual diff. A plan step that says "and update
X" is exactly as binding as one that says "implement Y" — Reviewer approving the stage does not
mean every sentence of that stage's plan step was checked off.

**What to do about a gap like this at DoD, if it's small**: a pure-documentation addition with no
design content (mirroring an existing, already-reviewed section exactly) can be written directly
by DoD rather than looped back through Implementer → Reviewer for a one-section mirror — this is a
judgment call, not a rule; a gap with any actual design content still goes back through the normal
loop.
