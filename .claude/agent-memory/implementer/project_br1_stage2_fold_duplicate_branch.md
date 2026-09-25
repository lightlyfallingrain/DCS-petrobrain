---
name: br1-stage2-fold-duplicate-branch
description: Folding a duplicate independently-implemented branch into the kept base -- worktree started stale (missing 2 commits), module-independence blocked a naive composition test
metadata:
  type: project
---

BR-1 Stage 2 (brain-layer) was implemented twice by two sessions that didn't know about each
other: `feature/brain-layer-stage2` (kept as base, per user direction -- its non-blocking fix was
structural, a background poll thread + bounded decide() executor, vs. the other branch's
timeout-only fix) and `feature/br1-stage2` (folded in for its real content, then retired).

**Worktree branch was stale by 2 commits.** The assigned worktree's own branch ref pointed at the
base branch's *parent*, missing both the Stage 2 implementation commit and its review commit --
git status context showed the correct HEAD, but the worktree's actual checkout lagged. Caught by
comparing `git log -3` against the stated recent-commits list before starting any work. Fixed with
`git checkout -B <worktree-branch> <correct-tip-sha>` after confirming ancestor relationship
(non-destructive, same pattern [[project_pb1_stage2_3_body_layer]] and others have hit before).
**Always diff the worktree's actual HEAD against what the task's own context/gitStatus block
claims before trusting the checkout.**

**A "composition regression test that pipes X through Y end to end" can be blocked by module
independence when X and Y live in different subprojects with no sanctioned cross-import.**
brain-layer and body-layer are HTTP peers with zero shared imports (test or production) by explicit
convention (`body-layer/tests/test_brain_client.py`'s own docstring states this). Resolved by
splitting the composition into two joined tests instead of one cross-boundary test: brain-layer's
own test proves its parser produces the correct wire value for a quoted model reply; body-layer's
new test proves *that exact value* validates correctly. Together they cover what the review asked
for without importing across the boundary. Worth remembering as the general pattern whenever a
review/task asks for an "end-to-end" test across a boundary this project treats as HTTP-only.

**When two branches solved the same prerequisite differently, "which one is more correct" (not
size or recency) decided which stayed base** -- one used a real structural fix (persistent thread),
the other conceded in its own commit message that it took "the simpler fix." The user's own
framing ("keep yours as base") had already settled this, but it's worth independently confirming
*why* before writing it into the implementation log, since the next reader will want the reason,
not just the outcome.

See [[feedback_verify_git_log_after_commit]] -- same family of "don't trust the stated state,
check the actual one" lesson, this time about the starting checkout rather than a concurrent
commit.
