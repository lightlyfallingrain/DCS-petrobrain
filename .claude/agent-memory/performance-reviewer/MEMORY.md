# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [Belief LOS call pattern](project_belief_los_call_pattern.md) — check cheap-gate/expensive-call ordering explicitly; dwell/deadband often gates the event, not the call.
- [Watch-reporting scale notes](project_watch_reporting_scale_notes.md) — AttentionArea uncaps watch count; position_uncertainty=None undercounts LOS sweep cost; git-archive harness technique for worktree branch review.
- [Brain-layer poll thread stall](project_brain_layer_poll_thread_stall.md) — poll_replies() 5s timeout: down=13ms fast, wedged=5015ms every poll sustained; empty poll 0.3ms cheap.
- [Brain-layer Stage 2 decider timeout](project_brain_layer_stage2_decider_timeout.md) — per-/escalate worker thread unbounded; needs Ollama call timeout before Stage 2 or threads/stalls leak.
