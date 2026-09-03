#!/usr/bin/env bash
# M2 recon: inspect Syria's RasterCharts archive contents, file formats,
# and (if present) any georeferencing/index metadata, without modifying
# the DCS install.
#
# This is the canonical, version-controlled copy. To run it: copy this file
# into win-mac-sync/run-wsl/ on the machine where win-mac-sync is synced
# (Dropbox), then run it there in WSL bash on the Windows DCS machine.
# win-mac-sync itself is NOT part of this repo — see world-model/WORKFLOW.md.
#
# Why: world-model/data/raw/dcs/2026-09-02/DCS-files.txt (filename-only,
# from an M0 `find` listing) shows Syria/RasterCharts contains exactly:
#   Mods/terrains/Syria/RasterCharts/rasterCharts.sup5
#   Mods/terrains/Syria/RasterCharts/rasterCharts.zip
# — a single archive, unlike Caucasus which has scale-tiered subdirectories
# (0.25M/0.5M/1M/2M/5M) each holding many small per-tile zips. This script
# looks *inside* rasterCharts.zip (read-only, listing + extracting a couple
# of sample entries to a scratch dir — never writes into the DCS install)
# to determine actual tile format, naming/indexing, and dimensions, and
# probes rasterCharts.sup5's header bytes since its format is undocumented
# (an open ED forum question as of this investigation).
#
# Requires env var:
#   DCS_INSTALL_PATH - DCS World install dir (Windows or WSL-style path)
#
# Writes results to ../wsl-output/ (i.e. win-mac-sync/wsl-output/ once
# deployed) as a timestamped .txt report plus a small samples/ dir with a
# few extracted sample tile files (for format/dimension inspection on the
# Mac side, e.g. via `file` or PIL). Does NOT extract the full archive
# (could be large) — only lists it and pulls a handful of sample entries.
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
if [ ! -d "$install_path" ]; then
  echo "ERROR: resolved DCS_INSTALL_PATH does not exist: $install_path" >&2
  exit 1
fi

raster_dir="$install_path/Mods/terrains/Syria/RasterCharts"
zip_path="$raster_dir/rasterCharts.zip"
sup5_path="$raster_dir/rasterCharts.sup5"

if [ ! -f "$zip_path" ]; then
  echo "ERROR: rasterCharts.zip not found at $zip_path" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report="$output_dir/syria_rastercharts_probe_${timestamp}.txt"
samples_dir="$output_dir/syria_rastercharts_samples_${timestamp}"
mkdir -p "$samples_dir"

{
  echo "=== Syria RasterCharts probe — $timestamp ==="
  echo "zip_path: $zip_path"
  echo "sup5_path: $sup5_path"
  echo

  echo "--- rasterCharts.zip: full entry listing (unzip -l) ---"
  unzip -l "$zip_path" || echo "unzip -l FAILED"
  echo

  echo "--- rasterCharts.zip: entry count ---"
  unzip -l "$zip_path" | tail -1
  echo

  echo "--- rasterCharts.sup5: file size + first 64 bytes (hex+ascii) ---"
  if [ -f "$sup5_path" ]; then
    ls -la "$sup5_path"
    xxd -l 64 "$sup5_path" || od -A x -t x1z -v "$sup5_path" | head -5
  else
    echo "rasterCharts.sup5 not found (unexpected — was present in M0 file listing)"
  fi
  echo

  echo "--- Extracting up to 5 sample entries for local format inspection ---"
  # List entry names only, skip the unzip header/footer lines, take first 5.
  mapfile -t sample_entries < <(unzip -Z1 "$zip_path" | grep -v '/$' | head -5)
  for entry in "${sample_entries[@]}"; do
    echo "extracting: $entry"
    unzip -o -j "$zip_path" "$entry" -d "$samples_dir" || echo "  FAILED to extract $entry"
  done
  echo
  echo "--- Sample files extracted to $samples_dir ---"
  ls -la "$samples_dir"
  echo
  echo "--- 'file' identification of sample files (if 'file' command available) ---"
  if command -v file >/dev/null 2>&1; then
    file "$samples_dir"/* || true
  else
    echo "'file' command not available in this WSL environment"
  fi
} > "$report" 2>&1

echo "Wrote $report"
echo "Sample files in $samples_dir"
