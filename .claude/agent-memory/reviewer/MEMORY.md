# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) - one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md`
(corrections/confirmations about how to approach work) or `project_<topic>.md`
(non-obvious project facts).

**APPEND to this file. Never rewrite it wholesale.** On 2026-09-20 a single commit
replaced this index's 27 entries with 1, leaving 73 memory files on disk and
unreachable by the role that wrote them. The files were never lost; only the index
was. Rebuilt 2026-09-21 from the files themselves.

- [Aircraft layer stage1 2 review](aircraft-layer-stage1-2-review.md) - Review outcome for aircraft-layer stage 1-2 (Export.lua + collector) — approved w/ one minor fix
- [Body layer plan review](body-layer-plan-review.md) - Body-layer plan review outcome — invariants held, but plan contradicted its own provenance rule in worked examples and asserted an open question as...
- [Agent memory path recurrence](feedback_agent_memory_path_recurrence.md) - implementer has written agent-memory files under world-model/.claude/agent-memory/ instead of top-level .claude/agent-memory/ at least twice (f7a7e...
- [Attribution on artifact not just logs](feedback_attribution_on_artifact_not_just_logs.md) - external-data attribution (OSM ODbL etc.) must be burned into the distributable artifact itself, not just printed to console/docs
- [Bounded magnitude isnt optional severity](feedback_bounded_magnitude_isnt_optional_severity.md) - A bounded/small-magnitude risk is not automatically "optional" severity — check whether it violates a stated invariant first
- [Check agent memory staged](feedback_check_agent_memory_staged.md) - implementer/other agents can leave their own .claude/agent-memory/ writes unstaged — check git status for this, not just the feature files
- [Clamp structural vs measured residual](feedback_clamp_structural_vs_measured_residual.md) — a formula matching measured RATIO but not absolute figure isn't a bug if research doc names it a known residual; check structural property, not raw number.
- [Coverage floor fixture check](feedback_coverage_floor_fixture_check.md) - How to check a "coverage floor" test isn't vacuous when its fixture was built by curating only-passing real examples
- [Entrypoint class logic untested](feedback_entrypoint_class_logic_untested.md) — "no test for __main__.py" policy can mask untested state-machine logic bundled inside it; check placement, not filename.
- [Estimate flags must reach code](feedback_estimate_flags_must_reach_code.md) — sourced-vs-estimated numeric fields need per-field inline comments in code, not just a research-doc citation.
- [Keyword vocabulary domain check](feedback_keyword_vocabulary_domain_check.md) - How to review hand-authored DCS object_type keyword tables (association.py, object_model.py, and future ones) for real defects hiding behind "unval...
- [Regression test empirical check](feedback_regression_test_empirical_check.md) - Empirically disable the fix under test and re-run the new regression tests — don't just reason about whether they'd catch the bug
- [Rerun mypy dont trust log](feedback_rerun_mypy_dont_trust_log.md) - A dependency shipping py.typed stubs after implementation can silently break mypy --strict via stale type:ignore comments — always rerun mypy yours...
- [Side-quest commits on feature branch](feedback_side_quest_commits_on_feature_branch.md) — check `git log main...HEAD` per-commit, not just aggregate diff, for bundled skill/docs/research commits that should've used a worktree.
- [Transform confidence verification](feedback_transform_confidence_verification.md) - How to check a coordinate-transform "confirmed" confidence label instead of trusting the field name
- [Verify mypy cwd claims by reproduction](feedback_verify_mypy_cwd_claims_by_reproduction.md) - When an implementer's report claims mypy behaves differently by invocation cwd, reproduce the bug rather than just re-running the final (already-fi...
- [Verify pipeline wiring not just module](feedback_verify_pipeline_wiring_not_just_module.md) - When reviewing a fix to a low-level module, always read the actual call site that wires it into the pipeline/orchestrator, not just the module's ow...
- [M2 raster registration approved](m2-raster-registration-approved.md) - Review outcome for M2 Stage 2 (feature/m2-rastercharts-registration) — approved with no required fixes
- [M4 elevation review outcome](m4-elevation-review-outcome.md) - M4 (DCS elevation vs SRTM) reviewed APPROVED WITH MINOR FIXES — code/tests/checks clean, only blocker was unstaged agent-memory + plan.md files
- [M5 stage1 offline sources approved](m5-stage1-offline-sources-approved.md) - M5 Stage 0+1 (census + offline sources) review outcome and what a clean multi-trap implementation looks like in this project
- [M5 stage2 roadnet approved](m5-stage2-roadnet-approved.md) - M5 Stage 2 (src/roadnet/ DCS-native road parsing) review outcome — approved with minor fixes
- [M5 stage3 probe chunking review](m5-stage3-probe-chunking-review.md) - M5 Stage 3 elevation/surface_type probe review — checklist-mandated timer.scheduleFunction chunking was silently dropped, and implementation.md mis...
- [M5 stage4 validation and resync fix](m5-stage4-validation-and-resync-fix.md) - M5 Stage 4 validation + debugger resync false-positive fix review outcome and reasoning
- [M6 terrain semantics review](m6-terrain-semantics-review.md) - M6 (ridge/valley curvature extraction) review outcome — approved w/ minor fixes; fourth recurrence of unstaged agent-memory files
- [M7 full theatre review approved](m7-full-theatre-review-approved.md) - M7 full-theatre pipeline (Stages 0-4) reviewed clean; execution boundary and provenance invariant both independently verified true, not just docume...
- [M8 probe store read path drift gap](m8-probe-store-read-path-drift-gap.md) - M8 probe store — write-path drift detection (open_probe_store) is solid and tested, but describe_position's ATTACH-based read path only checks sche...
- [Pb1 stage2 3 review](pb1-stage2-3-review.md) - PB-1/body-layer stage 2-3 review outcome and the mypy-cwd-hard-failure variant found in body-layer's cross-subproject seam
- [Pb1 stage4 9 hybrid source review](pb1-stage4-9-hybrid-source-review.md) - PB-1 stages 4-9 (HybridPerceptionSource, association.py) review outcome — APPROVED clean
- [Bl26 dual field pattern](project_bl26_dual_field_pattern.md) - Contact carries both last_class_raw (gate input, unconditional overwrite) and classification (folded best claim, user-facing) — intentional dual fi...
- [Bl26 stage10 docs confidence decay gap](project_bl26_stage10_docs_confidence_decay_gap.md) - BL-2.6 Stage 10 docs claimed classification confidence decays via decay.classification_confidence_at; that function was never built.
- [Bl3 gating placement](project_bl3_gating_placement.md) - BL-3 pattern — policy/attention-gating logic must live in belief/, not perception/; verify by checking the geometry-layer function takes a plain sc...
- [Bl3 summary punctuation](project_bl3_summary_punctuation.md) - belief/tools.py _contact_summary appends fragments onto a string that already ends in "." — check for double punctuation before approving new appends
- [Bl4 effective attention and worktree recon](project_bl4_effective_attention_and_worktree_recon.md) - BL-4 review findings — effective-vs-direct attention event semantics, and a disposable-worktree technique for reconciling per-commit test counts.
- [Bl5 repl thread sqlite fix](project_bl5_repl_thread_sqlite_fix.md) - BL-5 fix for REPL-thread reuse of poll-thread sqlite3.Connection via ConsolePerceptionRunner.enrichment; recurring bug class to re-check on new fields
- [Bl5a urgentcall pattern](project_bl5a_urgentcall_pattern.md) - UrgentCall vs Event dispatch pattern in belief/speech.py — how to judge if it's still clean when BL-6/7 extend it
- [Bl6 scan area review](project_bl6_scan_area_review.md) - BL-6 scan_area/get_task_status/cancel_task review outcome and the copyrighted-PDF-in-git finding
- [Bl7 mission phase minor fixes](project_bl7_mission_phase_minor_fixes.md) - BL-7 mission-phase reviewed — solid implementation, two minor doc fixes needed
- [Body layer research dir convention](project_body_layer_research_dir_convention.md) - DCS-internals verification findings for body-layer/aircraft-layer work are filed in aircraft-layer/research/, not world-model/research/
- [Claude md structure drift on move](project_claude_md_structure_drift_on_move.md) - When code moves between subprojects, check the losing subproject's CLAUDE.md Structure section for stale descriptions of the old location, even if...
- [Cockpit visibility approved](project_cockpit_visibility_approved.md) - cockpit-visibility (body-relative occlusion mask) reviewed and approved — rotation math verified by hand, sign-convention risk confirmed fails-dang...
- [Concurrent session race verification](project_concurrent_session_race_verification.md) - How to verify an implementer's "no content was lost" claim after a concurrent-session git mishap without worktree isolation.
- [Contact report wording approved](project_contact_report_wording_approved.md) - contact-report-wording (9035317) reviewed, APPROVED clean — SAM-safety and vocabulary claims verified real
- [Dcs lua static review technique](project_dcs_lua_static_review_technique.md) - How to review unverified DCS-side Lua/.dlg artifacts without a live DCS session
- [F10 command vocabulary review cycle](project_f10_command_vocabulary_review_cycle.md) - f10-command-vocabulary review cycle — required fix (captured AttentionArea staleness in TaskStore.tick) found, fixed, re-reviewed and APPROVED.
- [F10 crew commands minor fix](project_f10_crew_commands_minor_fix.md) - F10 radio-menu command input reviewed APPROVED WITH MINOR FIXES; caught a flaky test by actually running pytest instead of trusting reported numbers
- [F10 scan naked eye fix approved](project_f10_scan_naked_eye_fix_approved.md) - Live-test fix 89b8b1d (scan-naked-eye-not-9k113) reviewed and approved; console.py's scan-area still drives the 9K113 under the same name, backlogg...
- [Group contact model speech rereview minor fix](project_group_contact_model_speech_rereview_minor_fix.md) - Re-review of feature/group-contact-speech's 3 post-approval commits (couple-of, attention-earned exact counts, speak_samples.py) — APPROVED WITH MI...
- [Group contact model stage1 2 minor fixes](project_group_contact_model_stage1_2_minor_fixes.md) - Structural gate-vs-cluster-radius mismatch found in Stage 2, and how to hand-verify it
- [Group contact model stage3bi rev2 angular](project_group_contact_model_stage3bi_rev2_angular.md) - Stage 3b-i rev.2 (angular separability, 88e493a) reviewed, minor fixes — gate revert and cancellation claims verified genuine.
- [Group contact model stage4b approved](project_group_contact_model_stage4b_approved.md) - Stage 4b (speech/events) reviewed and approved — how the dead-code and structural-test claims were independently verified.
- [Inbound speech stage1 minor fixes](project_inbound_speech_stage1_minor_fixes.md) - srs-adapter STT bench (Stage 1) review found real "unverified external contract" bugs by direct repro, not just reading.
- [Inbound speech stage2 matcher review](project_inbound_speech_stage2_matcher_review.md) - Stage 2 command_matcher/voice_commands review found the verb anchor's leak goes further than the flagged case; fix verified genuine on re-review, A...
- [Inbound speech stage3 approved](project_inbound_speech_stage3_approved.md) - Stage 3 (recognition-as-a-service, stop_talking dispatch) reviewed APPROVED — sequencing trace and interrupt-mechanism reasoning worth reusing.
- [Junctions streaming fix minor fix](project_junctions_streaming_fix_minor_fix.md) - junctions-streaming-fix reviewed, minor fix — tracemalloc call present but unasserted in the memory-bound test.
- [M10 junction review](project_m10_junction_review.md) - M10 road-junction review — APPROVED WITH MINOR FIXES; missing ROADMAP.md entry was the only required fix; canonical-store-safety claim independentl...
- [M1 coordinate transform review](project_m1_coordinate_transform_review.md) - M1 coordinate-transform review outcome and what "earned confirmed confidence" looks like in this project
- [Mi1 mi15 review](project_mi1_mi15_review.md) - Mission Interpreter's first code (MI-1 parser + MI-1.5 filter) — verification technique for the no-leak invariant and vendoring claims
- [Mi3 reviewed approved](project_mi3_reviewed_approved.md) - MI-3 Mission Understanding schema reviewed and approved 2026-09-12, sets the bar for future Tagged[T]-consuming milestones.
- [Mi4 reviewed minor fixes](project_mi4_reviewed_minor_fixes.md) - MI-4 capable-model synthesis review outcome and the two required fixes found.
- [Mi5 reviewed approved](project_mi5_reviewed_approved.md) - MI-5 (player questions) reviewed and approved with no required fixes; disclosed choice-path gap verified against source, not taken on faith.
- [Mi6 reviewed minor fix](project_mi6_reviewed_minor_fix.md) - MI-6 runtime compilation reviewed; one required fix on Tagged[str] | None collapsing rejected-vs-never-asked states.
- [Mock flight fixture review](project_mock_flight_fixture_review.md) - Reviewer verification approach for the cross-layer mock-flight HTTP+belief chain test harness (body-layer) -- APPROVED, no fixes.
- [Object permanence continuity review](project_object_permanence_continuity_review.md) - Object-permanence continuity-of-track fix (fix/association-gate-ambiguity-runaway) reviewed APPROVED, 370 tests, no required fixes.
- [Osm classified cache approved](project_osm_classified_cache_approved.md) - Third M8-pattern persistent store (osm_cache) reviewed and approved — atomicity, invalidation, and source_id-drop deviation all verified sound.
- [Osm landcover optimization minor fixes](project_osm_landcover_optimization_minor_fixes.md) - osm-landcover-optimization (Stages 0-8) reviewed APPROVED WITH MINOR FIXES — ROADMAP entry missing, hole/outer-ring topology unchecked after indepe...
- [Osm streaming ingest approved](project_osm_streaming_ingest_approved.md) - OSM streaming-ingest memory fix (feature/osm-streaming-ingest) reviewed and approved 2026-09-12.
- [Pb2 belief invariants](project_pb2_belief_invariants.md) - Load-bearing invariants for body-layer/src/belief/ to re-check on every future PB-2/BL-2 stage review
- [Pb2 contactstore thread safety](project_pb2_contactstore_thread_safety.md) - How to judge ContactStore thread-safety when reviewing body-layer's --console REPL (poll thread vs REPL thread), reusable pattern for any future un...
- [Pb2 placeholder constants](project_pb2_placeholder_constants.md) - Known-placeholder tuning constants in belief/association_over_time.py, not yet calibrated
- [Pb2 review log append only](project_pb2_review_log_append_only.md) - plans/<feature>/review.md is an append-only running log across stages, not a per-review scratch file — always read it in full and append, never ove...
- [Pb2 stage5 fusion finding](project_pb2_stage5_fusion_finding.md) - PB-2 Stage 5 confirmed certainty/classification fusion is last-writer-wins, not quality-weighted; PB-2/BL-2 fixture-testable work is done. Classifi...
- [Pb2 symmetric gate fix](project_pb2_symmetric_gate_fix.md) - association_over_time's spatial gate fix (both-sided uncertainty budget) verified by reverting to pre-fix commit and re-running the regression test...
- [Ruff cwd dependent isort](project_ruff_cwd_dependent_isort.md) - ruff check's I001 import-sort verdict for world-model/tests flips depending on invocation cwd, not a real regression
- [Stale backlog close review](project_stale_backlog_close_review.md) - How to verify a "bug already fixed, closing stale backlog item" debug report before approving it.
- [Tts voice output stages1 4 approved](project_tts_voice_output_stages1_4_approved.md) - srs-adapter subproject (BL-10 first slice) reviewed and approved; winsound mypy claim reproduced directly, agent-memory commit flagged as side-ques...
- [Vision calibration research doc error](project_vision_calibration_research_doc_error.md) - Pass 1 vision-range-calibration reviewed with one required fix — a "confirmed live" claim in the research doc that reproduction disproved.
- [Provenance confidence pattern](provenance_confidence_pattern.md) - The dataclass+confidence+source shape from coordinates/projections.py is this project's template for any empirically-fitted registration/transform...
- [Cones 2C implementation-log gap](project_cones_2c_implementation_log_gap.md) — implementer skipped implementation.md, wrote only agent-memory; check each sub-slice has its own implementation.md section, not just memory.
- [Callout scheduling approved](project_callout_scheduling_approved.md) — CalloutScheduler reviewed APPROVED clean; how to hand-verify sim-time-only occupancy and clock-merge boundaries beyond the test suite.
- [Boundary only tested via fixture](feedback_boundary_only_tested_via_fixture.md) — a merge/chain-cap boundary can be correct but only incidentally covered by one large fixture; call the private helper directly with hand-built boundary cases.
- [Group detectability roadmap lag](project_group_detectability_roadmap_lag.md) — group-detectability APPROVED WITH MINOR FIXES; ROADMAP.md entry lagged a same-day constant-correction commit, cited stale 0.0013 figure.
- [Movement detection review approved](project_movement_detection_review_approved.md) — APPROVED clean; grep-for-absence technique to verify omniscience-boundary/replay-determinism claims structurally.
- [Precise position belief hybrid gap](project_precise_position_belief_hybrid_gap.md) — NEEDS REVISION: hybrid_source.py never got Stage 2's perturbation, still hands belief exact truth; also no ROADMAP entry.
- [Binocular optic stage2 3b review](project_binocular_optic_stage2_3b_review.md) — APPROVED WITH MINOR FIXES; D4 "any command lowers binoculars" only wired for F10 path, not free-form utterances.
- [Voice command completeness stages1 5 approved](project_voice_command_completeness_stages1_5_approved.md) — APPROVED clean; compass-wrap and multi-contact-report-truncation seams verified by direct execution, both untested but correct.
- [Watch reporting approved](project_watch_reporting_approved.md) — APPROVED clean; all four flagged judgement calls verified true; Stage-5 ROADMAP "merged" claims land before actual merge, a recurring pattern to watch for.
- [Watch reporting fix review](project_watch_reporting_fix_review.md) — single follow-up fix (7f4f24d) APPROVED; how to judge whether an asymmetric gate-reset (hysteresis on one gate, none on another) is fail-safe or a real bug.
