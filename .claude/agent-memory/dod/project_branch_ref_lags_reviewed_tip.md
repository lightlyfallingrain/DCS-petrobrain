---
name: branch-ref-lags-reviewed-tip
description: multi-theatre-afghanistan — the feature branch's own ref was 7+ commits behind the sha DoD was told to verify; the review/security/fix/fix-review chain existed only across scattered detached-HEAD worktrees.
metadata:
  type: project
---

On `feature/multi-theatre-afghanistan`, DoD was dispatched to verify at `0690a74` (the tip after
Reviewer → Security → Performance → security-fix → fix-review → fix-review-2). `git rev-parse
feature/multi-theatre-afghanistan` returned `381f828` — the implementer's own last commit, before
Reviewer ever ran. The entire later chain existed only as commits reachable by sha across several
still-live detached-HEAD worktrees (`git worktree list` showed separate worktrees sitting at each
intermediate tip); none of it was reachable by the branch name a user's `git checkout
feature/<name>` would resolve.

**Why this matters for DoD specifically:** AGENTS.md rule 4 already requires verifying `git
rev-parse HEAD` against the expected sha at dispatch — that check passed here, correctly. But it
only confirms *this worktree* sits on the right commit; it says nothing about whether the
*feature branch itself* has been fast-forwarded to include it. Those are different checks, and
only the second one determines whether the acceptance card's `git checkout <branch>` instruction
will actually give the user the reviewed code.

**How to apply:** after confirming `HEAD` matches the expected tip, also run `git rev-parse
<feature-branch>` and compare. If it lags, say so explicitly in the DoD report *and* in the
acceptance card itself (name both shas, tell the user what `git log --oneline -3` should show) —
don't assume the main loop already fast-forwarded it just because a chain of isolated agents ran
in sequence. This is the same failure class AGENTS.md rule 1's handoff section exists to prevent
(cherry-pick the sha, verify, only then remove the worktree) — it is possible for every
individual agent in a chain to have followed their own dispatch instructions correctly and for
the branch to still end up stale, because the fast-forward step is the main loop's responsibility
between agents, not any one agent's.
