# Kola and Caucasus theatre recon (adding the third/fourth theatre entries)

**Date:** 2026-10-05
**DCS version:** not independently re-verified this session (read-only file-tree investigation
via WSL at `/mnt/f/Games/DCS World/Mods/terrains/{Kola,Caucasus}/`; no live DCS/Mission-Scripting
access). File mtimes: Kola 2026-08-10, Caucasus 2025-10-20 (roads) / 2026-08-29 (other) —
consistent with the same install family already used for Syria/Afghanistan's investigations.
**Theatre:** Kola (full pass, no prior registry entries), Caucasus (filling in the registry work
the 2026-10-04 note already did the projection/extent legwork for).

### Question

Following `plans/multi-theatre-afghanistan/plan.md`'s pattern (now built and merged for
Afghanistan), what do `THEATRE_PROJECTIONS`, `REGIONS`, `EXPECTED_TOWN_COUNT`/
`EXPECTED_BEACON_COUNT` need for Kola and Caucasus, and are there any theatre-specific breakages
(DEM coverage, OSM coverage, hardcoded-Syria assumptions) that would make either theatre behave
differently from Afghanistan's now-exercised path?

### Bottom line / blocking findings

**Nothing here blocks starting the same five-stage plan Afghanistan used.** Both theatres are
registry-entry work, not a new design pass — exactly what `multi-theatre-afghanistan/plan.md`'s
"Design confirmation" section predicted. Three small, non-blocking gaps to carry into the plan:

1. Kola has **no count-guard entries yet** (`EXPECTED_TOWN_COUNT`/`EXPECTED_BEACON_COUNT`) —
   confirmed by actually calling the real parsers, which raise `ValueError` naming `'Kola'`
   (see Q4). Caucasus already has both (`1759`/`164`), added when Afghanistan's plan pre-added
   it opportunistically — nothing further needed there.
2. Kola is missing **one DEM tile with a real town in it** (`N71E023`, the Norwegian village
   Tufjord) at the extreme NE corner of the padded envelope — see Q3. Everything else missing is
   open sea.
3. **Both theatres' `tmerc` parameters are provisional** (pydcs cross-check + local beacon-fit
   agreement, no live `coord.LOtoLL` run) — same posture Afghanistan's were before its own Stage 4,
   and the same upgrade path applies.

---

## Q1 — Tmerc projection parameters

### Findings

- **Kola: `central_meridian=21` confirmed, matching the 6°-series expectation and pydcs exactly.**
  — **evidence: reproduced-locally** (beacon-pair least-squares fit, same method validated to
  0.03 m against Syria and <0.01 m against Caucasus in the 2026-10-04 note) — **source:** this
  session's fit against the real `/mnt/f/Games/DCS World/Mods/terrains/Kola/beacons.lua` (69
  beacons, lat 64.95–70.18, lon 14.34–34.49).

  Raw fit (all 69 beacons, `k0` solved independently, not yet rounded):
  ```
  central_meridian=21, scale_factor=0.999600, false_easting=-62702.0018,
  false_northing=-7543624.8566, rms=0.1055 m, max=0.1532 m
  ```
  This floor (~0.11 m RMS) is higher than Syria/Afghanistan/Caucasus's ~0.03–0.05 m — **checked
  and it is not the off-map-navaid effect** (filtering to the 61 `airfield*`-tagged beacons only,
  excluding the 8 `world_*` enroute beacons, gives *worse* RMS, 0.1099 m, not better — see Q1
  "Unresolved" below for the one open question this leaves).

  **Rounding to the nearest metre (`false_easting=-62702`, `false_northing=-7543625`) drops the
  residual to the same floor every other confirmed theatre sits at**: RMS **0.0364 m**, max
  **0.0573 m** across all 69 beacons. This is the same pattern Afghanistan's live check found
  (`2026-10-05-afghanistan-projection-live-check.md`: "the false easting/northing should be
  rounded to the nearest metre when the fit lands within a few centimetres of one — every
  confirmed DCS theatre so far uses round values") — reproduced again here without a live probe,
  since the round value is already known independently.

- **Cross-check against pydcs: exact agreement.** — **evidence:** documented (pydcs source,
  fetched 2026-09-05, already on record in `2026-09-05-m7-kola-square-vs-rectangle-stress-test.md`)
  — **source:** `github.com/pydcs/dcs/dcs/terrain/kola/projection.py`:
  ```
  PARAMETERS = TransverseMercator(
      central_meridian=21, false_easting=-62702.00000000087,
      false_northing=-7543624.999999979, scale_factor=0.9996,
  )
  ```
  pydcs's own float values round to exactly `-62702` / `-7543625` — the same round values this
  session's independent beacon fit converges on. Two independent sources (pydcs's own generation
  pipeline, and this session's beacon-fit) now agree to the metre, the same corroboration tier
  Caucasus had before today.

  **Proposed `THEATRE_PROJECTIONS["Kola"]`:**
  ```
  central_meridian=21, false_easting=-62702.0, false_northing=-7543625.0,
  scale_factor=0.9996, lat_0=0, confidence="provisional"
  ```

- **Caucasus: restating the 2026-10-04 note's numbers and independently re-deriving them this
  session gives the same answer.** — **evidence: reproduced-locally**, a second independent run
  of the same method — **source:** this session's fit against
  `/mnt/f/Games/DCS World/Mods/terrains/Caucasus/Beacons.lua` (164 beacons):
  ```
  central_meridian=33, scale_factor=0.9996, false_easting=-99517.0004,
  false_northing=-4998115.0339, rms=0.0433 m, max=0.0814 m (unrounded)
  ```
  With the round values (`-99517`/`-4998115`, matching pydcs's `-99516.9999999732`/
  `-4998114.999999984` to sub-millimetre): **rms=0.0385 m, max=0.0655 m** — same floor as every
  other theatre. (The 2026-10-04 note reported "<0.01 m" for this same comparison; this session's
  number is the RMS over all 164 raw beacon pairs rather than whatever subset/metric produced that
  figure — not a contradiction, just a different aggregate; both land in the same
  "effectively confirms pydcs's published numbers" conclusion.) Caucasus's `THEATRE_PROJECTIONS`
  entry does not exist in the registry yet — nothing in the 2026-10-04 note's or this session's
  findings changes what it should be from what was already on record.

### Confidence

Both **provisional**, not `confirmed` — no live `coord.LOtoLL` run exists for either theatre.
Kola and Caucasus are *lower*-risk than Afghanistan was pre-Stage-4, because both have a pydcs
cross-check (a second source) agreeing to the metre; Afghanistan had no second source at all and
still turned out correct in Stage 4. Recommend the identical upgrade path: a Windows-side
`coord_probe.lua` run (unmodified, already theatre-agnostic) against each terrain, same pass
criterion (~0.1 m residual ceiling) used for Afghanistan.

---

## Q2 — Region rectangle (derived the way `afghanistan-full` was)

### Method

Same as the Afghanistan plan's Stage 2: project `towns.lua` into DCS x/z via each theatre's
(round-valued) tmerc fit, union with `beacons.lua`'s native x/z, pad ±30 km/side, derive
centre/half-extents and the WGS84 envelope via `RegionDefinition.to_wgs84_envelope`'s own corner
method.

**Caucasus-specific check, repeating the 2026-10-04 note's warning on a slightly different
question (region bbox, not projection fit) — confirmed it still applies:** unioning `towns.lua`
with the *full* beacon set (including the 13 off-map `world_*` enroute navaids already identified)
inflates the z-range from `[191968, 927038]` to `[-379811, 929610]` — a **570 km** phantom
southward extension. Unioning with the **airfield-tagged beacon subset only** (`bid.startswith
("airfield")`) gives back exactly the towns-only bound (towns.lua already dominates the filtered
beacon bound on every edge) — **evidence: reproduced-locally**, this session's probe script.

**Kola does not show this problem** — union with the *full* 69-beacon set (8 `world_*`, 61
`airfield*`) gives the identical bound as union with the airfield-only subset, and both equal the
towns-only bound exactly. Same conclusion the 2026-10-04 note already reached for Afghanistan
("Afghanistan's beacon set does not show this problem to the same degree") — Kola is a second
confirmation that the off-map-navaid inflation is Caucasus-specific (it borders many distant
Russian/Ukrainian cities with real-world VORs; Kola and Afghanistan's neighbours apparently don't
place enough off-map beacons to matter here). — **evidence: reproduced-locally.**

### Results

**Kola** (towns n=787, beacons n=69; union with towns dominating):
```
raw union  x: [-300,145.9, 356,393.5]   z: [-498,256.1, 699,635.2]
padded     x: [-330,145.9, 386,393.5]   z: [-528,256.1, 729,635.2]
footprint: 716.5 x 1,257.9 km  (aspect ratio ~0.57, i.e. elongated ~1.75x N-S vs E-W)
centre_x=28,123.8  centre_z=100,689.6  half_extent_x_m=358,269.7  half_extent_z_m=628,945.7
WGS84 envelope: lat [64.1203, 71.0246]  lon [8.0852, 42.3509]
```
The elongation (~1.75x) matches the already-recorded 2026-09-05 stress-test note's two independent
estimates (ED/Orbx marketing ~1.4x, pydcs 9-airfield bbox ~1.67x) closely enough to treat as the
same finding re-derived with more points (787 towns + 69 beacons vs. 9 airfields) — this is the
`RegionDefinition` rectangular half-extent case that stress test argued for in the first place.

**Caucasus** (towns n=1759, airfield-beacons n=100; union with towns dominating):
```
raw union  x: [-372,138.2, 39,455.0]    z: [191,968.0, 927,037.7]
padded     x: [-402,138.2, 69,455.0]    z: [161,968.0, 957,037.7]
footprint: 471.6 x 795.1 km  (aspect ratio ~0.59, i.e. elongated ~1.69x)
centre_x=-166,341.6  centre_z=559,502.8  half_extent_x_m=235,796.6  half_extent_z_m=397,534.9
WGS84 envelope: lat [40.8298, 45.7123]  lon [36.1314, 46.3988]
```
Elongation (~1.69x) matches the 2026-10-04 note's airfield-filtered beacon-only estimate (~1.8x,
368.6 x 664.6 km) closely — towns.lua widens the bound somewhat (471.6 x 795.1 vs 368.6 x 664.6)
but the aspect ratio and "meaningfully non-square" conclusion are the same.

### Cross-check: `nodesMapBorders` exists for Kola too, in a different file than expected, and it
re-confirms (not contradicts) the already-established falsification

Kola's `entry.lua` has **no** `nodesMapBorders` field (same as Afghanistan). But
`MissionGenerator/nodesMap.lua` does:
```
theatre.nodesMapBorders = { -285184.000000, -557056.000000, 393216.000000, 884736.000000 }
```
This is **wider than** this session's towns+beacons point-cloud bound on every edge (x:
`[-285184, 393216]` vs. ours `[-300145.9, 356393.5]` — min less negative, max larger; z:
`[-557056, 884736]` vs. ours `[-498256.1, 699635.2]` — same pattern, wider on both ends). This is
exactly the shape the Syria investigation already found and named a falsification
("mission-generator working envelope, not a terrain bound" —
`2026-09-05-m7-syria-theatre-extent.md`, restated in the 2026-10-04 note's Q1): a plausible-looking
field that oversizes the real terrain. Finding it in a different file than `entry.lua` this time
doesn't change the conclusion — **do not use it** for the region definition, same as before. —
**evidence: reproduced-locally** (field read directly, comparison arithmetic this session).

---

## Q3 — DEM coverage

Checked by computing the exact set of 1°×1° SRTM-named tiles the padded WGS84 envelope implies,
and diffing against what's actually staged on disk in the **main checkout** (read-only; nothing
written there).

### Kola — one real gap, 85 non-issues

`data/raw/dem/kola-full/`: **194** `.hgt` files present (confirmed by `find`, matches the task's
stated count), plus 11 leftover `.zip` source archives (`Q32v2.zip`…`R37v2.zip` — viewfinderpanoramas'
own DEM3 block names at this latitude band, residual from extraction, not `.hgt` data).

The padded envelope (lat 64.12–71.02, lon 8.09–42.35) implies **280** 1°×1° tiles. **86 are
missing.** Checked each missing tile's 1°×1° box against `towns.lua`'s 787 real entries:

- **85 of 86 have zero `towns.lua` entries** — consistent with open sea (Norwegian Sea to the
  west, Barents Sea to the north, and simple padding overshoot past the theatre's real eastern
  edge: `towns.lua`'s own lon range tops out at 39.51°, while the padded envelope's lon max is
  42.35° purely from the +30 km DCS-space pad translating non-linearly through the projection —
  there is no real land there to be missing elevation for).
- **One tile, `N71E023`, has exactly one town in it: `Tufjord` (71.0051°N, 23.9090°E).** This is a
  small Norwegian coastal village right at the theatre's extreme NE corner — a real, if minor, DEM
  gap. — **evidence: reproduced-locally** (tile/town coincidence check, this session's probe
  script).

### Kola — `.hgt` format at this latitude: square, no blocker

Checked the specific concern the task named: does a DEM3-sourced tile at 64–71°N parse as a
square grid the same way SRTM1/SRTM3 tiles do further south? **Yes, no change needed.** Three
sampled tiles (`N64E009`, `N70E020`, `N71E024`) are all exactly **2,884,802 bytes = 1201×1201×2**
— the same SRTM3 (3 arc-second) byte-for-byte layout `elevation/dem.py`'s `SrtmTile.from_file`
already expects, confirmed by actually running it:
```
SrtmTile.from_file(...N70E020.hgt) -> size=1201, sw_lat=70.0, sw_lon=20.0
```
`from_file`'s existing file-size-derived sizing logic (not a hardcoded 1201/3601) needed zero
changes. The sample-count-stays-square-while-physical-width-shrinks property of `.hgt` files at
high latitude (longitude degrees cover less real distance near the poles, but the file format
doesn't encode that — it's still 1201 columns regardless of latitude) means there is **no
blocking finding here** — the task's hypothesis ("if a Kola tile is not square or not
1201/3601, that is a blocking finding") does not materialize. — **evidence: reproduced-locally.**

### Caucasus — confirms the 2026-10-04 note's "Black Sea corner" finding, now against the tighter
derived envelope

`data/raw/dem/caucasus-full/`: **123** `.hgt` files (matches the task's stated count and the
2026-10-04 note's DEM3-block-derived figure exactly), no leftover zips.

Against the **original wider** DEM3-block envelope (`K36`–`L38`, lat 40–48/lon 30–48, 144 possible
tiles), 21 are missing — already established. Against **this session's tighter, towns+beacon-
derived** envelope (lat 40.83–45.71, lon 36.13–46.40, 66 tiles implied), only **8** are missing,
all eight (`N42E036`–`N44E036`, the NW corner) confirmed to contain **zero** `towns.lua` entries —
i.e. genuinely open Black Sea, not a land gap. The 65 tiles present but outside this tighter
envelope are simply the original wider block's margin — Caucasus's staged DEM already
over-covers the recommended region rectangle, nothing missing to fetch. — **evidence:
reproduced-locally.**

---

## Q4 — Parsers

All four parsers run read-only against the real installed files from this worktree.

| | Kola | Caucasus |
|---|---|---|
| `towns.lua` path/case | `map/towns.lua` (lowercase, same as Syria/Afghanistan) | `Map/towns.lua` (capital M, as 2026-10-04 note already found) |
| `beacons.lua` path/case | `beacons.lua` top-level (lowercase, same as Syria/Afghanistan) | `Beacons.lua` top-level (capital B) |
| towns count | **787** | **1759** (confirmed, matches existing `EXPECTED_TOWN_COUNT["Caucasus"]`) |
| beacons count | **69** | **164** (confirmed, matches existing `EXPECTED_BEACON_COUNT["Caucasus"]`) |
| `.routes` filename | `Kola.routes` (68.2 MB) | `Caucasus.routes` (980.5 MB) |
| `.rn4` filename | `Kola.rn4` (255.3 MB) | `Caucasus.rn4` (203.5 MB) |

- **`dcs_data.towns.parse_towns_lua(path, "Kola")` and `parse_beacons_lua(path, "Kola")` both
  raise `ValueError`** today — correctly, per the per-theatre dict's own fail-loudly design —
  naming the theatre exactly: `"No EXPECTED_TOWN_COUNT entry for theatre 'Kola' -- add one before
  parsing this theatre's towns.lua"` (and the equivalent for beacons). This is **expected
  behavior, not a bug** — Kola's counts (787 towns, 69 beacons) just need to be added to the two
  dicts before the parser will run, exactly the mechanical step the Afghanistan plan's Stage 1
  already established the pattern for. — **evidence: reproduced-locally** (ran the real
  parser, not a reimplementation).
- **`dcs_data.towns.parse_towns_lua(path, "Caucasus")` and `parse_beacons_lua(path, "Caucasus")`
  both parse cleanly** (1759/164), since Afghanistan's plan already pre-added Caucasus's counts
  to both dicts. Nothing further needed here.
- **`roadnet.routes.iter_routes` and `roadnet.rn4.parse_header` both work unmodified on both
  theatres**, zero sync-loss on a 20-route partial walk, same container format Syria/Afghanistan/
  Caucasus (2026-10-04 pass) already share:
  - Kola `.rn4`: `field_a=5`, 17-entry string table (`primary`, `viaduct_primary`, …,
    `viaduct_rail_10`), `topology_table_offset=315`.
  - Caucasus `.rn4`: `field_a=5`, 14-entry string table (`road`, `rdb`, …, `vpp_border_vbig`),
    `topology_table_offset=266`.
  — **evidence: reproduced-locally.**
- **`build/pipeline.py`'s roadnet-ingest stage already derives its `Source.name`/stage-label from
  `routes_path.name`** (checked by reading the current file, not from the 2026-10-04 note) — the
  Afghanistan plan's Stage 1 fix for the hardcoded `"Syria.routes"` string has already landed, so
  neither theatre will mislabel roadnet provenance.

---

## Q5 — OSM coverage

Checked against each theatre's padded WGS84 envelope (Q2) using `osmium fileinfo -e` (available
on this machine as a CLI binary; the `osmium` *Python* module is not installed, only the CLI
needed for a bbox check) against every staged `.osm.pbf`'s own header/data bounding box — a
direct read of each file's own declared extent, not an inference from the extract's name.

### Kola — fully covered, no missing country/district

Staged: `finland`, `northwestern-fed-district` (Russia), `norway`, `sweden` (all `.osm.pbf`,
`data/raw/osm/kola-full/`). Needed envelope: lat 64.12–71.02, lon 8.09–42.35.

- `northwestern-fed-district-261003.osm.pbf` data bbox: lon **10.29–69.99**, lat **51.57–83.74**
  — comfortably covers the envelope's eastern half (up to lon 42.35) and northern edge (lat
  71.02).
- `norway-261003.osm.pbf` data bbox: lon **-20.92–38.0**, lat **53.32–83.74** — covers the western
  edge (lon 8.09) and, combined with the Russia extract above, the two together fully span the
  needed lon range with overlap in the middle.
- Finland/Sweden not individually checked beyond confirming they're staged — Norway + the Russia
  extract already fully bound the envelope on their own, so Finland/Sweden are extra coverage
  (correctly staged for a Scandinavia-spanning theatre, not strictly load-bearing for the bbox
  check). — **evidence: reproduced-locally** (`osmium fileinfo -e` output, this session).

### Caucasus — confirms the 2026-10-04 note's conclusion, and now shows North-Caucasus-FD is
load-bearing (not just "cheap to leave in")

Staged: `armenia`, `azerbaijan`, `georgia`, `north-caucasus-fed-district`, `south-fed-district`,
`turkey` (the Turkey gap the 2026-10-04 note flagged and the user already closed by reusing the
Syria-build extract). Needed envelope: lat 40.83–45.71, lon 36.13–46.40.

- `north-caucasus-fed-district-261003.osm.pbf` data bbox: lon **37.21–54.14**, lat **36.57–47.62**
  — this session's wider (towns-inclusive) envelope reaches lon 46.40, which **is** inside this
  extract's bbox. The 2026-10-04 note left open whether this extract was "actually needed, or
  whether its one real signal (the `Grozny` beacon) is purely an off-map enroute navaid" —
  this session's region-rectangle derivation answers that: the envelope's own NE corner genuinely
  reaches into North-Caucasus-FD territory on its own, independent of any single beacon. Keep it
  staged; it is load-bearing, not merely low-cost. — **evidence: reproduced-locally.**
- `south-fed-district-261003.osm.pbf` data bbox: lon **30.67–54.14**, lat **36.57–55.57** — fully
  covers the envelope.
- `azerbaijan-261003.osm.pbf` data bbox: lon **37.21–54.14**, lat **36.57–46.99** — covers the
  envelope's eastern edge (lon 46.40).
- Armenia/Georgia/Turkey not re-checked by bbox this session — already resolved in the 2026-10-04
  note (Georgia/Armenia/Azerbaijan core coverage, Turkey gap identified and closed).

No additional missing country/district found for either theatre.

---

## Q6 — Syria/Afghanistan-specific breakage elsewhere

Grepped `world-model/src`, `body-layer/src`, `mission-interpreter/src` for literal `"Syria"`/
`'Syria'` and `"Afghanistan"`/`'Afghanistan'` string matches (not case-insensitive comment
mentions, which are harmless prose).

- **One real hardcode, already known and explicitly out of scope:**
  `raster/registration.py`'s `THEATRE_RASTER_REGISTRATIONS` has only a `"Syria"` entry. The
  Afghanistan plan already scoped this out deliberately ("Nothing in the serving path... consumes
  `raster/registration.py` — only two diagnostic tools do... An Afghanistan sortie loses nothing a
  pilot would notice") — the same reasoning applies unchanged to Kola and Caucasus; neither gets a
  raster registration from this investigation, and neither needs one for anything a pilot would
  notice.
- **Everything else matching the grep is a docstring/comment reference** (e.g.
  `belief/mission_phase.py`'s docstring using `"Afghanistan"` as an example value, `ingest_roadnet.py`
  referring to "the real `Syria.routes` file" descriptively) — not a code path that would behave
  differently for Kola/Caucasus.
- **Body-layer's theatre resolution (Afghanistan plan Stage 5) is already theatre-generic**:
  `logger.py` derives `world_model_db = args.world_model_dir / f"{theatre.lower()}-full.sqlite"`
  and guards with `load_only_region` — this resolves to `kola-full.sqlite`/`caucasus-full.sqlite`
  automatically, matching the staged raw-data directory naming (`kola-full`, `caucasus-full`)
  already on disk. No change needed for either new theatre.
- **`mission["theatre"]` string match not independently re-verified this session** (same caveat
  the Afghanistan plan carried for its own Stage 2 pre-check) — Kola's `entry.lua` sets `['id'] =
  "Kola"`, Caucasus's presumably `"Caucasus"` (not directly re-checked this session, but it's the
  terrain folder name in both cases, same convention already confirmed for Syria/Afghanistan).
  Recommend the same cheap pre-check (open a saved `.miz` for each theatre, read `mission["theatre"]`
  directly) before Stage 5's code depends on the exact string for either.

---

### Reproducible Test

All probe scripts for this session are throwaway (scratch area, not committed — per the
project's `research/`-vs-`tools/` convention, these are one-off and the logic is restated in full
below so they can be rebuilt):

1. **Beacon-pair tmerc fit** — identical method to the 2026-10-04 note's (pure Python +
   `pyproj.Transformer`, no numpy/scipy): parse `beacons.lua`'s multi-line blocks for
   `position`/`positionGeo`/`beaconId`, project each `positionGeo` through a unit-scale tmerc at
   each UTM-zone-centre candidate `central_meridian`, solve the shared-`k0` linear least squares
   independently on each axis, average the two `k0` estimates, report RMS/max residual. Run
   against `Kola/beacons.lua` and `Caucasus/Beacons.lua` directly.
2. **Region bbox** — parse `towns.lua` (same regex `dcs_data.towns` uses), project through the
   now-rounded tmerc fit, union with native-x/z `beacons.lua` points (airfield-tagged subset for
   Caucasus, full set for Kola — see Q2), pad ±30,000 m per side, compute centre/half-extent and
   WGS84 corner envelope via the same four-corner method `RegionDefinition.to_wgs84_envelope`
   already implements.
3. **DEM tile diff** — compute the expected `N<lat>E<lon>.hgt`-style tile-name set for a given
   lat/lon envelope (`floor`/`ceil` to whole degrees), diff against `find <dem-dir> -iname
   "*.hgt"`'s real output, then cross-reference any missing tile's 1°×1° box against parsed
   `towns.lua` entries to distinguish "open sea" from "real gap."
4. **Parser checks** — `dcs_data.towns.parse_towns_lua`, `dcs_data.beacons.parse_beacons_lua`,
   `roadnet.routes.iter_routes` (20-route partial walk via `itertools.islice`), `roadnet.rn4.
   parse_header` (via `mmap`), run directly against the real installed files, using the project's
   own parser code (not a reimplementation) via `PYTHONPATH=world-model/src`.
5. **OSM coverage** — `osmium fileinfo -e <file>.osm.pbf` (CLI, already on this machine) against
   each staged extract, compared against the region bbox from step 2.

---

### Possible Approaches

1. **Register Kola exactly the way Afghanistan was registered**, following
   `multi-theatre-afghanistan/plan.md`'s five stages with Kola's own numbers from this note:
   `EXPECTED_TOWN_COUNT["Kola"]=787`, `EXPECTED_BEACON_COUNT["Kola"]=69`,
   `THEATRE_PROJECTIONS["Kola"]` (Q1, `confidence="provisional"`), `REGIONS["kola-full"]` (Q2).
2. **Register Caucasus the same way** — its count-guard entries already exist; it needs
   `THEATRE_PROJECTIONS["Caucasus"]` and `REGIONS["caucasus-full"]` added, both already fully
   specified by this note and the 2026-10-04 note together.
3. **Decide whether to fetch the single missing Kola DEM tile (`N71E023`) before building**, or
   accept the gap — it's one coastal village at the theatre's extreme edge, not a load-bearing
   location, so accepting the gap (same posture as Syria/Afghanistan's own "padded lower bound,
   not corner-verified" regions) seems reasonable, but it's cheap enough to fetch if Architect
   would rather not carry a known hole.
4. **Run both theatres' Stage-4-equivalent live `coord_probe.lua` check** on the Windows box at
   the same time if a session is already being spent there — the script is unmodified and
   theatre-agnostic, so both could be probed in one sitting rather than two separate trips.
5. **Do not re-investigate `nodesMapBorders`** as a possible region-bound source for any future
   theatre — this is now the second theatre (after Syria) where it's been found wider than the
   real point-cloud bound. Worth promoting from "falsified for Syria" to "falsified pattern,
   recurs across theatres" in whichever doc Architect judges should carry that generalization.

### Unresolved

- **Why Kola's raw (unrounded) beacon fit sits at a ~0.11 m RMS floor instead of the ~0.03–0.05 m
  floor every other theatre's raw fit lands at** — checked and ruled out that it's the off-map
  `world_*` beacons specifically (filtering them out makes the raw fit *worse*, not better). The
  rounded-value fit recovers the normal floor (0.036 m), so this doesn't block registering Kola's
  parameters, but the mechanism behind the raw-fit gap is not explained — possibly just fewer
  beacons (69 vs. Syria's 151/Caucasus's 164) giving a noisier float-precision estimate before
  rounding absorbs it. Evidence that would resolve it: refitting with more decimal-precision
  arithmetic, or simply not caring, since the live-probe upgrade path doesn't depend on this
  explanation.
- **Neither theatre's `tmerc` parameters are live-`coord.LOtoLL`-confirmed** — both are
  provisional on the pydcs-cross-check-plus-beacon-fit tier, one step better-evidenced than
  Afghanistan was pre-Stage-4 (which had no second source at all and still needed the live check
  to catch Afghanistan's uniform 5 cm offset before rounding). Evidence that would resolve it: the
  same Windows-side `coord_probe.lua` run, once per theatre.
- **`mission["theatre"]`'s exact string for Kola/Caucasus was not independently re-checked against
  a real saved `.miz`** this session (inferred from the terrain folder name / `entry.lua`'s `id`
  field, same convention as every other theatre, but not opened and read directly). Evidence that
  would resolve it: the same cheap pre-check the Afghanistan plan's Stage 2 used.
- **Finland/Sweden's OSM extracts weren't individually bbox-checked** (Q5) — Norway + the Russia
  Northwestern Federal District extract already fully bound Kola's envelope on their own, so this
  is a completeness gap in the *investigation*, not a known gap in the *data* (both are staged and
  presumably correct, just not independently verified by this session's `osmium fileinfo` pass).
