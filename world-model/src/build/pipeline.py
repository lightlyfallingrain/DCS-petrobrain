"""`build_region`: assembles one region's `.sqlite` from `data/raw/` sources.

Idempotent -- `open_for_build` deletes and recreates the target `.sqlite` on
every call, per the concept doc's "keep raw separate from derived so the
database can be rebuilt". M5 Stage 1 wired in towns, beacons and OSM; Stage
2 added the DCS-native roadnet layer (`.routes` walk -> `road` features,
`provenance["geometry"] == "dcs"`); Stage 3 adds the elevation/surface-type
probe grid (`build.ingest_probe`).

`routes_path` and `probe_output_path` are both optional: a fresh checkout or
CI environment will not have the real 2.25 GB `Syria.routes` or a live
probe's output staged, and each layer degrading to absent (with a logged
skip in `BuildReport`) is the correct "absence reported as absence"
behaviour, not an error -- see `describe_position`'s rule 3.
"""

import datetime
import logging
import sqlite3
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from build.ingest_beacons import BeaconIngestStats, ingest_beacons
from build.ingest_osm import OsmIngestStats, ingest_osm
from build.ingest_probe import ProbeIngestStats, ingest_probe
from build.ingest_roadnet import RoadnetIngestStats, ingest_roadnet
from build.ingest_terrain import TerrainIngestStats, ingest_terrain
from build.ingest_towns import ingest_towns
from build.region import RegionDefinition
from dcs_data.beacons import parse_beacons_lua
from dcs_data.towns import parse_towns_lua
from elevation.dem import SrtmTile
from osm.features import load_features
from store.models import Region, Source
from store.reader import load_full_grid
from store.writer import (
    insert_features,
    insert_grid,
    insert_region,
    insert_source,
    open_for_build,
)

_PROBE_GRID_SPACING_M = 500.0
_TOTAL_STAGES = 6

logger = logging.getLogger(__name__)


@contextmanager
def _stage(name: str, index: int) -> Iterator[None]:
    """Log start/end of one build stage with a coarse `n/N stages`
    completion estimate -- each stage is one raw-data source ingested, not
    weighted by how long it actually takes (roadnet dwarfs everything else),
    so this is "which stage" visibility, not a time-remaining estimate."""
    logger.info("[%d/%d] %s: starting", index, _TOTAL_STAGES, name)
    started_at = time.monotonic()
    yield
    elapsed_s = time.monotonic() - started_at
    logger.info("[%d/%d] %s: done (%.1fs)", index, _TOTAL_STAGES, name, elapsed_s)


def probe_grid_for_region(
    region: RegionDefinition, spacing_m: float = _PROBE_GRID_SPACING_M
) -> tuple[float, float, float, int, int]:
    """Derive `(origin_x, origin_z, spacing_m, n_rows, n_cols)` for the
    Stage 3 probe grid: a regular grid covering the whole region square at
    `spacing_m` spacing, `origin` at the region's south-west corner (row 0 /
    col 0). For M5's 10,000 m half-extent / 500 m spacing this is 41x41 =
    1,681 points, matching the checklist's locked grid decision."""
    n = round(2 * region.half_extent_m / spacing_m) + 1
    origin_x = region.centre_x - region.half_extent_m
    origin_z = region.centre_z - region.half_extent_m
    return origin_x, origin_z, spacing_m, n, n


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
    probe_stats: ProbeIngestStats | None = None
    probe_skipped: bool = False
    terrain_stats: TerrainIngestStats | None = None
    terrain_skipped: bool = False


def build_region(
    region: RegionDefinition,
    towns_lua_path: Path,
    beacons_lua_path: Path,
    osm_cache_path: Path,
    out_path: Path,
    routes_path: Path | None = None,
    probe_output_path: Path | None = None,
    srtm_tile_path: Path | None = None,
) -> BuildReport:
    """Build `out_path` from scratch for `region`, ingesting towns.lua,
    beacons.lua, the cached Overpass response, (if `routes_path` is given
    and exists) the DCS-native `.routes` roadnet layer, and (if
    `probe_output_path` is given and exists) the elevation/surface-type
    probe grid. `srtm_tile_path`, if given, adds an SRTM delta summary to
    the elevation grid's metadata (see `ingest_probe`'s module docstring --
    stats only, never stored samples). Returns a `BuildReport` with per-kind
    feature counts."""
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
        with _stage("towns.lua", 1):
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
        with _stage("beacons.lua", 2):
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
        with _stage("OSM overlay", 3):
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
            with _stage(f"Syria.routes ({routes_path.stat().st_size} bytes)", 4):
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

        if probe_output_path is not None and probe_output_path.exists():
            probe_source_id = insert_source(
                conn,
                Source(
                    name="terrain_probe (land.getHeight + land.getSurfaceType)",
                    fetched_at=built_at,
                    raw_path=str(probe_output_path),
                    attribution="DCS live mission-scripting probe (Eagle Dynamics)",
                    notes="Elevation + surface-type sample grid; see "
                    "build.ingest_probe module docstring and "
                    "tools/dcs-mission-probe/terrain_probe_full.lua.",
                ),
            )
            srtm_tile = (
                SrtmTile.from_file(srtm_tile_path)
                if srtm_tile_path is not None and srtm_tile_path.exists()
                else None
            )
            origin_x, origin_z, spacing_m, n_rows, n_cols = probe_grid_for_region(
                region
            )
            with _stage("elevation/surface probe grid", 5):
                elevation_grid, surface_grid, probe_stats = ingest_probe(
                    probe_output_path,
                    region.theatre,
                    origin_x,
                    origin_z,
                    spacing_m,
                    n_rows,
                    n_cols,
                    probe_source_id,
                    srtm_tile=srtm_tile,
                )
                insert_grid(conn, elevation_grid)
                insert_grid(conn, surface_grid)
                report.probe_stats = probe_stats

            with _stage("terrain semantics (ridge/valley)", 6):
                terrain_grid = load_full_grid(conn, "elevation")
                if terrain_grid is not None:
                    terrain_features, terrain_stats = ingest_terrain(
                        terrain_grid, probe_source_id
                    )
                    insert_features(conn, terrain_features)
                    for f in terrain_features:
                        report.feature_counts[f.kind] += 1
                    report.terrain_stats = terrain_stats
                else:
                    report.terrain_skipped = True
        else:
            report.probe_skipped = True
            report.terrain_skipped = True

        return report
    finally:
        conn.close()


def open_region_db(db_path: Path) -> sqlite3.Connection:
    """Open an already-built `.sqlite` read-only for querying."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
