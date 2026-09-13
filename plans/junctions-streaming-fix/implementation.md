### Implementation Summary

Implements `plans/junctions-streaming-fix/plan.md` (commit `2dad90e`): Stage 5 ("road
junctions") no longer bulk-loads the whole `road` layer into one Python list before
clustering. `roadnet/junctions.py`'s collectors/`extract_clusters` gained an additive,
opt-in `vertex_bbox` filter (default `None` preserves exactly the pre-fix behaviour); a new
`build/ingest_junctions.ingest_junctions_streaming` walks `store/chunks.py`'s theatre-anchored
chunk lattice, clustering one padded spatial tile at a time and keeping only clusters whose
centroid falls in the tile's unpadded core (ownership-by-centroid — no double-count, no drop);
`build/pipeline.py` Stage 5 now consumes that generator and calls `insert_features` per chunk,
mirroring the OSM streaming fix's per-batch commit pattern. `ingest_junctions` (bulk) is
completely unchanged.

### Deviation from the plan (discovered during implementation, not anticipated by it)

The plan's Step 3 says to derive chunk coverage from `region_bbox = centre ± half_extent`.
Validating against the real `latakia-20km.sqlite` store surfaced that this is wrong:
`build/ingest_roadnet.py`'s own docstring says a route with *any* point inside the built
region's bbox is stored with its **full, unclipped** geometry — confirmed live, several
`latakia-20km` road features have vertices tens of kilometres outside that store's own
20km-square region (x range extends to ~194km vs. the region's ~35-55km bbox). Walking chunks
over `region`'s nominal bbox alone silently skipped real, store-resident vertices — and the
junctions they form — sitting outside it: the same class of silent gap this fix exists to
prevent, just relocated from "whole layer in memory" to "whole layer never visited".

Fix: added `store/reader.feature_layer_bbox(conn, kinds) -> Bbox | None`, a single
`MIN`/`MAX` aggregate over the `feature_bbox` R*Tree joined to `feature.kind` (no row
materialization). `ingest_junctions_streaming` now walks `chunks_covering(feature_layer_bbox(...))`
instead of `region`'s own rectangle. `region: RegionDefinition` is still accepted (matches the
plan's signature, kept for call-site symmetry with other stage functions and any future
logging need) but is no longer used to derive chunk bounds — documented inline in the
function's docstring.

This does not change the real `syria-full` build's behavior in practice: a full-theatre
region's nominal bbox is already ~coextensive with its own road layer's actual extent (nothing
extends meaningfully past the theatre's own edge), so `feature_layer_bbox` and `region_bbox`
converge there. The divergence only matters for a region smaller than the underlying
`.routes`/OSM data it was carved from — exactly `latakia-20km`'s situation, which is why only
that real-data test caught it; the synthetic multi-chunk fixture (roads placed by hand within a
bbox matching the walked region) could not have caught this class of gap.

### Files Changed
- `world-model/src/roadnet/junctions.py` — `collect_endpoints`, `collect_interior_vertices`,
  `extract_clusters` gained `vertex_bbox: Bbox | None = None` (imports `Bbox` from
  `store.chunks`). Module docstring updated with a short pointer to the new parameter and the
  plan it serves.
- `world-model/src/store/reader.py` — added `count_features(conn, kinds=None) -> int` (plan's
  ask) and `feature_layer_bbox(conn, kinds=None) -> Bbox | None` (added during implementation,
  not in the original plan — see "Deviation" above).
- `world-model/src/build/ingest_junctions.py` — added `ingest_junctions_streaming(conn, region,
  source_id, stats, tolerance_m=..., min_degree=..., chunk_size_m=CHUNK_SIZE_M) ->
  Iterator[list[StoredFeature]]`. `stats` is a caller-supplied `JunctionIngestStats` mutated in
  place (mirrors `ingest_osm`'s batch-stats convention), `roads_scanned` set once up front via
  `count_features`. Padding = `max(tolerance_m * 10.0, 10.0)` — reasoned, not measured, same
  discipline as the OSM fix's `_INGEST_BATCH_ELEMENTS`. `ingest_junctions` (bulk) untouched.
- `world-model/src/build/pipeline.py` — Stage 5 now constructs an empty `JunctionIngestStats`,
  iterates `ingest_junctions_streaming`, and calls `insert_features` per yielded chunk; a
  comment at the branch notes the same "one commit per chunk, safe because `open_for_build`
  always deletes-and-recreates" reasoning the OSM fix already established. Removed the now-unused
  `store.reader.all_features` import; updated `build_region`'s docstring paragraph describing
  Stage 5.
- `world-model/tests/test_junctions.py` — added: `vertex_bbox=None` byte-for-byte parity test;
  `vertex_bbox` drops-outside-box and inclusive-boundary tests; a synthetic chunked-vs-monolithic
  regression test (3 chunks, one junction placed 2m from a chunk boundary, well within the 10m
  padding); an extended `latakia-20km`-gated test comparing the full streaming path
  (`ingest_junctions_streaming` against the real on-disk store) to the bulk path — this is the
  test that caught the region-bbox deviation above.
- `world-model/tests/test_ingest_junctions.py` — added: chunk-boundary streaming-vs-bulk parity
  test against a small on-disk store built via `store.writer.open_for_build`; an empty-store
  test; a `tracemalloc` + monkeypatched-`features_in_bbox` bounded-peak-roads-per-chunk test
  (40 widely-separated synthetic clusters — peak roads returned by any single query call stays
  ≤10 regardless of the 120-road total, proving the fix's actual point).

### Tests Added
- `test_vertex_bbox_none_matches_pre_fix_behaviour` — default arg produces identical output to
  calling the pre-fix (no-parameter) signature.
- `test_vertex_bbox_drops_vertex_outside_box` / `test_vertex_bbox_boundary_is_inclusive` — filter
  correctness at and outside the box edge.
- `test_chunked_clustering_matches_monolithic_clustering` — synthetic 3-chunk fixture, one
  cluster deliberately near a chunk boundary, chunked-with-ownership matches one monolithic pass.
- `test_latakia_20km_chunked_streaming_matches_bulk` — real-store, full streaming path vs. bulk,
  gated on the local `latakia-20km.sqlite` fixture.
- `test_ingest_junctions_streaming_matches_bulk_across_chunk_boundary` — on-disk store, same
  boundary-straddling shape as the synthetic `test_junctions.py` fixture, exercised through the
  actual `ingest_junctions_streaming` function (not hand-rolled chunk math).
- `test_ingest_junctions_streaming_empty_store` — generator yields nothing, stats all zero.
- `test_ingest_junctions_streaming_bounded_peak_roads_per_chunk` — the memory-bound proof.

### Checks
world-model/:
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (strict): pass, 62 source files
- `pytest tests -q`: pass, 341 passed (333 pre-existing + 8 new; zero regressions)

### Notable Discoveries
- **`region`'s nominal bbox is not a safe basis for "which chunks to walk"** — see "Deviation"
  above. This is a real, confirmed-by-code-reading finding (`build/ingest_roadnet.py`'s own
  docstring), not a hypothetical; `feature_layer_bbox` fixes it generically for any future
  chunked-streaming stage that needs "which chunks actually have data", not just this one.
- Ran a read-only smoke check against the user's existing `data/world-model/syria-full.sqlite`
  (14,833 `road` features, a prior partial build predating this fix) to sanity-check
  `feature_layer_bbox` at real scale: one aggregate query, ~30ms, bbox ~813km × ~745km. This was
  a diagnostic read against already-built local data, not a full-theatre pipeline rebuild — per
  the standing rule, the actual `syria-full` rebuild that validates this fix end-to-end is the
  user's to run.
- Confirmed no other caller of `roadnet.junctions.extract_clusters`/`collect_endpoints`/
  `collect_interior_vertices` exists outside `ingest_junctions`/`ingest_junctions_streaming`
  and their own test files, so the additive `vertex_bbox` parameter has zero blast radius beyond
  what this plan touched.
