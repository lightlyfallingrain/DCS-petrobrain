# Memory Index

- [Rerun mypy, don't trust the log](feedback_rerun_mypy_dont_trust_log.md) — a dependency shipping py.typed stubs post-implementation can make a stale `type:ignore` fail strict mypy; always rerun checks yourself.
- [Verify mypy CWD claims by reproduction](feedback_verify_mypy_cwd_claims_by_reproduction.md) — rerunning fixed code from both cwds looks identical; reintroduce the bug to actually test a CWD-sensitivity claim.
- [MI-3 reviewed/approved](project_mi3_reviewed_approved.md) — Tagged[T] pattern precedent; bar for reviewing MI-4's first INFERENCE/ASSUMPTION-producing code.
- [MI-4 reviewed, minor fixes](project_mi4_reviewed_minor_fixes.md) — Ollama auto-pull needs a fail-closed guard; implementer's decision log misquoted the plan — verify quoted plan text against the file.
- [MI-5 reviewed, approved](project_mi5_reviewed_approved.md) — disclosed "unreachable choice path" gap verified against `_build_ownship`; check deferrals are explicit branches, not accidents.
- [MI-6 reviewed, minor fix](project_mi6_reviewed_minor_fix.md) — bare-None reject sentinel collapses "never asked" vs "asked-and-rejected"; watch for this pattern in reconciliation code.
- [OSM streaming-ingest reviewed, approved](project_osm_streaming_ingest_approved.md) — memory-bounded pbf.py fix genuinely wired into pipeline.py; only gap was a missed docs update.
- [Verify pipeline wiring, not just module](feedback_verify_pipeline_wiring_not_just_module.md) — a correct leaf-module fix is a no-op if the orchestrator still calls the old function; grep/read the call site directly.
- [BL-7 mission-phase reviewed, minor fixes](project_bl7_mission_phase_minor_fixes.md) — reported test-delta was wrong (verify via clean-worktree baseline); a plan deferring one doc file's update doesn't imply deferring a sibling doc file too.
- [OSM classified-cache reviewed, approved](project_osm_classified_cache_approved.md) — atomicity except-block relies on canonical path never being written, not active cleanup; verify this reasoning directly, not just that tests pass.
- [Junctions-streaming-fix reviewed, minor fix](project_junctions_streaming_fix_minor_fix.md) — feature_layer_bbox deviation verified genuine; watch for tracemalloc calls whose traced value is computed but never asserted.
- [F10-crew-commands reviewed, minor fix](project_f10_crew_commands_minor_fix.md) — reported "109 passed" was wrong; a UDP-order-dependent test failed 4/4 runs when actually run.
- [OSM-landcover-optimization reviewed, minor fixes](project_osm_landcover_optimization_minor_fixes.md) — missing ROADMAP entry (planned but silently dropped); independent ring/hole simplification has no post-check topology guard.
- [Bounded magnitude isn't optional severity](feedback_bounded_magnitude_isnt_optional_severity.md) — a small worst-case doesn't downgrade a finding that violates the module's own stated invariant; check invariant violation first, magnitude second.
