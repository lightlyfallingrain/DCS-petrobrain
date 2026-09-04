# M5 Stage 0 — Latakia region census

Date: 2026-09-04
Status: findings recorded after deriving the `latakia-20km` envelope, confirming both known
`towns.lua` entries fall inside it, running one widened Overpass fetch, and confirming
`Syria.routes`'s local path/size. See `plans/m5-first-persistent-model/plan.md` ("Region —
DECIDED: Latakia", "Road layer scope" acquisition decision) and
`plans/m5-first-persistent-model/checklist.md` (Stage 0) for the approved scope this session
executes. No store code was written — this is a census/verification stage only, per the
checklist.

## 1. Envelope

Centre: `wgs84_to_dcs("Syria", 35.40109, 35.94868)` = **x = 41934.892, z = 5685.076** (the
published OSLK ARP, also `tests/control_points.py`'s Latakia control point). Half-extent
10,000 m.

## 2. Offset

Both `towns.lua` entries were re-derived from their exact lat/lon (not the plan's rounded
values) via `coordinates.wgs84_to_dcs`:

| Name | lat/lon | DCS x/z |
|---|---|---|
| Jablah | 35.363965, 35.927291 | 37875.860, 3613.909 |
| Al Hannadi | 35.480731, 35.927036 | 50832.549, 3993.869 |

At offset 0 (no shift), Jablah sits 5,940.97 m from the box's west edge and Al Hannadi sits
1,102.34 m from the east edge — both comfortably inside a 20 km box. Re-running the count at
increasing offsets shows Jablah does not actually drop out of the box until roughly **+5,941 m**
of eastward shift (`plan.md`'s "beyond roughly +3 km, Jablah drops out" appears to have been a
conservative approximation rather than the exact threshold — this session's recomputation with
the towns.lua entries' full-precision lat/lon gives a materially larger margin). This is recorded
as a discrepancy for future reference, not acted on: the checklist's instruction is an explicit
0–+3 km cap ("re-run the count if you approach the +3km boundary"), and that cap is respected
regardless of the wider margin actually available.

**Chosen offset: +3,000 m** (the maximum of the mandated 0–+3 km band). Reasoning: the region is
a coastal box (Mediterranean to the west), so any eastward shift trades sea coverage for land
coverage; taking the full mandated cap maximizes that trade without approaching either town's
margin:

| Offset | Jablah margin to west edge | Al Hannadi margin to east edge |
|---|---|---|
| 0 m | 5,940.97 m | 1,102.34 m |
| +3,000 m | 2,940.97 m | 4,102.34 m |

Both margins stay multi-kilometre at +3,000 m — no re-run-the-count trigger was hit.

**Resulting region** (centre x = 44,934.892, z = 5,685.076, half-extent 10,000 m):

| Corner | DCS x, z | lat, lon |
|---|---|---|
| SW | 34934.892, -4314.924 | 35.335238, 35.841176 |
| SE | 54934.892, -4314.924 | 35.515298, 35.834131 |
| NW | 34934.892, 15685.076 | 35.340786, 36.060946 |
| NE | 54934.892, 15685.076 | 35.520883, 36.054390 |

WGS84 bounding box (south/west/north/east): **35.335238 / 35.834131 / 35.520883 / 36.060946**.

## 3. Widened Overpass fetch

`tools/fetch_m5_stage0_census.py` reuses `osm.overpass.fetch_bbox`'s cache-first/single-call/
User-Agent discipline (M3's established convention — `2026-09-03-m3-osm-overlay.md`) via a new
optional `query` override parameter on `fetch_bbox` (backward compatible; M3's default query
path is untouched). Query widened per Stage 0's instruction — M3's `highway`/`building`/`place`
node/`waterway` set plus `landuse`, `natural=water`, and `place` way/relation:

```
way["highway"](bbox); way["building"](bbox); node["place"](bbox); way["place"](bbox);
relation["place"](bbox); way["waterway"](bbox); way["natural"="water"](bbox);
relation["natural"="water"](bbox); way["landuse"](bbox);
```

Single network call. Cached raw response:
`world-model/data/raw/osm/2026-09-04/latakia_20km_widened.json` (gitignored, not committed;
19,631,612 bytes).

**Feature counts:**

| Category | Count |
|---|---|
| Total elements | 13,618 |
| Nodes | 112 |
| Ways | 13,493 |
| Relations | 13 |
| Water polygons (`natural=water` or `waterway=riverbank`, way/relation) | 27 |
| Settlement polygons (`place=*` or `landuse=residential`, way/relation) | 194 |
| Named places (`place` node with a `name` tag) | 112 |
| Highways | 3,342 |
| Buildings | 9,679 |

Spot-checked two named nodes with an English name tag: **جبلة / "Jable"** (`place=city`) —
matching `towns.lua`'s Jablah — and **هنادي / "Hanadi"** (`place=village`) — matching
`towns.lua`'s Al Hannadi. Independent corroboration, from OSM, that DCS's two gazetteer entries
correspond to real, OSM-mapped settlements inside the chosen box (no name-string match was
required for the gate itself — the two datasets are compared here only as a sanity check, not
fused).

## 4. Gate

**Gate: region must contain water polygons AND settlement polygons AND named places.**

| Check | Result |
|---|---|
| Water polygons | 27 — **PASS** |
| Settlement polygons | 194 — **PASS** |
| Named places | 112 — **PASS** |

All three pass. This is the exact failure mode M3/Gemerek hit (0 named places, 0 waterways in
its bbox) — Latakia does not repeat it.

## 5. `Syria.routes` acquisition check

Checklist item 9: confirm `Syria.routes` landed at the expected path/size before Stage 2 needs
it.

```
$ ls world-model/data/raw/dcs/syria/roads/
Syria.routes
$ stat -f "%z bytes" world-model/data/raw/dcs/syria/roads/Syria.routes
2251462776 bytes
```

Path and byte count match the plan's acquisition decision exactly
(`Mods/terrains/Syria/roads/Syria.routes`, 2,251,462,776 bytes, Option A — full local copy).
Nothing was moved or copied by this session; the file was already present at the expected path.

## Attribution

Overpass fetch and reported counts: (c) OpenStreetMap contributors.
