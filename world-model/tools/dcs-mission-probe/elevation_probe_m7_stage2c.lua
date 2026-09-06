--[[
M7 Stage 2c probe: DCS live-probe spot-check for syria-full SRTM alignment
validation. Dumps land.getHeight(...) for a small set of points scattered
across the whole Syria theatre (one per major region/airbase cluster), NOT
a dense grid -- per world-model/docs/M7_RUN_INSTRUCTIONS.md Stage 2c: "small,
scattered point set spread across the theatre... not a dense grid".

Points below are the 8 Syria control points already vetted in
world-model/tests/control_points.py (DCS-authoritative x/z from beacons.lua,
cross-checked non-circularly against independently-published real-world ARPs):
Damascus, Latakia, Beirut, Aleppo (Stage 1 set) + Rene Mouawad/Klieat (coastal),
Mezzeh (urban), Deir ez-Zor (desert), Kahramanmaras (mountainous) (Stage 3 set).
Reusing these gives geographic spread AND a free cross-check against SRTM at
points whose real-world lat/lon is already independently known.

Mechanism unchanged from M4/M5's elevation_probe.lua (per the plan's Stage 2:
"no chunking/resumability redesign needed" -- 8 points is trivial, one
blocking loop is fine here even though terrain_probe_*.lua's larger grids
use timer.scheduleFunction chunking instead).

PREREQUISITE (one-time manual step, probe-only -- never required for
pipeline code): uncomment the `io`/`lfs` sanitizeModule lines in the
installed Scripts/MissionScripting.lua.

HOW TO RUN (manual, in-game on the Windows DCS machine):
1. Uncomment the io/lfs lines in Scripts/MissionScripting.lua (see above).
2. Copy this file to a location DCS can read, e.g. alongside a test mission.
3. In the DCS Mission Editor, create a new mission on the SYRIA terrain
   (not Gemerek/Caucasus -- this probe's points are Syria x/z).
4. Add a trigger: type ONCE, condition TIME MORE 5, action DO SCRIPT FILE,
   pointing at this elevation_probe.lua file.
5. Save the mission, start it, let it run a few seconds (8 points, trivial),
   then exit.
6. Output is written to Saved Games/DCS/Logs/elevation_probe_output.jsonl
   (one JSON object per line).
7. Copy that file into win-mac-sync/wsl-output/ via
   world-model/tools/wsl/collect_elevation_log.sh (run on the Windows/WSL
   side), sync back to the Mac, then move it into
   world-model/data/raw/dcs/syria/probes/syria-full-spot-check.jsonl and
   run tools/validate_m7_stage2_elevation.py against it.

This script performs no writes to the DCS installation itself -- it only
writes to the user's Saved Games/DCS/Logs directory, which is standard
mission-script log output, not an installation change. The io/lfs sandbox
edit itself IS an installation change, but is explicitly user-authorized,
scoped to investigation probes, and not made by this script.
--]]

local points = {
  { name = "damascus_osdi",       x = -179748.32812500, z = 50728.26562500 },
  { name = "latakia_oslk",        x = 43237.96875000,   z = 5841.16455078 },
  { name = "beirut_olba",         x = -132952.73437500, z = -42476.58203125 },
  { name = "aleppo_osap",         x = 126175.296875,    z = 123040.015625 },
  { name = "klieat_olka_coastal", x = -48636.152344,    z = 7884.588867 },
  { name = "mezzeh_os67_urban",   x = -171265.828125,   z = 25122.662109 },
  { name = "deir_ez_zor_osdz_desert", x = 25885.554688, z = 390774.875000 },
  { name = "kahramanmaras_ltcn_mountainous", x = 276904.968750, z = 101895.742188 },
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
