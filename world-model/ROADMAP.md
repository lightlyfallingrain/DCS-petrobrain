# World Model Builder — Roadmap

Decisions locked in for this phase:

- **Theatre**: Syria (first).
- **Stack**: Python 3.11+, type-hinted, `mypy --strict`. Spatial libraries TBD during Milestone 1-2.
- **Machines**: DCS on Windows, dev on Mac, manual-copy workflow (`WORKFLOW.md`).

Milestones below are from `../docs/concept/WORLD_MODEL_BUILDER.md` — status tracked here as work proceeds.

- [x] **M0 — Repo + research notebook.** Scaffold done. DCS version + Syria theatre presence recorded in `research/`.
- [x] **M1 — One coordinate.** Prove DCS x/z ↔ lat/lon for Syria against a known real-world control point. Measure error. Done: `src/coordinates/` (pyproj-based, theatre-agnostic), three real-world ARP control points (Damascus, Latakia, Beirut), measured residual ~1.0-1.3km (DCS terrain-art placement error, not transform error). See `research/2026-09-03-m1-coordinate-transform-verification.md`.
- [x] **M2 — Raster understanding.** Read Syria's `RasterCharts`: tile hierarchy, dimensions, scales, registration. Render a known DCS coordinate onto the raster. Done: `src/raster/` (Pillow-based DDS loader + empirical x/z-arithmetic registration, `confidence="provisional"`), `tools/inspect_raster.py` (`scan`/`mark` diagnostic CLI), control-point + held-out-point tests. Registration fitted against Sivas/Kahramanmaras/Hama/Erzincan; independently validated against held-out Gemerek (~129m x-axis, ~5.5km z-axis residual). Scope note: this raster is scanned real-world cartography (Turkish JOG-A-class chart), not DCS-rendered geometry — feeds only the F10 paper-map mode; provenance-taxonomy follow-up still open, see `plans/m2-raster-understanding/plan.md` "Decisions Requiring User Input". `level` tile-suffix semantics (`-2`/`-1`/`00`/`01`) remain unresolved, no sample beyond `"00"`. See `research/2026-09-03-m2-rastercharts-recon.md`.
- [x] **M3 — OSM overlay.** Small OSM region around the known location, transformed into DCS/raster space. Diagnostic overlay, quantify displacement. Done: `src/osm/` (Overpass API fetch + in-memory parse), `tools/inspect_osm_overlay.py` diagnostic overlay CLI, control-point + transform tests, held-out Gemerek validation. Expected ~5.2 km z-axis displacement observed (consistent with M1/M2 residual), OSM coverage non-trivial (96 highways, 17 buildings), attribution rendered onto output PNG. Spatial-storage choice deferred to M5 (no DB needed yet). See `research/2026-09-03-m3-osm-overlay.md`.
- [x] **M4 — DCS elevation.** Sample DCS terrain elevation over a small region, compare against external DEM. Done: `src/elevation/` (`dcs_grid.py` parses `land.getHeight` live-probe output, `dem.py`'s `SrtmTile` parses SRTM `.hgt` with dynamic grid-size detection), `tools/dcs-mission-probe/elevation_probe.lua` (live-mission probe, io/lfs-based), `tools/inspect_elevation.py` (DCS-vs-SRTM delta report CLI). 100-point grid over the Gemerek bbox vs. a real SRTM3 tile: mean delta +13.89m, stddev 28.02m, range -86.09m to +69.19m — spatially clustered (west edge + one diagonal band), consistent with terrain-mesh-resolution mismatch rather than a systematic vertical datum offset. See `research/2026-09-03-m4-elevation-recon.md` (recon) and `.../2026-09-03-m4-dcs-elevation.md` (results).
- [x] **M5 — First persistent model.** Small geographic DB (~20×20 km test region): elevation, roads, settlements, water, named places. Implement `describe_position(...)`. Done: `src/store/` (stdlib `sqlite3` + R*Tree, JSON geometry), `src/roadnet/` (DCS-native `.routes` binary parser), `src/dcs_data/` (towns/beacons Lua parsers), `src/query/describe_position`. Region: Latakia (`latakia-20km`). Real store: `airfield=1, named_place=108, navaid=8, road=3266, runway=2, settlement=338, water=117`; 1,681-point elevation/surface_type probe grid at 100% coverage; 8.57 MB `.sqlite`; `describe_position` p99 275ms. Two real defects found+fixed: `pyproj.Transformer` per-call rebuild (perf), roadnet resync denormalized-float validation gap that let one corrupted route into the store (correctness). `.rn4` graph decoding, airfield taxiways/structures, Latakia SRTM tile, and a full-theatre per-route resync audit are deferred to M6+. See `research/2026-09-04-m5-first-persistent-model.md` (milestone summary, links every per-stage note) and `plans/m5-first-persistent-model/`.
- [x] **M6 — Terrain semantics.** One derived feature class (ridges/valleys). Validate usefulness from an Mi-24 cockpit perspective. Done: `src/terrain/` (stdlib discrete-Laplacian curvature classification + 4-connected-component grouping + closed-form principal-axis line extraction over the existing `latakia-20km` elevation grid, no numpy needed), `src/build/ingest_terrain.py`, `src/store/reader.load_full_grid`, `nearby_ridges`/`nearby_valleys` in `describe_position`, `tools/inspect_terrain.py` diagnostic visualizer. Real store: `ridge=12, valley=12` at tuned defaults (`threshold=20.0m`, `min_cell_count=6`; Stage 1's 3.0m first guess classified ~71% of interior cells, unusable). Validated against an independent (non-DCS) elevation source: the classifier reliably catches the region's single most dominant peak/trough (~200m agreement) but misses/misclassifies secondary bumps and troughs, and the per-cell classification shows persistent checkerboard-pattern noise across the mountainous quadrant that a higher threshold reduces but does not eliminate — a real "grid resolution vs. feature scale" limitation, not a bug. `confidence: "low"` is carried on every emitted feature. No new dependency needed or added. See `research/2026-09-05-m6-terrain-semantics.md` and `plans/m6-terrain-semantics/`.
- [x] **M7 — Full theatre pipeline.** Scale the M5/M6 pipeline to the whole Syria theatre. Scope locked: SRTM-primary elevation (not a full-grid DCS probe, repurposed to a scattered spot-check), OSM dropped entirely (re-scoped for a future milestone via geofabrik.de per-country extracts, not live Overpass queries), M6's terrain classifier out of scope. Done: `syria-full` registered as a rectangular-half-extent region (`build.region`), `build.pipeline`/`build.ingest_srtm` generalized for full-theatre scale, `tools/validate_m7_stage{1,2,3}.py` + `tools/measure_m7_stage4_perf.py`. Real store: `road=14833` (exact match to Stage 0's independent census), `airfield=35, runway=27, named_place=1182`; SRTM ingest 591,732/639,216 points sampled (92.6%) from 131 staged `.hgt` tiles; 461 MB `.sqlite`; full rebuild 449.3s (close to M5's 430.9s baseline, `.routes` walk-dominated as expected); `describe_position` mean 136.8ms/median 52.4ms/p95 497.7ms/p99 803.4ms (tail ~3x M5's baseline, flagged as a follow-up, not a blocker). All 8 theatre-spread coordinate control points within tolerance; DCS-probe spot-check vs. SRTM: mean delta -7.19m, stddev 11.52m (tighter than M4's Gemerek baseline, no degradation with distance). One accepted gap: `surface_type` stays `"unavailable"` theatre-wide (only ever populated by the full DCS-probe grid, which M7 deliberately never stores) — real, documented, not a defect. Incremental per-layer builds deferred to backlog (`todo/todo.md`). See `research/2026-09-06-m7-stages-1-2-3-full-build-results.md` and `plans/m7-full-theatre-pipeline/`.

- [x] **M8 — Incremental probe store.** Accumulate probe-tier data (fine elevation, `surface_type`, ridge/valley) chunk-by-chunk in a **second `.sqlite` per theatre** (`<region>-probe.sqlite`), separate from M7's base store: a theatre-anchored 5 km chunk lattice at 100 m probe spacing, tri-state per-chunk coverage (`unqueried`/`queried-with-data`/`queried-void`), and ATTACH-based probe-then-base resolution at query time. Two stores rather than a `grid.tier` column because probe data is *not* rebuildable from `data/raw/` and must survive the base store's delete-and-recreate lifecycle — and because it leaves M7-validated write paths untouched; the probe store holds exactly one grid per kind, enforced by `UNIQUE(kind)`. `build_region` is untouched. Done: `src/probe_store/` (schema, writer, reader, paths), separate `-probe.sqlite` per theatre, ATTACH-based probe-then-base fallback in `describe_position`, locked chunk/probe spacing, drift detection on both write and read paths. All 244 tests pass (241 base + 3 new from a required fix). Two-store separation prevents "newest grid wins" silent failure; read-path drift protection closes a reviewer-found cross-theatre/stale-lattice gap. Fixture-only testing; no live-mission channel (deferred to Runtime). See `plans/m8-incremental-store/plan.md`, `plans/m8-incremental-store/implementation.md`, `plans/m8-incremental-store/review.md`, and `world-model/docs/M8_PROBE_STORE.md`.
- [x] **Line-of-sight query primitive (no M-number — a cross-subproject refactor, not a
  milestone; done, merged 2026-09-12).** `query.line_of_sight.line_of_sight_clear(conn, theatre,
  observer, target)` — an ownship-agnostic point-A-to-point-B terrain-masking LOS check, moved
  verbatim (no behavior change) from body-layer's `perception/geometry.py`, which now owns only a
  thin delegating wrapper for its own ownship-to-contact case. Motivation: makes general-purpose
  A↔B visibility queries available to future consumers (Mission Interpreter, a future brain-layer
  tool) without depending on body-layer's own perception pipeline. Uses `tuple[float,float,float]`
  (x, z, alt_m) points, `store.reader.sample_grid` directly (not `describe_position`, to avoid its
  settlement/road join overhead for a bare elevation read — rationale restated in the new module's
  docstring). See `plans/world-model-los-generalization/plan.md`.

- [x] **M10 — Road-junction detection (done, merged 2026-09-13).** Derives road-junction
  landmarks purely from geometry over the already-parsed `.routes`/road layer — no new
  dependency, no OSM data. Grid-bucketed union-find over road-segment endpoints/interior
  vertices (`src/roadnet/junctions.py`); a junction is emitted at degree ≥ 3 (endpoint = 1 arm,
  interior-attachment = 2 arms). New pipeline stage 5 (`src/build/ingest_junctions.py`,
  `_TOTAL_STAGES` 7→8), new query surface `describe.nearest_junction`/`JunctionInfo`. Real
  numbers against `latakia-20km`: 3,266 roads → 6,496 endpoints + 155,900 interior vertices →
  3,980 clusters → 3,634 junctions kept (346 dropped as degree-2 route continuation); pipeline
  stage 0.6s, `nearest_feature(["junction"])` mean 8.2ms (cheaper than the pre-existing road
  lookup). Known bounded limitation: ~32/3,634 false positives where DCS represents one road
  corridor as multiple exactly-coincident `.routes` polylines, indistinguishable from a genuine
  multi-way junction by tolerance/min-degree tuning alone — documented in `junctions.py`'s
  docstring, not fixed. Also clarified (docstring-only, no behavior change): `nearby_ridges`/
  `nearby_valleys` both `None` already means "flat terrain," no new classification needed. 266
  tests pass. Raised while scoping tactical-landmark enrichment for Mission Interpreter — see
  `plans/world-model-tactical-landmarks/plan.md` and `plans/m10-road-junctions/`.

- [x] **Road-junction detection memory fix (no M-number — a bug fix on M10, not a milestone; done,
  merged 2026-09-13).** A real `syria-full` rebuild (with M9's OSM roads folded into the DCS
  `road` layer) died at Stage 5 ("road junctions") with a silent OOM-kill after OSM ingest
  completed. Root cause: M10's junction detector (`roadnet.junctions.extract_clusters` +
  `ingest_junctions.ingest_junctions`) bulk-loaded the entire combined `road` feature layer
  into one Python list before clustering — a size (~500K+ vertices at `syria-full` scale with
  OSM) that the pipeline had never actually run against, only extrapolated for. Fixed: spatial
  chunking reuses M8's existing chunk lattice (`store/chunks.py`), walking the theatre in 5 km
  tiles, querying padded-bbox per tile (`padding_m = max(tolerance_m * 10.0, 10.0)` = 10 m at
  defaults), clustering only within that tile's padded extent, keeping only clusters whose
  centroid falls in the tile's unpadded core (centroid-in-core ownership — no double-count,
  guaranteed exhaustive coverage). `roadnet/junctions.py` gains an additive, opt-in
  `vertex_bbox` parameter; `ingest_junctions` (bulk) is untouched; new
  `ingest_junctions_streaming` generator walks chunks. Planning deviation (discovered during
  implementation): region nominal bbox does not include all stored road features; fixed with
  new `feature_layer_bbox(conn, kinds)` MIN/MAX aggregate for actual data extent. Post-merge
  verification: all 341 tests pass (333 pre-existing + 8 new streaming/boundary/memory-bound
  tests), no regressions. Reviewer independently validated chunking correctness against
  `latakia-20km.sqlite` and confirmed the deviation's fix (MIN/MAX query prevents silent
  skipping of roads outside region bbox). Wall-clock time for Stage 5 may increase (roads
  are re-fetched once per chunk that overlaps them) but completion instead of OOM is the
  fundamental win. **Follow-up validation now done:** the user's `syria-full` rebuild of
  2026-09-15/16 completed Stage 5 in 2,885 s over 24,600 chunks (8,732 junctions kept) with no
  OOM — the fix holds at full theatre scale. That run also exposed a separate problem the
  streaming fix does not address: a handful of chunks take 330+ s each (~28 of the 48 minutes),
  with nothing logged during a single slow chunk and a badly swinging ETA. Filed to
  `todo/todo.md`. See `plans/junctions-streaming-fix/plan.md`,
  `plans/junctions-streaming-fix/review.md`, `plans/junctions-streaming-fix/dod-check.md`,
  and `plans/junctions-streaming-fix/implementation.md`.

- [x] **Road-junction progress logging (no M-number — a follow-up to junctions-streaming-fix; done,
  merged 2026-09-13, merge `8c18a2c`, branch `feature/junctions-progress-logs`).** A real
  `syria-full` rebuild logged nothing between `[5/8] road junctions: starting` and `done`, so a
  long Stage 5 looked hung. `ingest_junctions_streaming` now logs the road and chunk totals up
  front, then `chunk i/N`, percent, junctions kept, elapsed and a rough remaining estimate at
  most every 30 s (`_PROGRESS_LOG_INTERVAL_S`). Time-based rather than every-N-chunks because
  per-chunk cost varies widely between empty and dense chunks. One remaining gap: nothing is
  logged *during* a single slow chunk. 2 new tests (340 passed, 3 skipped). Small change, no
  plan/review files — Implementer plus self-review of the diff. Next-milestone impact: none; it
  only makes the pending `syria-full` validation run observable.

- [x] **HTTP API server (no M-number — a cross-subproject interface, done, merged 2026-09-12).** 
  Wraps world-model's read-only query surface (`describe_position`, `find_place_by_name`, 
  `line_of_sight_clear`) as a single-threaded `http.server.HTTPServer` for mission-interpreter's 
  `world_enrich/` package to call over the network (mirrors `aircraft-layer` ↔ `body-layer`'s 
  existing HTTP seam; `body-layer` ↔ `world-model` remains the sole in-process exception). 
  Implemented in `src/api/` (`server.py` + `__main__.py`); three `GET` routes with proper 
  error handling (400 on bad params/theatre mismatch, 404 on unknown path); test coverage 
  `tests/test_api.py` (10 tests). Single-threaded design (not `ThreadingHTTPServer`) is sound 
  for offline, low-volume, pre-mission use — `sqlite3.Connection` is not thread-safe by default, 
  and this is a read-only consumer. Enables MI-2 (world enrichment, producing `EnrichedMission` 
  with nearest-settlement/road/junction/terrain context attached to mission coordinates). See 
  `plans/mi2-world-enrichment/plan.md`.

- [x] **M9 — OSM augmentation (geofabrik) — done 2026-09-12, merged 2026-09-12.** Re-introduced
  OSM as an augmentation layer from offline geofabrik.de per-country extracts (`.osm.pbf` format,
  parsed via `pyosmium`'s C++-backed sparse_mem_array index to handle node-location resolution
  without Python-side memory blowup). Fills the `nearest_settlement`/`nearest_water`/
  `inside_settlement` gap M7 leaves `null` theatre-wide and unlocks settlement *boundary* polygons
  (DCS only ever gives center points). Stages 1-4 complete: (1) theatre bbox derivation and
  `M9_OSM_RUN_INSTRUCTIONS.md` with exact `osmium-tool` clip/merge commands; (2) `osm/pbf.py`
  parser, tested against synthetic fixture covering all four classification rules + dangling-node
  edge case + relation skip; (3) pipeline integration (`osm_pbf_path` parameter on `build_region`,
  additive alongside `osm_cache_path`, takes precedence); (4) validation against real
  `syria-260911.osm.pbf` extract (no classification-rule gaps found). Stages 5-6 (full 7-country
  merge + rebuild) are user-run prerequisites, documented in RUN_INSTRUCTIONS.md per execution-
  boundary pattern (mirrors M7). Implementation: `src/osm/pbf.py` (new), test coverage
  `tests/test_osm_pbf.py` + `tests/test_ingest_osm.py` (19 tests for classification logic, first
  direct coverage of code live since M3), `pyproject.toml` adds `pyosmium` dependency. Design
  Decision 3 verified: query surface unchanged (both Overpass and pbf paths produce identical
  `OsmFeatureSet` shape, so `query/describe.py` needs zero changes). Reviewer all-clear. DoD PASSED.
  See `plans/m9-osm-geofabrik/plan.md`, `plans/m9-osm-geofabrik/review.md`, `plans/m9-osm-geofabrik/dod-check.md`.

- [x] **OSM streaming-ingest memory fix (no M-number — a bug fix on M9, not a milestone; done,
  merged 2026-09-13).** A real `syria-full` rebuild (full 7-country merge, dominated by Turkey's
  646MB extract) stalled after ~8.6M ways / high memory usage on the user's Windows box, killed
  after 22 minutes of total silence — `osm/pbf.py`'s `_FeatureCollector` accumulated every kept
  node/way into Python lists for the entire `apply_file` pass, gigabytes of Python object overhead
  at theatre-merged scale. Fixed: `stream_features` flushes to caller callbacks every `batch_size`
  (50,000) elements instead of buffering the whole file; `build/pipeline.py`'s `osm_pbf_path`
  branch calls it directly, writing each batch to the store immediately (`tracemalloc`-verified
  memory bound, Reviewer confirmed the pipeline actually uses the new path, not just that better
  code exists unused). `load_features` (M9's original entry point) stays a thin
  backward-compatible wrapper (`stream_features` with an unbounded batch), so its existing
  correctness tests are untouched. New regression test proves streaming and bulk paths produce
  byte-identical output. Also produced a memory-exhaustion audit of the rest of the pipeline
  (`plans/osm-streaming-ingest/plan.md`'s addendum) — `roadnet/`, `ingest_srtm.py`,
  `ingest_terrain.py`, `dcs_data/towns.py` all judged fine at current scale; `roadnet/junctions.py`
  flagged as backlog below (unmeasured at `syria-full`+OSM-combined scale, probably fine by
  extrapolation but not confirmed). `M9_OSM_RUN_INSTRUCTIONS.md` updated with what steady-but-slow
  progress looks like vs. a genuine stall. Reviewer approved, no required fixes. See
  `plans/osm-streaming-ingest/plan.md`, `plans/osm-streaming-ingest/review.md`.

- [x] **OSM classified-feature persistent cache (no M-number — a performance optimization, not a
  milestone; done, merged 2026-09-13).** Extends M8's two-store pattern (persistent sibling store,
  atomic populate, explicit invalidation key) to a third instance: `<region>-osm-cache.sqlite`
  caches already-classified `StoredFeature` rows from M9's pyosmium parse + classification pass.
  Motivation: the ~25-30+ minute parse-plus-classify cost, while not eliminated, is incurred only
  once per `.osm.pbf`/classifier-version pair; subsequent `syria-full` rebuilds (schema bump, road
  fix, DCS patch) skip the expensive parse and copy pre-classified rows from the cache instead,
  completing the OSM stage in low minutes. Cache is **not** manually managed — automatic invalidation
  on: pbf SHA-256 hash, pbf file size (belt-and-suspenders), `CLASSIFIER_VERSION` (if rules change),
  `OSM_CACHE_SCHEMA_VERSION` (if `StoredFeature` shape changes), and region bbox (rows are baked
  with bbox clip). Populate is atomic (write at `.tmp`, `os.replace` to canonical path only after
  success) — no corrupt half-populated cache can silently lead to wrong data. Population happens
  during the same `stream_features` pass M9 already runs (piggybacks on `_flush_nodes`/`_flush_ways`
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

- [x] **OSM ingest optimization + landcover split (no M-number — an optimization and data-model
  change on M9, not a milestone; done 2026-09-16, merged 2026-09-16, merge `b9d7c17`, branch
  `feature/osm-landcover-optimization`).**
  Two changes in one branch: a tags pre-filter step that shrinks the `.osm.pbf` before parsing
  (RUN.md §2.4), and a rework of what OSM contributes — `road` dropped from OSM entirely (DCS
  `.routes` is authoritative, per root CLAUDE.md), `landcover` and `coastline` added as new kinds,
  multipolygon relations gain hole support, and every stored ring/line is simplified at
  `SIMPLIFY_TOLERANCE_M = 30.0` with a `MIN_AREA_M2 = 50_000.0` per-ring floor. New query surface:
  `describe_position`'s `nearest_coastline` (with a `side` of `"sea"`/`"land"`) and
  `inside_landcover`; body-layer turns both into crew-facing semantic facts. New `src/geometry/`
  package holds the ring/polyline primitives.

  Real `syria-full` build (run by the user on Windows against this branch state, 2026-09-15/16,
  ~60 min wall-clock): `landcover=44811` (`fields` 21428, `forest` 9710, `orchard` 7171,
  `scrub` 4027, `barren` 2475), `coastline=1269`, `water=5119`, `settlement=26182`,
  `named_place=23044` (21,862 OSM + 1,182 DCS `towns.lua` — both kinds share `named_place`),
  `road=14833` (DCS-only, unchanged from M7). Simplification: 8,343,864 → 2,010,767 vertices
  (24.1% kept) across 12,450 multipolygon relations, `relations_skipped=0`,
  `ways_skipped_unresolved_nodes=0`. Drops are all counted, per the module's "never a silent
  drop" convention: `rings_dropped_min_area=183492`, `holes_kept=4575` vs
  `holes_dropped_below_min_area=36974`, `lines_skipped_unclassified=291933`,
  `areas_skipped_unclassified=3708`, `unnamed_peaks_dropped=9867`, `unnamed_dams_dropped=689`.

  **`holes_dropped_not_contained_after_simplify=58`** is the number that mattered: the reviewer
  found (and a re-review corrected) that independently simplifying an outer ring and its holes can
  strand a hole partly outside its own outer ring, which `store/reader.py`'s `_distance_to_feature`
  would turn into a fabricated `nearest_feature` distance because it tests holes before the outer
  ring. The small-extract validation never exercised it; the full theatre hit it 58 times. Class of
  bug worth remembering: individually-valid transforms composing into an invalid structure — see
  NOTES.md.

  **Cache-invalidation defect found while reviewing that build's log and fixed here.** The hole fix
  (`638239a`) changed both `_ingest_ring`'s geometry output and `OsmIngestStats`' fields — two of
  the conditions the comment above `CLASSIFIER_VERSION` says must force a bump — but left the
  version at 3, the same value the pre-fix code used. A pre-fix cache would therefore have matched
  the invalidation key and been served as a hit, silently reinstating the invalid hole geometry the
  fix removed. (That one transition happens to raise `TypeError` in `load_cached_stats` instead,
  because the fix also *removed* a stats field — an accident of that change, not the invalidation
  working; any future `_ingest_ring` geometry change that left stats fields alone would have been
  served silently.) Bumped to `CLASSIFIER_VERSION = 4` with the rationale recorded inline. The
  user's own build is unaffected — its cache was written by post-fix code.

  Validation: Stage 6 small-extract control points (Hmeimim relation-derived settlement, sea/land
  sides west and east of Latakia, Lake Assad reservoir at distance 0) all pass; `latakia-20km`
  parse+ingest 9.15s cold / 0.07s cached; `describe_position` p99 34 ms at Lake Assad scale.
  474 world-model + 506 body-layer + 109 aircraft-layer tests pass.

  **Follow-ups, updated 2026-09-16 after a second `syria-full` build (Mac, cold cache, full
  log at `world-model/syria-full-build.log`):**

  - *OSM parse time* — **answered: 87.2 s**, against a plan estimate of ~2 min. That build genuinely
    parsed (no cache-hit line; it then wrote a 119 MB `syria-full-osm-cache.sqlite`), unlike the
    2026-09-15 Windows run whose 21.3 s Stage 3 was a warm-cache read of 99,243 rows.
  - *Peak RSS* — still unmeasured; nothing in the pipeline logs it. The plan's ~1–1.5 GB estimate
    stands unverified.
  - *Largest post-simplification polygon (the tiling gate)* — **answered, and it corrects an earlier
    claim**: Atatürk Baraj Gölü at 13,097 outer + 127 hole = 13,224 vertices, 3.9x the Lake Assad
    figure Stage 6's extract-scale validation had named. Still under the "tens of thousands"
    threshold, so no tiling — but at ~1.5x margin, not ~6x. See `world-model/CLAUDE.md`'s corrected
    paragraph.
  - *`describe_position` p99 at full-theatre scale* — **answered** (user-run
    `tools/measure_m7_stage4_perf.py latency --region syria-full`, 348 points: 8 control + 300
    random + 40 boundary): mean 53.4 ms, median 24.5 ms, p95 211.6 ms, **p99 440.7 ms**, max
    551.3 ms. Every quantile is roughly half M7's recorded baseline (mean 136.8 / median 52.4 /
    p95 497.7 / p99 803.4 ms), which also retires M7's own open flag that its p99 tail ran "~3x
    M5's baseline".

    **The apparent halving against M7 is not a code effect — do not cite it as one.** Resolved
    2026-09-16 by measuring the *same* milestone's store on both hosts:

    | | Mac | Windows (WSL, store on `/mnt/d`) | ratio |
    |---|---|---|---|
    | mean | 53.4 ms | 339.3 ms | 6.4x |
    | median | 24.5 ms | 151.0 ms | 6.2x |
    | p95 | 211.6 ms | 1101.4 ms | 5.2x |
    | p99 | 440.7 ms | 1929.2 ms | 4.4x |
    | min | 0.31 ms | 27.7 ms | 89x |

    Same store content, same code, ~4.4x apart at p99. **Host variance is several times larger
    than any delta this milestone could plausibly have caused**, and M7's 803 ms baseline has no
    recorded host and falls *between* the two — so it cannot support a claim in either
    direction. Any future `describe_position` latency comparison must name its host and,
    ideally, re-measure the baseline store on that same host; a bare number is not evidence.

    The `min` row is the diagnostic one. A best-case query does almost no work, so an 89x gap at
    the floor is near-constant per-query overhead rather than compute — consistent with SQLite's
    many small reads and lock operations crossing WSL's `drvfs` boundary to a Windows-mounted
    drive. **Leading hypothesis, not verified**; the cheap test is to copy `syria-full.sqlite`
    onto the WSL-native filesystem and re-run the same command. Worth doing only if world-model
    is ever queried *on* the Windows box.

    Operationally it currently is not: per the compute topology, body-layer runs on the Mac and
    imports world-model in-process, so the Mac column is the production path and the number that
    matters for the runtime budget. The Windows figures characterise a development-box
    filesystem penalty, not the deployed query path.
  - *§2.4 pre-filter node/way counts* — still open, upstream of the build log.

  **Cross-platform determinism confirmed** as a side effect: every OSM statistic from the Mac build
  is byte-identical to the Windows one — same 44,811 landcover, same
  `holes_dropped_not_contained_after_simplify=58`, same 8,343,864 → 2,010,767 vertices — from a
  fresh parse on a different OS. Same for the SRTM stats (47,484 void, `tiles_used=79`). Nothing
  in the ingest path is platform- or iteration-order-dependent.

  Next-milestone impact: none — all changes are additive except the `road`-from-OSM removal, which
  restores the DCS-authoritative invariant rather than breaking a consumer (mission-interpreter
  reads only `nearest_settlement.name`, untyped). Unblocks two previously-blocked follow-ups:
  landcover-aware detectability in body-layer perception, and a Mission Interpreter place-name
  fallback to `named_places_within_radius`. See `plans/osm-landcover-optimization/plan.md`,
  `.../review.md` (APPROVED), `.../dod-check.md` (PASS), `.../implementation.md`, and
  `research/2026-09-13-osm-landcover-optimization-validation.md`.

## Backlog (open, unscheduled)

- [>] **Power lines from DCS data — deferred 2026-09-13 (user: not important now).** Wanted as a
  low-level wire hazard and navigation landmark, but only with exact in-DCS positions (OSM's ~1 km
  offset rules it out as a source). Recon done: `research/2026-09-13-dcs-power-lines-recon.md`.
  Syria's model catalogs include `power_trans_line_big`/`power_pole_wooden`; placements live in
  `Scenes/Syria.scn5` (5.5 GB scenery placement database; header and 15,289-entry model-name table
  decoded, per-object record layout not). Recommended route when picked up: a live
  `world.searchObjects(SCENERY)` probe, `tools/dcs-mission-probe/power_line_scenery_probe.lua`
  (written, never run; run steps in its header). Alternative: decode `Syria.scn5` records, a large,
  uncertain reverse-engineering job.

- **Multi-theatre support (Afghanistan, Caucasus, Kola, others) — needed soonish, not yet scoped.**
  Raised 2026-09-13. Architecture already generalizes (`THEATRE_PROJECTIONS`/`REGIONS` are
  per-theatre registries, not per-theatre code forks) — this is "add entries + verify," not a
  rewrite. Per-theatre work identified: (1) Transverse Mercator projection params — `pydcs` has
  fitted values for every theatre, but each needs live-DCS verification against real
  `coord.LOtoLL` output like M1 did for Syria, not trusted blind; (2) a `RegionDefinition` entry
  (bbox/name) — cheap, mechanical; (3) raster chart registration (F10 paper map) — M2's Syria fit
  was hand-derived from real-world control points on that specific raster, genuinely per-theatre
  manual work, not automatable from the pattern; (4) DCS source files (`towns.lua`/`beacons.lua`/
  `.routes`) — same parsers *should* work (same DCS-internal formats) but need an investigator
  pass per theatre, not assumed, since format has drifted across DCS versions before and no
  theatre besides Syria has been checked; (5) OSM/Geofabrik country-extract set differs per
  theatre, same `derive_m9_osm_clip_bbox.py`-style approach per theatre.
  **Kola is a genuinely harder case, not just "repeat the pattern":** SRTM only covers ±60°
  latitude, and Kola peninsula sits ~68-69°N, entirely outside SRTM's coverage — needs a
  different DEM source (ASTER GDEM to 83°N, or a Nordic national elevation dataset), unresolved
  and needs its own investigation before committing. Afghanistan and Caucasus are both within
  SRTM range, no elevation-source blocker. Needs an Architect + investigator pass before any
  theatre starts, per this project's standing convention for DCS-internals-uncertain work.

- **RESOLVED: `roadnet/junctions.py` memory issue at `syria-full`+OSM scale (2026-09-13).**
  Raised 2026-09-12 during the OSM streaming-ingest memory audit (`plans/osm-streaming-ingest/plan.md`
  addendum): M10's bulk-load approach (`store.reader.all_features`) failed in practice when that
  `"road"` layer grew to include both DCS `.routes` and OSM `highway` ways (~500K vertices at
  theatre scale), causing a silent OOM-kill of the actual `syria-full` rebuild at Stage 5.
  **Fixed by junctions-streaming-fix (merged 2026-09-13):** spatial chunking walks the theatre
  in 5 km tiles with padded-bbox queries and centroid-ownership filtering, keeping peak
  vertex memory bounded to one tile's content instead of the whole layer. Correctness validated:
  synthetic and real-store (`latakia-20km`) tests prove chunked path produces byte-identical
  output to bulk path; Reviewer independently verified against real data. User's next real
  `syria-full` rebuild is the natural follow-up to confirm end-to-end completion (expected
  to complete, wall-clock time for Stage 5 may increase due to per-chunk road re-fetching).

- **Incremental per-layer pipeline builds.** `build_region` deletes and recreates the entire `.sqlite` on every call, forcing a full rebuild of all layers each time. Wanted: run individual pipeline sections (roads only, elevation only, validation only) and *add* that data into an existing store — staged builds, partial re-runs when debugging a single layer. Raised during M7 DoD acceptance testing (2026-09-06), explicitly considered for M8 and dropped from it to keep that milestone scoped to the probe store. M9 (OSM) would also benefit — see `plans/m9-osm-geofabrik/plan.md` design decision 4. See `plans/m7-full-theatre-pipeline/` and `src/build/pipeline.py`'s `build_region`.

Not doing yet (see concept doc "Things Not To Do Yet"): Petrovich dialogue, speech, embeddings, screenshot interpretation, full-theatre processing, elaborate distributed architecture. Threat-level-driven contact reporting/prioritization (`../docs/concept/threat-levels.md`) is deferred further still — runtime layer, needs contact memory + attention model (PB-2/PB-4) first.
