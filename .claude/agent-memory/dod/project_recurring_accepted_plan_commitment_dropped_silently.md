---
name: project_recurring_accepted_plan_commitment_dropped_silently
description: an explicit plan commitment (a named doc-update step, or a user-accepted recommendation with a stage number attached) survives multiple Reviewer-approved passes unimplemented, caught only when a later-stage role actually diffs the commitment against the real code -- second occurrence, now a pattern worth checking for at DoD before trusting an implementation log's own stage-boundary claim
metadata:
  type: project
---

Two independent occurrences of the same shape, different mechanism:

1. **`plans/bl15-mission-start/plan.md` step 4** named a documentation deliverable
   (`aircraft-layer/WORKFLOW.md`'s deploy section) explicitly. Three Reviewer-approved batches all
   passed with that sentence of the plan simply never done — Reviewer's scope was "does the code do
   what the plan says," not "re-read the plan's own numbered checklist and confirm every named
   deliverable landed." Caught at DoD by grepping the plan's own step list against the diff
   (`project_plan_named_doc_step_can_be_dropped_silently`).

2. **BR-2's U4** ("fold `[[BR-B2]]`/`[[BR-B3]]`'s fixes into Stage 2") was accepted by the user
   verbatim ("1,2,4 - as recommended"). Stage 0's implementation log correctly deferred it with a
   stage number attached ("out of scope for Stage 0... folding into Stage 2 is U4"). Stage 2's own
   implementation log and Files Changed list then made **no mention of it at all**, and a full
   NEEDS-REVISION review round passed without raising it either. Caught only by Security's deep
   analysis, which read the two actual call sites directly (`server.py`'s still-unguarded
   `Content-Length`, `ollama_client.py`'s still-uncapped `response.read()`) rather than trusting
   that an accepted "yes" plus a stage-numbered deferral note meant a diff existed
   (`plans/brain-tool-calls/security-review.md`).

**The shared mechanism**: a plan or a deferral note names *which stage* a commitment will land in.
Every review pass at or after that stage reads the implementation log's account of what that stage
did, and the account's own silence about the commitment is mistaken for "nothing to check" rather
than "unverified." Nobody's job, by default, is to re-derive the commitment list independently and
grep for each one in the real diff — Reviewer scopes to "does the built code match the plan's
design," which a dropped side-commitment with no design content doesn't visibly violate.

**How to apply at DoD**: before writing the DoD report, build an explicit checklist from two
sources — the plan's own numbered "Implementation Plan"/"Decisions" sections (every named
deliverable, not just the headline design), and any user-accepted recommendation that carries a
stage number ("fold into Stage N", "do this when X ships"). Grep each item against the actual diff
by name (a file, a function, a constant, a backlog ID's resolution line) rather than trusting the
implementation log's own account that the stage "did" it. Two occurrences in two different feature
families (a documentation step; a security backlog fold) is enough to treat this as a standing
check, not a one-off miss — and it is cheap: the grep that would have caught either case is a few
seconds once you know what to look for.

See also `[[feedback_execute_the_unblock_condition_of_accepted_debt]]` (a related but distinct
shape: there the unblock *condition* existed but had never been run; here the commitment itself
was never converted into a diff at all) and the `notes/planning-and-process-lessons.md` entry this
DoD pass added for BR-2's U4 specifically.
