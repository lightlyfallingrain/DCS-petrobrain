---
name: bl-b80-v2-f4-scope-and-missing-mutation-tests
description: BL-B80 v2's F4 differential no-leak test was built narrower than the plan's own spec (ContactStore positions only, not MissionMemory/utterances/TOOL_SET), and the plan's explicitly-named run_once wiring-plus-mutation tests (Stage 3, Stage 3b) were not built at all -- both caught by comparing the plan's own test-list wording against the actual test file, not by reading the diff.
metadata:
  type: project
---

Two gaps found reviewing BL-B80 v2 (Stages 1-4/3b, `feature/9k113-sight-pointing`,
`plans/9k113-sight-pointing/plan.md`/`review.md`), both found the same way: reading the plan's own
stated test requirements word-for-word and grepping the actual test file for whether each one
landed, rather than reading the diff and judging whether it "looks tested."

1. **F4 (the plan's "strongest fence," the one Security's plan review explicitly approved on the
   strength of being a behavioural proof, not a grep) was implemented scoped down to `ContactStore`
   positions only.** The plan's spec (and Security's review of it) required
   `ContactStore`/`MissionMemory`/utterances/`TOOL_SET` all identical between the seen-aim-enabled
   and seen-aim-monkeypatched-to-`None` runs. The implemented test's own docstring rationalizes the
   narrower scope by falling back to "the structural fact that `seen_world_direction`'s only
   consumer is `sight_head.py`" -- i.e. the exact grep-based (F2/F3) argument the plan and Security
   both said F4 exists to verify *independently of*, not fall back on. A scope note in a test's own
   docstring that argues away part of what the test was supposed to prove is worth treating as a
   finding, not as settled.
2. **The plan names, by sentence, a "wiring test + mutation" requirement for both Stage 3 and Stage
   3b** -- explicitly because this project has three prior leaf-tested/wiring-untested defects on
   the exact same shape (a unit test on the leaf function passes, nothing proves the runner
   actually wires it in). Grepping the test files for `mutation` found two hits, both unrelated
   (guidance-unit power-up sequencer, "ready" announcement latch) -- the `sight_head`/
   `select_sight_goal` wiring itself has real, passing wiring tests but no demonstrated-red
   mutation for either stage.

**Transferable lesson**: when a plan's Implementation Plan section names a specific test by
description (not just "add tests"), grep the actual test file for that description's own keywords
(here: `mutation`, and the F4 spec's own named consumers) rather than confirming "a test with a
plausible name exists." A plan that explicitly repeats itself about a named failure class (here:
"the recurring leaf-tested/wiring-untested defect, three prior instances") is telling the Reviewer
exactly what to check for by name -- treat that as a checklist item, not background colour.

See `plans/9k113-sight-pointing/review.md`'s "Finding 2"/"Finding 3" for the full citations, and
`.claude/agent-memory/reviewer/project_recurring_field_of_regard_enforcement_gap.md` and
`.claude/agent-memory/reviewer/feedback_mutation_revert_blocked_on_security_parser.md` for this
subsystem's other recurring-defect-class memories.
