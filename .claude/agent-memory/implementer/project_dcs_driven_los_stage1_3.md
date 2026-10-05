---
name: project_dcs_driven_los_stage1_3
description: X-B29 DCS-driven LOS Stages 1-3 -- worktree/scratch split, two-%d splice, tolerance boundary correction
metadata:
  type: project
---

Built X-B29 (DCS-driven batched line of sight) Stages 1-3 on `feature/dcs-driven-los`. Worth
remembering:

**Worktree landed on a commit whose plan.md predates the feature branch's revisions and the
security review, but the actual src/ files hadn't diverged.** `git rev-parse HEAD` (`be12734`)
confirmed not-an-ancestor of the feature tip (`f6a8692`), per AGENTS.md rule 4. Rather than working
entirely from the `git archive` snapshot and hoping a diff would apply cleanly later, I diffed every
file I was about to touch between the snapshot and the worktree's own checkout — all identical
(main hadn't touched aircraft-layer/body-layer for these files since the branch point) — then made
every actual edit directly in the worktree, using the snapshot only for reading context. This
matters because **editing scratch-only copies and then committing from the worktree commits
nothing** — I did this by mistake for the first ~15 files before catching it, had to re-diff and
copy everything back in. Next time: confirm early whether snapshot-vs-worktree divergence exists
for the files in scope, and if none, just edit the worktree directly from the start — don't edit a
scratch copy "for safety" when the real commit target is the worktree.

**A Security-recommended invariant test ("exactly one `%d`") needed a documented deviation, not
blind compliance.** The review's phrasing was about FOV alone; the actual plan (§17, user-approved)
coalesces hour+FOV into one `dostring_in` call, so the template legitimately needs two `%d`
substitutions. Relaxing "exactly one" to "exactly two, no other specifier" preserves the review's
real intent (no non-%d specifier, no silent third substitution point) — written down explicitly in
both the Lua file's header and the test's docstring so a future reader doesn't read the count as a
regression of the review's requirement.

**A mid-task user correction landed after most of the implementation was already done** (the 12 m
tolerance must never apply on the live path). Checked first whether any code change was actually
needed — none was: gate 4 already never calls the offline primitive once `live_los_clear is not
None`, by construction, so the fix was purely documentation (the constant's own comment + the
plan's own now-half-wrong section, corrected with a forward pointer per instruction, original text
kept beneath it). Worth always checking "is this already true by construction" before reaching for
a code change when a correction arrives mid-task.

See [[feedback_agent_memory_path]] and [[feedback_implementation_log_append]] for recurring
cross-feature lessons this task did not newly discover but re-confirmed.
