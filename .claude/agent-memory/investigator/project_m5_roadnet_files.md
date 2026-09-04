---
name: m5-roadnet-files
description: DCS ships per-theatre .rn4/.routes road network files and per-airfield taxiway .rn4 files; format undocumented, scripting API is query-only (no bulk export)
metadata:
  type: project
---

Every installed DCS terrain (Syria, Afghanistan, Caucasus, Kola, MarianaIslands
checked) ships `Mods/terrains/<Terrain>/roads/<Terrain>.rn4` + `<Terrain>.routes`,
plus one `AirfieldsTaxiways/<Airfield>.rn4` per airfield. Confirmed only via
filename listing (`world-model/data/raw/dcs/2026-09-02/DCS-files.txt`) — bytes
never inspected (no Mac-side DCS filesystem access; requires WSL round-trip).

No public doc of the `.rn4`/`.routes` binary format found anywhere: not Hoggit,
not pydcs, not dcs-liberation/dcs-retribution, not
`JonathanTurnock/dcs-global-terrain-database` (a community GeoJSON terrain DB
project that hand-curates rather than parses terrain files). dcs-liberation's
"on-road" convoy routing uses the Mission Editor's live "On Road" waypoint
option, not static file parsing.

The `Terrain` Lua module (cockpit/avionics-Lua, documented unofficially at
`modding.caffeinesimulations.com/Aircraft/Lua/Modules/Terrain/` — direct
WebFetch 403s, use `r.jina.ai/<url>` proxy) mirrors Mission Scripting's
`land.*` road functions: `findPathOnRoads`, `getClosestPointOnRoads`,
`getClosestValidPoint`, `FindNearestPoint`, `FindOptimalPath`. All are
point/path queries; there is no bulk "get all road segments" function, and
the `roadnet` argument to airfield helpers is described as an opaque
"filepath string" the engine consumes internally, not a table the script
walks. See [[../architect/project_m5_storage_decision]] type memories if
they exist, and world-model/research/2026-09-03-m5-roadnet-file-recon.md for
full findings and the byte-inspection probe script
(world-model/tools/wsl/probe_syria_roadnet_files.sh, not yet run).

Two forum.dcs.world threads found but unread (403 to automated fetch, ask
user to paste manually if this becomes load-bearing again): "NAV / Terrain /
Road Database" (topic/164627) and "Creating custom terrain/map for DCS: World"
(topic/271289 — possible terrain-SDK road-authoring docs for terrain module
developers).
