# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) - one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md`
(corrections/confirmations about how to approach work) or `project_<topic>.md`
(non-obvious project facts).

**APPEND to this file. Never rewrite it wholesale.** On 2026-09-20 a single commit
replaced this index's 27 entries with 1, leaving 73 memory files on disk and
unreachable by the role that wrote them. The files were never lost; only the index
was. Rebuilt 2026-09-21 from the files themselves.

- [Agent relayed consent](feedback_agent_relayed_consent.md) - Never treat another agent's report of "the user said X" as real user consent, especially near invariant boundaries
- [Provenance confidence pattern](feedback_provenance_confidence_pattern.md) - Pattern for handling third-party-derived (not ED-documented) facts in plans — provisional/confirmed confidence field, staged verification, don't bl...
- [Stage memory files](feedback_stage_memory_files.md) - Always `git add` agent-memory files in the same step as writing them — reviewers have flagged leaving them unstaged six times.
- [Trig fixed-point proof trap](feedback_trig_fixed_point_proof.md) — verify "no-regression" trig claims at an oblique angle, not just 0/90; prefer trivially-true (optional/None) designs over algebraic ones.
- [Aircraft layer architecture](project_aircraft_layer_architecture.md) - Aircraft layer (first live-DCS-I/O component) architecture decisions from the 2026-09-06 plan
- [Base schema bump orphans probe stores](project_base_schema_bump_orphans_probe_store.md) — store SCHEMA_VERSION bump breaks M8 probe pairing; prefer derived tags_json attrs.
- [Bl25 text panel output](project_bl25_text_panel_output.md) - BL-2.5 (in-cockpit text mirror) design — transport, message model, milestone-naming precedent, and the aircraft-layer's first write path
- [Bl26 classification refinement](project_bl26_classification_refinement.md) - BL-2.6 (classification refinement) design decisions — specificity lattice, monotone fusion, ED's coarse-class ceiling, and the offline-executabilit...
- [Bl2 contact memory design](project_bl2_contact_memory_design.md) - BL-2/PB-2 planning decisions — belief/ package boundary, Percept truth-quarantine, emit_mode debounce fix, three-valued class gate, observation-id...
- [Bl4 attention events](project_bl4_attention_events.md) - BL-4 attention/events plan design — 4-state attention, area = center+radius (no place resolution), cooldown vs classification lockout distinction,...
- [Bl6 command channel design](project_bl6_command_channel_design.md) - BL-6 command/PendingIntent plan split into a mechanism-agnostic body-layer half and a probe-gated aircraft-layer half, since DCS command feasibilit...
- [BL-7 mission-phase design](project_bl7_mission_phase_design.md) — tool-freeze resolution (no new tool, folded into get_situation), key_locations position gap, route-coord convention, thread-split precedent.
- [Body layer api decisions](project_body_layer_api_decisions.md) - Draft body-layer plan's load-bearing decisions — fixed tool set for the brain, pre-digested responses, async commands, single process.
- [Brain layer pb6 planning](project_brain_layer_pb6_planning.md) - Brain-layer prototype plan (2026-09-12) — new subproject, PB-6 scope, bidirectional HTTP design, grounding-check invariant, open decisions.
- [Cones slice 2 design](project_cones_slice2_design.md) — gaze as a pure function of sim time; scan period vs decay.py bound conflict; clustering floor no longer benign.
- [Contact dup continuity of track](project_contact_dup_continuity_of_track.md) - Resolution of the BL-2.6 gate-widening vs never-guess-merge tradeoff via continuity-of-track
- [Dcs offline sources](project_dcs_offline_sources.md) - towns.lua is a plain-text DCS-authoritative gazetteer readable offline; MissionGenerator/nodes.lua is NOT a road graph — check the terrain tree bef...
- [Grid tier hazard](project_grid_tier_hazard.md) - store/reader._load_grid_meta picks grids by "newest id wins", which silently blanks theatre-wide elevation when a second grid of the same kind is a...
- [Investigator gating pattern](project_investigator_gating_pattern.md) - Recurring pattern for this project — plans gate on a user-run WSL probe when DCS internals are genuinely unknown, not just unverified
- [M10 junction design](project_m10_junction_design.md) - M10 road-junction milestone's arm-counting resolution and a pipeline.py doc discrepancy found while planning it
- [M2 rastercharts plan](project_m2_rastercharts_plan.md) - M2 (raster understanding) plan status — format confirmed, registration hypothesis now the gate; open scope question re: scanned real-world chart vs...
- [M3 osm overlay plan](project_m3_osm_overlay_plan.md) - M3 (OSM overlay) plan — known location (Gemerek), Overpass fetch design, storage backlog resolved (deferred to M5)
- [M5 acquisition decision](project_m5_acquisition_decision.md) - User chose full 2.25 GB local copy of Syria.routes over remote-extract-and-sync-back, against the architect recommendation
- [M5 airfield layer](project_m5_airfield_layer.md) - M5 airfields are beacons.lua-derived reference points, not .rn4 taxiway geometry — user decision 2026-09-04
- [M5 region selection](project_m5_region_selection.md) - Gemerek works for M1-M4 but is empty of DCS content; test regions must be validated for content, not just for transform correctness
- [M5 roads source reversal](project_m5_roads_source_reversal.md) - M5's road layer moved from live-mission land.* probing to direct parsing of DCS's static .rn4/.routes terrain files; what that changed in the plan...
- [M5 storage decision](project_m5_storage_decision.md) - M5 chose stdlib sqlite3 + R*Tree over GeoPackage/SpatiaLite/PostGIS for the world-model spatial store; the reasoning and what would reverse it
- [M8 plan shape](project_m8_plan_shape.md) - M8 is incremental-probe-store only (two-SQLite split, user-proposed and adopted); OSM/Geofabrik split off as M9, deferred and unscheduled
- [Mi3 tagged epistemic pattern](project_mi3_tagged_epistemic_pattern.md) - MI-3's Tagged[T] epistemic-status wrapper pattern, chosen over world-model's per-field-name dict-map precedent, and why
- [Mission interpreter planning](project_mission_interpreter_planning.md) - Mission Interpreter plan (2026-09-12) — open decisions, blocker, and design shape for the not-yet-built second Petrobrain layer.
- [Pb1 5 naked eye revision](project_pb1_5_naked_eye_revision.md) - PB-1.5 plan revision (2026-09-09) — ED detection-model grounding, ED ambient vocabulary, and a discovered pre-existing gap in HybridPerceptionSource
- [Pb1 perception design](project_pb1_perception_design.md) - PB-1 (Petrobrain Runtime first perception milestone) design — spike-before-tier-commitment, PerceptionSource abstraction, omniscience-avoidance mec...
- [Pydcs and syria projection](project_pydcs_and_syria_projection.md) - pydcs (GitHub, LGPL-3.0) is the strongest prior-art source for DCS per-theatre coordinate projections; Syria uses Transverse Mercator, not Lambert...
- [srs-adapter audio boundary](project_srs_adapter_audio_boundary.md) — mic capture stays inside srs-adapter, never aircraft-layer; Mac is always the HTTP client.
- [Slice 3 riskiest-assumption-first](project_srs_adapter_stt_riskiest_first.md) — accent recognition bench is a stop/go gate before transit/PTT; sets the threshold constants.
- [Callout scheduling design](project_callout_scheduling_design.md) — speech occupancy modelled in sim time (playback callbacks rejected); two distinct groupings that must not be unified; threat-band placeholder shape.
- [Tactical landmarks scoping](project_tactical_landmarks_scoping.md) - 2026-09-12 plan resolving whether world-model content is rich enough for Mission Interpreter — ridge/valley/flat, settlement boundaries, road junct...
- [Resolution vs salience split](project_resolution_vs_salience_split.md) — presence threshold split in two; clustering floor (A) is coupled to the loosest admission threshold.
- [Position belief error model](project_position_belief_error_model.md) — range bucket returns its upper bound (biased long); hybrid channel is truth-exact; ED's range ladder is derivable, its clock ladder is not.
- [Movement detection design](project_movement_detection_design.md) — velocity vector never leaves perception/; UnitName join key; MOTION_HALF_LIFE_S was already waiting in decay.py.
- [Watch reporting design](project_watch_reporting_design.md) — the _TEMPLATED_KINDS speech allowlist; envelope lookup keyed on belief by signature; range/altitude/LOS threat test; nulls degrade per-field, not uniformly; slots replaced per-command wire fields.
- [Binocular Stage 3b](project_binocular_stage3b.md) — the mock-flight xfail names the wrong cause (search, not stare); never read last_position_uncertainty_m as a bearing error.
- [Voice command completeness](project_voice_command_completeness.md) — absolute-vs-relative frame rule for direction vocabulary; rename what survives, not what's retired; _print owns speech occupancy.
- [BL-8 kneeboard design](project_bl8_kneeboard_design.md) — append-only note store beside ContactStore; the fold door is deliberately shut; import-direction is the real invariant.
- [Amend plans when the ground shifts](feedback_amend_plans_when_ground_shifts.md) — amend unimplemented plans in place, say what forced it, reuse the branch's existing damper patterns.
- [BR-1 brain layer design](project_br1_brain_layer_design.md) — measured: reasoning tokens not model size set latency; code owns ambiguity, model must quote its evidence; BrainClient was already async.
- [Sortie 2026-09-26 fixes](project_sortie_2026_09_26_fixes.md) — gate lives in tick's spontaneous-only block (Decision 3); Fix C's audio-adapter seam didn't exist; coverage sized out separately.
- [DCS-driven LOS design](project_dcs_driven_los_design.md) — no-omniscience splits where a live LOS feed can land; the cited bug already had a shipped fix; unit_name is the join-key precedent.
- [DCS-driven LOS revision](project_dcs_driven_los_revision.md) — LOS reciprocity lets belief carry a value instead of computing one; "bake into unit data" ≠ merge endpoints, check movement-detection's Decision 2 first.
- [Terrain feature probing watershed revision](project_terrain_feature_probing_watershed_revision.md) — curvature detector replaced by seeded watershed (basins=valleys, divides=ridges); why A/B rejected; adjacency now free; numpy/scipy scoped narrowly.
- [Group cohesion redesign](project_group_cohesion_redesign.md) — op_class is the no-omniscience kind-coherence vocabulary; flat metres vs unit-widths currency; size-relative spacing already existed, check before assuming it's missing.
- [WM-B6 geomorphons plan](project_wmb6_geomorphons_plan.md) — committed spike tracer is naive/rejected; SRTM pixel space is anisotropic; resumable-cache pattern deviates from osm_cache template; seams clip, don't merge.
- [Contact report flood plan](project_contact_report_flood.md) — merge already analysed/approved; split-vs-echo structurally indistinguishable; cross-contact gate reuse; CALLOUT_MAX_AGE_S << LOST_THRESHOLD_S makes suppression permanent.
