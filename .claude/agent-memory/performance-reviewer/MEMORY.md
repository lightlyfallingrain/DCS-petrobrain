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
