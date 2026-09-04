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
