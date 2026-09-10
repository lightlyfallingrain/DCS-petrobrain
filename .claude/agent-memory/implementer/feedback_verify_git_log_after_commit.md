---
name: verify-git-log-after-commit
description: another live session in the same checkout can rewrite/reset the branch mid-task; re-check git log/status after committing, not just before
metadata:
  type: feedback
---

On BL-5 (`plans/bl5-tool-api/plan.md`), a concurrent session working in the same checkout
(no worktree isolation) committed mid-implementation, briefly sweeping this session's
already-`git add`-staged `console.py`/`test_console.py` changes into its own unrelated commit.
That session then `git reset`-and-recommitted with only its own file, which put the swept files
back as unstaged working-tree changes -- no content was lost, but a naive "did my commit
succeed" check right after `git commit` would have been misleading, since HEAD's subject line
briefly named something else entirely.

**Why:** multiple agent sessions can run against the same repo directory without worktree
isolation (this project's `/merge` skill was itself being rewritten, by a separate session, at
the exact same time as this implementation task). `git commit` operates on whatever is staged
at call time, not just what one session itself `git add`ed.

**How to apply:** after every commit in a task, re-run `git log --oneline -3` and `git status
--short` and confirm the new commit's subject matches what was just written and the working tree
is clean/expected -- don't assume a successful `git commit` return code means the commit contains
only this session's changes. If `git reflog` shows an unexpected `reset` between two commits with
the same message, that is the concurrent-session signature seen here; re-diff the affected files
against what was actually written before recommitting, don't just trust "nothing to commit."
See [[project_bl5_tool_api_stages]] for the concrete incident this was learned from.
