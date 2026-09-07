---
name: stage-memory-files
description: Always `git add` agent-memory files in the same step as writing them — reviewers have flagged leaving them unstaged six times.
metadata:
  type: feedback
---

When you write or update anything under `.claude/agent-memory/`, stage it immediately in the same step: `git add .claude/agent-memory/architect/`.

**Why:** agent memory is project-scoped and version-controlled — it is shared with the team, so an unstaged memory file is a memory nobody else gets. Reviewers have now flagged this same omission six times; it is the single most repeated process defect in this role's output. The project's own Definition of Done ("all new/modified files staged") already covers it.

**How to apply:** treat "write memory file → update MEMORY.md → git add both" as one indivisible action, not three. This holds even when the task says to leave *plan/doc* changes unstaged for user review — that instruction is about the deliverable under review, not about memory bookkeeping. Stage memory regardless; if genuinely unsure, stage it and say so in the report.
