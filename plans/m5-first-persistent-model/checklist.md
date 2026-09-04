# M5 — Implementer checklist

Condensed from `plan.md` (1300 lines — full rationale/decision-log there; read a section only
if something here is ambiguous). All decisions closed, zero open items. Region: **Latakia**
(`latakia-20km`), centre x=41934.892 z=5685.076, half-extent 10,000 m, +0..+3km eastward offset
allowed per Stage 0 census.

## Locked decisions (do not reopen)

1. Storage: **one SQLite file** per region (`data/world-model/<theatre>.sqlite`), stdlib
   `sqlite3`, R*Tree index, geometry as JSON `[[x,z],...]` in DCS x/z metres (not WKB, not GPKG).
   QGIS access via `tools/export_geojson.py` export, not a GeoPackage writer.
2. Region: Latakia, not Gemerek (`gemerek-20km` stays registered for continuity).
3. Elevation/surface grid: 500m spacing, 41x41 = 1,681 points, reached via incremental ladder
   (100-200 → ~500 → 1,681), never jumped to.
4. **Roads: DCS-native, not live-probe.** New `src/roadnet/` package parses
   `Mods/terrains/Syria/roads/Syria.routes` (+ `.rn4` for type vocabulary) directly —
   `land.getClosestPointOnRoads`/`findPathOnRoads` are **dropped entirely**, not used.
5. Road type/subtype: **null in M5** (deferred — `.rn4` row→geometry join unconfirmed; do not
   guess it, a test pins `subtype is None`).
6. Road graph connectivity: **explicit non-goal** — do not decode `.rn4`'s adjacency section.
7. OSM roads: **kept as a separate comparison layer** (`nearest_road_osm`), not fused with DCS
   roads, no proximity-matching heuristic to fill in type/name.
8. Airfields: **in scope**, as reference points only, sourced from `beacons.lua` (NOT
   `tests/control_points.py`, NOT pydcs). No taxiways/structures/extents — explicit non-goals.
9. Acquisition: full local copy of `Syria.routes` (2,251,462,776 bytes) — already landed at
   `world-model/data/raw/dcs/syria/roadnet-samples/Syria.routes.full` (rename/move to
   `data/raw/dcs/syria/roads/Syria.routes` per plan's expected path before Stage 2 rung 3).
   `Syria.rn4` full file NOT needed — 50MB head sample + full Damascus/Incirlik airfield files
   already local are sufficient (string table + topology rows live in the header).

## Already-available raw inputs (no new probe needed)

- `world-model/research/2026-09-03-m5-nodes-lua-probe.txt` — full `towns.lua` (1,182 entries,
  **list not dict — 31 duplicate names, all real**), full `beacons.lua` (151 entries, Latakia =
  `airfield21`, 8 beacons), `nodes.lua`/`nodesMap.lua` (confirmed NOT road graphs).
- `world-model/data/raw/dcs/syria/roadnet-samples/`: `Damascus.rn4` (376KB, full),
  `Incirlik.rn4` (825KB, full), `Syria.rn4.head50m` (50MB), `Syria.routes.head50m` (50MB),
  `Syria.routes.full` (2.25GB, full).
- Byte-exact format spec: `world-model/research/2026-09-04-m5-roadnet-byte-decode.md`
  (sessions 1+2 — **the authoritative parsing reference**, has literal byte offsets/values to
  copy into test fixtures).

## Stage order (each independently checkable; do not reorder)

**Stage 0 — census, no store code.** Derive DCS-space square + lat/lon envelope, confirm 2
towns.lua entries inside (Jablah, Al Hannadi), pick eastward offset (0 to +3km), one Overpass
fetch with widened query (add `landuse`, `natural=water`, `place` way/relation). **Gate: region
must contain water + settlement polygons + named places** (Gemerek/M3 shipped empty layers —
don't repeat that). Confirm `Syria.routes` landed at correct path/size.

**Stage 1 — offline sources only, no DCS round-trip.** Build `src/geometry/` (planar primitives,
shared by build+query so bbox/distance agree exactly), `src/dcs_data/towns.py` +
`src/dcs_data/beacons.py` (regex parsers, NOT a dict — strict/raises-on-malformed, exact-count
assert: 1182 towns, 151 beacons), `src/store/` (schema below), `src/build/` (region + towns +
beacons + osm + pipeline). `describe_position` should answer named places/airfields/
runways/navaids/roads(OSM)/settlements/water; elevation+surface_type null until Stage 3.
Export GeoJSON, eyeball in QGIS.

**Stage 2 — `src/roadnet/` (DCS-native roads, still offline).** Stdlib only:
`struct`/`array`/`mmap`. Three rungs, smallest first:
1. `container.py` + `rn4.py` against `Damascus.rn4`/`Incirlik.rn4` (known expected answers:
   literal ASCII strings `taxiway_24m`/`runway_65m` etc, row counts 79/132 + sentinel).
2. `routes.py` against local `Syria.routes.head50m`: reproduce 15+ consecutive clean routes,
   route 1 N=343 closed loop near Damascus, unit-magnitude direction vectors. **Mandatory
   first/middle/last pre-filter before full N-point unpack** — naive form took 6+ CPU-min on
   this exact buffer.
3. Full-file walk against local `Syria.routes` (already copied) → Latakia extract + manifest →
   `ingest_roadnet.py`.

   **Gate:** zero routes intersecting Latakia bbox = stop and escalate (don't silently ship
   empty road layer) — decide explicitly whether to fall back to OSM-only for M5.
   **Coverage check:** compare walked route count to header's speculated `11464` (byte ~63).

**Stage 3 — DCS probe: elevation + surface_type only.** M4's proven `getHeight` loop + one
`getSurfaceType` call/point (`land.getSurfaceType`, never called on this install before — treat
like `getHeight` was pre-M4). `timer.scheduleFunction` chunking, append-mode `io.write`,
100-200pt smoke test → ~500 → full 1,681. Wire into `describe_position`; SRTM delta as metadata
stats only (not stored samples).

**Stage 4 — validate correctness.** Control-point test at Latakia ARP; R*Tree-vs-brute-force
agreement test; 6-8 point manual spot-check table (town centre, open country, road, water,
outside-coverage — confirm outside-coverage degrades to explicit nulls, not plausible-wrong
answers). Airfield spot-checks: derived point vs `control_points.py`'s in-game position (expect
~1504m gap, report don't reconcile — different reference points); ILS/PRMG/beacon-`direction`
bearing agreement (~1°); axis length vs published OSLK 17/35 (~2635m vs 2797m, expected shorter
since antenna-to-antenna not threshold-to-threshold). Cross-subsystem check: `getSurfaceType`
ROAD/RUNWAY cells vs nearest `.routes` centerline distance. DCS-vs-OSM road displacement
distribution (expect ~M1's 1.0-1.3km residual).

**Stage 5 — light perf.** Rebuild wall time, `.sqlite` size, `describe_position` latency over
~100 points. Plus: full `.routes` walk wall time + peak memory (proves streaming generator
actually streams — this is M5's only multi-GB workload).

**Stage 6 — close out.** Research note (`world-model/research/2026-09-03-m5-first-persistent-model.md`),
`world-model/CLAUDE.md` tech-stack lines (SQLite+R*Tree, roadnet format, towns/beacons sources),
ROADMAP/todo flip, full verification (`ruff format`, `ruff check`, `mypy --strict`, `pytest`).

## Schema (ordinary SQL, no extensions)

```sql
CREATE TABLE meta   (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source (id INTEGER PRIMARY KEY, name TEXT, fetched_at TEXT,
                     raw_path TEXT, attribution TEXT, notes TEXT);
CREATE TABLE region (name TEXT PRIMARY KEY, theatre TEXT, centre_x REAL, centre_z REAL,
                     half_extent_m REAL, built_at TEXT);
CREATE TABLE feature (id INTEGER PRIMARY KEY, kind TEXT, geom_type TEXT,
                      geom_json TEXT,            -- [[x, z], ...] in DCS metres
                      name TEXT, subtype TEXT, tags_json TEXT,
                      source_id INTEGER REFERENCES source(id), source_ref TEXT,
                      provenance_json TEXT,      -- {"geometry": "dcs", "name": "dcs"}
                      confidence_json TEXT,      -- {"geometry": "high", "name": "high"}
                      position_uncertainty_m REAL);
CREATE VIRTUAL TABLE feature_bbox USING rtree(id, min_x, max_x, min_z, max_z);
CREATE TABLE grid   (id INTEGER PRIMARY KEY, kind TEXT,  -- 'elevation' | 'surface_type'
                     origin_x REAL, origin_z REAL, spacing_m REAL, n_rows INT, n_cols INT,
                     source_id INTEGER REFERENCES source(id), stats_json TEXT);
CREATE TABLE grid_sample (grid_id INT, row INT, col INT, value REAL,
                          PRIMARY KEY (grid_id, row, col)) WITHOUT ROWID;
```

## `describe_position(conn, theatre, x, z)` contract

Input DCS-native x/z (lat/lon callers go through `coordinates.wgs84_to_dcs`). Returns frozen
JSON-serializable dataclass. Four rules: (1) every claim carries provenance +
`position_uncertainty_m` side by side, never collapsed; (2) DCS wins over OSM when both answer,
disagreement reported not hidden; (3) absence → explicit null, never a guess; (4) structured
data only, no prose.

Fields: `theatre`, `position`, `lat`/`lon` (derived), `elevation` (dcs_m/external_m/delta,
never blended), `surface_type` (+ `sampled_at_m` spacing), `nearest_road` (DCS, uncertainty=0,
subtype/name=null), `nearest_road_osm` (OSM, uncertainty≈1300), `nearest_settlement`,
`inside_settlement`, `nearest_water`, `named_places_within_radius`, `nearest_airfield`
(+ `derivation` field), `nearest_runway` (orientation from beacon `direction`, not computed
bearing), `navaids_within_radius`, `region`.

## Traps already found — do not rediscover

- `towns.lua`: **list, not dict** (31 duplicate names, all real places at different coords).
- `beacons.lua`: `{x, y, z}` — **middle value is elevation, not z**. `positionGeo` must NEVER
  be used to validate/position anything (circular — tests DCS against itself, M1 Finding 2).
  Beacon antennas are NOT runway thresholds — never label derived runway/airfield points as
  surveyed; use generous uncertainty (runway 300m, airfield 500-1000m).
- Runway pairing: within one `airfield_group`, pair `ILS_LOCALIZER`+`ILS_GLIDESLOPE` and
  `PRMG_LOCALIZER`+`PRMG_GLIDESLOPE` — **never cross the two systems**; unpaired → skip, don't
  guess a partner.
- `.routes`/`.rn4` container: always assert the `landscape4::` class-name header and
  bounds-check every length prefix — a format change must be a loud exception, not silent
  garbage.
- `.routes` block walk: use **scan-forward resync** (find next `[N][plausible xyz triples]`),
  not naive sequential trailer-parsing — trailer is deliberately left partially undecoded.
- Real DCS files are gitignored (`data/raw/` — 2.25GB+) — test fixtures must be **hardcoded
  literals copied from the research note / probe capture**, with a provenance comment, per
  `test_dcs_grid.py`'s existing pattern. Never assume a real file is present in CI.
- `src/raster/` is NOT in M5's path — OSM uncertainty here is M1's ~1.0-1.3km, not M3's ~5km
  figure (that one compounds the still-provisional raster registration).

## Tests to write (see plan.md "Tests" section for exact fixture literals)

`test_geometry.py`, `test_towns_lua.py`, `test_beacons_lua.py`, `test_ingest_beacons.py`,
`test_roadnet_container.py` (must include valid-block-after-garbage resync test),
`test_roadnet_routes.py`, `test_roadnet_rn4.py` (must pin `subtype is None`),
`test_store_roundtrip.py`, `test_store_reader.py` (R*Tree vs brute-force agreement),
`test_describe_position.py` (control-point test, tolerance bands not exact values).
