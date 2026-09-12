#!/usr/bin/env python3
"""One-off: derive the M9 theatre `.osm.pbf` clip bbox from `syria-full`'s
four DCS-space region corners, padded for safety margin.

Not part of the pipeline; run once to produce the fixed numbers written into
`docs/M9_OSM_RUN_INSTRUCTIONS.md` -- the run instructions never recompute
this at build time (per the plan's "Affected Modules / Files" entry for
that doc).

Padding: `RegionDefinition.to_wgs84_envelope()` already returns
`syria-full`'s own padded (+30 km/side, see `build.region.REGIONS`
`"syria-full"` comment) DCS-space corners converted to lat/lon -- that
padding absorbs DCS's own point-cloud-derived extent uncertainty, not the
OSM clip's own margin. This script adds a further +0.3 degree pad on every
side (~30-33 km at these latitudes: 1 deg latitude ~111 km, 1 deg longitude
~91 km at 35 deg N) so `osmium extract`'s bbox comfortably contains the
built region's own clip window with room to spare -- a way whose nodes
straddle the *region's* edge should never also straddle the *extract's*
edge, which is what `--strategy=smart` (see Design Decision 1) protects
within the extract, not what protects the extract's own boundary from
being flush with the region it needs to cover.
"""

import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from build.region import REGIONS

_CLIP_PAD_DEG = 0.3


def main() -> None:
    region = REGIONS["syria-full"]
    south, west, north, east = region.to_wgs84_envelope()

    clip_south = south - _CLIP_PAD_DEG
    clip_west = west - _CLIP_PAD_DEG
    clip_north = north + _CLIP_PAD_DEG
    clip_east = east + _CLIP_PAD_DEG

    print(
        f"syria-full envelope (south, west, north, east): "
        f"{south:.4f}, {west:.4f}, {north:.4f}, {east:.4f}"
    )
    print(
        f"+{_CLIP_PAD_DEG} deg clip bbox (south, west, north, east): "
        f"{clip_south:.4f}, {clip_west:.4f}, {clip_north:.4f}, {clip_east:.4f}"
    )
    print(
        "osmium extract -b "
        f"{clip_west:.4f},{clip_south:.4f},{clip_east:.4f},{clip_north:.4f}"
    )


if __name__ == "__main__":
    main()
