#!/usr/bin/env bash
# M4 recon: copy elevation_probe.lua's own output file out of DCS's Saved
# Games/Logs directory. This is a pure read of a file the probe script wrote
# itself during a live mission run -- no installation change, no dcs.log
# grep step needed (unlike a net.log-based probe).
#
# This is the canonical, version-controlled copy. To run it: copy this file
# into win-mac-sync/run-wsl/ on the machine where win-mac-sync is synced
# (Dropbox), then run it there in WSL bash on the Windows DCS machine.
# win-mac-sync itself is NOT part of this repo -- it's a scratch transfer
# channel; see world-model/WORKFLOW.md.
#
# Requires env var:
#   DCS_SAVED_GAMES_PATH   - DCS Saved Games dir (Windows or WSL-style path)
#
# Copies Logs/elevation_probe_output.jsonl into ../wsl-output/ (i.e.
# win-mac-sync/wsl-output/ once deployed), timestamped. That output is
# scratch too -- once synced back to the Mac, move it into
# world-model/data/raw/dcs/<date>/ and reference it from the corresponding
# world-model/research/*.md note; do not leave it only in win-mac-sync/.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_dir="$(cd "$script_dir/../wsl-output" && pwd)"

require_env() {
  local var_name="$1"
  if [ -z "${!var_name:-}" ]; then
    echo "ERROR: $var_name is not set." >&2
    exit 1
  fi
}

require_env DCS_SAVED_GAMES_PATH

to_wsl_path() {
  local p="$1"
  if [ -d "$p" ]; then
    echo "$p"
    return
  fi
  if command -v wslpath >/dev/null 2>&1; then
    wslpath -u "$p"
    return
  fi
  echo "$p"
}

saved_games_path="$(to_wsl_path "$DCS_SAVED_GAMES_PATH")"

if [ ! -d "$saved_games_path" ]; then
  echo "ERROR: resolved DCS_SAVED_GAMES_PATH does not exist: $saved_games_path" >&2
  exit 1
fi

probe_output="$saved_games_path/Logs/elevation_probe_output.jsonl"
if [ ! -f "$probe_output" ]; then
  echo "ERROR: probe output not found at $probe_output -- run elevation_probe.lua in a live mission first (see tools/dcs-mission-probe/README.md)." >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_file="$output_dir/elevation_probe_output_${timestamp}.jsonl"

cp "$probe_output" "$out_file"

echo "Wrote $out_file"
wc -l "$out_file"
