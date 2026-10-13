---
name: structure-md-goes-stale-within-a-branch
description: STRUCTURE.md docs committed mid-branch (e.g. after a Stage N "attempted and reverted") can be invalidated by a later commit in the same branch that lands what was reverted -- check STRUCTURE.md's own narrative against the branch tip, not just against the plan.
metadata:
  type: feedback
---

On `feature/group-collapse` (reviewed 2026-10-13), `body-layer/docs/STRUCTURE.md`'s entry for
`group_view.py` was written and committed (`c60c6cb`) describing Stage 3 as "attempted and
reverted" -- true at that commit. A later commit on the *same branch* (`fc87237`, the tip) landed
Stage 3 after all, on a second pass that found the original "revert" was based on an unreachable
test fixture rather than a real product fork. `implementation.md` was updated to reflect this
("Stage 3 -- landed (second pass)"), but STRUCTURE.md was not touched again, so at the branch tip
it asserted something false about merged code.

**Why this is easy to miss:** STRUCTURE.md commits inside a feature branch read as "done, in the
past" the moment they're committed, the same way any other file does. But a per-module structure
doc that narrates *process* ("attempted and reverted") rather than only *current shape* has a
shelf life tied to the branch's own later commits, not just to the plan being finished. A reviewer
who reads STRUCTURE.md once near the start of a review, takes it as ground truth, and doesn't
diff it against the actual tip state can approve a doc that contradicts the code it describes.

**How to apply:** when a plan's own implementation log shows a stage was reverted and then
re-attempted/landed later in the same branch (or any multi-pass implementation), re-read
STRUCTURE.md's entry for the touched module(s) *after* establishing what the final state actually
is, not from an earlier skim -- specifically check whether its narrative ("attempted", "reverted",
"not yet built") still matches the tip. `git log -p -- <STRUCTURE.md path>` across the review range
shows when it was last touched relative to the branch's other commits; if a later commit changed
the behaviour STRUCTURE.md describes and STRUCTURE.md's own commit predates it, flag it as a
required fix -- it is exactly the staleness this project's CLAUDE.md names as a standing failure
mode, just happening within one branch instead of across branches.
