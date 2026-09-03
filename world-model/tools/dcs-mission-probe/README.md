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
