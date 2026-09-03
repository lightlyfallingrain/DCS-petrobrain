#!/usr/bin/env bash
# M2 recon: inspect Syria's terrain-mesh base texture ("clipmap") tree —
# the candidate location for the imagery behind F10's "satellite" map mode
# — without modifying the DCS install.
#
# This is the canonical, version-controlled copy. To run it: copy this file
# into win-mac-sync/run-wsl/ on the machine where win-mac-sync is synced
# (Dropbox), then run it there in WSL bash on the Windows DCS machine.
# win-mac-sync itself is NOT part of this repo — see world-model/WORKFLOW.md.
#
# Why: world-model/data/raw/dcs/2026-09-02/DCS-files.txt (an M0 `find`
# listing) shows Mods/terrains/Syria/clipmaps/ containing three
# subdirectories — colortexture/, normalmap/, splatmap/ — each tiled by
# scale (1m/4m/8m/16m/128m, some with (spring)/(winter) seasonal variants)
# and named like RasterCharts's tiles (`{scale}m{sheet}{level}.tif.clipmap`,
# e.g. `1mAA00.tif.clipmap`). "clipmap" is a standard real-time terrain
# rendering technique (nested LOD texture grids streamed around the
# viewer — see NVIDIA GPU Gems 2 ch.2) — this is very likely the terrain
# mesh's own base-color texture pyramid, i.e. the asset that ALSO backs
# F10's satellite mode, in DCS's native x/z tiling scheme (NOT an external
# chart product like RasterCharts). This script inspects colortexture/
# (and takes one normalmap/splatmap sample for comparison) to confirm file
# format/dimensions and pull samples for local decode, without extracting
# the whole multi-gigabyte tree.
#
# Requires env var:
#   DCS_INSTALL_PATH - DCS World install dir (Windows or WSL-style path)
#
# Writes results to ../wsl-output/ (i.e. win-mac-sync/wsl-output/ once
# deployed) as a timestamped .txt report plus a small samples/ dir with a
# few extracted sample .tif.clipmap files (for format/dimension inspection
# on the Mac side). Does NOT copy the full clipmap tree (likely tens of GB)
# — only a directory listing plus a handful of sample files.
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

clipmaps_dir="$install_path/Mods/terrains/Syria/clipmaps"
colortexture_dir="$clipmaps_dir/colortexture"

if [ ! -d "$colortexture_dir" ]; then
  echo "ERROR: colortexture dir not found at $colortexture_dir" >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report="$output_dir/syria_satellite_texture_probe_${timestamp}.txt"
samples_dir="$output_dir/syria_satellite_texture_samples_${timestamp}"
mkdir -p "$samples_dir"

{
  echo "=== Syria clipmaps/colortexture probe — $timestamp ==="
  echo "clipmaps_dir: $clipmaps_dir"
  echo

  echo "--- Top-level clipmaps/ subdirectories ---"
  find "$clipmaps_dir" -maxdepth 1 -mindepth 1 -type d
  echo

  echo "--- colortexture/ scale-tier subdirectories (incl. seasonal variants) ---"
  find "$colortexture_dir" -maxdepth 1 -mindepth 1 -type d
  echo

  echo "--- Full recursive listing: colortexture/1m (highest-res tier — likely satellite-mode source) ---"
  if [ -d "$colortexture_dir/1m" ]; then
    find "$colortexture_dir/1m" -type f -printf '%s\t%p\n' | sort -k2
  else
    echo "colortexture/1m not found — listing whatever the highest-res tier actually is:"
    find "$colortexture_dir" -maxdepth 1 -mindepth 1 -type d | sort
  fi
  echo

  echo "--- Full recursive listing: entire colortexture/ tree (all scales/seasons) ---"
  find "$colortexture_dir" -type f -printf '%s\t%p\n' | sort
  echo

  echo "--- File count and total size per scale-tier ---"
  for d in "$colortexture_dir"/*/; do
    tier="$(basename "$d")"
    count="$(find "$d" -type f | wc -l)"
    size="$(du -sh "$d" 2>/dev/null | cut -f1)"
    echo "$tier: $count files, $size"
  done
  echo

  # NOTE: every `find | head` below wraps find in `{ find ... || true; }` —
  # without this, `head` closing the pipe early after N lines can SIGPIPE
  # `find` before it finishes walking a large directory (colortexture/1m has
  # 200+ files); under `set -euo pipefail` that non-zero find exit aborts the
  # whole script silently mid-report. A prior run of this script died exactly
  # here for exactly this reason — output cut off with no error message.

  echo "--- Sample file: first 64 bytes hex of one 128m colortexture tile (smallest tier) ---"
  sample_file="$( { find "$colortexture_dir/128m" -type f -name '*.tif.clipmap' 2>/dev/null || true; } | sort | head -1)"
  if [ -n "${sample_file:-}" ]; then
    echo "sample: $sample_file"
    ls -la "$sample_file"
    xxd -l 64 "$sample_file" || od -A x -t x1z -v "$sample_file" | head -5
  else
    echo "no .tif.clipmap file found under colortexture/128m"
  fi
  echo

  echo "--- Extracting 2 sample colortexture files (128m tier, smallest — keeps sync payload light) for local decode ---"
  mapfile -t sample_entries < <({ find "$colortexture_dir/128m" -type f -name '*.tif.clipmap' 2>/dev/null || true; } | sort | head -2)
  if [ "${#sample_entries[@]}" -eq 0 ]; then
    mapfile -t sample_entries < <({ find "$colortexture_dir" -type f -name '*.tif.clipmap' 2>/dev/null || true; } | sort | head -2)
  fi
  for entry in "${sample_entries[@]}"; do
    echo "copying: $entry"
    cp "$entry" "$samples_dir/" || echo "  FAILED to copy $entry"
  done
  echo

  echo "--- One normalmap/ and one splatmap/ sample (smallest available tier), for comparison ---"
  for kind in normalmap splatmap; do
    kdir="$clipmaps_dir/$kind"
    if [ -d "$kdir" ]; then
      one="$( { find "$kdir" -type f -name '*.tif.clipmap' 2>/dev/null || true; } | sort | head -1)"
      if [ -n "${one:-}" ]; then
        echo "copying $kind sample: $one"
        cp "$one" "$samples_dir/${kind}_$(basename "$one")" || echo "  FAILED to copy $one"
      fi
    fi
  done
  echo

  echo "--- Sample files copied to $samples_dir ---"
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
