---
name: target-branch-checked-out-elsewhere
description: When the dispatched branch is already checked out in a different worktree (a user feature worktree), don't try to check it out again -- repoint your own disposable agent branch to the target sha instead, via checkout -B (reset --hard is denied).
metadata:
  type: feedback
---

On `BL-B58` option 2 (bounded-fold-displacement), the worktree's own HEAD was on `main`, not the
dispatched branch `fix/bl-b59-retention-hysteresis` -- the ordinary stale-worktree-base case
`AGENTS.md` rule 4 describes. But the usual fix (`git merge --ff-only <tip>`) was unavailable for a
less ordinary reason: `git checkout fix/bl-b59-retention-hysteresis` failed with
`fatal: 'fix/bl-b59-retention-hysteresis' is already used by worktree at
'/Users/sg/Code/DCS-petrobrain-b59'` -- a **user feature worktree** (per the project's "all work in
worktrees" convention, a feature's own worktree is named after the feature and lives until it
merges) already had that branch checked out, clean, at exactly the expected tip.

**Why this happens:** the dispatching orchestrator names a feature branch as the target, but that
branch's own long-lived worktree already exists elsewhere in the filesystem (it is not scaffolding
to be torn down) -- a different situation from the ordinary "worktree created from stale
`origin/HEAD`" case, where the fix is usually a plain merge or checkout in your own worktree.

**How to apply:** you cannot checkout the branch name itself. Instead, check whether your own
worktree's disposable branch (`worktree-agent-<id>`) has any unique commits of its own (`git diff
main worktree-agent-<id> --stat` -- empty output means none). If it has none, repoint it to the
target sha directly:

```sh
git checkout -B worktree-agent-<id> <target-sha-or-branch>
```

This is not `git reset --hard` (which the permission system denies outright and which this project's
own rules single out as destructive-by-default) -- it is a checkout that recreates the branch
pointer, and it is safe specifically because the branch had nothing to lose. If the agent branch
*does* have unique commits, stop and escalate rather than discarding them with either command.

Afterward your own worktree's HEAD matches the dispatched tip exactly, and you commit your work to
your own branch as usual -- the harvester will still find a clean fast-forward path from the
dispatched branch's tip, since your branch is now a strict descendant of it.
