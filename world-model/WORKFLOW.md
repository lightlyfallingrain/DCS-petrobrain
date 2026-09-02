# Cross-machine workflow

DCS World is installed on a Windows PC. Primary development happens on a Mac. This is a manual-copy workflow by default, with an escape hatch to run Claude Code directly on Windows for extraction-heavy sessions.

## Default: manual copy via `win-mac-sync`

`win-mac-sync` (repo root) is a local symlink to a Dropbox-synced folder shared
between the Mac and the Windows DCS machine — **not part of this repo, not
tracked by git.** It's a scratch transfer channel only, with two
subdirectories: `run-wsl/` and `wsl-output/`.

1. Canonical probe/extraction scripts live under version control at
   `world-model/tools/wsl/` (WSL-bash scripts, run against the DCS
   installation — e.g. `Mods/terrains/<theatre>/RasterCharts`, Lua probe
   output, etc.).
2. To run one: copy it from `world-model/tools/wsl/` into `win-mac-sync/run-wsl/`
   (now synced to the Windows machine via Dropbox), then run it there in WSL
   bash. **Always copy — never edit/run scripts directly inside
   `win-mac-sync/run-wsl/`**, since it's gitignored and not version-controlled;
   the copy step keeps the script in the repo as source of truth.
3. Scripts require two env vars set on the Windows/WSL side:
   - `DCS_INSTALL_PATH` — DCS World install directory.
   - `DCS_SAVED_GAMES_PATH` — DCS Saved Games directory.
4. Scripts write **only raw extracted artifacts** into `win-mac-sync/wsl-output/`
   — no processing, no pipeline logic on the Windows side.
5. Once `win-mac-sync/wsl-output/` syncs back to the Mac, treat it as temp
   storage: copy anything worth keeping into the repo — findings into
   `research/`, raw pipeline input into `data/raw/dcs/<theatre>/` — then it can
   be cleared. Nothing of record should live only in `win-mac-sync/`.
6. All processing, reconciliation, and querying happens on the Mac against
   `data/raw/`.

Keep extraction scripts themselves under version control
(`world-model/tools/wsl/` for WSL/Windows-side scripts, `tools/` for Mac-side
probes) even though their output isn't — so the extraction step is
reproducible, not a one-off manual hack.

## Escape hatch: Claude Code on Windows

For extraction work heavy enough to want an agent driving it directly against the DCS folder (e.g. large raster/Lua exploration), install Claude Code on the Windows machine and point it at the DCS installation read-only. Sync results back via git (extraction scripts + `research/` notes only — never commit `data/`).

## Rules

- Never modify the DCS installation. All extraction is read-only.
- Raw extraction output is never committed (see `.gitignore`).
- Extraction *scripts* are committed — the pipeline must be reproducible without depending on manual steps that weren't captured in code.
