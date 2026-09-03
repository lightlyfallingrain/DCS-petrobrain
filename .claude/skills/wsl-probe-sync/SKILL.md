---
name: wsl-probe-sync
description: Copy a WSL/Windows-side DCS probe or extraction script from world-model/tools/wsl/ out to win-mac-sync/run-wsl/ for the Windows machine to run, and/or pull resulting raw output back from win-mac-sync/wsl-output/ into the repo. Use when the user wants to run a probe against the DCS installation on the Windows box, or wants results synced back after a run.
---

# WSL Probe Sync

Cross-machine workflow helper for Petrobrain's World Model Builder. Full rules: `world-model/WORKFLOW.md`.
`win-mac-sync/` is a Dropbox-synced scratch channel, gitignored, not part of the repo.

## Copy-out (script → Windows)

1. Confirm the canonical script exists under `world-model/tools/wsl/<script>`.
   If not, stop — canonical scripts must be version-controlled first; do not create it directly in `win-mac-sync/`.
2. Copy it into `win-mac-sync/run-wsl/`:
   ```
   cp world-model/tools/wsl/<script> win-mac-sync/run-wsl/<script>
   ```
3. Tell the user it's synced (via Dropbox) and ready to run in WSL bash on the Windows machine, and that it needs `DCS_INSTALL_PATH` and `DCS_SAVED_GAMES_PATH` set there.
4. Never edit or run the copy inside `win-mac-sync/run-wsl/` directly — always edit the canonical copy under `world-model/tools/wsl/` and re-copy.

## Copy-back (raw output → repo)

1. List what landed in `win-mac-sync/wsl-output/`:
   ```
   ls -la win-mac-sync/wsl-output/
   ```
2. Ask (or infer from content) whether each item is:
   - a **finding** → goes to `world-model/research/`
   - **raw pipeline input** → goes to `world-model/data/raw/dcs/<theatre>/`
3. Move (not copy) each item to its destination so `win-mac-sync/wsl-output/` ends up cleared — nothing of record should live only there.
4. Stage the moved files in git if they belong in the repo (raw `data/` may be gitignored — check before assuming it should be staged).

## Rules

- Read-only against the DCS installation; never modify it.
- Raw extraction output is never committed — only extraction scripts and research notes are.
- If `win-mac-sync/` doesn't exist or isn't a symlink, stop and tell the user — it's expected to already be set up as a Dropbox-synced folder, not something to create.
