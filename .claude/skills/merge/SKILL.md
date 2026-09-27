---
name: merge
description: Merge a feature branch to main via a disposable worktree, verify, push, clean up
type: user-invocable
---

Merge a feature branch into main. Usage: `/merge <branch-name>` or `/merge feature/<branch-name>`.

If no branch name is given, use the current branch (confirm with the user if ambiguous).

**First decide: is the branch being merged the one already checked out in the main working
directory?**

- **Yes — it's the active branch this session has been working on.** Merge in place, no worktree:
  `git checkout main`, `git merge --no-ff <branch>`, verify, `git push origin main`. A worktree
  here is redundant — the main working directory ends up on `main` afterward either way, so
  routing through a second checkout just to land back where `git checkout main` would put you
  directly adds a step for no benefit. (User decision, 2026-09-10.)
- **No — merging some other branch while the main working directory is on a different branch (or
  something else may be active in it).** Use the disposable-worktree path below.
  **Why a worktree in this case, not `git checkout main` in the current directory:** switching
  branches in-place would disturb whatever branch the session is mid-task on, and would race
  anything else operating in that checkout. A disposable worktree lets the merge happen without
  touching the current checkout at all. `AGENTS.md`'s "Where work happens" section states who owns
  the main checkout and where agents run — read it there, because that division has been inverted
  once already and the reasoning here depends on it.

## In-place merge (active branch == branch being merged)

1. `git status --short` — should be clean (the branch should already have all its work committed;
   if not, stop and say so rather than merging incomplete work).
2. `git checkout main && git pull --ff-only`.
3. `git merge --no-ff <branch> -m "<message>"` — never `--squash`, never rebase main. Write a real
   merge commit message summarizing what the branch did and citing its DoD report, matching this
   project's commit-message conventions (see root CLAUDE.md/AGENTS.md).
4. **On conflict:** resolve by hand, preserving both sides' intent where the resolution is
   clear-cut; do not silently drop either side's work. If genuinely ambiguous, stop and describe it
   to the user rather than guessing.
5. Run the affected subproject(s)' full verification suite (format, lint, type check, test — see
   that subproject's CLAUDE.md) before finalizing, even if the branch passed its own checks before
   merging — the merge itself can introduce breakage neither branch's own tests would catch.
6. **Update the roadmap before pushing.** The merged branch's subproject `ROADMAP.md` is the
   source of truth for milestone status; root `ROADMAP.md`'s status table names every subproject
   and links its roadmap, so read which file that is from there rather than from a list here —
   mark the milestone done/merged (status, branch, merge
   commit hash), fix any stale entry the merge makes wrong (e.g. a sibling item that said "pending
   merge" or a blocked item this merge unblocks), and update root `ROADMAP.md`'s status table if
   the subproject's overall phase status changed. Only touch `todo/todo.md` / `todo/backlog.md` if the branch also
   affects a cross-cutting/unscoped item there. Commit this (a separate commit from the merge
   commit is fine — do not amend the merge commit). A merge is not finished until the roadmap
   reflects it, and it must go out in the *same push* as the merge itself, not a later,
   easy-to-forget follow-up.
7. `git push origin main`.
8. `git branch -d <branch>` if the user wants the local branch cleaned up (ask, or infer from
   context — don't delete without at least implicit consent).
9. Show the user the updated relevant section of the roadmap.

## Worktree merge (any other case)

1. Confirm the full branch name — prefix `feature/` if the user omitted it.
2. `ListAgents` — if anything is still running in this session, prefer waiting or proceeding via
   the worktree anyway (the worktree itself never races, since it's a separate directory); just
   don't `git checkout` anything in the *current* directory while agents are active.
3. `git status --short` on the current checkout — not touched by this path, but worth confirming
   nothing there is about to be lost by an unrelated later step.
4. `git fetch origin main`.
5. `git worktree add ../<repo-name>-merge-<short-branch-name> main` — a fresh worktree on latest main.
6. In that worktree: `git merge --no-ff feature/<name> -m "<message>"` — same commit-message rules
   as above.
7. **On conflict:** same as above.
8. Run the affected subproject(s)' full verification suite **inside the worktree** before finalizing.
9. `git commit` (if the merge didn't auto-commit, e.g. after manual conflict resolution).
10. **Update the roadmap before pushing, inside the same worktree.** The merged branch's
    subproject `ROADMAP.md` is the source of truth for milestone status — mark the milestone
    done/merged (status, branch, merge commit hash), fix any stale entry the merge makes wrong, and
    update root `ROADMAP.md`'s status table if the subproject's overall phase status changed. Only
    touch `todo/backlog.md` if the branch also affects a cross-cutting/unscoped item there. Commit
    this (separate commit from the merge commit is fine). A merge is not finished until the
    roadmap reflects it, and it must go out in the *same push* as the merge — not a later,
    easy-to-forget follow-up.
11. `git push origin main`.
12. `git worktree remove ../<repo-name>-merge-<short-branch-name>`.
13. `git branch -d feature/<name>` if the user wants the local branch cleaned up.
14. Show the user the updated relevant section of the roadmap.

Rules:
- Never force-push main.
- Never rebase main onto a feature branch or vice versa — always a `--no-ff` merge commit, so the
  branch's own commit history (stages, review passes, DoD) stays intact and readable in `git log`.
- After a successful merge, ask the user what to work on next rather than assuming.
