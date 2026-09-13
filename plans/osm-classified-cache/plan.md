### Goal

Give the World Model Builder a persistent, per-region cache of already-classified OSM feature
rows so a DCS-driven `syria-full` rebuild (schema bump, roadnet fix, DCS patch) can skip the
~25-30+ minute pyosmium-parse-plus-`_classify_way` pass entirely and bulk-copy pre-classified
rows into the fresh base store instead, while automatically detecting and rebuilding when the
source `.osm.pbf` or the classification rules actually change.

**Performance-optimization note for a future reader**: this is squarely a performance change.
Per `CLAUDE.md`'s Agents section, Security and Performance Reviewer stay exempt for this project
phase (offline single-user local pipeline, no hot path, no untrusted-input surface) — that
exemption is a standing phase-wide policy, not a judgment call made specifically for this
feature, so neither role is invoked here despite the subject matter.

**No investigator step.** Nothing in this plan depends on an unverified DCS-internals claim — it
rests entirely on this project's own existing schema/pipeline code (`store/`, `build/ingest_osm.py`,
`osm/pbf.py`), well-established SQLite behaviour, and stdlib `hashlib`. Per the architect
process, investigator is skipped when the relevant facts are already known from code, not from
DCS itself.

### Context already established (read, not re-derived here)

- `plans/m8-incremental-store/plan.md` / `world-model/docs/M8_PROBE_STORE.md` — the precedent
  this design mirrors: a **second, persistent SQLite store** per region, separate from the base
  store's delete-and-recreate lifecycle, because the cached data must survive that lifecycle. M8's
  reason was "not rebuildable at all"; this plan's reason is "rebuildable, but at a cost that
  materially hurts a DCS-driven rebuild loop" — same *shape* of problem, weaker premise, same
  answer.
- `world-model/src/build/ingest_osm.py` — `_classify_way` (four keyword rules), `_ingest_node`/
  `_ingest_way` (per-item, no cross-element state), and the exact `StoredFeature` shape a
  classified row takes. This is what the cache persists.
- `world-model/src/osm/pbf.py` — the just-merged `stream_features` bounded-batch flow
  (`_flush_nodes`/`_flush_ways` in `pipeline.py`). Cache population hooks into these same
  callbacks rather than requiring a second pass over the `.osm.pbf`.
- `world-model/src/build/pipeline.py`'s `osm_pbf_path` branch (`_stage("OSM overlay (.osm.pbf)", 3)`)
  — where the fast-path/slow-path fork belongs.
- `world-model/src/store/schema.py`/`models.py`/`writer.py` — `feature` table shape and
  `StoredFeature` dataclass the cache's rows must be either directly usable as, or trivially
  convertible to.
- `world-model/docs/M9_OSM_RUN_INSTRUCTIONS.md` — current build procedure; Step 5 needs a note
  about the cache.
- `world-model/ROADMAP.md`'s multi-theatre backlog item (Afghanistan/Caucasus/Kola, "needed
  soonish, not yet scoped") — this cache is designed to generalize per-theatre from the start
  (keyed by region, not hardcoded to Syria), without implementing any other theatre here.

### Affected Modules / Files

**New package — `world-model/src/osm_cache/`, mirroring `probe_store/`'s file layout**

- `osm_cache/schema.py` — DDL + its own `OSM_CACHE_SCHEMA_VERSION`: a `meta` table (identity/
  invalidation fields, see below) and a `feature` table shaped like `store.schema`'s `feature`
  table (same columns except no `id` semantics tied to the base store and no `feature_bbox`
  R\*Tree — the cache is read by full sequential scan, never queried spatially). Comment placed
  directly beside `OSM_CACHE_SCHEMA_VERSION` noting it must be bumped if `store.models.
  StoredFeature`'s shape ever changes incompatibly, so the two versions can't silently drift
  apart the way M8 flagged as a risk for `_load_grid_meta`.
- `osm_cache/writer.py` — `open_osm_cache_for_populate(tmp_path) -> Connection` (creates schema
  on an empty file), `insert_cached_features(conn, features: list[StoredFeature]) -> None` (one
  `executemany`-style batch insert per call, same JSON encoding as `store.writer.insert_features`
  minus the bbox insert), `finalize_cache(tmp_path, final_path, meta, stats) -> None` — writes the
  `meta` row and the serialized `OsmIngestStats`, closes the connection, then `os.replace(tmp_path,
  final_path)`. **This function is the only thing that makes a cache visible/valid** — see
  "Invalidation & atomicity" below.
- `osm_cache/reader.py` — `load_cache_meta(path) -> OsmCacheMeta | None` (returns `None` if the
  file is absent — absence-as-absence, this project's standing convention), `iter_cached_features
  (conn, batch_size) -> Iterator[list[StoredFeature]]`, `load_cached_stats(conn) -> OsmIngestStats`.
- `osm_cache/paths.py` — `osm_cache_store_path(base_db_path) -> Path`, the one place mapping
  `<region>.sqlite` to its `<region>-osm-cache.sqlite` sibling (mirrors `probe_store/paths.py`'s
  `probe_store_path`), plus the `.tmp` naming convention used during population.
- `osm_cache/hashing.py` — `sha256_file(path, chunk_size=...) -> str`, a streamed stdlib
  `hashlib.sha256` read (fixed-size chunks, never `path.read_bytes()` on a 476 MB+ file) — the one
  piece of this plan that touches the raw `.osm.pbf` bytes a second time, and it never loads more
  than one chunk into memory.
- `osm_cache/models.py` — `OsmCacheMeta` (frozen dataclass): `pbf_sha256`, `pbf_size_bytes`,
  `classifier_version`, `cache_schema_version`, `region_name`, `centre_x`, `centre_z`,
  `half_extent_x_m`, `half_extent_z_m`, `built_at`. No new abstraction for the feature rows
  themselves — the cache reuses `store.models.StoredFeature` directly rather than inventing a
  parallel type.

**Modified**

- `world-model/src/build/ingest_osm.py` — add `CLASSIFIER_VERSION: int = 1` next to
  `_classify_way`, with a docstring instruction to bump it whenever the classification rules
  (the four `if`/`elif` branches) change. This is the second half of the invalidation key.
- `world-model/src/build/pipeline.py` — the `osm_pbf_path` branch gains a fork:
  1. Compute `expected_meta` (region bbox + `CLASSIFIER_VERSION` + `OSM_CACHE_SCHEMA_VERSION`,
     cheap) and `sha256_file(osm_pbf_path)` (a few seconds for a 476 MB file — dominated by disk
     read, not CPU).
  2. If `osm_cache_store_path(out_path)` exists and its stored `OsmCacheMeta` matches
     `expected_meta` field-for-field: **fast path** — open the cache read-only, insert a fresh
     `source` row in the base store (same as today, but `notes` records "served from OSM
     classified cache, see osm_cache/"), iterate cached feature batches via
     `iter_cached_features`, reassign each batch's `source_id` to the new row, call the existing
     `insert_features(conn, batch)` per batch (unmodified — see "Why reuse `insert_features`"
     below), accumulate `report.feature_counts`, and set `report.osm_stats` from
     `load_cached_stats` directly (already-correct aggregate counts, not recomputed).
  3. Otherwise: **slow path**, structurally the existing streaming code, with one addition —
     `_flush_nodes`/`_flush_ways` also call `insert_cached_features` on a cache-populate
     connection opened at the `.tmp` path alongside their existing `insert_features(conn, ...)`
     call. After `stream_features_from_pbf` returns, call `finalize_cache(...)` with the
     just-computed hash/meta and the completed `OsmIngestStats` — this is the only point a cache
     becomes visible at its canonical path (see "Invalidation & atomicity").
- `world-model/docs/M9_OSM_RUN_INSTRUCTIONS.md` — Step 5 gets a short addition: the first
  `syria-theatre.osm.pbf` build populates `data/raw/../data/world-model/syria-full-osm-cache.sqlite`
  (a few seconds/minutes on top of the existing OSM stage, not a second full pass — see "Why the
  cache write is free"); subsequent rebuilds against the *same* pbf and classification rules hit
  the cache and finish the OSM stage in low minutes instead of 25-30+; changing the merged extract
  or `_classify_way` invalidates it automatically; deleting the `-osm-cache.sqlite` file (or
  bumping `CLASSIFIER_VERSION`) forces a deliberate rebuild.
- `world-model/CLAUDE.md` — new Tech Stack entry recording the decision, matching the existing
  M5/M8/M9-style per-milestone paragraphs (two-store precedent extended to a third pair; cache
  invalidation key; theatre-agnostic naming).

**New tests**

- `world-model/tests/test_osm_cache.py` — round-trip (write features -> read back byte-for-byte
  identical `StoredFeature` list, minus `id`); `OsmCacheMeta` equality/mismatch detection for each
  field independently (hash, classifier version, cache schema version, each bbox field);
  `finalize_cache`'s atomicity (killing/interrupting before `finalize_cache` leaves no file at the
  canonical path, only a stray `.tmp` at worst).
- `world-model/tests/test_pipeline_osm_cache.py` (or extend `test_pipeline.py`) — the parity test:
  run `build_region` twice against the same small fixture `.osm.pbf` (cache miss, then cache hit);
  assert the two resulting `.sqlite` files' OSM-derived `feature` rows are identical on every field
  except `id`/`source_id`, and `BuildReport.osm_stats` matches between the two runs. Then three
  invalidation variants: mutate the fixture pbf's bytes between runs (hash mismatch -> miss and
  repopulate with new content), bump `CLASSIFIER_VERSION` via monkeypatch between runs (version
  mismatch -> miss), and change the region's `half_extent_x_m` between runs (bbox mismatch ->
  miss). Also: simulate a mid-stream failure (patch `_flush_ways` to raise on the second batch) and
  assert no file exists at the canonical cache path afterward, and that a subsequent normal build
  still succeeds and correctly treats this as "no cache" rather than crashing on a partial one.
- `world-model/tools/measure_osm_cache_perf.py` — times a cache-hit `insert_cached_features` +
  `insert_features` copy loop against a synthetic ~100k-row cache (mirrors
  `tools/measure_m8_probe_chunk_perf.py`'s precedent: a locally generated fixture, never a real
  `syria-full` run — see "Execution boundary" below).

### Cache identity / invalidation key

Stored in the cache's `meta` table, all checked together on every read attempt (a mismatch on
*any* field is a full cache miss, never a partial reuse):

| Field | Source | Why it must match |
|---|---|---|
| `pbf_sha256` | `sha256_file(osm_pbf_path)`, streamed | The actual content check — catches a re-clipped/re-merged extract even if the filename is unchanged |
| `pbf_size_bytes` | `osm_pbf_path.stat().st_size` | Cheap belt-and-suspenders; not load-bearing on its own since the hash already covers content |
| `classifier_version` | `ingest_osm.CLASSIFIER_VERSION` | Catches a `_classify_way` rule change even when the source `.osm.pbf` is untouched |
| `cache_schema_version` | `osm_cache.schema.OSM_CACHE_SCHEMA_VERSION` | Catches a change to the cache's own row shape (tracks `StoredFeature`'s shape, see the schema.py comment above) |
| `region_name`, `centre_x`, `centre_z`, `half_extent_x_m`, `half_extent_z_m` | `RegionDefinition` passed to `build_region` | `_within_region`'s bbox clip is baked into every cached row; a different bbox means different, wrong rows |

Deliberately **not** part of the key: the base store's own `SCHEMA_VERSION` (`store.schema`) or
`routes_path`/`srtm_tile_paths`/anything about the other build stages — the OSM cache's rows are
independent of every other ingest stage, exactly like M8's probe store is independent of the base
store's own rebuild cadence.

### Invalidation & atomicity ("no corrupt half-populated cache" requirement)

The cache is populated at `<region>-osm-cache.sqlite.tmp` throughout the entire streaming pass and
is **only** renamed to its canonical `<region>-osm-cache.sqlite` path — via `os.replace`, one
atomic filesystem operation — inside `finalize_cache`, called once after `stream_features_from_pbf`
returns successfully. If the process dies or raises at any point during population (pyosmium
error, disk full, killed run), the `.tmp` file is simply abandoned; nothing exists yet at the path
`osm_cache_store_path` looks up, so the next build correctly sees "no cache" and falls through to
the slow path, exactly the fallback behaviour a missing file already produces. No flag column, no
"is this cache valid" query is needed — the file's *existence at its canonical path* is the
validity signal, matching this project's absence-as-absence convention. A leftover `.tmp` file
from an interrupted run is disk-usage noise, not a correctness hazard (the next successful build
overwrites it); cleaning it up proactively is a nice-to-have in the implementation, not required
for correctness.

### Why reuse `insert_features` for the cache-hit fast path (design decision, stated for the record)

The fast path calls the base store's existing `insert_features(conn, batch)` per batch, the same
function the slow (parse) path already calls per flushed batch — it is **not** reimplemented as a
raw `ATTACH DATABASE` + `INSERT INTO ... SELECT` bulk copy, even though that would in principle be
faster. Reasoning:

- `insert_features` already computes each feature's bbox and writes the matching `feature_bbox`
  R\*Tree row in the same transaction. A bulk cross-database `INSERT ... SELECT` would either need
  to recompute bboxes anyway (no time saved on that part) or correlate freshly-autoincremented
  `feature.id` values with `feature_bbox.id` values across two separate bulk statements — solvable
  with `ROW_NUMBER() OVER (...)` and a captured `last_insert_rowid()` offset, but that correlation
  is exactly the kind of fragile, hard-to-verify-by-inspection SQL this project's decision
  heuristics (*prefer simple, debuggable solutions over clever ones*) argue against introducing
  for a first cut.
- The classification/parsing work this cache exists to skip (pyosmium `apply_file` over 77M raw
  elements plus `_classify_way` keyword matching) is what actually costs 25-30+ minutes. A batched
  read-from-cache-sqlite + `insert_features` copy, with no parsing and no classification, is
  expected to land in low minutes even without a hand-tuned bulk-SQL path — this is stated as an
  expectation, not a measured guarantee (see Risks).
- If the batched-Python-copy fast path turns out too slow once measured against a real
  `syria-full`-scale cache, the `ATTACH`-based bulk `INSERT ... SELECT` (with bbox columns
  precomputed and stored in the cache's `feature` table so no bbox recompute is needed, correlated
  via `ROW_NUMBER()`/`last_insert_rowid()`) is the documented fallback optimization — not
  implemented now, named here so a future reader doesn't have to re-derive it from scratch.

### Why the cache write is "free" (piggybacks on the existing pass)

Cache population happens inside the same `_flush_nodes`/`_flush_ways` callbacks the slow path
already calls per batch during the one required `stream_features_from_pbf` pass over the
`.osm.pbf` — it is one extra `insert_cached_features` call per batch (a plain SQLite insert of
already-in-memory `StoredFeature` objects), not a second pass over the file. The only genuinely
new cost on a cache-miss (first) build is the one `sha256_file` read plus the marginal SQLite
write cost of the second (cache) store's inserts — both small relative to the pass they ride
alongside.

### Execution boundary (standing project rule, restated for this plan)

Per this project's rule against running real full-theatre builds in an agent session
(`M7_RUN_INSTRUCTIONS.md`/`M9_OSM_RUN_INSTRUCTIONS.md`'s precedent, and the architect's own
memory of this rule), the Implementer/Reviewer/DoD verify this cache against small synthetic
fixtures and, where already gitignored real data exists locally
(`data/raw/osm/syria-260911.osm.pbf`, per the `osm-streaming-ingest` precedent), a
`pytest.mark.skipif`-gated single-country regression test — never against the real merged
`syria-theatre.osm.pbf` or a real `syria-full` rebuild. The user runs the real first
cache-populating build and the real first cache-hit rebuild themselves, and that run is the actual
performance validation, not this plan's test suite.

### Implementation Plan

1. **`osm_cache/` package: schema, models, hashing (minimal working version).** Greenfield,
   no changes to any existing module yet. Round-trip tests only (write features -> read back
   identical, minus `id`; meta write/read identical). `sha256_file` tested against a small fixture
   with a known digest.
2. **Writer atomicity.** `open_osm_cache_for_populate` / `insert_cached_features` /
   `finalize_cache`, with the `.tmp`-then-`os.replace` contract. Test: interrupt mid-population
   (raise inside a batch), assert nothing exists at the canonical path afterward.
3. **Pipeline integration — cache-miss path unchanged except for the extra write.** Wire
   `insert_cached_features` into `_flush_nodes`/`_flush_ways` and `finalize_cache` into the
   existing streaming branch's end. At this stage the cache is populated but never yet consulted —
   verify the existing OSM ingest tests still pass unchanged, and that a cache file now appears
   after a build.
4. **Pipeline integration — cache-hit fast path.** Add the `expected_meta` computation, the
   `osm_cache_store_path(out_path)` lookup, and the fork. Parity test (Step 4 in "New tests"
   above) is the correctness gate for this step: same fixture, cache-miss build vs. cache-hit
   build, byte-for-byte-equal feature rows.
5. **Invalidation tests.** The three mismatch variants (content hash, classifier version, region
   bbox) plus the mid-stream-failure test.
6. **Performance sanity, not a real `syria-full` run.** `tools/measure_osm_cache_perf.py` against
   a locally generated ~100k-row synthetic cache — establishes the fast path's per-row cost so the
   user has an order-of-magnitude expectation before running the real thing. Do **not** run a real
   `syria-theatre.osm.pbf` build locally.
7. **Docs.** `M9_OSM_RUN_INSTRUCTIONS.md` addition and the `world-model/CLAUDE.md` Tech Stack
   entry.

### Risks & Unknowns

- **The batched-copy fast path's real-scale performance is an expectation, not a measurement.**
  "Low minutes, not tens of minutes" is reasoned from "no parsing, no classification, just a
  SQLite-to-SQLite copy through existing `insert_features`," not profiled against a real
  multi-million-row `syria-full` OSM feature set. If the user's first real cache-hit rebuild shows
  this is still too slow, the `ATTACH`+bulk-`INSERT...SELECT` fallback described above is the next
  step, not a redesign.
- **`sha256_file` over a 476 MB+ (and growing, as more countries/theatres are added) file runs on
  every build, cache-hit or miss.** A few seconds today; if a future merged theatre extract grows
  much larger this cost grows linearly with it, though it stays trivial next to either the parse
  time it replaces or the copy time it gates.
- **Cache is keyed per region, not per theatre-plus-pbf.** Two region definitions sharing the same
  theatre and the same `.osm.pbf` (e.g. a smaller test region carved from the same merged extract)
  each pay their own full first-parse cost independently — no cross-region sharing. This is an
  explicit non-goal for this plan, not an oversight: sharing would require decoupling the cached
  rows from the bbox clip already baked into them, which is a materially different (and more
  complex) design. Worth a backlog line if a future multi-region-per-theatre workflow makes this
  cost matter.
- **`OSM_CACHE_SCHEMA_VERSION` must be remembered whenever `StoredFeature`'s shape changes.** Same
  drift risk class M8 flagged for `_load_grid_meta` — mitigated with a comment at the definition
  site, not by any enforcement mechanism, because none is cheap to build here.
- **A `.tmp` file can be left behind by an interrupted first build.** Disk usage only, not a
  correctness hazard (see "Invalidation & atomicity") — the next successful build's `os.replace`
  overwrites it either way.
- **This plan does not itself validate against the real merged `syria-theatre.osm.pbf` or a real
  `syria-full` rebuild** — per the standing execution-boundary rule, that is the user's own result,
  same as M7/M9/the OSM streaming fix before it.

### Second-order effect

This narrows the cost of every future `syria-full` rebuild that doesn't touch OSM data or
classification rules (the common case: a DCS patch, a roadnet/junction fix, a schema bump on a
non-OSM table) from "OSM stage dominates at 25-30+ minutes" to "low minutes," which matters more
as Mission Interpreter/body-layer come to depend on a current world model and rebuilds become
routine rather than rare. It also establishes a second instance of the M8 two-store pattern
(persistent sibling store, atomic populate-then-publish, explicit invalidation key) as a reusable
shape for "expensive-to-recompute derived data that must survive a delete-and-recreate rebuild" —
a future SRTM-ingestion cache, if that ever becomes a bottleneck too, would extend the same
pattern rather than invent a new one. It does not change what the next roadmap milestone should
be, and does not touch the multi-theatre backlog item beyond confirming the cache's naming
convention is already theatre-agnostic.
