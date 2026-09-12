#!/usr/bin/env python3
"""CLI over `build.pipeline.build_region` -- rebuild a region's `.sqlite`
from `data/raw/`.

Not part of the pipeline's importable API; a thin CLI wrapper. Run from
`world-model/`:

    .venv/bin/python tools/build_world_model.py <region_name> \\
        --towns <towns.lua> --beacons <beacons.lua> --osm-cache <cache.json> \\
        [--out <out.sqlite>]

Defaults for `latakia-20km` point at the raw paths M5 Stage 1/2 already
populated (`data/raw/dcs/syria/map/*.lua`,
`data/raw/osm/2026-09-04/latakia_20km_widened.json`,
`data/raw/dcs/syria/roads/Syria.routes`) so the common case needs only the
region name. `--osm-cache`, `--routes` and `--probe-output` are all
optional -- if a file isn't present (e.g. a fresh checkout without the
2.25 GB `Syria.routes` or a live probe's output staged), that layer is
skipped and reported as absent, not an error. `--srtm-tile` is optional and
only affects the `--probe-output` elevation grid's stored `stats` (a
metadata-only SRTM delta summary, never stored samples -- see
`build.ingest_probe`).

`--srtm-dir` (M7 Stage 2) is a directory of `.hgt` tiles ingested as the
region's *primary* `elevation` grid (`provenance="srtm"`, see
`build.ingest_srtm`) -- distinct from `--srtm-tile` above. Every `*.hgt`/
`*.HGT` file directly inside the directory is loaded (not recursive).
`--srtm-grid-spacing-m` controls the storage grid's cell spacing (default
1000m); see `build.pipeline`'s `DEFAULT_SRTM_GRID_SPACING_M` for the row-count
sizing tradeoff this default is a judgment call about.

`syria-full` (M7 Stage 1) has no registered defaults and no OSM cache at
all -- OSM is out of scope for M7 (see
`plans/m7-full-theatre-pipeline/plan.md` clarification 2) -- so it must be
invoked with explicit `--towns`, `--beacons` and `--routes` and no
`--osm-cache`:

    .venv/bin/python tools/build_world_model.py syria-full \\
        --towns <path/to/towns.lua> --beacons <path/to/beacons.lua> \\
        --routes <path/to/Syria.routes> --srtm-dir <path/to/hgt_tiles/>

See `world-model/docs/M7_RUN_INSTRUCTIONS.md` for the full step-by-step
procedure -- this is the actual full-theatre build, which per the plan's
"Execution boundary" only the user runs, on their Windows DCS machine.

`--osm-pbf` (M9) points at a pre-clipped, pre-merged Geofabrik `.osm.pbf`
extract (see `world-model/docs/M9_OSM_RUN_INSTRUCTIONS.md`) and, if given,
takes precedence over `--osm-cache` for that build -- `build.pipeline.
build_region`'s `osm_pbf_path` parameter.
"""

import argparse
import logging
import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from build.pipeline import DEFAULT_SRTM_GRID_SPACING_M, build_region
from build.region import REGIONS

_DEFAULT_RAW_PATHS: dict[str, dict[str, Path]] = {
    "latakia-20km": {
        "towns": _WORLD_MODEL_ROOT / "data/raw/dcs/syria/map/towns.lua",
        "beacons": _WORLD_MODEL_ROOT / "data/raw/dcs/syria/map/beacons.lua",
        "osm_cache": _WORLD_MODEL_ROOT
        / "data/raw/osm/2026-09-04/latakia_20km_widened.json",
        "routes": _WORLD_MODEL_ROOT / "data/raw/dcs/syria/roads/Syria.routes",
    },
}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("region", choices=sorted(REGIONS.keys()))
    parser.add_argument("--towns", type=Path, default=None)
    parser.add_argument("--beacons", type=Path, default=None)
    parser.add_argument("--osm-cache", type=Path, default=None)
    parser.add_argument("--osm-pbf", type=Path, default=None)
    parser.add_argument("--routes", type=Path, default=None)
    parser.add_argument("--probe-output", type=Path, default=None)
    parser.add_argument("--srtm-tile", type=Path, default=None)
    parser.add_argument("--srtm-dir", type=Path, default=None)
    parser.add_argument(
        "--srtm-grid-spacing-m", type=float, default=DEFAULT_SRTM_GRID_SPACING_M
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    region = REGIONS[args.region]
    defaults = _DEFAULT_RAW_PATHS.get(args.region, {})

    towns_path = args.towns or defaults.get("towns")
    beacons_path = args.beacons or defaults.get("beacons")
    osm_cache_path = args.osm_cache or defaults.get("osm_cache")
    routes_path = args.routes or defaults.get("routes")
    probe_output_path = args.probe_output or defaults.get("probe_output")
    srtm_tile_path = args.srtm_tile or defaults.get("srtm_tile")
    if towns_path is None or beacons_path is None:
        parser.error(
            f"No default raw paths registered for region {args.region!r} -- "
            "pass --towns/--beacons explicitly"
        )

    srtm_tile_paths: list[Path] | None = None
    if args.srtm_dir is not None:
        srtm_tile_paths = sorted(
            {*args.srtm_dir.glob("*.hgt"), *args.srtm_dir.glob("*.HGT")}
        )
        if not srtm_tile_paths:
            parser.error(f"--srtm-dir {args.srtm_dir} contains no .hgt files")

    out_path = args.out or (
        _WORLD_MODEL_ROOT / "data/world-model" / f"{args.region}.sqlite"
    )

    report = build_region(
        region,
        towns_path,
        beacons_path,
        osm_cache_path,
        out_path,
        routes_path,
        probe_output_path,
        srtm_tile_path,
        srtm_tile_paths,
        args.srtm_grid_spacing_m,
        osm_pbf_path=args.osm_pbf,
    )

    print(f"Built {out_path}")
    for kind, count in sorted(report.feature_counts.items()):
        print(f"  {kind}: {count}")
    if report.beacon_stats is not None:
        print(f"  beacon stats: {report.beacon_stats}")
    if report.osm_stats is not None:
        print(f"  osm stats: {report.osm_stats}")
    elif report.osm_skipped:
        print("  osm: skipped (osm_cache_path not given or not found)")
    if report.roadnet_stats is not None:
        print(f"  roadnet stats: {report.roadnet_stats}")
    elif report.roadnet_skipped:
        print("  roadnet: skipped (routes_path not given or not found)")
    if report.probe_stats is not None:
        print(f"  probe stats: {report.probe_stats}")
    elif report.probe_skipped:
        print("  probe: skipped (probe_output_path not given or not found)")
    if report.srtm_stats is not None:
        print(f"  srtm stats: {report.srtm_stats}")
    elif report.srtm_skipped:
        print("  srtm: skipped (--srtm-dir not given or no .hgt files found)")


if __name__ == "__main__":
    main()
