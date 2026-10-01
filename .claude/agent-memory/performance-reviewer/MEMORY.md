# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [Belief LOS call pattern](project_belief_los_call_pattern.md) — check cheap-gate/expensive-call ordering explicitly; dwell/deadband often gates the event, not the call.
- [Watch-reporting scale notes](project_watch_reporting_scale_notes.md) — AttentionArea uncaps watch count; position_uncertainty=None undercounts LOS sweep cost; git-archive harness technique for worktree branch review.
- [Brain-layer poll thread stall](project_brain_layer_poll_thread_stall.md) — poll_replies() 5s timeout: down=13ms fast, wedged=5015ms every poll sustained; empty poll 0.3ms cheap.
- [Brain-layer Stage 2 decider timeout](project_brain_layer_stage2_decider_timeout.md) — fixed & measured 2026-09-25: urllib socket timeout bounds a wedged Ollama at ~5003ms, no thread leak observed.
- [Stale worktree check first](feedback_stale_worktree_check_first.md) — an assigned worktree's HEAD can predate the task's named branch tip; verify with merge-base before trusting git log/diff.
- [Ollama deliberation chained drops](project_ollama_deliberation_chained_drops.md) — per-call timeout bounds one client's cost, not Ollama's own serialized queue; a deliberating model can chain-drop several utterances.
- [Aircraft-layer hotspots](project_aircraft_layer_hotspots.md) — Export.lua runs on DCS's thread; LoGetWorldObjects/list_indication cost unmeasured; audio queue unbounded unlike F10's.
- [Audio-adapter hotspots](project_audio_adapter_hotspots.md) — DcsPTT polls collector at 60Hz not documented 30Hz (dead constant); queues bounded correctly; readback caching already tracked in ROADMAP.
- [Claude setup overhead baseline](project_claude_setup_overhead.md) — posttooluse-mypy.sh runs whole-subproject mypy per edit, covers only 3/6 subprojects; body-layer/CLAUDE.md is ~24K tokens, largest fixed-context item.
- [Cockpit-mask gate cost](project_cockpit_mask_gate_cost.md) — measured 1.44us/contact, 0.08ms/tick at 55 contacts for the sortie-2026-09-26 observability gate; non-issue at 1Hz.
- [Optic-policy dict-copy cost](project_optic_policy_dict_copy_cost.md) — measured 0.08/0.45/1.46 ms/call at 55/300/1000 contacts for decide()'s unpruned-map copies; non-issue at this project's scale.
- [Contact ingest/association unmeasured](project_contact_ingest_association_unmeasured.md) — ingest+tick microbenchmark didn't finish in minutes at 55x500; ingest itself untouched by sortie-2026-09-26-fixes but worth a dedicated future pass.
- [Group-reporting cohesion scale](project_group_reporting_cohesion_scale.md) — measured O(n^2) _cluster_contacts: 0.6ms@52, 8.4ms@200, 54ms@500, 879ms@2000; needs 300-400+ contacts to matter.
- [Terrain watershed scaling](project_terrain_watershed_scaling.md) — full-theatre grow_basins+extract ~65-80s (vs 5.8s old curvature), 2GB RSS, mildly superlinear not linear; synthetic-terrain calibration trap noted.
- [ContactStore never pruned](project_contact_store_never_pruned.md) — _contacts has no delete path; group reconcile runs over every contact ever seen, so O(n^2) cost grows with sortie length not live count.
- [Player-bubble capped by existing gates](project_player_bubble_capped_by_existing_gates.md) — measured ~1.4% saving not ~77%; NAKED_EYE_RANGE_CAP_M/RANGE_CAP_M already rejected out-of-bubble candidates cheaply before LOS.
- [Contact-store pruning live-count axis](project_contact_store_pruning_live_count_axis.md) — BL-B23 fixed total-ever-seen growth only; simultaneous-live-count clustering is still O(n^2), unchanged, MONITOR per the earlier cohesion finding.
- [Geomorphons smoothing and memory scale](project_geomorphons_smoothing_and_memory_scale.md) — flagged thinning risk was fine; real cost is O(N^2) Chaikin deviation check + unbounded theatre-wide feature-list memory (~29GB extrapolated).
