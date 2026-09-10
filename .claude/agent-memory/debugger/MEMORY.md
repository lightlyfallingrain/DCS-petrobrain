# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [roadnet resync validation](project_roadnet_resync_validation.md) — container.py's envelope check missed denormalized-float garbage; fixed but resync isn't proven exhaustively safe.
- [world_objects ownship echo](project_worldobjects_ownship_echo.md) — LoGetWorldObjects includes own aircraft; new consumers must call exclude_ownship() or get a phantom contact.
- [sqlite thread affinity](project_sqlite_thread_affinity_bodylayer.md) — world-model sqlite conn is thread-affine; open+use on the same thread, and don't monkeypatch past sample_grid in tests.
- [association gate uncertainty](project_bodylayer_association_gate_uncertainty.md) — spatial gate must budget both incoming AND contact's stored position uncertainty; one-sided budgeting caused a duplicate-contact snowball via the ambiguity rule.
- [REPL thread sqlite reuse](project_repl_thread_sqlite_reuse.md) — logger.py's REPL thread must build its own sqlite3.Connection/EnrichmentContext, never reuse the poll thread's; recurred once after Stage 6's fix (BL-3's `enrichment` field, same bug class).
