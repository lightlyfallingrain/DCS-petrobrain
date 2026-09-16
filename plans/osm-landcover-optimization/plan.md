# OSM ingest optimization and landcover split: plan

Status: proposed 2026-09-13 (architect). Branch `feature/osm-landcover-optimization`.

## Read first: mechanism substitutions and deviations from the brief

No open user questions block implementation. Every item below is a local, reversible decision
(a store rebuild plus the `CLASSIFIER_VERSION` bump undo it). Each is flagged here because it
builds something other than the literal wording of the brief:

1. **`built_up` is stored as kind `settlement`, not kind `landcover`.** The brief lists
   `built_up` as a landcover class. Each built-up polygon is stored once, as
   `kind="settlement", subtype="built_up"`, with the derived tag `landcover_class="built_up"`.
   `describe_position.inside_landcover` reads both kinds and reports all six classes.
   Rationale: no duplicate rows, `nearest_settlement` stays a single-kind R\*Tree query, and
   `store.reader` needs no subtype filter.
2. **Multipolygon holes are stored as a derived `inner_rings` entry in `tags_json`, not as a new
   geometry column.** A new column would change the DDL and bump `store.schema.SCHEMA_VERSION`.
   `probe_store.schema.check_probe_paired_with_base` compares that version, so any existing M8
   probe store would be orphaned, and probe data is not rebuildable. Precedent for derived
   structured values in `tags_json` already exists: junction `connecting_road_ids`, terrain
   `elevation_range_m`. "Store only needed tags" is honoured: no raw OSM tags are kept.
3. **A second, in-process filter is added (`osmium.filter.KeyFilter` in `apply_file`)** alongside
   the job (a) `osmium tags-filter` pre-filter. This is additive, not a replacement. Measured on
   the Syria clip, it makes an unfiltered file parse in 7 s instead of 50 s with identical output.
   The pre-filter's remaining job is shrinking the node-location index (see Context).
4. **Dams are `named_place` Points and are kept only when named** (`subtype="dam"`). Unnamed dams
   are counted and dropped. Syria clip: 29 named, 128 unnamed; Turkey clip: 158 named, 384
   unnamed. The reservoir behind a dam is kept as water regardless.
5. **Coastline is its own kind, `coastline`**, not `water`. Rivers and lakes stay under `water`,
   so `nearest_water` is not swallowed by the coast.
6. **`nearest_road_osm` is removed** from `PositionDescription` rather than left always-`None`
   (reasons in Design D6).
7. **Water synonyms beyond the brief's literal tag list are accepted**, because they are the same
   three categories under older tagging: `natural=water` with no `water=*` (generic, subtype
   `lake`), `landuse=reservoir` (subtype `reservoir`), `waterway=riverbank` (subtype `river_area`).
   All are subject to the 5 ha minimum. The Syria clip has 601 untyped `natural=water` areas
   (51 at 5 ha or more) and 496 `landuse=reservoir` areas (25 at 5 ha or more). Drop them by
   removing three lines if unwanted.

No investigator was invoked. Nothing here depends on DCS internals. The pyosmium and osmium-tool
behaviour below was verified directly against the installed versions (next section).

### Goal

Cut OSM parse time and data size by pre-filtering to the tags a Mi-24 crew's eye uses, then
re-classify OSM into DCS-subordinate layers: `settlement` (built-up and place areas), a new
`landcover` kind, river/lake water, a `coastline` line kind, and peaks/dams. Multipolygon
relations and their holes are assembled, and the new facts are exposed through
`describe_position` to body-layer and the Mission Interpreter.

### Context verified for this plan (2026-09-13)

Tool versions: pyosmium `osmium` 4.3.1 in `world-model/.venv` (Python 3.12.3); `osmium-tool`
1.16.0 / libosmium 2.20.0. Probe scripts and outputs live in the session scratchpad only; nothing
was written under `data/`.

- **Area assembly API (fixture-verified).** `SimpleHandler.apply_file(path, locations=True,
  idx="sparse_mem_array")` on a handler that defines `area()` runs libosmium's two-pass
  multipolygon manager automatically.
  - `area.from_way()` and `area.orig_id()` identify the source; `outer_rings()` and
    `inner_rings(outer)` yield node-ref lists with `.lat`/`.lon`.
  - A multipolygon relation with two untagged outer way pieces plus an inner ring assembled
    correctly into one outer ring with one hole.
  - **A closed tagged way is delivered to both `way()` and `area()`.** A closed
    `natural=coastline` way (an island) also arrives as an area.
  - Untagged closed member ways do not produce areas.
  - `apply_file(..., filters=[osmium.filter.KeyFilter(...)])` filters only the Python callbacks;
    locations and relation assembly still see every element (the Syria-clip counts were identical
    with and without it).
- **`osmium tags-filter` semantics (fixture-verified).** Referenced objects are added by default:
  a matched `type=multipolygon` relation brings its untagged member ways and their nodes. `a/`
  matches closed ways with 4+ nodes and `type=multipolygon|boundary` relations. Output order is
  preserved (the filtered file reports "Objects ordered (by type and id): yes").
- **Real-extract measurements** (expression file from Design D1):

  | extract | nodes | ways | relations | size | tags-filter | Python area pass (filtered) |
  |---|---|---|---|---|---|---|
  | syria-clipped | 11.41 M → 1.52 M | 1.72 M → 58 k | 2,550 → 462 | 72 → 10 MB | 3.8 s, 2.2 GB RSS | 6.5 s, 117 MB RSS |
  | turkey-clipped | 28.57 M → 8.38 M | 2.91 M → 168 k | 14,417 → 5,462 | 170 → 40 MB | 7.8 s, 2.3 GB RSS | 31 s, 467 MB RSS |

  - **Lake Assad** (`بحيرة الفرات`, reservoir, about 654 km²), Tishreen reservoir and Sabkhat
    al-Jabbul are relations. All are skipped today and assemble correctly now. Three of the four
    city `place` areas in the Syria clip are relations.
  - **Holes are material.** Turkey clip: 39,324 inner rings, 4,086 of them at 5 ha or more, and
    103 forest holes of 1 km² or more. Syria clip: 2,325 inner rings, 561 at 5 ha or more.
    Dropping holes would misreport clearings or villages inside forest relations at a scale
    comparable to the ~1.3 km DCS offset.
  - **Place areas are rare** (Syria clip: 4 city, 4 town, 46 village). Built-up landuse polygons
    carry the settlement signal (22.5 k polygons, 11 k at 5 ha or more, 818 named).
- **Coordinate projection cost:** `coordinates.wgs84_to_dcs` takes 0.7 µs per point, so no
  batching is needed even at tens of millions of vertices.
- **Consumers (grep across the repo):**
  - `nearest_road_osm` has no consumer outside world-model's own `describe.py` and tests.
  - body-layer reads `nearest_settlement`, `inside_settlement`, `nearest_road`, `nearest_water`
    and the ridge/valley fields by attribute (`belief/enrichment.py`); its test fakes are
    duck-typed. `belief/tools.py`, `console.py` and `speech.py` pick the highest-confidence
    `SemanticFact.text`, and `speech.py` rounds a trailing `(NNNm)`.
  - mission-interpreter reads only `position["nearest_settlement"]["name"]`
    (`synth/prompts.py::_place_name`) from the raw API JSON.
  - `query.search.PLACE_KINDS` (`settlement`, `named_place`, `airfield`, `navaid`) stays valid.
    Peaks and dams become searchable by name through `named_place`.

### Affected Modules / Files

**world-model**
- `tools/osm_tags_filter.txt` *(new)*: the committed `osmium tags-filter -e` expression file,
  the single source for RUN.md.
- `RUN.md` §2 (new filter step, file names, counts), §3.3/§3.5 (expected kinds);
  `docs/M9_OSM_RUN_INSTRUCTIONS.md` (supersession note: no OSM roads, filter step, relations now
  assembled).
- `src/osm/features.py`: new frozen `OsmRing(outer, inners)` and
  `OsmArea(id, from_way, tags, rings)` dataclasses. `OsmFeatureSet` gains `areas`. The Overpass
  `load_features` also emits every tagged closed way with 4+ points as an `OsmArea`, mirroring
  libosmium so ingest has no source branching (M9 Design Decision 3 continuity). Overpass
  relations stay a counted skip.
- `src/osm/pbf.py`: `area()` callback with its own batch buffer (`_INGEST_BATCH_AREAS`, smaller
  than `_INGEST_BATCH_ELEMENTS` because areas are vertex-heavy), and `stream_features(...,
  on_areas, ...)`.
  - `KeyFilter("landuse", "natural", "place", "waterway", "water")` passed via `filters=`.
  - `way()` returns early on untagged ways before materializing points.
  - `relation()` counts `multipolygon_relations_seen` instead of `relations_skipped`.
  - The location index stays `sparse_mem_array`, named as a constant.
- `src/geometry/__init__.py`: pure additions. `simplify_polyline(points, tol_m)` (iterative
  Douglas-Peucker), `simplify_ring(ring, tol_m)` (keeps closure, returns `None` below 3 distinct
  vertices), `ring_area_m2(ring)` (shoelace), `polygon_contains(p, outer, holes)`,
  `signed_side_of_polyline(p, points)` (sign at the closest segment, angle-weighted pseudo-normal
  at a shared vertex).
- `src/build/ingest_osm.py`: rewrite of the classification rules as three pure functions,
  `classify_node`, `classify_line` and `classify_area` (Design D2).
  - New named constants: `MIN_AREA_M2 = 50_000.0` (5 ha), `SIMPLIFY_TOLERANCE_M = 30.0`.
  - `ingest_osm_areas_batch`.
  - New `OsmIngestStats` fields (per-kind/per-class counts, min-area drops, holes kept/dropped,
    unnamed dams, degenerate after simplify, vertices before/after simplify).
  - `CLASSIFIER_VERSION = 2`. The `road` kind is removed from OSM ingest entirely.
- `src/build/pipeline.py`: a `_flush_areas` callback mirroring `_flush_ways` (base-store insert,
  cache insert, counts); the Overpass branch picks up `areas` through `ingest_osm`. Docstring note
  that stage 5 junctions now see DCS roads only (no code change: it reads `kind="road"`, and OSM no
  longer emits that kind).
- `src/osm_cache/schema.py` / `reader.py`: **no DDL change and no `OSM_CACHE_SCHEMA_VERSION`
  bump**. `StoredFeature`'s shape is unchanged; the new kinds and tags are row data. Serialized
  `OsmIngestStats` changes shape, but `CLASSIFIER_VERSION` 1 → 2 invalidates every existing cache
  before `load_cached_stats` could read it. Add a comment beside `CLASSIFIER_VERSION`: "a change to
  `OsmIngestStats`' fields also requires a bump, because the cache stores it."
- `src/store/models.py` docstring: document the reserved derived tags `inner_rings`, `area_m2`
  and `landcover_class`.
- `src/store/reader.py`: `containing_polygons` and `_distance_to_feature` honour `inner_rings`
  (a point inside a hole is not contained, and its distance is measured to that hole's ring).
  `store.schema.SCHEMA_VERSION` stays 3.
- `src/query/describe.py`: contract changes (Design D6).
- `src/api/server.py`: no code change (`asdict` picks up the new fields). Docstring mention only.
- `tools/export_geojson.py`: emit `inner_rings` as GeoJSON polygon holes, so QGIS inspection of
  the new layer is truthful.
- `tests/`: `test_osm_pbf.py`, `test_osm_features.py`, `test_ingest_osm.py`, `test_geometry*`,
  `test_store_reader.py`, `test_describe_position.py`, `test_api.py`,
  `test_pipeline_osm_cache.py`, `test_pipeline_build_region.py` (update and extend);
  `tests/test_osm_tags_filter.py` *(new; drift guard, Stage 0)*.
- `tools/validate_osm_landcover.py` *(new, Stage 6)*; a dated research note in
  `research/` (Stage 6); `CLAUDE.md` Tech-stack entry; `ROADMAP.md` entry.

**body-layer** (Stage 7)
- `src/belief/enrichment.py` plus `tests/test_enrichment.py`: subtype-aware labels, and new
  landcover and coast facts.

**mission-interpreter**: no change in this branch (Design D7).

### Design

**D1. Job (a) pre-filter: extract, then merge, then tags-filter.** Filter once, after the merge:
one command on one file. `extract --strategy=smart` has already completed multipolygon members,
and tags-filter re-adds referenced members, so relations stay complete. RUN.md changes:
- §2.3 merges to `syria-theatre-unfiltered.osm.pbf`.
- New §2.4: `osmium tags-filter syria-theatre-unfiltered.osm.pbf -e <repo>/world-model/tools/osm_tags_filter.txt -o syria-theatre.osm.pbf --overwrite`.
  The final name is unchanged, so the job (b) command is unchanged. Note that tags-filter holds
  about 2-3 GB of ID tables regardless of input size.
- §2.5 "Check it": filtered counts are expected to be roughly a quarter of the unfiltered node
  count and a few percent of the ways.

`tools/osm_tags_filter.txt` (most frequent matches first, per the osmium man page):
```
# osmium tags-filter expressions for world-model OSM ingest (RUN.md job a).
# Must stay a superset of build/ingest_osm.py's rules -- tests/test_osm_tags_filter.py guards this.
a/landuse=farmland,meadow,grass,residential,commercial,retail,industrial,military,construction,forest,orchard,vineyard,plantation,quarry,reservoir
a/natural=wood,scrub,heath,grassland,sand,bare_rock,scree,water
a/waterway=riverbank
a/place=city,town,village
w/waterway=river,dam
w/natural=coastline
n/place=city,town,village
n/natural=peak
n/waterway=dam
```
The drift-guard test parses this subset grammar (`types/key=v1,v2`) and asserts every
`(element type, key, value)` the Python classifier accepts is matched. The Python classifier
remains the authoritative second filter (it drops ponds, unnamed peaks, and so on).

**D2. Classification rules** (pure functions over a tag dict; no raw OSM tags stored).
- **Nodes:**
  - `place ∈ {city, town, village}` with `name` → `named_place`, subtype = place.
  - `natural=peak` with `name` → `named_place`, subtype `peak`.
  - `waterway=dam` with `name` → `named_place`, subtype `dam`.
- **Lines (`way()` only; closed or open):**
  - `waterway=river` → `water`/`river` LineString (name kept).
  - `natural=coastline` → `coastline` LineString, vertex order preserved.
  - `waterway=dam` with `name` → `named_place`/`dam` Point at the polyline's half-length vertex.
  - All line geometry is simplified at 30 m. No area minimum applies.
- **Areas (`area()` only).** Evaluated in precedence order, so conflicting tags resolve
  deterministically:
  1. Water: `natural=water` with `water ∈ {lake, reservoir, river}` or no `water` tag →
     `water`/`lake|reservoir|river_area`; `landuse=reservoir` → `water`/`reservoir`;
     `waterway=riverbank` → `water`/`river_area`. Every other `water=*` value is dropped and
     counted.
  2. `place ∈ {city, town, village}` → `settlement`, subtype = place (named extent). Gets
     `landcover_class=built_up` too if its `landuse` is also built-up.
  3. `landuse ∈ {residential, commercial, retail, industrial, military, construction}` →
     `settlement`/`built_up`, `landcover_class=built_up`.
  4. Landcover by `landuse` (`forest`; `orchard|vineyard|plantation` → `orchard`;
     `farmland|meadow|grass` → `fields`; `quarry` → `barren`), then by `natural` (`wood` →
     `forest`; `scrub|heath` → `scrub`; `grassland` → `fields`; `sand|bare_rock|scree` →
     `barren`). Result: `landcover`, subtype = class, `landcover_class` = class.
  5. Anything else → counted unclassified. `natural=coastline` and `waterway=dam` areas are
     ignored here, because `way()` already handles them.

**D3. Per-ring geometry pipeline.** Each outer ring becomes its own `Polygon` feature, with
`source_ref` = `way/<orig_id>` or `relation/<orig_id>`. For each ring:
1. Project every vertex to DCS x/z.
2. Region check: keep the ring if any vertex is inside the region (unchanged rule).
3. Compute the unsimplified net area: outer minus holes at or above the minimum.
4. **Apply `MIN_AREA_M2` to water, landcover and built-up rings only.** Place-area settlements
   are exempt (named, rare); points and lines are exempt.
5. Simplify the outer ring and each kept hole at 30 m. A ring that degenerates below 3 distinct
   vertices is dropped and counted.
6. Holes below 5 ha are dropped and counted; kept holes go to `tags["inner_rings"]`.
7. `tags["area_m2"]` = net area.

Min-area is judged per outer ring, not per relation total, so it is consistent for fragmented
multipolygons.

**D4. Memory and the location index at `syria-full` scale.**
- **Index:** `sparse_mem_array` costs about 16 B per node in the file.
  - Unfiltered merged extract (69 M nodes): about 1.1 GB, the same as the last build.
  - Pre-filtered estimate from the two measured ratios (Syria 13 %, Turkey 29 % of nodes): about
    18-22 M nodes, roughly 300-350 MB.
  - `flex_mem` and dense indexes are not adopted: `sparse_mem_array` is already proven at this
    scale. The pre-filter makes this comfortable; it is not a hard requirement.
- **Area assembly:** the manager buffers member ways only until each relation completes. The
  Turkey clip peaked at 467 MB total RSS.
- **Estimate for the filtered merged file:** about 1-1.5 GB peak and about 2 minutes for the area
  pass. This is extrapolated, not measured; the user's full build is the measurement.
- **Streaming bounds unchanged:** nodes, ways and areas each flush in bounded batches, one base
  store transaction plus one cache insert per batch.

**D5. Coastline side rule.** OSM coastlines run with land on the left and sea on the right in
geographic (east, north) coordinates.
- DCS x is north and z is east, which flips handedness. With
  `cross_dcs = (bx-ax)(pz-az) - (bz-az)(px-ax)`, the point is to the geographic left (land) when
  `cross_dcs < 0`.
- At a shared vertex, `signed_side_of_polyline` uses the sum of the two adjacent segments' unit
  normals.
- Coastline ways are split, so each way is judged independently from its nearest segment.
- **Correctness gate:** a control-point test pushes a real-geography, north-to-south
  Mediterranean coastline (lon 35.75, lat 35.60 → 35.45) through `wgs84_to_dcs`, then asserts
  lon 35.70 → `"sea"` and lon 35.80 → `"land"`. This encodes the axis flip through the real
  transform instead of trusting the derivation above.

**D6. `describe_position` contract (world-model API JSON follows via `asdict`).**

| field | change |
|---|---|
| `nearest_road_osm` | **removed** |
| `nearest_road` | unchanged (DCS-only; keeps `provenance_geometry="dcs"` as a guard) |
| `nearest_settlement` | same field and query, now only built-up/place polygons. `SettlementInfo` gains `subtype` (`built_up`, `city`, `town`, `village`) |
| `inside_settlement` | containing settlement polygons (holes honoured); prefer named, then smallest `area_m2`. `SettlementInfo.subtype` as above |
| `nearest_water` | kind `water` only (river line, lake, reservoir, river area); `WaterInfo` gains `subtype` |
| `nearest_coastline` | **new** `CoastlineInfo(distance_m, side: "sea" \| "land", provenance, confidence, position_uncertainty_m)` or `None` beyond 30 km |
| `inside_landcover` | **new** `LandcoverInfo(landcover_class, name, provenance, confidence, position_uncertainty_m)`: smallest-`area_m2` polygon among `landcover` and `settlement` rows carrying `landcover_class`, holes honoured. `None` means **no mapped landcover (open or unmapped)**, not "confirmed open ground" and not "layer absent". The docstring states this, like M6's ridge/valley note |
| `named_places_within_radius` | `NamedPlaceInfo` gains `subtype` (`peak`, `dam`, place value, or DCS towns' `None`) |

Why `nearest_road_osm` is removed rather than left always-`None`:
- An always-`None` field would read under rule 3 as "no OSM road near here", when the truth is
  "this layer does not exist by design".
- It has zero consumers (grep across body-layer, mission-interpreter and aircraft-layer).
- A dead field invites someone to wire it back up.

Module docstring rule 2 is reworded generically (DCS wins; OSM augments different facts).
All other changes are additive fields, which is safe for body-layer's attribute access and MI's
dict access.

**D7. Downstream adaptation.**
- **body-layer, Stage 7, in this branch.** The first consumer lands with the contract it tests.
  Split it into a follow-up branch if body-layer has in-flight work on `enrichment.py`.
  `semantic_facts_for` changes:
  - Unnamed settlement: `subtype == "built_up"` → "near a built-up area (Nm)" / "inside a
    built-up area"; otherwise keep the current wording.
  - Unnamed water: "near a river|lake|reservoir (Nm)" from `subtype`.
  - New landcover fact, only when `inside_landcover` is non-`None` and the class is not
    `built_up` (built-up is already covered by `inside_settlement`). Texts: "in forest",
    "in orchards", "in scrubland", "in open fields", "on barren ground";
    `feature_id="landcover:<class>"`.
  - New coast fact, only when `nearest_coastline` is within `COAST_FACT_RADIUS_M = 5000`, or
    `side == "sea"`:
    - "over the sea, off the coast (Nm)" when `side == "sea"` and
      `distance_m >= position_uncertainty_m`;
    - otherwise "near the coast (Nm)".
    - Texts end in `(Nm)`, so `speech._ENRICHMENT_DISTANCE_RE` rounding still applies.
  - Facts are appended after the existing ones. `max(..., key=confidence)` returns the first
    maximum, so current location phrasing keeps priority on ties.
- **mission-interpreter: no code change required.** `_place_name` still reads
  `nearest_settlement.name`, which now only names built-up/place extents, never a named farm or
  cemetery parcel. **Scoped follow-up (not this branch):** fall back to
  `named_places_within_radius[0].name` (DCS `towns.lua`, authoritative) when the nearest
  settlement is unnamed. Most built-up polygons are unnamed (Syria clip: 818 of 22.5 k), so
  this would materially improve threat-signal phrasing.

### Implementation Plan

0. **Pre-filter and docs, no pipeline code.** Add `tools/osm_tags_filter.txt`, the RUN.md §2
   changes (D1) and `tests/test_osm_tags_filter.py`. The test asserts a hard-coded table of
   classifier-accepted tags against the file for now; Stage 3 rewires it to the classifier's own
   constants. Gate: `ruff`/`mypy`/`pytest` green.
1. **Parse layer: areas.** `OsmRing`/`OsmArea`, the `pbf.py` `area()` callback, `KeyFilter`, the
   untagged-way early return, `on_areas` batching, stats; the Overpass closed-way-to-area mirror.
   Tests use a `SimpleWriter` fixture built at test time (existing pattern):
   - closed landuse way → one area (and also one way callback);
   - a two-piece outer relation with an inner ring → one area with one hole;
   - a closed coastline way → a line and an area;
   - untagged inner member → no area;
   - highway/building ways never reach the Python callbacks;
   - batch-bound test extended to areas.
2. **Geometry primitives.** Simplify, ring area, polygon-with-holes containment and signed side.
   Pure unit tests, plus the D5 coastline control-point test through `wgs84_to_dcs`. Also a
   convex and a concave shared-vertex case for the pseudo-normal.
3. **Classifier and ingest.** The D2 rules and D3 ring pipeline, `MIN_AREA_M2` /
   `SIMPLIFY_TOLERANCE_M`, minimal tags, `CLASSIFIER_VERSION = 2`, the stats comment.
   - One test per D2 rule, including every drop-list value in the brief (hamlet,
     isolated_dwelling, farm, suburb, neighbourhood, quarter; stream, canal, ditch, drain, pond,
     pool; cemetery, park, village_green, allotments, recreation_ground, brownfield, wetland;
     `highway=*`).
   - Precedence conflicts; min-area boundary (just under or over 5 ha) for landcover, water and
     built-up; place-area exemption.
   - Hole kept vs dropped; simplify degeneracy; unnamed peak and dam dropped; dam line → Point.
   - Rewire the Stage 0 drift test to the classifier's constants.
4. **Pipeline and cache.** `_flush_areas`, stats plumbing, junction docstring. Extend the
   existing cache parity test (miss vs hit must be byte-identical) to a fixture with areas, holes,
   a coastline and a peak. The invalidation tests stay green; add a test that a
   `CLASSIFIER_VERSION = 1` cache is rejected. Check that bounded batching holds for areas (the
   existing `tracemalloc`-style test).
5. **Query contract.** Reader hole support (`containing_polygons`, polygon distance), the D6
   `describe_position` changes, `export_geojson` holes. Tests:
   - `inside_landcover` smallest-area precedence (a fields polygon inside a forest; a point in a
     forest relation's hole with nothing mapped → `None`);
   - `inside_settlement` named-over-unnamed;
   - `nearest_coastline.side` on both sides;
   - `nearest_road_osm` absent from `asdict` / API JSON;
   - `search.find_place_by_name` finds a peak.
   - An existing world-model test asserting OSM `road` rows or `nearest_road_osm` is **rewritten**,
     not extended, as a consequence of user decision 1 (listed here per the AGENTS.md escalation
     rule; already user-decided, so not escalated).
6. **Real small-extract validation (agent-run; never `syria-full`, never the merged file, never
   reading `data/world-model/syria-full.sqlite`).**
   - Pre-filter `syria-clipped.osm.pbf` (and `lebanon-clipped` if time allows) into a scratch
     directory.
   - Build `latakia-20km` with explicit DCS inputs plus `--osm-pbf` of the filtered file, to a
     scratch `--out`.
   - Build one ad-hoc 20 km region over Lake Assad's Tabqa end, defined in the tool rather than
     registered in `build.region`.
   - `tools/validate_osm_landcover.py` reports:
     - parse and ingest time, peak RSS;
     - counts per kind and class, vertex counts before and after simplification, the largest
       stored polygon's vertex count, holes kept;
     - `describe_position` timings over a few hundred points.
   - Control points:
     - Latakia city centre → non-`None` `inside_settlement` (closes M9's documented relation gap);
     - a sea point west of Latakia → `nearest_coastline.side == "sea"`;
     - a Latakia inland point → `"land"`;
     - a Lake Assad point → `nearest_water.distance_m == 0`, `subtype == "reservoir"`.
   - Write a dated research note with these numbers.
7. **body-layer adaptation** (D7): `enrichment.py` plus tests; run body-layer's own
   ruff/mypy/pytest, and world-model's as well.
8. **Docs and bookkeeping.** `world-model/CLAUDE.md` Tech-stack entry (pre-filter, landcover and
   coastline kinds, holes-in-tags rationale, `nearest_road_osm` removal); `M9_OSM_RUN_INSTRUCTIONS.md`
   supersession note; `world-model/ROADMAP.md` entry, including the milestone-completion question
   (does this change what comes next?).

User-run afterwards: job (a) with the new §2.4 filter step, then a full `syria-full` build. The
build re-parses once, because both the classifier version and the `.pbf` hash change.

### Risks & Unknowns

- **`describe_position` latency.** Two new queries (`inside_landcover`, `nearest_coastline`), and
  very large polygons (Lake Assad, big forest relations) are JSON-parsed and point-in-polygon
  tested in Python on every call whose bbox overlaps them. The M7 p99 is already ~800 ms. Simplify
  at 30 m first, and record the largest post-simplification polygon vertex count in Stage 6. If it
  stays in the tens of thousands, tiling large polygons is a follow-up, not a redesign.
- **Holes in `tags_json`** keep the base schema version fixed. Any future non-OSM producer of
  holed polygons must use the same tag, documented in `store.models`. If holes ever become common
  across sources, a real geometry column plus a probe-store pairing migration is the cleaner
  design.
- **Classifier edge cases vs uncertainty.**
  - Smallest-area precedence can misreport overlapping mapping. Example: a small `grass` polygon
    in a city → `fields` inside a built-up area.
  - `landcover` and settlement polygons are real-world geometry, ~1.3 km off DCS terrain, so
    containment is only meaningful at that scale.
  - `position_uncertainty_m = 1300` is carried on every row and surfaced in every Info type.
- **`nearest_coastline.side` near the coast is unreliable** within `position_uncertainty_m`, so
  body-layer's wording deliberately hedges there (D7). Coastline ways that end at the region edge
  or at extract seams (Turkey/Syria border smart-extract) may be missing pieces, which can give a
  wrong nearest segment in rare spots.
- **Memory and time figures at `syria-full` scale are extrapolated** from the two clips (D4), not
  measured. The user's full build is the check.
- **Legacy `waterway=riverbank` / generic `natural=water` / `landuse=reservoir`** inclusion
  (substitution 7) may admit some non-lake bodies at or above 5 ha (e.g. evaporation or treatment
  basins mapped generically).
- **`osmium tags-filter` holds ~2.3 GB of ID tables** regardless of input size. This is fine on
  the 15 GB WSL box, but worth one line in RUN.md.

### Out of scope / follow-ups

- **Power lines** (user decision 9): DCS-sourced, see
  `world-model/research/2026-09-13-dcs-power-lines-recon.md` (branch
  `worktree-agent-a75dd09dfecfd4726`).
- **Mission Interpreter `_place_name` fallback** to `named_places_within_radius` (D7).
- **Landcover-aware perception.** body-layer/PB-1.5 detection could modulate a target's
  detectability by `inside_landcover` at its position. This is the actual "visibility of units"
  payoff, but it is a perception-model change, not part of this plan.
- **Tiling of giant polygons**, only if Stage 6 shows it is needed.

### Second-order effect

This makes the landcover and settlement facts truthful (no more "near <farmland>"). It also
exposes a landcover class that unblocks landcover-aware detection and phrasing in body-layer
without further world-model work. The OSM stage shrinks from tens of minutes to low minutes even
on a cache miss, which reduces how much the OSM classified cache matters for future rule-tuning
iterations.
