#!/usr/bin/env bash
# M1 recon: search Syria terrain Lua config files for any directly-stated
# projection type/parameters (central meridian, false easting/northing,
# origin lat/lon), and dump beacons.lua (nav beacons often carry both a
# DCS x/z position and a real-world-derived frequency/ident, occasionally
# lat/lon in comments) for manual inspection.
#
# Why: world-model/data/raw/dcs/2026-09-02/DCS-files.txt is a filename-only
# listing (no file contents), so it cannot answer whether Syria's own Lua
# config states its projection directly. This script reads actual file
# contents, read-only, from the installed DCS Syria terrain.
#
# This is the canonical, version-controlled copy. To run it: copy this file
# into win-mac-sync/run-wsl/ on the machine where win-mac-sync is synced
# (Dropbox), then run it there in WSL bash on the Windows DCS machine.
# win-mac-sync itself is NOT part of this repo — it's a scratch transfer
# channel; see world-model/WORKFLOW.md.
#
# Requires env var:
#   DCS_INSTALL_PATH - DCS World install dir (Windows or WSL-style path)
#
# Writes a timestamped .txt result to ../wsl-output/ (i.e.
# win-mac-sync/wsl-output/ once deployed). That output is scratch too — once
# synced back to the Mac, copy anything worth keeping into world-model/research/
# (findings) or world-model/data/raw/ (raw artifacts).
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
syria_path="$install_path/Mods/terrains/Syria"

if [ ! -d "$syria_path" ]; then
  echo "ERROR: resolved Syria terrain path does not exist: $syria_path" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_file="$output_dir/syria_terrain_lua_probe_${timestamp}.txt"

{
  echo "=== Syria terrain Lua probe — $timestamp ==="
  echo "Install path: $install_path"
  echo

  for f in entry.lua notInstances.lua radio.lua beacons.lua shadingOptions.lua \
           map/towns.lua MissionGenerator/nodes.lua MissionGenerator/nodesMap.lua \
           misc/metacache/base.lua; do
    fp="$syria_path/$f"
    echo "--- $f ---"
    if [ -f "$fp" ]; then
      echo "(exists, $(wc -l < "$fp") lines)"
      echo "-- grep for projection/coordinate keywords --"
      grep -inE "lambert|mercator|tmerc|proj|meridian|false_?east|false_?north|scale_?factor|origin|latitude|longitude|centerPoint|zone" "$fp" || echo "(no matches)"
    else
      echo "(not found)"
    fi
    echo
  done

  echo "=== Full content of entry.lua (primary suspect for projection/origin config) ==="
  if [ -f "$syria_path/entry.lua" ]; then
    cat "$syria_path/entry.lua"
  else
    echo "(entry.lua not found)"
  fi
  echo

  echo "=== Full content of beacons.lua (nav beacon positions, for cross-checking) ==="
  if [ -f "$syria_path/beacons.lua" ]; then
    cat "$syria_path/beacons.lua"
  else
    echo "(beacons.lua not found)"
  fi
} > "$out_file"

echo "Wrote $out_file"
