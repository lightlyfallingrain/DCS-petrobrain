#!/usr/bin/env python3
"""Diagnostic: compare DCS `land.getHeight` samples against an external SRTM DEM.

Not part of the pipeline. Loads a parsed `elevation_probe.lua` output file
(via `elevation.dcs_grid.parse_probe_output`), runs each point's DCS x/z
through `coordinates.dcs_to_wgs84` to get lat/lon (the same transform M1-M3
already validated), looks up the corresponding SRTM elevation (via
`elevation.dem.SrtmTile.height_at`), and prints an
`elevation_dcs / elevation_external / delta` table plus summary stats
(mean/min/max/stddev delta) -- field names per
`docs/concept/WORLD_MODEL_BUILDER.md`'s Elevation section.

Vertical datum note: SRTM heights are typically referenced to the EGM96
geoid; DCS's own terrain-art vertical reference is not established (see
`world-model/research/2026-09-03-m4-elevation-recon.md` "Risks"). A
systematic offset across the whole grid (not point-to-point noise) is the
expected signature of a datum mismatch, not a bug -- this tool reports
summary stats so that pattern is visible, but does not attempt to correct
for it.

Run from `world-model/`:

    .venv/bin/python tools/inspect_elevation.py compare \\
        <probe_output_path> <hgt_path> <theatre>
"""

import argparse
import statistics
import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from coordinates import dcs_to_wgs84
from elevation.dcs_grid import parse_probe_output
from elevation.dem import SrtmTile


def cmd_compare(probe_output_path: Path, hgt_path: Path, theatre: str) -> None:
    samples = parse_probe_output(probe_output_path)
    tile = SrtmTile.from_file(hgt_path)

    rows: list[tuple[str, float, float, float]] = []
    off_tile = 0
    for sample in samples:
        lat, lon = dcs_to_wgs84(theatre, sample.x, sample.z)
        try:
            elevation_external = tile.height_at(lat, lon)
        except ValueError:
            off_tile += 1
            continue
        delta = sample.height_m - elevation_external
        rows.append((sample.name, sample.height_m, elevation_external, delta))

    if not rows:
        print("No points fell within the DEM tile -- nothing to compare.")
        return

    header = (
        f"{'name':<10} {'elevation_dcs':>15} {'elevation_external':>19} {'delta':>10}"
    )
    print(header)
    print("-" * len(header))
    for name, elevation_dcs, elevation_external, delta in rows:
        print(
            f"{name:<10} {elevation_dcs:>15.2f} {elevation_external:>19.2f} {delta:>10.2f}"
        )

    deltas = [delta for _, _, _, delta in rows]
    print()
    print(f"points compared: {len(rows)}, off-tile/skipped: {off_tile}")
    print(f"delta mean:   {statistics.mean(deltas):.2f} m")
    print(f"delta min:    {min(deltas):.2f} m")
    print(f"delta max:    {max(deltas):.2f} m")
    if len(deltas) > 1:
        print(f"delta stddev: {statistics.stdev(deltas):.2f} m")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare_parser = subparsers.add_parser(
        "compare", help="compare a parsed DCS elevation grid against an SRTM tile"
    )
    compare_parser.add_argument("probe_output_path", type=Path)
    compare_parser.add_argument("hgt_path", type=Path)
    compare_parser.add_argument("theatre")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "compare":
        cmd_compare(args.probe_output_path, args.hgt_path, args.theatre)


if __name__ == "__main__":
    main()
