# M5 recon — DCS-native road network files (`.rn4` / `.routes`)

**Date:** 2026-09-03
**DCS version:** 2.9.29.27278 (per M0)
**Theatre:** Syria (cross-checked against Afghanistan, Caucasus, Kola, MarianaIslands filenames)

### Question

M5 currently assumes road geometry must come from live-mission point sampling
(`land.getSurfaceType` / `land.findPathOnRoads`) or from OSM (already used for M3).
Does the Syria terrain module ship road network geometry as a **static,
extractable file** — i.e. can real road polylines/graph be pulled by parsing
terrain module files directly, without live-mission scripting?

### Findings

- **Every installed DCS terrain ships a per-theatre road network file pair**:
  `Mods/terrains/<Terrain>/roads/<Terrain>.rn4` + `<Terrain>.routes`. Confirmed
  present for Syria, Afghanistan, Caucasus, Kola, and MarianaIslands (identical
  naming pattern in all five) — **evidence:** reproduced-locally (filename
  listing only) — **source:** `world-model/data/raw/dcs/2026-09-02/DCS-files.txt`,
  lines 92072-92074 (Syria) and equivalents for the other four terrains.
- **Every airfield additionally ships its own taxiway network file**:
  `Mods/terrains/<Terrain>/AirfieldsTaxiways/<Airfield>.rn4` (no paired `.routes`
  at this level) — e.g. `Syria/AirfieldsTaxiways/Damascus.rn4`, one file per
  airfield (~230 files for Syria alone) — **evidence:** reproduced-locally
  (filename listing) — **source:** same file, lines 89259-89707.
- **This is strong indirect evidence that DCS stores road/taxiway topology as
  discrete vector-ish data, not baked only into the terrain mesh/texture** —
  a separate `.rn4`/`.routes` file per network only makes sense if it encodes
  actual graph/geometry (nodes, edges, connectivity) consumed by the engine's
  pathfinding and AI-unit road-following. **evidence:** inferred (from file
  layout only — the bytes have not been inspected) — **source:** same listing.
- **No public documentation of the `.rn4`/`.routes` binary format was found.**
  Checked: web search for `.rn4` DCS terrain (no hits beyond generic terrain
  pages), Hoggit wiki, ED forums search results, `pydcs` and
  `dcs-liberation`/`dcs-retribution` GitHub search results, and
  `JonathanTurnock/dcs-global-terrain-database` (a community GeoJSON terrain
  database project — its README does not mention `.rn4`, roadnet extraction,
  or road files at all; it appears to hand-curate/scrape rather than parse
  terrain module files). **evidence:** forum-claim-unverified / absence-of-evidence
  — **source:** WebSearch queries run 2026-09-03; `forum.dcs.world` threads
  ("NAV / Terrain / Road Database", "Creating custom terrain/map for DCS: World")
  returned HTTP 403 to automated fetch and were not manually read this session
  (per convention: not recorded as an unread gap, but genuinely unread — see
  Unresolved).
- **`dcs-liberation`'s "on-road" convoy routing does not parse `.rn4` either** —
  it relies on placing waypoints with the Mission Editor's "On Road" waypoint
  option, i.e. it delegates to DCS's own live in-engine road-snapping rather
  than extracting static geometry. **evidence:** forum-claim-unverified (from
  WebSearch summary of GitHub search results, not a direct source read) —
  **source:** WebSearch results referencing `dcs-liberation/dcs_liberation`
  issues/wiki on convoy routing.
- **The scripting-API road functions are point/path queries only, never a bulk
  graph export.** A community-maintained modding-doc site
  (`modding.caffeinesimulations.com/Aircraft/Lua/Modules/Terrain/`) documents
  the `Terrain` Lua singleton (used from **aircraft/cockpit avionics Lua**,
  e.g. moving-map/INS pages — a different environment than Mission Scripting's
  `land.*`/`coord.*`, though functionally the same class of live-engine query
  API) with a complete function list: `Terrain.findPathOnRoads(type, x1, y1, x2, y2)`,
  `Terrain.getClosestPointOnRoads(type, x, z)`, `Terrain.getClosestValidPoint`,
  `Terrain.FindNearestPoint`, `Terrain.FindOptimalPath`, plus airfield/taxiway
  helpers (`getRadio`, `getRunwayHeading`, `getRunwayList`, `getStandList`) that
  all take a `roadnet` argument described as **"a filepath string ... passed
  directly to the roadnet functions"** (i.e. even at the Lua API level, the
  network is an opaque engine-internal object referenced by path, not a table
  the script can walk). There is no `Terrain.getRoadNetwork()` / "list all
  segments" function in the documented set. **evidence:** forum-claim-unverified
  (single community doc site, not ED-official, and this session could not
  fetch it directly — content came via a `r.jina.ai` proxy render, itself
  unverifiable against the live DCS API) — **source:**
  `modding.caffeinesimulations.com/Aircraft/Lua/Modules/Terrain/` (fetched via
  proxy 2026-09-03; direct WebFetch returned HTTP 403).
- This matches and reinforces the existing M5 finding (`2026-09-03-m5-recon.md`)
  that `land.getSurfaceType` / `land.findPathOnRoads` are Mission-Scripting-only,
  point-in/point-out APIs — the `Terrain.*` cockpit-Lua family appears to be the
  same shape of API in a different Lua sandbox, not a richer one.

### Reproducible Test

Not yet run — this session has no direct filesystem access to the DCS
installation (Mac-side session; DCS runs on a separate Windows PC per
`world-model/WORKFLOW.md`). A probe script has been written to determine
whether `.rn4`/`.routes` are actually parseable (plaintext, simple fixed-record
binary, a known container like zlib) or opaque/compiled:

`world-model/tools/wsl/probe_syria_roadnet_files.sh`

It reports, per file (`Syria.rn4`, `Syria.routes`, two sample
`AirfieldsTaxiways/*.rn4` files, and the equivalent Caucasus files for
cross-terrain comparison): byte size, `file(1)` guess, hex+ASCII dump of the
first 512 and last 256 bytes, and a naive control-byte scan to flag whether
the file could be plaintext.

To run it: copy into `win-mac-sync/run-wsl/`, run in WSL bash on the Windows
DCS machine with `DCS_INSTALL_PATH` set (per `WORKFLOW.md`), sync the output
back, and bring the resulting `syria_roadnet_files_probe_*.txt` back into this
conversation (or `world-model/data/raw/dcs/`) for inspection.

### Possible Approaches

1. **Run the probe above first.** If `.rn4`/`.routes` turn out to be a simple,
   documented-elsewhere container (e.g. a zlib-wrapped table, or a fixed
   binary record format similar to other ED formats already reverse-engineered
   in this project — see `clipmap-container-format.md` in agent memory for
   the precedent of a previously "opaque" DCS format turning out to be a
   simple documented container plus zlib chunks), a from-scratch Python parser
   in `world-model/src/` becomes viable and would give **real polylines**
   (a strict improvement over OSM's ~1-5 km real-world displacement noted in
   M1/M3 recon) at essentially zero DCS-side runtime cost.
2. **If the format is opaque/compiled** (e.g. LuaJIT bytecode, a proprietary
   binary graph with no recoverable schema), the current M5 plan (live-mission
   point sampling via `land.getSurfaceType`/`land.findPathOnRoads`, or the
   `Terrain.*` cockpit-Lua equivalents if a cockpit context is more convenient
   than Mission Scripting) remains necessary, but the road *routing/pathfinding
   queries* (`findPathOnRoads`, `getClosestPointOnRoads`) can still be used to
   **trace actual road centerlines at high sample density** rather than
   guessing polylines from OSM alone — i.e. use the API to walk each road
   segment via repeated `getClosestPointOnRoads` probing rather than treating
   it as a mesh-only surface classifier. This is slower than static extraction
   but still DCS-authoritative and strictly more accurate than pure OSM.
3. In either case, **OSM remains the right source for road *attributes*** DCS
   likely does not encode at all (road class/surface/name), per the existing
   M3 pipeline design — this only affects whether road *geometry* can be
   DCS-native instead of OSM-derived.

### Unresolved

- **The actual byte structure of `.rn4`/`.routes` is unverified** — this is
  the single biggest open question and the probe script above should resolve
  it (plaintext vs. binary vs. known container).
- **Two ED forum threads were found but not read**: "NAV / Terrain / Road
  Database" (`forum.dcs.world/topic/164627-nav-terrain-road-database/`) and
  "Creating custom terrain/map for DCS: World"
  (`forum.dcs.world/topic/271289-creating-custom-terrainmap-for-dcs-world/`,
  which may cover terrain-SDK road authoring for terrain module developers).
  Both returned HTTP 403 to automated fetch this session (consistent with
  prior recon — `forum.dcs.world` blocks WebFetch). **If the user can open
  either URL manually and paste the content back, that is the fastest way to
  resolve whether ED or terrain-SDK developers have ever documented the
  `.rn4` format**, without needing the WSL probe round-trip.
- **`Terrain.*` cockpit-Lua environment scope is unconfirmed** — it's inferred
  from the doc site's URL path (`Aircraft/Lua/Modules/Terrain`) to be aircraft/
  avionics-Lua-accessible, not confirmed against the installed DCS version or
  against Mi-24P/Petrovich's own Lua specifically. Worth checking against
  Mi-8MTV2 or Mi-24P cockpit Lua source (if accessible read-only) if this
  environment turns out to matter for Petrobrain runtime (not World Model
  Builder) work later.
- **`modding.caffeinesimulations.com` is an unofficial, community-run doc
  site** — its function list should be treated as a lead, not verified fact,
  until cross-checked against the actual installed DCS Lua environment (e.g.
  by probing whether `Terrain.findPathOnRoads` is callable and what it
  returns) or against ED's own SDK documentation if that exists.
