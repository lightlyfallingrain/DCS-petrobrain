"""`build_region`: assembles one region's `.sqlite` from `data/raw/` sources.

Idempotent -- `open_for_build` deletes and recreates the target `.sqlite` on
every call, per the concept doc's "keep raw separate from derived so the
database can be rebuilt". M5 Stage 1 wired in towns, beacons and OSM; Stage
2 adds the DCS-native roadnet layer (`.routes` walk -> `road` features,
`provenance["geometry"] == "dcs"`). The elevation/surface-type probe grid
(Stage 3) is still deliberately not called here -- `describe_position`
answers `null` for `elevation`/`surface_type` until then.

`routes_path` is optional: a fresh checkout or CI environment will not have
the real 2.25 GB `Syria.routes` staged, and the roadnet layer degrading to
absent (with a logged skip in `BuildReport`) is the correct "absence
reported as absence" behaviour, not an error -- see `describe_position`'s
rule 3.
"""

import datetime
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from build.ingest_beacons import BeaconIngestStats, ingest_beacons
from build.ingest_osm import OsmIngestStats, ingest_osm
from build.ingest_roadnet import RoadnetIngestStats, ingest_roadnet
from build.ingest_towns import ingest_towns
from build.region import RegionDefinition
from dcs_data.beacons import parse_beacons_lua
from dcs_data.towns import parse_towns_lua
from osm.features import load_features
from store.models import Region, Source
from store.writer import insert_features, insert_region, insert_source, open_for_build


@dataclass
class BuildReport:
    """Summary of one `build_region` run -- feature counts by `kind`, plus
    each ingest module's own census, for the research note and for Stage
    0/1's "did the region actually get populated" sanity check."""

    feature_counts: Counter[str] = field(default_factory=Counter)
    beacon_stats: BeaconIngestStats | None = None
    osm_stats: OsmIngestStats | None = None
    roadnet_stats: RoadnetIngestStats | None = None
    roadnet_skipped: bool = False


def build_region(
    region: RegionDefinition,
    towns_lua_path: Path,
    beacons_lua_path: Path,
    osm_cache_path: Path,
    out_path: Path,
    routes_path: Path | None = None,
) -> BuildReport:
    """Build `out_path` from scratch for `region`, ingesting towns.lua,
    beacons.lua, the cached Overpass response and (if `routes_path` is given
    and exists) the DCS-native `.routes` roadnet layer. Returns a
    `BuildReport` with per-kind feature counts."""
    conn = open_for_build(out_path)
    try:
        built_at = datetime.datetime.now(datetime.UTC).isoformat()
        insert_region(
            conn,
            Region(
                name=region.name,
                theatre=region.theatre,
                centre_x=region.centre_x,
                centre_z=region.centre_z,
                half_extent_m=region.half_extent_m,
                built_at=built_at,
            ),
        )

        report = BuildReport()

        towns_source_id = insert_source(
            conn,
            Source(
                name="towns.lua",
                fetched_at=built_at,
                raw_path=str(towns_lua_path),
                attribution="DCS terrain module (Eagle Dynamics)",
                notes="Named-place gazetteer; see dcs_data.towns module docstring.",
            ),
        )
        towns = parse_towns_lua(towns_lua_path)
        town_features = ingest_towns(
            towns,
            region.theatre,
            region.centre_x,
            region.centre_z,
            region.half_extent_m,
            towns_source_id,
        )
        insert_features(conn, town_features)
        for f in town_features:
            report.feature_counts[f.kind] += 1

        beacons_source_id = insert_source(
            conn,
            Source(
                name="beacons.lua",
                fetched_at=built_at,
                raw_path=str(beacons_lua_path),
                attribution="DCS terrain module (Eagle Dynamics)",
                notes="Navaid/airfield-beacon gazetteer; see dcs_data.beacons module docstring.",
            ),
        )
        beacons = parse_beacons_lua(beacons_lua_path)
        beacon_features, beacon_stats = ingest_beacons(
            beacons,
            region.centre_x,
            region.centre_z,
            region.half_extent_m,
            beacons_source_id,
        )
        insert_features(conn, beacon_features)
        for f in beacon_features:
            report.feature_counts[f.kind] += 1
        report.beacon_stats = beacon_stats

        osm_source_id = insert_source(
            conn,
            Source(
                name="OpenStreetMap (Overpass)",
                fetched_at=built_at,
                raw_path=str(osm_cache_path),
                attribution="(c) OpenStreetMap contributors, ODbL",
                notes="Cached single Overpass fetch; see osm.overpass module docstring.",
            ),
        )
        feature_set = load_features(osm_cache_path)
        osm_features, osm_stats = ingest_osm(
            feature_set,
            region.theatre,
            region.centre_x,
            region.centre_z,
            region.half_extent_m,
            osm_source_id,
        )
        insert_features(conn, osm_features)
        for f in osm_features:
            report.feature_counts[f.kind] += 1
        report.osm_stats = osm_stats

        if routes_path is not None and routes_path.exists():
            roadnet_source_id = insert_source(
                conn,
                Source(
                    name="Syria.routes",
                    fetched_at=built_at,
                    raw_path=str(routes_path),
                    attribution="DCS terrain module (Eagle Dynamics)",
                    notes="Whole-theatre road centerline geometry; see "
                    "roadnet package docstring and "
                    "research/2026-09-04-m5-roadnet-byte-decode.md.",
                ),
            )
            road_features, roadnet_stats = ingest_roadnet(
                routes_path,
                region.centre_x,
                region.centre_z,
                region.half_extent_m,
                roadnet_source_id,
            )
            insert_features(conn, road_features)
            for f in road_features:
                report.feature_counts[f.kind] += 1
            report.roadnet_stats = roadnet_stats
        else:
            report.roadnet_skipped = True

        return report
    finally:
        conn.close()


def open_region_db(db_path: Path) -> sqlite3.Connection:
    """Open an already-built `.sqlite` read-only for querying."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
