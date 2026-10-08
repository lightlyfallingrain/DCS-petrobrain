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
- [Inspect tool drifted from real pipeline](project_inspect_tool_drifted_from_real_pipeline.md) — a dev `tools/` script can silently stop calling the real pipeline function it claims to visualize; check that at DoD.

- [Recurring: approved plan wrong on real data](project_recurring_approved_plan_wrong_on_real_data.md) — 2nd occurrence this week (contact-report-flood, geomorphons perf); consider a real-data check earlier than Implementer.
- [Recurring: outcome-only regression test](project_recurring_outcome_only_regression_test.md) — 2nd occurrence of a guard test asserting only final status/exception, not the specific mechanism, next to a broader catch-all; raise at Reviewer.
- [Branch ref lags reviewed tip](project_branch_ref_lags_reviewed_tip.md) — HEAD matching the dispatched sha doesn't mean the feature branch itself was fast-forwarded; check `git rev-parse <branch>` too.
- [Plan staleness across parked stages](project_plan_staleness_across_parked_stages.md) — terrain-feature-probing's parked Stages 3-5 assumed basin adjacency from a since-replaced detector; 1st occurrence, watch for a 2nd.
- [Cross-machine handoff, zero gate risk](project_cross_machine_handoff_zero_gate_risk.md) — a branch built entirely on another machine/session can arrive with literally no test run ever performed on it.
- [Roadmap edit target: feature branch vs main](project_roadmap_edit_target_feature_vs_main.md) — diff the file against the fork point first; if the feature branch already touched it, edit a branch off the feature tip, not main.
- [Recurring: prose count of a code set](project_recurring_prose_count_of_a_code_set.md) — 5th+ occurrence; derive "N of M kinds" by import at writing time, at Architect/Implementer not Reviewer.
- [main doc describes unmerged-branch behaviour](project_main_doc_describes_unmerged_branch_behaviour.md) — verify a card's runtime claims against the branch being flown, not against a skill/doc committed on main.
- [Name the boundary when the observable is an absence](feedback_name_the_acceptance_boundary_when_the_observable_is_an_absence.md) — a suite of `== []` asserts can't tell a working gate from a broken producer; give the user the asked-vs-unprompted split.
- [Stale worktree base: plain checkout first](feedback_stale_worktree_base_try_plain_checkout_first.md) — try `git checkout <branch>` before ff-only/git-archive; it's exact whenever the branch isn't held elsewhere.
- [Recurring: correct conclusion, unearned reason](project_recurring_correct_conclusion_unearned_reason.md) — 5 instances on one branch; read a review's *reason* as its own claim, usually one grep from falsification.
- [Stage [x] can live on an unmerged branch](project_stage0_x_lives_on_an_unmerged_branch.md) — a "that stage is already done" claim may be true only of a second branch; check before editing a shared roadmap.
- [Voice card: never prefix a command with the wake word](feedback_voice_card_never_prefix_a_command_with_the_wake_word.md) — "Petrovich, describe" routes to the brain, not the matcher; run every utterance through match_transcript first.
- [Recurring: predicate granularity mismatch](project_recurring_predicate_granularity_mismatch.md) — 3+ rounds strengthening one predicate means it is a granularity coarser than what it governs; raise at Architect.
- [pcall degradation without a counter](project_pcall_degradation_without_counter.md) — a pcall added for graceful degradation shipped with no paired failure counter; 1st occurrence at DoD, watch for a 2nd.
- [caplog.at_level masks default logging visibility](project_caplog_at_level_masks_default_logging_visibility.md) — a `logger.info` call can pass every caplog-based test and still never print on a real run with no handler/level configured; grep + direct repro at DoD.
