#!/usr/bin/env python3
"""One-off: derive `REGIONS["afghanistan-full"]`'s DCS-space centre and
rectangular half-extents from the union of `towns.lua` and `beacons.lua`
point clouds, projected through Afghanistan's provisional `tmerc` fit.

Not part of the pipeline; run once to produce the fixed numbers written
into `build/region.py`'s `"afghanistan-full"` entry -- that entry never
recomputes this at build time, same discipline
`derive_m9_osm_clip_bbox.py` already uses for Syria's OSM clip bbox.

Method (multi-theatre-afghanistan plan, Stage 2, main-loop amendment
2026-10-05): **union of towns.lua (projected to x/z) and beacons.lua**,
not beacons alone -- Afghanistan has only 49 beacons, all airfield-tied,
and the investigator found towns.lua the safer lower-bound source (see
`world-model/research/2026-10-04-multi-theatre-afghanistan-caucasus-recon.md`
Q1: beacons alone gave x span 1,023.9 km / z span 1,249.1 km, inflated
relative to the towns.lua bound). `towns.lua` only carries lat/lon, so
each entry is projected to DCS x/z via `coordinates.wgs84_to_dcs`, using
the now-registered (provisional) `THEATRE_PROJECTIONS["Afghanistan"]`.
`beacons.lua` entries already carry native DCS x/z (`position`'s x/z
fields, mid-value is elevation -- see `dcs_data.beacons` module
docstring) and are used directly, not reprojected from `positionGeo`.

Padding: +30 km/side on every edge of the raw union bbox, mirroring
`syria-full`'s own padding (`build.region.REGIONS` `"syria-full"`
comment) and `research/2026-09-05-m7-syria-theatre-extent.md`'s method.
"""

import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from coordinates import wgs84_to_dcs
from dcs_data.beacons import parse_beacons_lua
from dcs_data.towns import parse_towns_lua

_PAD_M = 30_000.0


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "usage: derive_afghanistan_full_region.py <towns.lua path> "
            "<beacons.lua path>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    towns_path = Path(sys.argv[1])
    beacons_path = Path(sys.argv[2])

    towns = parse_towns_lua(towns_path, "Afghanistan")
    beacons = parse_beacons_lua(beacons_path, "Afghanistan")

    xs: list[float] = []
    zs: list[float] = []
    for town in towns:
        x, z = wgs84_to_dcs("Afghanistan", town.lat, town.lon)
        xs.append(x)
        zs.append(z)
    for beacon in beacons:
        xs.append(beacon.x)
        zs.append(beacon.z)

    x_min, x_max = min(xs), max(xs)
    z_min, z_max = min(zs), max(zs)

    padded_x_min = x_min - _PAD_M
    padded_x_max = x_max + _PAD_M
    padded_z_min = z_min - _PAD_M
    padded_z_max = z_max + _PAD_M

    centre_x = (padded_x_min + padded_x_max) / 2
    centre_z = (padded_z_min + padded_z_max) / 2
    half_extent_x_m = (padded_x_max - padded_x_min) / 2
    half_extent_z_m = (padded_z_max - padded_z_min) / 2

    print(f"towns.lua entries: {len(towns)}, beacons.lua entries: {len(beacons)}")
    print(
        f"raw union x range: {x_min:.1f} .. {x_max:.1f} ({(x_max - x_min) / 1000:.1f} km)"
    )
    print(
        f"raw union z range: {z_min:.1f} .. {z_max:.1f} ({(z_max - z_min) / 1000:.1f} km)"
    )
    print(
        f"padded (+{_PAD_M / 1000:.0f}km/side) x range: "
        f"{padded_x_min:.1f} .. {padded_x_max:.1f}"
    )
    print(
        f"padded (+{_PAD_M / 1000:.0f}km/side) z range: "
        f"{padded_z_min:.1f} .. {padded_z_max:.1f}"
    )
    print(f"centre_x={centre_x:.1f}, centre_z={centre_z:.1f}")
    print(
        f"half_extent_x_m={half_extent_x_m:.1f}, half_extent_z_m={half_extent_z_m:.1f}"
    )
    print(
        f"footprint: {2 * half_extent_x_m / 1000:.1f} x "
        f"{2 * half_extent_z_m / 1000:.1f} km, "
        f"aspect ratio {half_extent_x_m / half_extent_z_m:.2f}"
    )


if __name__ == "__main__":
    main()
