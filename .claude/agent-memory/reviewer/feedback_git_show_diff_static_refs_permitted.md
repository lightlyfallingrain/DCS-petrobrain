---
name: feedback_git_show_diff_static_refs_permitted
description: git show/git diff with literal, static ref arguments (two shas, a sha:path) run fine in a worktree; only dynamically-constructed refs (command substitution) are refused
metadata:
  type: feedback
---

`feedback_worktree_without_venv_borrow_tooling.md` claims `git show <ref>:<path>` is "refused here
as a shared-resource modification" inside a worktree. That was not reproduced on
`fix/atgm-run-sight-tracking` review (2026-10-30): `git show cc6dafac:plans/.../implementation.md`,
`git show cc6dafac --stat`, and `git diff a0e8bf11 cc6dafac -- body-layer/src/body.py` (literal
shas typed directly, no `$(...)`) all ran without any refusal, repeatedly, across a diverged branch
(neither sha an ancestor of the worktree's own `HEAD`).

**Why the contradiction:** the one call that *was* refused in this same session used a shell
variable built at runtime for part of the path:
`git merge-base --is-ancestor <feature-branch> ...` style compound forms, or (separately,
documented elsewhere) a command that assembles a tool path in a shell variable. The refusal reason
given was specifically about the command being "too complex to verify it stays inside the
worktree" — i.e. it is about *dynamic construction*, not about reading another ref's content as
such. A `git show`/`git diff` with two literal, hard-coded refs typed directly into the command is
not a "shared-resource modification" at all — it only reads objects, which are shared across
worktrees of the same repo by design (that sharing is exactly why this works).

**How to apply:** when a branch under review is diverged from (or far ahead/behind) the review
worktree's own `HEAD`, do not assume a merge or checkout is required to read it. `git show
<sha>[:<path>]` and `git diff <shaA> <shaB> -- <path>` with literal shas work directly from the
worktree's own `.git` (shared object store) and are the right tool for reviewing a diverged
branch's diff without disturbing anything. Reserve the stash-hazard/checkout-swap workaround in
`feedback_shared_stash_stack_hazard_prefer_git_show.md` for cases that need the *working tree*
itself changed (e.g. running code against an old version), not for reading content.
