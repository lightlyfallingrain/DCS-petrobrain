### Implementation Summary

Implemented all 5 steps of the M8 plan: the theatre-anchored chunk lattice, the probe store
(schema/writer/reader/paths), ATTACH-based probe-then-base read integration in
`query.describe.describe_position`, the `build.pipeline.add_probe_chunk` entry point (plus its
`ingest_probe_chunk`/`ingest_terrain_chunk` supporting functions), and a local performance
sanity tool. `store/writer.py`, `store/schema.py`, `store/reader.py`, and `build_region` itself
are byte-for-byte unmodified — only additive imports and one new function were appended to
`build/pipeline.py`.

### Files Changed

- `world-model/src/store/chunks.py` (new) — `chunk_index_for`/`chunk_bounds`/`chunks_covering`,
  the pure theatre-anchored chunk lattice (`CHUNK_SIZE_M = 5000.0`), anchored at the DCS x/z
  origin so a chunk index needs no store lookup and survives region redefinition.
- `world-model/src/probe_store/schema.py` (new) — DDL (`meta`, `chunk_coverage` PK
  `(kind, chunk_ix, chunk_iz)`, `grid` with `UNIQUE(kind)`, `grid_sample`, `feature` +
  `feature_bbox` R*Tree, keyed by `kind`+`chunk_ix`/`chunk_iz`) and its own
  `PROBE_SCHEMA_VERSION`. Also owns `PROBE_SPACING_M = 100.0` and the
  `CHUNK_SIZE_M % PROBE_SPACING_M == 0` assertion (imports `CHUNK_SIZE_M` from `store.chunks`).
- `world-model/src/probe_store/models.py` (new) — `ChunkStatus` enum (`UNQUERIED` /
  `QUERIED_WITH_DATA` / `QUERIED_VOID`) and `Chunk`. `Source`/`StoredFeature` are reused from
  `store.models`, not duplicated.
- `world-model/src/probe_store/writer.py` (new) — `open_probe_store` (create-on-first-use, not
  delete-and-recreate; verifies theatre/chunk_size_m/probe_spacing_m/base_schema_version
  identity meta on reopen and raises `ValueError` on any mismatch), `insert_source`,
  `upsert_chunk_coverage`, `upsert_grid_samples` (one grid per `kind`, anchored at `(0, 0)`,
  `executemany` upsert), `replace_chunk_features` (delete+reinsert `feature`+`feature_bbox` in
  one transaction, scoped by `kind`+chunk).
- `world-model/src/probe_store/reader.py` (new) — every function takes a `schema` parameter
  (default `"main"`) so the same code reads a bare probe-store connection or one where the
  probe store has been `ATTACH`ed under an alias. `chunk_status` (never returns `None`),
  `chunks_in_bbox`, `sample_probe_grid` (nearest-cell only, deliberately not bilinear — see its
  docstring), `grid_spacing_m`, `load_chunk_elevation_window` (chunk + 1-cell border, for
  `ingest_terrain_chunk`).
- `world-model/src/probe_store/paths.py` (new) — `probe_store_path`, the one place mapping
  `<region>.sqlite` -> `<region>-probe.sqlite`.
- `world-model/src/query/describe.py` — added optional `probe_db_path: Path | None` parameter.
  When given and present, `ATTACH`es the probe store as alias `"probe"` for the call, tries
  `sample_probe_grid`/`chunk_status` first for `elevation`/`surface_type`, falls back to the
  existing base-store path otherwise. Added `coverage: str` field to `ElevationInfo` and
  `SurfaceTypeInfo` (`"no_probe_store"` when no probe path given/absent, else the chunk's
  `ChunkStatus.value`). `source`/`provenance` report `"probe"` when the probe store answered.
  `store/reader.py` needed no change.
- `world-model/src/build/ingest_probe.py` — added `ingest_probe_chunk` +
  `ChunkProbeIngestStats`. Unlike `ingest_probe`, points are not `r{row}c{col}`-named against a
  caller-supplied grid shape; `(row, col)` is derived directly from each point's absolute
  `(x, z)` (`round(x / probe_spacing_m)`), matching the probe store's single theatre-wide sparse
  grid per kind. Raises `ValueError` if a point falls outside the claimed chunk's bounds.
- `world-model/src/build/ingest_terrain.py` — added `ingest_terrain_chunk`, a thin
  chunk-scoped wrapper that calls the existing `ingest_terrain` unchanged. No new logic was
  needed: `load_chunk_elevation_window`'s 1-cell border is exactly what lets
  `terrain.curvature.classify_curvature`'s existing edge-exclusion rule guarantee every
  produced feature comes from the chunk's own interior, never a border cell.
- `world-model/src/build/pipeline.py` — added `add_probe_chunk` + `ProbeChunkReport`. Opens the
  base store **read-only** (`open_region_db`) only to confirm `SCHEMA_VERSION` and read
  `theatre`; every write goes to the probe store. `build_region` itself is unmodified.
- `world-model/tools/measure_m8_probe_chunk_perf.py` (new) — local-only perf sanity per plan
  step 5 (not a full-theatre run): builds a synthetic base store via `store.writer` directly
  (bypassing `parse_towns_lua`'s exact-count guard, which a throwaway perf fixture can't
  satisfy), writes a full 2,601-point chunk fixture at the locked production defaults, times one
  `add_probe_chunk` call and 100 `describe_position` calls with the probe store attached.
- `world-model/docs/M8_PROBE_STORE.md` (new) — two-file model, lifecycle, backup/sync
  implication, drift protection, and the perf numbers below.
- `world-model/CLAUDE.md` — added the M8 two-store Tech Stack entry.

### Tests Added

- `tests/test_store_chunks.py` — chunk index/bounds for positive and negative coordinates
  (Syria's SW quadrant), the `chunk_size_m % probe_spacing_m == 0` invariant, the
  `chunk_index_for(centre_of(chunk_bounds(ix, iz))) == (ix, iz)` round-trip (parametrized over 5
  index pairs including negatives), `chunks_covering` for a single chunk and a multi-chunk
  span, and a degenerate-bbox `ValueError`.
- `tests/test_probe_store.py` (19 tests) — `open_probe_store` create-vs-reopen, accumulation
  across reopens, drift detection (theatre / base_schema_version / chunk_size_m mismatch each
  raise), `chunk_status` tri-state semantics (absent → `UNQUERIED`, `QUERIED_VOID` distinct from
  `UNQUERIED`, scoped by `kind`), `chunks_in_bbox`, grid sample round-trip (re-upsert doesn't
  double `grid_sample` row count), spacing-change guard, `replace_chunk_features` R*Tree
  row-count parity, replace-not-accumulate, cross-kind/cross-chunk isolation, kind-mismatch
  guard, `load_chunk_elevation_window` shape/border/None-handling, and the extensibility test
  (an invented raster + vector kind through the exact same generic paths, with a
  `sqlite_master` introspection assertion that no table/column was added for them).
- `tests/test_probe_chunk_pipeline.py` (5 tests) — full `add_probe_chunk` wiring against a
  synthetic 3x3 chunk fixture (deliberately smaller than the locked 51x51 production default,
  per this project's "decouple fixtures from tuned defaults" convention): grid+coverage+terrain
  feature ingestion end to end, base store provably untouched (mtime + region row unchanged),
  `QUERIED_VOID` coverage for an empty chunk output, `ValueError` on a point outside the claimed
  chunk, and accumulation across two separate `add_probe_chunk` calls.
- `tests/test_describe_position.py` (+4 tests) — probe-then-base fallback control-point test
  (probe value inside the one written cell, base grid's interpolated value elsewhere in the same
  chunk), absent-probe-store-path behaves exactly as before, and no-probe-store-at-all reports
  `coverage="no_probe_store"` honestly.

### Checks

- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass
- `mypy world-model/src` (strict, run with `cwd=world-model/`): pass, 47 source files
- `pytest world-model/tests -q`: pass, 241 passed (up from 233 before this milestone)
- `tools/measure_m8_probe_chunk_perf.py` also individually format/lint/mypy-strict clean (not
  in the mandated command list, checked anyway per project convention for new tool files)

### Notable Discoveries

- **`sample_probe_grid` is deliberately nearest-cell only, never bilinear**, unlike the base
  store's `sample_grid`. The base store's grid is dense and whole-region, so a 2x2 interpolation
  window is always fully sampled; the probe store's grid is sparse by construction (filled
  chunk by chunk), so an unwritten neighbour is the *common* case, not an edge case — bilinear
  interpolation there would silently blend a real reading with a fabricated one. This wasn't
  called out explicitly in the plan; it follows directly from the "code owns factual state,
  never fabricates" invariant once the sparse-grid shape is taken seriously.
- **The chunk-scoped terrain classifier needed no new curvature/features logic at all** — only
  a thin naming wrapper (`ingest_terrain_chunk`) plus a window-loading function in
  `probe_store/reader.py`. `terrain.curvature.classify_curvature`'s existing rule (skip any cell
  without a full 4-neighbour window) already guarantees that a "chunk + 1-cell border" window
  can only ever classify the chunk's own interior cells — border cells never qualify because
  *their* outward neighbour (2 rings out) is never in the window. This made the M6 code reuse
  the plan called for ("a scope reduction, not a redesign") exactly as clean as advertised.
  `test_probe_chunk_pipeline.py`'s single-cell valley fixture confirms this concretely: the one
  cell classified in a 3x3 chunk needs zero cross-chunk border data because its own 4 neighbours
  are all inside the same chunk.
- **Real perf numbers from `tools/measure_m8_probe_chunk_perf.py`** (Apple Silicon Mac, local
  disk, single run): ~23 ms for one full 2,601-point `add_probe_chunk` call (parse + two grid
  upserts + chunk-scoped ridge/valley classification), ~0.4 ms mean / ~0.4 ms p95 for a
  probe-attached `describe_position` call. Both are far under the ~72 s a Mi-24 at 250 km/h
  takes to cross one 5 km chunk, so no throttling/batching concern surfaced at this scale — a
  question the plan explicitly left open ("probe throttling or look-ahead policy" is out of
  scope) and this doesn't need to reopen it, but it's a reassuring data point for whoever picks
  that up later.
- **`parse_towns_lua`/`parse_beacons_lua`'s exact-count guard (from M7) blocks any script that
  wants a throwaway base store without going through `pytest`'s monkeypatch fixture.**
  `tools/measure_m8_probe_chunk_perf.py` works around this by building its base store directly
  via `store.writer.open_for_build`/`insert_region` rather than `build.pipeline.build_region` —
  the same direct-writer pattern `test_describe_position.py`'s `_fixture_conn` already uses, just
  outside `pytest`.
- **No deviations from the plan.** All five Implementation Plan steps, the required test list,
  the drift-detection test, and the R*Tree row-count-parity test were all implemented as
  specified; `store/writer.py`/`store/schema.py`/`store/reader.py`/`build_region` are untouched.

### Post-review fix (Required Fix #1, `plans/m8-incremental-store/review.md`)

Reviewer found and reproduced a real gap: `describe_position`'s `ATTACH` block only ran
`check_probe_schema_version` on the probe store, never comparing `theatre`/`chunk_size_m`/
`probe_spacing_m`/base schema version against the base store actually being queried. A probe
store built for a different theatre (or a stale chunk lattice), with a matching
`PROBE_SCHEMA_VERSION`, was silently accepted and answered as if correct — exactly the "opening
a mismatched pair must fail loudly" risk the plan's "Risks & Unknowns" names as the main new
risk of the two-store split, and the write path (`open_probe_store`) already had this check
while the read path didn't.

Fix:
- `probe_store/schema.py` — added `check_probe_paired_with_base(conn, theatre, chunk_size_m,
  probe_spacing_m, base_schema, probe_schema)`, the read-path counterpart to
  `open_probe_store`'s drift check. Compares the attached probe store's identity meta against
  `theatre`/the locked chunk-lattice defaults, and its recorded `base_schema_version` against
  `base_schema`'s own live `schema_version` (read directly off the base connection, so it
  reflects the actual store being queried, not a hardcoded constant). Raises `ValueError` on any
  mismatch, mirroring `open_probe_store`'s error shape. Extracted `IDENTITY_META_KEYS` as a
  shared tuple so `writer.open_probe_store` and this new function can't drift apart on which
  keys "identity" means (`writer.py`'s previously-private `_META_KEYS` now imports this).
- `query/describe.py` — `describe_position`'s `ATTACH` block now calls
  `check_probe_paired_with_base` immediately after `check_probe_schema_version`, inside the same
  `try`/`except ValueError` that already existed for the schema-version check — a mismatch on
  either detaches and falls back to base-only, exactly like a missing probe store file. No
  change to the happy path or to any existing test's expected output.
- `tests/test_describe_position.py` — added three tests reproducing the reviewer's exact
  scenario and two siblings: wrong theatre (`"Kola"` probe attached while querying a `"Syria"`
  base store, matching schema version), wrong `chunk_size_m`, and a stale recorded
  `base_schema_version`. Each asserts the probe value is never returned and `coverage` reports
  `"no_probe_store"`, i.e. degrade-to-absent, not a crash and not a fabricated answer.
- `docs/M8_PROBE_STORE.md` — "Drift protection" section rewritten to describe both the write
  path and the read path explicitly (it previously only described the write path, which is what
  the reviewer flagged as an overstatement of actual coverage).

Did not implement the two review-flagged **optional** refinements (`insert_source` duplication,
`add_probe_chunk`'s coverage-marking repetition) — reviewer explicitly marked both non-blocking
and "not worth doing now" / "isn't required," and the coordinator's instruction was to fix them
"only if trivial, not required." Left as-is to keep this fix commit scoped to the required item.

Re-ran the full check suite after the fix: `ruff format --check`, `ruff check`, `mypy --strict
world-model/src` (47 files), `pytest world-model/tests -q` — **244 passed** (up from 241; the
three new drift tests), all green.
