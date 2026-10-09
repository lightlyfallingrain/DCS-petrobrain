# WM-W11 — OSM classified-feature persistent cache

- [x] **OSM classified-feature persistent cache (no M-number — a performance optimization, not a
  milestone; done, merged 2026-09-13).** #status/done Extends WM-M8's two-store pattern (persistent sibling store,
  atomic populate, explicit invalidation key) to a third instance: `<region>-osm-cache.sqlite`
  caches already-classified `StoredFeature` rows from WM-M9's pyosmium parse + classification pass.
  Motivation: the ~25-30+ minute parse-plus-classify cost, while not eliminated, is incurred only
  once per `.osm.pbf`/classifier-version pair; subsequent `syria-full` rebuilds (schema bump, road
  fix, DCS patch) skip the expensive parse and copy pre-classified rows from the cache instead,
  completing the OSM stage in low minutes. Cache is **not** manually managed — automatic invalidation
  on: pbf SHA-256 hash, pbf file size (belt-and-suspenders), `CLASSIFIER_VERSION` (if rules change),
  `OSM_CACHE_SCHEMA_VERSION` (if `StoredFeature` shape changes), and region bbox (rows are baked
  with bbox clip). Populate is atomic (write at `.tmp`, `os.replace` to canonical path only after
  success) — no corrupt half-populated cache can silently lead to wrong data. Population happens
  during the same `stream_features` pass WM-M9 already runs (piggybacks on `_flush_nodes`/`_flush_ways`
  callbacks, not a second read of the `.osm.pbf`). Cache-hit read path reuses the existing
  `insert_features` per batch rather than a hand-rolled `ATTACH`+bulk-SQL optimization (documented
  fallback if real-scale performance proves insufficient). Implemented in `src/osm_cache/` (schema,
  models, writer, reader, paths, hashing), mirroring `probe_store/`'s file layout. Design decision
  verified: theatre-agnostic keying (no hardcoded "Syria"), correctness asserted via 332 passing
  tests (atomicity, invalidation parity, cache-hit/miss byte-for-byte feature match, mid-stream
  failure recovery). Real-scale performance (actual observed speedup on user's next `syria-full`
  rebuild) is an expectation from the design, not a measurement made in the test suite (per
  execution-boundary rule, full-theatre builds run by the user, not agents). See
  `plans/osm-classified-cache/plan.md`, `plans/osm-classified-cache/review.md` (APPROVED),
  `plans/osm-classified-cache/dod-check.md` (PASS).
