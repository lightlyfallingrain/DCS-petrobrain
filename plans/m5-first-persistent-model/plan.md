### Goal

Build the first persistent, rebuildable spatial database for a ~20x20 km DCS-space region
(elevation, roads, settlements, water, named places, and airfields as reference points), fusing
DCS-authoritative sources with OSM
augmentation under explicit per-field provenance/confidence/uncertainty, and implement
`describe_position(theatre, x, z)` on top of it — returning structured position understanding
whose stated precision never exceeds the underlying data's known uncertainty.

---

### Revision 2026-09-04 — the road layer's data source changed (roads only)

**What changed.** The original Stage 2 sourced road geometry from live-mission `land.`
scripting calls (`getClosestPointOnRoads` / `findPathOnRoads`) because no offline road source
was known — and that stage was this plan's own stated largest single risk. Three investigator
sessions have since decoded DCS's static terrain files, and that assumption is now obsolete:
**whole-theatre road centerline geometry, per-point heading, and road/taxiway type labels all
ship as static files inside the terrain module** (`Mods/terrains/<Terrain>/roads/<Terrain>.rn4`
+ `<Terrain>.routes`, plus per-airfield `.rn4` under `AirfieldsTaxiways/`). No mission needs to
run. See Finding G.

**Why this is a stage restructure and not a patch.** Roads move out of the probe stage and into
the offline stage. **Stage 1 now delivers five of M5's six layers with no DCS round-trip at all**
(the sixth, airfields, was added by the 2026-09-04 decisions below and is also fully offline), and the live probe shrinks to elevation + surface type — M4's already-proven mechanism
plus one extra call. The stages are renumbered accordingly (old Stage 2 split into new Stage 2
`roadnet` and new Stage 3 `probe`).

**What deliberately did not change.** The storage decision (SQLite + R*Tree, JSON geometry,
GeoJSON export), the region (`latakia-20km` and its exact centre), the 500 m / 1,681-point grid,
the `describe_position` contract's shape, and every OSM layer other than roads. This finding
changes where road *geometry* comes from; it does not touch the storage or query design, and it
is not grounds to reopen those decisions.

**Scope guard.** This revision is **roads-only**. Settlement polygons, water, and named places
keep their planned sources unchanged.

---

### Research inputs

All DCS-internals claims below trace to these files. Nothing in this plan rests on an
unverified community claim.

- `world-model/research/2026-09-03-m5-roadnet-file-recon.md` — discovery that every terrain
  ships `roads/<Terrain>.rn4` + `<Terrain>.routes`, and every airfield its own `.rn4`.
- `world-model/research/2026-09-03-m5-terrain-file-formats.md` — first-round format
  characterization. **Superseded on byte offsets and structure** by the note below; cited for
  the header/file-size fields only.
- `world-model/research/2026-09-04-m5-roadnet-byte-decode.md` — **the authoritative format
  note.** Both sessions. Carries the final schema, the validated walk technique, and the
  explicit list of what is still undecoded.

- `world-model/research/2026-09-03-m5-recon.md` — the investigator findings (Q1-Q4) plus the
  same-day addendum recording the `nodes.lua` probe outcome.
- `world-model/research/2026-09-03-m5-nodes-lua-probe.txt` — raw read-only WSL capture,
  `20260903T204237Z`. Sections: `entry.lua` (full), `beacons.lua` (full), `map/towns.lua` grep
  pass (1,182 entry lines) plus head/tail, `MissionGenerator/nodes.lua` (full),
  `MissionGenerator/nodesMap.lua` (size + bounded preview). This is the **first-class raw input
  for the towns.lua ingest** and should be copied under `data/raw/dcs/` by Stage 1 rather than
  read out of `research/`. **It is also the source for the airfield layer** — its full
  `beacons.lua` section is what the 2026-09-04 airfield decision rests on, and this role verified
  the Latakia group and the runway-axis cross-checks directly against it.
- `world-model/research/2026-09-03-m4-dcs-elevation.md` — M4's proven probe mechanism and n=100
  data point.
- `world-model/research/2026-09-03-m3-osm-overlay.md` — OSM cache and payload precedent.

### Investigator gate — invoked, and it changed the plan twice

Step 2 of this role requires resolving unverified DCS-internals claims before finalizing. Four
were dispatched to `investigator`; findings are in
`world-model/research/2026-09-03-m5-recon.md`. Two of them are plan-changing, not addenda.

**Finding A — DCS ships an offline, plain-text named-place gazetteer.**
`Mods/terrains/Syria/map/towns.lua` is an unencrypted Lua data file with ~1,186 entries of the
form `["Aleppo"] = { latitude = 36.219471, longitude = 37.142091, display_name = _("Aleppo")}`.
It is **already synced to this Mac** at
`world-model/data/raw/dcs/2026-09-03/syria_terrain_lua_probe_20260903T075625Z.txt` — no live
mission, no probe, no io/lfs sandbox, no Windows round-trip. This overturns the working
assumption that place names must come from OSM: for any place DCS chose to label, **name and
point are DCS-authoritative**. Structure confirmed exhaustively across all entries: a flat table,
one line per entry, exactly three fields (`latitude`, `longitude`, `display_name`) — **no
category, type, radius, or extent field exists at all**. So OSM remains required for settlement
*extent* and for the many places DCS did not label, and any settlement-vs-POI distinction must be
inferred (towns.lua mixes cities, villages, military units, landmarks and even hotels and malls
in one undifferentiated list).

**Finding B — the Gemerek region is empty of DCS-named places. Region moved to Latakia (DECIDED).**
Verified directly by this role against the synced towns.lua dump, using the existing
`coordinates.wgs84_to_dcs`:

- Entries inside the Gemerek 20x20 km region (x=461319.5, z=29815.4, ±10 km): **0**.
- Distance from Gemerek centre to the *nearest* towns.lua entry (Kahramanmaras): **192.3 km**.

Independently confirmed by the investigator, which also found the cause: **towns.lua's northern
coverage ceiling is ~37.88°N** (Konya), roughly 130 km south of the Gemerek envelope
(39.09-39.28°N). This is not sparse labelling near Gemerek — the region is entirely outside the
gazetteer. Gemerek sits in unpopulated filler terrain at the far northern edge of the Syria map. That was
irrelevant to M1-M4 (a coordinate transform, a raster tile, an OSM overlay and an elevation grid
all work anywhere), but M5 is the first milestone that needs the region to *contain things*.
Combined with M3's separate observation of **zero waterways** in the small Gemerek bbox, keeping
Gemerek would mean shipping a "first persistent model" whose named-place layer is structurally
empty and whose water layer is probably empty — while the newly-found DCS-authoritative
gazetteer sits unusable 192 km away. **User has confirmed the move to Latakia** — see "Region"
below.

**Finding F — `MissionGenerator/nodes.lua` is NOT a road graph. Probe run.**
The follow-up Windows/WSL round-trip landed
(`research/2026-09-03-m5-nodes-lua-probe.txt`, lines 3180-3273) and settles the highest-priority
open lead from the recon note. `nodes.lua` defines a global `missionNodes` table of **9 entries**,
each a named strategic zone for AI campaign generation — Adana, Hatai, Damascus, Aleppo, Palmyra,
Beirut, Cyprus, H3, Efrat — carrying `id`, `name`, a single `redPos` and a single `bluePos` DCS
x/z pair, an empty `Tasks` table, and lists of AI unit-template names. **There are no edges, no
waypoint topology, no polylines, no connectivity of any kind.** It is a campaign-seeding table,
not a road network. The hoped-for outcome (an offline, zero-probe-risk road topology source that
would moot Finding D) did not materialise *from this file*. **The conclusion drawn from that at
the time — "the live-mission `land.` mechanism remains the only route to DCS-authoritative road
geometry" — was wrong and is withdrawn; see Finding G.** The search had been scoped to
`MissionGenerator/`; the road data is in `roads/`. `nodes.lua` itself is still not a road graph,
so this finding stands on its own terms — only the inference drawn past it does not.

Two useful by-products of the same probe, neither anticipated:

- **`towns.lua`'s table declaration is now known**: the file is `local gettext = require("i_18n")`
  / `local _ = gettext.translate` / `towns = { ... }` — a single **global named `towns`**, closed
  by a bare `}`. This was an explicitly open question in the recon note and it de-risks
  `parse_towns_lua`: the parser can anchor on `towns = {` and the closing brace rather than
  guessing the enclosing structure.
- **`nodesMap.lua` is one line**: `theatre.nodesMapBorders = { -257003.953125, -419498.875000,
  248852.046875, 368981.125000 }  --minX, minZ, maxX, maxZ`. Not a graph either — a bare DCS x/z
  bounding box. Worth noting because it **independently corroborates the region move**: Gemerek's
  x=461,320 lies ~212 km *beyond* this envelope's `maxX` of 248,852, while Latakia's x≈41,935 sits
  comfortably inside. Two unrelated DCS-internal datasets (the gazetteer's 37.88°N ceiling and the
  mission generator's node-map bounds) independently place Gemerek outside the map's populated
  content region. Treat this as corroboration only — `nodesMapBorders` is the *mission generator's*
  working envelope, not a documented terrain extent, and must not be encoded as one.

**Finding G — DCS ships static road geometry after all. Roads are now an offline layer.
(2026-09-04, supersedes Finding D as M5's road source.)**
Finding F closed the `nodes.lua` lead negatively and this plan concluded "the live-mission
`land.` road-extraction mechanism remains the only route to DCS-authoritative road geometry."
**That conclusion was wrong, and is withdrawn.** It was drawn from the `MissionGenerator/` tree;
the road data lives in `roads/`. Byte-exact decode against real files establishes:

- **`.routes` (whole-theatre, `Syria.routes`, 2,251,462,776 bytes) — road centerline geometry,
  GO.** A `landscape4::` container whose data region begins at **byte 93**, holding a sequence
  of per-route blocks: `[int32 N][N × float64 xyz position][int32 N][N × float64 xyz unit
  direction][trailer]`. The direction array is confirmed by unit magnitude (`1.0` exactly, which
  cannot happen by chance for coordinates in the tens of thousands) — so the format hands us
  **per-point heading for free**, with no need to numerically differentiate the polyline. The
  trailer is partially decoded (per-point cumulative arc-length float64 array, an int32 flags
  array, a bounded float32 array, then a ~64-byte-per-point undecoded region) and scales at a
  tight, reproducible **~156 bytes/point**.
- **Block boundaries are solved by scan-forward resync, and this is a validated technique, not
  guesswork.** From the end of a route's direction array, scan forward for the next offset whose
  `int32` reads a plausible `N` (5–20000) followed by `N` xyz triples inside DCS's real
  coordinate envelope. **Verified clean across 15 consecutive whole-theatre routes with zero
  false positives.** The trailer therefore never needs full decoding — it is located and
  skipped. A first/middle/last-triple pre-filter before the full `N`-point unpack is
  **mandatory**, not an optimization: the naive form was killed after 6+ CPU-minutes on a 50 MB
  buffer.
- **`.rn4` (`landscape4::lRoadNetwork`) — road/segment *type* labels, confirmed.** Header is
  class name, `int32` (constant `5`, meaning unknown), `int32` string count, then that many
  length-prefixed ASCII strings. The string table holds **type names**, read directly with no
  inference: Damascus `taxiway_24m, taxiway_61m, …, runway_65m`; Incirlik similar; Syria 23
  entries. Then a topology table of 32-byte / 8×int32 rows in which **column 6 is confirmed as
  the string-table type index**, and columns 2/5 form a forward/reverse directed-edge-pair
  index. After that comes an **undecoded int32-pair adjacency/graph section**, and after *that*,
  point geometry in the same `[int32 N][N × float64 xyz]` schema `.routes` uses.
- **Latakia coverage is present but only moderate-confidence.** A direct bulk `float64` scan of
  the 50 MB head sample found 17 coordinate triples inside the Latakia bbox, spatially coherent
  (near-zero coastal elevations plus a ~1046 m point consistent with Jabal Ansariyah). None was
  confirmed to belong to a fully walked route. This reverses the earlier "not found" but is
  **not** proof of coverage — see the Stage 2 gate.

**What is still open, and is carried as risk rather than assumed away:** the `.rn4` adjacency
section's schema is undecoded; the `.rn4` geometry walker reached only ~67% of `Damascus.rn4`
before losing sync; and **no topology row has been linked to a specific geometry block**, so
road *type* and road *geometry* are each independently extractable but **not provably joinable
per-segment**. M5's scope decision on that is stated below.

**Finding C — `land.getSurfaceType` can give a DCS-authoritative water AND road mask.**
Documented (Hoggit), Mission-Scripting-only, same environment and same `{x=, y=z}` vec2 shape as
the already-proven `land.getHeight`. Enum `LAND=1, SHALLOW_WATER=2, WATER=3, ROAD=4, RUNWAY=5` —
one call per point separates road from water. **Limitation that constrains the design**: it is
point sampling with no width, centerline, or connectivity, so any grid coarser than a road's few
metres of width aliases roads badly. It is a good *water mask* and a poor *road geometry* source.

**Role upgraded by Finding G.** Now that road geometry comes from `.routes`, this function's
`ROAD` / `RUNWAY` enum values stop being a weak geometry source and become something more
valuable: **an independent cross-check on the roadnet parser.** `getSurfaceType` and the
terrain-module road files are different DCS subsystems, so a grid cell reporting `ROAD` that
falls near an extracted `.routes` centerline is independent confirmation that the parser decoded
real roads rather than plausible-looking noise. This is the roadnet layer's closest available
equivalent to a control-point test, and it costs nothing because the probe runs anyway for
elevation and water. Wired in at Stage 4.

**Finding D — DCS road geometry is reachable but awkward. NO LONGER USED (superseded by
Finding G).**
`land.getClosestPointOnRoads(roadType, x, y)` and `land.findPathOnRoads(roadType, x, y, destX,
destY)`, both Mission-Scripting-only. Two landmines were recorded here: these take **plain
numbers, not a vec2 table**, and `findPathOnRoads`'s railroad type string is **`'rails'`** while
its sister function's is `'railroads'` — a documented ED inconsistency. **Neither function is
called by M5 any more**, so neither landmine is in the implementation's path and the
"behaviour far from any road" question no longer needs settling. Retained in the decision log
because deleting it would hide that the awkward path was investigated and then made unnecessary,
not overlooked. If M6 wants on-road *pathfinding* rather than geometry, start again here.

**Finding E — probe scale has no documented ceiling, so it must be approached incrementally.**
No numeric watchdog limit was found for many quick sequential `land.*` calls (distinct from the
well-documented busy-wait-hangs-DCS failure mode). The standard community pattern is
`timer.scheduleFunction` self-rescheduling chunking with incremental append-mode `io.write`,
never one giant loop holding results in memory. M4's proven data point is n=100.

**Still unresolved (carried into Risks, not silently assumed):**

- `getSurfaceType` has **not** been called against the live install — documented-only, exactly
  the status `getHeight` held before M4 Stage 1. (`getClosestPointOnRoads` / `findPathOnRoads`
  are **dropped from M5 entirely**, so their unverified status no longer matters here.)
- **`.rn4`'s adjacency section is undecoded, its geometry walker reaches ~67% of a real airfield
  file, and no topology row has been joined to a geometry block.** M5's design is built so that
  none of these three block it — see "Road layer scope" below — but they are real and stay in
  Risks.
- **`.routes` coverage of the Latakia region is moderate-confidence, not proven.** Stage 2
  carries an explicit gate for it.
- ~~`MissionGenerator/nodes.lua` / `nodesMap.lua` unread~~ — **RESOLVED, see Finding F.** Neither
  is a road graph. (The follow-on conclusion is superseded by Finding G.)
- ~~The 4-entry towns.lua parse discrepancy~~ — **RESOLVED, see the towns.py note below.** It was
  a line-count artifact, not lost entries.
- Whether towns.lua's lat/lon are DCS's *in-game* label positions or real-world gazetteer
  coordinates — this sets the layer's positional uncertainty (≈0 vs ≈1.3 km). See Risks for a
  cheap diagnostic.
- ED forum thread "land.getSurfaceType small enhancement" 403'd on fetch (a known pattern for
  this site). If it matters, it needs a manual paste.

---

### Key decision: spatial storage — recommendation

**Recommendation: one SQLite file per theatre-region (`data/world-model/<theatre>.sqlite`),
written and read with the stdlib `sqlite3` module, geometry stored in DCS x/z metres, with a
built-in R*Tree index for bbox pruning. QGIS-inspectability is served by a *GeoJSON exporter
tool*, not by making the storage file itself a GeoPackage.**

Against the four candidates the concept doc names:

- **PostGIS — rejected.** Requires a server process. The concept doc's own criteria for the
  initial local application explicitly include "no required server process", and this is a
  single-user offline pipeline on a two-machine manual-copy workflow. A server is pure
  operational cost here with no query it uniquely enables at this scale.
- **SpatiaLite — rejected for now.** The most capable option (real `ST_*` predicates, real
  spatial indexing), and the venv's Python *can* load extensions — verified locally:
  `sqlite3.Connection.enable_load_extension` works, SQLite 3.53.4, `ENABLE_RTREE` and
  `ENABLE_GEOPOLY` compiled in. But `mod_spatialite` is a native per-machine install, **not
  present on this machine**, and not pip-installable in a way that survives the Mac/Windows
  workflow. That is precisely the class of heavyweight native dependency M4 already declined once
  (GDAL/rasterio for COG DEMs) in favour of a ~150-line stdlib parser, and declining it again is
  consistent rather than novel. The spatial predicates M5 actually needs — point-to-point
  distance, point-to-segment distance, point-in-polygon, bbox pruning — are ~100 lines of planar
  geometry that can be unit-tested against hand-computed answers.
- **GeoPackage — rejected as the *storage* format; kept as a future *export* format.** Worth
  being precise, because it is the concept doc's own leading candidate: **a GeoPackage is just a
  SQLite file with a standard schema**, so this is not a fork in the road so much as a question
  of how much spec conformance to buy. Buying it means either (a) GDAL/fiona/geopandas — the
  dependency just rejected — or (b) hand-implementing `gpkg_contents`,
  `gpkg_spatial_ref_sys`, `gpkg_geometry_columns`, the rtree trigger set, and GPKG-flavoured WKB
  blobs. Real, spec-shaped work whose sole M5 payoff is QGIS double-click. And it carries a live
  risk: our authoritative space is DCS x/z, whose PROJ definition uses **`+axis=neu`**, and QGIS's
  handling of a custom neu-axis SRS is unverified — a nominally conformant GPKG could render
  transposed or mirrored, which is the *worst* failure mode for a project whose stated hazard is
  "convincing but wrong geography". A GeoJSON export in plain WGS84, via the
  `confidence="confirmed"` `coordinates.dcs_to_wgs84`, loads in QGIS with zero ambiguity and is
  ~40 lines of `json.dumps`.
- **FlatGeobuf / GeoParquet + application index — rejected.** New dependency, and its advantage
  (streaming very large datasets) is irrelevant at a few thousand features.

Three consequences that are what make this cheap, and that argue the decision on the merits
rather than on dependency-aversion alone:

- **DCS x/z is a metric projected plane, so Euclidean distance in x/z *is* distance in metres.**
  No geodesic math, no per-query reprojection, no CRS machinery anywhere in the query path. This
  is the single largest available simplification and it removes most of what a general-purpose
  spatial stack would be doing for us.
- **Zero new dependencies**, consistent with M1-M4 (`pyproj` + `Pillow` + stdlib
  `json`/`array`/`urllib`).
- **Not a one-way door.** The schema is ordinary SQL. A GPKG or SpatiaLite writer can be added
  later as an *exporter* without touching the store, the builder, or `describe_position`; and if
  M7's full-theatre workload proves Python-side geometry too slow, SpatiaLite becomes a swap
  behind `store/reader.py`'s interface rather than a rewrite. Choosing the simple thing now
  costs the later option nothing.

**Sub-decision — geometry encoding: JSON coordinate arrays (`[[x, z], ...]`), not WKB. DECIDED
(user-confirmed).** WKB is the standard and would make a future GeoPackage exporter nearly free
(~80 lines to write, ~80 to read). JSON is `json.dumps`/`json.loads`, readable in any SQLite
browser mid-debugging, and cannot be silently mis-endianed. At M5's scale the size difference is
immaterial. Per decision heuristic 2 (simple and debuggable over clever), JSON it is; a WKB
emitter can live inside the exporter later, reading the already-parsed coordinate list.

**Sub-decision — QGIS access: a GeoJSON export tool, not a GeoPackage writer. DECIDED
(user-confirmed).** `tools/export_geojson.py` emits WGS84 GeoJSON via
`coordinates.dcs_to_wgs84`. The `+axis=neu` SRS ambiguity described above is therefore never
exercised, and no GPKG conformance work is in M5's scope.

**Sub-decision — storage coordinate space: DCS x/z metres, canonical and singular.** lat/lon is
*derived* on export and in `describe_position`'s output, never stored as a second geometry.
Storing both would create two truths that can drift; DCS is authoritative about the simulated
world, so DCS space is the one that persists.

**Explicit non-dependency: `src/raster/` is not in M5's path.** The store never consults the
RasterCharts registration, whose `confidence` is still `"provisional"` with a ~9% z-axis
residual. All OSM→DCS positioning goes through `coordinates.wgs84_to_dcs`
(`confidence="confirmed"`, sub-centimetre against live `coord.LOtoLL`). This matters for the
uncertainty budget: **M5's OSM feature uncertainty is M1's ~1.0-1.3 km terrain-art placement
error, NOT M3's ~5 km figure**, which compounded the provisional raster registration and does
not apply to a store that never touches the raster. Do not import the 5 km number.

---

### Region — DECIDED: Latakia

**M5's test region is `latakia-20km`, not Gemerek.** User-confirmed. Named-place counts inside a
20x20 km box, computed by this role from the towns.lua dump via `coordinates.wgs84_to_dcs`:

| Candidate centre | DCS x/z | towns.lua entries in 20x20 km | Notes |
|---|---|---|---|
| ~~Gemerek~~ (M1-M4) | 461320 / 29815 | **0** (nearest 192 km) | plus 0 OSM waterways in M3's bbox; also outside `nodesMapBorders` |
| **Latakia ARP** (M1 control point) | **41935 / 5685** | **2** (Jablah, Al Hannadi) | **CHOSEN.** Mediterranean coast → water guaranteed; airbase; published ARP inside the region |
| Homs | -34024 / 73753 | 3 (Homs, Fairuzah, Zaidal) | Orontes river; all-land; no published control point |
| Damascus ARP (M1 cp) | -180212 / 51769 | 6 | large city → very large OSM payload; arid |
| Uckubbe (N Syria) | 184963 / 155276 | 21 | densest found; no prior validation continuity |

**Exact region definition for the Implementer** (recomputed and verified by this role, not
copied forward — the earlier draft's `41925 / 5687` was approximate):

- Centre: `wgs84_to_dcs("Syria", 35.40109, 35.94868)` = **x = 41934.892, z = 5685.076**, i.e. the
  published OSLK ARP, which is already `tests/control_points.py`'s Latakia control point
  (`real_lat` / `real_lon` fields). Half-extent 10,000 m.
- Note the distinction the Implementer must not blur: `control_points.py` also carries
  `dcs_x=43237.969, dcs_z=5841.165`, which is DCS's **in-game airbase position**, ~1.3 km from
  the ARP-derived point. That ~1.3 km gap *is* the M1 terrain-placement residual and is exactly
  the quantity `describe_position`'s uncertainty reporting exists to expose. Define the region
  from the ARP-derived centre; use the in-game position as a second query point in Stage 4's
  spot-check table, not as the region origin.
- The two named places sit at x/z ≈ **Jablah (37876, 3614)** and **Al Hannadi (50833, 3994)** —
  4.1 km and 8.9 km from centre respectively.

**Centre-offset latitude for Stage 0.** A coastal box spends some probe points on sea. This role
re-ran the census under eastward (inland) offsets: **both named places remain inside the box for
any offset up to +3 km in x**, so Stage 0 can trade sea coverage for land coverage without
collapsing the named-place layer. Beyond roughly +3 km, Jablah drops out. Pick the offset from
the Stage 0 census and record it; do not exceed +3 km without re-running the count.

Latakia is chosen not because it has the most content but because it is the only candidate
that is simultaneously: (a) an **M1 published-ARP control point**, so `describe_position` has an
independently-sourced expected answer inside the region and the control-point test stays
non-circular — the exact trap NOTES.md records M1 falling into once; (b) **guaranteed to contain
water** (Mediterranean coastline plus the Nahr al-Kabir), which makes `getSurfaceType`'s water
mask meaningful instead of a column of `LAND`; (c) populated with DCS-named places, so the
towns.lua layer is non-empty; (d) moderate density, so the Overpass payload and probe stay
tractable; (e) home to an airbase, a landmark class that actually matters for the eventual Mi-24
use case. Its one cost is the sea coverage quantified above.

Crucially, **this is a one-line change, not a re-plan**: regions live in a
`REGIONS: dict[str, RegionDefinition]` registry mirroring the established
`THEATRE_PROJECTIONS` / `THEATRE_RASTER_REGISTRATIONS` pattern, so `gemerek-20km` stays
registered for continuity and comparison. Little is lost by moving: M4's elevation grid is only
100 points and must be re-probed for a 20x20 km region regardless, and M2's Gemerek raster
validation is irrelevant because raster is not in M5's path.

---

### Road layer scope — what M5 takes from the roadnet files, and what it deliberately leaves

The format is understood well enough to extract more than M5 needs, and incompletely enough that
taking everything would mean guessing. The line is drawn at what `describe_position` actually
consumes.

**In scope for M5 — road existence, geometry, and orientation.** `describe_position`'s
`nearest_road` needs a distance, an orientation, and a provenance. All three come from
`.routes`' position array (distance, via `geometry.distance_point_polyline`) and its direction
array (orientation, read directly rather than differentiated). This is the milestone deliverable
and it rests only on the parts of the format that are solidly decoded.

**Out of scope — graph connectivity.** The `.rn4` adjacency section and the directed-edge
pairing are a *routing* substrate. Nothing in `describe_position` asks "can I drive from here to
there", so M5 does not decode the adjacency section at all. This is an **explicit non-goal**,
not an omission: it is M6/pathfinding work, and the Implementer should not chase it.

**Deferred, with the reason stated — road type/subtype.** `.rn4` column 6 is a confirmed
string-table type index, but **no topology row has been linked to a geometry block**, so "this
polyline is a `taxiway_52m`" cannot yet be asserted. M5 therefore emits road features with
**`subtype = null` and `name = null`**, and `describe_position` returns those as null rather
than as a guess. Emitting a type by assuming, say, positional correspondence between row order
and block order would be exactly the "convincing but wrong geography" failure this project is
least able to detect after the fact. The parser should still read and expose the string table
and topology rows (they are cheap and correctly decoded) so that a later linkage pass has
somewhere to land — it just must not join them.

**Rejected — using OSM to fill in the missing road type and name by proximity matching.**
Tempting, and it would populate `subtype`/`name` today. Rejected: OSM's positional uncertainty
in this theatre is ~1.3 km, which is far larger than the spacing between distinct roads in a
built-up area, so a nearest-OSM-way match would confidently attach the wrong name to the wrong
road a meaningful fraction of the time — and the result would look correct. A fusion heuristic
that can invent facts violates "code owns facts". Revisit in M6 only with a matching rule that
can *decline* (unique nearest within tolerance, second-nearest much farther, bearings agreeing)
and that records its match distance.

**OSM's remaining role for roads: a separate, clearly-labelled comparison layer. KEPT, not
dropped.** OSM roads are still ingested, still tagged `provenance={"geometry": "osm"}`, and
still carry `position_uncertainty_m ≈ 1300` — but they are no longer the road layer, they sit
*beside* it. This costs no new code (`ingest_osm` already classifies highways) and buys two
things worth having:

- It satisfies `describe_position`'s rule 2 — where DCS and OSM both answer, DCS wins and the
  disagreement is *reported*. `nearest_road` answers from DCS; `nearest_road_osm` answers from
  OSM; a caller can see the gap.
- It produces a real measurement: **the DCS-vs-OSM road centerline displacement across the
  Latakia region is the M1 terrain-art residual observed on a linear feature**, rather than on
  three airfield reference points. That is genuinely new evidence about the theatre and belongs
  in the research note.

The uncertainty contrast is the headline result of this revision and must be visible in the
data: DCS road geometry carries `position_uncertainty_m ≈ 0` (it *is* the simulated world's
truth, expressed in the authoritative coordinate space), against OSM's ~1300 m.

**Airfields — DECIDED (user, 2026-09-04): IN SCOPE for M5, as reference points only. Source is
`beacons.lua`, not `.rn4`.** See "Airfield layer" immediately below. The user's framing:
"airfields are important as a whole, not so much as individual taxiways or structures", and
runway reference points are good enough for this milestone. This is narrower than pulling in the
airfield `.rn4` geometry and wider than pure deferral.

**Airfield taxiway/runway *geometry* (`AirfieldsTaxiways/<Airfield>.rn4`) — still DEFERRED to
M6+, and the decision above is what makes the deferral cheap.** Deferred for three reasons that
are unchanged: the airfield walker is the *least* mature part of the finding (~67% file coverage,
block-separator logic in that region not reverse-engineered, geometry-region start located by
brute-force scan rather than from a header field); road *type* cannot be joined to geometry
anyway (Decision 7), so a decoded taxiway polyline could not even be labelled `taxiway_24m` with
confidence; and `describe_position` gains little from individual taxiway polylines that a
reference point does not give it far more cheaply. **Two notes for whoever picks it up:** the
per-airfield files are small (`Damascus.rn4` 376 KB, `Incirlik.rn4` 825 KB) and already local, so
acquisition is trivial whenever it is wanted; and whole-theatre `Syria.routes`' very first route
decodes as a closed loop near Damascus airport, so some airfield surface geometry may already
arrive for free in the theatre file — worth *counting* in Stage 2's census, but not worth
claiming as an airfield layer.

---

### Airfield layer — DECIDED, and cheaper than either option previously offered

M5 gains a sixth, deliberately lightweight layer: **airfields and runway axes as reference
points**, treated the same way `towns.lua` named places are treated — DCS-authoritative points
with names, not extracted structures.

**Source: `Mods/terrains/Syria/map/beacons.lua`, which is already synced to this Mac** inside
`world-model/research/2026-09-03-m5-nodes-lua-probe.txt` (the same read-only WSL capture that
carries `towns.lua`). No new probe, no new round trip, no `.rn4` work. This role verified the
file's contents and the Latakia coverage directly; the numbers below are computed from the synced
dump and the Implementer can reproduce them.

**Why not the sources considered first:**

- **`towns.lua` does not cover airfields.** Its `Latakia` entry is the *city*
  (35.525744, 35.785411) — about 14 km NNW of the airfield and **outside the `latakia-20km`
  region entirely**. There is no OSLK/Bassel Al-Assad entry. towns.lua is a settlement/POI
  gazetteer with exactly three fields and no category, so it cannot carry an airfield layer.
- **`tests/control_points.py` covers three airfields, hand-collected, and must not become a data
  source.** Its Latakia row (`dcs_x=43237.969, dcs_z=5841.165`) came from a live `coord.LOtoLL`
  probe during M1. It is a *test fixture*, and feeding it into the store would make the Stage 4
  control-point test circular — the exact trap NOTES.md records M1 falling into once. It stays a
  test input and a Stage 4 comparison point, never an ingest source.
- **pydcs / community airbase tables — rejected.** A new dependency whose airfield coordinates
  are community-transcribed, which is precisely "unverified community claim encoded as fact".
  `beacons.lua` is the same information read from the installed terrain module itself.

**What `beacons.lua` actually contains.** A global `beacons = { ... }` list (151 entries for
Syria, `beaconsTableFormat = 2`), each entry carrying `display_name`, `beaconId`, `type`,
`callsign`, `frequency`, **`position = { x, y, z }` in DCS-native metres**, `direction`, and
`positionGeo = { latitude, longitude }`. Airfield beacons are grouped by a `beaconId` prefix of
the form `airfield<N>_<M>`; `world_<N>` marks standalone en-route navaids. Beacon types present:
`AIRPORT_HOMER`, `AIRPORT_HOMER_WITH_MARKER`, `HOMER`, `DME`, `TACAN`, `VOR`, `VOR_DME`,
`VORTAC`, `RSBN`, `ILS_LOCALIZER`, `ILS_GLIDESLOPE`, `PRMG_LOCALIZER`, `PRMG_GLIDESLOPE`.

**Latakia is well covered — eight beacons, group `airfield21`, all eight inside the region:**

| beaconId | type | DCS x | DCS z | direction |
|---|---|---|---|---|
| `airfield21_0` | ILS_GLIDESLOPE | 43058.035 | 5704.971 | -1.444 |
| `airfield21_1` | ILS_LOCALIZER | 40423.035 | 5690.543 | -1.456 |
| `airfield21_2` | VOR_DME | 41480.648 | 5966.445 | 0.0 |
| `airfield21_3` | HOMER | 50737.488 | 5622.082 | -1.444 |
| `airfield21_4` | RSBN | 41451.059 | 5953.934 | 0.0 |
| `airfield21_5` | DME | 43057.664 | 5717.976 | 178.907 |
| `airfield21_6` | PRMG_LOCALIZER | 43417.754 | 5806.485 | 178.553 |
| `airfield21_7` | PRMG_GLIDESLOPE | 41140.094 | 5768.382 | 178.556 |

**The runway axis falls out of this, and cross-checks cleanly.** The ILS localizer/glideslope pair
spans **2635 m on a bearing of 0.31°**; the PRMG pair (opposite-direction system) spans 2278 m on
0.96°. Both agree with the beacons' own `direction` field (-1.444 ≈ 358.6°), and all three agree
with the published OSLK runway 17/35 at 2797 m. Three independent quantities agreeing is what
makes this trustworthy enough to ship without decoding a single byte of `.rn4`.

**What gets emitted, and the honesty constraint that shapes it.** A localizer antenna sits a few
hundred metres *beyond* the far runway end and a glideslope antenna sits laterally offset near the
touchdown zone — **so these are not surveyed threshold coordinates, and must never be labelled as
such.** Emitting a "runway threshold" from a beacon position would invent precision the source
does not have, which is the failure class this project is least able to detect afterwards.
Accordingly:

- **`kind = "navaid"`** — one point feature per beacon. Geometry is the beacon's own DCS x/z, so
  `provenance = {"geometry": "dcs", "name": "dcs"}`, `position_uncertainty_m = 0.0`. `subtype` is
  the beacon type; `tags_json` carries `beaconId`, `callsign`, `frequency`, `direction`, and the
  parsed `airfield_group` (e.g. `"airfield21"`) or `null` for `world_*` entries. This layer is
  pure transcription and asserts nothing beyond what the file says.
- **`kind = "runway"`** — a 2-point LineString per same-system localizer+glideslope pair within
  one airfield group (so Latakia yields two: one ILS, one PRMG). `provenance =
  {"geometry": "derived_from_dcs_beacons"}`, `confidence = {"geometry": "medium"}`,
  **`position_uncertainty_m = 300.0`** — a stated, deliberately generous figure reflecting
  antenna-vs-threshold displacement, not a measured residual. `tags_json` records the derivation
  method, the contributing `beaconId`s, the beacon `direction` value, and the segment's computed
  bearing so a reader can see the two agree. Orientation is reported from the beacon `direction`
  field, not from the segment, for the same reason road orientation comes from `.routes`'
  direction array: prefer what DCS states over what we derive.
- **`kind = "airfield"`** — one point feature per `airfield<N>` group, `name` from
  `display_name`. Geometry is the midpoint of the runway axis where one was derived, else the
  centroid of the group's beacons; `provenance = {"geometry": "derived_from_dcs_beacons",
  "name": "dcs"}`, with `position_uncertainty_m = 500.0` (axis-midpoint case) or `1000.0`
  (centroid case), and `tags_json` recording which of the two applies. For Latakia the ILS
  midpoint is **(41740.5, 5697.8)**.

**A built-in disagreement worth reporting rather than hiding.** That derived Latakia airfield
point sits **1504 m from `control_points.py`'s in-game airbase position (43237.97, 5841.165)**.
That is not an error in either: DCS's "airbase position" is a tower/ramp reference, while the
derived point is a runway-axis midpoint. They are different things and the gap is roughly a
runway half-length. This is exactly the case `describe_position`'s provenance and uncertainty
machinery exists for, and it belongs in Stage 4's spot-check table.

**Explicit non-goals for this layer**, so it cannot quietly grow: no taxiways, no structures, no
parking or ramp geometry, no airfield *extent* polygon, no ATC frequencies beyond the verbatim
beacon `frequency` field, and no attempt to reconcile beacon-derived points against
`AirfieldsTaxiways/*.rn4`. If the eventual Mi-24 use case needs "am I on a taxiway", that is the
deferred `.rn4` work, not this layer.

---

### Affected Modules / Files

**New — shared planar geometry**

- `world-model/src/geometry/__init__.py` — primitives in the DCS x/z metre plane, used by both
  the builder (bbox computation) and the query layer: `distance_point_point`,
  `distance_point_segment`, `distance_point_polyline`, `point_in_polygon` (ray casting),
  `bearing_deg` / `orientation_label` (e.g. `"N-S"`), `bbox_of`. Pure functions, no I/O, no
  dependencies. A shared module rather than duplicated helpers because build and query must agree
  *exactly* on bbox and distance or the R*Tree will prune correct answers.

**New — DCS offline data extraction**

- `world-model/src/dcs_data/__init__.py`
- `world-model/src/dcs_data/towns.py` — `TownEntry` frozen dataclass (name, display_name, lat,
  lon) and `parse_towns_lua(path) -> list[TownEntry]`. Regex-based extraction, no Lua interpreter
  dependency; the format is a flat `towns = { ... }` global of single-line entries (declaration
  now confirmed, Finding F). Two facts this role established by re-parsing the probe capture,
  both of which are parser requirements, not trivia:

  - **The entry count is exactly 1,182, and the earlier "1,186" was a line-count artifact — there
    are no missing entries.** All 1,182 entry-shaped lines match a strict, fully-anchored regex
    with **zero** failures. The arithmetic closes exactly: 1,182 entries + 4 header lines
    (`local gettext`, `local _`, blank, `towns = {`) + 1 closing `}` = the 1,187 lines originally
    reported. **This removes the "resolve the 4 missing entries" task from Stage 1.** The parser
    should still assert `len(entries) == EXPECTED_COUNT` and raise on any unmatched entry-shaped
    line, but it is now asserting a *known* number rather than hunting a discrepancy.
  - **31 entries have duplicate names; only 1,151 of the 1,182 names are unique.** Examples:
    `Yeniyurt` ×3, `Hisarkoy` ×3, `Army Vehicle Training Ground` ×4, plus 22 more Turkish village
    names appearing twice at genuinely different coordinates. **Therefore `parse_towns_lua` must
    return a `list`, never a `dict` keyed by name, and the `feature` table must not treat
    `name` as unique** — either would silently discard 31 real places. (Note the Lua semantics:
    because these are duplicate keys in one table literal, DCS's own runtime `towns` table only
    holds 1,151 of them, the later shadowing the earlier. The *file* is the authoritative record
    of what the terrain contains; the parser reads the file, so it sees all 1,182.) A test must
    pin this: parse a fixture containing a duplicated name and assert both rows survive.

- `world-model/src/dcs_data/beacons.py` — `BeaconEntry` frozen dataclass (`display_name`,
  `beacon_id`, `beacon_type`, `callsign`, `frequency`, `x`, `y`, `z`, `direction`, `lat`, `lon`,
  `airfield_group`) and `parse_beacons_lua(path) -> list[BeaconEntry]`. Sits beside `towns.py`
  because it is the same class of thing — a plain-text DCS gazetteer parsed without a Lua
  interpreter — and shares its discipline: strict, fully-anchored matching that **raises on an
  entry-shaped block it cannot parse rather than skipping it**, plus an expected-count assertion
  (151 for Syria) so a DCS patch that reformats the file fails loudly.

  Three parser requirements specific to this file, all established by this role against the synced
  dump: entries are **multi-line blocks** (`{ ... };`), not one-per-line like towns.lua, so the
  parser splits on block boundaries first and extracts `key = value;` fields second; `position` is
  a **three-element `{x, y, z}` list in DCS metres whose middle value is elevation, not `z`** —
  transposing it would silently place every beacon at the wrong spot at sea level, so a test must
  pin the field order; and `beaconId` must be split into `airfield_group` via the
  `airfield<N>_<M>` / `world_<N>` forms, returning `None` for the latter.

  **`positionGeo` is parsed and kept in `tags_json` but must NOT position anything, and must never
  enter a coordinate-transform test.** DCS ships both `position` and `positionGeo` per beacon, so
  validating `coordinates` against them would test DCS against itself — the circularity
  `world-model/research/2026-09-03-m1-coordinate-transform-verification.md` Finding 2 explicitly
  warns about. Geometry comes from `position`; `positionGeo` is an inspectable cross-reference
  only. State this in the module docstring, not just here.

**New — DCS road network extraction (`src/roadnet/`)**

A new package rather than a module inside `dcs_data/`, following the precedent of
`src/elevation/` (a DCS-side parser `dcs_grid.py` plus an external-source parser `dem.py`) and
`src/osm/`: a self-contained binary format with its own vocabulary earns its own package.
**Stdlib only — `struct`, `array`, `mmap`. No new dependencies**, consistent with M1-M4.

- `world-model/src/roadnet/__init__.py` — package docstring stating the format's provenance
  (which research note, which DCS version, which files) and, prominently, **which parts of the
  format are decoded and which are skipped**. Mirrors `coordinates/__init__.py`'s convention of
  putting the invariant at the package boundary. A future reader must not have to guess that the
  trailer is intentionally opaque.
- `world-model/src/roadnet/container.py` — the `landscape4::` container primitives shared by
  both file types: read the length-prefixed class-name header and assert it (a DCS patch that
  changes the format must fail here, loudly, not produce plausible garbage); read the
  length-prefixed string table; read an `[int32 N][N × float64 xyz]` block; and
  `find_next_point_block(buf, start)` — the **scan-forward resync** with the mandatory
  first/middle/last pre-filter and the DCS coordinate-envelope validation. This module exists to
  remove a *named* duplication: `.routes` and `.rn4` use the identical point-block schema and
  the identical resync technique, and letting the two parsers each grow their own copy is how
  they would drift.
- `world-model/src/roadnet/routes.py` — `RoutePolyline` frozen dataclass (`route_index`,
  `byte_offset`, `points: list[tuple[float, float, float]]`, `directions: …`) and
  **`iter_routes(path, bbox=None) -> Iterator[RoutePolyline]`, a streaming generator over an
  `mmap`**. Never loads the file into memory — `Syria.routes` is 2.25 GB. `bbox` filters during
  the walk so a region extract stays small. Also returns walk statistics (bytes covered, routes
  found, resync events, sync-loss events) because those are the parser's only self-diagnostic.
- `world-model/src/roadnet/rn4.py` — `parse_header`, `read_string_table`,
  `iter_topology_rows` (8×int32 rows, terminating on the sentinel row where column 1 stops being
  `1` and column 4 becomes `3`), exposing `type_name_for_row` via column 6.
  **Explicit non-goals recorded in the module docstring: the adjacency section is not decoded,
  and topology rows are not joined to geometry blocks.** M5 uses this module for the type
  vocabulary and a sanity read; it does not depend on it for the road layer.
- `world-model/src/roadnet/extract.py` — the cross-machine artifact format:
  `write_region_extract` / `read_region_extract` over JSON Lines (one route per line) plus a
  sidecar `manifest.json` recording the source file's path, byte size and mtime, the extractor
  version, the bbox, the route/point counts, and the walk statistics. This manifest is what
  makes a region extract *auditable* rather than an unexplained blob — see the acquisition
  decision immediately below.

**Acquisition — DECIDED (user, 2026-09-04): full local copy of `Syria.routes`. Option A.**
This is the *opposite* of the previous revision's recommendation (Option B, extract on the
Windows box and sync back a small result), and the user chose A deliberately. The user is copying
the complete `Mods/terrains/Syria/roads/Syria.routes` (2,251,462,776 bytes) from the DCS install
to this Mac, landing in `win-mac-sync/` the same way the earlier sample files did, and it is then
moved into `world-model/data/raw/dcs/syria/roads/Syria.routes`. Consequences the Implementer
should take as settled:

- **All development and Stage 2 rung 3 run against the full local file directly**, via the
  already-planned `mmap` streaming walk in `routes.py`. There is no remote-extraction round trip
  for `.routes` at any point in M5.
- **`tools/wsl/run_roadnet_extract.sh` is dropped from M5's scope**, and with it the unverified
  "does WSL have a working `python3`" prerequisite. It is no longer on the critical path; if a
  later milestone wants remote extraction it can be added then.
- **`extract.py` and `tools/extract_roadnet_region.py` are kept, and their manifest still
  matters** — not for cross-machine transfer any more, but because a Latakia region extract is a
  *derived* artifact and the manifest is what records which source file (path, size, mtime),
  which extractor version and which bbox produced it. Under Option A the extract becomes an
  optional local cache in `data/processed/` rather than a raw-equivalent input: `ingest_roadnet.py`
  can read either the extract or walk the full file. Keeping the manifest also keeps the
  provenance chain intact if the extract is ever regenerated on another machine.
- **The DB stays rebuildable from `data/raw/` on this machine alone**, which is the cleanest fit
  for the concept doc's "keep raw separate from derived". Cost is 2.25 GB of gitignored disk,
  which `data/` is already gitignored to absorb.
- **Local iteration speed is now the default**, so the walker's failure modes (resync, sync loss,
  coverage shortfall against the header's speculated `11464`) are debugged by rerunning a local
  command rather than by scheduling a round trip. This materially de-risks the Stage 2 gate.

**`Syria.rn4` (2,275,957,360 bytes) — the full file is NOT needed for M5. Optional, do not
block on it.** M5 uses `.rn4` for exactly two things: the string table (the road/taxiway *type*
vocabulary) and a sanity read of the topology rows. **Both live in the file's header region, at
the very start**, so the existing 50 MB head sample already on this Mac covers them completely.
The parts of `.rn4` that would need the whole file — the geometry region and the adjacency
section — are precisely the parts M5 deliberately does not use (Decisions 7 and 8: the
row→geometry join is unconfirmed and connectivity is an explicit non-goal). The `Damascus.rn4`
(376 KB) and `Incirlik.rn4` (825 KB) full airfield files already present are what Stage 2 rung 1
validates against, and they are complete. If the full `Syria.rn4` happens to be convenient to
copy it would let a future milestone attempt the type join without another transfer — worth
having, worth zero delay.

**New — persistent store**

- `world-model/src/store/__init__.py` — package docstring recording the storage decision and its
  rationale, mirroring `coordinates/__init__.py`'s convention of stating the invariant at the
  package boundary.
- `world-model/src/store/schema.py` — SQL DDL as module constants, `create_schema(conn)`, and a
  `SCHEMA_VERSION` integer in a `meta` table so a stale DB is detected loudly rather than misread
  quietly.
- `world-model/src/store/models.py` — frozen dataclasses crossing the store boundary: `Source`,
  `Region`, `StoredFeature`, `ElevationGrid`, `SurfaceGrid`.
- `world-model/src/store/writer.py` — `open_for_build`, `insert_source`, `insert_region`,
  `insert_features`, `insert_grid`. Populates the R*Tree in the same transaction as the feature
  insert, by explicit insert rather than triggers — one place to read, one place to debug.
- `world-model/src/store/reader.py` — read-only primitives: `load_region`,
  `features_in_bbox(conn, kinds, bbox)` (R*Tree-pruned), `nearest_feature(conn, kinds, x, z,
  max_radius_m)` (expanding-radius bbox search — 500 m, 2 km, 8 km, 30 km — then exact geometry
  distance over candidates), `containing_polygons`, `sample_grid(conn, grid_kind, x, z)`
  (bilinear for elevation, nearest-cell for the categorical surface grid — **interpolating an
  enum would be a category error**).

Proposed schema (ordinary SQL, no extensions):

```sql
CREATE TABLE meta   (key TEXT PRIMARY KEY, value TEXT NOT NULL);   -- schema_version, builder_version
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

Provenance is carried as per-field JSON maps on the feature, matching the concept doc's
`provenance: {geometry: dcs, name: osm}` shape, rather than as a separate
feature-field-provenance table — same expressiveness, far less join machinery, still inspectable
in plain SQL. `source` rows carry the fetch timestamp, the `data/raw/` path the row was built
from (so the DB is rebuildable and auditable), and the attribution string — **ODbL / "© OpenStreetMap
contributors" for the OSM source row**, which M3 established is a licence obligation, not a nicety.

**New — region definition and build pipeline**

- `world-model/src/build/region.py` — `RegionDefinition` (theatre, name, centre x/z, half-extent)
  with `to_wgs84_envelope()`, and a `REGIONS` registry. Ships **`latakia-20km` as M5's active
  region** (centre x=41934.892, z=5685.076, half-extent 10,000 m) and keeps `gemerek-20km`
  registered for M1-M4 continuity and comparison. **Regions are defined as squares in DCS x/z**,
  the authoritative space; the Overpass lat/lon bbox is a padded envelope of the four corners,
  not the definition — for Gemerek the corners disagree by ~0.008° of latitude, so a lat/lon-first
  definition would silently be a different shape than the region it claims to be.
- `world-model/src/build/ingest_towns.py` — towns.lua entries → `named_place` features,
  `provenance={"geometry": "dcs", "name": "dcs"}`. Clipped to the region.
- `world-model/src/build/ingest_beacons.py` — beacons.lua entries → `navaid`, `runway` and
  `airfield` features per "Airfield layer" above. Clipped to the region. The only module allowed
  to *derive* geometry (the runway segment and the airfield point); everything it derives is
  tagged `provenance={"geometry": "derived_from_dcs_beacons"}` with an explicit
  `position_uncertainty_m`, and the derivation method plus contributing `beaconId`s go in
  `tags_json`. Pairing rule, stated so it cannot drift: within one `airfield_group`, pair
  `ILS_LOCALIZER` with `ILS_GLIDESLOPE` and `PRMG_LOCALIZER` with `PRMG_GLIDESLOPE`; **never
  cross the two systems**, and where a group has an unpaired localizer or glideslope, emit no
  runway feature and count the skip rather than guessing a partner.
- `world-model/src/build/ingest_osm.py` — cached Overpass response via the existing
  `osm.features.load_features`, every vertex through `coordinates.wgs84_to_dcs`, classified by
  tags into `road` / `settlement` / `water` / `named_place`, clipped to the region, emitted with
  `provenance={"geometry": "osm", "name": "osm"}` and `position_uncertainty_m` from the M1
  residual envelope (~1300 m), the `source` string citing the M1 verification note. No new
  network code.
- `world-model/src/build/ingest_roadnet.py` — a `.routes` region extract → `road` features,
  one per route polyline clipped to the region, with `provenance={"geometry": "dcs"}`,
  `confidence={"geometry": "high"}`, **`position_uncertainty_m = 0.0`**, `subtype=None`,
  `name=None`. Carries `source_ref` = the originating route index and byte offset, so any
  feature in the DB can be traced back to its bytes in the DCS file — the roadnet layer's
  equivalent of a raw-path citation. Per-point direction vectors are stored alongside the
  geometry (or, if that proves awkward in the `feature` row, the segment orientation is computed
  once at build time and stored in `tags_json`); either way `describe_position` must not
  differentiate the polyline at query time when DCS already told us the heading. A route clipped
  at the region boundary is flagged `clipped: true` in `tags_json` rather than silently
  truncated.
- `world-model/src/build/ingest_probe.py` — the DCS probe grid (elevation + surface type) → an
  `ElevationGrid` and a `SurfaceGrid`. Reuses `elevation.dcs_grid` for the height column.
  **No longer emits road features** — that was the live-probe road path, now replaced by
  `ingest_roadnet.py`.
- `world-model/src/build/pipeline.py` — `build_region(region, raw_paths, out_path)`, idempotent:
  deletes and rebuilds the `.sqlite` from `data/raw/` on every run, per the concept doc's "keep
  raw separate from derived so the database can be rebuilt".

**New — query API (the milestone deliverable)**

- `world-model/src/query/__init__.py` — exports `describe_position`.
- `world-model/src/query/describe.py` — `describe_position` and its frozen result dataclasses.
  See the contract below.

**New — tools**

- `world-model/tools/build_world_model.py` — CLI over `build.pipeline`.
- `world-model/tools/describe_position.py` — `describe <db> <theatre> <x> <z>` (plus a `--latlon`
  mode routing through `coordinates.wgs84_to_dcs`), printing JSON. The human-inspectable
  diagnostic the concept doc's testing philosophy asks for.
- `world-model/tools/export_geojson.py` — store → WGS84 GeoJSON for QGIS. This is what replaces
  "make the storage file a GeoPackage".
- `world-model/tools/extract_roadnet_region.py` — CLI over `src.roadnet`: walk a `.routes` (or
  `.rn4`) file, clip to a region bbox, write the extract + manifest. Stdlib-only and importable
  with no third-party packages, so the *same* file runs on this Mac and on the DCS machine
  under Option B.
- `world-model/tools/inspect_roadnet.py` — the human-inspectable diagnostic the concept doc's
  testing philosophy asks for: print the string table, the first N topology rows with their
  resolved type names, per-route point counts and bboxes, and dump routes as WGS84 GeoJSON so a
  human can look at the roads on a map and say whether they are sane. This is how the parser is
  validated at all, given the input files are gitignored and cannot be pytest fixtures at scale.

**Modified**

- `world-model/tools/wsl/probe_syria_terrain_lua.sh` — extend its full-dump file list to include
  `map/towns.lua`, `map/beacons.lua`, `MissionGenerator/nodes.lua`,
  `MissionGenerator/nodesMap.lua`, so towns.lua and beacons.lua are first-class re-pullable raw
  inputs rather than side effects of one grep run. Also add a **plain recursive `ls` of the Syria
  terrain module root** — one line, read-only, and it answers for free whether a richer airdrome
  or runway table ships alongside `map/` (currently unverified, and the reason the airfield layer
  is beacon-derived rather than surveyed). Read-only throughout; it never writes inside the DCS
  install.
- ~~`world-model/tools/wsl/run_roadnet_extract.sh`~~ — **dropped.** It existed only to serve
  acquisition Option B, which the user has decided against; see the acquisition decision above.
- `world-model/tools/dcs-mission-probe/` — a new `terrain_probe.lua` (or an extended
  `elevation_probe.lua`) emitting `height_m` + `surface_type` per point, using
  `timer.scheduleFunction` chunking and append-mode `io.write` per Finding E. **Simplified by
  this revision**: `getClosestPointOnRoads` / `findPathOnRoads` are gone, so Finding D's two
  landmines (plain-number args, `'rails'` vs `'railroads'`) are no longer in the probe's path at
  all. The probe is now M4's proven `getHeight` loop plus one `getSurfaceType` call per point.
- `world-model/src/osm/overpass.py` — widen `_build_query` to add `way["landuse"]`,
  `way["natural"="water"]`, `relation["natural"="water"]`, and `way`/`relation["place"]`, so
  settlements have extent (for point-in-polygon) and water is actually present. Preserve the
  module's hard "at most one network call per cache miss" rule.
- `world-model/src/osm/features.py` — handle `"relation"` elements, currently ignored by design.
- `world-model/pyproject.toml` — add `store`, `build`, `query`, `geometry`, `dcs_data`,
  `roadnet` to `[tool.ruff.lint.isort] known-first-party`. NOTES.md records this exact omission
  causing a recurring, self-resurrecting I001 finding across M1/M2.
- `world-model/CLAUDE.md` — add a "Spatial storage: SQLite + R*Tree (M5 decision)" tech-stack
  line; add a **"Road/taxiway geometry: DCS-native `.rn4`/`.routes` (`landscape4::` container),
  stdlib `struct`/`array`/`mmap`, no new deps (M5 decision)"** line citing the byte-decode note;
  add **towns.lua and beacons.lua** as named DCS data sources, with beacons.lua annotated
  "airfield/navaid reference points; `positionGeo` must never be used for transform validation
  (circularity — M1 verification note Finding 2)"; drop the "deferred to M5" wording.
- `world-model/ROADMAP.md`, `todo/todo.md` — flip M5; clear the deferred storage item.
- `world-model/research/2026-09-03-m5-first-persistent-model.md` — new dated note: region used
  and why it moved, feature census by kind and provenance, grid spacing and probe run
  characteristics, towns.lua-vs-OSM position comparison (see Risks), `describe_position` outputs
  at control points, and the storage decision with rationale — per CONVENTIONS.md, spatial-library
  choices must be recorded in `research/`. **Plus, from this revision:** the roadnet walk
  statistics (routes found, points, resyncs, sync losses, coverage against the header's
  speculated `11464` route count), the `getSurfaceType`-`ROAD`-vs-centerline agreement rate, and
  the **DCS-vs-OSM road displacement distribution** — the first measurement of the M1 terrain-art
  residual on a linear feature rather than on point control points. **Plus the airfield layer's
  numbers**: the beacon census by type and airfield group, the ILS-vs-PRMG-vs-`direction` runway
  bearing agreement, the derived-axis length against published OSLK 17/35, and the ~1504 m gap
  between the derived airfield point and DCS's in-game airbase position — with the explanation
  that the two reference different things, so a future reader does not read it as an error.

**Tests**

- `tests/test_geometry.py` — primitives against hand-computed answers, including degenerate
  cases (zero-length segment, point on a polygon vertex/edge, polygon wound both ways).
- `tests/test_towns_lua.py` — parse a hardcoded multi-entry fixture copied verbatim from the
  synced dump (with a provenance comment, the pattern `test_dcs_grid.py` already uses since
  `data/` is gitignored); assert the strict parser rejects a malformed entry rather than skipping
  it.
- `tests/test_beacons_lua.py` — parse a hardcoded fixture copied verbatim from the synced dump
  (with a provenance comment naming `research/2026-09-03-m5-nodes-lua-probe.txt`), covering the
  full Latakia `airfield21` group plus one `world_*` entry. Must assert: the `{x, y, z}` field
  order (the middle value is elevation — pin it with a beacon whose y is small and whose z is
  clearly not), `airfield_group` parsing for both `airfield<N>_<M>` and `world_<N>` forms, and
  that a malformed block raises rather than being skipped.
- `tests/test_ingest_beacons.py` — the derivation rules, which are where this layer can go wrong
  quietly. Assert: the ILS pair yields a runway segment of ~2635 m at bearing ~0.31° and the PRMG
  pair ~2278 m at ~0.96° (tolerance bands, not exact values); **ILS and PRMG are never crossed**;
  an unpaired localizer emits no runway and increments a skip count; the derived `airfield` point
  is the ILS-axis midpoint ~(41740.5, 5697.8); and every derived feature carries
  `provenance["geometry"] == "derived_from_dcs_beacons"` with a non-zero
  `position_uncertainty_m`, while every `navaid` feature carries `"dcs"` and `0.0`. That last
  pair is a scope guard expressed as a test: it makes it impossible to promote a derived point to
  DCS-authoritative without arguing with the suite.
- `tests/test_roadnet_container.py` — the container primitives against **synthetic byte fixtures
  built in the test** (`data/` is gitignored, so real files can never be fixtures — the pattern
  `test_dcs_grid.py` already established). Must cover: a well-formed point block; a wrong
  class-name header raising rather than parsing; an `N` that would read past end-of-buffer being
  rejected; and — most importantly — **a valid block preceded by a region of plausible-looking
  garbage, asserting the scan-forward resync lands on the real block.** Resync is the technique
  the whole parser rests on; it gets tested directly, not just implicitly.
- `tests/test_roadnet_routes.py` — a fixture assembled from **literal values copied verbatim from
  the byte-decode research note** (with a provenance comment naming the note, the file and the
  byte offset), asserting the decoded positions and that the direction vectors have unit
  magnitude. The unit-magnitude assertion is the cheap invariant that catches a misaligned read.
- `tests/test_roadnet_rn4.py` — string-table parse and topology-row decode against literals from
  `Damascus.rn4` (`taxiway_24m`, `runway_65m`, column 6 resolving to a type name, the sentinel
  row terminating the table). Also asserts the parser **does not** attempt a row→geometry join,
  by pinning that `subtype` on emitted features is `None` — a scope guard expressed as a test,
  so a future well-meaning change has to argue with it.
- `tests/test_store_roundtrip.py` — schema creation, insert/read roundtrip, provenance and
  confidence JSON preserved verbatim, `SCHEMA_VERSION` mismatch detected.
- `tests/test_store_reader.py` — **R*Tree-pruned `nearest_feature` must agree with a brute-force
  scan** over a synthetic feature set. The brute-force reference lives in the test, not in
  `src/`; this is how an index is kept honest.
- `tests/test_describe_position.py` — the control-point test `world-model/CLAUDE.md` requires.
  Fixture DB built from hardcoded real-data literals. At the Latakia ARP: asserts the nearest
  named place, a distance inside a stated **tolerance band** (not an exact value — asserting
  sub-100 m precision would encode a precision the data does not have), an elevation in a
  plausible band, and that **every returned field carries non-null provenance**.

No changes to `src/coordinates/` or `src/raster/`.

---

### `describe_position` contract

```python
describe_position(conn, theatre: str, x: float, z: float) -> PositionDescription
```

Input is **DCS-native x/z** — the concept doc's signature and the authoritative space. lat/lon
callers go through `coordinates.wgs84_to_dcs`; one entry point, no overload.

Returns a frozen, JSON-serialisable dataclass — deterministic, structured, no prose:

- `theatre`, `position: {x, z}`, `lat`, `lon` (marked derived)
- `elevation`: `{dcs_m, source: "dcs", confidence, external_m | null, delta_m | null}` — the
  concept doc's `elevation_dcs / elevation_external / delta` triple. **Never a blended number.**
  Outside grid coverage, `dcs_m` is `null` and says why.
- `surface_type`: `{value: "LAND"|"SHALLOW_WATER"|"WATER"|"ROAD"|"RUNWAY", provenance: "dcs",
  sampled_at_m: <grid spacing, 500 m>}` — the spacing is returned because a `LAND` sample 350 m from the
  query point is a much weaker claim than one 10 m away, and the caller must be able to see that.
- `nearest_road`: `{distance_m, orientation, subtype, name | null, provenance, confidence,
  position_uncertainty_m}` — **answered from the DCS `.routes` layer**, so
  `provenance="dcs"` and `position_uncertainty_m = 0.0`; `orientation` comes from the format's
  own per-point direction vector, not from differentiating the polyline; and **`subtype` and
  `name` are `null` in M5** per "Road layer scope" — the type index exists but is not yet
  joinable to geometry, and a null is the honest answer.
- `nearest_road_osm`: the same shape, answered from the OSM road layer with `provenance="osm"`
  and `position_uncertainty_m ≈ 1300`. Present so that rule 2 below is observable rather than
  merely asserted: the two roads' disagreement *is* the reported disagreement. If OSM has no
  road in range, this is `null` like any other absence.
- `nearest_settlement`, `inside_settlement` (point-in-polygon, where extents exist),
  `nearest_water`, `named_places_within_radius` (radius stated in the result)
- `nearest_airfield`: `{name, distance_m, provenance: "derived_from_dcs_beacons", confidence,
  position_uncertainty_m, derivation: "runway_axis_midpoint" | "beacon_centroid"}` — the
  reference-point airfield layer. `derivation` is returned rather than buried in tags because it
  is what the stated uncertainty means; a caller reading `distance_m: 1400` needs to see that the
  point is a runway midpoint, not a terminal.
- `nearest_runway`: `{airfield_name, distance_m, orientation_deg, system: "ILS" | "PRMG",
  provenance, confidence, position_uncertainty_m}` — distance to the derived runway axis segment
  via `geometry.distance_point_polyline`. **`orientation_deg` is the beacons' own `direction`
  field, not the segment bearing** (same principle as road orientation coming from `.routes`'
  direction array: prefer what DCS states over what we compute). No threshold, no designator, no
  length claim — the source does not support them.
- `navaids_within_radius`: verbatim beacon transcriptions (`name`, `type`, `callsign`,
  `frequency`, `distance_m`), `provenance: "dcs"`, `position_uncertainty_m: 0.0`. Separate from
  the airfield entries specifically so a caller can tell transcribed fact from derived geometry
  at a glance.
- `region`: which built region answered, and its build timestamp.

Four rules that define what "position understanding" means at this stage:

1. **Every geographic claim carries its provenance and its positional uncertainty.** A road from
   OSM reports `distance_m: 80` *alongside* `position_uncertainty_m: 1300`. Downstream layers must
   be able to see that the 80 is not trustworthy to 80 m. This is the milestone's most important
   honesty property and it follows directly from the invariant against collapsing "DCS says X" and
   "the real world says X" into one undocumented fact.
2. **Where DCS and OSM both answer, DCS wins and the disagreement is reported, not hidden.** If
   the surface grid says `WATER` and no OSM water feature is near, the result says so. Recording
   disagreement is the entire point of the provenance model.
3. **Absence is reported as absence.** No water in range yields `null` — never a guess, never a
   match dragged in from outside the built region. Code owns facts.
4. **No natural language.** Structured data only; prose is a later presentation layer.

---

### Implementation Plan

1. **Stage 0 — data census and centre offset (gate; no store code).** The region itself is
   settled (Latakia). Remaining Stage 0 work: derive the DCS-space square and its lat/lon
   envelope, confirm the towns.lua count inside it (expect 2 — Jablah, Al Hannadi), choose the
   eastward centre offset within the verified 0-to-+3 km band, and run **one** Overpass fetch
   with the widened query. Report counts by kind. **Gate: does the region contain water,
   settlement polygons, and
   named places?** M3's bbox had zero waterways and Gemerek had zero named places — shipping a
   six-layer model with two empty layers is the failure this gate exists to prevent. The airfield
   layer needs no gate — this role has already verified eight Latakia beacons inside the region. Also record
   the payload size before it is a surprise (M3's 2.8x3.4 km bbox was ~98 KB; 20x20 km with
   landuse and water added is plausibly a few MB).

   **Roadnet acquisition is no longer a Stage 0 question** — the user has decided (Option A, full
   local copy) and the only Stage 0 action is to confirm
   `data/raw/dcs/syria/roads/Syria.routes` has landed and its size matches 2,251,462,776 bytes
   before Stage 2 rung 3 needs it. Stage 0 does not block on that arriving; rungs 1 and 2 run
   against local samples regardless.

2. **Stage 1 — minimal working version: offline sources only, no probe.** Build `src/geometry/`,
   `src/dcs_data/towns.py`, `src/dcs_data/beacons.py`, `src/store/`, `src/build/` (region + towns
   + beacons + OSM + pipeline), and a `describe_position` answering named places, airfields,
   runways, navaids, roads, settlements and water, with elevation and surface type null.
   Everything here runs from data already on this Mac — **the entire storage decision gets
   validated against a real query workload before a single minute of DCS round-trip is spent**,
   which is the main reason the stages are ordered this way. Copy the probe capture into
   `data/raw/dcs/` as the towns.lua **and beacons.lua** ingest's raw input (it currently lives
   only under `research/`). Export GeoJSON and eyeball it in QGIS against the M3 overlay — the
   concept doc's "a human should be able to look at a generated map and say whether it is sane"
   check, and for the airfield layer specifically an unusually strong one: the derived runway axis
   should visibly lie along the runway in the imagery.

3. **Stage 2 — DCS-native road layer (`src/roadnet/`). Still offline, still no live mission.**
   This stage replaces the old live-probe road plan entirely. Build it in three rungs, smallest
   first, because each rung is independently checkable:
   1. **`container.py` + `rn4.py` against the small airfield files already on this Mac.**
      `Damascus.rn4` (376 KB) and `Incirlik.rn4` (825 KB) are fully local, small, and have
      *known expected answers* recorded in the research note — the string tables are literal
      ASCII (`taxiway_24m`, `runway_65m`) and the topology row counts are known (79 and 132 plus
      a sentinel). If the parser cannot reproduce those exact strings and counts, nothing further
      is worth attempting. Cheapest possible proof the container model is right.
   2. **`routes.py` against the local 50 MB `Syria.routes.head50m` sample.** Walk it end to end
      and reproduce the note's validated result: 15+ consecutive routes with clean boundaries,
      route 1 at `N=343` decoding as a closed loop near Damascus with unit-magnitude directions.
      Report walk statistics. **Do not skip the first/middle/last pre-filter** — the note records
      the naive form being killed after 6+ CPU-minutes on exactly this buffer.
   3. **The full-file walk against the local `data/raw/dcs/syria/roads/Syria.routes`**, producing
      the Latakia extract + manifest, then `ingest_roadnet.py` into the store. Local and
      rerunnable, per the acquisition decision — a walker bug is a local edit, not a round trip.

   **Gate — Latakia coverage.** `.routes` coverage of the Latakia region is *moderate*
   confidence (17 candidate triples in the head sample, none confirmed as belonging to a walked
   route). If the full-file walk yields **zero** routes intersecting the region bbox, that is an
   escalation, not a silent degrade: stop, report it, and decide explicitly whether the road
   layer falls back to OSM-only for M5. Do not quietly ship an empty road layer — that is the
   same failure mode the Stage 0 census exists to prevent.

   **Coverage check, cheap and worth doing.** `.routes`' header carries an `int32` reading
   `11464` at byte ~63, speculated in the research note to be the total route count. If the
   full walk finds ≈11,464 routes, that is strong independent evidence the walker covered the
   whole file; if it finds far fewer, the walker is losing sync and the shortfall is quantified
   rather than invisible. Record the number either way — it either confirms a header field's
   meaning or exposes a parser gap, and both are useful.

4. **Stage 3 — DCS probe: elevation + surface type only.** Substantially smaller than in the
   previous revision: the road functions are gone, so this is M4's proven `getHeight` loop plus
   one `getSurfaceType` call per point. **Grid: 500 m spacing, 41x41 = 1,681 points
   (user-decided)**, reached by the incremental ladder, not jumped to. Follow Finding E's
   pattern — `timer.scheduleFunction` chunking, append-mode `io.write`, and a **100-200 point
   smoke test first** (M4's proven order of magnitude) carrying all the calls the full run will
   use. Then the intermediate rung (~500), then the full 1,681. Stop and reassess if any rung
   shows non-linear cost. Wire elevation and surface type into `describe_position`; compute SRTM
   delta stats with the existing M4 tooling and store them as grid metadata (stats only — SRTM
   samples are **not** copied into the DB).

5. **Stage 4 — validate correctness.** Control-point test at the region's published ARP;
   R*Tree-vs-brute-force agreement test; a manual spot-check table of `describe_position` at 6-8
   hand-chosen points (town centre, open country, a road, over water, and a point outside
   coverage) recorded in the research note. Confirm the outside-coverage case degrades to explicit
   nulls rather than to plausible-looking wrong answers — that failure mode is the one this
   project is most exposed to.

   **Airfield-layer validation, and it is cheap because independent answers already exist.** Add
   to the spot-check table: (a) the derived Latakia airfield point vs `control_points.py`'s
   in-game airbase position — expect ~1504 m and *report* it rather than reconciling it, since
   they are a runway midpoint and a tower/ramp reference and the gap is roughly a runway
   half-length; (b) the ILS-derived and PRMG-derived runway bearings vs each other and vs the
   beacons' `direction` field — three quantities that should agree within ~1°, and a disagreement
   means the parser has the `{x, y, z}` order or the pairing wrong; (c) the runway axis length
   (~2635 m ILS) against published OSLK 17/35 at 2797 m — close, and expected to be *short*, since
   the axis spans antenna to antenna, not threshold to threshold. If (c) came out *longer* than
   the published runway, something is wrong. None of these is a pass/fail gate; all three go in
   the research note.

   Two roadnet-specific validations, both only possible once Stages 2 and 3 have both landed —
   this is the reason they are sequenced before this stage rather than after:
   - **Cross-subsystem check (Finding C).** For every probe grid cell whose `getSurfaceType`
     returned `ROAD` or `RUNWAY`, measure the distance to the nearest extracted `.routes`
     centerline. High agreement is independent confirmation from a *different* DCS subsystem
     that the parser decoded real roads. Report the agreement rate and the outliers; do not
     assert a pass/fail threshold before seeing the distribution, since the 500 m grid aliases
     roads badly in the other direction (many roads fall between samples — that is expected and
     is not a parser failure).
   - **DCS-vs-OSM road displacement.** Distance distribution between DCS centerlines and the
     nearest OSM highway across the region. Expected to sit near the M1 ~1.0-1.3 km terrain-art
     residual; if it does, two independent methods agree on that number for the first time. A
     wildly different figure means something is wrong and is worth stopping for.

6. **Stage 5 — validate performance (light).** Not a hot path, but establish the numbers M7 will
   be judged against: full rebuild wall time, `.sqlite` size, `describe_position` latency over
   ~100 random in-region points. If a brute-force scan is already comparable to the R*Tree path at
   this scale, say so plainly — that is useful evidence for M7, not a failure.
   **Add one roadnet number**: wall time and peak memory for the full-file `.routes` walk. This
   is M5's only multi-GB workload, it runs once per rebuild, and M7 (full theatre, all layers)
   will be sized against it. Peak memory matters specifically because it is the assertion that
   the streaming generator is actually streaming.

7. **Stage 6 — refine and close out.** Research note, `CLAUDE.md` tech-stack lines, ROADMAP/todo
   updates including clearing the deferred storage item, full verification sequence (`ruff
   format`, `ruff check`, `mypy --strict`, `pytest`), user sign-off.

---

### Net risk change from this revision — stated honestly

This is **not** a pure risk reduction, though it is close to one.

**Removed.** The previous revision named the live-mission road mechanism "the largest single risk
in M5", and it is gone outright rather than mitigated: two never-called scripting functions, ED's
documented `'rails'`/`'railroads'` inconsistency, the plain-number-vs-vec2 argument trap, the
unknown far-from-any-road return behaviour, and the whole question of whether repeated
`getClosestPointOnRoads` probing could trace a centerline at all. The road layer no longer
depends on DCS running, on the mission-scripting sandbox, on the `MissionScripting.lua` io/lfs
edit, or on probe-scale limits. What remains of the DCS round-trip for roads is *reading a
static file*.

**Added.** Multi-GB file logistics across a manual-copy workflow; a parser whose walk technique
is validated on 15 routes but not on ~11,464; three genuinely undecoded regions of the format;
no ground truth for road geometry other than the two cross-checks in Stage 4; and a new package
of ~300-400 lines to write and test.

**Net.** Code volume is roughly a wash — a new package replaces the probe's road half. Risk is
meaningfully lower, because the new risks are *inspectable and local* (a file on disk, parsed by
code that can be rerun in a second) whereas the removed ones were *remote and stateful* (a
running simulator on another machine, sampled through an API with unverified behaviour). A
parser bug is found by looking; a probe bug is found by scheduling another round trip. That is
the real improvement, more than the count of risks.

### Risks & Unknowns

- **`getSurfaceType` is documented-only, never called against this install.** This is exactly
  where `land.getHeight` stood before M4 Stage 1 — which resolved cleanly — but it is not yet
  evidence. Stage 3's smoke test is the first real test. (Reduced from three functions to one by
  this revision.)
- **The `.routes` walker is validated on 15 consecutive routes, not on a whole 2.25 GB file.**
  Scan-forward resync had zero false positives at that sample size, and the ~156 bytes/point
  trailer ratio held tightly across all 15 — good evidence, not proof. A production walk will
  meet route shapes the sample did not contain. Mitigations, all in the design rather than
  bolted on: the walker reports resync and sync-loss events instead of silently skipping;
  every `N` is bounds-checked against the buffer; and Stage 2's route-count-vs-`11464` check
  quantifies coverage. **A walker that silently drops a third of the theatre's roads is the
  dangerous failure here, and it is dangerous precisely because the output would still look
  correct.**
- **`.rn4`'s adjacency section is undecoded and no topology row is joined to a geometry block.**
  M5 is designed not to need either (see "Road layer scope"), so this is a *bounded* unknown —
  but it is why `subtype` ships null, and it is the work that has to happen before per-segment
  typed roads or any pathfinding is possible. Do not let it leak into M5 as a guessed join.
- **The `.rn4` geometry walker reached only ~67% of `Damascus.rn4`.** Relevant only to the
  deferred airfield layer, not to M5's roads, since M5's geometry comes from `.routes`. Recorded
  so the deferral's cost is visible: whoever takes on airfields inherits an incomplete walker,
  not a finished one.
- **`.routes` coverage of Latakia is moderate-confidence.** Gated explicitly at Stage 2. Listed
  separately from the walker risk because the failure looks identical (no roads in the region)
  while the cause and the remedy are completely different — the gate must distinguish "the
  walker failed" from "the region genuinely has no routes", which the walk statistics make
  possible.
- **`Syria.routes`' header size field is ~2.3 MB short of the actual file size** (and the same
  discrepancy appears in `Caucasus.routes`, so it is systematic, not corruption). Unexplained.
  `.rn4`'s equivalent field matches exactly. Non-blocking — the walker does not trust that field
  — but it means there may be trailing structure past what the walk models, and it is a reason
  not to treat a header field as authoritative without checking.
- **Format fragility across DCS patches.** A terrain update could change `.rn4`/`.routes`
  silently. The parser must assert the `landscape4::` class-name header and bounds-check every
  length prefix, so a format change is a loud exception rather than plausible-looking wrong
  geography. The same discipline as the towns.lua parser, for the same reason.
- **Multi-GB walk cost.** Acquisition risk is now largely retired — the file is copied once,
  locally, and parser iteration costs nothing. What remains is an **unmeasured CPython full-file
  walk time and peak memory** over 2.25 GB, which lands on every rebuild. Bounded by developing
  against the local 50 MB samples and measured explicitly in Stage 5. If the full walk turns out
  to cost minutes per rebuild, the region extract (kept, with its manifest) becomes the standing
  local cache and the full walk becomes an occasional refresh — a change of habit, not of design.
- **The airfield layer's geometry is *derived*, and derived geometry is the easiest place in this
  plan to accidentally overclaim.** Beacon antennas are not runway thresholds; the runway feature
  is an antenna-to-antenna segment carrying a deliberately generous 300 m uncertainty, and the
  airfield point is a midpoint or centroid carrying 500-1000 m. The specific danger is a
  downstream consumer — or a later milestone — reading `nearest_runway.distance_m` as a precise
  distance to pavement. Mitigated by returning `derivation` and `position_uncertainty_m` in the
  result rather than only in the store, and pinned by `test_ingest_beacons.py`'s
  provenance/uncertainty assertions. **This is the one M5 layer where "convincing but wrong
  geography" is produced by our own arithmetic rather than by a source**, so it gets the strictest
  labelling in the plan.
- **beacons.lua may not be the best available airfield source, and that is currently unverified.**
  The Syria terrain module's directory tree has never been listed in full, so a richer airdrome or
  runway table could exist. Non-blocking: beacons.lua is sufficient for reference points, already
  local, and cross-checks cleanly. The one-line recursive `ls` folded into
  `probe_syria_terrain_lua.sh` answers it on the next probe run at no cost. If a surveyed runway
  table turns up, the airfield layer's derivation is replaced and its uncertainty drops — an
  upgrade behind the same feature kinds, not a redesign.
- **Beacon coverage is per-airfield and uneven across the theatre.** Latakia has a full eight-beacon
  group with both ILS and PRMG; a smaller field may have one homer and no localizer/glideslope
  pair, yielding an `airfield` point by centroid and **no runway feature at all**. That is correct
  behaviour (absence reported as absence), but it means the layer's completeness varies by field
  and the census must report how many groups produced a runway versus only a point. Irrelevant
  inside `latakia-20km`; it matters at M7's full-theatre scale.
- **Long polylines weaken R*Tree pruning.** A route's bbox is only a useful index key if the
  route is short relative to the query radius. Inside a 20x20 km region a clipped route's bbox is
  at most ~20 km across and there are a few hundred features, so this is fine at M5 scale — but
  at M7's full-theatre scale, theatre-spanning routes will need splitting into bounded-extent
  segments before indexing. Noted for M7; **explicitly not solved in M5**, per "choose designs
  that can be iterated later".
- ~~`nodes.lua` is unread~~ — **closed** (Finding F), though the conclusion originally drawn from
  it was wrong; see Finding G. Kept in the log because "we searched, found nothing, and concluded
  too much from that" is worth remembering: the negative result was real, the inference past it
  was not.
- **towns.lua positional semantics are unresolved** — are those lat/lon values DCS's *in-game*
  label positions (uncertainty ≈ 0, since the transform is confirmed to sub-centimetre) or
  real-world gazetteer coordinates a terrain artist pasted in (uncertainty ≈ 1.3 km, the M1
  art-placement envelope)? This sets the named-place layer's entire uncertainty budget.
  **Cheap diagnostic, worth doing in Stage 1**: for every towns.lua entry that has a matching OSM
  `place` node, compute the offset. A systematic offset with coherent direction says "DCS in-game
  position"; scatter about ~0 says "real-world copy". This is the same class of reasoning M4 used
  to separate datum offset from mesh-resolution noise, and NOTES.md already warns (from M3) that
  two sources can use different reference conventions for the same named place.
- **Regex-parsing Lua is brittle** — though *not* lossy here, contrary to the earlier draft: a
  fully-anchored regex matches all 1,182 entries with zero failures, and the apparent 4-entry
  shortfall was a line-count artifact. The residual risk is a future DCS patch reformatting
  towns.lua (e.g. wrapping entries across lines, which would break the one-entry-per-line
  assumption the whole parser rests on). Mitigated by a strict parser that raises rather than
  skips, plus the exact-count assertion. Acceptable because the file is a versioned raw input
  under `data/raw/` and a parse failure is loud.
- **Duplicate place names are real and easy to destroy.** 31 of 1,182 entries share a name with
  another entry. Any `dict`-keyed intermediate, any `SELECT DISTINCT name`, any unique constraint
  on `feature.name`, or any dedup-by-name step in the OSM/towns reconciliation will silently drop
  real places — and silently dropping real geography is precisely the failure class this project
  is least able to detect after the fact. Pinned by a test.
- **A 20x20 km box at Latakia includes open sea.** The Mediterranean occupies part of the western
  edge, so a fraction of the 1,681 probe points return `WATER` and carry no useful road or
  settlement content. This is a cost, not a defect — it is also the only reason the water layer
  is guaranteed non-empty. Stage 0's centre offset bounds it; the exact land/sea split is not
  known until Stage 0's census runs.
- **`getSurfaceType` aliases roads at any usable grid spacing** (Finding C). The surface grid must
  be presented as a *water* mask with a road hint, never as a road geometry source; the API
  returns the sample spacing precisely so callers cannot over-read it.
- **OSM positional uncertainty (~1.3 km) is comparable to the distances being reported.** The API
  surfaces this rather than fixing it. **For roads this is now genuinely fixed** — the DCS layer
  carries ~0 m uncertainty — but settlements, water and OSM-sourced named places still live with
  it, so the honesty machinery stays exactly as designed. The risk that remains is a *reader*
  one: with `nearest_road` and `nearest_road_osm` sitting side by side, a downstream consumer
  could treat them as interchangeable. They are not, and the differing
  `position_uncertainty_m` is what says so.
- **Settlement extents may be poorly mapped.** Rural Turkish OSM had good road coverage (M3), but
  `landuse=residential` polygons are a different tagging practice; `inside_settlement` may be null
  far more often than expected. Stage 0's census is the early warning.
- **Overpass payload size versus the one-call rule.** A 20x20 km widened query is far larger than
  M3's. If it times out at `[timeout:25]`, raising the timeout or splitting the query is a
  *deliberate* change to `overpass.py`'s hard single-call constraint and must be surfaced, not
  slipped in.
- **Multipolygon relations.** Large water bodies and some settlement extents are encoded as
  relations with outer/inner rings; full support is real work. Scope guard: M5 handles ways as
  polygons and treats unsupported relations as an explicitly counted, logged skip reported in the
  research note — never a silent drop.
- **Vertical datum still unestablished** (carried from M4). Stored DCS elevation is authoritative
  and internally consistent; the SRTM delta stays a comparison statistic, not a correction.
- **`SCHEMA_VERSION` discipline.** The DB is gitignored and rebuilt from raw, so a stale file
  after a schema edit is a realistic and confusing failure mode; the version check turns it into a
  clear error.
- **`MissionScripting.lua` io/lfs edit remains in place** (M4 close-out, intentional, more probes
  expected). Still a standing modification to the user's install — worth re-confirming at M5
  close-out rather than becoming permanent by default.
- **Scope creep toward M6.** Ridges and valleys are explicitly M6. M5's elevation layer stays a
  stored grid plus interpolation — no slope, aspect, or ridgeline extraction. **This revision
  adds two more tempting M6 doors that must stay shut**: decoding `.rn4`'s adjacency section for
  road connectivity, and extracting airfield taxiway/runway geometry. Both are now clearly
  *possible*, which makes them harder to leave alone than when they were unknown. Neither is in
  M5. **The airfield reference-point layer sharpens this rather than softening it**: having
  airfields in the store makes "and now let us add the taxiways" feel like a small next step, and
  it is not — it is the ~67%-coverage `.rn4` walker plus an unconfirmed type join. The layer's
  explicit non-goals list is the guard.

---

### Decisions — resolved (decision log)

| # | Decision | Outcome | Recorded consequence |
|---|---|---|---|
| 1 | Test region | **Latakia**, not Gemerek | `latakia-20km` is M5's active region; `gemerek-20km` stays registered for continuity |
| 2 | `nodes.lua` road-graph lead | **Probed — not a road graph** | Closed (Finding F). The inference drawn past it was later overturned by Finding G |
| 3 | Elevation/surface grid spacing | **500 m / 1,681 points, incremental** | Stage 3 climbs 100-200 → ~500 → 1,681 rather than jumping |
| 4 | Geometry encoding | **JSON coordinate arrays**, not WKB | `feature.geom_json` holds `[[x, z], ...]`; a WKB emitter is deferred to a future exporter |
| 5 | QGIS access | **GeoJSON export tool**, not a GPKG writer | `tools/export_geojson.py`; the `+axis=neu` SRS ambiguity is never exercised |
| 6 | **Road geometry source** | **DCS-native `.routes` parsing**, not live-mission `land.` probing | New `src/roadnet/` package; roads move from the probe stage to the offline stage; Finding D's functions are dropped from M5 (Finding G) |
| 7 | **Road type/subtype in M5** | **Deferred — emit `null`** | The `.rn4` row→geometry join is unconfirmed; guessing it is barred, and pinned by a test |
| 8 | **Graph connectivity** | **Explicit non-goal for M5** | The `.rn4` adjacency section is not decoded; connectivity is M6/pathfinding scope |
| 9 | **OSM's role for roads** | **Kept as a separate comparison layer**, not dropped, not fused | `nearest_road_osm` sits beside `nearest_road`; no proximity attribute-matching heuristic |
| 10 | **Airfield taxiway/runway *geometry*** | **Deferred to M6+** | The `.rn4` walker reaches ~67% and the type join is unconfirmed; superseded as M5's airfield answer by row 12 |
| 11 | **Roadnet acquisition** | **Option A — full local copy of `Syria.routes` (user, 2026-09-04)** | Development and Stage 2 rung 3 run against the full local file via `mmap`; `tools/wsl/run_roadnet_extract.sh` dropped; the WSL `python3` prerequisite is moot. Full `Syria.rn4` **not** required — its string table and topology rows are in the header, covered by the local 50 MB head sample |
| 12 | **Airfields in M5** | **In scope as reference points, sourced from `beacons.lua` (user, 2026-09-04)** | New `navaid` / `runway` / `airfield` feature kinds and three new `describe_position` fields; zero new probes, zero `.rn4` geometry work. Explicitly excludes taxiways, structures and airfield extents |

### Decisions Requiring User Input

**None. Every open item is resolved — the plan is ready for the Implementer.**

The two items outstanding at the previous revision were both decided by the user on 2026-09-04
and are recorded as rows 11 and 12 above. What remains open in this plan is *unknowns carried as
risk* (the walker's whole-file behaviour, `getSurfaceType` never having been called on this
install, `.routes` coverage of Latakia, towns.lua positional semantics) — each is gated,
instrumented, or diagnosed inside a stage rather than left to be discovered. None of them is a
choice the Implementer is being asked to make.

One sequencing note, not a decision: **Stage 2 rung 3 needs
`data/raw/dcs/syria/roads/Syria.routes` to have finished copying.** Stage 0, Stage 1 and Stage 2
rungs 1-2 do not, so implementation starts immediately and the copy proceeds in parallel.

### Open, but not blocking

- **The 403'd ED forum thread** ("land.getSurfaceType small enhancement") may document a known
  limitation of `getSurfaceType`. It remains unread — forum.dcs.world blocks automated fetch. This
  does **not** block implementation: Stage 3's smoke test empirically settles the function's
  behaviour on this install regardless of what the thread says. If you would like it factored in
  anyway, open the URL and paste the content, and it can be folded into Stage 3's design before
  the probe is written. Otherwise M5 proceeds on the Hoggit documentation plus the smoke test.
