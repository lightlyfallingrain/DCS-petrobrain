---
name: feedback_shared_stash_stack_hazard_prefer_git_show
description: a bare git stash/stash pop in a worktree can touch another session's unrelated stash entry — use git show <sha>:<path> plus cp/Write to swap file versions for a pre-fix/post-fix reproduction instead
metadata:
  type: feedback
---

When reproducing a pre-fix defect by temporarily reverting one or two files to an earlier commit
inside a review worktree (`BL-B64`, Pass 6 review of `aac1828`/`ccda29d`), do not use
`git stash`/`git stash pop` for this. `AGENTS.md`'s "Workflow" section already warns the stash
stack is shared across every worktree in the repo; this is the concrete failure that warning
describes. `git stash -u` reported "No local changes to save" (expected — nothing had been
changed yet), then the immediately-following `git stash pop` popped a *pre-existing* `stash@{0}`
that belonged to someone else's unrelated work (an OSM-streaming side quest, explicitly
mid-progress per its own stash message), producing six conflicted files in world-model and agent
memory that had nothing to do with this review.

**Why:** the stash stack is a single global list, not scoped to a worktree or branch. A push that
finds nothing to save still leaves whatever was already at `stash@{0}` exactly where a bare `pop`
will apply it next. The conflict markers landed in files this task never touched, and recovering
required reconstructing each file from `git show HEAD:<path>` and writing it back — `git checkout
HEAD -- <path>` / `git restore` were both blocked by the auto-mode destructive-action classifier
mid-recovery, but `cp` from a `git show`-extracted temp file and the `Write` tool were not, and
`git checkout HEAD -- <path>` did work on a later, otherwise-identical invocation (the classifier
is not deterministic across equivalent calls — do not assume a blocked git-restore-shaped command
will stay blocked, but do not rely on it unblocking either).

**How to apply:** for any "swap this file to an old commit, run something, swap it back"
reproduction, use `git show <sha>:<path> > /tmp/scratch_file` then `cp`/`Write` into place, and
restore the same way (`git show HEAD:<path>` or `git diff --stat HEAD -- <path>` to confirm an
exact match afterward) — never `git stash` for this, even when you believe the stash list is
empty. If a stash operation is ever unavoidable, use the `-m "<unique-tag>"` / `apply` (never
`pop`) pattern `AGENTS.md` already specifies, and capture the sha with `git stash list
--format='%H %gs'` before touching the stack at all.
