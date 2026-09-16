--[[
Power-line recon probe (Stage A / discovery): confirm whether power-line
scenery (transmission-line spans, wooden distribution poles, substations,
power plants) actually exists as placed Object.Category.SCENERY objects on
the Syria terrain, and if so, capture their exact DCS x/y/z via
SceneryObject:getPoint() -- see
world-model/research/2026-09-13-dcs-power-lines-recon.md for the recon this
supports.

WHY THIS SHAPE: static-file recon (Mods/terrains/Syria/Models/*/StructTable.sht)
confirmed the model catalog contains power_trans_line_big, power_pole_wooden
(Environment/StructTable.sht), power_plant_01 (Misc/StructTable.sht), and
power_trans_station / Power_generator_01 / bengal_power_hub
(Small/StructTable.sht) -- i.e. these ARE real placeable scenery types in
Syria's own asset catalog, not borrowed/unused names. Scenes/Syria.scn5 (the
per-terrain "landscape5::Scene5File" placement database, ~5.5GB, format
undecoded) independently references "power_trans_line_big" and
"power_pole_wooden" in its own string table at byte offsets 565438/8598 and
14865 respectively -- consistent with (but not proof of) these being
instantiated somewhere on the map. This probe is the cheap way to get a
definitive yes/no plus exact coordinates, instead of reverse-engineering the
5.5GB binary placement format.

world.searchObjects(Object.Category.SCENERY, volume, handler) and
Object.Category.SCENERY are Hoggit-documented (DCS_Class_Scenery_Object,
DCS_func_searchObjects, DCS_func_getCategory) but NOT yet exercised against
this install -- treat with the same first-run caution M5's
terrain_probe_smoke.lua gave land.getSurfaceType. All engine calls below are
pcall-wrapped for that reason.

STAGE A SCOPE (this script): search a SPHERE volume around each of the
first N airbases returned by world.getAirbases() (N=3 by default -- an
incremental-ladder smoke test, per the project convention of never jumping
straight to full scale) rather than hardcoding coordinates, since we do not
have a verified real-world power-line location to convert into DCS x/z (the
whole reason OSM was rejected as a source is that its positions are ~1km off
DCS ground truth). Airbases are plausible anchors: they are real, exact,
already-verified DCS points (M7 theatre-extent recon), and real airfields
are frequently near substations/transmission corridors.

Two output streams, both to Saved Games/DCS/Logs/:
  - power_line_probe_matches.jsonl: one line per SCENERY object whose
    getTypeName() matched a power-infrastructure keyword, with exact
    getPoint() (DCS x/y/z, y=altitude) and getName() (instance id).
  - power_line_probe_typenames.jsonl: one line per DISTINCT getTypeName()
    seen in any searched sphere (whether or not it matched), written once at
    the end -- a discovery catalog in case power-line geometry uses a naming
    convention this script's keyword list didn't anticipate (e.g. separate
    "wire"/"fn_support" sub-objects seen adjacent to power_trans_line_big in
    Syria.scn5's string table -- if those turn out to be independently
    placed SCENERY objects rather than parts of one prefab mesh, they will
    show up here even though they aren't in MATCH_KEYWORDS).

HOW TO RUN (manual, in-game on the Windows DCS machine):
1. Uncomment the io/lfs sanitizeModule lines in the installed
   Scripts/MissionScripting.lua (same one-time, probe-only, user-authorized
   edit as M4/M5 -- see WORKFLOW.md; revert afterwards if you normally do).
2. Copy this file to a location DCS can read, e.g. alongside a test mission.
3. In the DCS Mission Editor, create a new mission on the Syria terrain
   (any start conditions are fine -- this probe does not need a player
   aircraft airborne).
4. Add a trigger: type ONCE, condition TIME MORE 5, action DO SCRIPT FILE,
   pointing at this file.
5. Save the mission, start it, and watch for an on-screen
   "power_line_probe: ..." message. Each airbase sphere search is one
   blocking engine call of unknown cost (never exercised before) -- if DCS
   visibly hangs for longer than ~30-60s on a single airbase, or becomes
   unresponsive, stop and report that as a finding (a probe-scale ceiling),
   rather than waiting indefinitely or enlarging N first.
6. Copy BOTH output files out of Saved Games/DCS/Logs/ via
   world-model/tools/wsl/collect_terrain_probe_log.sh (adjust the filename
   it copies, or copy manually), sync back, then move into
   world-model/data/raw/dcs/<date>/ and note in the corresponding
   research/*.md file.
7. If matches.jsonl is non-empty: Stage A is confirmed positive. Report back
   the matched type names and a couple of sample coordinates; a full-theatre
   chunked sweep (all airbases, plus a grid of spheres covering the M7
   bbox away from any airbase, following the Stage 5 junction-streaming
   chunking pattern) is the natural follow-on, left for Architect/Implementer
   to design as pipeline code.
   If matches.jsonl is empty but typenames.jsonl has entries: widen
   MATCH_KEYWORDS below using whatever type names typenames.jsonl actually
   contains, and rerun.
   If both are empty across all N airbases: widen N (more airbases) or
   RADIUS_M before concluding scenery-based extraction doesn't reach actual
   line placements near settlements.

This script performs no writes to the DCS installation itself -- it only
writes to the user's Saved Games/DCS/Logs directory, standard mission-script
log output, not an installation change. The io/lfs sandbox edit itself IS an
installation change, but is explicitly user-authorized, scoped to
investigation probes, and not made by this script.
--]]

-- How many airbases (in world.getAirbases() order) to search around in this
-- Stage A smoke test. Raise once Stage A confirms the mechanism works and
-- costs are acceptable.
local AIRBASE_LIMIT = 3

-- Sphere search radius around each airbase point, in metres.
local RADIUS_M = 20000

-- Case-insensitive substrings of SceneryObject:getTypeName() that count as
-- a "power infrastructure" match, per the Syria StructTable.sht catalog
-- read during static recon.
local MATCH_KEYWORDS = {
  "power_trans_line",
  "power_pole",
  "power_plant",
  "power_trans_station",
  "power_generator",
  "power_hub",
  "electric_box",
}

local function typeNameMatches(typeName)
  local lower = string.lower(typeName)
  for _, kw in ipairs(MATCH_KEYWORDS) do
    if string.find(lower, kw, 1, true) then
      return true
    end
  end
  return false
end

local matchesPath = lfs.writedir() .. "Logs/power_line_probe_matches.jsonl"
local typenamesPath = lfs.writedir() .. "Logs/power_line_probe_typenames.jsonl"

local matchesFile = io.open(matchesPath, "w")
if not matchesFile then
  trigger.action.outText(
    "power_line_probe: FAILED to create " .. matchesPath
    .. " -- check that io/lfs are uncommented in MissionScripting.lua", 20
  )
  return
end

local seenTypeNames = {} -- set: typeName -> true, dedup across all spheres
local matchCount = 0
local airbasesSearched = 0
local errors = {}

local okAirbases, airbases = pcall(world.getAirbases)
if not okAirbases or type(airbases) ~= "table" then
  matchesFile:close()
  trigger.action.outText(
    "power_line_probe: world.getAirbases() FAILED -- " .. tostring(airbases), 20
  )
  return
end

local limit = math.min(AIRBASE_LIMIT, #airbases)

for i = 1, limit do
  local ab = airbases[i]
  local okName, abName = pcall(ab.getName, ab)
  if not okName then abName = "?" end
  local okPoint, abPoint = pcall(ab.getPoint, ab)

  if okPoint and abPoint then
    local volume = {
      id = world.VolumeType.SPHERE,
      params = {
        point = abPoint,
        radius = RADIUS_M,
      },
    }

    local function handler(foundItem, _val)
      local okType, typeName = pcall(foundItem.getTypeName, foundItem)
      if okType and typeName then
        if not seenTypeNames[typeName] then
          seenTypeNames[typeName] = true
        end
        if typeNameMatches(typeName) then
          local okObjName, objName = pcall(foundItem.getName, foundItem)
          if not okObjName then objName = "?" end
          local okObjPoint, objPoint = pcall(foundItem.getPoint, foundItem)
          if okObjPoint and objPoint then
            local line = string.format(
              '{"airbase": "%s", "type_name": "%s", "object_name": "%s", '
              .. '"x": %.4f, "y": %.4f, "z": %.4f}',
              abName, typeName, objName, objPoint.x, objPoint.y, objPoint.z
            )
            matchesFile:write(line .. "\n")
            matchCount = matchCount + 1
          end
        end
      end
      return true -- keep searching for more objects in this volume
    end

    local okSearch, searchErr = pcall(
      world.searchObjects, Object.Category.SCENERY, volume, handler
    )
    if not okSearch then
      table.insert(errors, abName .. ": " .. tostring(searchErr))
    else
      airbasesSearched = airbasesSearched + 1
    end
  else
    table.insert(errors, abName .. ": getPoint failed")
  end
end

matchesFile:close()

local typenamesFile = io.open(typenamesPath, "w")
if typenamesFile then
  for typeName, _ in pairs(seenTypeNames) do
    typenamesFile:write(string.format('{"type_name": "%s"}\n', typeName))
  end
  typenamesFile:close()
end

local distinctCount = 0
for _ in pairs(seenTypeNames) do distinctCount = distinctCount + 1 end

trigger.action.outText(
  "power_line_probe: searched " .. airbasesSearched .. "/" .. limit
  .. " airbases, " .. matchCount .. " matches, " .. distinctCount
  .. " distinct scenery type names seen. Wrote " .. matchesPath
  .. " and " .. typenamesPath
  .. (#errors > 0 and (" -- " .. #errors .. " errors, see mission log") or ""),
  30
)

for _, e in ipairs(errors) do
  env.info("power_line_probe error: " .. e)
end
