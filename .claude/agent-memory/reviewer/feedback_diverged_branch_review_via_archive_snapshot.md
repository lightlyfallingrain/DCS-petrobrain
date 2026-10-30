---
name: feedback_diverged_branch_review_via_archive_snapshot
description: when a feature branch is diverged from the review worktree's HEAD (intentionally built on an older main, bug-fix path), review via git show/diff on literal shas plus a git-archive snapshot for running checks, rather than forcing a merge or touching another worktree that already holds the branch
metadata:
  type: feedback
---

`fix/atgm-run-sight-tracking` (reviewed 2026-10-30) was two commits on top of an **older** `main`,
built via the debugger bug-fix path. My review worktree started from `origin/HEAD` and had
diverged both ways from the branch tip — neither sha was an ancestor of the other — so
AGENTS.md rule 4's "strict ancestor -> ff-merge, otherwise stop and report" did not apply
cleanly: a ff-merge was correctly impossible, but stopping entirely would have blocked the review
for no real reason, since the commit objects are shared across worktrees regardless of divergence.

**Why:** rule 4 is written for the common case (stale base, same lineage). A diverged base from an
intentionally-older-main bug fix is a different shape: the content to review is fully present as
git objects in the shared `.git`, just not reachable from my branch tip. Forcing a merge would
either fail or pull in unrelated main history; refusing to review at all would be overcautious.

**How to apply:**
1. Confirm the divergence both ways (`git merge-base --is-ancestor A B` each direction) before
   concluding "stop and report" — a true diverged state (neither ancestor) is a different case
   from a simple stale base, and deserves a different response.
2. Check `git worktree list` first — if another worktree already holds the exact branch cleanly
   checked out (a feature worktree, not an agent scratch worktree), that confirms the sha is
   real and lets you note it, but **do not `cd` into it and run installs/writes there** — it is
   not this agent's worktree to modify (see the isolation rule).
3. Review the diff directly via literal-sha `git show`/`git diff` (see
   `feedback_git_show_diff_static_refs_permitted.md`) — no checkout needed to read it.
4. To run format/lint/type/test against the exact reviewed sha without touching any other
   worktree: `git archive <sha> | tar -x -C <scratchpad>/<name>`, plus (for body-layer's
   in-process world-model import) a second `git archive <sha> -- world-model | tar -x -C
   <same dir>` so the sibling-path import resolves, then build a fresh venv inside that
   extracted tree and run the subproject's own commands there. This is slower than borrowing an
   existing venv (full dependency install) but touches nothing outside your own scratchpad.
5. Say explicitly in the review report that this path was taken and why, so the verdict's
   evidentiary basis is clear (objects verified by sha, not by a merged working tree).
