---
name: stale-worktree-base-try-plain-checkout-first
description: On a stale worktree base, try an explicit `git checkout <branch>` before ff-only or git-archive — it works whenever the branch is not checked out elsewhere, and is exact.
metadata:
  type: feedback
---

**When the worktree lands on a stale commit, the first remedy to try is a plain
`git checkout <feature-branch>`.** It succeeds whenever that branch is not checked out in the main
checkout or another worktree, and it puts you on the exact named tip with no reasoning about
ancestry.

**Why:** `AGENTS.md` rule 4 prescribes `git merge --ff-only <tip>` for a strict-ancestor HEAD and
`git archive <branch> | tar -x` when the tip cannot be checked out, and both work — but they are
the fallbacks. 2026-10-06: the DoD worktree opened on `19143fa` (eleven-plus commits behind) on its
own `worktree-agent-*` branch, and one `git checkout fix/callout-observability-gate` landed exactly
on `304a367` with a clean tree, because the dispatcher had deliberately *not* left the branch in the
main checkout. Nine agents hit a stale base that night and each improvised differently; the cheap
check is simply whether the branch is free.

**How to apply:** report the mismatch first, always — that is what catches it. Then: plain checkout
if the branch is free → `--ff-only` if HEAD is a strict ancestor and the tree is clean → `git
archive` snapshot if the tip is held elsewhere. Stop only on a diverged HEAD, unique commits or a
dirty tree. Then re-prove imports resolve to *this* tree before trusting any number —
[[feedback_dod_worktree_pythonpath_trap_applies_here_too]] is the trap that survives a correct
checkout, and [[feedback_worktree_without_venv_borrow_tooling]] covers borrowing the main
checkout's `.venv` by absolute path.
