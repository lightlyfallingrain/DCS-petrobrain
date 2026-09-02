# M0 — DCS install recon (2026-09-02)

- **Version**: DCS 2.9.29.27278, host "Omen" (Windows, WSL bridge)
- **Theatre**: Mods/terrains/Syria present — Syria terrain confirmed installed
  (`syria_terrain_present: true`)
- **Install path**: `/mnt/f/Games/DCS World`
- **Saved Games path**: `/home/sg/winHome/Saved Games/DCS`
- **File/API**: `autoupdate.cfg` `"version"` field; presence check of
  `Mods/terrains/Syria` directory
- **Documented vs inferred**: inferred/observed directly from the installed
  copy, not from ED documentation — version string format matches known
  DCS autoupdate.cfg convention
- **Reproducible test**: `world-model/tools/wsl/probe_dcs_install.sh`
  (requires `DCS_INSTALL_PATH`, `DCS_SAVED_GAMES_PATH` env vars; run via WSL
  bash per `WORKFLOW.md`)
- **Source**: direct probe output, `dcs_install_probe_20260902T194132Z.json`
  (raw output retained at `data/raw/dcs/2026-09-02/`, gitignored)
- **Supplementary raw listings**: full file listing of DCS install dir
  (`DCS-files.txt`) and Saved Games dir (`DCS-saved-games-file-list.txt`)
  collected same session — not yet analyzed, kept as raw input for later
  milestones (e.g. locating RasterCharts tile layout for M2).

**M0 status: satisfied.** DCS version and Syria terrain presence recorded
with reproducible probe. Unblocks M1 (coordinate transform).
