#!/usr/bin/env bash
# M0 recon: record installed DCS version + confirm Syria terrain presence.
#
# This is the canonical, version-controlled copy. To run it: copy this file
# (and any sibling scripts) into win-mac-sync/run-wsl/ on the machine where
# win-mac-sync is synced (Dropbox), then run it there in WSL bash on the
# Windows DCS machine. win-mac-sync itself is NOT part of this repo — it's a
# scratch sync channel; see world-model/WORKFLOW.md.
#
# Requires env vars:
#   DCS_INSTALL_PATH       - DCS World install dir (Windows or WSL-style path)
#   DCS_SAVED_GAMES_PATH   - DCS Saved Games dir (Windows or WSL-style path)
#
# Writes a timestamped JSON result to ../wsl-output/ (i.e.
# win-mac-sync/wsl-output/ once deployed). That output is scratch too — once
# synced back to the Mac, copy anything worth keeping into world-model/research/
# (findings) or world-model/data/raw/ (raw artifacts); do not leave results
# only in win-mac-sync/wsl-output/.
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

require_env DCS_INSTALL_PATH
require_env DCS_SAVED_GAMES_PATH

# Accept either a native Windows path or an already-WSL path.
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

install_path="$(to_wsl_path "$DCS_INSTALL_PATH")"
saved_games_path="$(to_wsl_path "$DCS_SAVED_GAMES_PATH")"

if [ ! -d "$install_path" ]; then
  echo "ERROR: resolved DCS_INSTALL_PATH does not exist: $install_path" >&2
  exit 1
fi
if [ ! -d "$saved_games_path" ]; then
  echo "ERROR: resolved DCS_SAVED_GAMES_PATH does not exist: $saved_games_path" >&2
  exit 1
fi

autoupdate_cfg="$install_path/autoupdate.cfg"
dcs_version="null"
if [ -f "$autoupdate_cfg" ]; then
  version_raw="$(grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$autoupdate_cfg" | head -1 | sed -E 's/.*"([^"]+)"$/\1/' || true)"
  if [ -n "${version_raw:-}" ]; then
    dcs_version="\"$version_raw\""
  fi
fi

syria_terrain_path="$install_path/Mods/terrains/Syria"
syria_present=false
if [ -d "$syria_terrain_path" ]; then
  syria_present=true
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_file="$output_dir/dcs_install_probe_${timestamp}.json"

cat > "$out_file" <<EOF
{
  "timestamp_utc": "$timestamp",
  "hostname": "$(hostname)",
  "dcs_install_path": "$install_path",
  "dcs_saved_games_path": "$saved_games_path",
  "dcs_version": $dcs_version,
  "syria_terrain_present": $syria_present,
  "syria_terrain_path": "$syria_terrain_path"
}
EOF

echo "Wrote $out_file"
cat "$out_file"
