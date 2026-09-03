# M3 — OSM overlay (Gemerek)

Date: 2026-09-03
Status: findings recorded after implementing `world-model/src/osm/` and running the
diagnostic overlay once against the live Overpass fetch. See `plans/m3-osm-overlay/plan.md`
for the approved plan this session implements.

## Fetch

Single Overpass API request, `https://overpass-api.de/api/interpreter`, POST body per the
plan's exact query (bbox `south=39.170, west=36.050, north=39.195, east=36.090`, Gemerek,
Sivas Province, Turkey). Cached raw response:
`world-model/data/raw/osm/2026-09-03/gemerek_bbox.json` (gitignored, not committed).

- **Payload size**: 100,401 bytes (~98 KB) — within the plan's "plausibly under 100 KB"
  estimate.
- **Element counts**: 118 total (113 ways, 5 nodes). 96 `highway` ways, 17 `building` ways, 5
  `place` nodes (1 town — Gemerek itself — plus 4 `suburb`/mahalle nodes), 0 `waterway`
  features (none present in this bbox — a real finding, not a bug: Gemerek's bbox as drawn
  doesn't cross the mapped stream/river geometry, if any exists nearby).
- **Fix required**: the first live request returned `HTTP 406 Not Acceptable`. Overpass
  rejects requests with no `User-Agent` header, which `urllib.request`'s default has none of.
  Fixed by setting an explicit `User-Agent` (`osm/overpass.py`'s `_USER_AGENT` constant) — not
  a retry, a one-time code fix before the (only) successful fetch. No second bbox fetch was
  made; this counts as the plan's single network call.
- **Gemerek-vs-Sivas fallback**: not needed. 96 highway ways and 17 buildings is a
  non-trivial, meaningfully renderable feature set — Stage 1's density check passed on the
  first fetch.

## Diagnostic overlay results

Ran `tools/inspect_osm_overlay.py overlay` against the cached fetch and the already-decoded
`64maa00_x0_z0.tif.dds` tile (`world-model/data/raw/dcs/2026-09-03/.../64maa00_x0_z0.tif.dds`,
M2 session 12's tile). 110 of 113 ways drew fully inside this tile (3 ways crossed off-tile
and were skipped, not drawn partially); all 5 place nodes fell on-tile.

**Visual check**: the rendered overlay's road/building cluster lands directly on the chart's
own printed road network and settlement symbol near the "Gemerek" label — same general shape,
offset by roughly one town-width to the west. This is the expected residual (see below), not a
gross misalignment; the overlay is recognizably tracing the same town, not a different one.

**Displacement report** (DCS coordinate / F10 raster location / lat-lon / OSM location / error
distance, per `docs/concept/WORLD_MODEL_BUILDER.md`'s Validation format — pixel-space here
substitutes for a metric error distance since both points are on the same known tile/scale):

| Feature | OSM lat/lon | Transformed tile pixel (px, py) | M2 session-12 by-eye pixel | Pixel delta | Approx. delta (m, at 64 m/px) |
|---|---|---|---|---|---|
| Gemerek (town node) | 39.1831222, 36.0711044 | (408, 975) | (490, 975) | 82.0 px | ~5,248 m |
| Bahçeli Mahallesi | 39.1843355, 36.0687589 | (404, 972) | (490, 975) | 86.1 px | ~5,507 m |
| Muhsin Yazıcıoğlu Mahallesi | 39.1889924, 36.0794878 | (419, 965) | (490, 975) | 71.7 px | ~4,589 m |
| Fevzi Çakmak Mahallesi | 39.1832544, 36.0760546 | (414, 975) | (490, 975) | 76.0 px | ~4,864 m |
| Yukarı Mahalle | 39.1766343, 36.0748958 | (412, 986) | (490, 975) | 78.8 px | ~5,041 m |

Notably, the `py` (row / x-axis) component of the Gemerek node's transform matches M2's
by-eye reading exactly (975 vs 975); essentially all of the ~5.2 km delta is on `px` (column
/ z-axis) — consistent with M2's own finding that the z-axis fit is the looser of the two
(~9% residual, session 7), not a new discrepancy this session introduces.

**This displacement is expected, not a bug** — per the plan's "Risks & Unknowns": it compounds
M1's ~1.0–1.3 km DCS-vs-real-world residual with M2's raster registration z-axis residual
(~9%, several km worst-case over a 65.5 km tile edge). ~5.2 km on the z-axis is squarely
inside that already-understood envelope. Some of the delta is also not registration error at
all: the OSM node's coordinate (39.1831222, 36.0711044) and the Wikipedia-sourced coordinate
M2 session 12 used (39.18194, 36.06806) are two different real-world reference points for
"Gemerek" ~300 m apart in longitude — comparing an OSM node to a by-eye chart-symbol reading
is not an apples-to-apples residual measurement, only an internal-consistency sanity check
(this is why `test_osm_transform.py` uses a wider tolerance than
`test_raster_registration.py`'s control-point tests, and does not claim to newly validate the
registration's real-world accuracy).

## Storage backlog — resolved for M3: defer to M5

Confirms `plans/m3-osm-overlay/plan.md`'s "Storage backlog item" analysis: M3's only
persisted artifact is the raw Overpass JSON cache (already the correct interchange format,
no transformation needed); parsed features (`osm.features.OsmNode`/`OsmWay`) live as
in-memory dataclasses for one tool invocation; the diagnostic output is a rendered PNG plus a
text displacement table, not a queryable index. Nothing in M3 required point-in-polygon,
nearest-neighbor, or multi-feature-type joins — the actual workload that would justify
picking GeoPackage/SpatiaLite/PostGIS now. **Decision: defer the spatial-storage choice to
M5** ("First persistent model," `world-model/ROADMAP.md`), where `describe_position(...)`
first creates a real query workload to validate the choice against. `todo/todo.md` and
`world-model/CLAUDE.md`'s "Spatial storage" note updated accordingly.

## Attribution

Overlay output and this note: (c) OpenStreetMap contributors.
