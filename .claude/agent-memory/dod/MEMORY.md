# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [Verify ROADMAP prose claims](feedback_verify_roadmap_prose_claims.md) — grep/git-log-check "filed in X"/"recorded in Y" claims in ROADMAP.md/plan.md prose, don't trust plausibility.
- [Recurring: plan test-file naming](project_recurring_plan_test_file_naming.md) — 3rd occurrence of a plan citing a wrong/missing test file; likely an Architect-stage gap.
- [Recurring: keyword-table vocabulary mismatch](project_recurring_keyword_table_vocabulary_mismatch.md) — 3rd occurrence of object_model.profile_for under-joining an externally-sourced name table; raise at Architect.
- [DoD worktree pytest/PYTHONPATH trap](feedback_dod_worktree_pythonpath_trap_applies_here_too.md) — main-based DoD worktree + branch checked out elsewhere: use a git-archive scratch tree, not the worktree checkout.
- [curl blocked in worktree sandbox](feedback_curl_blocked_in_worktree_sandbox.md) — use Python urllib, not curl, for a live loopback HTTP spot-check from inside a worktree.
- [Change-request fix needs no security-plan-review](project_change_request_fix_no_security_plan_review_expected.md) — Security/Perf-Reviewer change-request branches correctly skip plan.md/security-plan-review.md; check the whole-subproject audit doc instead.
- [Recurring: multi-round threshold widening](project_recurring_multiround_threshold_widening.md) — widening a fixed set/threshold/window tends to take several rounds, each caught only by running the real subsystem, not by inspection.
- [Current cadence: one security pass per feature](project_current_cadence_one_security_pass_per_feature.md) — under the 2026-09-24 cadence, a missing security-plan-review.md is expected for ANY feature, not just change-request fixes.
