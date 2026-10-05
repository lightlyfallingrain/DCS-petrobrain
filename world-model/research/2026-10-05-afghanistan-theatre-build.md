# Afghanistan theatre: build and Stage 2 pre-check results

**Date:** 2026-10-05
**DCS version:** not independently re-verified this session (no live DCS/Mission-Scripting
access this session either -- see the 2026-10-04 recon note's own version caveat). Afghanistan
file mtimes 2026-08-30, consistent with the install this plan's recon session already inspected.
**Theatre:** Afghanistan

### Context

`plans/multi-theatre-afghanistan/plan.md` Stages 2 and 3. Builds on
`world-model/research/2026-10-04-multi-theatre-afghanistan-caucasus-recon.md` (the provisional
`tmerc` fit, the towns.lua/beacons.lua union method, the OSM/DEM input lists).

### Stage 2 pre-check: `mission["theatre"]` string match

**Confirmed, independently, against a real `.miz`** (not a blank Mission Editor save -- a real
campaign mission was available): `/home/sg/winHome/Saved Games/DCS/Missions/Campaigns/en/
Mi-24P_-_The_Dawn_of_the_Soviet_Afghan_War/Mi-24P - The Dawn of the Soviet Afghan War/
Mission 02-Bagram.miz`, read-only, via `zipfile`/regex over the `mission` entry:

```
["theatre"] = "Afghanistan"
```

Exact match (case included) against `coordinates.projections.THEATRE_PROJECTIONS`'s registry
key `"Afghanistan"`. This closes Stage 2's pre-check -- no code depends on an assumed string any
more. (For the record, the same campaign's other 13 missions and the "Hind Deployment 1.0"
campaign's `.miz` files were reported, not independently re-opened here, to carry
`"Afghanistan"` and `"Caucasus"` respectively.)

### Stage 3: `afghanistan-full` build

**Job (a) — OSM dataset.** Six country extracts already staged
(`data/raw/osm/afganistan-full/{afghanistan,iran,pakistan,tajikistan,turkmenistan,
uzbekistan}-261003.osm.pbf`). Clip bbox from `tools/derive_m9_osm_clip_bbox.py afghanistan-full`:
`59.8920,28.4585,75.5807,39.2511` (west,south,east,north) -- the `afghanistan-full` region's own
`to_wgs84_envelope()` plus the script's standard +0.3 deg safety pad. Ran `osmium extract
--strategy=smart` per country, `osmium merge`, then `osmium tags-filter` against the committed
`tools/osm_tags_filter.txt` (same filter Syria's job (a) uses). Result:
`afghanistan-theatre.osm.pbf`, 7,493,892 nodes / 279,134 ways / 6,806 relations -- 16.1% of the
merged-unfiltered file's nodes, 5.6% of its ways (Syria's own filter pass was ~13-29%/~3-6%,
same order).

**Job (b) — world model build.**

```
.venv/bin/python tools/build_world_model.py afghanistan-full \
    --towns   "/mnt/f/Games/DCS World/Mods/terrains/Afghanistan/Map/towns.lua" \
    --beacons "/mnt/f/Games/DCS World/Mods/terrains/Afghanistan/beacons.lua" \
    --routes  "/mnt/f/Games/DCS World/Mods/terrains/Afghanistan/roads/Afghanistan.routes" \
    --srtm-dir /mnt/e/DCS-petrobrain/world-model/data/raw/dem/afganistan-full/ \
    --osm-pbf  /mnt/e/DCS-petrobrain/world-model/data/raw/osm/afganistan-full/afghanistan-theatre.osm.pbf \
    --out /mnt/e/DCS-petrobrain/world-model/data/world-model/afghanistan-full.sqlite
```

**Result (real build, ~82 minutes end to end -- per-stage timings from the build log:
towns.lua 0.1s, beacons.lua 0.0s, OSM overlay 85.9s, `Afghanistan.routes` 320.2s, road
junctions **1751.1s (~29.2 min)**, SRTM elevation grid 136.8s, terrain semantics (ridge/valley)
**2640.2s (~44.0 min)** -- the last two stages dominate, as they did for `syria-full`):**

```
Built /mnt/e/DCS-petrobrain/world-model/data/world-model/afghanistan-full.sqlite
  airfield: 7
  junction: 196
  landcover: 24417
  named_place: 23595
  navaid: 49
  ridge: 634867
  road: 1590
  settlement: 25774
  valley: 551657
  water: 12189
```

`coastline` is **absent from the summary** (the dict only gets a key for a kind that occurs at
least once) -- i.e. 0, exactly as expected for a landlocked theatre (main-loop amendment
2026-10-05). Every other §3.5-required kind (`road`, `junction`, `settlement`, `named_place`,
`water`, `landcover`) is non-zero. `osm stats`' own `coastline_features=0` confirms the same
thing explicitly rather than by absence.

Stats worth recording:
- `beacon stats`: `airfield_groups=7, runway_features=0, airfields_with_runway_axis=0,
  airfields_with_centroid_only=7` -- Afghanistan's beacons give every one of its 7 airfield
  groups a centroid but no derivable runway axis (same shape as some of Syria's own airfields;
  not itself a new finding).
- `roadnet stats`: `routes_found_whole_file=1590, routes_in_region=1590, resync_events=1590,
  sync_loss_events=22, bytes_covered=996609990` -- the full ~1 GB `Afghanistan.routes` file was
  read (`996,609,990` of `1,001,016,304` bytes; the remainder is trailing container padding/
  footer, same pattern as Syria's own roadnet ingest), all 1,590 routes fell inside the region
  (expected -- the region *is* the whole theatre), 22 resync events is a small fraction of 1,590
  routes and in the same order as what the M5 byte-decode note already documents as a normal
  property of the scan-forward container format, not a new defect.
- `srtm stats`: `points_expected=5721822, points_sampled=5721763, points_void_or_uncovered=59,
  tiles_used=158` of the 288 staged tiles -- only the 158 tiles the padded region's 500 m grid
  actually samples were opened; 59 void/uncovered points out of 5.72M (0.001%) is noise-level,
  not a coverage gap worth investigating.
- Stage 8 (terrain semantics, ridge/valley) **ran** here, unlike `syria-full`'s own RUN.md
  §3.3 table which says it "skipped" without `--probe-output` -- a later milestone
  (landform-geomorphons) generalized ridge/valley derivation to run off the primary SRTM grid
  directly, not only off a live-mission probe; RUN.md's stage table predates that and is now
  stale on this one point (not fixed here -- out of this plan's scope, flagged for a future
  RUN.md pass).

**Spot-check (Kabul, lat 34.5456 lon 69.2075 -- near the city centre, not the airfield):**
`tools/describe_position.py ... Afghanistan --latlon 34.5456 69.2075` resolves to
`x=80545.7, z=269808.3`, elevation `1792.2m` (real-world Kabul is ~1,791 m -- strong agreement,
and a check on more than just the beacon-fit's own self-consistency, since SRTM elevation
depends on the x/z landing on the correct ground cell, not on the fit's output at all).
`nearest_settlement`/`inside_landcover` resolve to `"built_up"`; `named_places_within_radius`
lists "Kabul" (OSM city, 2.93 km), "Kabul" (DCS town, 3.51 km), and "Bibi Mahroo hill" (OSM
peak, 2.53 km) -- all real, correctly-placed Kabul-area features; `nearest_airfield` is "Kabul"
at 3.91 km via beacon centroid; `navaids_within_radius` lists the real Kabul TACAN (OKB) and
VOR/DME (KBL) beacons. Everything geographically coherent.

### Risks / open items carried forward (unchanged from the 2026-10-04 recon note)

- Afghanistan's `tmerc` parameters remain `confidence="provisional"` until Stage 4's live
  `coord.LOtoLL` probe (user task, Windows DCS box) -- not attempted this session.
- `afghanistan-full`'s half-extents are a point-cloud lower bound (towns.lua + beacons.lua
  union), not a corner-verified terrain edge.
- `tools/probe_surface5_elevation.py`'s quadratic-ish blowup on `Afghanistan.surface5` is a real,
  unfixed tool-performance bug (effort/value call, not pursued) -- flagged again so it isn't
  silently forgotten.
