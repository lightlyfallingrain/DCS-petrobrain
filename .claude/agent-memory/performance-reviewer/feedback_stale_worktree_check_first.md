---
name: stale-worktree-check-first
description: an assigned worktree's HEAD can predate the branch tip the task actually names — verify before trusting git diff/log output
metadata:
  type: feedback
---

On the BR-1 Stage 2 review (2026-09-25), the worktree handed to this agent
(`agent-a7ad1bdcc22399837`) had its own branch checked out at an older commit
(`6b8a86e`) than the feature branch tip the task named (`cdb8c7f`,
`feature/brain-layer-stage2`) — `cdb8c7f` was not even an ancestor of the
worktree's HEAD. A first `git log --oneline -15` looked plausible (real
commit messages, real shas) and would have silently reviewed the wrong,
older code if not cross-checked against the task's own stated tip.

**Why:** worktrees are created once and can go stale relative to a fast-moving
feature branch if other agents/commits land on it afterward, or if the
worktree was cut from a different point than expected. Nothing about a
clean `git status` or a normal-looking `git log` signals this.

**Happened again, the other way round (2026-10-06, `feature/bl11-tick-cost`).** The worktree's
HEAD was `19143fa` and the task named `8fa2ad6` — **42 commits ahead**, and this time HEAD *was*
an ancestor. That is the easy case and it has a one-command resolution the paragraph below
does not mention: **`git merge --ff-only <branch>`** onto the worktree's own
`worktree-agent-<id>` branch. No path-scoped checkout, no restore dance, the whole tree is real
code at the named tip. Check `--is-ancestor` in *both* directions first: ancestor ⇒ fast-forward;
not an ancestor ⇒ the `git show` / path-scoped route below. (A `git archive <branch> | tar -x`
snapshot is the third option when the tip is checked out elsewhere and cannot be fast-forwarded.)

**How to apply:** before reading/measuring anything, run
`git merge-base --is-ancestor <task's-named-tip> HEAD` (or diff HEAD against
the task's stated base commit and check it's non-empty in the expected way).
If the named tip isn't an ancestor, don't `git checkout`/`reset --hard` the
worktree's own branch (that's a denied destructive op here) — instead read
via `git show <tip>:<path>` and `git diff <base> <tip> --stat`, and if you
need real code on disk to run/measure against, `git checkout <tip> -- <paths>`
(a path-scoped checkout, not a branch switch) into the working tree, then
`git checkout HEAD -- <paths>` + delete any newly-added files afterward to
restore the worktree to its original clean state before your own commit —
see [[brain-layer-stage2-decider-timeout]] for what this let me actually
measure (real sockets, not a re-read of the implementer's claims).
