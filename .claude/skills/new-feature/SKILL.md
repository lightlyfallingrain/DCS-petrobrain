---
name: new-feature
description: Create a feature worktree and branch, and register the feature where this project tracks in-progress work
type: user-invocable
---

Start a new feature. Usage: `/new-feature <name>`

If no name is given, ask the user for one.

Steps:
1. Normalize the name to kebab-case (e.g. "User Auth" → "user-auth")
2. `git worktree add -b feature/<name> ../<repo-name>-<name> main` — branch from the **local**
   `main` (never `origin/main`), in the feature's own worktree, which lives until it merges.
3. `cd` into that worktree. Everything from here happens there.
4. Register the feature where this project tracks in-progress work. Root `CLAUDE.md` says which
   file that is and what the state markers mean — read it rather than assuming, since milestone
   tracking has moved between files before, and several of the files it used to name are now
   four-line pointers that carry no items. The entry takes the form:
   `- [~] <short description> (feature/<name>)`
5. Confirm: print the worktree path, the branch, and the new tracking line.

Then enter plan mode and present a concrete implementation plan for the feature for the user to
review before any code is written.

## Why a worktree, and not a checkout in the repo root

**The repo root belongs to the user** (`AGENTS.md`, "Where work happens", rule 3, revised
2026-10-09). They park it wherever they like — usually `main`, so they can drop a sortie-feedback
document in or check out a branch to fly without colliding with anything running. Moving its branch
under them is what that rule forbids, so this skill does not `git status` the root, does not ask the
user to commit or stash anything there, and does not `git checkout` in it. A worktree needs none of
that: it starts clean from `main` whatever state the root is in.

Until 2026-10-09 steps 2–3 did exactly the forbidden thing — stop on a dirty root, then
`git checkout main && git checkout -b` in it. A `PreToolUse` hook now refuses `git checkout -b`
while the root is parked off `main` and names this worktree form instead, so the old procedure
would have been blocked in the one case it mattered. Found by that day's integrity audit (Tier 2).

**Name the branch when you hand anything back to the user.** The root's branch no longer tells them
what to test, and that former backstop is gone — so the branch name is the whole of the channel.
