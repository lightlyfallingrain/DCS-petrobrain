# World Model Builder — Roadmap

Decisions locked in for this phase:

- **Theatre**: Syria (first).
- **Stack**: Python 3.11+, type-hinted, `mypy --strict`. Spatial libraries TBD during Milestone 1-2.
- **Machines**: DCS on Windows, dev on Mac, manual-copy workflow (`WORKFLOW.md`).

Milestones below are from `../docs/concept/WORLD_MODEL_BUILDER.md` — status tracked here as work proceeds.

**Live acceptance debt.** A milestone or fix can pass DoD on fixture testing alone; this list is
for the kind whose live-DCS acceptance was *deferred*, not waived, and hasn't been confirmed since
(mirrors `body-layer/ROADMAP.md`'s section of the same name). Clear an entry only once a real
sortie actually exercises it, and say which one.

- [ ] **`fix/los-elevation-tolerance` — `_TERRAIN_TOLERANCE_M = 12.0` added to
  `query.line_of_sight.line_of_sight_clear` (merged 2026-09-29), unflown.** Fixes a reproduced
  (offline, not yet re-confirmed live) defect: the SRTM elevation grid can place a real unit
  below the modelled terrain at its own position, permanently blocking terrain LOS to it from
  every angle. Card: `docs/acceptance/2026-09-29-los-tolerance-sortie.md` — same flight as the
  group-reporting acceptance. Settles two things a fixture cannot: whether Petrovich now detects
  the previously-missed insurgent AAA on a similar attack pass, and whether the 12 m tolerance
  starts revealing units genuinely masked by a ridge (accepted cost, but only a real flight can
  show it happening). Also carries `--detection-trace` and the two optional live-terrain-probing
  reads (`land.getHeight`, `bridge_call_ms`) riding along on the same sortie.

- [x] **`fix/latin-place-names` (`WM-B1`) — cleared by the user's 2026-10-02 `syria-full` build.**
  Name-source counts landed exactly as predicted: `via_name_en`≈12,926, `via_int_name`≈864,
  13,073-of-49,226. No outstanding item.

- [x] **`feature/landform-geomorphons` (`WM-B6`) raw extraction at theatre scale — cleared by the
  same 2026-10-02 build.** `ridge=700,142, valley=740,255` matched the pipeline's own measured
  figures exactly, confirming geomorphons extraction/tracing/caching/store-write all work
  correctly at full 131-tile scale. Not re-opened by the item below — that run is what *found* the
  two defects it fixes, not evidence against the extraction mechanism itself.

- [x] **`fix/landform-relief-gate` — cleared by the user's 2026-10-04 23:59 `syria-full` rebuild
  (verified 2026-10-05).** All three blocks of
  `docs/acceptance/2026-10-04-landform-relief-gate-rebuild.md` pass against the rebuilt store:

  - **Block A — zero relief-gate violations.** The query returns an empty list; no stored
    ridge/valley line has under 50 m of relief.
  - **Block B — `ridge=122,567, valley=112,232` = 234,799 combined**, hitting the predicted
    230-240k band exactly (it was a direct SQL measurement, and it did not move).
  - **Store size 720 MB, against a predicted 2.4-2.5 GB.** The prediction overshot ~3.3x. That is
    the safe direction, and the mechanism checks out rather than the geometry having been
    destroyed: median stored line is **5-6 vertices over ~1 km** (≈200 m vertex spacing, right for
    a 90 m DEM) and median relief is **90 m**, sitting in the middle of the user's own 50-150 m
    maskable-behind band with a hard floor at exactly 50.0 m. The extrapolation was from a
    geometry-byte reduction measured on sample data; at theatre scale the relief gate and the
    decimation compound, which the sample could not show. **This is the second time a reduction
    estimate on this feature has been off in the conservative direction** — the earlier one was a
    deviation check overstated by 5x. Treat these sample-derived size predictions as order-of-
    magnitude only.
  - **Block C — by eye, both renders.** Baalbek: the Bekaa floor is clean, lines confined to the
    flanking ranges and their real drainage (297 ridge / 282 valley lines in the 40 km window,
    611/672 dropped by the gate). Palmyra: the long isolated chains survive intact, crest-following,
    longest 6.06 km, flat desert clean.

  Original entry, for what it was clearing, follows. The 2026-10-02 build above, checked against the user's own acceptance
  criteria, found the ridge/valley layer had no relief gate (89-92% of stored lines under 50 m of
  relief; the Bekaa floor at Baalbek read as a valley) and stored geometry ~16x denser than a 90 m
  DEM supports (`feature` was 7.98 of 8.1 GB). Both fixed — see
  `plans/landform-relief-gate/implementation.md`. The theatre-wide feature count after the gate
  (234,799) is a direct SQL measurement against the existing store, not an extrapolation; the
  resulting store size (~2.4-2.5 GB, down from 8.1 GB) *is* extrapolated from a measured
  36.5-36.7x geometry-byte reduction, not from a full rebuild. It cleared on the user's own
  2026-10-04 23:59 rebuild, which fully invalidated the terrain cache as designed
  (`EXTRACTOR_VERSION` 1→2 plus two new knobs in the key — a full cold reprocess, not the warm
  path). Card: `docs/acceptance/2026-10-04-landform-relief-gate-rebuild.md` /
  https://claude.ai/artifact/S6sod3ZdB1mCWSYj8twCPP.

- [x] **`feature/terrain-landform-features` — marker-controlled watershed replaces the M6
  curvature ridge/valley detector (Stages 1-2). Merged 2026-10-01 (`0bef4b9`), and the user's own
  full-theatre build confirms it.** Acceptance ran against the real `syria-full` store, not a test
  region, and both falsifiable checks hold: **zero valleys within 8 km of Baalbek** (the Bekaa
  floor correctly excluded by the width gate, with three ridges flanking it at 2.1/7.4/7.8 km) and
  **Palmyra's isolated chains intact** (14 ridges within 20 km). Counts collapsed from the old
  11,749 ridges / 11,477 valleys to **8,189 / 2,314**, and sinuosity landed where the test regions
  predicted — **1.202 ridge / 1.172 valley** against the old 2.17/2.21.

  **One prediction missed, recorded rather than smoothed over**: ridge fragmentation came out
  **51.1 %** under 15 cells against the pooled test regions' 30.0 % (valleys: 28.9 % against
  22.2 %, close). Inspection of the densest patch shows this is **basin-pair segmentation at
  triple points**, not noise — a ridge is the divide between two specific basins, so a continuous
  crest is cut into separate features wherever a third basin touches it, and the segments sit on
  real crests. At the ~5 km working radius a 2-3 km segment is a serviceable referent, so this is
  not being tuned now; if "follow the ridge" navigation ever needs whole crests, the fix is merging
  adjacent segments that share a basin and continue in heading. **The broader lesson for this
  project's tuning method**: the three test regions were chosen because their answers were already
  known, so they do not sample ordinary terrain and over-promised by ~20 points on the one metric
  the motivating cases did not exercise.

  **Parked 2026-10-01 — see `WM-B6`.** The user judged the detector's real output wrong on the
  ground (aligned hillshade renders, three spacings): *"The real problem is that the ridge/valley
  detection itself does not seem to produce correct results."* The merge stands and the code is
  sound as written, but **the `ridge`/`valley` rows in `syria-full.sqlite` should not be treated as
  a layer to build on** until `WM-B6` is reopened. Stages 3-5 are parked with it.

  Card: `docs/acceptance/2026-10-01-terrain-landform-build.md` /
  https://claude.ai/artifact/AKXxX4R4R5a3tcztsR2qJC. DoD: `plans/terrain-feature-probing/
  dod-check.md`. Stages 3-5 (adjacency, bearing, callout) remain unbuilt — nothing in the cockpit
  changes from this. Follow-up queued as `WM-B4` (curve-smooth the polylines, user direction the
  same day after seeing the staircase in a real render).

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
    the floor is near-constant per-query overhead rather than compute — **and the cause is
    storage hardware: the Windows `D:` holding that store is a large mechanical HDD, while every
    other drive on that box is SSD** (user, 2026-09-16). A `describe_position` call needs a
    handful of random R*Tree and row reads; at ~8-12 ms of seek each, two or three of them land
    squarely on the observed 27.7 ms floor. An earlier note here blamed WSL's `drvfs` boundary
    instead — plausible, but it does not explain a floor that high, and the simpler hardware
    explanation fits the measurement much better.

    **Not being investigated further** (user direction 2026-09-16): which box runs which service
    is a placement decision, not a code problem, and the user manages it directly. Recorded only
    so nobody re-derives it from the numbers later, or reads the Windows column as a world-model
    regression.

    **This is a placement input, not just dev-box trivia.** Body-layer imports world-model
    in-process, and body-layer's host is *not* pinned — only aircraft-layer (Windows) and local
    LLM inference (Mac) are. So whichever box runs body-layer is the box that runs every
    `describe_position` call. Run body on the Mac and the budget is 440.7 ms p99; run it on the
    Windows box with the store on `D:` and it is 1929 ms, a 4.4x runtime cost decided entirely
    by where a file sits. If body-layer ever moves to Windows, put `syria-full.sqlite` on one of
    that box's SSDs first — it is a file copy, not an engineering task.
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

- [x] **LOS elevation-tolerance fix (no M-number — a bug fix, not a milestone; done, merged
  2026-09-29).** A real sortie (2026-09-28) flew close past an insurgent AAA position, boresight
  on an attack run, and Petrovich never called it out. Debugged and reproduced offline
  (`plans/missed-aaa-detection/debug.md`): `query.line_of_sight.line_of_sight_clear` treated its
  SRTM-sourced elevation grid as exact, so a unit sitting under a grid cell that overestimates
  ground height by as little as M7's own recorded error (mean −7.19 m, stddev 11.52 m) reads as
  permanently "underground" relative to the model at its own position — blocked from every
  angle, at every range, not a per-look coin flip. Fix (user-chosen option 1 of five laid out):
  `_TERRAIN_TOLERANCE_M = 12.0` (rounded up from the stddev) added to the terrain-blocking
  comparison in `world-model/src/query/line_of_sight.py` — terrain blocks only when it exceeds
  the sightline by more than that margin. A module constant, one comparison, one caller
  (body-layer's `perception.geometry.line_of_sight_clear`, an unchanged thin wrapper); no
  override surface. Two new regression tests pin the reproduction and the exact 12.0 m boundary
  in both directions. **Accepted cost, explicit and permanent, not a stopgap**: a unit genuinely
  masked by a real ridge clearing the sightline by less than 12 m now reads as visible — accepted
  because the Mi-24P attacks in a run rather than from a masked pop-up hover (user direction,
  2026-09-28); revisit if this primitive is ever asked to model a pop-up-and-shoot airframe
  (Ka-50, Apache). Reviewer: APPROVED, no required fixes (one optional boundary-test refinement,
  acted on in a follow-up commit). Security: APPROVED — confirmed the fix implements exactly the
  accepted no-omniscience trade and nothing wider. Both `world-model` (475 passed/3 skipped) and
  `body-layer` (1313 passed/4 xfailed, consumes the primitive via the unchanged wrapper) full
  check suites re-run clean. **Unflown — see "Live acceptance debt" above.** Next-milestone
  impact: none — a same-module constant change, no consumer contract change. Surfaces a broader
  gap worth tracking (`WM-B3` below): the elevation grid's own measured 11.52 m stddev sat in a
  research note for three weeks while a downstream gate consumed that data as if exact — the
  defect was in the gap between the measurement and its consumer, not in either one. See
  `plans/missed-aaa-detection/debug.md`, `.../implementation.md`, `.../review.md`,
  `.../security-review.md`.

## Backlog (open, unscheduled)

Items here are `WM-B<n>`. A new one takes the next unused number; numbers are never reused or
renumbered, `[x]` items included (root `CLAUDE.md`, "Backlog Management").

- [x] **WM-B1 — Prefer a Latin-script place name at OSM ingest.** Named places currently store OSM's `name`
  tag verbatim, so Syrian features arrive in Arabic script — and **DCS cannot render non-Latin-1
  text**, so they reach the cockpit overlay as blanks (observed live, 2026-09-18). Body-layer now
  guards at render time (`belief.enrichment.displayable_name` drops an unrenderable name so the
  caller falls back to "a wadi"/"a village"), which makes the current data usable but loses real
  information: many of these features *do* have an `name:en` or `int_name` tag carrying a perfectly
  good romanisation. Fix at ingest: prefer `name:en`, then `int_name`, then `name`, and record which
  was used. Needs a rebuild to take effect, so it should ride along with the next full-theatre run
  rather than triggering one.

  **Implemented, `fix/latin-place-names`** (2026-10-02). `build.ingest_osm._select_name` picks the
  first of `name:en`/`int_name`/`name` that both exists and actually encodes as Latin-1 (a
  romanisation can itself still fail that check), applied uniformly across every classified kind
  that carries a name — `named_place` (point and dam-line), `water`/`coastline` lines, and
  `settlement`/`landcover` areas via `_ingest_ring`, not just the one kind the item names. Which tag
  won is recorded as a new reserved `tags["name_source"]` entry (`store/models.py`'s existing
  convention; no schema change, `tags` is already a generic JSON blob) — `"name:en"`, `"int_name"`,
  or `"name"` (the last also covers the no-romanisation-available fallback, so a feature that would
  previously have stored an untranslatable name unmarked still does, just now distinguishable from an
  actual romanisation). `CLASSIFIER_VERSION` bumped 4 → 5 to force `osm-classified-cache` invalidation
  (verified: `cache_meta_matches` compares it against the cached meta, so a stale `CLASSIFIER_VERSION
  = 4` cache is correctly rejected rather than silently served). Renderability is checked with the
  same `name.encode("latin-1")` test as body-layer's `belief.enrichment.displayable_name`, but **not
  imported from it** — `body-layer` → `world-model` is the one sanctioned in-process cross-subproject
  import (root `CLAUDE.md`'s "Module independence"), and the reverse direction would be a new,
  unjustified coupling; both copies' docstrings say to keep them in sync by hand.

  **Measured against the real `syria-full` build** (`data/world-model/syria-full.sqlite` +
  `data/raw/osm/syria-theatre.osm.pbf`, read-only copies, never the live files): of 49,226
  `named_place`/`settlement` rows, 19,553 (40%) currently store a non-Latin-1 name — not only Arabic;
  this theatre's merged extract also carries Greek/Hebrew/Turkish names outside Syria proper. Of
  those, **13,073 (67%) have a usable `name:en` or `int_name` in the source `.osm.pbf`** (12,926 via
  `name:en`, a further 864 via `int_name` where `name:en` was absent or itself unrenderable) — this
  fix's real yield on the next rebuild. The remaining 6,480 (33%) have neither tag, or neither
  renders, and keep falling back to the raw non-Latin-1 name, same as before — body-layer's
  render-time guard still degrades those to a generic label. Worth saying plainly: a third of the
  affected features gain nothing from this change; it is a real improvement, not a complete fix.

  Full detail: `plans/latin-place-names/implementation.md`.

  **DoD (2026-10-02): Reviewer and Security both APPROVED, no required fixes; mechanical checks
  (`ruff format`/`check`, `mypy --strict`, `pytest`) independently reproduced — 511 passed, 3
  skipped, 20 new tests, zero regressions against `main`'s 491/3 baseline. No separate acceptance
  card: this change produces zero observable effect until a full-theatre rebuild runs (the user's
  to trigger), expected to ride along with `WM-B6`'s rebuild rather than its own. So this `[x]` means
  code merged and gated, not verified against real output yet — that verification is the following
  check, to run against `syria-full.sqlite` once that rebuild completes:**

  ```sql
  SELECT
    SUM(CASE WHEN json_extract(tags_json, '$.name_source') = 'name:en' THEN 1 ELSE 0 END) AS via_name_en,
    SUM(CASE WHEN json_extract(tags_json, '$.name_source') = 'int_name' THEN 1 ELSE 0 END) AS via_int_name,
    SUM(CASE WHEN json_extract(tags_json, '$.name_source') IS NOT NULL THEN 1 ELSE 0 END) AS any_name_source,
    COUNT(*) AS total
  FROM feature
  WHERE kind IN ('named_place', 'settlement');
  ```

  (table/column names confirmed against `world-model/src/store/schema.py`'s real `CREATE TABLE
  feature (... tags_json TEXT ...)` — not guessed from the ORM-style naming `StoredFeature`/`tags`
  might suggest.) `name_source = 'name'` covers both an already-Latin-1 name that never needed
  romanising *and* the 6,480 still-unrenderable fallback rows, so SQL alone can't isolate the
  "gained nothing" count — follow with a Python pass over rows where `name_source = 'name'`,
  checking `name.encode("latin-1")` the same way `_is_latin1_renderable` does, and count the
  failures. Predicted: `via_name_en` near 12,926, `via_int_name` near 864 (summing to the
  13,073-row yield), and roughly 6,480 of the `name_source = 'name'` rows failing that Python-side
  encode check. A result far off any of these means the fix did not take effect as expected on the
  real extract and needs a debugger pass before this item can be called verified, not just merged.

  **Milestone Completion question**: this does not change what the next milestone should be or
  invalidate a downstream assumption — it is a localized data-quality improvement inside the
  existing OSM ingest pipeline; `WM-B6` (geomorphons), already in flight, is unaffected in either
  direction, and no other roadmap item depended on `name`/`name_source` having a particular shape
  before this landed.

- [>] **WM-B2 — Power lines from DCS data — deferred 2026-09-13 (user: not important now).** Wanted as a
  low-level wire hazard and navigation landmark, but only with exact in-DCS positions (OSM's ~1 km
  offset rules it out as a source). Recon done: `research/2026-09-13-dcs-power-lines-recon.md`.
  Syria's model catalogs include `power_trans_line_big`/`power_pole_wooden`; placements live in
  `Scenes/Syria.scn5` (5.5 GB scenery placement database; header and 15,289-entry model-name table
  decoded, per-object record layout not). Recommended route when picked up: a live
  `world.searchObjects(SCENERY)` probe, `tools/dcs-mission-probe/power_line_scenery_probe.lua`
  (written, never run; run steps in its header). Alternative: decode `Syria.scn5` records, a large,
  uncertain reverse-engineering job.

- [ ] **WM-B3 — Measured data-quality figures need to reach their consumers, not just a research
  note.** Raised 2026-09-29, from `fix/los-elevation-tolerance`: M7's SRTM-vs-DCS accuracy figure
  (mean −7.19 m, stddev 11.52 m) sat correctly recorded in `world-model/ROADMAP.md`'s M7 entry for
  three weeks while `query.line_of_sight.line_of_sight_clear` consumed the elevation grid as if
  exact, causing a real missed-detection defect. The measurement wasn't wrong and the consumer
  code wasn't wrong in isolation — the gap was that nothing connected the two. No fix scoped yet;
  worth asking, next time a grid/store gains a measured error figure, whether every consumer that
  treats that data as exact has been checked against it, rather than trusting a docstring or
  roadmap entry to be read at the right moment.

- [ ] **WM-B4 — Smooth the ridge/valley polylines into curves instead of cell-edge staircases.**
  User direction, 2026-10-01, after looking at the first real watershed output: *"what I'd change is
  using bezier (or similar) lines instead of straight segments. That would solve much of the
  jaggedness and give a more realistic ridge (or other divider)."* The axis-sliced extraction that
  shipped is monotone and no longer wanders (sinuosity 2.2 → 1.2 on the real theatre), but it still
  emits one point per 500 m grid slice, so a crest renders as a staircase of cell-aligned steps that
  no real ridge has.

  **The tension to resolve before implementing, not after**: `terrain/features.py`'s own standard is
  *"an honest polyline through actual sampled grid points"*, and a fitted curve introduces positions
  that were never sampled. The counter-argument is that the staircase is itself an artifact — of
  500 m quantisation, not of the terrain — so a curve constrained to stay within the sampled band is
  the *better* estimate, not a fabrication. Suggested resolution: keep the fitted curve's maximum
  deviation from the sampled points below half a cell (250 m), which is already inside the stored
  `position_uncertainty_m`, and say in the docstring what the points now are. A centripetal
  Catmull-Rom or Chaikin pass is likely a better fit than a Bézier, since both interpolate rather
  than requiring control points off the crest.

  Consumers to check before changing the stored geometry: `geometry.signed_side_of_polyline`
  (proven on coastline), `geometry.bearing_deg`, and whatever Stage 3's adjacency ends up reading.
  Densifying into the same `LineString` shape keeps all three working unchanged.

  **Superseded by `WM-B6` and parked with it, 2026-10-01.** Implemented on
  `feature/landform-curve-smoothing` (unmerged, Chaikin, measured max deviation 182 m against the
  250 m cap) — but smoothing a line that is in the wrong place does not help, and the user's verdict
  below retires this as a standalone item. Keep the branch; revisit only once detection quality is
  fixed.

- [ ] **WM-B5 — Valley boundary extraction: where a valley *ends*, not just where its floor runs.**
  **This entry was written 2026-10-05, after an audit found `WM-B5` cited in `WM-B6`'s parking list
  and in several plans while no entry defining it existed anywhere in this file.** The ID was in use
  before it was declared; it is written down here rather than renumbered, per the never-reuse rule.

  What it means: the stored `valley` rows are **centre lines**, not extents. A pilot asking whether
  a contact is *in* a valley is asking about an area, and the line cannot answer it — which is
  exactly the gap `plans/terrain-feature-probing/`'s Revision 3 works around with a nearest-line
  dominance rule rather than closing. The honest versions are a per-vertex half-width (cheap, keeps
  the `LineString` shape, consumers unchanged) or a real polygon (expensive, new geometry type, new
  storage question).

  **Not scheduled, and deliberately so**: Revision 3's dominance rule is the cheap approximation,
  and whether it is good enough is a listening question the next sortie answers. Revisit only if
  flying shows "in a valley" landing on contacts that are plainly not in one.

- [~] **WM-B6 — Ridge/valley detection rebuilt on geomorphons. Unparked 2026-10-01, same day it
  was parked**, because the prior-art spike produced a design the user accepted from the renders
  and because `WM-B1` (Latin-script place names) already forces a full-theatre rebuild — so the
  expensive pass can ride along rather than triggering a second one. User: *"since WM-B1 needs
  world model rebuild, go ahead and start on WM-B6 also. Build the cache from the beginning so
  that we don't have to recreate the data every world model rebuild."* **The cache is not a
  follow-up stage: it is part of the first build**, per that instruction and the cache section
  below.

  The original parking text follows, because the judgement that caused it still stands over the
  old mechanism and is the reason the new one exists.

  **Originally: ridge/valley detection does not produce correct results. Parked 2026-10-01, needs
  much more effort at some other time.** User direction, after looking at aligned SRTM-hillshade
  renders of real output at three grid spacings:

  > *"500 m grid is too coarse, not useful. 250 m grid, if smoothed, would be precise enough, but
  > the data is bad. The real problem is that the ridge/valley detection itself does not seem to
  > produce correct results. Smoothing or finer grid does not solve that."*

  **This parks the whole landform line of work** — `WM-B4` (smoothing), `WM-B5` (valley boundary
  extraction) and `plans/terrain-feature-probing/`'s unbuilt Stages 3-5 (adjacency, bearing, the
  callout). Nothing should be built on `feature(kind='ridge'/'valley')` until this is reopened, and
  the merged detector's output in `syria-full.sqlite` should be treated as unreliable rather than as
  a layer later work can assume.

  **What is already known, so a future attempt does not re-derive it** (full detail:
  `research/2026-10-01-terrain-detection-resolution-spike.md`, branch
  `spike/terrain-detection-resolution`):

  - **The `min_cell_count` floor scaled by area while gating a 1-D line feature**, demanding ~150
    cells at 100 m where 500 m demands 6. That suppressed fine-spacing recall to ~1 surviving ridge
    where a linearly-scaled floor finds 23-37, and **it is why three separate sweeps concluded
    "finer spacing does not help"** — they were measuring their own floor. This is a real, fixed-in-
    principle bug and must not be rediscovered as a new finding.
  - **"Too coarse" is point density, not the floor**: the extraction emits one point per grid cell,
    so 500 m spacing puts 500 m between points. 250 m with the corrected floor is the affordable
    improvement (~6 GB, ~110 s extrapolated full-theatre); **100 m is infeasible as written**
    (~38 GB, from nested Python lists and a per-cell dict in `grow_basins` — a data-structure cost,
    not an algorithmic one, so a re-architecture could change this).
  - **Valleys stay sparse in steep terrain at every spacing and floor tested** — unexplained by the
    floor, and the spike's own guess is that one basin core swallows several real draws. This is a
    basin-definition question and is the most likely root of the user's "the data is bad", since
    *"next valley"* is a headline callout.
  - The watershed mechanism itself was never shown to be wrong, only never fairly tested; the
    user's judgement is about the **output**, which is what matters. A future attempt should treat
    "is a marker-controlled watershed the right mechanism at all" as open rather than settled.

  **Reopening condition**: a consumer that actually needs landform references — the Stage 5 callout
  (*"at the foot of the hill"*, *"next valley"*) or navigation phrasing once Petrovich flies. Until
  then this is unbuilt capability, not a defect in anything shipping.

  **The approach to try when it reopens — user's own, 2026-10-01, and it reframes the problem:**

  > *"You did create those shadow mapped terrain elevation images. That* **is** *the data. It*
  > **shows** *the ridges and valleys. If that was directly from the SRTM data that is on the disk,
  > we can use that as the source. ... can we just use the SRTM source, parse ridge/valley data from
  > it, as precise as it allows, and save the finished (smoothed) lines to world model. That'd
  > remove a whole lot of elevation data that we don't particularly need and replace it with terrain
  > features data that we actually do need. The ridge/valley lines would obviously have to carry
  > elevation data with them."*

  The hillshade renders that produced this judgement were built straight from the raw `.hgt` tiles
  at ~90 m, sampled in DCS x/z — not from the stored 500 m grid. **So the detector has been run at
  one fifth of the resolution the source already offers, for no reason except that the pipeline
  happened to detect off the stored grid.** Detect at native SRTM resolution, store only the
  resulting lines with their elevation profile. The plan always allowed processing spacing and
  storage spacing to differ; nothing ever acted on it.

  Two corrections to the storage half of the argument, neither fatal to it:

  - **Correction, 2026-10-01 (user): LOS is not a reason to keep the elevation grid.** This entry
    first claimed `query.line_of_sight.line_of_sight_clear` pins the grid in place. That is
    superseded by `plans/dcs-driven-los/plan.md` — DCS answers line of sight directly (terrain +
    buildings, collector-side, true position to true position), and the world model's own LOS
    primitive is *"way too imprecise exactly because of the sparse grid"* (user's words). So the
    grid's remaining consumers are elevation lookups in `describe_position` and the landform
    detection itself — and if detection moves to native SRTM, the case for storing any elevation
    mesh gets thinner rather than stronger. Re-check what still reads `sample_grid` before
    assuming it must stay.
  - **The storage saving is still smaller than it looks.** Measured on the real
    `syria-full.sqlite` (608 MB): `grid_sample` is **49 MB**, while `feature` is **576 MB**. The
    elevation grid is ~8 % of the store; OSM features are the bulk. Dropping it is defensible on
    its own terms once nothing reads it — but the reason to do this work is **quality**, not disk.

  What this does not answer, and must not be assumed away: the user's judgement was that the
  *output* is wrong, and a human eye reading a hillshade is doing the detection that the code has
  to do by itself. Native resolution supplies the signal; it does not supply the algorithm. The
  sparse-valleys-in-steep-terrain finding above is still unexplained and is the most likely root.

  **And the algorithm is explicitly in scope when this reopens** (user, 2026-10-01): *"Ridge/valley
  detection algorithm can and should be refined if it does not produce correct results. Or
  swapped/rewritten completely."* The marker-controlled watershed is not protected by having been
  built — a future attempt should weigh replacing it against refining it on the evidence, not
  inherit it.

  Memory is the practical constraint and has a known shape: the spike measured ~38 GB extrapolated
  at 100 m theatre-wide, from nested Python lists and a per-cell dict in `grow_basins`. **Tile-wise
  processing with overlapping margins** — SRTM's own 1° tiles are the natural unit — bounds that by
  construction and is the obvious way in, since the output is per-feature lines rather than a
  global grid.

  **Prior art surveyed before a third in-house attempt** (user direction, 2026-10-01: *"No need to
  build our own if there's something we can use, library or example."*). Full survey with sources:
  `research/2026-10-01-terrain-feature-detection-prior-art.md`.

  - **Primary candidate: geomorphons via WhiteboxTools.** Geomorphons classifies each cell into one
    of ten landform types (ridge, valley, spur, hollow, slope…) from a line-of-sight ternary
    pattern and is multi-scale by construction. WhiteboxTools ships `Geomorphons`, `FindRidges`,
    `ExtractValleys` **and `RasterStreamsToVector`** — and that last one matters most: it is the
    only surveyed tool that goes raster → clean `PolyLine`, which is precisely the step this
    project's own code botched twice (zigzag, then fragmentation). Cost: a binary-subprocess
    dependency and a `.hgt`→ESRI-ASCII bridge (modest, no GDAL). `curvature.py` and the basin core
    would be replaced; `StoredFeature`/provenance shaping survives.
  - **Licence constraint, and it rules out most of the obvious names**: GRASS, RichDEM, pysheds and
    pytopotoolbox are **GPL-3.0 / GPLv2+**, which conflicts with this project's intent to be public
    open source under a permissive licence. pysheds additionally pulls GDAL back in via rasterio,
    which M4 deliberately avoided. **Do not let a future architect reach for these without seeing
    this.** WhiteboxTools' MIT licence was corroborated from secondary sources but **not** read from
    its own LICENSE file (one fetch 404'd) — verify before committing to it. Landlab's MIT is
    unverified for the same reason.
  - **Drainage, not watershed basins, is the structurally better fit for the valley half.** A
    watershed basin is one blob per local minimum, which is exactly the observed "one basin
    swallows several draws" failure; a traced flow-accumulation channel keeps each tributary
    distinct until confluence. This independently matches the user's own *water flow, not rooms and
    doorways* analogue in `plans/terrain-feature-probing/explore-notes.md`.
  - **Fallback if a new dependency is unwanted**: D8 flow accumulation in-house — tens of lines
    over numpy, same complexity class as the priority-flood basin grower already shipped — keeping
    the project's own axis-sliced line extraction.

  ### DECIDED 2026-10-01 — geomorphons, classified then vectorised. User's call, from the renders.

  > *"The second image looks like the data I want. The lines there could use smoothing, probably
  > with the earlier smoothing algorithm we tried. But it does get the ridges and valleys correctly
  > and that is what matters. Choose Geomorphons approach."*

  **This overturns the spike's own D8 recommendation, and the reason is worth keeping.** The spike
  preferred in-house D8 drainage; the user then pointed at a single long ridge spanning one test
  window and showed what each approach did with it. Inverted-DEM drainage finds a crest only where
  the *inverted* catchment accumulates, so **every saddle breaks the line** — at a high threshold
  almost nothing was detected on that ridge, at a low one it became disconnected pieces plus a
  thicket of branch noise. Geomorphons labels a crest cell because the cell *looks like* a crest,
  independent of what is upstream, so a long ridge survives as a long ridge. Measured on that
  window: longest traced ridge **8.3 km** and valley **6.5 km**, against D8's fragments.

  **The pipeline, as validated by eye:**

  1. **Geomorphons classification** over the native-resolution DEM (~90 m SRTM, sampled on a DCS x/z
     lattice). Pure numpy, ~40 lines, no dependency: per cell, eight directions, line-of-sight
     zenith/nadir angles within a lookup radius, a flatness threshold, then the paper's ternary
     pattern → one of ten landform classes. Spike parameters that produced the accepted render:
     **lookup 15 cells (~1.35 km), flatness 1°**. WhiteboxTools is *not* needed — it was the
     survey's route to geomorphons, and an in-house implementation removes the binary dependency,
     the licence question and the Windows-support question in one go.
  2. **Masks**: ridge family = `ridge` + `peak`; valley family = `valley` + `pit`. (`spur`/`hollow`
     were left out of the accepted render — revisit, they may be what "at the foot of" wants.)
  3. **Binary closing before thinning.** Without it, a crest the classifier drops for a single cell
     breaks the line.
  4. **Zhang-Suen thinning** to a one-pixel skeleton.
  5. **Trace walking *through* junctions, not cutting at them** — at a fork continue in the
     incoming direction, stop only on a genuinely sharp turn. **This step is what makes or breaks
     the result**: naive cut-at-every-junction tracing gave 516 ridge fragments with a 2.2 km
     longest; the same skeleton with gap-closing and junction-walking gave 312 lines and the 8.3 km
     crest. It is also a heuristic — right for a spur leaving a ridge, wrong where two comparable
     crests genuinely meet — and needs checking on more terrain than one window.
  6. **Smoothing: reuse `WM-B4`'s Chaikin pass** (user's own instruction above). It is implemented
     and measured on `feature/landform-curve-smoothing` — deviation bounded by construction, 182 m
     max against a 250 m cap — so it is a port, not new work.
  7. Store as `LineString` features carrying their elevation range, as today.

  **Known costs and gaps, honestly:**

  - **The thinning is the scaling problem, not the classification.** Geomorphons is vectorised
    numpy (8 directions × lookup radius array ops) and tiles naturally; Zhang-Suen as written in
    the spike is a pure-Python double loop — 0.1 s for a 178×178 window, which extrapolates to
    hours over a theatre at 90 m. Vectorise it, or take a thinning from a permissively-licensed
    library, before this is anything but a spike.
  - **Density is still a product question.** 135 ridges and 121 valleys over 0.8 km in a 16×16 km
    window: fine as geometry, far too many to *speak*. The consolidation question does not go away,
    it changes from "reconnect the pieces" to "which of these is worth mentioning".
  - Spike implementation kept at `world-model/tools/spike_geomorphons.py` on
    `spike/terrain-detection-resolution` — scratch code, not a pipeline module.

  **Cache the extracted lines to a file, exactly as the OSM pass already does** (user direction,
  2026-10-01): *"data must be cached to a file, similar to OSM processing. It's too expensive to
  run at every world model rebuild. If cache exists, then just bring that into the sqlite."*

  This is the established third-store pattern, not a new mechanism — `world-model/CLAUDE.md`
  documents `data/world-model/<region>-osm-cache.sqlite` alongside the base store and M8's probe
  store, built for the same reason (a ~25-30 minute classify pass that hurts a rebuild loop).
  Mirror it:

  - A sibling cache file per region, `src/osm_cache/`'s layout as the template (schema / models /
    writer / reader / paths / hashing).
  - **Validity is a conjunction, and any mismatch means a full rebuild, never a partial reuse** —
    same rule the OSM cache already enforces: the DEM source's hash and size, the extractor's own
    version constant (the geomorphons parameters, mask membership, closing/thinning/tracing and
    smoothing all belong in it, since changing any of them changes the output), a cache schema
    version, and the region's bbox.
  - Populate at a `.tmp` path and `os.replace` into place only after the whole pass succeeds, so
    existence at the canonical path is the only validity signal and no flag column is needed.
  - On a hit, insert through the existing `store.writer.insert_features` per batch rather than a
    hand-rolled `ATTACH` + bulk copy — again the OSM cache's own choice, with the bulk path
    documented as the fallback if it proves slow at real scale.

  Note this fits the storage argument above rather than cutting against it: the cache holds the
  **lines**, which are small (4.6 MB of ridge+valley geometry on the current store against 49 MB of
  `grid_sample`), while the expensive thing being avoided is the native-resolution pass that
  produced them.

  **No longer parked — this is the design being built** (user, 2026-10-01). Build order follows
  from his own instruction: the cache is in from the first pass, not retrofitted.

  **The consumer half, user 2026-10-01**: *"Could we replace contact enrichment of near that hill
  to work from the ridge/valley data? Then we'd not need elevation grid for that and the ridge
  valley data would be superior in quality anyhow."*

  Checked, and it holds — with one exception that has to be named rather than discovered later.

  - **A ground unit's elevation already comes from DCS, exactly, per poll.**
    `aircraft_layer.schema.world_objects.WorldObjectSample` carries `altitude_m` on every object,
    and for a ground unit that *is* the ground elevation at its own position — DCS-authoritative,
    not SRTM-interpolated, and better than anything the grid can give (M7 measured the grid at
    −7.19 m mean / 11.52 m stddev against DCS). So the foot/slope/crest judgement is
    *contact's own reported altitude* against *the landform's stored `elevation_range_m`*. Neither
    term needs `sample_grid`.
  - `belief/enrichment.py` already consumes `describe_position`'s `nearby_ridges`/`nearby_valleys`
    and those features already carry `elevation_range_m` from their own `tags_json`. The rework is
    in which fields the fact is built from, not in new plumbing.
  - **The supposed offline exception is weaker than first stated — checked 2026-10-01 at the user's
    question "what does the MI need elevation for?".** Nothing in `mission-interpreter/src` reads
    `elevation` by name. `world_enrich/enrich.py` stores the whole `GET /describe_position` JSON
    blob as `WorldRef.position`, and `synth/prompts.py` reads only the nested place-name field out
    of it. So elevation currently reaches Mission Interpreter as unread payload, not as a
    dependency. Removing it would change what an LLM sees in context, which is a judgement call
    about mission understanding, **not a broken consumer**. Still worth re-grepping
    `query/describe.py`'s readers before deleting anything — but no code blocks this.
  - Net effect if both halves land: the grid stops being load-bearing for anything the pilot hears
    (DCS answers LOS, DCS answers elevation, features answer landform), which is what makes
    detecting at native SRTM resolution and storing only lines a coherent design rather than a
    half-measure.

  **And the last step the user proposed, 2026-10-01**: *"If something does need elevation, it could
  be approximated from the ridge/valley lines. Not perfect, but neither is the sparse grid. And
  we'd get rid of the grid data altogether. This of course requires high quality ridge/valley
  lines."*

  This is an established cartographic idea, not an improvisation — ridge and valley lines are
  terrain's *structure lines*, and interpolating a surface between them (TIN or natural-neighbour
  over structure lines) is a standard reconstruction. Worth noting that it sets the quality bar
  itself: an approximation is only as good as the lines, which is exactly why `WM-B6` is parked.

  Three things to weigh when it is tried, two of them favourable:

  - **Size, measured on the real store**: ridge+valley geometry is **4.6 MB** (3.5 MB ridge, 1.1 MB
    valley) against `grid_sample`'s **49 MB**. Even at native resolution with many more features,
    structure lines are a fraction of a mesh — and they carry meaning the mesh does not.
  - **Accuracy is a trade, not a loss.** The grid is bilinear interpolation between 500 m samples
    and measured at −7.19 m mean / 11.52 m stddev against DCS. Interpolating between a crest and a
    floor is worse for an absolute height on an open slope, and *better* for the relational
    question anything here actually asks — is this unit above or below that ridge, at its foot or on
    its crest.
  - **Flat ground: the caveat was raised here and then mostly withdrawn, 2026-10-01, at the user's
    question "where do we need flat ground elevation and why?".** Two answers, and both deflate it.

    *Nobody reads it.* `body-layer/src/perception/geometry.py::elevation_at` is the only consumer of
    `describe_position`'s point elevation anywhere in the subprojects, and it has **no production
    callers** — only its own test. LOS moves to DCS, contact enrichment uses the unit's own
    DCS-reported `altitude_m`, and Mission Interpreter never reads the field. So "elevation on flat
    ground" is not currently a question anything asks.

    *And where it is flat, the error is small because it is flat.* Interpolating from distant
    anchors over low-gradient ground is cheap in error terms; the degeneracy is largely
    self-correcting. The residual case is two flat areas at genuinely different heights — a plateau
    above a plain — and the boundary between them is an escarpment, which **is** a structure line,
    so the anchors exist exactly where the height changes.

    Keep as an open design point rather than a blocker: if a consumer ever does need absolute
    elevation over featureless ground, a very coarse mesh is cheap and accurate precisely there.
    Do not let it hold up dropping the grid.

  **Implementation status — DoD-passed 2026-10-02, live acceptance outstanding (see "Live
  acceptance debt" above), merge pending (`feature/landform-geomorphons`,
  `plans/landform-geomorphons/plan.md`/`implementation.md`/`dod-check.md`).** A Performance
  Reviewer pass found and a follow-up fix (`b4d38cf`) closed one blocking finding — unbounded
  whole-theatre memory accumulation (~29 GB extrapolated) — fixed to a per-tile-bounded ~1.75 GB
  plateau, independently re-verified by Reviewer round 3 on different real tiles. The same fix cut
  the O(N²) Chaikin-smoothing deviation check to O(N), bringing the extrapolated full-theatre
  terrain-stage CPU cost from ~25 minutes down to ~14 minutes. Everything this plan scoped
  (Stages A-F) is in place: vectorised geomorphons classification
  (`terrain/geomorphons.py`), vectorised Zhang-Suen thinning + the ported junction-walking tracer
  (`terrain/skeleton.py`), vectorised DCS-lattice resampling (`terrain/resample.py`), per-SRTM-tile
  margin/clip tiling with the resumable cache built in from the first pass (`terrain_cache/`,
  `build/ingest_terrain.py`), and `build/pipeline.py`'s terrain stage rewired off `srtm_tile_paths`
  directly rather than the stored grid. The watershed-era `terrain/curvature.py` and its
  basin/divide machinery in `terrain/features.py` are deleted; the elevation grid itself is
  untouched, per this plan's own scope note.

  **Reproduction against the accepted coastal-hills render is close but not exact, and is reported
  rather than tuned to match** (per the task's own instruction): 299 ridge / 289 valley lines,
  longest ridge 7.18 km / longest valley 7.70 km, against the accepted 312 / 273 and 8.3 km / 6.5 km.
  One real discrepancy was found and fixed during reproduction — the plan cited `min_cells=3` from
  the *naive* spike's own default; the actual reference implementation
  (`tools/spike_junction_walk.py`) defaults to `4`, and using `4` closed most of the gap (`3` gives
  448/418). The residual ~4-6% gap is unexplained (thinning was checked bit-for-bit against the
  reference pixel loop and matches exactly), most likely environment/data drift between this
  session's `data/raw/dem/syria-full` and whatever the original interactive spike session held, not
  a mechanism defect — the render (`data/renders/coastal-hills-geomorphons.png`) still shows the
  qualitative result the user accepted: continuous multi-kilometre crests through junctions, not
  fragmented stubs. See `plans/landform-geomorphons/implementation.md` for the full numbers.

  **One real plan-vs-reference-implementation discrepancy, now documented in `terrain/skeleton.py`
  itself**: the plan's design decision 5 described the junction-walk as "pair up incident branches
  by direction, greedy by smallest angular deviation" — an idealised description written before the
  actual reference code was located. What the ported code actually does is order-dependent: every
  degree-!=-2 node (endpoint *and* junction alike) walks into its own unused neighbours, and a
  junction's edges go to whichever walk reaches them first. On a real, dense skeleton a long
  approach chain usually wins that race (hence the multi-kilometre crests); on an **isolated**
  synthetic junction with no approach chain, it does not, and the junction splits into N stubs
  instead. Verified with synthetic fixtures (straight line, spur, 4-arm X) in `tests/test_skeleton.py`.

  **One discovered gap outside this plan's own scope, also handled rather than left broken**: M8's
  `build.pipeline.add_probe_chunk` called the now-deleted `ingest_terrain_chunk` for chunk-scoped
  ridge/valley extraction. Geomorphons' processing unit is a whole SRTM tile with a multi-kilometre
  margin, not a 5 km probe chunk, and this plan did not design a chunk-scoped equivalent. Chunk-scoped
  terrain extraction is removed from `add_probe_chunk` (grid/surface-type chunk ingestion is
  unaffected); `ProbeChunkReport.terrain_stats`/`terrain_skipped` are kept for shape compatibility
  but always come back `None`/`True` now. The old mechanism's own docstring already called the
  chunk-scoped case a degenerate, non-crashing one, so this is a narrowing of real behaviour, not a
  regression.

  **Known, unfixed gap: a region-scoped build does not clip terrain output to the region's own
  bbox.** `ingest_terrain`'s processing unit is one SRTM tile, independent of which region a
  caller is building (plan design decision 2) — `region` identifies the cache (name + bbox) but
  is never used to clip the extracted ridge/valley lines. A region-scoped build (e.g.
  `latakia-20km`, this project's standard small-region dev/test loop) therefore stores *every*
  ridge/valley line a covering SRTM tile produces across its whole ~1°×1° (~100×90 km at Syria's
  latitude) extent, not just the region's own (typically ~20-40 km) bbox. This does not affect the
  full-theatre build above — every tile is in-theatre there, so there is nothing to clip — but it
  will produce a geographically oversized `ridge`/`valley` set on the next region-scoped rebuild.
  Left unaddressed per the plan's own silence on region-bbox clipping (`implementation.md` has the
  fuller account); treat any `latakia-20km` (or other region-scoped) terrain rebuild as storing
  out-of-region geometry until this is fixed.

  **Not yet checked by this implementation pass**: Stage D's own two-adjacent-tile seam test (no
  tile boundary was exercised against real SRTM data beyond the single-tile reproduction above) and
  Stage E's kill-mid-build resume test against a real interrupted process (the cache's resumability
  was verified via direct unit tests in `tests/test_ingest_terrain.py`/`test_terrain_cache.py`, not
  a literal process-kill). **Stage G (the full-theatre build) is the user's own run, per the
  project's standing execution boundary** — not run here. Run command (mirrors the existing
  `RUN.md`/`tools/build_world_model.py` pattern, `--srtm-dir` already wired to the new stage; add
  `--osm-pbf` to also pick up `WM-B1`'s Latin-name preference on the same rebuild, which is the
  combined invocation the DoD acceptance card uses):

  ```sh
  world-model/.venv/bin/python world-model/tools/build_world_model.py syria-full \
      --towns <path/to/towns.lua> --beacons <path/to/beacons.lua> \
      --routes <path/to/Syria.routes> --srtm-dir <path/to/hgt_tiles/> \
      --osm-pbf <path/to/syria-theatre.osm.pbf>
  ```

  Full card with expected figures per block: `docs/acceptance/2026-10-02-geomorphons-latin-names-
  rebuild.md` / https://claude.ai/artifact/DKf9eTTWKmJtAKmKF96FdW.

  **Two real defects found and fixed against the user's own build (`fix/landform-relief-gate`,
  `plans/landform-relief-gate/implementation.md`), both checked directly against the real
  `syria-full.sqlite` (8.1 GB, read-only, not modified)**:

  - **No relief gate.** 89%/92% of ridges/valleys stored under 50 m of relief (measured: `>=50 m`
    keeps 234,799 of 1,440,397, exact match on a direct SQL query), and the Bekaa floor read as a
    valley — the exact case the user's own criteria (`plans/terrain-feature-probing/
    explore-notes.md`, "maskable-behind: sharp and/or high", ~50-150 m) rule out.
    `terrain.features.filter_by_relief` (default `min_relief_m=50.0`, the floor of that band) now
    drops any line below threshold before it reaches the cache or store.
  - **~16x-denser-than-DEM-justifies stored geometry** (one point per 5.6 m on a 90 m DEM; `feature`
    was 7.98 GB of the 8.1 GB store). `terrain.features._decimate_for_storage` (Douglas-Peucker,
    reusing the existing `geometry.simplify_polyline`) now decimates the smoothed line back toward
    DEM resolution, with its own deviation check against the real sampled points (never exceeding
    the pre-existing half-cell cap) — measured **36.7x point-count reduction** on a real
    region-scoped rebuild, worst real deviation **32.3 m** against a 45 m cap.

  A real correctness bug was found and fixed *during* verification of the second fix (not a named
  defect, but worth recording): an early version of the decimation deviation check compared each
  original point against only the one decimated segment a windowing shortcut assigned it to, which
  **overstated** real deviation by up to 5x on real traced lines near a genuine turn (it measured
  70-155 m where the true distance to the decimated line was 15-30 m) — so it was *safe*, never
  admitting a decimation it should have rejected, and useless, rejecting almost every one it should
  have accepted. Caught because the real built output's density barely dropped when it should have
  dropped ~37x, not because the check itself ever failed. Fixed to check against the whole decimated
  polyline; see the implementation doc for the full account.

  Both falsifiable checks hold on real renders (`data/renders/{coastal-hills,baalbek,palmyra}-
  relief-gate.png`): **the Bekaa floor is clean of ridge/valley lines**, and **Palmyra's isolated
  ridge chains survive** (a continuous ~6+ km chain visible through flat desert). Theatre-wide
  feature count after the gate is a direct measurement (234,799), not an extrapolation; expected
  new store size is extrapolated from the measured decimation ratio to **~2.4-2.5 GB** (down from
  8.1 GB) — not measured, since no full-theatre build was run here, per the project's execution-
  boundary rule. The terrain cache is fully invalidated by this change (new `min_relief_m`/
  `decimation_tolerance_fraction` knobs plus an `EXTRACTOR_VERSION` bump), so the user's next
  `syria-full` rebuild reprocesses every tile rather than serving stale, ungated geometry.

  **DoD-passed 2026-10-04 (`fix/landform-relief-gate`), Reviewer and Security both APPROVED with
  no required fixes, and acceptance cleared on the user's 2026-10-04 23:59 `syria-full` rebuild
  (verified 2026-10-05) — see "Live acceptance debt" above for the measured blocks.
  The one prediction that missed: the store came out **720 MB**, not the extrapolated 2.4-2.5 GB,
  with geometry density and relief distribution both healthy — the sample-derived byte-reduction
  figure undershot what the gate and the decimation do together at theatre scale.
  Card: `docs/acceptance/2026-10-04-landform-relief-gate-rebuild.md` /
  https://claude.ai/artifact/S6sod3ZdB1mCWSYj8twCPP.** No Performance Reviewer pass — this change
  strictly reduces work in a stage whose cost was already measured (drops lines before storage,
  decimates what remains), and Security's deep analysis agreed with that framing while checking
  the degenerate decimation cases directly (2000-collinear-point and adversarial-zigzag inputs);
  see `plans/landform-relief-gate/security-review.md`.

  **Milestone-completion check**: this closes the last known defect in `feature(kind='ridge'/
  'valley')` that blocked treating it as a layer to build on — Stages 3-5 (adjacency, bearing, the
  callout) can now assume gated, DEM-scale-appropriate geometry once they're picked up, rather
  than inheriting the two defects this fix removed. It does **not** change what the next milestone
  should be (Stages 3-5 are still unbuilt and still gated behind a real consumer need, per the
  reopening condition above) — but it does narrow what "trustworthy" means for anyone reading an
  older terrain render: see the `inspect_terrain.py` rewrite note below and the corresponding
  `NOTES.md` entry — every render judged by eye before this branch (including the ones that
  produced the 2026-10-01 "choose geomorphons" decision and the 2026-10-02 acceptance renders) was
  of raw/Chaikin-only geometry, not what the store actually holds. That does not reopen the
  geomorphons-vs-alternatives choice itself (made on a different, zoomed-in test window where the
  gate/decimation gap is proportionally small), but any density or clutter impression taken from
  those earlier renders should not be trusted for what ships.

  **Stages 3-5 built, Revision 3, 2026-10-05 (`plans/terrain-feature-probing/plan.md`).** The
  "a consumer that actually needs landform references" reopening condition fired: the contact-report
  callout is that consumer. Revision 3 replaces the void basin-adjacency design (there are no
  basins; Option C was abandoned before shipping) with a query-time divide counter —
  `query/divides.py`'s `divides_between(conn, theatre, observer, target)` counts distinct ridge
  crossings on the straight observer->target segment, deduplicated within `DIVIDE_MERGE_M` (400 m)
  — plus `store/reader.py`'s `closest_point_on_feature` (the companion to `_distance_to_feature`)
  feeding a new `bearing_deg: float | None` on `RoadInfo`/`SettlementInfo`/`WaterInfo`/
  `TerrainLineInfo` in `query/describe.py`. This closes `body-layer/BACKLOG.md`'s `BL-B14`
  world-model-support bullet (unblocked, not done — the body-layer wording items it names are
  separate). Real-store read-only check against `syria-full.sqlite` at Baalbek
  (x=-114453.8, z=25280.8): segments east toward the Anti-Lebanon flank read 1 divide at 8 km (and
  keep climbing with range — 2 at 12 km, 3 at 16 km — as the straight segment crosses successively
  more of the range's ridge lines); segments west/southwest, roughly along the Bekaa valley's own
  axis, stay at 0 divides out to 16-20 km. Matches the plan's own predicted check
  ("a segment across a flank should read 1, along the floor 0"). Body-layer's half (the dominance
  rule retuning `NEAR_FACT_RADIUS_M`, and the speech-priority wiring) is `plans/
  terrain-feature-probing/implementation-rev3.md`'s to describe; not duplicated here.

  **DoD mechanical checks passed, 2026-10-05, `feature/terrain-callout-stages-345` — not yet
  merged.** World-model: 548 passed / 3 skipped; body-layer: 1434 passed / 4 xfailed. Reviewer
  (round 2), Security deep analysis and Performance (MONITOR) all APPROVED. Live acceptance of
  the terrain qualifier itself (does "next valley"/"beyond the ridge" fire where the pilot would
  say it, does it ever displace something more useful) is outstanding and rides along with the
  already-pending `fix/contact-report-flood` / `fix/redundant-group-disclosure` sortie rather
  than needing its own flight — see `body-layer/ROADMAP.md`'s "Live acceptance debt" list.

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
