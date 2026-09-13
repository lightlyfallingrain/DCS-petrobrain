---
name: osm-classified-cache
description: Third two-store-pattern instance (osm_cache/); source_id dropped from cache schema; conn passed explicitly into finalize_cache/writer functions
metadata:
  type: project
---

Implemented `plans/osm-classified-cache/plan.md` on `feature/osm-classified-cache`: a new
`world-model/src/osm_cache/` package caching already-classified `StoredFeature` rows from
`build.ingest_osm`/`osm.pbf`, keyed by `pbf_sha256`+`pbf_size_bytes`+`CLASSIFIER_VERSION`+
`OSM_CACHE_SCHEMA_VERSION`+region bbox. Populated piggybacking on the existing
`_flush_nodes`/`_flush_ways` streaming-ingest callbacks in `build.pipeline`, atomically published
via `.tmp`-then-`os.replace` (`osm_cache.writer.finalize_cache`).

**Deviation from a literal plan reading**: the cache's `feature` table drops `source_id` (plan
said "same columns" as `store.schema`'s `feature` table). A cached row survives across many
builds, each with its own fresh `source` table — an old `source_id` would be meaningless, and the
fast-path reader always retags every batch with the *current* build's `source_id` before
`insert_features` anyway. Justified in the schema/writer docstrings and implementation.md.

**API shape not literally matching plan prose**: `finalize_cache`/`open_osm_cache_for_populate`
take an explicit `sqlite3.Connection` parameter — the plan's prose signature
(`finalize_cache(tmp_path, final_path, meta, stats)`) omitted it, but a connection has to be
threaded through from population to finalization somehow. Consistent with [[mi6_runtime_compilation]]-
style "prefer the type/actual signature over plan prose when they conflict."

Perf tool (`tools/measure_osm_cache_perf.py`) result at 100k synthetic features: populate ~697ms,
fast-path copy ~2.57s (~38.9k features/s) — order-of-magnitude sanity only, never run against the
real `syria-theatre.osm.pbf` (execution-boundary rule, see [[feedback_full_build_execution]]).

Full test run 333 passed, ~143s wall time (whole `world-model/tests` suite, not just new files).
