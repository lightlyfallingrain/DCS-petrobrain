# DCS mission-scripting probes

Unlike `world-model/tools/wsl/` (WSL-bash scripts that read files on the
Windows box without launching DCS), scripts here are **DCS Lua mission
scripts** — they only produce output while DCS is actually running a
mission that loads them. They still count as read-only recon (no DCS
installation files are modified; output goes to the user's Saved Games
directory only, which is normal mission-log behavior).

## Workflow

1. Copy the `.lua` file here into a place DCS can read it (or paste its
   contents directly into a Mission Editor "DO SCRIPT" trigger action).
2. Build a throwaway mission on the target terrain, wire up a trigger that
   runs the script a few seconds after mission start.
3. Run the mission briefly in DCS, then exit.
4. Collect the output file from `Saved Games/DCS/Logs/`, copy it into
   `win-mac-sync/wsl-output/`, sync back to the Mac, then move anything
   worth keeping into `world-model/data/raw/dcs/<date>/` and reference it
   from the relevant `world-model/research/*.md` finding.

See each script's header comment for exact trigger wiring and known caveats
(e.g. `coord_probe.lua`'s note on the mission-scripting `io`/`lfs` sandbox).

## Scripts

- `coord_probe.lua` — dumps `coord.LOtoLL` output for the theatre origin and
  every `world.getAirbases()` entry, to cross-check against
  community-derived (pydcs) projection parameters. See
  `world-model/research/2026-09-02-m1-coordinate-transform.md`.
- `elevation_probe.lua` — dumps `land.getHeight` output for a hardcoded grid
  of DCS (x, z) points over the Gemerek bbox, to compare against an external
  DEM (SRTM). **Prerequisite (probe-only, one-time manual step, never for
  pipeline code): uncomment the `io`/`lfs` lines in the installed
  `Scripts/MissionScripting.lua`** — user-authorized for investigation
  probes specifically (see `world-model/research/2026-09-03-m4-elevation-recon.md`
  and `plans/m4-dcs-elevation/plan.md`). Unlike `coord_probe.lua`, this probe
  writes its own dedicated output file (`elevation_probe_output.jsonl`) via
  `io.open` directly, rather than relying on `net.log`/`dcs.log` — no grep
  step needed, collect the file directly via
  `world-model/tools/wsl/collect_elevation_log.sh`. Revert the
  `MissionScripting.lua` edit once M4's probe runs are done, unless
  continuing to use it for a later probe. Currently holds the **Stage 2**
  full 10x10 (100-point) grid; Stage 1's 8-point smoke test already ran
  successfully and its real output is hardcoded into
  `tests/test_dcs_grid.py`'s fixture — re-running this script overwrites
  Stage 1's output file, which is expected and safe.
- `terrain_probe_{smoke,500,full}.lua` — M5 Stage 3: dump both
  `land.getHeight` **and** `land.getSurfaceType` output for the Latakia
  41x41 (500m spacing, 1,681-point) grid defined by
  `world-model/src/build/pipeline.py`'s `probe_grid_for_region`. Three
  files, not one, because the M5 checklist requires an **incremental
  ladder** — run `terrain_probe_smoke.lua` (121 points) first, then
  `terrain_probe_500.lua` (441 points), then `terrain_probe_full.lua` (the
  full 1,681) — never jump straight to full scale, and stop/reassess if a
  rung shows non-linear cost. Every point name is `r{row}c{col}` into the
  same grid coordinate system across all three files, so
  `world-model/src/build/ingest_probe.py` can ingest any rung's output
  (even a smoke-test-only run) as a real, if sparse, grid. Same
  `io`/`lfs`-sandbox prerequisite as `elevation_probe.lua`. `land.
  getSurfaceType` has **never been called against this install before** —
  documented-only (Hoggit: `LAND=1, SHALLOW_WATER=2, WATER=3, ROAD=4,
  RUNWAY=5`), same status `getHeight` held before M4 Stage 1 (see
  `plans/m5-first-persistent-model/plan.md` Finding C). Output is
  `terrain_probe_output.jsonl`; collect via
  `world-model/tools/wsl/collect_terrain_probe_log.sh` (one run per rung —
  each script overwrites the same output filename, so collect before
  running the next rung). **Uses `timer.scheduleFunction` chunking with
  append-mode `io.write`** per the M5 checklist / plan.md Finding E
  ("never one giant loop holding results in memory") — processes
  `CHUNK_SIZE` (20) points per scheduled tick, appending each chunk to the
  output file, then self-reschedules until done. Note this is **not** the
  same pattern as `elevation_probe.lua` above, despite both being M4/M5
  DCS terrain probes: `elevation_probe.lua` opens its output file once in
  `"w"` mode and runs one blocking loop over all its points, which is the
  "one giant loop" pattern Finding E warns against — that was flagged in
  M5 Stage 3's review (2026-09-04) as a mismatch between the checklist's
  instruction and what got built, and fixed in the `terrain_probe_*.lua`
  scripts directly rather than by retrofitting `elevation_probe.lua`
  (out of scope, a completed M4 milestone that already ran successfully
  at its smaller 100-point scale).
