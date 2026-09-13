### Implementation Summary

Implemented the full plan: a new `world-model/src/osm_cache/` package (schema/models/writer/
reader/paths/hashing, mirroring `probe_store/`'s layout), a `CLASSIFIER_VERSION` constant next to
`build.ingest_osm._classify_way`, and `build.pipeline.build_region`'s `osm_pbf_path` branch now
forks on a cache-hit check before parsing. All 6 implementation-plan steps completed; all tests
pass; both mandated Steps 6/7 items (perf tool, docs) done.

### Files Changed

- `world-model/src/osm_cache/__init__.py` — package docstring.
- `world-model/src/osm_cache/schema.py` — `OSM_CACHE_SCHEMA_VERSION`, DDL (`meta` + `feature`
  tables, no `feature_bbox`), `META_FIELDS`/`STATS_META_KEY` shared constants (public, not
  underscore-prefixed, so `writer.py`/`reader.py` can't drift on the key list — same pattern as
  `probe_store.schema.IDENTITY_META_KEYS`).
- `world-model/src/osm_cache/models.py` — `OsmCacheMeta` frozen dataclass and
  `cache_meta_matches(stored, expected)`, which checks only the invalidation-key fields
  (excludes `built_at`).
- `world-model/src/osm_cache/hashing.py` — `sha256_file`, streamed in 1 MiB chunks.
- `world-model/src/osm_cache/paths.py` — `osm_cache_store_path`, `osm_cache_tmp_path`.
- `world-model/src/osm_cache/writer.py` — `open_osm_cache_for_populate` (deletes a stale `.tmp`
  first), `insert_cached_features`, `finalize_cache` (writes meta+stats, closes the connection,
  `os.replace`s to the canonical path).
- `world-model/src/osm_cache/reader.py` — `load_cache_meta` (absence-as-absence), `load_cached_stats`,
  `iter_cached_features` (batched, `source_id`/`id` always `None` on the way out).
- `world-model/src/build/ingest_osm.py` — added `CLASSIFIER_VERSION = 1` next to `_classify_way`.
- `world-model/src/build/pipeline.py` — the `osm_pbf_path` branch now computes `expected_meta`
  (bbox + `CLASSIFIER_VERSION` + `OSM_CACHE_SCHEMA_VERSION` + a streamed `sha256_file`), looks up
  `osm_cache_store_path(out_path)`, and forks: cache hit reads cached batches, retags `source_id`,
  and calls the existing `insert_features` per batch (no ATTACH/bulk-SQL); cache miss runs the
  existing streaming parse unchanged except each flushed batch also calls
  `insert_cached_features` against a `.tmp`-path connection, with `finalize_cache` called once
  after the pass succeeds. A `try/except BaseException` around the miss path closes the
  population connection and re-raises on any failure, leaving no file at the canonical cache path.
- `world-model/docs/M9_OSM_RUN_INSTRUCTIONS.md` — added a paragraph after Step 5 describing the
  cache's first-build/subsequent-build behavior and how to force a rebuild.
- `world-model/CLAUDE.md` — new Tech Stack bullet recording the third two-store-pattern instance.
- `world-model/tools/measure_osm_cache_perf.py` — synthetic ~100k-row perf tool (made executable),
  mirrors `measure_m8_probe_chunk_perf.py`'s shape. One local run: populate ~697ms, fast-path copy
  ~2.57s (~38.9k features/s) — order-of-magnitude only, not a `syria-full`-scale measurement.

### Tests Added

`world-model/tests/test_osm_cache.py` (20 tests, no pipeline involved):
- Round-trip: features identical minus `id`/`source_id`; `OsmCacheMeta` round-trips identical;
  `OsmIngestStats` round-trips identical; `load_cache_meta` returns `None` for an absent path.
- `cache_meta_matches`: each of the 9 invalidation-key fields independently detected as a
  mismatch (parametrized); identical metas match; a `built_at`-only difference still matches
  (proving it is correctly excluded from the key).
- Atomicity: an interrupted population (no `finalize_cache` call) leaves no file at the canonical
  path, only the `.tmp`; a completed `finalize_cache` leaves no `.tmp` behind; a stale leftover
  `.tmp` doesn't break a fresh `open_osm_cache_for_populate` call.
- `sha256_file`: matches a known digest; small chunk size produces the same digest as the default.

`world-model/tests/test_pipeline_osm_cache.py` (6 tests, exercises real `build_region`):
- Parity: a cache-miss build followed by a cache-hit build against the same fixture `.osm.pbf`
  produce identical `osm_stats` and identical feature rows (ignoring `id`); the cache-hit build's
  own `out_path` sibling cache is still populated in the process (a cache-hit for a *different*
  `out_path` is itself a first-build for that path's own cache file).
- Invalidation: mutated `.osm.pbf` content forces a rebuild reflecting new content; a monkeypatched
  `CLASSIFIER_VERSION` bump forces a rebuild (verified via the stored cache meta before/after);
  a changed `half_extent_x_m` forces a rebuild of the same cache file.
- Mid-stream failure: `stream_features_from_pbf` monkeypatched to flush one batch then raise —
  no file exists at the canonical cache path afterward; a subsequent normal build (patch removed)
  succeeds and repopulates the cache.

### Checks

world-model/:
- ruff format --check: pass
- ruff check: pass
- mypy --strict src: pass (62 source files)
- pytest -q: pass (333 passed, ~143s)

tools/measure_osm_cache_perf.py checked individually (ruff format/check + mypy), per this
project's convention for `tools/` files even though they're outside the mandated per-commit
command list.

### Notable Discoveries

- **Cache's `feature` table drops `source_id`** relative to a literal "same columns as `store.
  schema`'s `feature` table" reading of the plan. `source_id` in the base store's schema always
  points at a `source` row created fresh by *that* build; a cache surviving across builds has no
  stable `source` table to reference, and the fast-path reader always retags every cached batch
  with the *current* build's own `source_id` before insertion anyway. Keeping a meaningless old
  `source_id` column would only invite a future reader to trust a value that's never actually used.
  Documented in `schema.py`'s and `writer.insert_cached_features`'s docstrings.
- `finalize_cache`'s and `open_osm_cache_for_populate`'s signatures take an explicit `conn`
  parameter (plan text showed `finalize_cache(tmp_path, final_path, meta, stats)` without one) —
  the connection has to come from somewhere between population and finalization, and threading it
  through explicitly is more debuggable than reopening/re-deriving it inside `finalize_cache`.
- One perf run only (order-of-magnitude, not `syria-full` scale, per the plan's Execution
  boundary): 100k synthetic `road` features populate in ~697ms and copy through the fast path
  (`iter_cached_features` + `insert_features`) in ~2.57s (~38.9k features/s). At `syria-full`
  scale (M9's real extract: ~1.86M ways + node counts in the low millions), this suggests the
  fast path lands in the "low tens of seconds to low minutes" range the plan hoped for, not the
  25-30+ minutes it replaces — but this is still an extrapolation, not a measurement, exactly as
  the plan's Risks & Unknowns flagged.
- No real `syria-theatre.osm.pbf` or real `syria-full` build was run in this session, per the
  plan's Execution boundary and this project's standing rule — the user's own first cache-populating
  build and first cache-hit rebuild are the actual validation.
