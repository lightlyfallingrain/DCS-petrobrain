--[[
M1 recon probe: dump coord.LOtoLL(...) output for the theatre origin (0,0,0)
and for every airbase returned by world.getAirbases(), from inside a running
DCS mission.

Why this exists: coord.LOtoLL / coord.LLtoLO are documented (Hoggit wiki) as
"Mission Scripting" environment functions — there is no evidence they are
callable from an offline/external process. This script is the minimal
reproduction of that claim: if it runs and produces output inside a live
mission, that confirms the environment requirement and gives us a live,
DCS-native x/z<->ll sample set to compare against pydcs's community-derived
Syria projection parameters (see world-model/research/2026-09-02-m1-coordinate-transform.md).

NOTE on evidence value: the lat/lon values this script reports come FROM
coord.LOtoLL itself. They are NOT independent real-world ground truth — do
not use them alone to validate the projection against reality. Cross-check
airbase lat/lon output here against an independently-sourced real-world
value (e.g. published Damascus Intl / OSDI ARP) for a genuine external
control point. Comparing this script's own output against a
pydcs-reimplemented transform only tests self-consistency between two things
that both ultimately trace back to coord.LOtoLL.

HOW TO RUN (manual, in-game on the Windows DCS machine):
1. Copy this file to a location DCS can read, e.g. alongside a test mission,
   or reference it directly by absolute path from a trigger.
2. In the DCS Mission Editor, create a new mission on the Syria terrain.
3. Add a trigger: type ONCE, condition TIME MORE 5, action DO SCRIPT FILE,
   pointing at this coord_probe.lua file (or paste its contents into a
   DO SCRIPT action).
4. Save the mission, start it, let it run ~10 seconds, then exit.
5. Output is written to Saved Games/DCS/Logs/coord_probe_output.json
   (see DCS_SAVED_GAMES_PATH in WORKFLOW.md / probe_dcs_install.sh).
6. Copy that JSON file into win-mac-sync/wsl-output/, sync back to the Mac,
   then move it into world-model/data/raw/dcs/<date>/ and note it in the
   corresponding research/*.md file.

This script performs no writes to the DCS installation itself — it only
writes to the user's Saved Games/DCS/Logs directory, which is standard
mission-script log output, not an installation change.

CAVEAT (unverified, flag before running): by default DCS's mission-scripting
sandbox (Scripts/MissionScripting.lua under the install dir) strips `io` and
`lfs` from the environment. If they are stripped, `io.open` below will be
nil and this script will error instead of writing output. The commonly
cited community workaround is editing MissionScripting.lua to re-expose
`io`/`lfs` — but that IS a modification to the DCS installation, which
conflicts with this project's read-only invariant. Do not do that without
explicit user sign-off; instead, if this script fails for that reason,
fall back to trigger.action.outText(...) to print the JSON to the in-game
message log/track file and transcribe it manually, or use a DO SCRIPT
FILE trigger combined with existing mission frameworks (e.g. MOOSE, which
many users already have io/lfs whitelisted for) rather than editing DCS
files directly.
--]]

local out = {}

-- Theatre origin
local zero = { x = 0, y = 0, z = 0 }
local lat0, lon0, alt0 = coord.LOtoLL(zero)
out.origin = { x = 0, z = 0, lat = lat0, lon = lon0 }

-- Every airbase in the theatre (includes airports, FARPs, ships with decks)
out.airbases = {}
local bases = world.getAirbases()
for i, base in ipairs(bases) do
  local ok, name = pcall(function() return base:getName() end)
  local ok2, point = pcall(function() return base:getPoint() end)
  if ok and ok2 and point then
    local lat, lon, alt = coord.LOtoLL(point)
    table.insert(out.airbases, {
      name = name,
      x = point.x,
      z = point.z,
      lat = lat,
      lon = lon,
    })
  end
end

-- Minimal JSON serialization (avoid depending on external json.lua)
local function jsonEscape(s)
  return tostring(s):gsub('"', '\\"')
end

local function numOrNull(n)
  if n == nil then return "null" end
  return string.format("%.8f", n)
end

local lines = {}
table.insert(lines, "{")
table.insert(lines, string.format(
  '  "origin": {"x": %s, "z": %s, "lat": %s, "lon": %s},',
  numOrNull(out.origin.x), numOrNull(out.origin.z),
  numOrNull(out.origin.lat), numOrNull(out.origin.lon)))
table.insert(lines, '  "airbases": [')
for i, ab in ipairs(out.airbases) do
  local comma = (i < #out.airbases) and "," or ""
  table.insert(lines, string.format(
    '    {"name": "%s", "x": %s, "z": %s, "lat": %s, "lon": %s}%s',
    jsonEscape(ab.name), numOrNull(ab.x), numOrNull(ab.z),
    numOrNull(ab.lat), numOrNull(ab.lon), comma))
end
table.insert(lines, "  ]")
table.insert(lines, "}")

local text = table.concat(lines, "\n")

local logDir = lfs.writedir() .. "Logs/"
local f = io.open(logDir .. "coord_probe_output.json", "w")
if f then
  f:write(text)
  f:close()
  trigger.action.outText("coord_probe: wrote " .. logDir .. "coord_probe_output.json", 20)
else
  trigger.action.outText("coord_probe: FAILED to open output file in " .. logDir, 20)
end
