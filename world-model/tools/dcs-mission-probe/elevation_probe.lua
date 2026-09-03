--[[
M4 Stage 2 probe: dump land.getHeight(...) output for a full 10x10 (100
point) regular grid covering the Gemerek bbox already used in M1-M3
(south=39.170, west=36.050, north=39.195, east=36.090), from inside a
running DCS mission.

Stage 1 (an 8-point smoke test over this same bbox) already confirmed both
open questions this probe depends on: land.getHeight returns plausible
meter values (1163-1340m, consistent with the Sivas plateau region) and
io.open/write under the user-authorized MissionScripting.lua edit works
with no truncation -- see world-model/research/2026-09-03-m4-elevation-recon.md
and tests/test_dcs_grid.py's fixture (the Stage 1 run's real output). This
probe scales that same mechanism up to a full grid for the DEM comparison
(elevation.dem.SrtmTile vs. this output, via tools/inspect_elevation.py).

PREREQUISITE (one-time manual step, probe-only -- never required for
pipeline code, not a permanent install change): uncomment the `io`/`lfs`
sanitizeModule lines in the installed Scripts/MissionScripting.lua (same as
Stage 1 -- if you already reverted that edit after Stage 1, redo it before
running this).

HOW TO RUN (manual, in-game on the Windows DCS machine):
1. Uncomment the io/lfs lines in Scripts/MissionScripting.lua (see above).
2. Copy this file to a location DCS can read, e.g. alongside a test mission.
3. In the DCS Mission Editor, create a new mission on the Syria terrain.
4. Add a trigger: type ONCE, condition TIME MORE 5, action DO SCRIPT FILE,
   pointing at this elevation_probe.lua file.
5. Save the mission, start it, let it run ~10-15 seconds (100 points is
   more work than Stage 1's 8, but still trivial for land.getHeight), then
   exit.
6. Output is written to Saved Games/DCS/Logs/elevation_probe_output.jsonl
   (one JSON object per line, one line per grid point) -- this OVERWRITES
   Stage 1's 8-point output file; that data is already captured in
   tests/test_dcs_grid.py's hardcoded fixture, so this is safe.
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

-- Full grid: 10x10 = 100 points, evenly spaced across the Gemerek bbox
-- (south=39.170, west=36.050, north=39.195, east=36.090), precomputed
-- offline in Python via coordinates.wgs84_to_dcs("Syria", lat, lon) -- see
-- the M4 plan Stage 2. Point spacing is ~280-380m depending on axis
-- (bbox isn't square in meters), close to the plan's proposed ~300m.
local points = {
  { name = "r0c0", x = 459922.0050, z = 27944.7275 },
  { name = "r0c1", x = 459909.5144, z = 28328.7608 },
  { name = "r0c2", x = 459897.0426, z = 28712.7938 },
  { name = "r0c3", x = 459884.5897, z = 29096.8264 },
  { name = "r0c4", x = 459872.1557, z = 29480.8587 },
  { name = "r0c5", x = 459859.7405, z = 29864.8908 },
  { name = "r0c6", x = 459847.3442, z = 30248.9225 },
  { name = "r0c7", x = 459834.9668, z = 30632.9539 },
  { name = "r0c8", x = 459822.6083, z = 31016.9850 },
  { name = "r0c9", x = 459810.2686, z = 31401.0158 },
  { name = "r1c0", x = 460230.3505, z = 27954.7643 },
  { name = "r1c1", x = 460217.8595, z = 28338.7824 },
  { name = "r1c2", x = 460205.3875, z = 28722.8002 },
  { name = "r1c3", x = 460192.9343, z = 29106.8177 },
  { name = "r1c4", x = 460180.5001, z = 29490.8349 },
  { name = "r1c5", x = 460168.0847, z = 29874.8518 },
  { name = "r1c6", x = 460155.6881, z = 30258.8683 },
  { name = "r1c7", x = 460143.3105, z = 30642.8846 },
  { name = "r1c8", x = 460130.9517, z = 31026.9005 },
  { name = "r1c9", x = 460118.6118, z = 31410.9162 },
  { name = "r2c0", x = 460538.6960, z = 27964.8017 },
  { name = "r2c1", x = 460526.2048, z = 28348.8047 },
  { name = "r2c2", x = 460513.7325, z = 28732.8073 },
  { name = "r2c3", x = 460501.2791, z = 29116.8096 },
  { name = "r2c4", x = 460488.8446, z = 29500.8117 },
  { name = "r2c5", x = 460476.4289, z = 29884.8134 },
  { name = "r2c6", x = 460464.0321, z = 30268.8148 },
  { name = "r2c7", x = 460451.6542, z = 30652.8159 },
  { name = "r2c8", x = 460439.2952, z = 31036.8167 },
  { name = "r2c9", x = 460426.9551, z = 31420.8172 },
  { name = "r3c0", x = 460847.0416, z = 27974.8397 },
  { name = "r3c1", x = 460834.5502, z = 28358.8275 },
  { name = "r3c2", x = 460822.0776, z = 28742.8150 },
  { name = "r3c3", x = 460809.6240, z = 29126.8022 },
  { name = "r3c4", x = 460797.1892, z = 29510.7890 },
  { name = "r3c5", x = 460784.7733, z = 29894.7756 },
  { name = "r3c6", x = 460772.3763, z = 30278.7618 },
  { name = "r3c7", x = 460759.9981, z = 30662.7478 },
  { name = "r3c8", x = 460747.6389, z = 31046.7334 },
  { name = "r3c9", x = 460735.2985, z = 31430.7187 },
  { name = "r4c0", x = 461155.3873, z = 27984.8783 },
  { name = "r4c1", x = 461142.8957, z = 28368.8509 },
  { name = "r4c2", x = 461130.4229, z = 28752.8233 },
  { name = "r4c3", x = 461117.9690, z = 29136.7953 },
  { name = "r4c4", x = 461105.5339, z = 29520.7670 },
  { name = "r4c5", x = 461093.1178, z = 29904.7384 },
  { name = "r4c6", x = 461080.7205, z = 30288.7095 },
  { name = "r4c7", x = 461068.3421, z = 30672.6803 },
  { name = "r4c8", x = 461055.9826, z = 31056.6507 },
  { name = "r4c9", x = 461043.6419, z = 31440.6209 },
  { name = "r5c0", x = 461463.7332, z = 27994.9175 },
  { name = "r5c1", x = 461451.2413, z = 28378.8750 },
  { name = "r5c2", x = 461438.7682, z = 28762.8321 },
  { name = "r5c3", x = 461426.3141, z = 29146.7890 },
  { name = "r5c4", x = 461413.8788, z = 29530.7455 },
  { name = "r5c5", x = 461401.4624, z = 29914.7018 },
  { name = "r5c6", x = 461389.0649, z = 30298.6577 },
  { name = "r5c7", x = 461376.6862, z = 30682.6133 },
  { name = "r5c8", x = 461364.3265, z = 31066.5687 },
  { name = "r5c9", x = 461351.9856, z = 31450.5237 },
  { name = "r6c0", x = 461772.0791, z = 28004.9573 },
  { name = "r6c1", x = 461759.5870, z = 28388.8996 },
  { name = "r6c2", x = 461747.1137, z = 28772.8416 },
  { name = "r6c3", x = 461734.6593, z = 29156.7833 },
  { name = "r6c4", x = 461722.2238, z = 29540.7247 },
  { name = "r6c5", x = 461709.8071, z = 29924.6658 },
  { name = "r6c6", x = 461697.4093, z = 30308.6065 },
  { name = "r6c7", x = 461685.0304, z = 30692.5470 },
  { name = "r6c8", x = 461672.6704, z = 31076.4872 },
  { name = "r6c9", x = 461660.3293, z = 31460.4270 },
  { name = "r7c0", x = 462080.4252, z = 28014.9977 },
  { name = "r7c1", x = 462067.9328, z = 28398.9248 },
  { name = "r7c2", x = 462055.4592, z = 28782.8517 },
  { name = "r7c3", x = 462043.0046, z = 29166.7782 },
  { name = "r7c4", x = 462030.5688, z = 29550.7044 },
  { name = "r7c5", x = 462018.1519, z = 29934.6304 },
  { name = "r7c6", x = 462005.7539, z = 30318.5560 },
  { name = "r7c7", x = 461993.3748, z = 30702.4813 },
  { name = "r7c8", x = 461981.0145, z = 31086.4063 },
  { name = "r7c9", x = 461968.6731, z = 31470.3310 },
  { name = "r8c0", x = 462388.7714, z = 28025.0387 },
  { name = "r8c1", x = 462376.2787, z = 28408.9507 },
  { name = "r8c2", x = 462363.8049, z = 28792.8623 },
  { name = "r8c3", x = 462351.3500, z = 29176.7737 },
  { name = "r8c4", x = 462338.9140, z = 29560.6848 },
  { name = "r8c5", x = 462326.4968, z = 29944.5955 },
  { name = "r8c6", x = 462314.0986, z = 30328.5060 },
  { name = "r8c7", x = 462301.7192, z = 30712.4161 },
  { name = "r8c8", x = 462289.3587, z = 31096.3260 },
  { name = "r8c9", x = 462277.0170, z = 31480.2355 },
  { name = "r9c0", x = 462697.1176, z = 28035.0803 },
  { name = "r9c1", x = 462684.6247, z = 28418.9771 },
  { name = "r9c2", x = 462672.1507, z = 28802.8736 },
  { name = "r9c3", x = 462659.6955, z = 29186.7698 },
  { name = "r9c4", x = 462647.2593, z = 29570.6657 },
  { name = "r9c5", x = 462634.8419, z = 29954.5613 },
  { name = "r9c6", x = 462622.4434, z = 30338.4566 },
  { name = "r9c7", x = 462610.0637, z = 30722.3516 },
  { name = "r9c8", x = 462597.7030, z = 31106.2463 },
  { name = "r9c9", x = 462585.3611, z = 31490.1406 },
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
