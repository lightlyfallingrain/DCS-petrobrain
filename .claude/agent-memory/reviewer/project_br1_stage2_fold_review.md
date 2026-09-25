---
name: br1-stage2-fold-review
description: Review outcome for the BR-1 Stage 2 duplicate-branch fold (e3fce0e) and the technique for verifying a split composition test closes a cross-subproject seam
metadata:
  type: project
---

Reviewed `e3fce0e`/`8253fba` on `feature/brain-layer-stage2` (folding `feature/br1-stage2`'s
BECAUSE-quoting fix into the kept base) against the prior Stage 2 review's required fix
(`plans/brain-layer/review.md`). **APPROVED, no required fixes.**

**Technique: verifying a "split composition test" across a module-independence boundary.** The
implementer could not write one cross-import test (brain-layer/body-layer have no sanctioned
shared import), so split it into brain-layer proving the parser's real entrypoint (`decider.decide()`,
not a private helper) emits the unquoted value, and body-layer proving that exact value validates.
**Don't just check both halves pass — trace whether every link between them is also covered by an
*already-existing, untouched* test using the real production function**, not a re-implementation.
Here the missing middle link was `BrainLayerClient._reply_from_dict`'s dict→`BrainReply` passthrough,
already covered (pre-fold, unrelated to this fix) by `test_brain_client.py`. Three real-function
tests chained by transitivity is real coverage of the seam, not two assertions that happen to agree —
but say so explicitly, and name the one gap it still leaves (no single test runs the actual JSON-over-
HTTP wire path end to end; only a manual assertion-free tool does).

**Worktree was `main`-based again, not on the branch under review** — see
[[feedback_worktree_main_based_pytest_pythonpath_trap]] (body-layer's own memory of this exact trap
from a prior review). Used `git archive <sha> | tar -x` into a scratch dir and built fresh venvs
there rather than trusting the ambient checkout; both subprojects' claimed test counts (brain-layer
35→44, body-layer 1288→1289/4xfailed) matched exactly on independent re-run.

**When a fold's commit message claims an omission is "structurally redundant"**, verify the claim by
reading the *current* code, not by comparing feature lists: here the older branch's poll-timeout
shortening fix was for a synchronous-on-shared-thread architecture; the kept branch's
`brain_client.py` already ran `poll_replies()` on its own lazy background thread pre-dating the fold
commit (confirmed via `git diff --stat` showing the file untouched by the fold) — the omission was
correct because the vulnerable architecture never existed on this branch, not because the fold
implementer merely judged it unnecessary.
