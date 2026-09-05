#!/usr/bin/env python3
"""M7 Stage 2: validate SRTM alignment against a real DCS live-probe
spot-check run.

Not part of the pipeline -- a throwaway analysis script per
`plans/m7-full-theatre-pipeline/plan.md` Stage 2 ("Run a scattered
live-DCS-probe control-point set ... via the existing `elevation_probe.lua`
mechanism unchanged, and compare against SRTM at the same points"). Reuses
`build.validate.compare_probe_to_srtm`, already unit-tested against small
fixtures in `tests/test_build_validate.py` -- this script is the one thing
those tests cannot cover: running the same comparison against a real
`elevation_probe.lua` spot-check output and real `.hgt` tiles.

Unlike `validate_m7_stage1.py`, this does **not** need a built
`syria-full.sqlite` at all -- the spot-check comparison only needs the
probe's own output file plus SRTM tiles, independent of what's been
ingested into the store (see `build.validate`'s module docstring). Per the
plan's "Execution boundary", nobody but the user runs the live-mission
probe or stages the `.hgt` tiles -- see `world-model/docs/
M7_RUN_INSTRUCTIONS.md`'s Stage 2 section for how to produce both inputs
this script reads.

Run from `world-model/`, after running the spot-check probe mission and
staging SRTM tiles:

    .venv/bin/python tools/validate_m7_stage2_elevation.py \\
        --probe-output <path/to/spot_check_output.jsonl> \\
        --srtm-dir <path/to/hgt_tiles/> \\
        [--theatre Syria]
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from build.validate import compare_probe_to_srtm
from elevation.dcs_grid import parse_probe_output
from elevation.dem import SrtmTile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-output", type=Path, required=True)
    parser.add_argument("--srtm-dir", type=Path, required=True)
    parser.add_argument("--theatre", default="Syria")
    args = parser.parse_args()

    if not args.probe_output.exists():
        print(f"error: {args.probe_output} does not exist", file=sys.stderr)
        sys.exit(1)

    tile_paths = sorted({*args.srtm_dir.glob("*.hgt"), *args.srtm_dir.glob("*.HGT")})
    if not tile_paths:
        print(f"error: {args.srtm_dir} contains no .hgt files", file=sys.stderr)
        sys.exit(1)

    probe_samples = parse_probe_output(args.probe_output)
    tiles = [SrtmTile.from_file(p) for p in tile_paths]

    report = compare_probe_to_srtm(probe_samples, tiles, args.theatre)

    result = {
        "probe_output": str(args.probe_output),
        "srtm_dir": str(args.srtm_dir),
        "tiles_loaded": len(tiles),
        "points_compared": len(report.points),
        "points_skipped": report.points_skipped,
        "mean_delta_m": report.mean_delta_m,
        "median_delta_m": report.median_delta_m,
        "stddev_delta_m": report.stddev_delta_m,
        "min_delta_m": report.min_delta_m,
        "max_delta_m": report.max_delta_m,
        "points": [asdict(p) for p in report.points],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
