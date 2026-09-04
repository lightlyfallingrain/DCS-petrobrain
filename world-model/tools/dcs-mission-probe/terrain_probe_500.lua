--[[
M5 Stage 3 rung 2/3 -- ~500pt intermediate: dump land.getHeight(...) and
land.getSurfaceType(...) output for 441 points of the Latakia
41x41 (500m-spacing, 1,681-point) probe grid, from inside a running DCS
mission.

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
ROAD=4, RUNWAY=5. Both calls are pcall-wrapped -- a failed call for a
point writes JSON null for that field rather than aborting the whole run;
ingest_probe.py raises loudly on any null it finds, so a partial failure
is never silently accepted into the store.

**Chunked via timer.scheduleFunction, not one blocking loop.** Per the
M5 checklist and plan.md Finding E ("timer.scheduleFunction chunking,
append-mode io.write ... never one giant loop holding results in
memory"): this script processes CHUNK_SIZE points per scheduled tick,
appending each chunk's lines to the output file (io.open(..., "a")),
then self-reschedules until every point is done. NOTE: M4's own
elevation_probe.lua does NOT do this -- it opens the file once in "w"
mode and runs a single blocking for-loop over all points. That was a
Stage-3-review finding (M5 checklist review, 2026-09-04): referring to
"M4's proven pattern" for this script was inaccurate, since M4's script
never implemented the chunking Finding E describes either. This script
implements the checklist's chunking requirement directly, not by
mirroring M4.

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
5. Save the mission, start it, let it run -- 441 points at
   CHUNK_SIZE points/tick will take several ticks to finish; a
   "terrain_probe: wrote ..." message confirms completion. If DCS visibly
   hangs or becomes unresponsive, stop and report rather than waiting
   indefinitely; that would be new evidence about a probe-scale ceiling
   Finding E says isn't documented anywhere.
6. Output is written to Saved Games/DCS/Logs/terrain_probe_output.jsonl
   (one JSON object per line, one line per grid point) -- this OVERWRITES
   any earlier rung's output from this same script name (truncated fresh
   at the start of this run, then appended to per chunk), so copy it out
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

-- 441-point subset of the 41x41 grid (~500pt intermediate), row/col
-- computed offline in Python from build.pipeline.probe_grid_for_region --
-- see the header comment above for the grid's coordinate system.
local points = {
  { name = "r0c0", x = 34934.8920, z = -4314.9240 },
  { name = "r0c2", x = 34934.8920, z = -3314.9240 },
  { name = "r0c4", x = 34934.8920, z = -2314.9240 },
  { name = "r0c6", x = 34934.8920, z = -1314.9240 },
  { name = "r0c8", x = 34934.8920, z = -314.9240 },
  { name = "r0c10", x = 34934.8920, z = 685.0760 },
  { name = "r0c12", x = 34934.8920, z = 1685.0760 },
  { name = "r0c14", x = 34934.8920, z = 2685.0760 },
  { name = "r0c16", x = 34934.8920, z = 3685.0760 },
  { name = "r0c18", x = 34934.8920, z = 4685.0760 },
  { name = "r0c20", x = 34934.8920, z = 5685.0760 },
  { name = "r0c22", x = 34934.8920, z = 6685.0760 },
  { name = "r0c24", x = 34934.8920, z = 7685.0760 },
  { name = "r0c26", x = 34934.8920, z = 8685.0760 },
  { name = "r0c28", x = 34934.8920, z = 9685.0760 },
  { name = "r0c30", x = 34934.8920, z = 10685.0760 },
  { name = "r0c32", x = 34934.8920, z = 11685.0760 },
  { name = "r0c34", x = 34934.8920, z = 12685.0760 },
  { name = "r0c36", x = 34934.8920, z = 13685.0760 },
  { name = "r0c38", x = 34934.8920, z = 14685.0760 },
  { name = "r0c40", x = 34934.8920, z = 15685.0760 },
  { name = "r2c0", x = 35934.8920, z = -4314.9240 },
  { name = "r2c2", x = 35934.8920, z = -3314.9240 },
  { name = "r2c4", x = 35934.8920, z = -2314.9240 },
  { name = "r2c6", x = 35934.8920, z = -1314.9240 },
  { name = "r2c8", x = 35934.8920, z = -314.9240 },
  { name = "r2c10", x = 35934.8920, z = 685.0760 },
  { name = "r2c12", x = 35934.8920, z = 1685.0760 },
  { name = "r2c14", x = 35934.8920, z = 2685.0760 },
  { name = "r2c16", x = 35934.8920, z = 3685.0760 },
  { name = "r2c18", x = 35934.8920, z = 4685.0760 },
  { name = "r2c20", x = 35934.8920, z = 5685.0760 },
  { name = "r2c22", x = 35934.8920, z = 6685.0760 },
  { name = "r2c24", x = 35934.8920, z = 7685.0760 },
  { name = "r2c26", x = 35934.8920, z = 8685.0760 },
  { name = "r2c28", x = 35934.8920, z = 9685.0760 },
  { name = "r2c30", x = 35934.8920, z = 10685.0760 },
  { name = "r2c32", x = 35934.8920, z = 11685.0760 },
  { name = "r2c34", x = 35934.8920, z = 12685.0760 },
  { name = "r2c36", x = 35934.8920, z = 13685.0760 },
  { name = "r2c38", x = 35934.8920, z = 14685.0760 },
  { name = "r2c40", x = 35934.8920, z = 15685.0760 },
  { name = "r4c0", x = 36934.8920, z = -4314.9240 },
  { name = "r4c2", x = 36934.8920, z = -3314.9240 },
  { name = "r4c4", x = 36934.8920, z = -2314.9240 },
  { name = "r4c6", x = 36934.8920, z = -1314.9240 },
  { name = "r4c8", x = 36934.8920, z = -314.9240 },
  { name = "r4c10", x = 36934.8920, z = 685.0760 },
  { name = "r4c12", x = 36934.8920, z = 1685.0760 },
  { name = "r4c14", x = 36934.8920, z = 2685.0760 },
  { name = "r4c16", x = 36934.8920, z = 3685.0760 },
  { name = "r4c18", x = 36934.8920, z = 4685.0760 },
  { name = "r4c20", x = 36934.8920, z = 5685.0760 },
  { name = "r4c22", x = 36934.8920, z = 6685.0760 },
  { name = "r4c24", x = 36934.8920, z = 7685.0760 },
  { name = "r4c26", x = 36934.8920, z = 8685.0760 },
  { name = "r4c28", x = 36934.8920, z = 9685.0760 },
  { name = "r4c30", x = 36934.8920, z = 10685.0760 },
  { name = "r4c32", x = 36934.8920, z = 11685.0760 },
  { name = "r4c34", x = 36934.8920, z = 12685.0760 },
  { name = "r4c36", x = 36934.8920, z = 13685.0760 },
  { name = "r4c38", x = 36934.8920, z = 14685.0760 },
  { name = "r4c40", x = 36934.8920, z = 15685.0760 },
  { name = "r6c0", x = 37934.8920, z = -4314.9240 },
  { name = "r6c2", x = 37934.8920, z = -3314.9240 },
  { name = "r6c4", x = 37934.8920, z = -2314.9240 },
  { name = "r6c6", x = 37934.8920, z = -1314.9240 },
  { name = "r6c8", x = 37934.8920, z = -314.9240 },
  { name = "r6c10", x = 37934.8920, z = 685.0760 },
  { name = "r6c12", x = 37934.8920, z = 1685.0760 },
  { name = "r6c14", x = 37934.8920, z = 2685.0760 },
  { name = "r6c16", x = 37934.8920, z = 3685.0760 },
  { name = "r6c18", x = 37934.8920, z = 4685.0760 },
  { name = "r6c20", x = 37934.8920, z = 5685.0760 },
  { name = "r6c22", x = 37934.8920, z = 6685.0760 },
  { name = "r6c24", x = 37934.8920, z = 7685.0760 },
  { name = "r6c26", x = 37934.8920, z = 8685.0760 },
  { name = "r6c28", x = 37934.8920, z = 9685.0760 },
  { name = "r6c30", x = 37934.8920, z = 10685.0760 },
  { name = "r6c32", x = 37934.8920, z = 11685.0760 },
  { name = "r6c34", x = 37934.8920, z = 12685.0760 },
  { name = "r6c36", x = 37934.8920, z = 13685.0760 },
  { name = "r6c38", x = 37934.8920, z = 14685.0760 },
  { name = "r6c40", x = 37934.8920, z = 15685.0760 },
  { name = "r8c0", x = 38934.8920, z = -4314.9240 },
  { name = "r8c2", x = 38934.8920, z = -3314.9240 },
  { name = "r8c4", x = 38934.8920, z = -2314.9240 },
  { name = "r8c6", x = 38934.8920, z = -1314.9240 },
  { name = "r8c8", x = 38934.8920, z = -314.9240 },
  { name = "r8c10", x = 38934.8920, z = 685.0760 },
  { name = "r8c12", x = 38934.8920, z = 1685.0760 },
  { name = "r8c14", x = 38934.8920, z = 2685.0760 },
  { name = "r8c16", x = 38934.8920, z = 3685.0760 },
  { name = "r8c18", x = 38934.8920, z = 4685.0760 },
  { name = "r8c20", x = 38934.8920, z = 5685.0760 },
  { name = "r8c22", x = 38934.8920, z = 6685.0760 },
  { name = "r8c24", x = 38934.8920, z = 7685.0760 },
  { name = "r8c26", x = 38934.8920, z = 8685.0760 },
  { name = "r8c28", x = 38934.8920, z = 9685.0760 },
  { name = "r8c30", x = 38934.8920, z = 10685.0760 },
  { name = "r8c32", x = 38934.8920, z = 11685.0760 },
  { name = "r8c34", x = 38934.8920, z = 12685.0760 },
  { name = "r8c36", x = 38934.8920, z = 13685.0760 },
  { name = "r8c38", x = 38934.8920, z = 14685.0760 },
  { name = "r8c40", x = 38934.8920, z = 15685.0760 },
  { name = "r10c0", x = 39934.8920, z = -4314.9240 },
  { name = "r10c2", x = 39934.8920, z = -3314.9240 },
  { name = "r10c4", x = 39934.8920, z = -2314.9240 },
  { name = "r10c6", x = 39934.8920, z = -1314.9240 },
  { name = "r10c8", x = 39934.8920, z = -314.9240 },
  { name = "r10c10", x = 39934.8920, z = 685.0760 },
  { name = "r10c12", x = 39934.8920, z = 1685.0760 },
  { name = "r10c14", x = 39934.8920, z = 2685.0760 },
  { name = "r10c16", x = 39934.8920, z = 3685.0760 },
  { name = "r10c18", x = 39934.8920, z = 4685.0760 },
  { name = "r10c20", x = 39934.8920, z = 5685.0760 },
  { name = "r10c22", x = 39934.8920, z = 6685.0760 },
  { name = "r10c24", x = 39934.8920, z = 7685.0760 },
  { name = "r10c26", x = 39934.8920, z = 8685.0760 },
  { name = "r10c28", x = 39934.8920, z = 9685.0760 },
  { name = "r10c30", x = 39934.8920, z = 10685.0760 },
  { name = "r10c32", x = 39934.8920, z = 11685.0760 },
  { name = "r10c34", x = 39934.8920, z = 12685.0760 },
  { name = "r10c36", x = 39934.8920, z = 13685.0760 },
  { name = "r10c38", x = 39934.8920, z = 14685.0760 },
  { name = "r10c40", x = 39934.8920, z = 15685.0760 },
  { name = "r12c0", x = 40934.8920, z = -4314.9240 },
  { name = "r12c2", x = 40934.8920, z = -3314.9240 },
  { name = "r12c4", x = 40934.8920, z = -2314.9240 },
  { name = "r12c6", x = 40934.8920, z = -1314.9240 },
  { name = "r12c8", x = 40934.8920, z = -314.9240 },
  { name = "r12c10", x = 40934.8920, z = 685.0760 },
  { name = "r12c12", x = 40934.8920, z = 1685.0760 },
  { name = "r12c14", x = 40934.8920, z = 2685.0760 },
  { name = "r12c16", x = 40934.8920, z = 3685.0760 },
  { name = "r12c18", x = 40934.8920, z = 4685.0760 },
  { name = "r12c20", x = 40934.8920, z = 5685.0760 },
  { name = "r12c22", x = 40934.8920, z = 6685.0760 },
  { name = "r12c24", x = 40934.8920, z = 7685.0760 },
  { name = "r12c26", x = 40934.8920, z = 8685.0760 },
  { name = "r12c28", x = 40934.8920, z = 9685.0760 },
  { name = "r12c30", x = 40934.8920, z = 10685.0760 },
  { name = "r12c32", x = 40934.8920, z = 11685.0760 },
  { name = "r12c34", x = 40934.8920, z = 12685.0760 },
  { name = "r12c36", x = 40934.8920, z = 13685.0760 },
  { name = "r12c38", x = 40934.8920, z = 14685.0760 },
  { name = "r12c40", x = 40934.8920, z = 15685.0760 },
  { name = "r14c0", x = 41934.8920, z = -4314.9240 },
  { name = "r14c2", x = 41934.8920, z = -3314.9240 },
  { name = "r14c4", x = 41934.8920, z = -2314.9240 },
  { name = "r14c6", x = 41934.8920, z = -1314.9240 },
  { name = "r14c8", x = 41934.8920, z = -314.9240 },
  { name = "r14c10", x = 41934.8920, z = 685.0760 },
  { name = "r14c12", x = 41934.8920, z = 1685.0760 },
  { name = "r14c14", x = 41934.8920, z = 2685.0760 },
  { name = "r14c16", x = 41934.8920, z = 3685.0760 },
  { name = "r14c18", x = 41934.8920, z = 4685.0760 },
  { name = "r14c20", x = 41934.8920, z = 5685.0760 },
  { name = "r14c22", x = 41934.8920, z = 6685.0760 },
  { name = "r14c24", x = 41934.8920, z = 7685.0760 },
  { name = "r14c26", x = 41934.8920, z = 8685.0760 },
  { name = "r14c28", x = 41934.8920, z = 9685.0760 },
  { name = "r14c30", x = 41934.8920, z = 10685.0760 },
  { name = "r14c32", x = 41934.8920, z = 11685.0760 },
  { name = "r14c34", x = 41934.8920, z = 12685.0760 },
  { name = "r14c36", x = 41934.8920, z = 13685.0760 },
  { name = "r14c38", x = 41934.8920, z = 14685.0760 },
  { name = "r14c40", x = 41934.8920, z = 15685.0760 },
  { name = "r16c0", x = 42934.8920, z = -4314.9240 },
  { name = "r16c2", x = 42934.8920, z = -3314.9240 },
  { name = "r16c4", x = 42934.8920, z = -2314.9240 },
  { name = "r16c6", x = 42934.8920, z = -1314.9240 },
  { name = "r16c8", x = 42934.8920, z = -314.9240 },
  { name = "r16c10", x = 42934.8920, z = 685.0760 },
  { name = "r16c12", x = 42934.8920, z = 1685.0760 },
  { name = "r16c14", x = 42934.8920, z = 2685.0760 },
  { name = "r16c16", x = 42934.8920, z = 3685.0760 },
  { name = "r16c18", x = 42934.8920, z = 4685.0760 },
  { name = "r16c20", x = 42934.8920, z = 5685.0760 },
  { name = "r16c22", x = 42934.8920, z = 6685.0760 },
  { name = "r16c24", x = 42934.8920, z = 7685.0760 },
  { name = "r16c26", x = 42934.8920, z = 8685.0760 },
  { name = "r16c28", x = 42934.8920, z = 9685.0760 },
  { name = "r16c30", x = 42934.8920, z = 10685.0760 },
  { name = "r16c32", x = 42934.8920, z = 11685.0760 },
  { name = "r16c34", x = 42934.8920, z = 12685.0760 },
  { name = "r16c36", x = 42934.8920, z = 13685.0760 },
  { name = "r16c38", x = 42934.8920, z = 14685.0760 },
  { name = "r16c40", x = 42934.8920, z = 15685.0760 },
  { name = "r18c0", x = 43934.8920, z = -4314.9240 },
  { name = "r18c2", x = 43934.8920, z = -3314.9240 },
  { name = "r18c4", x = 43934.8920, z = -2314.9240 },
  { name = "r18c6", x = 43934.8920, z = -1314.9240 },
  { name = "r18c8", x = 43934.8920, z = -314.9240 },
  { name = "r18c10", x = 43934.8920, z = 685.0760 },
  { name = "r18c12", x = 43934.8920, z = 1685.0760 },
  { name = "r18c14", x = 43934.8920, z = 2685.0760 },
  { name = "r18c16", x = 43934.8920, z = 3685.0760 },
  { name = "r18c18", x = 43934.8920, z = 4685.0760 },
  { name = "r18c20", x = 43934.8920, z = 5685.0760 },
  { name = "r18c22", x = 43934.8920, z = 6685.0760 },
  { name = "r18c24", x = 43934.8920, z = 7685.0760 },
  { name = "r18c26", x = 43934.8920, z = 8685.0760 },
  { name = "r18c28", x = 43934.8920, z = 9685.0760 },
  { name = "r18c30", x = 43934.8920, z = 10685.0760 },
  { name = "r18c32", x = 43934.8920, z = 11685.0760 },
  { name = "r18c34", x = 43934.8920, z = 12685.0760 },
  { name = "r18c36", x = 43934.8920, z = 13685.0760 },
  { name = "r18c38", x = 43934.8920, z = 14685.0760 },
  { name = "r18c40", x = 43934.8920, z = 15685.0760 },
  { name = "r20c0", x = 44934.8920, z = -4314.9240 },
  { name = "r20c2", x = 44934.8920, z = -3314.9240 },
  { name = "r20c4", x = 44934.8920, z = -2314.9240 },
  { name = "r20c6", x = 44934.8920, z = -1314.9240 },
  { name = "r20c8", x = 44934.8920, z = -314.9240 },
  { name = "r20c10", x = 44934.8920, z = 685.0760 },
  { name = "r20c12", x = 44934.8920, z = 1685.0760 },
  { name = "r20c14", x = 44934.8920, z = 2685.0760 },
  { name = "r20c16", x = 44934.8920, z = 3685.0760 },
  { name = "r20c18", x = 44934.8920, z = 4685.0760 },
  { name = "r20c20", x = 44934.8920, z = 5685.0760 },
  { name = "r20c22", x = 44934.8920, z = 6685.0760 },
  { name = "r20c24", x = 44934.8920, z = 7685.0760 },
  { name = "r20c26", x = 44934.8920, z = 8685.0760 },
  { name = "r20c28", x = 44934.8920, z = 9685.0760 },
  { name = "r20c30", x = 44934.8920, z = 10685.0760 },
  { name = "r20c32", x = 44934.8920, z = 11685.0760 },
  { name = "r20c34", x = 44934.8920, z = 12685.0760 },
  { name = "r20c36", x = 44934.8920, z = 13685.0760 },
  { name = "r20c38", x = 44934.8920, z = 14685.0760 },
  { name = "r20c40", x = 44934.8920, z = 15685.0760 },
  { name = "r22c0", x = 45934.8920, z = -4314.9240 },
  { name = "r22c2", x = 45934.8920, z = -3314.9240 },
  { name = "r22c4", x = 45934.8920, z = -2314.9240 },
  { name = "r22c6", x = 45934.8920, z = -1314.9240 },
  { name = "r22c8", x = 45934.8920, z = -314.9240 },
  { name = "r22c10", x = 45934.8920, z = 685.0760 },
  { name = "r22c12", x = 45934.8920, z = 1685.0760 },
  { name = "r22c14", x = 45934.8920, z = 2685.0760 },
  { name = "r22c16", x = 45934.8920, z = 3685.0760 },
  { name = "r22c18", x = 45934.8920, z = 4685.0760 },
  { name = "r22c20", x = 45934.8920, z = 5685.0760 },
  { name = "r22c22", x = 45934.8920, z = 6685.0760 },
  { name = "r22c24", x = 45934.8920, z = 7685.0760 },
  { name = "r22c26", x = 45934.8920, z = 8685.0760 },
  { name = "r22c28", x = 45934.8920, z = 9685.0760 },
  { name = "r22c30", x = 45934.8920, z = 10685.0760 },
  { name = "r22c32", x = 45934.8920, z = 11685.0760 },
  { name = "r22c34", x = 45934.8920, z = 12685.0760 },
  { name = "r22c36", x = 45934.8920, z = 13685.0760 },
  { name = "r22c38", x = 45934.8920, z = 14685.0760 },
  { name = "r22c40", x = 45934.8920, z = 15685.0760 },
  { name = "r24c0", x = 46934.8920, z = -4314.9240 },
  { name = "r24c2", x = 46934.8920, z = -3314.9240 },
  { name = "r24c4", x = 46934.8920, z = -2314.9240 },
  { name = "r24c6", x = 46934.8920, z = -1314.9240 },
  { name = "r24c8", x = 46934.8920, z = -314.9240 },
  { name = "r24c10", x = 46934.8920, z = 685.0760 },
  { name = "r24c12", x = 46934.8920, z = 1685.0760 },
  { name = "r24c14", x = 46934.8920, z = 2685.0760 },
  { name = "r24c16", x = 46934.8920, z = 3685.0760 },
  { name = "r24c18", x = 46934.8920, z = 4685.0760 },
  { name = "r24c20", x = 46934.8920, z = 5685.0760 },
  { name = "r24c22", x = 46934.8920, z = 6685.0760 },
  { name = "r24c24", x = 46934.8920, z = 7685.0760 },
  { name = "r24c26", x = 46934.8920, z = 8685.0760 },
  { name = "r24c28", x = 46934.8920, z = 9685.0760 },
  { name = "r24c30", x = 46934.8920, z = 10685.0760 },
  { name = "r24c32", x = 46934.8920, z = 11685.0760 },
  { name = "r24c34", x = 46934.8920, z = 12685.0760 },
  { name = "r24c36", x = 46934.8920, z = 13685.0760 },
  { name = "r24c38", x = 46934.8920, z = 14685.0760 },
  { name = "r24c40", x = 46934.8920, z = 15685.0760 },
  { name = "r26c0", x = 47934.8920, z = -4314.9240 },
  { name = "r26c2", x = 47934.8920, z = -3314.9240 },
  { name = "r26c4", x = 47934.8920, z = -2314.9240 },
  { name = "r26c6", x = 47934.8920, z = -1314.9240 },
  { name = "r26c8", x = 47934.8920, z = -314.9240 },
  { name = "r26c10", x = 47934.8920, z = 685.0760 },
  { name = "r26c12", x = 47934.8920, z = 1685.0760 },
  { name = "r26c14", x = 47934.8920, z = 2685.0760 },
  { name = "r26c16", x = 47934.8920, z = 3685.0760 },
  { name = "r26c18", x = 47934.8920, z = 4685.0760 },
  { name = "r26c20", x = 47934.8920, z = 5685.0760 },
  { name = "r26c22", x = 47934.8920, z = 6685.0760 },
  { name = "r26c24", x = 47934.8920, z = 7685.0760 },
  { name = "r26c26", x = 47934.8920, z = 8685.0760 },
  { name = "r26c28", x = 47934.8920, z = 9685.0760 },
  { name = "r26c30", x = 47934.8920, z = 10685.0760 },
  { name = "r26c32", x = 47934.8920, z = 11685.0760 },
  { name = "r26c34", x = 47934.8920, z = 12685.0760 },
  { name = "r26c36", x = 47934.8920, z = 13685.0760 },
  { name = "r26c38", x = 47934.8920, z = 14685.0760 },
  { name = "r26c40", x = 47934.8920, z = 15685.0760 },
  { name = "r28c0", x = 48934.8920, z = -4314.9240 },
  { name = "r28c2", x = 48934.8920, z = -3314.9240 },
  { name = "r28c4", x = 48934.8920, z = -2314.9240 },
  { name = "r28c6", x = 48934.8920, z = -1314.9240 },
  { name = "r28c8", x = 48934.8920, z = -314.9240 },
  { name = "r28c10", x = 48934.8920, z = 685.0760 },
  { name = "r28c12", x = 48934.8920, z = 1685.0760 },
  { name = "r28c14", x = 48934.8920, z = 2685.0760 },
  { name = "r28c16", x = 48934.8920, z = 3685.0760 },
  { name = "r28c18", x = 48934.8920, z = 4685.0760 },
  { name = "r28c20", x = 48934.8920, z = 5685.0760 },
  { name = "r28c22", x = 48934.8920, z = 6685.0760 },
  { name = "r28c24", x = 48934.8920, z = 7685.0760 },
  { name = "r28c26", x = 48934.8920, z = 8685.0760 },
  { name = "r28c28", x = 48934.8920, z = 9685.0760 },
  { name = "r28c30", x = 48934.8920, z = 10685.0760 },
  { name = "r28c32", x = 48934.8920, z = 11685.0760 },
  { name = "r28c34", x = 48934.8920, z = 12685.0760 },
  { name = "r28c36", x = 48934.8920, z = 13685.0760 },
  { name = "r28c38", x = 48934.8920, z = 14685.0760 },
  { name = "r28c40", x = 48934.8920, z = 15685.0760 },
  { name = "r30c0", x = 49934.8920, z = -4314.9240 },
  { name = "r30c2", x = 49934.8920, z = -3314.9240 },
  { name = "r30c4", x = 49934.8920, z = -2314.9240 },
  { name = "r30c6", x = 49934.8920, z = -1314.9240 },
  { name = "r30c8", x = 49934.8920, z = -314.9240 },
  { name = "r30c10", x = 49934.8920, z = 685.0760 },
  { name = "r30c12", x = 49934.8920, z = 1685.0760 },
  { name = "r30c14", x = 49934.8920, z = 2685.0760 },
  { name = "r30c16", x = 49934.8920, z = 3685.0760 },
  { name = "r30c18", x = 49934.8920, z = 4685.0760 },
  { name = "r30c20", x = 49934.8920, z = 5685.0760 },
  { name = "r30c22", x = 49934.8920, z = 6685.0760 },
  { name = "r30c24", x = 49934.8920, z = 7685.0760 },
  { name = "r30c26", x = 49934.8920, z = 8685.0760 },
  { name = "r30c28", x = 49934.8920, z = 9685.0760 },
  { name = "r30c30", x = 49934.8920, z = 10685.0760 },
  { name = "r30c32", x = 49934.8920, z = 11685.0760 },
  { name = "r30c34", x = 49934.8920, z = 12685.0760 },
  { name = "r30c36", x = 49934.8920, z = 13685.0760 },
  { name = "r30c38", x = 49934.8920, z = 14685.0760 },
  { name = "r30c40", x = 49934.8920, z = 15685.0760 },
  { name = "r32c0", x = 50934.8920, z = -4314.9240 },
  { name = "r32c2", x = 50934.8920, z = -3314.9240 },
  { name = "r32c4", x = 50934.8920, z = -2314.9240 },
  { name = "r32c6", x = 50934.8920, z = -1314.9240 },
  { name = "r32c8", x = 50934.8920, z = -314.9240 },
  { name = "r32c10", x = 50934.8920, z = 685.0760 },
  { name = "r32c12", x = 50934.8920, z = 1685.0760 },
  { name = "r32c14", x = 50934.8920, z = 2685.0760 },
  { name = "r32c16", x = 50934.8920, z = 3685.0760 },
  { name = "r32c18", x = 50934.8920, z = 4685.0760 },
  { name = "r32c20", x = 50934.8920, z = 5685.0760 },
  { name = "r32c22", x = 50934.8920, z = 6685.0760 },
  { name = "r32c24", x = 50934.8920, z = 7685.0760 },
  { name = "r32c26", x = 50934.8920, z = 8685.0760 },
  { name = "r32c28", x = 50934.8920, z = 9685.0760 },
  { name = "r32c30", x = 50934.8920, z = 10685.0760 },
  { name = "r32c32", x = 50934.8920, z = 11685.0760 },
  { name = "r32c34", x = 50934.8920, z = 12685.0760 },
  { name = "r32c36", x = 50934.8920, z = 13685.0760 },
  { name = "r32c38", x = 50934.8920, z = 14685.0760 },
  { name = "r32c40", x = 50934.8920, z = 15685.0760 },
  { name = "r34c0", x = 51934.8920, z = -4314.9240 },
  { name = "r34c2", x = 51934.8920, z = -3314.9240 },
  { name = "r34c4", x = 51934.8920, z = -2314.9240 },
  { name = "r34c6", x = 51934.8920, z = -1314.9240 },
  { name = "r34c8", x = 51934.8920, z = -314.9240 },
  { name = "r34c10", x = 51934.8920, z = 685.0760 },
  { name = "r34c12", x = 51934.8920, z = 1685.0760 },
  { name = "r34c14", x = 51934.8920, z = 2685.0760 },
  { name = "r34c16", x = 51934.8920, z = 3685.0760 },
  { name = "r34c18", x = 51934.8920, z = 4685.0760 },
  { name = "r34c20", x = 51934.8920, z = 5685.0760 },
  { name = "r34c22", x = 51934.8920, z = 6685.0760 },
  { name = "r34c24", x = 51934.8920, z = 7685.0760 },
  { name = "r34c26", x = 51934.8920, z = 8685.0760 },
  { name = "r34c28", x = 51934.8920, z = 9685.0760 },
  { name = "r34c30", x = 51934.8920, z = 10685.0760 },
  { name = "r34c32", x = 51934.8920, z = 11685.0760 },
  { name = "r34c34", x = 51934.8920, z = 12685.0760 },
  { name = "r34c36", x = 51934.8920, z = 13685.0760 },
  { name = "r34c38", x = 51934.8920, z = 14685.0760 },
  { name = "r34c40", x = 51934.8920, z = 15685.0760 },
  { name = "r36c0", x = 52934.8920, z = -4314.9240 },
  { name = "r36c2", x = 52934.8920, z = -3314.9240 },
  { name = "r36c4", x = 52934.8920, z = -2314.9240 },
  { name = "r36c6", x = 52934.8920, z = -1314.9240 },
  { name = "r36c8", x = 52934.8920, z = -314.9240 },
  { name = "r36c10", x = 52934.8920, z = 685.0760 },
  { name = "r36c12", x = 52934.8920, z = 1685.0760 },
  { name = "r36c14", x = 52934.8920, z = 2685.0760 },
  { name = "r36c16", x = 52934.8920, z = 3685.0760 },
  { name = "r36c18", x = 52934.8920, z = 4685.0760 },
  { name = "r36c20", x = 52934.8920, z = 5685.0760 },
  { name = "r36c22", x = 52934.8920, z = 6685.0760 },
  { name = "r36c24", x = 52934.8920, z = 7685.0760 },
  { name = "r36c26", x = 52934.8920, z = 8685.0760 },
  { name = "r36c28", x = 52934.8920, z = 9685.0760 },
  { name = "r36c30", x = 52934.8920, z = 10685.0760 },
  { name = "r36c32", x = 52934.8920, z = 11685.0760 },
  { name = "r36c34", x = 52934.8920, z = 12685.0760 },
  { name = "r36c36", x = 52934.8920, z = 13685.0760 },
  { name = "r36c38", x = 52934.8920, z = 14685.0760 },
  { name = "r36c40", x = 52934.8920, z = 15685.0760 },
  { name = "r38c0", x = 53934.8920, z = -4314.9240 },
  { name = "r38c2", x = 53934.8920, z = -3314.9240 },
  { name = "r38c4", x = 53934.8920, z = -2314.9240 },
  { name = "r38c6", x = 53934.8920, z = -1314.9240 },
  { name = "r38c8", x = 53934.8920, z = -314.9240 },
  { name = "r38c10", x = 53934.8920, z = 685.0760 },
  { name = "r38c12", x = 53934.8920, z = 1685.0760 },
  { name = "r38c14", x = 53934.8920, z = 2685.0760 },
  { name = "r38c16", x = 53934.8920, z = 3685.0760 },
  { name = "r38c18", x = 53934.8920, z = 4685.0760 },
  { name = "r38c20", x = 53934.8920, z = 5685.0760 },
  { name = "r38c22", x = 53934.8920, z = 6685.0760 },
  { name = "r38c24", x = 53934.8920, z = 7685.0760 },
  { name = "r38c26", x = 53934.8920, z = 8685.0760 },
  { name = "r38c28", x = 53934.8920, z = 9685.0760 },
  { name = "r38c30", x = 53934.8920, z = 10685.0760 },
  { name = "r38c32", x = 53934.8920, z = 11685.0760 },
  { name = "r38c34", x = 53934.8920, z = 12685.0760 },
  { name = "r38c36", x = 53934.8920, z = 13685.0760 },
  { name = "r38c38", x = 53934.8920, z = 14685.0760 },
  { name = "r38c40", x = 53934.8920, z = 15685.0760 },
  { name = "r40c0", x = 54934.8920, z = -4314.9240 },
  { name = "r40c2", x = 54934.8920, z = -3314.9240 },
  { name = "r40c4", x = 54934.8920, z = -2314.9240 },
  { name = "r40c6", x = 54934.8920, z = -1314.9240 },
  { name = "r40c8", x = 54934.8920, z = -314.9240 },
  { name = "r40c10", x = 54934.8920, z = 685.0760 },
  { name = "r40c12", x = 54934.8920, z = 1685.0760 },
  { name = "r40c14", x = 54934.8920, z = 2685.0760 },
  { name = "r40c16", x = 54934.8920, z = 3685.0760 },
  { name = "r40c18", x = 54934.8920, z = 4685.0760 },
  { name = "r40c20", x = 54934.8920, z = 5685.0760 },
  { name = "r40c22", x = 54934.8920, z = 6685.0760 },
  { name = "r40c24", x = 54934.8920, z = 7685.0760 },
  { name = "r40c26", x = 54934.8920, z = 8685.0760 },
  { name = "r40c28", x = 54934.8920, z = 9685.0760 },
  { name = "r40c30", x = 54934.8920, z = 10685.0760 },
  { name = "r40c32", x = 54934.8920, z = 11685.0760 },
  { name = "r40c34", x = 54934.8920, z = 12685.0760 },
  { name = "r40c36", x = 54934.8920, z = 13685.0760 },
  { name = "r40c38", x = 54934.8920, z = 14685.0760 },
  { name = "r40c40", x = 54934.8920, z = 15685.0760 },
}

local CHUNK_SIZE = 20
local outputPath = lfs.writedir() .. "Logs/terrain_probe_output.jsonl"
local index = 1

-- Truncate/create the output file fresh before the first chunk (this is
-- the "w"-mode open the checklist expects exactly once, at the start --
-- every chunk after this appends via "a", never re-truncates).
local initFile = io.open(outputPath, "w")
if initFile then
  initFile:close()
else
  trigger.action.outText(
    "terrain_probe: FAILED to create output file at " .. outputPath
    .. " -- check that io/lfs are uncommented in MissionScripting.lua", 20
  )
  return
end

local function processChunk()
  local f = io.open(outputPath, "a")
  if not f then
    trigger.action.outText(
      "terrain_probe: FAILED to open output file for append at " .. outputPath, 20
    )
    return nil
  end

  local chunkEnd = math.min(index + CHUNK_SIZE - 1, #points)
  for i = index, chunkEnd do
    local p = points[i]
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

  index = chunkEnd + 1

  if index <= #points then
    -- Self-reschedule for the next chunk, per Finding E's
    -- timer.scheduleFunction chunking pattern.
    return timer.getTime() + 0.1
  end

  trigger.action.outText(
    "terrain_probe: wrote " .. outputPath .. " (" .. #points .. " points)", 20
  )
  return nil
end

timer.scheduleFunction(processChunk, nil, timer.getTime() + 1)
