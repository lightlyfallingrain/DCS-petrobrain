---
name: feedback-check-agent-memory-staged
description: implementer/other agents can leave their own .claude/agent-memory/ writes unstaged — check git status for this, not just the feature files
metadata:
  type: feedback
---

During M2 Stage 4 review, `git status` showed `.claude/agent-memory/implementer/MEMORY.md`
modified and a new `project_m2_raster_open_questions.md` untracked — neither staged nor part of
the stage's commit, even though the implementation log and commit looked complete otherwise.

**Why:** root `CLAUDE.md`'s Definition of Done requires a clean working tree ("All new/modified
files staged and committed"). Agent-memory writes are real repo files subject to the same rule,
but they're easy to miss because they're not part of the feature diff a reviewer naturally reads
(`plans/<feature>/plan.md`, `src/`, `tests/`) — they show up only in a full `git status`.

**How to apply:** always run a full `git status` (not just `git diff <commit> --stat`) as part of
Reviewer's process, and check for any other agent's memory-directory writes left unstaged. Flag
as a required fix (stage + commit) rather than treating it as out-of-scope noise — it's cheap to
fix and blocks a clean DoD gate either way.
