# Memory Index

- [PB-2 belief invariants](project_pb2_belief_invariants.md) — no truth fields in belief/, no gating tiebreak; re-grep every future stage review.
- [PB-2 placeholder constants](project_pb2_placeholder_constants.md) — SCOPE_UNCERTAINTY_M/GATE_GROWTH_RATE_MPS are documented placeholders, not tuned values.
- [PB-2 ContactStore thread safety](project_pb2_contactstore_thread_safety.md) — accessors return copies, so unlocked poll/REPL threads are safe from crashes; check copy-vs-reference before flagging.
- [PB-2 Stage 5 fusion finding](project_pb2_stage5_fusion_finding.md) — certainty/classification confirmed last-writer-wins, tracked in todo.md backlog; PB-2/BL-2 fixture-testable work now complete.
- [PB-2 review log append-only](project_pb2_review_log_append_only.md) — review.md accumulates per-stage sections; always append (Edit), never Write-overwrite — did this wrong once, recovered via git.
- [DCS Lua static review technique](project_dcs_lua_static_review_technique.md) — diff unverified Hook/.dlg artifacts against real installed SRS/DCS reference files under $DCS_INSTALL_PATH before calling something "unreviewable."
