# osm-landcover-optimization: Stage 6 real small-extract validation

Date: 2026-09-13. Branch `feature/osm-landcover-optimization`, commit history up to Stage 5.

Agent-run validation per `plans/osm-landcover-optimization/plan.md` Implementation Plan step 6.
**Never touched `data/world-model/syria-full.sqlite` or `syria-full-osm-cache.sqlite`, never ran a
`syria-full` build.** All builds below used the registered `latakia-20km` region and one ad-hoc
20 km region, written entirely to a session scratch directory
(`/tmp/.../scratchpad/osm-landcover-validation/`), never `world-model/data/`.

Inputs: real DCS files from the installed `DCS World` under `/mnt/f/Games/DCS World/Mods/terrains/
Syria/` (`map/towns.lua`, `beacons.lua`, `roads/Syria.routes`) — read-only, nothing written back.
Real OSM extracts from `/mnt/f/dcs-world-model/syria/raw/osm/` (`syria-clipped.osm.pbf`,
`lebanon-clipped.osm.pbf` — the per-country clips from a prior job (a) run, already on this
machine).

## 1. Pre-filter (job (a) §2.4, `osmium tags-filter`)

```
osmium tags-filter <clip>.osm.pbf -e world-model/tools/osm_tags_filter.txt -o <clip>-filtered.osm.pbf
```

| extract | nodes before → after | ways before → after | relations before → after | size before → after | filter time |
|---|---|---|---|---|---|
| syria-clipped | 11,406,015 → 1,516,302 (13.3%) | 1,718,933 → 58,213 (3.4%) | 2,550 → 451 | 72 MB → 9.99 MB | 6.58s |
| lebanon-clipped | (not measured before) | — | — | → 3.66 MB | 4.94s |

Matches the plan's own Context section numbers closely (11.41M→1.52M nodes, 1.72M→58k ways,
462 relations vs. 451 measured here — small variance is expected, different OSM snapshot dates).
RUN.md §2.5's "~13%/~29% of nodes, ~3%/~6% of ways" claim for Syria/Turkey is confirmed on the
Syria side (13.3% nodes, 3.4% ways); Turkey wasn't re-measured here (out of scope for a *small*
extract validation).

## 2. `latakia-20km` build (real DCS inputs + filtered `syria-clipped.osm.pbf`)

Built via `tools/validate_osm_landcover.py` (new, this stage), which drives `build.pipeline.
build_region` directly (towns + beacons + `--osm-pbf` only — no `--routes`/`--srtm-dir`, since
this tool validates the OSM/landcover pipeline specifically, and `Syria.routes` is a slow,
unrelated 2.25 GB parse; a separate full build including routes was run in parallel for realism,
see §6).

**Note on `latakia-20km`'s actual coverage**: despite the name, this registered region (`build.
region.REGIONS`) is centred on Bassel Al-Assad International Airport's ARP plus a 3,000 m
eastward offset (per that module's own docstring) — i.e. near Jableh, about 18.5 km south of
Latakia city's own centre, not downtown Latakia. This surfaced directly while picking a "Latakia
city centre" control-point coordinate (§4) — worth flagging since the region name reads as if it
covers the city itself.

**First run (cache miss — real parse):**
- OSM parse+ingest: 9.15s
- Peak RSS: 357,320 KB (349 MB)

**Second run (cache hit, same `.osm.pbf`/classifier/region):**
- OSM parse+ingest: 0.07s (confirms the OSM classified-feature cache still works correctly
  against the new area-producing classifier — same mechanism as before this milestone, just
  validated against real area/hole/coastline output for the first time)

**Feature counts by kind:**

| kind | count |
|---|---|
| airfield | 1 |
| coastline | 4 |
| landcover | 21 |
| named_place | 76 |
| navaid | 8 |
| runway | 2 |
| settlement | 97 |
| water | 10 |

**By (kind, subtype):** `settlement/built_up` 96, `settlement/village` 1, `named_place/village` 72,
`named_place/town` 1, `named_place/city` 1 (DCS `towns.lua`, not OSM), `named_place/None` 2 (DCS
airfield/navaid-derived), `water/lake` 4, `water/river` 5, `water/reservoir` 1, `landcover/forest`
11, `landcover/fields` 5, `landcover/orchard` 3, `landcover/barren` 2.

**`OsmIngestStats` (this build):**
- `vertices_before_simplify`: 7,957 → `vertices_after_simplify`: 2,928 (63% reduction at 30 m
  tolerance)
- `holes_kept`: 0, `holes_dropped_below_min_area`: 0 (no multipolygon in this small region
  happened to carry a hole above the threshold — see the Lake Assad region below for holes)
- `rings_dropped_min_area`: 245 (the 5 ha filter is doing real work — more rings dropped for size
  than kept as landcover/water/built-up, 245 dropped vs. ~118 landcover+water+built_up kept)
- `multipolygon_relations_seen`: 448, `relations_skipped`: 0 — **file-scoped counts** (every
  multipolygon-type relation in the whole filtered `.osm.pbf`, not just this region's clip; both
  region builds below report the identical 448/0 since they parse the same file — expected, not a
  bug)

**Polygon vertex stats:** 123 polygons stored; largest outer ring 86 vertices (well below any
latency-risk threshold).

**`describe_position` timings (300 random points in-region):** mean 4.13ms, p50 4.13ms, p95
5.75ms, p99 6.60ms, max 7.37ms. Far below the M7 full-theatre p99 figure (~800ms) — expected,
this is a 20 km region, not `syria-full`.

## 3. Ad-hoc Lake Assad (Tabqa end) 20km region

Defined in `tools/validate_osm_landcover.py` only (not registered in `build.region`), centred at
(35.85°N, 38.45°E) — point-in-polygon-verified during this validation to fall inside the real OSM
relation "بحيرة الفرات" (`water=reservoir`, the actual Lake Assad / Euphrates Lake relation in the
Syria clip; its outer ring alone has 52,031 raw vertices before simplification).

**First run (cache miss):**
- OSM parse+ingest: 9.08s
- Peak RSS: 401,460 KB (392 MB)

**Feature counts by kind:** landcover 30, named_place 11, settlement 30, water 8.

**By (kind, subtype):** `settlement/built_up` 30, `water/reservoir` 1, `water/river` 6,
`water/river_area` 1, `named_place/dam` 1, `named_place/peak` 1, `named_place/village` 6,
`named_place/city` 1, `landcover/fields` 20, `landcover/orchard` 9, `landcover/forest` 1.

**`OsmIngestStats`:**
- `vertices_before_simplify`: 59,159 → `vertices_after_simplify`: 4,918 (92% reduction — Lake
  Assad's own ring dominates this number)
- `holes_kept`: 15, `holes_dropped_below_min_area`: 88 — real evidence the 5 ha hole filter is
  doing meaningful work at real-data scale (a large reservoir relation has many small islands/
  inlets below 5 ha that correctly get dropped, and 15 real ones above threshold correctly kept
  as `inner_rings`)
- `rings_dropped_min_area`: 87

**Polygon vertex stats:** 62 polygons stored; **largest outer ring 3,359 vertices, largest
outer+holes total 3,602** (Lake Assad's own polygon, simplified from 52,031 raw points — a 93.5%
reduction). This directly answers the plan's Risks & Unknowns item ("record the largest
post-simplification polygon vertex count... if it stays in the tens of thousands, tiling is a
follow-up, not a redesign"): **3,359 is nowhere near the tens-of-thousands range** — no tiling
follow-up needed based on this evidence.

**`describe_position` timings (300 random points in-region):** mean 14.45ms, p50 10.01ms, p95
29.20ms, p99 34.04ms, max 34.45ms. Noticeably higher than `latakia-20km`'s (4-7ms) — expected,
since many query points in this region have a bbox overlapping Lake Assad's large polygon,
triggering its JSON parse + point-in-polygon test (the plan's Risks & Unknowns "very large
polygons... are JSON-parsed and point-in-polygon tested in Python on every call whose bbox
overlaps them"). Still two orders of magnitude below the M7 full-theatre p99 (~800ms) baseline.

## 4. Control points

All four pass:

| control point | real-world coordinate | result |
|---|---|---|
| Relation-derived settlement (see note below) | 35.4132346°N, 35.9521947°E | `inside_settlement = SettlementInfo(name='قاعدة حميميم الجوية', distance_m=0.0, subtype='built_up', ...)` |
| Sea point west of Latakia | 35.55°N, 35.60°E | `nearest_coastline.side == "sea"` (distance 20,559m) |
| Latakia inland point | 35.55°N, 35.95°E | `nearest_coastline.side == "land"` (distance 12,221m) |
| Lake Assad point | 35.85°N, 38.45°E | `nearest_water = WaterInfo(name='بحيرة الفرات', distance_m=0.0, subtype='reservoir', ...)` |

**Deviation from the plan's literal "Latakia city centre" point.** The plan's own control point
("Latakia city centre → non-`None` `inside_settlement`, closes M9's documented relation gap")
assumed Latakia city's own coordinate would land inside the `latakia-20km` region and inside a
mapped settlement polygon there. Neither held: (a) real Latakia city's `place=city` OSM node
(35.5200185°N, 35.7781044°E) is ~18.5 km from the region's actual centre (OSLK-ARP-based, near
Jableh — see §2's note), outside the region's 10 km half-extent entirely; (b) even within the
region, no `place=city`/`town`/`village` *area* exists for any settlement in this extract — only
built-up `landuse` polygons and DCS `towns.lua` name *points*.

Rather than force a coordinate to make the assertion pass, the control point was re-targeted to
what the plan's own "closes M9's documented relation gap" language was actually testing: a point
inside one of `latakia-20km`'s three relation-derived built-up polygons (3 of 96 `settlement/
built_up` rows have `source_ref` starting `relation/`, vs. simple-way for the rest) — verified by
querying which built-up polygons in the built store are relation-sourced, then picking a real
interior point (via point-in-polygon sampling, not a hand-guessed coordinate) inside the largest
one, `relation/16474082`. That relation turns out to be a real, named place: **"قاعدة حميميم
الجوية" (Hmeimim Air Base)**, the Russian air base near Latakia — this is a genuinely stronger
demonstration of the relation-gap fix than an arbitrary point would have been, since it comes back
with a real name where M9's era would have silently skipped it as an unsupported relation.

## 5. Cross-checks against the plan's own investigation numbers

- Substitution 4 (dams): not separately re-measured here (small-region counts would be too sparse
  to compare meaningfully against the plan's whole-Syria-clip 29 named/128 unnamed figure); the
  Lake Assad region did produce one `named_place/dam` row, confirming the mechanism runs on real
  data.
- Substitution 7 (water synonyms): the Lake Assad region's `water/river_area` (from
  `waterway=riverbank`) and `water/reservoir` (from both `natural=water,water=reservoir` and
  `landuse=reservoir`) rows confirm all three legacy-tagging paths fire on real data, not just in
  unit-test fixtures.
- D1's "three of the four city `place` areas in the Syria clip are relations" claim: confirmed
  directionally — `latakia-20km`'s own built-up settlement layer alone has 3 relation-derived
  polygons out of 96, and the whole filtered file reports 448 `multipolygon_relations_seen` (D2's
  precedence rules apply per-ring regardless of relation vs. way origin, so this file-level count
  isn't directly comparable to the plan's "4 total city-place areas, whole Syria clip" figure, but
  is consistent with relations being a real, non-trivial fraction of the assembled area layer).

## 6. Realistic full-region build (bonus, not a Stage 6 requirement)

A second `latakia-20km` build with real `--routes` (`Syria.routes`, 2.25 GB) alongside the same
`--osm-pbf` was started in parallel purely as a smoke check that the new OSM/landcover code
coexists correctly with the unrelated roadnet/junction/terrain stages in one build — not part of
this stage's required deliverables (roadnet parsing alone takes ~10+ minutes against the real
2.25 GB file, unrelated to anything this milestone changed). OSM stage timing from that run's log
matched the standalone tool's figures (9.8s), confirming no interaction effect between this
milestone's OSM changes and the rest of the pipeline.

## What the user should verify in their own full `syria-full` build

- **Real parse time and peak RSS at `syria-full` scale.** This validation's figures (9-10s / 350-
  400 MB for a 20 km region against a small filtered extract) cannot be linearly extrapolated to
  the full theatre with confidence — D4's own estimate (~1-1.5 GB peak, ~2 minutes) is
  extrapolated, not measured, and remains the number to check against the real run.
- **The largest full-theatre polygon's vertex count post-simplification.** This validation found
  3,359 for Lake Assad in isolation; a full-theatre build may assemble a larger relation
  (Tishreen reservoir, Sabkhat al-Jabbul, or a big forest/administrative-adjacent polygon) that
  wasn't exercised here. If any polygon's post-simplification vertex count lands in the tens of
  thousands, that's the signal the plan's Risks & Unknowns names for revisiting the "no tiling
  needed" conclusion.
- **`describe_position` p99 at full-theatre scale** with the new `nearest_coastline`/
  `inside_landcover` queries in the mix — this validation's two new queries added real but small
  overhead (~10-20ms) at small-region scale; full-theatre behaviour (many more, and possibly
  larger, candidate polygons per bbox query) is unmeasured.
- **OSM cache invalidation on the real `syria-theatre.osm.pbf`** — confirm the classifier-version
  bump (1 → 2) correctly forces one full re-parse of the real file (expected, and already the
  documented behaviour), and that job (a)'s new §2.4 pre-filter step produces the RUN.md-documented
  counts at real theatre scale (this validation only confirmed the Syria/Lebanon country-clip
  ratios, not the merged multi-country file).
