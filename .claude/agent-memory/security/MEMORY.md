# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [Wire boundary: type-check not range-check](project_wire_boundary_type_check_not_range_check.md) — logger.py validates isinstance only, not value domain, across the audio-adapter<->body-layer wire; check this class of gap on future passes.
- [Elapsed-time inflation, quadratic dt composition](project_elapsed_time_inflation_quadratic_dt_composition.md) — a hold+inflate recovery pattern's time-to-recover scales ~1/poll_interval, not a fixed constant; test continuous polling, not just a single gap.
- [brain-layer wide bind, no benefit](project_brain_layer_wide_bind_no_benefit.md) — run-brain.sh overrides server.py's loopback default to 0.0.0.0 though both ends are same-box; flagged non-blocking 2026-09-25.
- [BR-1 Stage 2 Ollama trust boundary](project_br1_stage2_ollama_trust_boundary.md) — D10 CONFIRM validator checks full token set not offered vocabulary (fails safe); PICK got this right, CONFIRM didn't — check for this divergence pattern elsewhere.
- [aircraft-layer full audit 2026-09-26](project_aircraft_layer_full_audit_2026_09_26.md) — dostring_in call sites all clean (fixed literals only); recurring gap is unsupervised daemon threads, no REQUIRED FIX this pass.
- [audio-adapter full audit 2026-09-26](project_audio_adapter_full_audit_2026_09_26.md) — genuinely stdlib-only, no shell=True, no logged mic/transcript text; APPROVED, 3 RECOMMENDED (no request-size cap, unguarded Content-Length, mkstemp-reopen TOCTOU).
- [Claude setup audit 2026-09-27](project_claude_setup_audit_2026_09_27.md) — demonstrated deny-list bypasses (`rm -fr`, `git worktree remove -f`, `git -C reset --hard`) and a `..`-traversal gap in agent-memory-path-gate.sh; full report in reviews/claude-setup-security.md.
- [body-layer bounded-growth accepted pattern](project_body_layer_bounded_growth_accepted_pattern.md) — Contacts/optic-policy maps never shrink but are sortie-bounded by design; don't re-flag per-contact dict growth as new exhaustion risk.
- [LOS terrain tolerance accepted omniscience trade](project_los_terrain_tolerance_accepted_omniscience_trade.md) — 12.0 m LOS tolerance is a reviewed, user-approved relaxation; lapse condition is a pop-up-and-shoot airframe (Ka-50/Apache), not a re-flag target as-is.
- [world-model first native deps: numpy/scipy](project_world_model_first_native_deps_numpy_scipy.md) — terrain-watershed's numpy<2.5/scipy deps checked clean 2026-10-01; <2.5 ceiling is a mypy-stub pin, not security.
- [store.writer fail-closed geometry guard](project_store_writer_fail_closed_geometry_guard.md) — insert_features' new sub-2-point LineString/Polygon check aborts the whole transaction; confirmed fail-closed 2026-10-01.

- [Group cohesion redesign: reassign not accumulate](project_group_cohesion_reassign_not_accumulate.md) — new Group.last_spoken_* fields checked clean (reassigned, not unioned); installation_component fails closed.
- [Player bubble trace is local debug artifact](project_player_bubble_trace_is_local_debug_artifact.md) — PLAYER_BUBBLE trace row records a filtered-out unit but stays local-disk/read-only-join, no belief/network path; checked 2026-10-02.
- [BL-B23 contact-store-pruning security approved](project_bl_b23_contact_store_pruning_security_approved.md) — lost-contact clustering filter verified clean: memory unaffected, no false-departed claim; APPROVED 2026-10-02.
- [BL-B23 memory-vs-clustering-filter pattern](project_bl_b23_memory_vs_clustering_filter_pattern.md) — reusable check for future "filter input to O(n^2) consumer" perf fixes: trace unfiltered store stays readable, confirm consumer stays silent on shrink.
- [WM-B1 name tags not merged from raw OSM](project_wm_b1_name_tags_not_merged_from_raw_osm.md) — reserved tags dict is code-built, never spread from raw OSM tags, so no hostile-OSM-tag key collision; ingest-side Latin-1 filter is incidental, body-layer re-checks independently. APPROVED 2026-10-02.
- [terrain_cache resumable fail-closed, APPROVED](project_terrain_cache_resumable_fail_closed_approved.md) -- WM-B6 per-tile SQLite cache verified crash-safe without tmp-rename; theatre not in invalidation key mirrors pre-existing osm_cache gap, not new.
- [silence-command security approved](project_silence_command_security_approved.md) — ack-before-mute and clear-cannot-stick both checked by tracing code/exception paths, not assertion; CANCEL_TOKENS floor confirmed live on real voice path. APPROVED 2026-10-04.
- [landform-relief-gate security approved](project_landform_relief_gate_security_approved.md) — cache fail-closed on missing META_FIELDS confirmed independently; decimation deviation-check direction correct; DP O(n²) zig-zag noted non-finding (offline/trusted DEM input). APPROVED 2026-10-04.

- [contact-report-flood class-gate permissive by design](project_contact_report_flood_class_gate_permissive_by_design.md) -- contacts_plausibly_same's class check passes freely for OP_GROUPSOMETHING; inherited from already-trusted passes_gate, not a new weakness. APPROVED 2026-10-05.
- [redundant-group-disclosure approved](project_redundant_group_disclosure_approved.md) -- group-first-disclosure silencing composes safely with merge-echo suppression (per-member, not per-group); no cycle, no new dep. APPROVED 2026-10-05.
