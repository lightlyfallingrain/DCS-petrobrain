# M7 — Full Syria theatre extent (bounding box)

**Date:** 2026-09-05
**DCS version:** 2.9.29.27278 (per M0 probe; not re-verified this session — see
`2026-09-02-m0-dcs-install.md`)
**Theatre:** Syria, full map (M1-M6 validated only the ~20x20 km Latakia/Gemerek test
regions; this note is scoped to establishing the whole-theatre bound for M7)

### Question

M7 ("Full theatre pipeline") needs to scale M1-M6's pipeline from a 20x20 km test region
to the entire Syria DCS map. What is the actual full extent of the Syria theatre, in DCS
x/z metres and/or as a WGS84 bounding box? Prior notes only mention a "~500-600 km" figure
as inferred background, not an independently confirmed bbox.

### Findings

- **`MissionGenerator/nodesMap.lua`'s `theatre.nodesMapBorders` is NOT the theatre extent —
  falsified this session by real airbase coordinates that fall outside it.** —
  **evidence:** reproduced-locally — **source:**
  `world-model/research/2026-09-03-m5-recon.md` Finding 28 (`nodesMapBorders = {
  -257003.953125, -419498.875000, 248852.046875, 368981.125000 }`, i.e. minX, minZ, maxX,
  maxZ) cross-checked this session against
  `world-model/data/raw/dcs/2026-09-03/coord_probe_output.json`. `Ruwayshid` airbase sits at
  x=-294,673.3 — **37.7 km past `nodesMapBorders`' minX of -257,004**. `Nevatim` sits at
  x=-420,022.1, `Konya` at x=341,729.7, `T2` at z=389,224.3 — all real, DCS-authoritative
  airbase positions that lie outside the mission-generator's envelope on every side. This
  confirms and sharpens M5's own caveat ("`nodesMapBorders` is the mission generator's
  working envelope, not a documented terrain extent") with a concrete falsifying example —
  it should not be used as the theatre bbox for M7.

- **Best-available DCS-authoritative bounding box: the extremal x/z and lat/lon of all
  known airbases and radio beacons, from two independent DCS-native sources that agree
  closely.** — **evidence:** reproduced-locally — **source:**
  1. `world.getAirbases()` via live `coord.LOtoLL`, 225 airbases, captured in
     `world-model/data/raw/dcs/2026-09-03/coord_probe_output.json` (this exact dataset was
     already used and cross-validated to 0.00-0.03 m residual against pydcs's Syria `tmerc`
     parameters in `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`
     Finding 1 — i.e. this session trusts an already-verified dataset, not a fresh unverified
     one).
  2. `Mods/terrains/Syria/map/beacons.lua` (plain, unencrypted, offline-readable Lua data
     file — same file class as `towns.lua`), 151 beacon entries, parsed this session.

  Computed extremes (this session, both sources):

  | source | x range (m) | z range (m) | lat range | lon range |
  |---|---|---|---|---|
  | airbases (n=225) | -420,022.1 to 341,729.7 (762 km) | -320,441.1 to 389,224.3 (710 km) | 31.211-38.006°N | 32.286-40.204°E |
  | beacons (n=151) | -421,912.2 to 345,432.4 (767 km) | -320,235.1 to 390,774.9 (711 km) | 31.195-38.999°N [**typo — read 37.999°N**, see below] | 32.288-40.208°E |

> **CORRECTION 2026-09-21 — the beacon latitude maximum above is a transcription typo: it is
> `37.999`, not `38.999`.** Re-running this note's own Reproducible Test against the committed
> capture (`2026-09-03-m5-nodes-lua-probe.txt`) gives the beacon extremes as
> `lat 31.194762 … 37.999037`, `lon 32.288303 … 40.208231`, `x -421912.21875 … 345432.4375`,
> `z -320235.13614 … 390774.875`. **Every other figure in the row reproduces exactly**; only this
> one digit is wrong. (The x-max beacon is the same object: `position = { 345432.437500, …}`,
> `positionGeo = { latitude = 37.999037, … }`.)
>
> **The typo is also self-refuting from inside the table**, which is why it is worth keeping
> rather than silently fixing: the beacon and airbase x-maxima differ by ~3.7 km, and a 1.0°
> latitude difference is ~110 km. So the sentence "the two independent point sets agree to within
> ~2-4 km on every edge" cannot be true of the row as printed — it is true of the *corrected*
> row. The corroboration conclusion is right; the number under it was mistyped.
>
> **Downstream:** `2026-09-06-m8-geofabrik-osm-recon.md` takes its working envelope from this
> table ("lat 31.2–39.0 N, lon 32.3–40.2 E") and so carries the wrong northern edge through its
> coverage reasoning. The built `syria-full` region is unaffected — it is defined in DCS x/z
> (`world-model/src/build/region.py`, x-max 375,432.4 = beacon x-max + 30 km padding), not in
> latitude, so no code ever read the mistyped degree figure.

  The two independent point sets agree to within ~2-4 km on every edge — strong
  corroboration. Extremal points: `Nevatim` (SW, x-min), `Konya`/beacon near Konya (N,
  x-max), `Gazipasa` (W, z-min), `T2`/`Diyarbakir`-area beacon (E, z-max).

  **Caveat (important):** this is a *point-cloud* bound, not a terrain-mesh bound — it is
  guaranteed to be **inside or equal to** the true playable terrain extent (every airbase
  and beacon sits on land within the map), but the actual terrain mesh/coastline/border
  almost certainly extends somewhat further past the outermost airbase/beacon in most
  directions (sea, mountains, or unpopulated buffer). It should be treated as a tight
  **lower bound**, not the exact edge.

- **ED's own marketing copy gives a whole-map size, but the number has changed over time
  as the map was expanded, and does not give exact corners.** — **evidence:** documented
  (official ED source), but coarse and time-inconsistent — **source:**
  digitalcombatsimulator.com official Syria terrain product page (fetched this session):
  "The 1000x900 km Syria map covers most of the eastern Mediterranean" (current copy, post
  eastward Deir ez-Zor/H3/Iraq expansion). A 2021 Stormbirds.blog review of the map (fetched
  this session) instead states "900x500km" — the map's stated footprint grew between these
  two sources. The installed version (2.9.29.27278) **does include** the later eastward
  expansion — confirmed this session by finding `Deir_ez_Zor.rn4`/`.rn5` and `H3.rn4`/`.rn5`
  taxiway files in the local file listing, and `Deir ez-Zor`/`H3`/`H3 Northwest`/`H3
  Southwest`/`Ruwayshid` all present with live coordinates in `coord_probe_output.json` — so
  the current "1000x900 km" figure, not the 2021 "900x500 km" one, is the applicable ED
  claim for this install. 1000x900 km is larger than the 762x710 km airbase/beacon-derived
  bound above, which is directionally consistent with the airbase bound being a lower bound
  on the true mesh extent (per the caveat above), though the two numbers were not derived
  from the same methodology and should not be treated as cross-validating each other
  precisely.

- **No exact terrain-mesh/coastline bbox, and no readable projection/extent parameter, was
  found in any locally-synced DCS file.** — **evidence:** reproduced-locally (negative
  result) — **source:** `terrain.cfg.lua.pak.crypt` remains packed+encrypted (per
  M1/M4 findings, not re-opened this session); no other locally-synced file (RasterCharts
  manifest, `.rn4`/`.routes`, `towns.lua`, `beacons.lua`, `nodesMap.lua`) was found to carry
  an explicit "this is the terrain's outer boundary" field — every DCS-native source found
  so far is either a point/place list (airbases, beacons, towns) or an internal working
  subset (mission-generator borders), never a stated mesh polygon.

### Reproducible Test

Airbase/beacon extremes (re-run against the same already-synced files, no live DCS access
needed):

```python
import json, re

# Airbases (already-synced, already-verified dataset)
d = json.load(open("world-model/data/raw/dcs/2026-09-03/coord_probe_output.json"))
ab = d["airbases"]
print("x:", min(a["x"] for a in ab), max(a["x"] for a in ab))
print("z:", min(a["z"] for a in ab), max(a["z"] for a in ab))
print("lat:", min(a["lat"] for a in ab), max(a["lat"] for a in ab))
print("lon:", min(a["lon"] for a in ab), max(a["lon"] for a in ab))

# Beacons (already-synced plain Lua file)
text = open("world-model/data/raw/dcs/syria/map/beacons.lua").read()
pos = re.findall(r'position\s*=\s*\{\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\}', text)
xs = [float(p[0]) for p in pos]; zs = [float(p[2]) for p in pos]
print("beacon x:", min(xs), max(xs), "z:", min(zs), max(zs))
geo = re.findall(r'latitude\s*=\s*([-\d.]+)\s*,\s*longitude\s*=\s*([-\d.]+)', text)
lats = [float(g[0]) for g in geo]; lons = [float(g[1]) for g in geo]
print("beacon lat:", min(lats), max(lats), "lon:", min(lons), max(lons))
```

Falsification check for `nodesMapBorders`:

```python
borders = (-257003.953125, -419498.875000, 248852.046875, 368981.125000)  # minX,minZ,maxX,maxZ
ruwayshid_x = -294673.28125
assert ruwayshid_x < borders[0]  # True — Ruwayshid is outside the mission-generator envelope
```

### Possible Approaches

1. **Use the airbase+beacon-derived bbox, padded, as M7's working extent.** Recommended
   default: take the tighter of the two DCS-native point-cloud bounds (x: [-421,912,
   345,433], z: [-320,441, 390,775], rounding outward to the wider of the two sources on
   each edge) and add a fixed safety margin (e.g. +20-50 km per side, chosen by Architect
   based on how much sea/mountain buffer is tolerable to over-process) to account for the
   point-cloud-vs-mesh gap identified above. This is fully reproducible from already-synced
   data, needs no new DCS access, and is DCS-authoritative on every included point (though
   the margin itself is a judgment call, not derived from evidence).
2. **If a firmer, non-padded number is wanted, run a live `coord.LOtoLL`/edge-probe** that
   walks x/z outward from the airbase bound in each of the 4 cardinal directions and checks
   for a DCS-reported clamp, error, or `land.getSurfaceType` transition to an "off-map"
   value (if such a value exists — not confirmed) to find where the terrain itself actually
   ends. This is the minimal follow-up probe if Architect decides the ~40-50 km slack
   between the point-cloud bound and ED's marketing figure is unacceptable for M7's
   resource planning (e.g. tile/raster budgeting). Not required to proceed with M7 planning
   at a padded-lower-bound level of confidence.
3. **Treat RasterCharts' own tile-grid coverage as a cross-check, not a primary source.**
   M2's arithmetic (8x8 grid of 64 km tiles = ~524 km/side for the `aa`/64m sheet) is in
   the right order of magnitude but was explicitly flagged there as inferred/unresolved
   registration, with sheet-to-sheet stitching (`aa`/`ab`/`xab`/`xac`) not fully decoded —
   not recommended as the basis for M7's bbox given the airbase/beacon data now available.

### Unresolved

- The exact terrain mesh/coastline polygon (vs. this session's point-cloud lower bound) is
  not known and may not be discoverable without either decrypting `terrain.cfg.lua.pak.crypt`
  or a live edge-walking probe (Approach 2 above). Evidence that would resolve it: a
  decrypted `terrain.cfg.lua`, or `land.getSurfaceType`/`coord.LOtoLL` behavior at
  hand-picked x/z points progressively further outside the airbase/beacon bound.
  Decrypting `.pak.crypt` was out of scope for prior sessions and not attempted this
  session either.
- The ~40-50 km gap between the airbase/beacon bound (~762x710 km) and ED's current
  marketing figure (1000x900 km) is unreconciled — it's plausibly real (sea/buffer beyond
  the outermost airbases) but could also partly reflect ED rounding/marketing imprecision.
  Not resolvable from local data; would need either the edge-probe (Approach 2) or an
  ED/Hoggit source that states exact corner coordinates rather than a round "1000x900"
  figure (none found this session).
- Whether DCS possesses any single authoritative "map extent" field at all (as opposed to
  the terrain mesh simply ending wherever the artists stopped modeling) was not established
  either way.

### Update to prior research

`world-model/research/2026-09-03-m2-rastercharts-recon.md`'s "~500-600 km" background
figure should now be superseded by this note's airbase/beacon-derived bbox for any M7
planning purpose — it was explicitly marked there as unverified background knowledge, and
this session's reproducible airbase+beacon cross-check (762x710 km, extending to Turkey in
the north, Jordan/Israel in the south, Cyprus in the west, and the Deir ez-Zor/H3/Iraq
salient in the east) is now the stronger source.
