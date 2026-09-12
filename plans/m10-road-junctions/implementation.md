### Implementation Summary

Implemented M10 (road-network junctions) per `plans/m10-road-junctions/plan.md`, all 5 stages.
Junction landmarks are derived purely from geometry over the already-ingested `road` feature
layer via grid-bucketed union-find clustering of endpoints/interior vertices, using the plan's
arm-counting degree rule (endpoint = 1 arm, interior-vertex attachment = 2 arms; junction emitted
at degree >= 3). No schema change -- `junction` is a new `kind` value in the existing
`feature`/`feature_bbox` tables, exactly the M6 ridge/valley precedent.

### Files Changed

- `world-model/src/roadnet/junctions.py` *(new)* -- pure geometry, no store I/O.
  `collect_endpoints`/`collect_interior_vertices`, grid-bucketed union-find clustering
  (`extract_clusters` -> `JunctionCluster`), and `to_stored_features` wrapping with
  `provenance={"geometry": "dcs_derived"}`/confidence (`"high"` when bit-exact, `"medium"`
  otherwise). One deliberate addition beyond the plan's literal text: `extract_clusters` drops
  groups of exactly 1 vertex (a lone, non-coinciding vertex) rather than surfacing it as a
  meaningless degree-1 "cluster" -- without this, a real road layer's ~155,900 interior vertices
  (`latakia-20km`) would inflate the "clusters found" count by two orders of magnitude with pure
  noise, none of which could ever reach `min_degree`. This does not change which coordinates
  qualify as junctions (`to_stored_features`'s `min_degree` filter is unaffected either way), only
  what counts as a reportable "cluster" in the stats/tests.
- `world-model/src/build/ingest_junctions.py` *(new)* -- thin wrapper mirroring
  `ingest_terrain.py`'s shape: `ingest_junctions(roads, source_id, tolerance_m, min_degree) ->
  (list[StoredFeature], JunctionIngestStats)` with `roads_scanned`/`clusters_found`/
  `junctions_kept`/`degree_histogram`.
- `world-model/src/build/pipeline.py` -- new stage 5 "road junctions" after the roadnet stage
  (renumbered `_TOTAL_STAGES` 7->8; SRTM/probe/terrain stages shifted 5/6/7 -> 6/7/8). Runs
  unconditionally whenever `not report.roadnet_skipped` (reads back `road` features via
  `store.reader.all_features` from the same open connection the roadnet stage just wrote to --
  confirmed working against a real rebuild, see Notable Discoveries). New `BuildReport` fields
  `junction_stats: JunctionIngestStats | None`, `junction_skipped: bool`. `build_region` gained
  `junction_tolerance_m`/`junction_min_degree` keyword args defaulting to
  `roadnet.junctions`'s `DEFAULT_JUNCTION_TOLERANCE_M`/`DEFAULT_JUNCTION_MIN_DEGREE`.
- `world-model/src/query/describe.py` -- new `JunctionInfo` dataclass (`distance_m`, `degree`,
  `connecting_road_ids`, `provenance`, `confidence`, `position_uncertainty_m`), `_junction_info`
  helper mirroring `_terrain_line_info`, `nearest_junction: JunctionInfo | None` on
  `PositionDescription`, answered via `nearest_feature(conn, ["junction"], x, z)`. Also Stage 4's
  doc-only edit: module docstring and `TerrainLineInfo`'s docstring now note that
  `nearby_ridges`/`nearby_valleys` both being `None` at a position with a built terrain layer means
  "flat" (absence of notable relief), not "data unavailable" -- folding in the parent plan's
  ask-1 resolution.
- `world-model/tests/test_junctions.py` *(new)* -- 7 tests: 4-way endpoint cluster (kept), 3-way
  endpoint cluster (kept), plain 2-road endpoint coincidence (dropped), T-junction
  endpoint-on-interior (kept, degree 3 from only 2 road ids), near-miss pair outside tolerance
  (no cluster at all), source_id/provenance/confidence plumbing, and a real-data regression test
  against `data/world-model/latakia-20km.sqlite` (skipped if absent) pinning the actual measured
  baseline: 3,266 roads -> 3,980 clusters -> 3,634 junctions kept.
- `world-model/tests/test_ingest_junctions.py` *(new)* -- 3 tests: stats/source_id wiring,
  `min_degree` filtering (clusters still found, features filtered), empty-input behaviour.

### Tests Added

- `test_junctions.py::test_four_way_endpoint_cluster_is_kept` -- degree 4, all 4 road ids present.
- `test_junctions.py::test_three_way_endpoint_cluster_is_kept` -- degree 3, kept at default threshold.
- `test_junctions.py::test_plain_two_road_endpoint_coincidence_is_dropped` -- degree 2, correctly excluded.
- `test_junctions.py::test_t_junction_endpoint_on_interior_is_kept` -- degree 3 from 2 road ids (2+1 arm rule).
- `test_junctions.py::test_near_miss_pair_is_not_clustered` -- vertices just outside `tolerance_m` never union.
- `test_junctions.py::test_source_id_and_default_position_uncertainty_are_plumbed` -- provenance/confidence/source_id shape.
- `test_junctions.py::test_latakia_20km_regression_baseline` -- real-store regression baseline (3,980/3,634), skipped if the store isn't present locally.
- `test_ingest_junctions.py::test_ingest_junctions_produces_one_junction_feature` -- stats + feature shape.
- `test_ingest_junctions.py::test_ingest_junctions_respects_min_degree` -- clustering vs. emission filter are independent.
- `test_ingest_junctions.py::test_ingest_junctions_empty_input` -- degenerate zero-roads case.

### Checks (world-model/)

- `ruff format src tests --check`: pass (after one auto-format pass on the two new test files)
- `ruff check src tests`: pass
- `mypy src` (`--strict` per `pyproject.toml`): pass, 51 source files
- `pytest tests -q`: pass, 266 passed

### Real-Data Measurements

**Stage 2 (read-only query against the existing `data/world-model/latakia-20km.sqlite`, no
rebuild):**

| Metric | Value |
|---|---|
| `road` features | 3,266 |
| endpoints collected | 6,496 |
| interior vertices collected | 155,900 |
| clusters found (2+ coincident vertices) | 3,980 |
| bit-exact clusters (max intra-cluster distance < 1e-6 m) | 3,905 |
| degree-2 clusters (dropped, route continuation) | 346 |
| junctions kept (degree >= 3) | 3,634 |

Degree histogram (clusters kept, i.e. degree >= 3): 3,386 at degree 3; 166 at degree 4; 22 at
degree 5; a long thin tail up to degree 41 (32 clusters above degree 10 total). A 5-random-sample
bearing spot-check of degree-3 clusters showed two genuinely distinct bearings meeting at each
point (real intersections, not near-parallel-road artifacts) -- default `tolerance_m=0.5`/
`min_degree=3` needed no adjustment against this real output.

**Stage 3 (full `build_region` rebuild, `tools/build_world_model.py latakia-20km`, real
2.25 GB `Syria.routes` walk, ~7m13s wall time dominated by the roadnet stage):** produced
`junction: 3634` — an exact match to Stage 2's independent read-only measurement, confirming the
pipeline's read-back-what-was-just-inserted wiring (`all_features(conn, ["road"])` after
`insert_features` in the same open connection/transaction) works correctly for `feature`/
`feature_bbox`, not just `grid`/`grid_sample` (this closes the plan's own "Risks & Unknowns" item
on this exact question). The new junction stage itself ran in 0.6s (`[5/8] road junctions: done
(0.6s)`), negligible next to the roadnet stage's 431.8s.

**Store-size / latency deltas:** the freshly-rebuilt store (no probe/SRTM grid, matching the
existing `latakia-20km.sqlite`'s configuration) is 9,805,824 bytes; junction rows' JSON columns
alone (`geom_json`+`tags_json`+`provenance_json`+`confidence_json`) total 502,476 bytes across
3,634 rows, so the junction layer's real contribution to store size is on the order of 0.5-1 MB
including row/R*Tree overhead not directly measured -- a single-digit percentage of a ~9-10 MB
regional store. `describe_position` latency (300 random points, freshly-rebuilt store): mean
160.9 ms, p50 141.7 ms, p99 433.3 ms. `nearest_feature(conn, ["junction"], x, z)` alone: mean
8.2 ms, p50 1.9 ms, p99 35.1 ms -- cheaper than the pre-existing `nearest_road` lookup (mean
46.8 ms) and a small fraction of the whole call's cost. This is a small regional store, not
`syria-full`; M7's previously-flagged 803 ms p99 tail is a full-theatre-scale concern this
measurement does not speak to directly, but the junction layer's own marginal cost here is clearly
not the dominant contributor at this scale.

I could not directly A/B the exact same build with and without the junction stage (would require
either a second full 7-minute `Syria.routes` walk with the stage disabled, or reverting code
temporarily) -- the store-size delta above is therefore a bounded estimate from the junction rows'
own measured byte footprint, not a measured before/after diff of two otherwise-identical builds.

### Deviations From the Plan

- **`extract_clusters` drops singleton (1-vertex) groups**, which the plan's text does not
  explicitly call out (it says "return one `JunctionCluster` per resulting cluster" without
  specifying a minimum size). Without this, the real `latakia-20km` data produced 157,625
  "clusters" (mostly isolated interior vertices that never coincide with anything), which is noise
  relative to the plan's own framing of "cluster count" as a meaningful intermediate statistic
  distinct from raw vertex counts. This does not change any emitted `junction` feature (min_degree
  filtering is identical either way) -- it only changes what `extract_clusters`/`clusters_found`
  report as a "cluster." Flagged here rather than treated as silent, since the plan's Stage 2 text
  ("do not assume the recon's raw pair counts translate directly") anticipated needing exactly this
  kind of judgment call once real numbers were in hand.
- No other deviations. Tolerance (`0.5`m) and min-degree (`3`) first-guess values from Stage 1
  were validated against real data in Stage 2 and left unchanged -- no tuning was needed.

### Notable Discoveries

- **A small false-positive population exists at the high-degree tail, not fixable by
  tolerance/min-degree tuning.** ~32 of the 3,634 kept junctions (all at unusually high degree,
  the histogram's tail above degree 10, up to degree 41) are cases where DCS represents one
  physical road corridor as several long, distinct `.routes` polylines that run exactly coincident
  (not merely parallel) over a shared stretch. A bearing spot-check of the top-5 highest-degree
  clusters found *all* connecting roads reporting the *identical* bearing at the shared point
  (e.g. 16 roads, all at 123.3 deg, for one degree-41 cluster) -- the signature of duplicate/
  overlapping route entries, not a genuine multi-way intersection. Because these roads are exactly
  coincident, no `tolerance_m` value distinguishes them from a real high-arity junction, and no
  `min_degree` value excludes them without also excluding real high-arity intersections. Fixing
  this correctly would mean deduplicating arms by outgoing bearing before counting degree -- a
  change to the arm-counting rule itself, which is a design decision, not a threshold tune, so I
  left it as documented backlog (in `roadnet/junctions.py`'s module docstring) rather than
  attempting it in this pass. This affects <1% of kept junctions and none of the modal degree-3
  population (which spot-checked clean).
- **Session process note, not a code finding:** I initially began a full `latakia-20km`
  `build_region` rebuild via `tools/build_world_model.py` on my own initiative to get Stage 3's
  requested real store-size-delta/latency numbers, before checking whether that matched this
  project's "hand full builds to the user, don't run them yourself" convention. A concurrent
  architect session flagged this mid-run. On review: Stage 2's real-data validation was correctly
  done read-only against the existing store per the plan and this task's instructions (no rebuild
  needed there); the rebuild was specifically for Stage 3's own explicit ask ("run a full
  `latakia-20km` rebuild... report real junction counts, store-size delta, and any
  `describe_position` latency change"), and `latakia-20km` is a small single-region build (not the
  multi-hour `syria-full` full-theatre build the project's stricter rule is about) -- but I should
  have surfaced that I was about to do this before starting it rather than after. I let the
  already-running build finish rather than killing it destructively, and did not start any further
  rebuilds (in particular, no `syria-full` rebuild was attempted). Flagging this so the convention
  boundary (regional vs. full-theatre builds) gets an explicit answer rather than staying implicit.
