# Memory Index

- [PB-2 belief invariants](project_pb2_belief_invariants.md) — no truth fields in belief/, no gating tiebreak; re-grep every future stage review.
- [PB-2 placeholder constants](project_pb2_placeholder_constants.md) — SCOPE_UNCERTAINTY_M/GATE_GROWTH_RATE_MPS are documented placeholders, not tuned values.
- [PB-2 ContactStore thread safety](project_pb2_contactstore_thread_safety.md) — accessors return copies, so unlocked poll/REPL threads are safe from crashes; check copy-vs-reference before flagging.
