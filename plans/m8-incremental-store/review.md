### Review Summary

Reviewed commit `8e5ac81` on `feature/m8-incremental-probe-store` against
`plans/m8-incremental-store/plan.md` (final) and `world-model/CLAUDE.md` /
`docs/CONVENTIONS.md`.

Verified commands myself on this commit (not trusted from the implementer's report):

- `ruff format --check world-model/src world-model/tests` — pass (79 files), from both
  `world-model/` and repo-root cwd.
- `ruff check world-model/src world-model/tests` — pass, from both cwds (no isort-order
  flip this time — see prior memory on cwd-dependent I001).
- `mypy --strict world-model/src` — pass, 47 source files.
- `pytest world-model/tests -q` — pass, 241 passed.
- `git status` — clean; all new files (including both agent-memory files) are in the single
  commit, no unstaged stragglers.

Per-item findings against the plan:

1. **Base store untouched** — CONFIRMED. `git diff main..feature -- store/writer.py
   store/schema.py store/reader.py` is empty (zero lines). `build_region` itself is
   untouched; `pipeline.py`'s diff is additive-only (new imports + one new `add_probe_chunk`
   function appended at end of file).
2. **Two-store separation is real** — CONFIRMED for writes. Every `probe_store/writer.py`
   function takes a direct probe-store-only connection; nothing in the write path ever
   attaches or touches the base store. Reads use `ATTACH DATABASE ... AS probe` in
   `describe_position`, `DETACH`ed in a `finally` before the function returns, and degrade
   to the pre-M8 path when `probe_db_path` is `None` or the file doesn't exist
   (`test_describe_position_absent_probe_store_behaves_exactly_as_before` proves byte-identical
   output on every field but the new `coverage` field). See Required Fix #1 below for a gap
   in this story's failure-mode handling, not the happy path.
3. **Locked params** — CONFIRMED. `CHUNK_SIZE_M = 5000.0` (`store/chunks.py`),
   `PROBE_SPACING_M = 100.0` (`probe_store/schema.py`), divisibility asserted at import time.
4. **Coverage tri-state is total** — CONFIRMED. `chunk_status` never returns `None`
   (`ChunkStatus.UNQUERIED` on absent row), keyed `(kind, chunk_ix, chunk_iz)` throughout
   schema/writer/reader. `QUERIED_VOID` vs `UNQUERIED` distinction has a real test
   (`test_chunk_status_reports_queried_void_distinct_from_unqueried`).
5. **`UNIQUE(kind)` + extensibility test** — CONFIRMED. DDL has `kind TEXT NOT NULL UNIQUE`
   on `grid`. `test_extensibility_new_raster_and_vector_kind_need_no_schema_change` genuinely
   proves the claim: registers an invented raster kind and an invented vector kind through the
   exact same generic `upsert_grid_samples`/`replace_chunk_features`/`upsert_chunk_coverage`
   paths, confirms round-trip reads, confirms no cross-kind bleed on re-probe, and confirms
   via `sqlite_master` introspection that no table/column was added for either invented kind.
   Both invented kinds are test-only, never referenced in `src/`.
6. **R\*Tree row-count parity** — CONFIRMED with a real forcing test, not just an assertion in
   prose. `test_replace_chunk_features_roundtrip_and_bbox_parity` and
   `test_replace_chunk_features_replaces_not_accumulates` both assert `feature` and
   `feature_bbox` row counts stay equal (1 and 1, not 1 and 2) across a re-probe, which would
   fail if `replace_chunk_features`'s delete-then-reinsert ever missed the bbox side.
7. **Drift-detection** — PARTIALLY CONFIRMED, with a real gap. Write-side drift detection
   (`probe_store.writer.open_probe_store`, used by `build.pipeline.add_probe_chunk`) is
   genuinely tested and correct: mismatched `theatre`, `base_schema_version`, and
   `chunk_size_m`/`probe_spacing_m` each raise `ValueError` on reopen
   (`test_open_probe_store_raises_on_*`). **However, the read/query path
   (`query.describe.describe_position`'s `ATTACH`) only checks `check_probe_schema_version`
   — it never compares the attached probe store's `theatre`/`chunk_size_m`/`probe_spacing_m`
   meta against the base store currently being queried.** I reproduced this directly: built a
   base store for `theatre="Syria"`, attached a probe store created with `theatre="Kola"` (same
   schema version) via `probe_db_path`, and `describe_position(conn, "Syria", ...)` silently
   returned the Kola probe store's value (`dcs_m=999.0`, `source="probe"`,
   `coverage="queried_with_data"`) with no error and no signal. This is exactly the scenario the
   plan's "Risks & Unknowns" names as "the main new risk the split introduces" and says "needs
   an explicit test" — the test exists for the write path but not the read path, and the
   read path's actual behavior contradicts `docs/M8_PROBE_STORE.md`'s "Drift protection"
   section, which states the drift check applies without qualifying that it's write-path-only.
   See Required Fix #1.
8. **`describe_position` probe-then-base fallback control-point test** — CONFIRMED, and a
   good test: `test_describe_position_probe_store_answers_inside_probed_cell_falls_back_outside`
   checks the probe value at the one written cell, the base grid's (different) interpolated
   value 250 m away in the same chunk, correct `source` label on each, and that `coverage`
   correctly reports the chunk-level status even for the point the probe grid didn't have data
   at exactly. Absent-probe-store behavior is separately proven byte-identical.
9. **No live-DCS dependency** — CONFIRMED. `ingest_probe_chunk`/`ingest_terrain_chunk` and all
   new tests operate on synthetic fixture files/in-memory data;
   `tools/measure_m8_probe_chunk_perf.py` builds a synthetic base store directly via
   `store.writer` rather than running any live probe.
10. **Scope** — CONFIRMED. No Petrobrain Runtime code anywhere in the diff. No base-store
    per-layer append (`store/writer.py` untouched, as noted in #1). `add_probe_chunk` has
    deliberately no CLI wrapper, correctly deferred per the plan and documented as such.

### Required Fixes

- **Read-path drift detection is incomplete — a probe store built for a different theatre (or
  a different chunk/probe-spacing lattice) is silently accepted by `describe_position` and
  answers as if valid.** Only `check_probe_schema_version` runs on the `ATTACH`ed connection;
  `theatre`/`chunk_size_m`/`probe_spacing_m` meta are never compared against what the caller is
  actually querying. I reproduced this concretely (see item 7 above) — a "Kola" probe store
  attached while querying a "Syria" base store returns a fabricated-looking answer
  (`source="probe"`, `coverage="queried_with_data"`) with zero signal that anything is wrong.
  This directly violates the plan's explicit "opening a mismatched pair must fail loudly" risk
  mitigation and the project's "code owns factual state, never fabricates" / provenance
  invariants — a wrong-theatre or stale-lattice pairing should degrade to base-only with a
  visible signal (or raise), not answer with cross-theatre data labeled as if it came from the
  correct probe store. Fix: read the probe store's `meta` (theatre at minimum; ideally
  chunk_size_m/probe_spacing_m too) in `describe_position`'s `ATTACH` block and treat a mismatch
  the same way a bad schema version is treated (detach, fall back to base-only) — with a test
  proving it. `docs/M8_PROBE_STORE.md`'s "Drift protection" section should also be corrected —
  it currently states the check runs on "every subsequent `open_probe_store` call" without
  noting that `describe_position`'s direct `ATTACH` never goes through `open_probe_store` at
  all, so the stated protection does not actually cover the read path.

### Optional Refinements

- `probe_store/writer.py`'s `insert_source` duplicates `store.writer.insert_source`'s body
  verbatim rather than sharing it, with a docstring explaining why (distinct tables in distinct
  files). This is a reasonable call given the two-store isolation goal, but if a third near-
  identical `insert_source` ever shows up, it's worth extracting a shared helper parameterized
  by table name rather than triplicating. Not worth doing now for two copies (optional).
- `add_probe_chunk` in `pipeline.py` has some repetition between the elevation/surface_type
  coverage-marking blocks and the ridge/valley coverage-marking blocks (four near-identical
  `upsert_chunk_coverage` call pairs). Readable as-is and each block is short; a small
  `_mark_coverage(conn, kind, ix, iz, has_data)` helper would trim ~10 lines but isn't required
  (optional).

### Verdict

NEEDS REVISION — one required fix (read-path drift detection gap in `describe_position`,
demonstrated with a reproducing script, not merely theoretical). Everything else specified in
the plan — base-store isolation, two-store write separation, locked parameters, coverage
tri-state, `UNIQUE(kind)` + extensibility, R\*Tree parity, write-path drift detection, the
probe-then-base control-point test, fixture-only testing, and scope boundaries — is genuinely
and correctly implemented, with real tests behind each claim rather than assertions in prose.
