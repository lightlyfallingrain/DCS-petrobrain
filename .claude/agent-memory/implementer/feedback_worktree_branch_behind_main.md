---
name: worktree-branch-behind-main
description: Check the worktree's own branch against main before trusting a task's "base on main @ <sha>" instruction.
metadata:
  type: feedback
---

An implementer worktree's own branch (`worktree-agent-<id>`) can be created
before a commit the task's spec depends on lands on `main` — it was, on the
audio-adapter review-findings task: the worktree branch was 2 commits behind
`main`, missing exactly the two review-report commits the task said to read
first (`git log --oneline main -3` vs the worktree branch showed the gap
immediately).

**Why:** worktrees are created ahead of time relative to when the main loop
finishes prep work on `main` (e.g. cherry-picking review commits). Nothing
guarantees the worktree branch was cut *after* that landed.

**How to apply:** before reading a task's named files, run
`git log --oneline <worktree-branch> -5` and `git log --oneline main -5` and
compare. If the worktree branch has no commits of its own yet (clean
`git status`, no unique history), `git merge --ff-only main` is safe and
non-destructive — never `git reset --hard` (denied by the sandbox anyway,
and destructive on principle). If the branch already has real commits,
escalate instead of guessing how to reconcile.
