#!/usr/bin/env python3
"""Store -> WGS84 GeoJSON, for QGIS inspection.

This is the tool that replaces "make the storage file a GeoPackage" (see
`plans/m5-first-persistent-model/plan.md`'s "Key decision: spatial storage"
-- GeoJSON in plain WGS84 sidesteps the `+axis=neu` custom-SRS ambiguity a
GPKG would carry). Every vertex is converted DCS x/z -> WGS84 via
`coordinates.dcs_to_wgs84` (`confidence="confirmed"`). GeoJSON feature
`properties` carry the full provenance/confidence/uncertainty payload, not
just geometry -- the point of this exporter is to let a human eyeball
*and* audit the model, not just its shape.

Attribution: any GeoJSON containing OSM-sourced features must be
distributed with "(c) OpenStreetMap contributors" -- printed to stderr on
every run, per `world-model/CLAUDE.md`'s OSM/ODbL discipline.

Run from `world-model/`:

    .venv/bin/python tools/export_geojson.py <db> <out.geojson> [--kinds k1,k2,...]
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from coordinates import dcs_to_wgs84
from store.models import StoredFeature
from store.reader import all_features, load_only_region

_GEOM_TYPE_TO_GEOJSON = {
    "Point": "Point",
    "LineString": "LineString",
    "Polygon": "Polygon",
}


def _feature_to_geojson(feature: StoredFeature, theatre: str) -> dict[str, Any]:
    lonlat_points = [
        [lon, lat]
        for lat, lon in (dcs_to_wgs84(theatre, x, z) for x, z in feature.geometry)
    ]

    if feature.geom_type == "Point":
        coordinates: Any = lonlat_points[0]
    elif feature.geom_type == "LineString":
        coordinates = lonlat_points
    elif feature.geom_type == "Polygon":
        ring = lonlat_points
        if ring[0] != ring[-1]:
            ring = [*ring, ring[0]]
        coordinates = [ring]
    else:
        raise ValueError(f"Unknown geom_type {feature.geom_type!r}")

    return {
        "type": "Feature",
        "geometry": {
            "type": _GEOM_TYPE_TO_GEOJSON[feature.geom_type],
            "coordinates": coordinates,
        },
        "properties": {
            "kind": feature.kind,
            "name": feature.name,
            "subtype": feature.subtype,
            "tags": feature.tags,
            "source_ref": feature.source_ref,
            "provenance": feature.provenance,
            "confidence": feature.confidence,
            "position_uncertainty_m": feature.position_uncertainty_m,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument(
        "--kinds", default=None, help="Comma-separated list of feature kinds to export."
    )
    args = parser.parse_args()

    kinds = args.kinds.split(",") if args.kinds else None

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        region = load_only_region(conn)
        if region is None:
            parser.error(f"{args.db} has no built region")
            return
        features = all_features(conn, kinds)
    finally:
        conn.close()

    geojson = {
        "type": "FeatureCollection",
        "features": [_feature_to_geojson(f, region.theatre) for f in features],
    }
    args.out.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")

    osm_feature_count = sum(
        1 for f in features if f.provenance.get("geometry") == "osm"
    )
    print(f"Wrote {len(features)} features to {args.out}", file=sys.stderr)
    if osm_feature_count:
        print(
            f"{osm_feature_count} features are OSM-sourced: "
            "(c) OpenStreetMap contributors, ODbL",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
