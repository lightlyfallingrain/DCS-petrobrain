---
name: dod-worktree-pythonpath-trap-applies-here-too
description: When DoD's worktree is main-based and the feature branch is checked out elsewhere, run verification against a git-archive scratch tree, not the worktree's own checkout
metadata:
  type: feedback
---

The `body-layer/pyproject.toml` pytest-`pythonpath`-overrides-`PYTHONPATH` trap (first documented
by Reviewer, `.claude/agent-memory/reviewer/feedback_worktree_main_based_pytest_pythonpath_trap.md`)
is not reviewer-specific — it bites DoD identically whenever the DoD worktree is `main`-based and
the branch under gate is checked out in the main working directory (so it cannot be checked out a
second time in the worktree). Running the standard verification commands straight in the worktree
silently tests `main`'s code, not the branch's, and the test count is the tell: it will match
`main`'s baseline, not the branch's expected count.

**Why:** confirmed directly on `position-belief-runaway` (2026-09-25) — pytest in the worktree
reported 1177/4 (exactly `main`'s baseline) when the branch's own reported figure was 1192/4.
Running the same commands from inside a `git archive fix/<branch> | tar -x` scratch tree (`cwd`
set inside that tree's own `body-layer/`) reproduced 1192/4 correctly.

**How to apply:** whenever the DoD task prompt says the worktree is main-based and the branch is
checked out elsewhere (cannot `git checkout` it), archive the branch tip into an isolated scratch
directory before running any format/lint/type/test command, and run every command with `cwd`
inside that tree's own subproject directory — never trust a bare pytest count run from the
worktree's own checkout as evidence about the branch.
