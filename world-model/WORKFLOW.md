# Cross-machine workflow

DCS World is installed on a Windows PC. Primary development happens on a Mac. This is a manual-copy workflow by default, with an escape hatch to run Claude Code directly on Windows for extraction-heavy sessions.

## Default: manual copy

1. On Windows, run extraction/probe scripts (plain Python or WSL bash) directly against the DCS installation (e.g. `Mods/terrains/<theatre>/RasterCharts`, Lua probe output, etc.).
2. Scripts write **only raw extracted artifacts** to a local folder — no processing, no pipeline logic on the Windows side.
3. Copy that folder to this repo under `data/raw/dcs/<theatre>/` (gitignored, so any transfer method — AirDrop, USB, syncthing, cloud drive — is fine).
4. All processing, reconciliation, and querying happens on the Mac against `data/raw/`.

Keep extraction scripts themselves under version control (`tools/` or a `windows/` subfolder) even though their output isn't — so the extraction step is reproducible, not a one-off manual hack.

## Escape hatch: Claude Code on Windows

For extraction work heavy enough to want an agent driving it directly against the DCS folder (e.g. large raster/Lua exploration), install Claude Code on the Windows machine and point it at the DCS installation read-only. Sync results back via git (extraction scripts + `research/` notes only — never commit `data/`).

## Rules

- Never modify the DCS installation. All extraction is read-only.
- Raw extraction output is never committed (see `.gitignore`).
- Extraction *scripts* are committed — the pipeline must be reproducible without depending on manual steps that weren't captured in code.
