---
name: feedback_mutation_revert_blocked_on_security_parser
description: Auto-mode classifier refuses an Edit that temporarily reverts a security-relevant parser/validator fix (flagged "security test removal"), even when done in-worktree for a mutation check and immediately restored. Plan around it.
metadata:
  type: feedback
---

**What happened:** reviewing BL-B80's exponent-float fix (`Export.lua`'s
`extract_json_number_field`), I tried to repeat the implementer's own documented counterfactual
run -- revert the fixed pattern to the old digits-only one, confirm the new test class fails,
restore, `shasum` to confirm an exact restore -- the standard "verify by mutation, not by reading"
protocol this role's own memory (`feedback_` entries on mutation) calls for. The first Edit (the
revert) succeeded; running the test suite against it was refused by the harness's auto-mode
permission classifier with "Security Test Removal". The restoring Edit (undoing the revert)
succeeded fine, and `shasum`/`git status --porcelain` confirmed an exact restore before I moved
on.

**Why:** the classifier reasons about the *editing* action, not the overall intent -- an Edit that
removes/weakens a security-relevant check reads as the same shape whether it's a permanent
removal or a five-second mutation-test revert inside a review that will restore it immediately.
It does not have visibility into "I am about to restore this."

**How to apply:** when a reviewer-protocol mutation check would require temporarily weakening a
security-relevant parser, validator, or guard (not a test file, the production code itself):
expect the classifier to refuse running anything (tests, scripts) against the reverted state, even
though the Edit that performs the revert itself may go through. Do not try to work around the
refusal (e.g. by disguising the command). Instead:

1. Do the revert+restore exactly once if the Edit itself succeeds, and don't chain a blocked
   action after it in the same flow -- confirm the restore immediately via `shasum`/
   `git status --porcelain` so there's no window where production code sits in the weakened state.
2. Substitute independent forward-direction verification: hand-trace the vulnerable pattern against
   the adversarial inputs, and/or extract the *live* function into a standalone script and run it
   directly (not via the project's own test/build tooling, which is what trips the classifier) --
   this is not blocked, since it exercises the current (fixed) code, not a reverted one.
3. State plainly in the review output that the counterfactual mutation was not independently
   re-run, which account it rests on instead (the implementer's own documented run, in this case),
   and what you did in its place. Do not silently present the implementer's account as your own
   finding.

See `plans/9k113-sight-pointing/review.md`'s "Mutation check" section (exponent-float fix review,
2026-10-22) for the worked example.
