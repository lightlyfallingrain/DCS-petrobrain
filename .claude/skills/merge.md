---
name: merge
description: Merge a feature branch to main via a disposable worktree, verify, push, clean up
type: user-invocable
---

Merge a feature branch into main. Usage: `/merge <branch-name>` or `/merge feature/<branch-name>`.

If no branch name is given, use the current branch (confirm with the user if ambiguous).

**Why a worktree, not `git checkout main` in the current directory:** this project runs
background Architect/Implementer/Reviewer/DoD agents in the same working directory (no
`isolation: "worktree"` on those Agent calls). Switching branches in-place races any agent still
running — check `ListAgents` first. A disposable worktree lets the merge happen without touching
the current checkout at all, regardless of what else is running.

Steps (execute in order):

1. Confirm the full branch name — prefix `feature/` if the user omitted it.
2. `ListAgents` — if anything is still running in this session, prefer waiting or proceeding via
   the worktree anyway (the worktree itself never races, since it's a separate directory); just
   don't `git checkout` anything in the *current* directory while agents are active.
3. `git status --short` on the current checkout — should be clean (the branch being merged should
   already have all its work committed; if not, stop and say so rather than merging incomplete work).
4. `git fetch origin main`.
5. `git worktree add ../<repo-name>-merge-<short-branch-name> main` — a fresh worktree on latest main.
6. In that worktree: `git merge --no-ff feature/<name> -m "<message>"` — never `--squash`, never
   rebase main. Write a real merge commit message summarizing what the branch did and citing its
   DoD report, matching this project's commit-message conventions (see root CLAUDE.md/AGENTS.md).
7. **On conflict:** resolve by hand, preserving both branches' intent where the resolution is
   clear-cut (e.g. two features adding independent functions/entries to the same file — keep both;
   two doc updates in the same paragraph — merge the content, don't pick one side and discard the
   other). Do not silently drop either side's work. If a conflict is genuinely ambiguous — the two
   branches made incompatible design choices in the same code, not just nearby edits — stop and
   describe it to the user rather than guessing.
8. Run the affected subproject(s)' full verification suite **inside the worktree** (format, lint,
   type check, test — see that subproject's CLAUDE.md for exact commands) before finalizing. Do
   not skip this even if both branches individually passed CI before merging — the merge itself can
   introduce breakage neither branch's own tests would catch.
9. `git commit` (if the merge didn't auto-commit, e.g. after manual conflict resolution).
10. `git push origin main`.
11. `git worktree remove ../<repo-name>-merge-<short-branch-name>`.
12. Back in the original directory: `git branch -d feature/<name>` if the user wants the local
    branch cleaned up (ask, or infer from context — don't delete without at least implicit consent).
13. Read `todo/todo.md` and mark the relevant `[~]`/checkbox items for this branch as done/merged,
    matching this project's existing todo.md conventions for a shipped milestone.
14. Show the user the updated relevant section of `todo.md`.

Rules:
- Never force-push main.
- Never rebase main onto a feature branch or vice versa — always a `--no-ff` merge commit, so the
  branch's own commit history (stages, review passes, DoD) stays intact and readable in `git log`.
- Never touch the current working directory's branch/checkout to perform the merge — always via
  the disposable worktree, even when no other agent is currently running (consistent behavior is
  cheaper than remembering when it's "safe" to skip the worktree).
- After a successful merge, ask the user what to work on next rather than assuming.
