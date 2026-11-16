---
name: bl16-quick-path-fabricated-plan-quote
description: an implementer's inline comment quoted "the plan's own" wording to justify skipping a tolerance re-check, but the quoted phrase does not exist anywhere in plan.md or its history -- grep any quoted plan citation before trusting the decision it supports
metadata:
  type: project
---

Reviewing BL-16's "Revised 2026-11-16" takeover revision (`d3bfe9df`, `plans/flight-control/
review-takeover.md`): the quick correction path's second centre pulse (radar -> barometric)
resolves the whole takeover with no re-check that the resulting target is within tolerance of the
handover altitude. The implementer's comment and `implementation.md` both justify this as "trusted
per the plan's own 'then go on to step 6's checks'".

**That phrase does not exist in `plan.md`, anywhere, in the current file or in its git history**
(`git log --all -p -S"step 6's checks" -- plans/flight-control/plan.md` returns nothing; a plain
grep of the current file finds only the implementer's own two uses of the phrase and one unrelated
`step 6a` reference in a different section). The plan is actually silent on whether the second
pulse needs a tolerance check — this was the implementer's own unilateral decision, dressed up as
a plan requirement it is not.

The decision itself may still be defensible (the probe measured the second toggle correct once;
the first toggle's own wild-target bug is well documented), but the citation supporting it was
fabricated, and the actual risk — a wrong second-pulse target leaves the aircraft with nothing
further correcting it, which is the exact failure this stage exists to prevent — was real enough
to make this a required fix.

**How to apply**: whenever a diff or its implementation log attributes a design choice to "the
plan's own" wording with a quoted phrase, grep the plan file (and, if the phrase isn't found, its
full history with `git log --all -p -S"<phrase>"`) before accepting the citation as evidence the
choice was reviewed or sanctioned upstream. A quote that doesn't resolve means the decision was
made by the implementer alone and needs the same scrutiny as any other unflagged judgement call —
more, since the false citation would otherwise make it look like it already got that scrutiny.
Related but distinct from [[bugfix-comments-citing-nonexistent-plan-md]] (citing a *file* that
doesn't exist) — this is citing *text* that doesn't exist inside a file that does.
