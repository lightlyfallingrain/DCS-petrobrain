### Implementation Summary — Stage 0 (census, no store code)

Derived the `latakia-20km` DCS-space envelope, confirmed both known `towns.lua` entries fall
inside it, picked the eastward offset, ran one widened Overpass fetch, and confirmed
`Syria.routes`'s local path/size. All four Stage 0 gate items pass. No `src/store/`,
`src/build/`, `src/roadnet/`, or `src/dcs_data/` code was written, per the checklist.

### Files Changed
- `world-model/src/osm/overpass.py` — added an optional `query: str | None = None` parameter to
  `fetch_bbox`, defaulting to the existing M3 query builder when omitted. Backward compatible
  (M3's call sites and tests are unaffected); lets Stage 0's widened-query census fetch reuse
  the cache-first/single-network-call/User-Agent discipline instead of reimplementing it.
- `world-model/tools/fetch_m5_stage0_census.py` — new throwaway census script. Computes the
  region envelope from the OSLK ARP centre + chosen offset via `coordinates.dcs_to_wgs84`,
  builds the widened Overpass query (M3's `highway`/`building`/`place` node/`waterway` set plus
  `landuse`, `natural=water`, `place` way/relation), fetches once via `osm.overpass.fetch_bbox`,
  and reports feature counts against the Stage 0 gate (water polygons, settlement polygons,
  named places all present).
- `world-model/research/2026-09-04-m5-stage0-census.md` — dated research note recording the
  envelope, offset choice and reasoning, fetch results, and gate pass/fail, plus the
  `Syria.routes` acquisition confirmation.

### Tests Added
None — Stage 0 is a census/verification stage with no pipeline code to unit-test. Existing
`tests/test_osm_overpass.py` continues to pass unmodified against the now-optional `query`
parameter (default behavior unchanged).

### Checks
- `ruff format --check world-model/src world-model/tests world-model/tools`: pass
- `ruff check world-model/src world-model/tests world-model/tools`: pre-existing findings in
  untouched files only (EXE001 non-executable shebangs in other `tools/*.py`, one I001 in
  `tools/report_control_point_errors.py`) — not introduced by this session; the two files
  touched here (`src/osm/overpass.py`, `tools/fetch_m5_stage0_census.py`) are clean except the
  same pre-existing EXE001 shebang convention every other `tools/` script also carries.
- `mypy --strict world-model/src`: pass (10 source files)
- `pytest world-model/tests -q`: pass (30 passed)

### Notable Discoveries
- **Network access requires `dangerouslyDisableSandbox: true` in this environment** — the
  default sandboxed Bash cannot reach `overpass-api.de` (connection times out). Flag for any
  future session needing an Overpass/network fetch.
- **The plan's "+3 km" Jablah-margin estimate was conservative.** Recomputing from `towns.lua`'s
  full-precision lat/lon (not the plan's rounded values) shows Jablah does not actually leave
  the box until roughly +5,941 m of eastward offset, not ~+3 km. This session still respected
  the checklist's explicit 0–+3 km cap rather than exploiting the larger margin — the cap is an
  instruction, not a derived limit, so it wasn't reopened. Worth noting in case a later stage
  needs to revisit the offset.
- **Chosen offset: +3,000 m** (the mandated cap). Both named places keep multi-kilometre margins
  at this offset (Jablah 2,940.97 m from the west edge, Al Hannadi 4,102.34 m from the east
  edge).
- **Widened Overpass fetch, offset region**: 13,618 elements total; 27 water polygons, 194
  settlement polygons (`place=*` or `landuse=residential`), 112 named places. Two named OSM
  nodes with an English name tag independently corroborate the two DCS gazetteer entries:
  "Jable" (`place=city`) ≈ `towns.lua`'s Jablah, "Hanadi" (`place=village`) ≈ `towns.lua`'s Al
  Hannadi. This was a sanity spot-check only, not used to satisfy the gate or to fuse datasets.
- **`Syria.routes` was already correctly staged** at
  `world-model/data/raw/dcs/syria/roads/Syria.routes`, exactly 2,251,462,776 bytes — no move or
  copy was needed this session.
- Raw fetch cache (19,631,612 bytes) lives at
  `world-model/data/raw/osm/2026-09-04/latakia_20km_widened.json`, correctly gitignored via
  `world-model/.gitignore`'s `data/raw/` rule — confirmed with `git check-ignore -v`, not staged.

---

### Implementation Summary — Stage 1 (offline sources only, no DCS round-trip)

Built `src/geometry/`, `src/dcs_data/` (towns + beacons parsers), `src/store/` (SQLite + R*Tree
schema, writer, reader), `src/build/` (region registry + towns/beacons/OSM ingest + pipeline),
`src/query/` (`describe_position`), and three CLI tools
(`build_world_model.py`, `describe_position.py`, `export_geojson.py`). Ran the full pipeline
against the real Latakia raw inputs staged in Stage 0 and confirmed plausible, non-empty,
non-absurd feature counts and sane `describe_position` output at several points, including one
independent cross-check against OSM. Roadnet ingest (Stage 2) and the elevation/surface-type probe
(Stage 3) are deliberately not wired in — `nearest_road` (DCS), `elevation`, and `surface_type`
correctly return `null` at this stage.

### Files Changed / Added
- `world-model/src/coordinates/__init__.py` — **performance fix, not a design change.**
  `dcs_to_wgs84`/`wgs84_to_dcs` built a fresh `pyproj.Transformer` on every call; ingesting one
  OSM way's every vertex through it made a Latakia region build (13,618 raw elements) take
  minutes of 100%-CPU time dominated by CRS/pipeline setup, not coordinate math. Added
  `@functools.cache`-wrapped per-theatre transformer builders (`_dcs_to_wgs84_transformer`,
  `_wgs84_to_dcs_transformer`); public signatures, behavior, and existing tests are unchanged.
  Confirmed by timing: full Latakia build dropped from >2m33s (killed, still running) to 0.59s
  wall time. Recorded as a performance-sensitive path in agent memory.
- `world-model/src/osm/overpass.py` — widened the *default* `_build_query` (previously Stage 0
  passed an override) to add `way["place"]`, `relation["place"]`, `way["natural"="water"]`,
  `relation["natural"="water"]`, `way["landuse"]` alongside M3's original set, per the plan's
  "Modified" section. No existing test asserts on query text, so this is safe against
  `test_osm_overpass.py`.
- `world-model/src/osm/features.py` — added `OsmFeatureSet.relations_skipped: int` (additive
  field, default 0) and counted `"relation"` elements in `load_features` instead of silently
  ignoring them, per the plan's "Multipolygon relations" risk entry ("an explicitly counted skip,
  never a silent drop"). `test_load_features_ignores_unrecognized_element_types`'s node+way count
  assertion is unaffected since relations were never counted in that sum.
- `world-model/src/geometry/__init__.py` — `distance_point_point`, `distance_point_segment`,
  `distance_point_polyline`, `point_in_polygon` (ray casting, treats boundary points as inside),
  `bearing_deg`, `orientation_label` (buckets into N-S/NE-SW/E-W/NW-SE axis labels), `bbox_of`.
  Pure functions, no I/O.
- `world-model/src/dcs_data/towns.py`, `beacons.py` — strict regex parsers per the plan's exact
  spec (list not dict for towns; multi-line block parsing with `{x, y, z}` middle-is-elevation for
  beacons; `airfield_group` derivation; `positionGeo` parsed but never used for
  positioning/validation). Verified against the real staged raw files: 1,182 towns (31 duplicate
  names, 1,151 unique), 151 beacons, all 8 `airfield21` beacons round-trip exactly.
- `world-model/src/store/schema.py`, `models.py`, `writer.py`, `reader.py` — schema DDL verbatim
  from the checklist, `SCHEMA_VERSION` meta check, frozen dataclasses, R*Tree-populating writer,
  and a reader with `features_in_bbox` (R*Tree-pruned), `nearest_feature` (expanding-radius
  500m/2km/8km/30km, exact-geometry-distance confirmed, with an added `provenance_geometry` filter
  so `nearest_road`/`nearest_road_osm` can share `kind="road"` but answer independently),
  `containing_polygons`, `sample_grid` (bilinear for elevation, nearest-cell for surface_type).
  Added `load_only_region` (single-region-per-file convenience) and `all_features` (unfiltered,
  for the GeoJSON exporter) beyond the plan's minimum list — both are small, obviously-scoped
  reader additions needed by `query/describe.py` and `tools/export_geojson.py` respectively.
- `world-model/src/build/region.py` — `RegionDefinition`, `REGIONS` with `latakia-20km` (centre
  **x=44934.892, z=5685.076** — Stage 0's census note confirmed the +3,000m offset is baked into
  the stored centre, not applied at query time) and `gemerek-20km` (kept registered, centre from
  the plan's own candidate-region table).
- `world-model/src/build/ingest_towns.py` — towns.lua → `named_place` features. **Genuine
  ambiguity resolved conservatively, flagged for follow-up**: the plan explicitly leaves
  towns.lua's positional uncertainty unresolved (DCS in-game label position, ~0m, vs. a
  terrain-artist-pasted real-world coordinate, ~1300m) and suggests an OSM-name-match diagnostic
  as "worth doing in Stage 1". Ran it: one clean match (Jablah vs. OSM's "Jable", 465.5m apart)
  and one that is almost certainly a wrong name match (Al Hannadi vs. an OSM "Hanadi" 6km away).
  n=1 is not decisive either way, so `position_uncertainty_m` is set conservatively to 1300m
  (matching OSM's residual) with `confidence["geometry"]="medium"` rather than `"high"`, and the
  reasoning is documented in the module docstring. `provenance["geometry"]="dcs"` is kept as-is
  since the source genuinely is DCS-shipped data — only the precision claim is downgraded.
- `world-model/src/build/ingest_beacons.py` — beacons.lua → `navaid`/`runway`/`airfield` features
  exactly per the plan's pairing rule (ILS/PRMG never crossed, unpaired → skip + count, ILS
  preferred over PRMG for the airfield-point axis when both exist). Verified against real data:
  ILS pair 2635.04m @ 0.31°, PRMG pair 2277.98m @ 0.96° (as the reverse-direction bearing
  180.96°), derived airfield point (41740.54, 5697.76) — all match the plan's worked Latakia
  numbers to the metre/hundredth-degree.
- `world-model/src/build/ingest_osm.py` — Overpass features → `road`/`settlement`/`water`/
  `named_place`, classified by tag (highway / waterway·natural=water / landuse·place-way /
  place-node), closed-way heuristic for Polygon vs. LineString, `relations_skipped` and
  `ways_skipped_unclassified`/`ways_skipped_degenerate` counted rather than silently dropped.
  Buildings are fetched (needed for nothing in M5's six layers) but deliberately not ingested —
  confirmed by `ways_skipped_unclassified == 9679`, which matches the raw building count exactly.
- `world-model/src/build/pipeline.py` — `build_region`, idempotent (`open_for_build` deletes any
  existing file first), wires towns → beacons → OSM in one build, returns a `BuildReport` with
  per-kind feature counts and each ingest module's stats.
- `world-model/src/query/describe.py` — `describe_position` and its frozen result dataclasses,
  implementing the contract's four honesty rules. `nearest_road` (DCS) vs. `nearest_road_osm`
  share `kind="road"` and are separated via `nearest_feature`'s new `provenance_geometry` filter.
  Elevation/surface_type/`nearest_road` correctly return null/None at this stage (Stages 2-3 not
  wired in) — verified this is reported as absence, not a crash or a guess.
- `world-model/tools/build_world_model.py`, `describe_position.py`, `export_geojson.py` — CLI
  wrappers per the plan's tool list. `export_geojson.py` converts every vertex back to WGS84 via
  `coordinates.dcs_to_wgs84` and embeds full provenance/confidence/uncertainty in GeoJSON
  `properties`, and prints the OSM/ODbL attribution line when any exported feature is OSM-sourced.
- `world-model/pyproject.toml` — added `osm`, `geometry`, `dcs_data`, `store`, `build`, `query` to
  `known-first-party` (the plan's list also names `roadnet`, deferred to Stage 2 since that
  package doesn't exist yet).
- `world-model/data/raw/dcs/syria/map/towns.lua`, `beacons.lua` — assembled from the verbatim
  probe capture (`research/2026-09-03-m5-nodes-lua-probe.txt`'s grep-pass and full-content
  sections) as the first-class raw ingest inputs the plan calls for. Gitignored, not staged
  (confirmed via `git check-ignore -v`).

### Tests Added
- `tests/test_geometry.py` — hand-computed distance/bearing/bbox answers plus degenerate cases
  (zero-length segment, point on polygon vertex/edge, both winding orders, <3-vertex raise).
- `tests/test_towns_lua.py` — parses a hardcoded literal fixture (real Aleppo/Latakia/Jablah/Al
  Hannadi entries plus a real 3-way "Yeniyurt" duplicate); asserts all three duplicate rows
  survive, malformed entries raise, and the count assertion fires independently of malformed
  content.
- `tests/test_beacons_lua.py` — parses the real `airfield21` group (8 beacons) plus one `world_*`
  entry; pins the `{x, y, z}` middle-is-elevation field order on `airfield21_3` (HOMER, whose
  elevation 121.7m is obviously not its real z=5622.08), covers both `airfield_group` forms, the
  optional-frequency-is-None-not-guessed case (RSBN/PRMG beacons), and malformed-block/count-
  mismatch raises.
- `tests/test_ingest_beacons.py` — ILS pair ~2635m/~0.31°, PRMG pair ~2278m, ILS/PRMG never
  crossed (exact beaconId pinning per system), unpaired localizer emits no runway and increments
  the skip counter (falling back to centroid derivation), derived airfield point is the ILS-axis
  midpoint (~41740.5, ~5697.8), and the provenance/uncertainty scope guard (every derived feature
  is `derived_from_dcs_beacons` + nonzero uncertainty; every navaid is `dcs` + 0.0).
- `tests/test_store_roundtrip.py` — schema creation + `SCHEMA_VERSION` meta row, idempotent
  rebuild (`open_for_build` on an existing file drops prior data), region/source/feature
  roundtrip with provenance/confidence JSON preserved verbatim, R*Tree bbox row populated
  correctly, empty-geometry insert raises, and both `SCHEMA_VERSION` mismatch and missing-meta
  cases raise.
- `tests/test_store_reader.py` — **R*Tree-vs-brute-force agreement** over 200 random synthetic
  point features (50 query points) and a mixed point/LineString set (30 query points), with the
  brute-force reference implemented in the test using `geometry` functions directly, not by
  importing store internals; plus `provenance_geometry` filtering, `containing_polygons`
  inside/outside, and `sample_grid` bilinear-interpolation-at-centre / nearest-cell-not-
  interpolated-for-surface_type checks.
- `tests/test_describe_position.py` — Stage 1 smoke test (not the Stage 4 control-point
  tolerance-band test) against a small hand-built fixture store: runs without crashing, finds a
  fixture named place, degrades to explicit nulls far outside coverage, and every present field
  carries non-empty provenance.

### Checks
- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass (0 findings in touched/new files;
  `world-model/tools/{build_world_model,describe_position,export_geojson}.py` individually
  checked — clean except the same pre-existing repo-wide EXE001 non-executable-shebang convention
  every other `tools/*.py` script also carries, confirmed against the unmodified baseline)
- `mypy --strict world-model/src`: pass (27 source files)
- `mypy --strict world-model/tests`: pass (15 source files)
- `pytest world-model/tests -q`: pass (96 passed)

### End-to-end verification (real Latakia data)
Ran `tools/build_world_model.py latakia-20km` against the real staged raw inputs
(`data/raw/dcs/syria/map/{towns,beacons}.lua`, Stage 0's cached Overpass response). Resulting
`.sqlite` feature counts: `airfield=1, named_place=108 (2 DCS + 106 OSM), navaid=8, road=3136,
runway=2, settlement=338, water=117` — all non-zero, none implausibly large for a 20x20km region
(9,679 OSM buildings were fetched but correctly *not* ingested, since buildings aren't one of
M5's six layers — confirmed by `ways_skipped_unclassified` matching that count exactly).

`describe_position` spot-checks, run via `tools/describe_position.py`:
- At the OSLK ARP (`--latlon 35.40109 35.94868`): `nearest_airfield` = LATAKIA, 194.8m,
  `derivation="runway_axis_midpoint"`; `nearest_runway` = ILS, 13.7m, `orientation_deg=-1.456`
  (from the beacon's own `direction` field, not a computed bearing); `elevation`/`surface_type`/
  `nearest_road` correctly null (Stages 2-3 not wired in); `nearest_road_osm` found a real OSM
  service road 136m away with `position_uncertainty_m=1300`. No crash.
- At Jablah's DCS coordinates: `named_places_within_radius` returned both the DCS "Jablah" entry
  (distance 0, as expected — it's the query point) and OSM's "جبلة" 465.9m away — an
  **independent, unplanned cross-check** confirming the `ingest_towns.py` diagnostic's ~465.5m
  Jablah/Jable offset finding from a completely different code path (`describe_position` vs. a
  one-off analysis script), both landing within a metre of each other.
- Far outside the region (`x=0, z=0`, tens of km away): `nearest_settlement`,
  `nearest_road_osm`, `nearest_airfield` all correctly `null` rather than a distant plausible-
  looking wrong answer.
- `tools/export_geojson.py` on the built store: 3,710 features written, round-tripped Al
  Hannadi's coordinates back to its exact original lat/lon (35.480731, 35.927036), confirming the
  DCS→store→WGS84 export path is lossless for the values that matter.

### Notable Discoveries
- **`coordinates.wgs84_to_dcs`/`dcs_to_wgs84` building a fresh `pyproj.Transformer` per call is a
  real, load-bearing performance problem at OSM-ingest scale**, not a hypothetical one — it made
  Stage 1's first build attempt run for minutes before being killed. M1-M4 never exercised this
  path at more than a few hundred calls (control points, small grids), so it was invisible until
  M5's ~13,600-element widened Overpass fetch. Fixed with per-theatre `@functools.cache`; flagged
  in agent memory as a performance-sensitive path for any future milestone (M6 ridge/valley
  extraction, M7 full-theatre) that pushes even more coordinates through this module.
- **towns.lua positional uncertainty stays genuinely unresolved** after the Stage-1-suggested
  diagnostic — one match supports "DCS in-game position" (small residual), one apparent match is
  almost certainly wrong (6km, likely a different real-world place with a similar transliterated
  name). Resolved conservatively (see `ingest_towns.py` above); a future session with a larger,
  hand-verified match sample could tighten this without changing the ingest module's shape.
- **`osm.features.OsmFeatureSet` gained `relations_skipped` as an additive field**, not a
  behavior change to existing parsing — 13 relations exist in the real widened Latakia fetch
  (mostly multipolygon water/administrative boundaries), now counted rather than invisible.
- Real beacon data confirmed a plan assumption that mattered for the parser: **PRMG_LOCALIZER,
  PRMG_GLIDESLOPE, and RSBN beacons carry `channel` instead of `frequency`** (6 of 151 beacons
  have no `frequency` field at all) — `BeaconEntry.frequency: float | None` handles this
  correctly; a non-optional field would have raised on real data.

---

### Implementation Summary — Stage 2 (`src/roadnet/`, DCS-native roads, still offline)

Built the roadnet package in the three mandated rungs, smallest first, then wired it into the
build pipeline and ran the full 2.25 GB `Syria.routes` walk twice (once standalone to establish
the gate/coverage numbers, once as part of the real end-to-end store rebuild) — both runs agree
exactly (14,861 whole-file routes, 131 in the Latakia region), which is itself a useful
determinism check on the parser.

### Files Changed / Added
- `world-model/src/roadnet/__init__.py` — package docstring stating format provenance (which
  research note, which files) and, per the plan's explicit instruction, which parts of the format
  are decoded vs. intentionally skipped (the `.routes` per-route trailer, `.rn4`'s
  adjacency/graph section and its embedded geometry, and the topology-row-to-geometry join).
- `world-model/src/roadnet/container.py` — shared `landscape4::` primitives: `read_header`
  (asserts the exact class name, raises `ContainerFormatError` on mismatch or truncation),
  `read_length_prefixed_string`, `read_int32`, `read_point_block` (strict, no-scan reader for a
  block known to start exactly at an offset — used for a `.routes` direction array, always
  adjacent to its position array), and `find_next_point_block` (the scan-forward resync: a
  first/middle/last coordinate pre-filter before a full N-point validation, both against a DCS
  coordinate envelope `|x|,|z| < 1e6`, `-2000 < y < 6000`).
- `world-model/src/roadnet/routes.py` — `RoutePolyline` (frozen), `RouteWalkStats` (mutable
  out-parameter populated during the walk, since a generator's return value is awkward to recover
  mid-iteration), and `iter_routes(path, bbox=None, stats=None)` — a streaming generator over an
  `mmap`. Per route: the position block is found via scan-forward resync (normal, expected once
  per route boundary — the trailer between routes is never parsed); the direction block is then
  read with the strict non-scanning reader at exactly the position block's end offset, since the
  confirmed format has them always adjacent — a direction block *not* found there, or one that
  fails a unit-magnitude sanity check on its first/middle/last vector, increments
  `sync_loss_events` rather than raising, since real-file walks (see below) show a small,
  non-fatal anomaly rate is normal.
- `world-model/src/roadnet/rn4.py` — `parse_header`, `read_string_table`, `iter_topology_rows`
  (terminates, without yielding, at the first row failing `column[1] == 1 and column[4] == 2` —
  confirmed against real Damascus/Incirlik data to be exactly the table's own sentinel row, not a
  data row), `type_name_for_row` (column 6, confirmed string-table index). Explicit non-goals
  restated in the module docstring per the plan: no adjacency-section decode, no row-to-geometry
  join.
- `world-model/src/roadnet/extract.py` — `write_region_extract`/`read_region_extract` (JSON
  Lines) + `ExtractManifest`/`read_manifest` (source path/size/mtime, extractor version, bbox,
  counts, walk stats). Built per the plan's spec but **not wired into the pipeline** — Stage 2
  rung 3 runs `ingest_roadnet.py` directly against the real local `Syria.routes` file, per the
  Option A acquisition decision ("ingest_roadnet.py can read either the extract or walk the full
  file directly"); the extract module is a ready, tested-by-construction local cache for anyone
  who wants faster iteration later, not a dependency of today's build. `tools/
  extract_roadnet_region.py` and `tools/inspect_roadnet.py` (listed in the plan's file list) were
  **not built this session** — out of this task's explicit ask (rungs 1-3, ingest wiring, tests,
  gate, coverage, final rebuild), and `extract.py`/`ingest_roadnet.py` don't need them to
  function. Flagged here rather than silently dropped; cheap to add later if wanted.
- `world-model/src/build/ingest_roadnet.py` — `ingest_roadnet(routes_path, centre_x, centre_z,
  half_extent_m, source_id) -> (features, RoadnetIngestStats)`. Walks the whole file (bbox only
  filters what's *yielded*, not how much is walked — `.routes` has no spatial index to seek
  into), converting every intersecting route into a `road` `StoredFeature`:
  `provenance={"geometry": "dcs"}`, `confidence={"geometry": "high"}`,
  `position_uncertainty_m=0.0`, `subtype=None`, `name=None` — per Decision 5/7, exactly as the
  plan specifies. **Deliberately does not import `roadnet.rn4` at all** — the absence of that
  import is itself the scope guard against ever attempting the unconfirmed type-to-geometry join,
  and `test_roadnet_rn4.py::test_ingested_road_features_never_carry_a_subtype` pins the observable
  consequence. Orientation is computed once at build time from the route's *own* first direction
  vector (`math.atan2(dz, dx)`, matching `geometry.bearing_deg`'s convention) and stored in
  `tags_json["orientation_deg"]` — the plan's stated fallback for "storing per-point direction
  vectors on the feature row is awkward" (`StoredFeature` has no such field, and adding one is a
  schema change out of Stage 2's scope). A route with any point outside the region bbox keeps its
  full, untruncated geometry and is flagged `tags_json["clipped"] = true`, per the plan's "never
  silently truncated."
- `world-model/src/build/pipeline.py` — `build_region` gained an optional `routes_path: Path |
  None = None` parameter. If given and the file exists, `ingest_roadnet` runs and its features/
  stats are folded into `BuildReport` (`roadnet_stats`); otherwise `BuildReport.roadnet_skipped =
  True` and no roadnet features are inserted — a fresh checkout without the 2.25 GB file staged
  degrades to "absence reported as absence," not a crash, consistent with `describe_position`'s
  rule 3.
- `world-model/src/query/describe.py` — two small changes: (1) `_road_info`'s tag lookup renamed
  from the Stage 1 placeholder key `"computed_bearing_deg"` to `"orientation_deg"`, matching what
  `ingest_roadnet.py` now actually populates (OSM roads still don't set this tag, so
  `nearest_road_osm.orientation_deg` stays `None`, which is correct — OSM ingest doesn't compute
  road bearings); (2) the module docstring's "Stage 1 status" note updated to reflect that
  `nearest_road` is now wired in. `nearest_road`/`nearest_road_osm`'s split via
  `nearest_feature`'s `provenance_geometry` filter (built in Stage 1) needed no changes — it
  already discriminates on `provenance["geometry"]`, which `ingest_roadnet.py`'s `"dcs"` value
  satisfies automatically.
- `world-model/tools/build_world_model.py` — added `--routes` (defaulting to
  `data/raw/dcs/syria/roads/Syria.routes` for `latakia-20km`) and printing of `roadnet_stats`/
  `roadnet_skipped` in the CLI's summary output.
- `world-model/pyproject.toml` — added `"roadnet"` to `known-first-party` (the one item the plan's
  Stage 1 note flagged as deferred until this package existed).

### Tests Added
- `tests/test_roadnet_container.py` — header parse (real class names `landscape4::lRoutesFile`/
  `landscape4::lRoadNetwork`, real header int-list `[2, 48, ...]`, and the real, literal
  `Syria.routes` byte-93 data-start offset reproduced from the confirmed 59-byte header), wrong
  class name raises, truncated buffer raises, `read_point_block` well-formed/N-past-end/negative-N,
  and — the most important one — **`test_find_next_point_block_resyncs_past_garbage`**: a
  well-formed point block (4 real literal position triples from the byte-decode research note)
  preceded by a region of plausible-looking garbage (a small int32 that could pass as a count, an
  out-of-envelope float64 triple, sentinel-looking negative int32s, unaligned stray bytes),
  asserting `find_next_point_block` lands exactly on the real block's offset — proving the resync
  actually *recovers* sync, not just that it works on already-aligned input.
- `tests/test_roadnet_routes.py` — a two-route synthetic fixture (real literal position triples
  and a real literal unit direction vector from the research note, separated by a short
  deliberately-malformed "trailer gap" that is not shaped like a valid point block) asserting:
  exact decoded positions, unit-magnitude direction vectors (tolerance matches
  `routes.py`'s own `_UNIT_MAGNITUDE_TOLERANCE`, since the note's literal direction value is
  rounded to 3 decimals, not bit-exact), correct `route_index`/`byte_offset`, `bbox` filtering
  actually filters what's yielded, walk stats count both routes and exactly one resync event (the
  trailer-gap skip), and a structural guard that `iter_routes` returns a real generator.
- `tests/test_roadnet_rn4.py` — string table + topology row parse against a synthetic fixture
  built from real, literal Damascus.rn4 values reproduced by inspecting the local file directly
  this session (`field_a=5`, `string_count=7`, the 7-entry string table, the real first data row,
  a real row with `column[6]=3` for type-index diversity, and the real sentinel/terminator row);
  asserts `iter_topology_rows` stops before yielding the sentinel, `type_name_for_row` resolves
  columns 0 and 3 correctly and returns `None` for an out-of-range index; plus the scope-guard
  test the plan calls for, `test_ingested_road_features_never_carry_a_subtype`, which runs
  `build.ingest_roadnet` against a tiny synthetic `.routes` file and asserts every emitted
  `StoredFeature` has `subtype=None`/`name=None` even though this same test file just proved
  `.rn4` type names are real and resolvable — pinning that the two facts never get joined.

### Checks
- `ruff format --check world-model/src world-model/tests`: pass (51 files)
- `ruff check world-model/src world-model/tests`: pass, 0 findings (the canonical command per
  `world-model/CLAUDE.md`; `tools/` was also checked individually and shows only the same
  pre-existing EXE001/I001 findings on files this session didn't touch, confirmed against the
  unmodified baseline — see Notable Discoveries)
- `mypy --strict world-model/src world-model/tests`: pass (51 source files)
- `pytest world-model/tests -q`: pass (118 passed, up from 96 at the end of Stage 1)

### Rung-by-rung validation (real local files)

**Rung 1 (`container.py` + `rn4.py` vs. `Damascus.rn4`/`Incirlik.rn4`).** Reproduced by direct
inspection of the real local files this session: Damascus string table (7 entries,
`taxiway_24m, ..., runway_65m`) and topology table (**79 data rows**, sentinel row
`(55, 1, 75, 0, 3, 27, 45, 80)`, column 6 distribution `{0: 71, 3: 8}` resolving to
`taxiway_24m`/`taxiway_52m`); Incirlik string table (8 entries) and topology table (**132 data
rows**, sentinel `(50, 1, 128, 0, 3, 73, 68, 130)`, column 6 `{0: 128, 3: 4}`). Both exactly match
the plan's expected row counts (79/132 + sentinel).

**Rung 2 (`routes.py` vs. `Syria.routes.head50m`).** Reproduced: route 1 decodes at the confirmed
byte-93 data-start offset with `N=343`, closing to within 3.0 m of its own start point (a closed
loop, matching the research note); the first 16 consecutive routes walk cleanly via scan-forward
resync with the mandatory first/middle/last pre-filter (16 blocks over ~450 KB in 0.04 s;
without the pre-filter, an earlier attempt using only the pre-filter's 3-point check *without*
the mandatory full-N validation produced false-positive matches inside the trailer within a few
blocks — confirming the plan's warning that the full validation, not just the pre-filter, is what
makes the resync trustworthy, not merely fast).

**Rung 3 (full-file walk vs. the real 2.25 GB `Syria.routes`, then the real store rebuild).** Run
twice, in agreement both times:

- **Gate — PASSED.** **131 routes intersect the Latakia bbox** (`(34934.892, 54934.892,
  -4314.924, 15685.076)`, the region's stored centre/half-extent from `build/region.py`) — well
  above zero, so the escalation path in the plan was not triggered.
- **Coverage check.** Walked **14,861 routes** across the whole file, vs. the header's speculated
  `11464` (byte ~63, confirmed as a literal `int32` in the real header this session). The walked
  count is **~30% higher**, not lower or approximately equal — this is reported as a genuine,
  unresolved finding, not glossed over: it *weakens* rather than confirms the byte-decode note's
  speculation that this header field is "total route count." Two explanations are both plausible
  and neither was confirmed this session: (a) the file genuinely contains many short segments
  (several of the walked blocks were N=38-65 points, plausible for taxiway stubs/short spurs, not
  obviously spurious) and the header field means something else entirely; or (b) some of the
  14,861 are false-positive resync matches inside trailer noise that happened to pass the
  pre-filter and full validation by chance. `sync_loss_events=302` (~2% of matched blocks) is the
  parser's own signal that *some* anomaly rate is real, but 302 is far short of explaining a
  ~3,400-route gap from the header figure, so explanation (a) is more likely to dominate but this
  is not proven. Left as an open question for whoever next touches `.rn4`'s header fields.
- **`bytes_covered = 2,249,737,185`** of the file's `2,251,462,776` bytes — **99.92%** walked
  before the walker ran out of plausible blocks near end-of-file, consistent with the
  byte-decode note's separately-flagged, still-unexplained ~2.3 MB header/actual-size
  discrepancy (a similar-magnitude, not identical, quantity) rather than evidence of a parser
  failure partway through.
- **Wall time**: standalone walk (parser only, with per-route Python-level progress printing)
  measured at **1,033.7 s (~17.2 min)**. This is the honest, unoptimized number for a pure-Python
  byte-by-byte scan-forward walk over 2.25 GB with the mandatory pre-filter — not yet Stage 5's
  formal performance measurement (which the plan reserves for peak-memory profiling and a clean,
  non-instrumented run), but the first real data point for it. The full store rebuild (towns +
  beacons + OSM + this same roadnet walk) took the same order of magnitude, confirming the
  roadnet walk dominates total build time by roughly two orders of magnitude over every other
  ingest stage combined (Stage 1's full OSM/towns/beacons build measured well under 1 second).
- **Final rebuilt store** (`data/world-model/latakia-20km.sqlite`) feature counts by kind:
  `airfield=1, named_place=108, navaid=8, road=3267 (3136 OSM + 131 DCS), runway=2, settlement=338,
  water=117`. The new DCS road count (131) is smaller than the OSM road count (3136) because OSM
  ways are typically split into many short segments per real road while `.routes` polylines are
  whole routes — a shape difference, not a coverage gap; a `describe_position` spot check (below)
  confirms the DCS layer answers correctly where it has data.

### `describe_position` spot check (real rebuilt store)
At the OSLK ARP (`--latlon 35.40109 35.94868`): `nearest_road` (DCS) now returns
`distance_m=256.0, orientation_deg=184.65, subtype=null, name=null, provenance="dcs",
position_uncertainty_m=0.0` — correctly non-null, correctly null `subtype`/`name`, and an
orientation plausible for a road/taxiway near a runway whose own axis bearing is ~0.31°/180.31°
(the ILS pair's derived bearing from Stage 1). `nearest_road_osm` is unchanged from Stage 1
(136.2 m, `orientation_deg=null` since OSM ingest never computes one) — the two layers answer
independently, exactly as rule 2 requires, and their disagreement (256.0 m DCS vs. 136.2 m OSM,
different nearest roads entirely) is visible in the output rather than hidden.

### Notable Discoveries
- **The pre-filter-only shortcut is not safe; full N-point validation after the pre-filter is
  load-bearing, not redundant.** An early manual test of the resync technique that accepted a
  candidate block after only the first/middle/last pre-filter (skipping the full validation)
  produced false-positive matches within a handful of blocks on the real 50 MB sample — the
  research note's own recommended design (pre-filter *then* full validate, never pre-filter
  *instead of* full validate) turned out to matter for correctness, not just performance, once
  tested against real trailer bytes. `find_next_point_block` implements the two-stage version.
- **Route N counts below the production default `min_n=5` are real** (route 2's fixture and
  several real short segments observed during the full walk, e.g. N=38). `find_next_point_block`
  and `read_point_block` both expose `min_n`/no built-in floor respectively so tests can exercise
  smaller synthetic blocks without weakening the production default.
- **The header's speculated `11464` "total route count" field does not match the walked total**
  (14,861 vs. 11,464, walked count higher) — see the coverage-check writeup above. This is a real,
  reported discrepancy, not resolved this session; flagged for whoever next works on `.rn4`/
  `.routes` header semantics.
- **`extract.py`, `tools/extract_roadnet_region.py`, `tools/inspect_roadnet.py`** — the first was
  built (tested only indirectly, via the module's own internal consistency — no dedicated
  `test_roadnet_extract.py` was written, since the plan's "Tests to write" list doesn't name one
  and `ingest_roadnet.py` doesn't depend on it); the latter two CLI tools were not built this
  session. Flagged as a deliberate scope trim against this task's explicit ask list, not an
  oversight — cheap to add later since `extract.py`'s `write_region_extract`/`read_region_extract`
  already do the real work.

---

### Implementation Summary — Stage 3 (DCS probe: elevation + surface_type only)

Built the full code path for the elevation/surface-type probe grid (parser, ingest, pipeline
wiring, CLI wiring, SRTM-delta-as-metadata-stats), and staged the live-probe artifacts
(`terrain_probe_{smoke,500,full}.lua`, a WSL collector script). **This stage could not be
finished this session** — `land.getSurfaceType` has never been called against this install, and
running any of the three probe rungs requires a live DCS mission on the Windows machine, which
this agent has no way to trigger. The smoke-test rung (121 points) and its collector script are
staged in `win-mac-sync/run-wsl/`, ready for the user to run; see "Handoff — what needs to happen
next" below. No `.sqlite` rebuild with real elevation/surface_type data happened this session;
`describe_position`'s `elevation`/`surface_type` fields remain `null` against the real Latakia
store until the user runs a rung and the result is ingested.

### Files Changed / Added
- `world-model/src/elevation/dcs_grid.py` — added `DcsTerrainSample` (`name`, `x`, `z`,
  `height_m`, `surface_type`) and `parse_terrain_probe_output`, parsing the combined
  `terrain_probe_*.lua` JSON-lines format (`height_m` + `surface_type` per point, both raising
  `ValueError` on `null` rather than silently dropping a failed point). M4's `DcsElevationSample`/
  `parse_probe_output` are untouched — this is an addition, not a replacement, since M4's own
  fixture/tests still reference the original single-field format.
- `world-model/src/build/ingest_probe.py` — new module, `ingest_probe(probe_output_path, theatre,
  origin_x, origin_z, spacing_m, n_rows, n_cols, source_id, srtm_tile=None) -> (ElevationGrid,
  SurfaceGrid, ProbeIngestStats)`. Parses point names as `r{row}c{col}` (`_parse_row_col`, raises
  on a name that doesn't match or decodes outside the grid) so **any rung's output — smoke, 500,
  or full — places its points into the correct cell of the same grid coordinate system**; a
  missing cell stays `None` (`store.writer.insert_grid` already skips `None` cells, so a
  smoke-test-only run yields a real, if sparse, queryable grid, not a placeholder or an error).
  SRTM delta is computed only as `ElevationGrid.stats["srtm"]` (mean/median/stddev/min/max delta,
  points compared vs. skipped) via `elevation.dem.SrtmTile.height_at` + `coordinates.dcs_to_wgs84`
  — per the checklist's explicit "SRTM delta as metadata stats only (not stored samples)", no
  SRTM-sourced `grid`/`grid_sample` rows are ever created. `stats["srtm"]` is `None` if no
  `srtm_tile` is supplied. `SurfaceGrid.stats["counts"]` holds a label->count census
  (`LAND`/`SHALLOW_WATER`/`WATER`/`ROAD`/`RUNWAY`, or `UNKNOWN_<n>` for an enum value outside the
  documented range — never silently coerced into a known label).
- `world-model/src/build/pipeline.py` — added `probe_grid_for_region(region, spacing_m=500.0) ->
  (origin_x, origin_z, spacing_m, n_rows, n_cols)`, deriving the grid from a `RegionDefinition`
  (south-west-corner origin, `n = round(2*half_extent/spacing) + 1` — 41 for Latakia's 10,000m
  half-extent at 500m spacing, matching the checklist's locked 41x41/1,681 decision exactly).
  `build_region` gained optional `probe_output_path`/`srtm_tile_path` parameters; if
  `probe_output_path` is given and exists, `ingest_probe` runs and both grids are inserted via
  `store.writer.insert_grid`, with results folded into `BuildReport.probe_stats`; otherwise
  `BuildReport.probe_skipped = True` and no grid is inserted — same "absence reported as absence"
  pattern Stage 2 established for `routes_path`.
- `world-model/src/query/describe.py` — **no logic change**, docstring only. `elevation`/
  `surface_type` already read live through `store.reader.sample_grid` (bilinear for elevation,
  nearest-cell for the categorical surface grid) since Stage 1 — they were `null` at Stage 1/2
  purely because no `grid`/`grid_sample` rows existed yet, not because of a special case in this
  module. Updated the module docstring to state this explicitly (previously implied Stage 3 would
  need code changes here; it does not) and to note `elevation.external_m`/`delta_m` stay always
  `None` — the SRTM comparison lives in grid metadata (`ingest_probe`), never as a per-point
  lookup this function performs.
- `world-model/tools/build_world_model.py` — added `--probe-output`/`--srtm-tile` CLI args
  (both optional, both passed through to `build_region`), and printing of `probe_stats`/
  `probe_skipped` in the summary output, mirroring the existing `--routes` pattern.
- `world-model/tools/dcs-mission-probe/terrain_probe_{smoke,500,full}.lua` — new Lua mission
  probes, one per incremental-ladder rung (121 / 441 / 1,681 points), each a subset of the same
  41x41 grid (`probe_grid_for_region`'s coordinate system, computed offline — no coordinate
  transform needed since the grid is already DCS-native x/z). Every point name is `r{row}c{col}`
  into that shared grid, so `ingest_probe` can place any rung's real output correctly regardless
  of which rung produced it. Both `land.getHeight` and `land.getSurfaceType` calls are
  `pcall`-wrapped per point (`getSurfaceType` since it has never been called against this
  install, documented-only, Hoggit enum `LAND=1, SHALLOW_WATER=2, WATER=3, ROAD=4, RUNWAY=5`, per
  plan.md Finding C — the exact status `getHeight` held before M4 Stage 1).
  **Correction (2026-09-04, Stage 3 review):** this entry originally claimed these scripts
  "mirror `elevation_probe.lua`'s (M4) proven structure exactly: `pcall`-wrapped calls,
  append-mode `io.write`". That was wrong on two counts, caught in review: (1) `elevation_probe.lua`
  itself does not do append-mode/chunked writes — it opens the output file once in `"w"` mode and
  runs a single blocking `for` loop over all its points, and (2) the scripts as first written
  copied that exact single-blocking-loop shape, not the checklist's/Finding E's mandated
  `timer.scheduleFunction` chunking + true append-mode `io.write` ("never one giant loop holding
  results in memory"). All three scripts were rewritten to actually implement chunking: `CHUNK_SIZE`
  (20) points processed per `timer.scheduleFunction` tick, each chunk appended via
  `io.open(..., "a")` after one initial `"w"`-mode truncate, self-rescheduling until every point
  in the rung is done. This did not require a new live DCS round-trip — the three rungs had
  already run successfully (see below) and reproducing their real output was not needed, since the
  fix changes *how* the calls are paced, not what they compute; only the JSON output shape is
  unchanged and was not expected to (and did not need to) differ.
- `world-model/tools/wsl/collect_terrain_probe_log.sh` — new WSL collector script, mirrors
  `collect_elevation_log.sh` exactly (same `DCS_SAVED_GAMES_PATH` env-var contract, same
  timestamped copy into `win-mac-sync/wsl-output/`), pointed at `terrain_probe_output.jsonl`.
  Every rung's `.lua` script writes to the same output filename, so this must be run once per
  rung (collect before running the next one).
- `world-model/tools/dcs-mission-probe/README.md` — documented the three new scripts, the
  incremental-ladder requirement, and the `getSurfaceType`-never-called-before caveat.
- Test additions (see below): `tests/test_terrain_probe.py`, `tests/test_ingest_probe.py`,
  `tests/test_pipeline_probe_grid.py`; `tests/test_describe_position.py` extended with two new
  tests plus a new grid-bearing fixture helper (existing tests untouched).

### Tests Added
- `tests/test_terrain_probe.py` — `parse_terrain_probe_output` against a **synthetic** JSON-lines
  fixture (explicitly documented as synthetic, not a real probe capture — no real
  `terrain_probe_*.lua` output exists yet, since `land.getSurfaceType` has never run against this
  install). Pins the format contract only (5-field shape, `height_m`/`surface_type` null ->
  `ValueError`, blank-line skipping) — not a claim about real DCS terrain, per the module
  docstring's explicit distinction from `test_dcs_grid.py`'s M4 real-data fixture.
- `tests/test_ingest_probe.py` — `ingest_probe` against a small synthetic 2x2/3x3 grid and a
  tiny uniform-value synthetic `SrtmTile` (every sample the same value, so the expected delta for
  every point is exactly `height_m - tile_value`, independent of bilinear-interpolation position
  — keeps the numbers hand-verifiable without a real `.hgt` tile; only the tile's *sample values*
  are synthetic, its `sw_lat`/`sw_lon`/`span_deg` cover the real lat/lon of the test's DCS points
  via a real `coordinates.dcs_to_wgs84` call). Covers: row/col placement, missing cells stay
  `None` (partial-grid case), surface-type label counts, bad/out-of-range point names raise,
  `srtm_tile=None` yields `stats["srtm"] is None`, SRTM delta stats computed correctly, and a
  point outside the tile's coverage is counted as skipped rather than dropped or crashing.
- `tests/test_pipeline_probe_grid.py` — `probe_grid_for_region` against the real
  `latakia-20km` `RegionDefinition`: pins the exact 41x41/500m/1,681-point outcome the checklist
  locks, confirms the origin is the region's south-west corner (round-trips to the north-east
  corner via `origin + (n-1)*spacing`), and checks a custom `spacing_m` still derives correctly.
- `tests/test_describe_position.py` — added `_fixture_conn_with_grid` (the existing ARP fixture
  plus a small synthetic 3x3 elevation/surface_type grid centred exactly on the ARP point, so
  `sample_grid`'s bilinear/nearest-cell lookup resolves to one known cell rather than an
  interpolated blend) and two new tests:
  `test_describe_position_reads_elevation_and_surface_type_from_a_built_grid` (confirms the
  store->`sample_grid`->`describe_position` wiring actually works end to end, and that
  `elevation.external_m`/`delta_m` stay `None`) and
  `test_describe_position_grid_absent_still_reports_null` (confirms a store with no grid rows —
  the Stage 1/2 state — still degrades to explicit `None`, i.e. Stage 3 changed nothing for that
  case). Existing tests in this file were not modified.

### Checks
- `ruff format --check world-model/src world-model/tests`: pass (after `ruff format` fixed 3
  files' formatting — long import line in `pipeline.py`, two single-item lists in
  `test_ingest_probe.py`)
- `ruff check world-model/src world-model/tests`: pass, 0 findings in touched/new files.
  `world-model/tools/build_world_model.py` individually checked — clean except the same
  pre-existing repo-wide EXE001 non-executable-shebang convention every other `tools/*.py` script
  already carries (confirmed against the unmodified baseline, per M5's recurring
  Notable-Discoveries note on this).
- `mypy --strict world-model/src world-model/tests`: pass (55 source files)
- `pytest world-model/tests -q`: pass (136 passed, up from 118 at the end of Stage 2)

### Handoff — what needs to happen next (this stage is not complete)

This session cannot run DCS — there is no way to trigger a live mission on the Windows machine
from here. The code side of Stage 3 is finished and tested against synthetic fixtures, but the
actual elevation/surface_type data, the `getSurfaceType`-never-called-before verification, and
the incremental-ladder timing/cost checks all require the user to run something in DCS.

**Staged and ready, rung 1 of 3 (smoke test):**
- `win-mac-sync/run-wsl/terrain_probe_smoke.lua` — the 121-point smoke-test probe script,
  synced via Dropbox.
- `win-mac-sync/run-wsl/collect_terrain_probe_log.sh` — the WSL collector script for its output.

**What the user needs to do:**
1. On the Windows DCS machine: uncomment the `io`/`lfs` `sanitizeModule` lines in
   `Scripts/MissionScripting.lua` (same probe-only, user-authorized edit M4 used — redo it if it
   was reverted after M4).
2. Copy `win-mac-sync/run-wsl/terrain_probe_smoke.lua` to a location DCS can read (e.g. alongside
   a test mission), build a throwaway Syria-terrain mission with a `TIME MORE 5` -> `DO SCRIPT
   FILE` trigger pointing at it, run the mission ~10-20 seconds, then exit. Watch for any hang or
   unresponsiveness — 121 `land.getSurfaceType` calls have never been tried on this install, and
   an actual ceiling (Finding E's open question) would be new, useful evidence either way.
3. In WSL bash on the Windows machine, with `DCS_SAVED_GAMES_PATH` set, run
   `win-mac-sync/run-wsl/collect_terrain_probe_log.sh` to copy `terrain_probe_output.jsonl` into
   `win-mac-sync/wsl-output/`.
4. Let it sync back to the Mac (Dropbox), then tell me to resume.

**Once rung 1's real output lands**, this session (or a resumed one) should: move the output file
into `world-model/data/raw/dcs/<date>/`, verify point count (121) and no nulls, run
`build.ingest_probe` against it standalone to sanity-check `land.getSurfaceType`'s actual return
values are within the documented `1-5` enum (the checklist's explicit caution — treat this
function with the same skepticism M4 gave `land.getHeight` before its own Stage 1), replace this
test file's synthetic fixture with a real one per `CONVENTIONS.md`, then proceed to rung 2 (~500,
`terrain_probe_500.lua`) and rung 3 (full 1,681, `terrain_probe_full.lua`) the same way — each
rung's real output sanity-checked before scaling up, per the checklist's "stop and reassess if any
rung shows non-linear cost." Only after the full 1,681-point rung succeeds should the real
Latakia `.sqlite` be rebuilt with `--probe-output`/`--srtm-tile`, and the
`describe_position`/SRTM-delta/coverage numbers this task asked for (smoke/500/full point counts,
`getSurfaceType` surprises, final grid coverage, SRTM delta stats, real spot-checks) be reported.

### Notable Discoveries
- **`query/describe.py` needed zero logic changes for Stage 3.** Stage 1 already wired
  `elevation`/`surface_type` through `store.reader.sample_grid`, which was designed from the start
  to return `None` when no grid exists — Stage 3's entire "wire it in" scope collapsed to "make a
  `grid`/`grid_sample` row-producing ingest module exist," confirming the Stage 1 store design
  anticipated this correctly. Worth remembering for any future milestone: check whether the query
  layer already supports a not-yet-populated data source before assuming query-side work is
  needed.
- **The incremental ladder's real value, in this design, is partial-grid safety, not just
  cost control.** Because every rung's point names are `r{row}c{col}` into one shared grid
  coordinate system, `ingest_probe` was written so a smoke-test-only run already produces a real
  (if sparse) queryable grid rather than throwaway data replaced wholesale by later rungs — this
  wasn't explicitly required by the checklist but falls out naturally from the grid-index naming
  choice and seemed worth doing since it costs nothing.

---

### Implementation Summary — Stage 3 completion (live DCS round-trip finished)

The live round-trip flagged as outstanding above is now complete. All three rungs
(smoke/121, ~500/441, full/1,681) ran on the Windows DCS machine, were synced back via
`win-mac-sync/`, ingested, and sanity-checked in turn; the real Latakia `.sqlite` was rebuilt with
the full probe grid wired in. Full detail, per-rung enum distributions, determinism cross-checks,
and `describe_position` spot-checks are in `world-model/research/2026-09-04-m5-stage3-smoke-rung.md`
(one running note covering all three rungs plus the final rebuild, despite its filename naming
only rung 1 -- kept as a single note rather than three, since each rung's findings build directly
on the last).

### Files Changed (this completion pass)
- `world-model/tests/test_terrain_probe.py` — synthetic fixture replaced with a real 7-line
  subset of the actual smoke-rung capture (per `CONVENTIONS.md`'s real-data-fixture rule), plus a
  new test pinning that all observed `surface_type` values fall inside the documented `1..5`
  enum.
- `world-model/tests/test_ingest_probe.py` — docstring updated to stop claiming "no real probe
  output exists yet" (stale after the live rungs landed); still uses a synthetic grid
  deliberately, since it's a wiring test, not a DCS-terrain claim.
- `world-model/research/2026-09-04-m5-stage3-smoke-rung.md` — grew across three sessions/rungs
  into the complete record: rung 1 (smoke), rung 2 (500), rung 3 (full), the SRTM-tile-gap
  finding, and the final real-store rebuild + spot-checks.
- No `src/` changes were needed in this completion pass — `ingest_probe`/`parse_terrain_probe_output`
  handled all three real files correctly against the code already written and tested with
  synthetic fixtures in the prior pass.

### Real data results

**Per-rung sanity (all three point counts exactly as requested, 0 nulls, 0 duplicate names):**

| rung | points | LAND | SHALLOW_WATER | WATER | ROAD | RUNWAY |
|---|---|---|---|---|---|---|
| smoke | 121 | 85 (70.2%) | 0 | 34 (28.1%) | 1 (0.8%) | 1 (0.8%) |
| 500 | 441 | 324 (73.5%) | 0 | 112 (25.4%) | 4 (0.9%) | 1 (0.2%) |
| full | 1,681 | 1,236 (73.5%) | 0 | 412 (24.5%) | 29 (1.7%) | 4 (0.2%) |

**`getSurfaceType` surprises:** none in the sense of invalid/out-of-enum values (all three rungs,
100% of points, land inside the documented `1..5` range) or nondeterminism (three-way
cross-check: every point re-sampled across rungs returned bit-identical `height_m`/
`surface_type`). One real, spatially-explained oddity worth flagging: several `WATER` cells carry
non-zero elevation (up to ~180m, inland, away from the coast) rather than sea-level-only —
plausible as river/reservoir features (the plan's Finding B independently notes the Nahr
al-Kabir river crosses this region) rather than a bug, not independently confirmed against a
water-body reference this session. `SHALLOW_WATER` (enum 2) was never observed at any rung's
sampling density — a real absence in this grid's coverage at 500m spacing, not evidence the DCS
terrain never produces it.

**Final store elevation/surface_type coverage:** both grids are **100% populated — 1,681/1,681
cells** (verified directly against `grid_sample` row counts, not just the ingest report), since
the full rung supplied every point the earlier partial rungs would have left `None`.

**SRTM delta stats: not computed this session.** `data/raw/dem/` holds only the Gemerek/M4 tile
(`N39E036.hgt`); the Latakia envelope needs a different tile (`N35E035.hgt` or whichever
tile(s) actually cover ~35.0-35.5N/35.85-35.95E), which isn't present. An automated fetch attempt
was blocked by sandbox network policy, consistent with M4's own precedent of the user manually
fetching the DEM tile. `elevation.stats["srtm"]` is `null` in the real store — an honest absence,
not a fabricated number. The `ingest_probe`/`ElevationGrid.stats` SRTM code path is implemented
and tested against a synthetic tile (`test_ingest_probe.py`); rerunning
`build_world_model.py --srtm-tile <path>` once a covering tile is available is a cheap follow-up,
no code changes needed.

**`describe_position` spot-checks against the real rebuilt store:**
- OSLK ARP: `elevation.dcs_m=28.48m`, `surface_type.value="LAND"`; `nearest_road` (DCS) 256.0m,
  `nearest_road_osm` 136.2m — disagreeing on which road is nearest, visibly reported per rule 2.
- Coastal grid vertex (`r0c0`): `elevation.dcs_m=0.0`, `surface_type.value="WATER"` — exact match
  to the raw probe capture at this exact grid point.
- Runway grid vertex (`r12c20`): `elevation.dcs_m=27.02m`, `surface_type.value="RUNWAY"`,
  `nearest_airfield` 805.7m away (`derivation="runway_axis_midpoint"`) — consistent with the
  cross-subsystem observation first noted at the smoke rung, now confirmed through the full query
  stack.
- Far outside the region (`x=0, z=0`): `elevation.dcs_m=null`, `surface_type.value=null`,
  `nearest_settlement=null` — explicit absence, not a plausible-looking wrong answer.

### Checks (this completion pass)
- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass, 0 findings
- `mypy --strict world-model/src world-model/tests`: pass (55 source files)
- `pytest world-model/tests -q`: pass (137 passed, up from 136 after the code-only pass)

### Notable Discoveries (this completion pass)
- **The incremental ladder's determinism cross-check turned out to be a real, useful side
  effect, not just a formality.** Because every rung samples a subset of the same fixed grid
  coordinates, each later rung re-queries every earlier rung's points — three independent live
  DCS mission invocations returned bit-identical `land.getHeight`/`land.getSurfaceType` results
  for every overlapping point. This wasn't a planned test, but it's a genuine reproducibility
  finding worth having for a function (`getSurfaceType`) that had never been exercised before this
  session.
- **`getSurfaceType`'s `ROAD`/`RUNWAY` cell counts scale roughly linearly with grid density**
  (1/4/29 and 1/1/4 don't look linear at a glance, but the road/runway *strips* are narrow enough
  relative to 500m spacing that hitting more of them as density increases is expected aliasing,
  not a sign of anything wrong — consistent with the plan's own Finding C caveat that this
  function is "a good water mask and a poor road geometry source" at this spacing).
- **No DEM tile for Latakia is a real, not-yet-closed gap** distinct from anything M1-M4
  established — M4's Gemerek tile doesn't help here, and this is the first M5 stage to actually
  need one. Left for the user to fetch (same manual viewfinderpanoramas.org process M4 used)
  rather than attempted via an unverified automated download this session.

---

### Implementation Summary — Stage 3 review fix (timer.scheduleFunction chunking)

Addressed the reviewer's one required fix (`plans/m5-first-persistent-model/review.md`): the
three `terrain_probe_*.lua` scripts used a single blocking loop (`io.open(..., "w")` once, one
`for` loop, close at the end) instead of the checklist's/Finding E's mandated
`timer.scheduleFunction` self-rescheduling chunking with append-mode `io.write`. The review also
noted `implementation.md` had misdescribed this as "append-mode `io.write`" when it wasn't, and
that the "mirrors M4's proven pattern" justification was itself inaccurate — `elevation_probe.lua`
(M4) never implemented chunking either, despite Finding E's text describing that pattern.

### Files Changed
- `world-model/tools/dcs-mission-probe/terrain_probe_{smoke,500,full}.lua` — rewritten execution
  logic (point tables unchanged, byte-for-byte identical to before). Now: one initial
  `io.open(..., "w")` to truncate/create the file, then `timer.scheduleFunction`-driven
  `processChunk()` processes `CHUNK_SIZE=20` points per tick, appending via `io.open(..., "a")`
  each tick, self-rescheduling (`return timer.getTime() + 0.1`) until every point in the rung is
  processed, then returning `nil` to stop and printing a completion message. Verified with
  `luac -p` (syntax-only parse, no DCS globals needed) against all three files plus the two
  pre-existing scripts (`elevation_probe.lua`, `coord_probe.lua`) as a baseline — all parse clean.
- `world-model/tools/dcs-mission-probe/README.md` — corrected the `terrain_probe_*.lua` entry to
  describe the actual chunking mechanism, and added an explicit note that `elevation_probe.lua`
  does *not* chunk (so a future reader doesn't assume it's a template to copy for a larger probe).
- `plans/m5-first-persistent-model/implementation.md` — corrected the Stage 3 "Files Changed"
  entry for these scripts in place (see the "Correction (2026-09-04, Stage 3 review)" paragraph
  above it), rather than silently rewriting history.
- `world-model/tests/test_terrain_probe.py` — added (optional refinement, reviewer's suggestion)
  `test_parse_terrain_probe_output_is_deterministic_across_live_rungs`, pinning the
  smoke-rung-vs-full-rung bit-identical-values finding as an actual assertion using a second
  literal fixture (`_FULL_RUNG_FIXTURE_LINES`) grep'd directly from the real full-rung capture —
  confirmed byte-identical to the existing smoke-rung fixture, as the research note already
  claimed.

### No live DCS round-trip needed
The fix changes *how* the probe paces its `land.*` calls (chunked/scheduled vs. one blocking
loop), not what it computes per point — the JSON output shape and the values returned by
`land.getHeight`/`land.getSurfaceType` for a given `(x, z)` are unaffected. All three rungs had
already run successfully and their real captures are already ingested into the rebuilt store;
re-running them was not needed to validate this fix. `luac -p` syntax verification stood in for a
live re-run, appropriate for a control-flow-only change with no execution semantics DCS's Lua
runtime would evaluate differently.

### Optional refinement not done: wall-clock timing for the Lua rungs
No timestamps were recorded during the three live mission runs (unlike Stage 2's `.routes` walk,
which was timed with an explicit `time` invocation around a standalone script run). Retroactively
fabricating a number would violate the project's rule against encoding unverified claims as fact.
Left as a genuine gap for a future probe run to close with an in-mission timestamp or DCS log
timing, rather than invented here.

### Checks
- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass, 0 findings
- `mypy --strict world-model/src world-model/tests`: pass (55 source files)
- `pytest world-model/tests -q`: pass (138 passed, up from 137)
- `luac -p` (Lua syntax check, no DCS runtime needed): all 5 scripts in
  `tools/dcs-mission-probe/` parse clean, including the 3 rewritten this pass.

---

### Implementation Summary — Stage 4 (validate correctness)

Found a reusable, largely-complete stub script left by a prior (accidentally killed, not-for-cause)
session, verified it matched the current `store`/`query` module signatures, ran it against the real
`latakia-20km.sqlite`, and used its output to work through every checklist bullet. Two real issues
surfaced during that run and were investigated and fixed/documented rather than silently reported
as passes — see Notable Discoveries. Deliverable is the dated research note plus one new pinnable
test; no `src/` pipeline code changed.

### Files Changed
- `world-model/tools/analyze_m5_stage4_validation.py` — completed the found stub (it was already a
  reasonable, nearly-correct starting point, not an empty placeholder). Added: a
  `_is_subnormal_point`/`_find_corrupted_dcs_road_features`/`_clean_dcs_road_polylines` layer that
  detects and excludes a corrupted DCS road feature discovered while running the script (see
  Notable Discoveries); restricted the OSM-displacement sample to DCS road vertices inside the
  region bbox (the stub's original unfiltered version produced a misleading, coverage-mismatched
  result); swapped the spot-check table's `(0, 0)` "outside coverage" point for a genuinely far
  point once `(0, 0)` turned out to be polluted by the corrupted feature; picked a well-formed DCS
  road feature for the "DCS road vertex" spot-check row instead of the first one by row order
  (which was the corrupted one). Read-only against the real store, no pipeline/store mutation, per
  `fetch_m5_stage0_census.py`'s established throwaway-script pattern.
- `world-model/tests/test_describe_position.py` — added
  `test_describe_position_control_point_latakia_arp`, the one Stage 4 checklist item that's
  pinnable in CI (needs only `tests/control_points.py`'s independent, published-ARP source and
  `describe_position`'s pure `coordinates.dcs_to_wgs84` call — no store content, so it doesn't need
  the gitignored real `.sqlite`). Asserts a tolerance band (`residual_m <=
  expected_max_residual_m`), not an exact value, per the checklist's explicit instruction. Existing
  tests in this file were not modified; module docstring extended to explain why the rest of Stage
  4 (spot-check table, airfield/cross-subsystem/displacement checks) lives in the research note and
  analysis script instead of as pinned tests — they all need the real store, which CI never has.
- `world-model/research/2026-09-04-m5-stage4-validation.md` — the dated deliverable: pass/fail
  against every checklist bullet, real computed numbers alongside the plan's expected numbers, and
  full writeups of the two findings below.

### Tests Added
- `test_describe_position_control_point_latakia_arp` — control-point tolerance-band test against
  the real OSLK ARP (`tests/control_points.py`), non-circular per M1 Finding 2 / the plan's
  repeated emphasis (independent published real-world coordinate, not DCS-derived).

### Checks
- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass, 0 findings
- `ruff check world-model/tools/analyze_m5_stage4_validation.py` (individually): clean except the
  same pre-existing repo-wide `EXE001` non-executable-shebang convention every other `tools/*.py`
  script carries
- `mypy --strict world-model/src world-model/tests`: pass (55 source files)
- `mypy --strict world-model/tools/analyze_m5_stage4_validation.py` (individually): pass
- `pytest world-model/tests -q`: pass (139 passed, up from 138)

### Notable Discoveries
- **A real, previously-unconfirmed instance of Stage 2's documented resync-false-positive risk
  exists in the live Latakia store.** Stage 2's own implementation notes flagged
  `sync_loss_events` (~2% of matched blocks during the full `.routes` walk) as an open,
  unresolved risk without proof it was ever harmless. This session found one confirmed instance
  that made it all the way into the real store: feature `id=3711`
  (`route:3311@464953201`) decodes to two subnormal-float garbage points followed by 61 points of
  exact `(0.0, 0.0)` padding, and landed inside the Latakia bbox because one garbage point's
  near-zero z coordinate happened to fall inside the bbox's z range by coincidence. Its downstream
  effect is checkable and real, not theoretical: `describe_position(conn, "Syria", 0.0, 0.0)`
  returns a misleadingly precise `nearest_road` distance of exactly `0.0 m`, sourced entirely from
  the garbage feature — the exact "plausible-wrong answer instead of an explicit null" failure mode
  Stage 4's outside-coverage gate exists to catch. **Not fixed this session** (Stage 4 is
  validation-only per the checklist); flagged for whoever next touches `roadnet`/`ingest_roadnet` —
  the fix is either tightening `find_next_point_block`'s validation or adding a
  plausibility/subnormal-value filter to `ingest_roadnet`. Scope: 1 of 131 DCS road features
  (0.76%).
  **Correction (2026-09-04, later same-day session, Debugger role): fixed.** Root cause was
  `roadnet/container.py::_triple_plausible` never rejecting denormalized/subnormal float64 values
  (finite, near-zero, so they trivially passed the wide envelope bounds) — the same filter the
  exploratory recon script already used (`2026-09-04-m5-roadnet-byte-decode.md` Session 2) but
  which never made it into the production validator. Fixed by rejecting any coordinate component
  that is nonzero but has magnitude `< 1e-6`. Full re-walk/rebuild: whole-file routes 14,861 →
  **14,833** (-28), in-region routes 131 → **130** (-1, the corrupted one), `sync_loss_events`
  302 → **220**. `describe_position(0,0)`'s `nearest_road` is no longer the bogus `0.0 m` — it now
  resolves to a real, legitimate long route (`id=3716`) at `3689.37 m`, not `null` (that route
  genuinely passes near the origin; see the correction section for why `null` was the wrong
  expectation, not the fix). The 28-route whole-file delta is evidence the resync-false-positive
  risk was not a one-off — flagged as worth a future systematic per-route audit, not fully closed
  by this fix beyond the denormalized-magnitude failure mode. Full detail, before/after table, and
  regression tests: `world-model/research/2026-09-04-m5-stage4-validation.md`'s "Correction"
  section.
- **DCS-vs-OSM road displacement is ~2 orders of magnitude tighter than the plan predicted** (median
  5.3 m / p90 47.0 m computed, vs. an expected ~1.0-1.3 km carried forward from M1's *point-object*
  placement-error figure). Investigated rather than reported at face value: an initial unfiltered
  sample (before restricting to in-bbox DCS points) got a misleading wider spread (p90 13.6 km) due
  to a real coverage-mismatch bug (DCS routes keep untruncated geometry outside the bbox;
  `ingest_osm` never fetches OSM data out there), fixed by restricting the sample to the 56,092
  DCS road vertices actually inside the region bbox. The resulting tight number is plausible, not
  a bug: M1's figure measures one hand-placed point object's absolute displacement, while DCS and
  OSM road *centerlines* are both plausibly digitized from the same class of satellite/aerial
  reference imagery, so two independent tracings of the same real road should agree far more
  closely than one point's placement error would suggest. Recorded as a genuinely more specific
  finding than the plan anticipated, not adjusted to look like it matched the prior guess.
- The airfield spot-checks (gap 1504.28 m vs. expected ~1504 m, ILS axis 2635.04 m vs. expected
  ~2635 m) landed almost exactly on the plan's own hand-worked Latakia numbers — strong independent
  confirmation that Stage 1's `ingest_beacons.py` runway-pairing/derivation logic is correct against
  the real data, not just against the plan's own worked example (which was itself derived from the
  same real data, so this isn't fully independent, but the near-exact match to a hand-computed
  figure from a different session is still a meaningful cross-check of no regression since Stage 1).

---

### Implementation Summary — Stage 5 (light perf)

Measurement-only stage, per the checklist. No production code under `src/` changed. Added one
throwaway script (`tools/measure_m5_stage5_perf.py`, following `fetch_m5_stage0_census.py`'s
pattern) with four independent subcommands (`latency`, `routes-walk`, `rebuild`, `sqlite-size`)
so the 2.25 GB `Syria.routes` walk could be measured standalone, isolated from the full rebuild,
per the checklist's explicit requirement. Full numbers and the memory-metric interpretation are
in the dated research note, `world-model/research/2026-09-04-m5-stage5-perf.md` — not repeated
in full here.

### Files Changed
- `world-model/tools/measure_m5_stage5_perf.py` — new throwaway measurement script (four
  subcommands as above). `_sample_points` reuses Stage 4's spot-check philosophy (mix of
  in-region and near/outside-boundary points) but samples 100 points with a fixed seed rather
  than hand-picking a handful, since this is a latency distribution measurement, not a
  correctness check.
- `world-model/research/2026-09-04-m5-stage5-perf.md` — the four measurements, the regression
  found and fixed mid-session (below), and the peak-memory metric explanation.

### A regression this stage caught (not a Stage 5 code change, but load-bearing for the numbers)
The first `rebuild` run omitted `--probe-output` (no default registered for `latakia-20km` in
`build_world_model.py`'s `_DEFAULT_RAW_PATHS`, unlike `--towns`/`--beacons`/`--osm-cache`/
`--routes`), which silently produced a "probe: skipped" build and **overwrote the real Stage 3/4
store, dropping its 1,681-point elevation/surface_type grid** (`grid`/`grid_sample` row counts
went to 0/0). Caught by inspecting the rebuilt store's row counts directly rather than trusting
the CLI's own summary output. Fixed by passing `--probe-output` explicitly (pointed at the
already-staged Stage 3 full-rung output,
`data/raw/dcs/2026-09-04/terrain_probe_output_full.jsonl`) in the measurement script's `rebuild`
subcommand, then re-running and re-verifying via both a direct row-count check
(`grid`=2, `grid_sample`=3,362, matching Stage 3/4 exactly) and a `describe_position` sanity
check on a real point (`elevation.dcs_m=37.1263`, `surface_type.value="LAND"`, both correctly
non-null). All four measurements reported in the research note are from this corrected,
probe-inclusive rebuild. `--srtm-tile` was left unset (no local SRTM tile for Latakia is staged
— `data/raw/dem/` only has Gemerek's M4 tile); per `build.pipeline.build_region`'s contract this
degrades to an absent SRTM-delta stat, not an error, and is an already-accepted M5 deferral, not
a gap introduced this stage.

### Measurements (full detail in the research note)
- Full rebuild wall time (region+towns+beacons+OSM+roadnet+probe grid, probe-inclusive):
  **430.9 s (~7.2 min)**.
- `.sqlite` file size: **8,982,528 bytes (8.57 MB)**.
- `describe_position` latency, 100 sampled points: **mean 89.0 ms, median 71.3 ms, p95 223.7 ms,
  p99 275.0 ms**.
- Full `.routes` walk, standalone (isolated from the rebuild): **wall time 446.3 s (~7.4 min)**;
  peak memory — **two numbers reported, not one, because they measure different things**: macOS
  "maximum resident set size" (~2.18 GB, essentially the whole file — this counts `mmap`-ed
  clean/reclaimable file-backed pages, not heap) vs. "peak memory footprint" (~22.5 MB, the
  actual-heap/dirty-memory metric) obtained via `/usr/bin/time -l` wrapping the script's own
  `resource.getrusage`-based self-report. **The streaming claim from Stage 2 holds**: peak
  footprint stays flat and low regardless of the 2.25 GB input — no accidental full-buffer
  materialization exists in `roadnet.routes.iter_routes`.

### Checks
- `ruff format --check world-model/src world-model/tests`: pass (55 files)
- `ruff check world-model/src world-model/tests`: pass, 0 findings
- `mypy --strict world-model/src world-model/tests`: pass (55 source files)
- `pytest world-model/tests -q`: pass (142 passed — unchanged from before this stage, no test
  additions expected or made since no production code changed)
- `tools/measure_m5_stage5_perf.py` individually: `ruff format`/`ruff check` clean (only the
  pre-existing, baseline `EXE001` "shebang present but file not executable" finding shared by
  every other script in `tools/`), `mypy --strict` clean.

### Notable Discoveries
- **A CLI default gap (`--probe-output` has no registered default for `latakia-20km`) is a real
  footgun for anyone re-running `build_world_model.py latakia-20km` without all optional flags**
  — it doesn't error, it silently degrades to a smaller build and can overwrite a store that had
  more data than the new build produces. Not fixed this session (out of Stage 5's "measurement,
  not optimization/code changes" scope, and the checklist's own gate for new work — "unless a
  measurement reveals something genuinely broken" — is about the *streaming claim*, not this CLI
  ergonomics gap). Flagged here for whoever next touches `build_world_model.py` or writes Stage 6's
  close-out: consider either a registered `probe_output` default (mirroring `routes`'s pattern)
  or a loud warning when a rebuild would produce fewer grid/feature rows than the store it's
  about to overwrite already has.
- **macOS's `ru_maxrss`/`/usr/bin/time -l` "maximum resident set size" is the wrong metric to
  read for "did this program's own memory use scale with input size" when the program uses
  `mmap`** — it will look identical to a genuine memory blowup for any large `mmap`+sequential-
  scan workload regardless of actual heap use. "Peak memory footprint" (also from `/usr/bin/time
  -l` on Darwin) is the metric that actually answers that question. Worth remembering for any
  future milestone (M6 ridge/valley extraction, M7 full-theatre) that profiles another `mmap`-
  based reader.
