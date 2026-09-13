### Implementation Summary

All 9 stages (0-8) of `plans/osm-landcover-optimization/plan.md` implemented in order on
`feature/osm-landcover-optimization`, one commit per stage, all local/reversible per the plan's
own framing (a store rebuild plus the `CLASSIFIER_VERSION` bump undoes everything). No
`syria-full` build was run; `world-model/data/` was never touched. Real small-extract validation
(Stage 6) used the installed DCS World's Syria terrain files (read-only) plus the real,
already-clipped `/mnt/f/dcs-world-model/syria/raw/osm/*-clipped.osm.pbf` country extracts, all
output written to a session scratch directory.

Commits (all on `feature/osm-landcover-optimization`):
- `b89b239` Stage 0 — OSM tags-filter and RUN.md pre-filter step
- `97a8f2a` Stage 1 — OSM area assembly (OsmRing/OsmArea)
- `4980e26` Stage 2 — geometry primitives (simplify, area, containment, coastline side)
- `37afad8` Stage 3 — classifier rewrite (D2 rules, D3 ring pipeline)
- `cd20002` Stage 4 — wire areas into the pipeline and cache
- `80a5f50` Stage 5 — query contract (Design D6)
- `e89f708` Stage 6 — real small-extract validation
- `493242c` Stage 7 — body-layer semantic facts (Design D7)
- `da047b4` Stage 8 — docs and bookkeeping

### Files Changed

**Stage 0** (`b89b239`)
- `world-model/tools/osm_tags_filter.txt` *(new)* — the committed `osmium tags-filter -e`
  expression file, exactly as specified in Design D1.
- `world-model/RUN.md` — §2.3 now merges to `syria-theatre-unfiltered.osm.pbf`; new §2.4 runs the
  filter; old §2.4 "Check it" renumbered §2.5.
- `world-model/tests/test_osm_tags_filter.py` *(new)* — drift guard; Stage 0's version used a
  hard-coded table of D2's *planned* rules (rewired to import the classifier's own constants in
  Stage 3).

**Stage 1** (`97a8f2a`)
- `world-model/src/osm/features.py` — `OsmRing`/`OsmArea` dataclasses; `OsmFeatureSet.areas`;
  Overpass `load_features` mirrors every closed tagged way into a single-ring `OsmArea`
  (multipolygon relations stay a counted `relations_skipped` skip on that path — Overpass has no
  relation geometry to assemble from).
- `world-model/src/osm/pbf.py` — `area()` callback (defining it makes `apply_file` run libosmium's
  two-pass multipolygon manager); `osmium.filter.KeyFilter(landuse, natural, place, waterway,
  water)`; `relation()` splits into `multipolygon_relations_seen` (type=multipolygon/boundary) vs.
  `relations_skipped` (anything else); `stream_features`/`load_features` gain `on_areas` and
  return `StreamFeaturesResult` (named fields, replacing the old 2-tuple).
- `world-model/src/build/pipeline.py` — updated to the new `stream_features` signature with a
  placeholder `_flush_areas` (real wiring is Stage 4).
- `world-model/tests/test_osm_pbf.py`, `test_osm_features.py`, `test_pipeline_osm_cache.py` —
  rewritten/extended fixtures (the new `KeyFilter` drops `highway`-tagged elements entirely, so
  fixtures using `highway=*` had to move to `waterway=`/`landuse=` tags).

**Stage 2** (`4980e26`)
- `world-model/src/geometry/__init__.py` — `simplify_polyline`/`simplify_ring` (iterative
  Douglas-Peucker), `ring_area_m2` (shoelace), `polygon_contains` (ring-with-holes), `signed_side_of_polyline`
  (sign at the closest segment, angle-weighted pseudo-normal — sum of unit normals — at a shared
  vertex).
- `world-model/tests/test_geometry.py` — new tests, including Design D5's real-geography coastline
  control-point test through `coordinates.wgs84_to_dcs`.

**Stage 3** (`37afad8`)
- `world-model/src/build/ingest_osm.py` — full rewrite: `_classify_node`/`_classify_line`/
  `_classify_area` (three pure functions), `_ingest_ring` (the D3 per-ring pipeline: region-clip,
  independent min-area filter for outer ring and every hole, unsimplified `area_m2`, simplify,
  degenerate-after-simplify drop), `_ingest_area` (dispatches an `OsmArea`'s rings, skips
  coastline/dam areas silently), `ingest_osm_areas_batch`. `CLASSIFIER_VERSION` 1 → 2.
  `OsmIngestStats` redesigned (per-kind/per-class counts, every drop reason independently
  counted, vertex totals before/after simplify).
- `world-model/tests/test_ingest_osm.py` — full rewrite, one test class per classify function plus
  `_ingest_ring`/`_ingest_area`/end-to-end aggregation tests.
- `world-model/tests/test_osm_tags_filter.py` — rewired to import the classifier's own vocabulary
  constants.
- `world-model/tests/test_osm_cache.py`, `world-model/tools/measure_osm_cache_perf.py` —
  `OsmIngestStats(roads=...)` → `OsmIngestStats(water_features=...)` (field rename fallout).

**Stage 4** (`cd20002`)
- `world-model/src/build/pipeline.py` — real `_flush_areas` (calls `ingest_osm_areas_batch`,
  mirrors `_flush_ways`); `multipolygon_relations_seen` threaded onto the running `OsmIngestStats`;
  road-junction stage docstring updated (OSM no longer contributes `road` rows).
- `world-model/tests/test_pipeline_osm_cache.py` — shared fixture extended to cover every new
  shape (area, hole, coastline, peak); new `classifier_version=1` rejection test.

**Stage 5** (`80a5f50`)
- `world-model/src/store/reader.py` — `containing_polygons`/`_distance_to_feature` honour
  `inner_rings`.
- `world-model/src/store/models.py` — documents the reserved derived tags.
- `world-model/src/query/describe.py` — `nearest_road_osm` removed; `SettlementInfo`/`WaterInfo`/
  `NamedPlaceInfo` gain `subtype`; new `CoastlineInfo`/`LandcoverInfo` + `nearest_coastline`/
  `inside_landcover` fields; `inside_settlement` now explicitly prefers named-then-smallest-area
  (`_preferred_settlement`, a real behavior fix, not just a field addition — previously took
  whatever `containing_polygons` returned first).
- `world-model/src/api/server.py` — docstring note only (`asdict` needs no code change).
- `world-model/tools/export_geojson.py` — emits `inner_rings` as GeoJSON polygon holes.
- `world-model/tools/analyze_m5_stage4_validation.py` — dropped the now-nonexistent
  `nearest_road_osm` field reference (this M5-era tool requires the real gitignored
  `latakia-20km.sqlite` to run at all, so it's not covered by any check command, but was left
  broken otherwise).
- `world-model/tests/test_store_reader.py`, `test_describe_position.py`, `test_query_search.py` —
  new hole-awareness, `inside_landcover`/`inside_settlement`/`nearest_coastline` tests, a
  `find_place_by_name` peak test.

**Stage 6** (`e89f708`)
- `world-model/tools/validate_osm_landcover.py` *(new)*.
- `world-model/research/2026-09-13-osm-landcover-optimization-validation.md` *(new)*.

**Stage 7** (`493242c`)
- `body-layer/src/belief/enrichment.py` — `semantic_facts_for`'s D7 changes.
- `body-layer/tests/test_enrichment.py`, `test_tools.py`, `test_console.py`, `test_speech.py`,
  `test_crew_console.py` — every `_FakeDescription` fixture across the suite needed the two new
  optional fields (`inside_landcover`/`nearest_coastline`, defaulting `None`) added, since
  `semantic_facts_for` now unconditionally reads both — see "Notable Discoveries".

**Stage 8** (`da047b4`)
- `world-model/RUN.md`, `world-model/CLAUDE.md`, `world-model/docs/M9_OSM_RUN_INSTRUCTIONS.md`,
  `body-layer/CLAUDE.md` — docs only, no code.

### Tests Added

Summarized per stage above; roughly 140 new/rewritten tests across world-model
(`test_osm_tags_filter.py`, `test_osm_pbf.py`, `test_osm_features.py`, `test_geometry.py`,
`test_ingest_osm.py`, `test_pipeline_osm_cache.py`, `test_store_reader.py`,
`test_describe_position.py`, `test_query_search.py`) and body-layer (`test_enrichment.py`'s D7
section — 20 new tests — plus fixture-only edits in four other files). world-model's suite grew
from 341 to 465 passing tests over the branch; body-layer's from 488 to 506.

### Checks

**world-model/** (final state, all stages)
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (`--strict`): pass, 62 source files
- `pytest tests -q`: pass, 465 passed, 3 skipped (the 3 skips are real-data-gated tests requiring
  gitignored `data/raw/` files, unrelated to this branch)

**body-layer/** (Stage 7 checks, still green through Stage 8)
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (`--strict`, run from `body-layer/`): pass, 30 source files
- `pytest tests -q`: pass, 506 passed

No failures encountered in the final state of any check command; failures hit *during*
implementation (fixture mismatches, a real classifier bug caught by a test, etc.) were fixed
before moving to the next stage and are not reproduced here — see the per-stage commit messages
for what each one found and fixed.

### Notable Discoveries

- **`osmium.filter.KeyFilter` narrows what reaches Python callbacks, not just what gets
  classified.** Fixture-verified (Stage 1): an untagged closed way, or one tagged only outside the
  filter's key set (`highway`, `building`, `amenity`), never reaches `node()`/`way()`/`area()`/
  `relation()` at all once the filter is active — location resolution and multipolygon assembly
  still see every element, only the Python-visible callbacks are restricted. This meant several
  pre-existing test fixtures using `highway=*` tags (to exercise the *old* road classifier) had to
  move to tags inside the new filter's vocabulary before they could exercise anything at all,
  independent of the classifier rewrite itself (Stage 1, before Stage 3 touched the classifier).
- **libosmium strips a relation's own `type` tag from the assembled area's tags.** An
  area assembled from a `type=multipolygon, landuse=forest` relation reports `tags == {"landuse":
  "forest"}` — no `type` key at all. Caught a wrong test assertion in Stage 1's own test
  development; worth knowing for anyone reading `_classify_area` and wondering why it never checks
  for `type=multipolygon` itself.
- **A relation's own `type` tag gates area assembly, not just its member ways' tags.** A
  multipolygon-shaped fixture missing `"type": "multipolygon"` on the *relation* silently produces
  zero areas (libosmium's manager requires it) — caught during Stage 6 validation when a
  hand-written test fixture in `test_pipeline_osm_cache.py` initially omitted it and the forest
  polygon with a hole never appeared in the built store.
- **`latakia-20km`'s registered centre is not downtown Latakia.** Per `build.region.REGIONS`'s own
  docstring it's OSLK-ARP-based (near Jableh), ~18.5 km from real Latakia city's own OSM node —
  discovered while picking a "Latakia city centre" control-point coordinate for Stage 6, which
  required re-targeting that control point (see the research note and Stage 6's commit message).
- **`Area.rings` growing from 3 to 6 in real data changed a downstream mypy narrowing shape
  nowhere** — worth noting only as a non-event: the `OsmArea`/`OsmRing` dataclasses added in Stage
  1 needed no further changes through Stages 3-6 despite carrying real multi-ring/multi-hole data
  at theatre-clip scale (Lake Assad: 52,031 raw outer-ring vertices, 15 real kept holes in the
  Lake Assad validation region).
- **Every `_FakeDescription`-style duck-typed test fixture in body-layer needed the same two-field
  patch.** `semantic_facts_for` unconditionally reads `description.inside_landcover`/
  `nearest_coastline` now, so any test file with its own hand-rolled fake `PositionDescription`
  (five files, not just `test_enrichment.py`) hit `AttributeError` until patched — a recurrence of
  the "duck-typed fixture, real attribute access" pattern this project's `belief/enrichment.py`
  module docstring itself already calls out for `SettlementInfo`/`WaterInfo`/`TerrainLineInfo`.
