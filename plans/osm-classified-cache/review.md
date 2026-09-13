### Review Summary

Reviewed the OSM classified-feature cache (`world-model/src/osm_cache/`) against the locked plan
(`plans/osm-classified-cache/plan.md`, commit ff68282) and `implementation.md`. This is the
highest-stakes kind of change this project makes — a silently-wrong cache would feed incorrect
OSM data into a live DCS mission model — so all eight review points were checked directly against
source, not taken from the implementer's report.

1. **Atomicity — confirmed sound.** `writer.py`'s `open_osm_cache_for_populate` writes only to
   `osm_cache_tmp_path`; `finalize_cache` is the only call site of `os.replace`, and it runs after
   `stream_features_from_pbf` returns successfully (`pipeline.py` lines ~447-463). The
   `except BaseException: cache_populate_conn.close(); raise` block (pipeline.py ~464-473) never
   touches the canonical path — the claim "no canonical cache file exists after a mid-stream
   failure" is trivially true because `finalize_cache` (the only writer of the canonical path) is
   never reached, not because the except block does cleanup work itself. The `.tmp` file is left
   behind, exactly as the plan specifies as acceptable ("disk-usage noise, not a correctness
   hazard") — `open_osm_cache_for_populate` deletes a stale `.tmp` on the next attempt
   (`writer.py` line 38-39), verified by `test_osm_cache.py::test_open_osm_cache_for_populate_clears_a_stale_tmp_file`.
   `test_pipeline_osm_cache.py::TestMidStreamFailure::test_no_canonical_cache_file_after_a_failed_populate`
   genuinely simulates a real failure: the monkeypatched `stream_features_from_pbf` flushes one
   real batch via `on_ways(...)` (so a partial cache population actually happens) before raising,
   and the test asserts no canonical file exists afterward. A sibling test confirms a subsequent
   normal build succeeds and repopulates. This is real, not decorative.

2. **Invalidation-key completeness — confirmed.** `cache_meta_matches` (`osm_cache/models.py`)
   checks all nine fields the plan specifies (`pbf_sha256`, `pbf_size_bytes`, `classifier_version`,
   `cache_schema_version`, `region_name`, `centre_x`, `centre_z`, `half_extent_x_m`,
   `half_extent_z_m`), deliberately excluding only `built_at` as the plan requires. `pipeline.py`'s
   fork (lines 362-364) calls `cache_meta_matches` on the whole tuple, not a subset. All three
   plan-mandated invalidation scenarios are exercised by real `build_region` calls in
   `test_pipeline_osm_cache.py::TestInvalidation` (pbf content mutation, `CLASSIFIER_VERSION`
   monkeypatch, region bbox change) and each asserts a real behavioral consequence (new feature
   content served, or the stored meta reflecting the new value) — not just "doesn't crash".
   `test_osm_cache.py::TestCacheMetaMatches` parametrizes all nine fields independently plus a
   `built_at`-only-difference-still-matches case, proving the exclusion is deliberate rather than
   accidental.

3. **Cache-hit/cache-miss parity — confirmed genuine.**
   `TestCacheMissThenHitParity::test_second_build_hits_cache_and_matches_first_build_byte_for_byte`
   builds once via the real streaming (cache-miss) path against a real `.osm.pbf` fixture, then
   builds again — the second build necessarily hits the freshly-populated cache — and asserts
   `report_1.osm_stats == report_2.osm_stats` and field-for-field-equal feature rows (via
   `_feature_rows_ignoring_ids`, which compares every `StoredFeature` field except `id`). This is
   a real byte-for-byte-equivalent-content assertion, not a count-only check.

4. **`source_id` deviation — sound, and honestly logged.** `store/schema.py` confirms
   `feature.source_id` is a nullable FK to `source(id)`, and `source` rows are created fresh per
   build (`insert_source` in `pipeline.py`, called once per stage per build). A cache row that
   outlives the build that created it has no valid `source_id` to preserve — the deviation's
   reasoning holds. The retagging is verified correct in both the fast-path pipeline code
   (`replace(f, source_id=osm_source_id) for f in batch`, pipeline.py line 378) and the perf tool
   (mirrors the identical retag). Every batch read from the cache passes through this retag before
   `insert_features`, so no row reaches the base store with a stale/`None` `source_id`. The
   deviation is disclosed plainly in both `implementation.md`'s "Notable Discoveries" and the
   `osm_cache/schema.py`/`writer.py` docstrings — not glossed over.

5. **Piggybacking on flush callbacks — confirmed, no second pass.** `_flush_nodes`/`_flush_ways`
   (pipeline.py ~415-445) each call `insert_cached_features(cache_populate_conn, ...)` in the same
   callback invocation that calls `insert_features(conn, ...)` against the base store — both driven
   by the one `stream_features_from_pbf` call. No second read of the `.osm.pbf`.

6. **Theatre-agnostic keying — confirmed.** `osm_cache_store_path`/`osm_cache_tmp_path` derive
   purely from `base_db_path`'s stem/suffix; no "syria" string appears anywhere under
   `world-model/src/osm_cache/`.

7. **No real external-resource operation snuck in — confirmed.** All new tests build synthetic
   `.osm.pbf` fixtures in-process via `osmium.SimpleWriter` (`test_pipeline_osm_cache.py`'s
   `_write_fixture_osm_pbf`); none reference `syria-theatre.osm.pbf` or any real data path.

8. **Perf tool — plausible and safely scoped.** `tools/measure_osm_cache_perf.py` runs entirely
   inside a `tempfile.TemporaryDirectory`, uses the real `osm_cache`/`store.writer` primitives on
   100k synthetic rows, and its measured loop (`iter_cached_features` + retag + `insert_features`)
   is exactly what the pipeline's fast path runs — the reported ~697ms populate / ~2.57s
   (~38.9k features/s) copy numbers are plausible for a local SQLite-to-SQLite batched insert of
   this size and are honestly framed as order-of-magnitude, not `syria-full`-scale, measurements.

**Verification run directly (not trusted from the report):**
- `ruff format --check world-model/src world-model/tests` — pass (103 files)
- `ruff check world-model/src world-model/tests` — pass
- `mypy world-model/src` (`--strict` per `pyproject.toml`) — pass, 62 source files
- `pytest world-model/tests -q` — 333 passed in 142.79s (matches the reported count)

**Scope check:** matches the plan's implementation-plan steps 1-7 exactly; no multi-theatre
implementation, no `ATTACH`-based bulk-SQL fast path was built (plan explicitly named this as a
documented, not-implemented, fallback — confirmed not present in `pipeline.py`). `world-model/CLAUDE.md`
and `docs/M9_OSM_RUN_INSTRUCTIONS.md` both got the plan-mandated additions and accurately describe
what was built (cache path, invalidation key, how to force a rebuild). All new/modified files are
already committed (commit `8fbf9a8`) and the working tree is clean.

### Required Fixes

None.

### Optional Refinements

- `osm_cache/reader.py::load_cache_meta` raises a bare `ValueError` if a meta key is missing from
  an existing file — reasonable per its docstring ("not a valid finalize_cache-published cache"),
  but there is no test exercising a corrupt/partial file at the canonical path (as opposed to a
  merely-absent one). This is a very unlikely state given the atomicity guarantee (nothing but
  `finalize_cache` ever publishes to the canonical path, and `finalize_cache` always writes all
  meta keys in one commit), so it's optional, not required — worth a one-line test only if this
  package sees future changes to `finalize_cache`'s meta-writing order.
- `pipeline.py`'s cache-hit branch instantiates `sqlite3.connect(f"file:{cache_path}?mode=ro", uri=True)`
  inline rather than through a small `osm_cache.reader` helper (c.f. `open_region_db` for the base
  store). Minor duplication, no correctness impact; would only be worth fixing if a third read-only
  open call site appears.

### Verdict
APPROVED

### Review Confidence
Full read — all eight review-focus points were checked against the actual source (`writer.py`,
`reader.py`, `schema.py`, `models.py`, `pipeline.py`'s full integration block, both new test files,
`ingest_osm.py`'s `CLASSIFIER_VERSION`, `store/schema.py`'s `feature`/`source` relationship, the
perf tool, and both doc updates), not just the implementer's summary. Format/lint/type/test commands
were re-run directly rather than trusted from the report.
