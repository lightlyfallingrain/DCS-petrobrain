#!/usr/bin/env bash
# M5 recon: inspect the raw bytes of DCS Syria's road-network files
# (Mods/terrains/Syria/roads/Syria.rn4 and Syria.routes) to determine
# whether they are a parseable static format (plaintext, simple binary
# structure, known container like zlib) or an opaque ED-proprietary
# compiled format.
#
# Why: file-listing recon (world-model/data/raw/dcs/2026-09-02/DCS-files.txt)
# found that every DCS terrain ships roads/<Terrain>.rn4 + <Terrain>.routes,
# plus one AirfieldsTaxiways/<Airfield>.rn4 per airfield. This is strong
# evidence DCS stores road/taxiway network topology as discrete files
# (not baked only into the terrain mesh/texture) -- but nobody in this
# project has looked at the actual bytes yet, and no public DCS modding
# doc or community project (pydcs, dcs-liberation, dcs-global-terrain-database)
# was found to document or parse the .rn4/.routes format. This probe is
# read-only and only reports structure -- it does not modify anything.
#
# This is the canonical, version-controlled copy. To run it: copy this file
# into win-mac-sync/run-wsl/ on the machine where win-mac-sync is synced
# (Dropbox), then run it there in WSL bash on the Windows DCS machine.
# win-mac-sync itself is NOT part of this repo -- it's a scratch transfer
# channel; see world-model/WORKFLOW.md.
#
# Requires env var:
#   DCS_INSTALL_PATH - DCS World install dir (Windows or WSL-style path)
#
# Writes a timestamped .txt result to ../wsl-output/ (i.e.
# win-mac-sync/wsl-output/ once deployed). That output is scratch too --
# once synced back to the Mac, copy anything worth keeping into
# world-model/research/ (findings) or world-model/data/raw/ (raw artifacts).
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
out_file="$output_dir/syria_roadnet_files_probe_${timestamp}.txt"

inspect_file() {
  local fp="$1"
  echo "--- $fp ---"
  if [ ! -f "$fp" ]; then
    echo "(not found)"
    echo
    return
  fi
  echo "size (bytes): $(wc -c < "$fp")"
  echo "file(1): $(file "$fp" 2>/dev/null || echo 'file command unavailable')"
  echo "-- first 512 bytes (hex+ascii) --"
  xxd -l 512 "$fp" 2>/dev/null || od -A x -t x1z -v "$fp" | head -32
  echo "-- last 256 bytes (hex+ascii) --"
  local size
  size="$(wc -c < "$fp")"
  if [ "$size" -gt 256 ]; then
    xxd -s -256 -l 256 "$fp" 2>/dev/null || tail -c 256 "$fp" | od -A x -t x1z -v
  fi
  echo "-- is it valid UTF-8 / mostly printable text? --"
  if LC_ALL=C grep -qP '[\x00-\x08\x0E-\x1F]' "$fp" 2>/dev/null; then
    echo "contains control bytes -> NOT plain text"
  else
    echo "no control bytes found in a naive scan -> could be text; inspect head below"
    echo "-- head -c 2000 as text --"
    head -c 2000 "$fp"
    echo
  fi
  echo
}

{
  echo "=== Syria roadnet files probe — $timestamp ==="
  echo "Install path: $install_path"
  echo

  echo "## Primary road network (whole-theatre)"
  inspect_file "$syria_path/roads/Syria.rn4"
  inspect_file "$syria_path/roads/Syria.routes"

  echo "## Sample airfield taxiway network (for format comparison — should share Syria.rn4's structure if it's one shared format)"
  inspect_file "$syria_path/AirfieldsTaxiways/Damascus.rn4"
  inspect_file "$syria_path/AirfieldsTaxiways/Incirlik.rn4"

  echo "## For comparison: does Caucasus (a much older, smaller terrain) use the identical container header?"
  caucasus_path="$install_path/Mods/terrains/Caucasus"
  if [ -d "$caucasus_path" ]; then
    inspect_file "$caucasus_path/roads/Caucasus.rn4"
    inspect_file "$caucasus_path/roads/Caucasus.routes"
  else
    echo "(Caucasus terrain not installed — skipping comparison)"
  fi
} > "$out_file"

echo "Wrote $out_file"
