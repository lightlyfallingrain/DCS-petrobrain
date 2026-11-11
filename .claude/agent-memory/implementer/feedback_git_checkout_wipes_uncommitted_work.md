---
name: git-checkout-wipes-uncommitted-work
description: never run `git checkout -- <file>` to undo a counterfactual-proof edit or any temporary sabotage when that file also has real uncommitted work -- it silently discards everything, not just your last edit
type: feedback
---

On `BL-B111` pass 1, twice in one session: after proving a test goes red for
the stated reason by temporarily breaking a fix (`git diff` to confirm the
break, run the test, see it fail), I ran `git checkout -- <file>` to restore
it. Both times the file also held a full step's worth of *other*
uncommitted work (new `_TEMPLATED_KINDS` entries, a new method, comment
rewrites) that had not yet been committed. `git checkout --` restores to
HEAD, not to "a moment ago" -- it threw away all of it silently, with no
warning, no diff shown. Had to reconstruct the whole step from scratch both
times by re-reading what I'd just written a few tool calls earlier.

**Why it happened**: muscle-memory reach for `git checkout --` as "undo my
last edit," which is only safe immediately after a commit with a clean tree.
The user's own global instructions already say "run `git status` before any
command that could discard uncommitted work" -- I ran `git diff --stat`
first (which *showed* the pending work) and still typed the checkout command
on the same breath, because the check and the destructive command were not
causally connected in my own reasoning, just adjacent.

**How to apply**: when restoring from a deliberate counterfactual break
(red-test verification), **never use `git checkout --`, `git restore`, or
any ref-based restore on a file with uncommitted changes.** Instead:
1. Keep the original text in hand (you just wrote it, or re-read it with
   `Read` immediately before breaking it) and use `Edit` to put it back --
   the same tool that made the break.
2. Or `git stash push` the real work *before* making the temporary break,
   confirm red, `git checkout --`/`git restore` the break away cleanly, then
   `git stash pop` the real work back.
3. Treat "this file has a nonzero `git diff --stat` right now" as a hard
   stop on any command whose job is "make this file match some other
   version" -- that includes `checkout`, `restore`, `reset --hard` on a
   path, and `stash` without `-u`/a label if other stashes might collide.

The commit message for the second incident spells out exactly what was lost
and why, so a reviewer reading the diff knows the redone code is the
original intent, not a hasty second guess.
