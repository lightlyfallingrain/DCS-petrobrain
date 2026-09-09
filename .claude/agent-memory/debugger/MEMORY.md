# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [roadnet resync validation](project_roadnet_resync_validation.md) — container.py's envelope check missed denormalized-float garbage; fixed but resync isn't proven exhaustively safe.
- [world_objects ownship echo](project_worldobjects_ownship_echo.md) — LoGetWorldObjects includes own aircraft; new consumers must call exclude_ownship() or get a phantom contact.
- [sqlite thread affinity](project_sqlite_thread_affinity_bodylayer.md) — world-model sqlite conn is thread-affine; open+use on the same thread, and don't monkeypatch past sample_grid in tests.
