# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [No dep tooling in world-model](project_worldmodel_no_dep_tooling.md) — no venv/lockfile existed before M1; create `world-model/.venv` ad hoc, use pytest `pythonpath` ini for src/tests imports.
- [Verify full suite, not just new files](verify_full_suite_not_just_new_files.md) — ruff check can flag pre-existing drift in untouched files; fix in its own small commit.
- [Append, don't overwrite implementation.md](feedback_implementation_log_append.md) — multi-stage plans share one implementation.md; read/append, never replace.
- [world-model mypy_path needs cwd=world-model/](project_worldmodel_mypy_path_cwd.md) — strict-checking tools/tests imports (raster, coordinates) fails from repo root; cd into world-model/ first.
