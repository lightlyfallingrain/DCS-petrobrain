---
name: harvest-agent-commit
description: Harvest an isolated agent's worktree commit onto a feature branch, verify it against the agent's own file list, then remove the worktree and delete its branch. Use after any agent run with isolation "worktree" -- Reviewer, DoD, Architect, Investigator, Security, Performance Reviewer, or an Implementer on worktree-agent-<id>.
type: user-invocable
---

Harvest one isolated agent's work. Usage: `/harvest-agent-commit <agent-id-or-sha>`, or with no
argument to harvest whatever worktrees are currently present.

`AGENTS.md`'s "Where work happens" rule 1 states the *policy* — commit inside the worktree,
cherry-pick the sha, verify against the file list, remove the worktree, delete the branch. This
skill is the *mechanics*, which were being improvised each time. Three complications recur, and
one of them nearly lost work.

## The failure this prevents

An agent writes far more than its headline report: agent-memory files under
`.claude/agent-memory/<role>/`, a `NOTES.md` harvest, research notes, roadmap and `todo/` edits.
All of it lives only in the worktree. Copying back the report alone looks like success and
silently drops the rest — and a memory file that is never harvested is the most expensive loss in
this system, because its whole purpose is to stop the next agent repeating a mistake.

## Procedure

### 1. Find what is there before touching anything

```sh
git worktree list
git branch --list 'worktree-agent-*' -v
```

A worktree row ending `locked` is an agent that is still registered as running (or crashed while
registered). A `worktree-agent-<id>` branch that still exists means **not yet harvested** — that is
the only signal distinguishing harvested from unharvested work, which is why step 5 deletes it.

### 2. Identify the commit, and do not trust the branch ref alone

```sh
git log --oneline -3 worktree-agent-<id>
git show --stat <sha>
```

**The branch ref can sit at the worktree's base commit while the real work is on a detached
HEAD.** This happens whenever the agent committed detached (which rule 1 explicitly allows). If
`worktree-agent-<id>` points at `main`'s tip and the agent reported a different sha, the sha is
the truth — use it. Check it is reachable before anything else deletes it:

```sh
git cat-file -t <sha>   # must print "commit"
```

A commit stranded on a detached HEAD whose branch was deleted too early is recoverable only by sha
or `git reflog`. That happened once here and was close to unrecoverable.

### 3. Apply it to the right branch

Three cases:

- **The commit is a strict descendant of the target branch's tip — check first, and prefer this.**
  `git merge --ff-only <sha>`. It preserves the agent's shas, so its branch registers as merged and
  `git branch -d` works, which answers "has this been harvested?" with git rather than bookkeeping.
  Agents fast-forward to the named tip before working, so this is the normal case:

  ```sh
  git merge-base --is-ancestor <target-branch> <sha>   # true => fast-forward available
  ```
- **It is not a descendant** (the branch moved while the agent worked). `git cherry-pick <sha>` —
  a fallback, not a failure, but it rewrites shas and the agent branch will never register as
  merged. Prefer not to commit to a branch an agent is working on.
- **The target branch is checked out *somewhere else*** (another worktree — now the normal case,
  since all work happens in one). Git refuses a second checkout. Make a temporary worktree in the
  scratchpad, fast-forward there, remove it:

  ```sh
  git worktree add <scratchpad>/ff <target-branch>
  git -C <scratchpad>/ff merge --ff-only <sha>
  git worktree remove <scratchpad>/ff
  ```

**Check which branch you actually landed on before and after.** A cherry-pick aimed at a feature
branch, run from a checkout sitting on something else, lands on that something else — and the repo
root is usually on `main`. `git log --oneline -1` costs nothing.

### 4. Verify against the agent's own file list, not against the pick

```sh
git show --stat <sha>
```

Compare that list to the file list in the agent's final message, name by name. The pick succeeding
is not evidence it caught everything; the agent's list is the only independent record. Pay
attention to `.claude/agent-memory/<role>/*` — those are the files most often missing and least
often noticed.

### 5. Remove the worktree, then delete the branch — in that order

```sh
git worktree unlock .claude/worktrees/agent-<id>   # only if the list said "locked"
git worktree remove .claude/worktrees/agent-<id>
git branch -D worktree-agent-<id>
git worktree prune                                  # if a directory was deleted externally
```

**Never `git worktree remove --force`.** It is in the deny list (`.claude/settings.json`) and it
destroys uncommitted work without warning. A plain remove succeeds on a clean worktree and on one
holding only gitignored build artifacts; it refuses only when genuinely untracked files are
present — **and that refusal is the safety check**. Read what it names: it is telling you either
about work you have not harvested, or about an artifact that needs a `.gitignore` entry. The one
artifact that ever forced the flag here was `*.egg-info/`, and every subproject now ignores it.

`unlock` is the correct answer to a locked worktree, not `--force`. The lock is bookkeeping about
a registered agent process, not a guard over file contents.

### 6. Confirm

```sh
git worktree list
git branch --list 'worktree-agent-*'
git status --porcelain
```

The harvested worktree and its branch should both be gone, and the tree clean.

## Why branches accumulate, and why it matters

The harvest is a cherry-pick, so these branches never register as merged and nothing used to
delete them. By 2026-09-27 there were 67 against 58 real branches, which broke the Session Start
state check and — worse — left no way to tell a harvested branch from an unharvested one. The 41
already-ambiguous ones were left in place rather than guessed at; they are still there. Deleting
at harvest time is what keeps a branch's existence meaningful.
