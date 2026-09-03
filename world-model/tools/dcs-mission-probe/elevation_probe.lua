--[[
M4 Stage 1 recon probe: dump land.getHeight(...) output for a small,
hardcoded handful of DCS (x, z) points scattered across the Gemerek bbox
already used in M1-M3 (south=39.170, west=36.050, north=39.195,
east=36.090), from inside a running DCS mission.

Why this exists: land.getHeight is documented (Hoggit wiki, DCS_func_getHeight)
as a Mission Scripting-only function, same environment as coord.LOtoLL (M1's
coord_probe.lua). It has never been called against the live install before
this probe -- see world-model/research/2026-09-03-m4-elevation-recon.md
"Unresolved". This is the first real test of both (a) land.getHeight itself
returning plausible values, and (b) io/lfs write access under the
user-authorized MissionScripting.lua edit (see below) -- deliberately a
small-N smoke test, not the full grid, so either failure mode is cheap to
diagnose before committing to a ~100-point run.

PREREQUISITE (one-time manual step, probe-only -- never required for
pipeline code, not a permanent install change): uncomment the `io`/`lfs`
sanitizeModule lines in the installed Scripts/MissionScripting.lua. Unlike
coord_probe.lua (M1), this probe uses io.open directly rather than
net.log/dcs.log, per this session's explicit user authorization -- see the
M4 plan and research note for the resolved decision. Do NOT uncomment io/lfs
for any other purpose; revert the edit once M4's probe runs are done unless
the user says otherwise (see M4 research note close-out).

HOW TO RUN (manual, in-game on the Windows DCS machine):
1. Uncomment the io/lfs lines in Scripts/MissionScripting.lua (see above).
2. Copy this file to a location DCS can read, e.g. alongside a test mission.
3. In the DCS Mission Editor, create a new mission on the Syria terrain.
4. Add a trigger: type ONCE, condition TIME MORE 5, action DO SCRIPT FILE,
   pointing at this elevation_probe.lua file.
5. Save the mission, start it, let it run ~10 seconds, then exit.
6. Output is written to Saved Games/DCS/Logs/elevation_probe_output.jsonl
   (one JSON object per line, one line per grid point).
7. Copy that file into win-mac-sync/wsl-output/ via
   world-model/tools/wsl/collect_elevation_log.sh (run on the Windows/WSL
   side), sync back to the Mac, then move it into
   world-model/data/raw/dcs/<date>/ and note it in the corresponding
   research/*.md file.

This script performs no writes to the DCS installation itself -- it only
writes to the user's Saved Games/DCS/Logs directory, which is standard
mission-script log output, not an installation change. The io/lfs sandbox
edit itself IS an installation change, but is explicitly user-authorized,
scoped to investigation probes, and not made by this script.
--]]

-- Smoke-test grid: 8 points scattered across the Gemerek bbox (4 corners +
-- center + 3 interior), precomputed offline in Python via
-- coordinates.wgs84_to_dcs("Syria", lat, lon) -- see the M4 plan Stage 1.
local points = {
  { name = "corner_sw", x = 459922.01, z = 27944.73 },
  { name = "corner_se", x = 459810.27, z = 31401.02 },
  { name = "corner_nw", x = 462697.12, z = 28035.08 },
  { name = "corner_ne", x = 462585.36, z = 31490.14 },
  { name = "center", x = 461253.50, z = 29717.74 },
  { name = "interior_1", x = 460767.96, z = 29269.60 },
  { name = "interior_2", x = 461517.05, z = 30158.66 },
  { name = "interior_3", x = 462052.57, z = 30781.25 },
}

local logDir = lfs.writedir() .. "Logs/"
local f = io.open(logDir .. "elevation_probe_output.jsonl", "w")

if f then
  for _, p in ipairs(points) do
    local ok, height = pcall(land.getHeight, { x = p.x, y = p.z })
    local heightStr = "null"
    if ok and height ~= nil then
      heightStr = string.format("%.4f", height)
    end
    local line = string.format(
      '{"name": "%s", "x": %.4f, "z": %.4f, "height_m": %s}',
      p.name, p.x, p.z, heightStr
    )
    f:write(line .. "\n")
  end
  f:close()
  trigger.action.outText(
    "elevation_probe: wrote " .. logDir .. "elevation_probe_output.jsonl", 20
  )
else
  trigger.action.outText(
    "elevation_probe: FAILED to open output file in " .. logDir
    .. " -- check that io/lfs are uncommented in MissionScripting.lua", 20
  )
end
