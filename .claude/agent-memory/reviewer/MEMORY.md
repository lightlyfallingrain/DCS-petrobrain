# Memory Index

- [Entrypoint class logic untested](feedback_entrypoint_class_logic_untested.md) — "no test for __main__.py" policy can mask untested state-machine logic bundled inside it; check placement, not filename.
- [Side-quest commits on feature branch](feedback_side_quest_commits_on_feature_branch.md) — check `git log main...HEAD` per-commit, not just aggregate diff, for bundled skill/docs/research commits that should've used a worktree.
- [Estimate flags must reach code](feedback_estimate_flags_must_reach_code.md) — sourced-vs-estimated numeric fields need per-field inline comments in code, not just a research-doc citation.
- [Clamp structural vs measured residual](feedback_clamp_structural_vs_measured_residual.md) — a formula matching measured RATIO but not absolute figure isn't a bug if research doc names it a known residual; check structural property, not raw number.
- [Cones 2C implementation-log gap](project_cones_2c_implementation_log_gap.md) — implementer skipped implementation.md, wrote only agent-memory; check each sub-slice has its own implementation.md section, not just memory.
