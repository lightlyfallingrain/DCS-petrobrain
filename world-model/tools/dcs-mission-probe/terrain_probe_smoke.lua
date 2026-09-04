--[[
M5 Stage 3 rung 1/3 -- 100-200pt smoke test: dump land.getHeight(...) and land.getSurfaceType(...)
output for 121 points of the Latakia 41x41 (500m-spacing, 1,681-point)
probe grid, from inside a running DCS mission.

Grid coordinate system (see world-model/src/build/pipeline.py's
`probe_grid_for_region`): origin (row=0, col=0) at DCS x=34934.892,
z=-4314.924 (the latakia-20km region's south-west corner), spacing
500m, cell (row, col) at x = origin_x + row*500, z = origin_z + col*500.
Every point name below is "r{row}c{col}" into that same grid so
world-model/src/build/ingest_probe.py can place a partial run's points
directly into the right cell of the full grid -- see that module's
docstring on the incremental-ladder / partial-grid design.

**land.getSurfaceType has never been called against this install before**
this probe -- treated with the same caution M4 gave land.getHeight before
its Stage 1 smoke test (see plans/m5-first-persistent-model/plan.md
Finding C). Documented enum (Hoggit): LAND=1, SHALLOW_WATER=2, WATER=3,
ROAD=4, RUNWAY=5. This script wraps both calls in pcall, matching
elevation_probe.lua's (M4) proven pattern -- a failed call for a point
writes JSON null for that field rather than aborting the whole run;
ingest_probe.py raises loudly on any null it finds, so a partial failure is
never silently accepted into the store.

**Incremental ladder -- run rungs in order, not all at once.**
Per the M5 checklist: 100-200pt smoke test first (terrain_probe_smoke.lua),
then ~500 (terrain_probe_500.lua), then the full 1,681
(terrain_probe_full.lua) -- never jump straight to full scale. Each rung is
this same script structure with a different point-count subset of the same
grid; stop and reassess before the next rung if this one shows non-linear
cost or DCS becomes unresponsive.

HOW TO RUN (manual, in-game on the Windows DCS machine):
1. Uncomment the io/lfs sanitizeModule lines in the installed
   Scripts/MissionScripting.lua (same as M4 -- if you already reverted that
   edit after M4, redo it before running this; probe-only, never a
   permanent install change, see WORKFLOW.md).
2. Copy this file to a location DCS can read, e.g. alongside a test mission.
3. In the DCS Mission Editor, create a new mission on the Syria terrain.
4. Add a trigger: type ONCE, condition TIME MORE 5, action DO SCRIPT FILE,
   pointing at this file.
5. Save the mission, start it, let it run, then exit. 121 points is
   a larger workload than M4's proven n=100 (Finding E) -- if it visibly
   hangs or DCS becomes unresponsive, stop and report rather than waiting
   indefinitely; that would be new evidence about a probe-scale ceiling
   Finding E says isn't documented anywhere.
6. Output is written to Saved Games/DCS/Logs/terrain_probe_output.jsonl
   (one JSON object per line, one line per grid point) -- this OVERWRITES
   any earlier rung's output from this same script name, so copy it out
   (step 7) before running the next rung.
7. Copy that file into win-mac-sync/wsl-output/ via
   world-model/tools/wsl/collect_terrain_probe_log.sh (run on the
   Windows/WSL side), sync back to the Mac, then move it into
   world-model/data/raw/dcs/<date>/ and note it in the corresponding
   research/*.md file.

This script performs no writes to the DCS installation itself -- it only
writes to the user's Saved Games/DCS/Logs directory, standard mission-script
log output, not an installation change. The io/lfs sandbox edit itself IS an
installation change, but is explicitly user-authorized, scoped to
investigation probes, and not made by this script.
--]]

-- 121-point subset of the 41x41 grid (rung 1/3 -- 100-200pt smoke test), row/col
-- computed offline in Python from build.pipeline.probe_grid_for_region --
-- see the header comment above for the grid's coordinate system.
local points = {
  { name = "r0c0", x = 34934.8920, z = -4314.9240 },
  { name = "r0c4", x = 34934.8920, z = -2314.9240 },
  { name = "r0c8", x = 34934.8920, z = -314.9240 },
  { name = "r0c12", x = 34934.8920, z = 1685.0760 },
  { name = "r0c16", x = 34934.8920, z = 3685.0760 },
  { name = "r0c20", x = 34934.8920, z = 5685.0760 },
  { name = "r0c24", x = 34934.8920, z = 7685.0760 },
  { name = "r0c28", x = 34934.8920, z = 9685.0760 },
  { name = "r0c32", x = 34934.8920, z = 11685.0760 },
  { name = "r0c36", x = 34934.8920, z = 13685.0760 },
  { name = "r0c40", x = 34934.8920, z = 15685.0760 },
  { name = "r4c0", x = 36934.8920, z = -4314.9240 },
  { name = "r4c4", x = 36934.8920, z = -2314.9240 },
  { name = "r4c8", x = 36934.8920, z = -314.9240 },
  { name = "r4c12", x = 36934.8920, z = 1685.0760 },
  { name = "r4c16", x = 36934.8920, z = 3685.0760 },
  { name = "r4c20", x = 36934.8920, z = 5685.0760 },
  { name = "r4c24", x = 36934.8920, z = 7685.0760 },
  { name = "r4c28", x = 36934.8920, z = 9685.0760 },
  { name = "r4c32", x = 36934.8920, z = 11685.0760 },
  { name = "r4c36", x = 36934.8920, z = 13685.0760 },
  { name = "r4c40", x = 36934.8920, z = 15685.0760 },
  { name = "r8c0", x = 38934.8920, z = -4314.9240 },
  { name = "r8c4", x = 38934.8920, z = -2314.9240 },
  { name = "r8c8", x = 38934.8920, z = -314.9240 },
  { name = "r8c12", x = 38934.8920, z = 1685.0760 },
  { name = "r8c16", x = 38934.8920, z = 3685.0760 },
  { name = "r8c20", x = 38934.8920, z = 5685.0760 },
  { name = "r8c24", x = 38934.8920, z = 7685.0760 },
  { name = "r8c28", x = 38934.8920, z = 9685.0760 },
  { name = "r8c32", x = 38934.8920, z = 11685.0760 },
  { name = "r8c36", x = 38934.8920, z = 13685.0760 },
  { name = "r8c40", x = 38934.8920, z = 15685.0760 },
  { name = "r12c0", x = 40934.8920, z = -4314.9240 },
  { name = "r12c4", x = 40934.8920, z = -2314.9240 },
  { name = "r12c8", x = 40934.8920, z = -314.9240 },
  { name = "r12c12", x = 40934.8920, z = 1685.0760 },
  { name = "r12c16", x = 40934.8920, z = 3685.0760 },
  { name = "r12c20", x = 40934.8920, z = 5685.0760 },
  { name = "r12c24", x = 40934.8920, z = 7685.0760 },
  { name = "r12c28", x = 40934.8920, z = 9685.0760 },
  { name = "r12c32", x = 40934.8920, z = 11685.0760 },
  { name = "r12c36", x = 40934.8920, z = 13685.0760 },
  { name = "r12c40", x = 40934.8920, z = 15685.0760 },
  { name = "r16c0", x = 42934.8920, z = -4314.9240 },
  { name = "r16c4", x = 42934.8920, z = -2314.9240 },
  { name = "r16c8", x = 42934.8920, z = -314.9240 },
  { name = "r16c12", x = 42934.8920, z = 1685.0760 },
  { name = "r16c16", x = 42934.8920, z = 3685.0760 },
  { name = "r16c20", x = 42934.8920, z = 5685.0760 },
  { name = "r16c24", x = 42934.8920, z = 7685.0760 },
  { name = "r16c28", x = 42934.8920, z = 9685.0760 },
  { name = "r16c32", x = 42934.8920, z = 11685.0760 },
  { name = "r16c36", x = 42934.8920, z = 13685.0760 },
  { name = "r16c40", x = 42934.8920, z = 15685.0760 },
  { name = "r20c0", x = 44934.8920, z = -4314.9240 },
  { name = "r20c4", x = 44934.8920, z = -2314.9240 },
  { name = "r20c8", x = 44934.8920, z = -314.9240 },
  { name = "r20c12", x = 44934.8920, z = 1685.0760 },
  { name = "r20c16", x = 44934.8920, z = 3685.0760 },
  { name = "r20c20", x = 44934.8920, z = 5685.0760 },
  { name = "r20c24", x = 44934.8920, z = 7685.0760 },
  { name = "r20c28", x = 44934.8920, z = 9685.0760 },
  { name = "r20c32", x = 44934.8920, z = 11685.0760 },
  { name = "r20c36", x = 44934.8920, z = 13685.0760 },
  { name = "r20c40", x = 44934.8920, z = 15685.0760 },
  { name = "r24c0", x = 46934.8920, z = -4314.9240 },
  { name = "r24c4", x = 46934.8920, z = -2314.9240 },
  { name = "r24c8", x = 46934.8920, z = -314.9240 },
  { name = "r24c12", x = 46934.8920, z = 1685.0760 },
  { name = "r24c16", x = 46934.8920, z = 3685.0760 },
  { name = "r24c20", x = 46934.8920, z = 5685.0760 },
  { name = "r24c24", x = 46934.8920, z = 7685.0760 },
  { name = "r24c28", x = 46934.8920, z = 9685.0760 },
  { name = "r24c32", x = 46934.8920, z = 11685.0760 },
  { name = "r24c36", x = 46934.8920, z = 13685.0760 },
  { name = "r24c40", x = 46934.8920, z = 15685.0760 },
  { name = "r28c0", x = 48934.8920, z = -4314.9240 },
  { name = "r28c4", x = 48934.8920, z = -2314.9240 },
  { name = "r28c8", x = 48934.8920, z = -314.9240 },
  { name = "r28c12", x = 48934.8920, z = 1685.0760 },
  { name = "r28c16", x = 48934.8920, z = 3685.0760 },
  { name = "r28c20", x = 48934.8920, z = 5685.0760 },
  { name = "r28c24", x = 48934.8920, z = 7685.0760 },
  { name = "r28c28", x = 48934.8920, z = 9685.0760 },
  { name = "r28c32", x = 48934.8920, z = 11685.0760 },
  { name = "r28c36", x = 48934.8920, z = 13685.0760 },
  { name = "r28c40", x = 48934.8920, z = 15685.0760 },
  { name = "r32c0", x = 50934.8920, z = -4314.9240 },
  { name = "r32c4", x = 50934.8920, z = -2314.9240 },
  { name = "r32c8", x = 50934.8920, z = -314.9240 },
  { name = "r32c12", x = 50934.8920, z = 1685.0760 },
  { name = "r32c16", x = 50934.8920, z = 3685.0760 },
  { name = "r32c20", x = 50934.8920, z = 5685.0760 },
  { name = "r32c24", x = 50934.8920, z = 7685.0760 },
  { name = "r32c28", x = 50934.8920, z = 9685.0760 },
  { name = "r32c32", x = 50934.8920, z = 11685.0760 },
  { name = "r32c36", x = 50934.8920, z = 13685.0760 },
  { name = "r32c40", x = 50934.8920, z = 15685.0760 },
  { name = "r36c0", x = 52934.8920, z = -4314.9240 },
  { name = "r36c4", x = 52934.8920, z = -2314.9240 },
  { name = "r36c8", x = 52934.8920, z = -314.9240 },
  { name = "r36c12", x = 52934.8920, z = 1685.0760 },
  { name = "r36c16", x = 52934.8920, z = 3685.0760 },
  { name = "r36c20", x = 52934.8920, z = 5685.0760 },
  { name = "r36c24", x = 52934.8920, z = 7685.0760 },
  { name = "r36c28", x = 52934.8920, z = 9685.0760 },
  { name = "r36c32", x = 52934.8920, z = 11685.0760 },
  { name = "r36c36", x = 52934.8920, z = 13685.0760 },
  { name = "r36c40", x = 52934.8920, z = 15685.0760 },
  { name = "r40c0", x = 54934.8920, z = -4314.9240 },
  { name = "r40c4", x = 54934.8920, z = -2314.9240 },
  { name = "r40c8", x = 54934.8920, z = -314.9240 },
  { name = "r40c12", x = 54934.8920, z = 1685.0760 },
  { name = "r40c16", x = 54934.8920, z = 3685.0760 },
  { name = "r40c20", x = 54934.8920, z = 5685.0760 },
  { name = "r40c24", x = 54934.8920, z = 7685.0760 },
  { name = "r40c28", x = 54934.8920, z = 9685.0760 },
  { name = "r40c32", x = 54934.8920, z = 11685.0760 },
  { name = "r40c36", x = 54934.8920, z = 13685.0760 },
  { name = "r40c40", x = 54934.8920, z = 15685.0760 },
}

local logDir = lfs.writedir() .. "Logs/"
local f = io.open(logDir .. "terrain_probe_output.jsonl", "w")

if f then
  for _, p in ipairs(points) do
    local okHeight, height = pcall(land.getHeight, { x = p.x, y = p.z })
    local heightStr = "null"
    if okHeight and height ~= nil then
      heightStr = string.format("%.4f", height)
    end

    local okSurface, surface = pcall(land.getSurfaceType, { x = p.x, y = p.z })
    local surfaceStr = "null"
    if okSurface and surface ~= nil then
      surfaceStr = string.format("%d", surface)
    end

    local line = string.format(
      '{"name": "%s", "x": %.4f, "z": %.4f, "height_m": %s, "surface_type": %s}',
      p.name, p.x, p.z, heightStr, surfaceStr
    )
    f:write(line .. "\n")
  end
  f:close()
  trigger.action.outText(
    "terrain_probe: wrote " .. logDir .. "terrain_probe_output.jsonl", 20
  )
else
  trigger.action.outText(
    "terrain_probe: FAILED to open output file in " .. logDir
    .. " -- check that io/lfs are uncommented in MissionScripting.lua", 20
  )
end
