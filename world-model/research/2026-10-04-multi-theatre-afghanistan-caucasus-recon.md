# Multi-theatre recon: Afghanistan (primary) and Caucasus (extent-only)

**Date:** 2026-10-04
**DCS version:** not independently re-verified this session (no live DCS/Mission-Scripting
access — this was a read-only file-tree investigation via WSL, `/mnt/f/Games/DCS World/
Mods/terrains/<Theatre>/`). Syria's already-confirmed DCS version is 2.9.29.27278 per
`2026-09-02-m0-dcs-install.md`; Afghanistan/Caucasus file mtimes are 2026-08-30 and
2025-10-20/2026-08-29 respectively, consistent with the same install family but not
independently pinned to a version string here.
**Theatre:** Afghanistan (primary pass), Caucasus (lighter, extent-only pass)

### Question

Backlog item "Multi-theatre support" (`world-model/ROADMAP.md`, raised 2026-09-13):
resolve, for Afghanistan and Caucasus, (1) true theatre extent in DCS x/z and WGS84, (2)
the resulting padded WGS84 bbox and the exact SRTM/DEM3/Geofabrik download lists, (3)
whether the existing towns/beacons/.routes/.rn4 parsers work unmodified, (4) whether
viewfinderpanoramas DEM3 covers Kola (66–70°N) — **this question was separately answered
and confirmed by the user mid-investigation; see "Q4" below.**

### Base

Worktree `worktree-agent-a99be6f0b560e05d5` off `main` @ `28f8aee`. DCS install reachable
read-only at `/mnt/f/Games/DCS World/Mods/terrains/{Afghanistan,Caucasus}/`.
`world-model/.venv` does not exist in this worktree (gitignored); all probes below ran
against the main checkout's venv (`/mnt/e/DCS-petrobrain/world-model/.venv/bin/python3`,
read-only interpreter invocation — no files written there) or `/usr/bin/python3` stdlib-only.

---

## Q1 — True theatre extent

### Findings

- **Both theatres' `entry.lua` give no usable extent.** Afghanistan's has no
  `nodesMapBorders` field at all; Caucasus's does (`{-418619.1875, 113728.15625,
  26382.5, 943187.0625}`, minX/minZ/maxX/maxZ) but this is the same field the Syria
  investigation (`2026-09-05-m7-syria-theatre-extent.md`) **falsified** as a mission-
  generator working envelope, not a terrain bound — not reused here. — **evidence:**
  reproduced-locally — **source:** both theatres' `entry.lua`, read directly.

- **Neither theatre is in `pydcs`'s terrain list** (checked via GitHub API listing of
  `dcs/terrain/`: `caucasus, falklands, germany, kola, marianaislands, nevada, normandy,
  persiangulf, projections, sinai, syria, thechannel` — no `afghanistan`). Caucasus *is*
  present (`central_meridian=33, false_easting=-99516.9999999732,
  false_northing=-4998114.999999984, scale_factor=0.9996`). — **evidence:** documented
  (pydcs source, fetched this session) for Caucasus; Afghanistan has **no pydcs source at
  all** — pydcs predates ED's Afghanistan release. — **source:**
  `github.com/pydcs/dcs/dcs/terrain/caucasus/projection.py`.

- **Both theatres' `tmerc` projection parameters were independently derived this session
  by least-squares-fitting `beacons.lua`'s `position`↔`positionGeo` pairs, and the method
  is validated to 0.03 m against Syria's already-live-confirmed parameters before being
  trusted on new theatres.** — **evidence: reproduced-locally.** Method: for each
  candidate `central_meridian` from the standard UTM-zone-centre series (odd multiples of
  3, spaced 6° — the series Syria=39, Caucasus=33, Kola=21 already sit on), project every
  beacon's `positionGeo` through a unit-scale (`k0=1,x0=0,y0=0,lat_0=0`) tmerc, then solve
  the shared-scale-factor linear least squares (`x = k0·N + false_northing`,
  `z = k0·E + false_easting`) via hand-derived normal equations (no numpy/scipy available
  in this worktree). **Validation run against Syria's 151 beacons reproduced pydcs's
  confirmed Syria parameters to 0.03 m RMS** (`central_meridian=39, scale_factor=0.9996,
  false_easting=282800.998, false_northing=-3879865.948` vs. confirmed
  `282801.00000003993` / `-3879865.9999999935`). Run against **Caucasus's 164 beacons**,
  it independently reproduced pydcs's *already-known* Caucasus parameters to <0.01 m
  (`central_meridian=33, scale_factor=0.9996, false_easting=-99517.0014,
  false_northing=-4998115.0030` vs pydcs's `-99516.9999999732` / `-4998114.999999984`) —
  a second, independent cross-check of the method using a case whose answer was already
  known from a different source. The method was then applied to **Afghanistan's 49
  beacons**, for which no other source exists:

  **Afghanistan `tmerc` parameters (provisional, not pydcs-sourced, not yet confirmed
  against a live `coord.LOtoLL` run):**
  ```
  central_meridian=63, scale_factor=0.9996,
  false_easting=-300149.9912, false_northing=-3759656.9499
  ```
  Fit RMS 0.03 m against the 49 beacon pairs (same residual floor as the Syria/Caucasus
  validation runs, i.e. consistent with float-rounding noise, not a poor fit).

  **Caveat carried over from M1 (`2026-09-03-m1-coordinate-transform-verification.md`
  Finding 2), unavoidable here too:** `beacons.lua`'s `positionGeo` is itself computed by
  DCS's *own* internal projection at terrain-build time, not an independent real-world
  source — so this fit reproduces DCS's internal geodesy with very high fidelity (as the
  Syria/Caucasus validation shows), but is **not** equivalent to a live `coord.LOtoLL`
  confirmation, and says nothing about real-world ARP accuracy (Syria's own ARP residual
  was ~1.0–1.3 km even after live confirmation). Recommend treating Afghanistan's
  parameters as `confidence="provisional"` in `THEATRE_PROJECTIONS`, upgradeable to
  `"confirmed"` the same way Syria's were (M1→M1-verification): a live `coord.LOtoLL` probe
  on a Windows session with Afghanistan loaded.

  Reproducible probe: `tools (scratch, not committed to pipeline)`, logic described above;
  rerun recipe is in "Reproducible Test" below.

- **Point-cloud lower bound from `towns.lua` + `beacons.lua` — but the Syria-era
  methodology ("beacon+airbase bound is a tight lower bound") does NOT transfer cleanly to
  Caucasus, and this is itself a finding, not a restatement.**

  | theatre | source | lat range | lon range | x range (DCS m) | z range (DCS m) |
  |---|---|---|---|---|---|
  | Afghanistan | towns.lua (n=1225) | 29.7358–38.4958 | 60.6373–74.5789 | — | — |
  | Afghanistan | beacons.lua (n=49, all) | 29.3498–38.5439 | 60.8962–74.5092 | -498,490–525,449 (1,023.9 km) | -504,146–745,003 (1,249.1 km) |
  | Caucasus | towns.lua (n=1759) | 41.3749–45.4254 | 36.7120–45.3326 | — | — |
  | Caucasus | beacons.lua (n=164, all) | 41.6017–47.4032 | 29.3833–45.7000 | -356,585–255,528 (612.1 km) | -379,811–929,610 (1,309.4 km) |

  **Caucasus's full-beacon bound is not a tight lower bound — it is badly inflated by
  off-map enroute navaids.** Filtering the 13 outlier beacons that push the Caucasus bound
  past its towns-derived envelope shows they are real-world **navaids at Ukrainian/Russian
  cities far outside the rendered terrain** — Taganrog, Mariupol, Rostov-Na-Donu, Grozny,
  Tiraspol, Nikolaev-Matveyevka — placed in `beacons.lua` purely for enroute radio-nav
  reference, the same way a VOR 200 nm away is usable in a real cockpit without being
  "on" any rendered map. **Splitting Caucasus's beacons by `beaconId` prefix
  (`airfield<N>_<M>` = co-located with an actual in-game airfield, vs. `world_<N>` = enroute
  reference, same distinction `dcs_data/beacons.py`'s `airfield_group` field already
  encodes) recovers a trustworthy bound**: 100 airfield-tagged Caucasus beacons give x
  -356,585–11,981 (368.6 km), z 239,512–904,122 (664.6 km) — which lines up closely with
  ED's own marketing figure for Caucasus, **"over 700×400 km"** (WebSearch, ED product
  page via search snippet — documented but coarse, same tier as Syria's marketing figure).
  Afghanistan's beacon set does not show this problem to the same degree (its `world_*`
  beacons — Peshawar, Dushanbe, Quetta, Multan — sit just across the Afghan border in
  Pakistan/Tajikistan/Iran, not hundreds of km beyond it), so its full-beacon bound stays
  close to its towns bound. **This is why towns.lua, not the full beacon set, should be
  the primary point-cloud source for a new theatre's extent until the airfield/world split
  has been checked** — the Syria note's implicit assumption ("beacons are DCS-authoritative
  points near the map") does not generalize; "DCS-authoritative" and "near the map" are
  different properties and beacons.lua only guarantees the first.

- **`Afghanistan.surface5`'s node-descriptor region does not scan tractably at the same
  150 MB budget that worked for Syria — a real, reportable performance problem with the
  existing probe tool, not a data-format finding.** `tools/probe_surface5_elevation.py`'s
  `walk_descriptors` (written and validated against *Syria* in
  `2026-09-29-surface5-elevation-confirmed.md`) was re-run against
  `Afghanistan.surface5` (41.5 GB, vs. Syria's 30.4 GB) this session: 20 MB scanned in
  0.21 s (8,063 tile descriptors — ~5.5× denser per MB than Syria's ~65–75/MB), but 50 MB
  took **31.25 s**, a scaling far worse than linear. The run was killed before 150 MB
  (8+ minutes of CPU and climbing with no output). **Evidence: reproduced-locally
  (the slowdown itself; the mechanism is inferred, not confirmed)** — the likely cause,
  read from the walker's own logic, is that a scan-forward `buf.find(b"TRITYPE", i)` from
  a spurious `"Surface5.0"`-byte-pattern match deep in payload territory, with no real
  descriptor following nearby, costs `O(remaining-buffer)` per failure; if Afghanistan's
  file has many more such false candidates per MB than Syria's did, the walk degrades
  towards quadratic. **Not pursued further this session** — per the project's own
  "effort clearly outweighs value" framing used for the original `.surface5` decode spike,
  burning the session on a tool-performance bug in a throwaway probe script (not pipeline
  code) when the point-cloud + DEM-tile evidence below already gives a workable extent is
  the wrong trade. The **partial** 50 MB scan did complete and found
  x -1,266,498…582,576, z -654,787…813,230 — **reported for completeness, not trusted**:
  it is roughly 2.4× past the beacon-derived x-min on one side, which is exactly the
  shape a mis-anchored resync (not caught by the walker's own `±1e7` sanity filter) would
  produce, and no ground-truth cross-check (the Syria note's actual validation step) was
  possible without a live Afghanistan `land.getHeight` probe.

- **A concrete, Afghanistan-independent corroboration: the ED marketing total area for
  Afghanistan (2,290,264 km², WebSearch of ED's own product pages) is close to the area of
  this session's padded bbox** (lat 28–40°N × lon 54–78°E ≈ 1,332 km × ~1,748 km at this
  latitude ≈ 2.33 M km² — within ~2% of the marketing figure), stronger corroboration than
  Syria's own marketing-figure check had (Syria's bbox was ~25% under its marketing
  figure). — **evidence: documented (coarse marketing source) + reproduced-locally
  (area arithmetic).**

### Q1 bottom line

No single source gives a corner-verified mesh edge for either theatre (same conclusion as
Syria's M7 note — this is apparently just how DCS is, no theatre has published an exact
boundary). The working lower bound recommended for both:

- **Afghanistan:** towns.lua bound (lat 29.7358–38.4958, lon 60.6373–74.5789), cross-checked
  against beacons.lua (close agreement) and ED's marketing total area (good agreement after
  padding). Afghanistan's `tmerc` parameters are **provisional** (beacon-fit only, no pydcs
  source exists, no live confirmation).
- **Caucasus:** towns.lua bound (lat 41.3749–45.4254, lon 36.7120–45.3326), cross-checked
  against the **airfield-filtered** beacon subset (not the full set) and ED's marketing
  figure ("over 700×400 km"). Caucasus's `tmerc` parameters are provisional-but-strong
  (beacon-fit reproduces pydcs's own already-published values to <0.01 m — effectively a
  second independent confirmation of pydcs's numbers, though still not a live
  `coord.LOtoLL` run).

---

## Q2 — Padded WGS84 bbox, DEM tile lists, Geofabrik extracts

**Update, mid-session:** the user independently downloaded data into the main checkout
(not this worktree — `data/` is gitignored) while this investigation was in progress:
`world-model/data/raw/dem/afganistan-full/` (288 `.hgt`, from zip blocks `H40–J43`, i.e.
lat 28–40°N × lon 54–78°E) and `dem/caucasus-full/` (123 `.hgt` from blocks `K36–L38`,
sea tiles absent — see note on the missing 21 below); `osm/afganistan-full/` (Afghanistan,
Iran, Pakistan, Tajikistan, Turkmenistan, Uzbekistan `.osm.pbf`) and `osm/caucasus-full/`
(Armenia, Azerbaijan, Georgia, Russia North-Caucasus-Fed-District, Russia
South-Fed-District `.osm.pbf`). The lists and formula below were derived independently in
this session **before** that download was known, and the DEM3 block formula in particular
is now cross-checked against it (see "DEM3 block formula" below) — they agree exactly.

### DEM3 block-code formula (derived and cross-checked this session, not found stated
verbatim on viewfinderpanoramas.org — `WebFetch` could not read the site's interactive
image-map, only its prose changelog)

```
lat band:  letter_index = floor(lat / 4);  letter = chr(ord('A') + letter_index)
           band covers [letter_index*4, letter_index*4 + 4) degrees N
lon band:  number = floor((lon + 180) / 6) + 1
           band covers [-180 + (number-1)*6, -180 + number*6) degrees
```

**Evidence: inferred, then reproduced-locally against real downloaded data.** Derived from
one directly-stated fact (`L11` = 44–48°N, 120–114°W, from a WebSearch snippet) plus four
more recovered from a changelog mention ("H44(n31e079,n30e081), H46(n30e090,n30e091),
I43(n35e074), J43(n38e075)") — all five independently consistent with the formula above.
**The formula's own prediction for Afghanistan (`H41` = 28–32°N, 60–66°E) was given to this
investigation as a hint before the fit** — it was not reverse-engineered from the hint, the
hint was a spot-check the derived formula passed. It is now further confirmed by the actual
downloaded tile count: the formula's predicted Afghanistan block set (`H40–J43`, lat
28–40°N × lon 54–78°E) is **exactly** 12 lat-degrees × 24 lon-degrees = 288 — the exact
`.hgt` count the user's download has. Caucasus: `K36–L38` predicts lat 40–48°N × lon
30–48°E = 8 × 18 = 144 possible tiles; 123 are present, 21 missing — consistent with "sea
tiles absent" (the NW corner of that block, lat 40–44°/lon 30–36°, is overwhelmingly open
Black Sea). Recommend still spot-checking the formula against the site's own interactive
map before relying on it for a theatre this session didn't check (e.g. Kola, see Q4) — this
is a derived rule cross-checked five ways, not a documented one.

### Afghanistan

**Padded bbox used for the actual download: lat 28–40°N, lon 54–78°E** (wider on the west
than this session's own first-pass pick of lon 59–76°E — the wider bbox is the one now on
disk and is the one to treat as current).

- **SRTM 1°×1° tiles:** `N28E054`–`N39E077` inclusive, i.e. 12 lat × 24 lon = 288 tiles —
  matches the 288 `.hgt` files already on disk exactly, so this list is **confirmed
  present**, not just computed.
- **DEM3 blocks:** `H40, H41, H42, H43, I40, I41, I42, I43, J40, J41, J42, J43` (12 blocks)
  — also confirmed present on disk (`dem/H40.zip`…`J43.zip`).
- **Geofabrik `.osm.pbf` extracts, decided per-country:**

  | country | decision | reasoning | status |
  |---|---|---|---|
  | Afghanistan | include | the theatre itself | **downloaded** |
  | Pakistan | include | shares most of the southern/eastern border; also covers Gilgit-Baltistan (Pakistan-administered Kashmir) — no separate "India" extract is needed for that area, since Geofabrik files it under Pakistan | **downloaded** |
  | Iran | include | western border, bbox reaches into Iran at the west edge (lon down to 54°) | **downloaded** |
  | Turkmenistan | include | northern border | **downloaded** |
  | Uzbekistan | include | brushes the far north at the padded bbox's upper lat edge | **downloaded** |
  | Tajikistan | include | NE border, includes the Wakhan corridor's Tajik side | **downloaded** |
  | **China** | **exclude** | `towns.lua` has a real DCS-placed point literally named `"China"` at the Wakhan corridor's eastern tip (37.1684°N, 74.5789°E) confirming the terrain *does* nominally reach the border — but the area is high, essentially unpopulated Pamir with negligible OSM feature density, and Geofabrik's China extract is a multi-GB whole-country download. Same cost/value call as Syria's Sinai-corner decision (`2026-09-06-m8-geofabrik-osm-recon.md`): real but negligible, not worth it. | **not downloaded — consistent with this recommendation** |
  | **Kyrgyzstan** | **exclude** | checked directly: Afghanistan's northernmost `towns.lua` entries (up to 38.4958°N) are all Tajik place names (Vahdat, Lakhsh, etc.) — the bbox's northern edge stays inside Tajikistan and never actually reaches Kyrgyzstan's border | **not downloaded — consistent** |
  | India | not applicable | see Pakistan row — the relevant Kashmir-area territory is already covered there | **not downloaded — consistent** |

  **This set matches exactly what the user already downloaded** — no gap, no unnecessary
  extract.

### Caucasus (extent-only pass)

**Padded bbox used for the actual download implies lat 40–48°N, lon 30–48°E** (from the
`K36–L38` DEM3 block set), somewhat wider than this session's own towns.lua-derived
working bbox (lat 41.37–45.43, lon 36.71–45.33).

- **SRTM/DEM3:** `K36, K37, K38, L36, L37, L38` — matches the downloaded zip set exactly.
- **Geofabrik extracts — one real gap found, flagged by the coordinator and confirmed
  here:**

  | region | decision | reasoning | status |
  |---|---|---|---|
  | Georgia | include | core of the map (`europe/georgia.html` — **filed under `europe/`, not `asia/`, the same Geofabrik continent-grouping trap the M8 note already flagged for Turkey**) | **downloaded** |
  | Armenia | include | `asia/armenia.html` | **downloaded** |
  | Azerbaijan | include | `asia/azerbaijan.html`; towns.lua's lon max (45.33) reaches into Azerbaijani territory | **downloaded** |
  | Russia South Fed. District | include | covers Krasnodar Krai/Sochi/Rostov — most of the map's northern half, and the "Anapa" end of ED's own "720 km Anapa→Tbilisi" quote | **downloaded** |
  | Russia North-Caucasus Fed. District | marginal, included anyway | would add Chechnya/Dagestan/Ingushetia; the one beacon found there (`Grozny`, 43.38°N/45.70°E) is a `world_*` enroute navaid, not an on-map airfield beacon, by the same test used to disqualify Caucasus's other distant beacons above — likely mostly unnecessary, but already downloaded and not large enough to be worth discarding | **downloaded** |
  | Crimea / Ukraine | **exclude** | ED's own marketing anchor points the map's NW corner at **Anapa** (37.3°E) — Crimea (32–36.6°E) sits entirely west of that, outside the real map regardless of how far this session's padded bbox nominally reaches | **not downloaded — consistent** |
  | **Turkey** | **include — this is the gap the coordinator flagged, and it is real** | Checked directly: the southernmost `towns.lua` entries (lat 41.3749–41.55°N) are almost all Georgian border towns (Marneuli, Gardabani — Kvemo Kartli region) **except one**, `Kemal'pasha` at 41.4688°N/41.5191°E — a real Turkish town name (Kemalpaşa), confirming the rendered terrain genuinely includes a sliver of NE Turkey (the Posof/Ardahan border area near Çıldır), not merely a padding artefact. **A Turkey extract already exists and does not need re-downloading**: `/mnt/f/dcs-world-model/syria/raw/osm/countries/turkey-260911.osm.pbf` (from the Syria build). Recommend re-clipping that existing file to the Caucasus bbox rather than fetching Turkey's ~612 MB extract a second time. | **not yet staged for Caucasus — action needed, see below** |

### Action needed

**Copy or symlink `/mnt/f/dcs-world-model/syria/raw/osm/countries/turkey-260911.osm.pbf`
into the Caucasus OSM raw-data location** (`data/raw/osm/caucasus-full/`, following
whatever naming convention the other five files there use) before any Caucasus OSM build —
the current Caucasus OSM set is missing real, DCS-confirmed Turkish territory without it.

---

## Q3 — Do the existing parsers work on Afghanistan's files?

All four binary/text parsers were run read-only against the real installed Afghanistan
(and, for the Lua ones, also Caucasus) files from this worktree, writing nothing into
`data/`.

- **`dcs_data.towns.parse_towns_lua` — format matches, hardcoded count guard does not.**
  No `ValueError: Unparseable towns.lua entry` was raised for either theatre (the regex
  itself is fine) — only `EXPECTED_TOWN_COUNT = 1182` (Syria's count) fails:
  Afghanistan has 1,225 entries, Caucasus has 1,759. **This constant needs to become
  per-theatre** (or be loosened to a sanity floor rather than an exact match) before this
  parser can run on anything but Syria.
- **`dcs_data.beacons.parse_beacons_lua` — same pattern.** No field-level or
  `beaconId`-shape errors on either theatre (the `airfield<N>_<M>` / `world_<N>` regex
  split, used above for the Caucasus off-map-navaid finding, holds on both). Only
  `EXPECTED_BEACON_COUNT = 151` (Syria's count) fails: Afghanistan has 49, Caucasus has
  164. **Same fix needed as towns.lua's count.**
- **`roadnet.routes.iter_routes` — works unmodified, zero sync-loss.** Both theatres'
  `.routes` files share Syria's exact container header (`landscape4::lRoutesFile`,
  identical byte layout). A 20-route partial walk against each produced
  `RouteWalkStats(sync_loss_events=0)` for both — the scan-forward resync the format
  depends on is not Syria-specific. (A full-file walk was not run — both files are
  ~1 GB and the existing docstring already notes the walk is slow and single-pass; not
  needed to answer "does it work," which this partial walk answers.)
- **`roadnet.rn4.parse_header` — works unmodified.** Afghanistan's `.rn4` header parses
  cleanly (`field_a=5`, 8-entry road-type string table, `topology_table_offset=158`) —
  same container format as Syria's.
- **One concrete Syria-hardcoded bug found, unrelated to the two count guards above:**
  `build/pipeline.py`'s roadnet-ingest stage (`build_region`, ~line 554) writes the
  `Source` row's `name` field as the **literal string `"Syria.routes"`**, and the stage's
  progress-log label the same way (`f"Syria.routes ({routes_path.stat().st_size} bytes)"`)
  — neither is derived from `routes_path.name`. Building Afghanistan or Caucasus today
  would silently record "Syria.routes" as the provenance source for roadnet features that
  actually came from a different file. (`towns.lua`/`beacons.lua`'s own `Source.name`
  fields are theatre-generic strings already and do **not** have this problem.)
- **Path casing is a usage note, not a parser bug.** Syria and Afghanistan both ship
  `beacons.lua` top-level and `towns.lua` under a lowercase `map/`; Caucasus ships
  `Beacons.lua` (capital B) top-level and `towns.lua` under capitalized `Map/`. The
  pipeline/CLI takes explicit `--towns`/`--beacons` paths (no hardcoded case inside
  `pipeline.py` itself), so this is not a code defect, but every existing `RUN.md`/
  `docs/*_RUN_INSTRUCTIONS.md` example is written against Syria's lowercase layout and
  would need the caller to substitute the correct case per theatre — worth a one-line
  callout in whichever doc ends up with Afghanistan/Caucasus run instructions.
- **No theatre registry entries exist yet for either theatre** — `THEATRE_PROJECTIONS`
  (`coordinates/projections.py`) has only `"Syria"`; `REGIONS` (`build/region.py`) has
  only Syria regions. This is expected (the backlog item itself frames this as "add
  entries," not a parser problem) and is an Architect/Implementer decision (which
  confidence tier to ship Afghanistan's provisional tmerc params at, what a first
  Afghanistan `RegionDefinition` should cover), not something this investigation should
  decide.

### Q3 bottom line

**Format-wise, all four parsers generalize with zero changes.** The two blocking issues
found are both small and mechanical: (1) `EXPECTED_TOWN_COUNT`/`EXPECTED_BEACON_COUNT`
need to become per-theatre (dict keyed by theatre name, or a `min_count` sanity floor
instead of an exact match — the project's actual intent, "fail loudly if the format
changes," survives either fix), and (2) the hardcoded `"Syria.routes"` provenance string
in `build/pipeline.py` needs to read from `routes_path.name`. Neither is a parser-format
risk; both are "someone forgot there would be a second theatre" artifacts.

---

## Q4 — Does viewfinderpanoramas DEM3 cover Kola (66–70°N)?

**Answered and confirmed by the user mid-investigation: yes, it covers Kola — treat the
SRTM >60°N gap as resolved for Kola and do not re-investigate.**

This session's own (now superseded by the user's direct confirmation) supporting evidence,
kept for the record: a GLIMS RGI 6.0 technical report (WebSearch) states high-latitude
glacier hypsometry for Svalbard and Scandinavia was sourced from viewfinderpanoramas DEM3
specifically *replacing* ASTER GDEM2, using Russian 1:100,000/1:200,000 and Norwegian
1:50,000 topographic maps rather than SRTM — i.e. DEM3's whole reason for covering that
latitude band at all is to fill exactly the gap SRTM leaves above 60°N, and Kola sits
inside the same North-Eurasia/Scandinavia coverage region the report describes. —
**evidence: documented (secondary technical report), now superseded by user confirmation
as the operative answer.**

---

### Reproducible Test

**Tmerc beacon-fit** (pure Python + `pyproj`, no numpy/scipy; validated against Syria
first):
```python
# parse beacons.lua's `position {x,y,z}` / `positionGeo {latitude,longitude}` pairs,
# then for each central_meridian candidate in the UTM-zone-centre series (odd
# multiples of 3, spaced 6 deg, spanning the theatre's lon range):
#   - project each (lat,lon) through a unit tmerc (k0=1,x0=0,y0=0,lat_0=0,axis=neu)
#     to get (N,E)
#   - solve the shared-k0 linear least squares x=k0*N+false_northing,
#     z=k0*E+false_easting via hand-derived normal equations
#   - keep the candidate with lowest RMS residual
# Full script: see this session's scratch files (not committed; logic restated above
# is sufficient to reproduce it in ~60 lines).
```
Run against Syria's `beacons.lua` first and confirm the fit reproduces
`central_meridian=39, scale_factor=0.9996, false_easting≈282801, false_northing≈-3879866`
to ~0.03 m before trusting the fit on an unverified theatre.

**Parser compatibility checks** (from `world-model/`, using the main checkout's venv or
any Python 3.11+ with no extra deps for towns/beacons, `pyproj`-free):
```sh
PYTHONPATH=src python3 -c "
from pathlib import Path
from dcs_data.towns import parse_towns_lua      # raises on count mismatch — expected
from dcs_data.beacons import parse_beacons_lua   # same
from roadnet.routes import iter_routes, RouteWalkStats
from roadnet import rn4
import mmap, itertools
# towns/beacons: catch ValueError, confirm it names only the count, not a parse shape
# routes: list(itertools.islice(iter_routes(Path(...), stats=RouteWalkStats()), 20))
# rn4: parse_header(mmap.mmap(...)) on the .rn4 file
"
```

**DEM3 block formula**, and its cross-check against the real downloaded tile counts:
```python
import math
def dem3_blocks(lat_min, lat_max, lon_min, lon_max):
    li = range(math.floor(lat_min/4), math.floor((lat_max-1e-9)/4)+1)
    ni = range(math.floor((lon_min+180)/6)+1, math.floor((lon_max-1e-9+180)/6)+1+1)
    return [f"{chr(ord('A')+l)}{n}" for l in li for n in ni]
# dem3_blocks(28,40,54,78) -> H40..J43 (12 blocks); 12 lat-deg * 24 lon-deg = 288
#   -- matches data/raw/dem/afganistan-full/ exactly (288 .hgt files)
# dem3_blocks(40,48,30,48) -> K36..L38 (6 blocks); 8 lat-deg * 18 lon-deg = 144 possible
#   -- 123 present in data/raw/dem/caucasus-full/, 21 missing (Black Sea corner)
```

---

### Possible Approaches

1. **Promote Afghanistan's and Caucasus's provisional `tmerc` params to `THEATRE_PROJECTIONS`
   at `confidence="provisional"`**, following the same dataclass shape Syria uses, with a
   clear upgrade path to `"confirmed"` (a live `coord.LOtoLL` probe on the Windows box,
   exactly M1→M1-verification's pattern) noted in the `source` field.
2. **Fix the two count guards as a per-theatre dict** (`EXPECTED_TOWN_COUNT: dict[str, int]`
   keyed by theatre, or a documented `min_count` floor) rather than a bare constant —
   small, mechanical, unblocks both theatres' ingest immediately.
3. **Fix `build/pipeline.py`'s hardcoded `"Syria.routes"` provenance string** to
   `routes_path.name` — small, prevents silently mislabelled provenance on every
   non-Syria roadnet ingest.
4. **Stage the Turkey OSM gap for Caucasus** by reusing the existing Syria-build extract
   (see Q2 action) rather than re-downloading.
5. **Do not re-attempt the full `.surface5` scan for Afghanistan as currently written** —
   file a note (this one) rather than a code fix, since `tools/probe_surface5_elevation.py`
   is explicitly a throwaway investigation script (nothing imports it); if Afghanistan's
   true mesh extent is ever needed to sub-degree precision, the fix is either a smaller
   initial scan window with exponential backoff/retry, or restricting the `TRITYPE`
   forward-search to a bounded lookahead distance (reject-and-resync past it) rather than
   an unbounded `buf.find`.

### Unresolved

- Afghanistan's and Caucasus's `tmerc` parameters are not live-`coord.LOtoLL`-confirmed —
  this needs a Windows-side mission-scripting probe, the same one M1-verification ran for
  Syria. Caucasus's case is lower-risk (independently reproduces pydcs's existing published
  numbers), Afghanistan's is higher-risk (no second source exists at all).
- Afghanistan's true mesh extent beyond the point-cloud/marketing-area lower bound is not
  established — the `.surface5` route stalled on a tool-performance problem, not a data
  question, and was not pursued further this session (see Q1 finding above).
- Whether the Russia North-Caucasus-Fed-District extract is actually needed for Caucasus,
  or whether its one real signal (the `Grozny` beacon) is purely an off-map enroute navaid
  the same way Taganrog/Mariupol/Rostov are, was not resolved to the same confidence as the
  Turkey finding — it is already downloaded, so the practical cost of leaving it in is low,
  but a future validation pass (does any `towns.lua` entry actually fall inside it?) would
  settle it cleanly.
- The DEM3 letter/number formula is derived and cross-checked five ways (one direct fact,
  four changelog mentions, the user's own already-downloaded tile counts for both
  theatres) but was never read directly off viewfinderpanoramas.org's own interactive
  index map (`WebFetch` strips the image-map/JS, and the page's prose documentation does
  not state the rule) — safe to treat as settled for Afghanistan/Caucasus given the exact
  tile-count match, but worth a direct look before trusting it on a theatre with no
  downloaded data to cross-check against (e.g. if Kola's own per-degree block names are
  ever needed, rather than just "DEM3 covers Kola" at the confirmed-by-user level).
