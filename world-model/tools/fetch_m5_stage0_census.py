#!/usr/bin/env python3
"""M5 Stage 0: derive the `latakia-20km` envelope and run one widened Overpass
census fetch to gate the region choice before any store code is built.

Not part of the pipeline -- a throwaway census script per
`plans/m5-first-persistent-model/checklist.md` Stage 0. Reuses
`osm.overpass.fetch_bbox`'s cache-first/single-network-call/User-Agent
discipline (see `world-model/research/2026-09-03-m3-osm-overlay.md`) with a
widened query (`landuse`, `natural=water`, `place` way/relation added to
M3's `highway`/`building`/`place` node/`waterway` set) and reports feature
counts against Stage 0's gate: the region must contain water polygons AND
settlement polygons AND named places (Gemerek/M3 shipped empty water/place
layers -- this script exists to catch that failure mode before Stage 1).

Run from `world-model/`:

    .venv/bin/python tools/fetch_m5_stage0_census.py [--offset-m 3000]

Attribution: any reported counts are derived from OSM data and must carry
"(c) OpenStreetMap contributors" wherever they are reused.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from coordinates import dcs_to_wgs84
from osm.overpass import BBox, fetch_bbox

_THEATRE = "Syria"
# Centre: wgs84_to_dcs("Syria", 35.40109, 35.94868) -- the published OSLK ARP,
# `plans/m5-first-persistent-model/plan.md` "Region" section.
_CENTRE_X = 41934.892
_CENTRE_Z = 5685.076
_HALF_EXTENT_M = 10_000.0

_CACHE_PATH = (
    _WORLD_MODEL_ROOT
    / "data"
    / "raw"
    / "osm"
    / "2026-09-04"
    / "latakia_20km_widened.json"
)


def _envelope(offset_m: float) -> BBox:
    """DCS-space square -> WGS84 bounding box for the (offset) region."""
    ox = _CENTRE_X + offset_m
    corners = [
        (ox - _HALF_EXTENT_M, _CENTRE_Z - _HALF_EXTENT_M),
        (ox + _HALF_EXTENT_M, _CENTRE_Z - _HALF_EXTENT_M),
        (ox - _HALF_EXTENT_M, _CENTRE_Z + _HALF_EXTENT_M),
        (ox + _HALF_EXTENT_M, _CENTRE_Z + _HALF_EXTENT_M),
    ]
    latlons = [dcs_to_wgs84(_THEATRE, x, z) for x, z in corners]
    south = min(lat for lat, _lon in latlons)
    north = max(lat for lat, _lon in latlons)
    west = min(lon for _lat, lon in latlons)
    east = max(lon for _lat, lon in latlons)
    return BBox(south=south, west=west, north=north, east=east)


def _build_widened_query(bbox: BBox) -> str:
    coords = f"{bbox.south},{bbox.west},{bbox.north},{bbox.east}"
    return (
        "[out:json][timeout:25];\n"
        "(\n"
        f'  way["highway"]({coords});\n'
        f'  way["building"]({coords});\n'
        f'  node["place"]({coords});\n'
        f'  way["place"]({coords});\n'
        f'  relation["place"]({coords});\n'
        f'  way["waterway"]({coords});\n'
        f'  way["natural"="water"]({coords});\n'
        f'  relation["natural"="water"]({coords});\n'
        f'  way["landuse"]({coords});\n'
        ");\n"
        "out geom;\n"
    )


def _tag_has(tags: dict[str, Any], key: str, value: str | None = None) -> bool:
    if key not in tags:
        return False
    return value is None or tags[key] == value


def _census(elements: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "total": len(elements),
        "nodes": 0,
        "ways": 0,
        "relations": 0,
        "water_polygons": 0,
        "settlement_polygons": 0,
        "named_places": 0,
        "highways": 0,
        "buildings": 0,
    }
    for element in elements:
        element_type = element["type"]
        tags = element.get("tags", {})
        if element_type == "node":
            counts["nodes"] += 1
        elif element_type == "way":
            counts["ways"] += 1
        elif element_type == "relation":
            counts["relations"] += 1

        if element_type in ("way", "relation"):
            if _tag_has(tags, "natural", "water") or _tag_has(
                tags, "waterway", "riverbank"
            ):
                counts["water_polygons"] += 1
            if _tag_has(tags, "place") or _tag_has(tags, "landuse", "residential"):
                counts["settlement_polygons"] += 1
            if _tag_has(tags, "highway"):
                counts["highways"] += 1
            if _tag_has(tags, "building"):
                counts["buildings"] += 1
        if element_type == "node" and _tag_has(tags, "place") and "name" in tags:
            counts["named_places"] += 1

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offset-m",
        type=float,
        default=3000.0,
        help="Eastward (inland) offset in DCS x metres, 0..3000 per Stage 0's cap.",
    )
    args = parser.parse_args()

    bbox = _envelope(args.offset_m)
    print(f"Offset: +{args.offset_m:.0f} m")
    print(f"BBox (WGS84 south/west/north/east): {bbox}")

    query = _build_widened_query(bbox)
    cache_path = fetch_bbox(bbox, _CACHE_PATH, query=query)
    print(f"Cache: {cache_path} ({cache_path.stat().st_size} bytes)")

    data = json.loads(cache_path.read_text(encoding="utf-8"))
    counts = _census(data["elements"])
    print("Feature counts:")
    for key, value in counts.items():
        print(f"  {key}: {value}")

    gate_water = counts["water_polygons"] > 0
    gate_settlement = counts["settlement_polygons"] > 0
    gate_named = counts["named_places"] > 0
    print(
        "Gate: water polygons="
        f"{'PASS' if gate_water else 'FAIL'}, settlement polygons="
        f"{'PASS' if gate_settlement else 'FAIL'}, named places="
        f"{'PASS' if gate_named else 'FAIL'}"
    )
    return 0 if (gate_water and gate_settlement and gate_named) else 1


if __name__ == "__main__":
    sys.exit(main())
