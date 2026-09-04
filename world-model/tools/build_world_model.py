#!/usr/bin/env python3
"""CLI over `build.pipeline.build_region` -- rebuild a region's `.sqlite`
from `data/raw/`.

Not part of the pipeline's importable API; a thin CLI wrapper. Run from
`world-model/`:

    .venv/bin/python tools/build_world_model.py <region_name> \\
        --towns <towns.lua> --beacons <beacons.lua> --osm-cache <cache.json> \\
        [--out <out.sqlite>]

Defaults for `latakia-20km` point at the raw paths M5 Stage 1 already
populated (`data/raw/dcs/syria/map/*.lua`,
`data/raw/osm/2026-09-04/latakia_20km_widened.json`) so the common case
needs only the region name.
"""

import argparse
import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from build.pipeline import build_region
from build.region import REGIONS

_DEFAULT_RAW_PATHS: dict[str, dict[str, Path]] = {
    "latakia-20km": {
        "towns": _WORLD_MODEL_ROOT / "data/raw/dcs/syria/map/towns.lua",
        "beacons": _WORLD_MODEL_ROOT / "data/raw/dcs/syria/map/beacons.lua",
        "osm_cache": _WORLD_MODEL_ROOT
        / "data/raw/osm/2026-09-04/latakia_20km_widened.json",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("region", choices=sorted(REGIONS.keys()))
    parser.add_argument("--towns", type=Path, default=None)
    parser.add_argument("--beacons", type=Path, default=None)
    parser.add_argument("--osm-cache", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    region = REGIONS[args.region]
    defaults = _DEFAULT_RAW_PATHS.get(args.region, {})

    towns_path = args.towns or defaults.get("towns")
    beacons_path = args.beacons or defaults.get("beacons")
    osm_cache_path = args.osm_cache or defaults.get("osm_cache")
    if towns_path is None or beacons_path is None or osm_cache_path is None:
        parser.error(
            f"No default raw paths registered for region {args.region!r} -- "
            "pass --towns/--beacons/--osm-cache explicitly"
        )

    out_path = args.out or (
        _WORLD_MODEL_ROOT / "data/world-model" / f"{args.region}.sqlite"
    )

    report = build_region(region, towns_path, beacons_path, osm_cache_path, out_path)

    print(f"Built {out_path}")
    for kind, count in sorted(report.feature_counts.items()):
        print(f"  {kind}: {count}")
    if report.beacon_stats is not None:
        print(f"  beacon stats: {report.beacon_stats}")
    if report.osm_stats is not None:
        print(f"  osm stats: {report.osm_stats}")


if __name__ == "__main__":
    main()
