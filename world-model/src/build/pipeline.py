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

`osm_cache_path` is optional too (M7 Stage 1): M7's `syria-full` build has
no Overpass cache at all -- OSM is dropped from M7 scope entirely (see
`plans/m7-full-theatre-pipeline/plan.md` clarification 2), not merely
absent from a fresh checkout the way `routes_path`/`probe_output_path` can
be. A missing/absent OSM cache degrades the same way: skipped, reported in
`BuildReport.osm_skipped`, never an error.

`srtm_tile_paths` is M7 Stage 2's addition: SRTM as the region's *primary*
`elevation` grid (`build.ingest_srtm`, `provenance="srtm"`), run before the
pre-existing live-probe grid stage (`probe_output_path`,
`provenance="dcs_probe"`) so that a build supplying both still lets the
probe grid win as "most recent" for M6's ridge/valley classifier -- which
this pipeline does **not** run over an SRTM-sourced grid (M6 is locked out
of M7 entirely; see the plan's "Deferred / Out of Scope"). In practice a
real `syria-full` build supplies only `srtm_tile_paths`, since M7 repurposes
the live probe to a small spot-check validation set
(`build.validate.compare_probe_to_srtm`) rather than a stored full grid, so
this ordering concern does not arise for M7's own builds -- it exists only
so the two paths compose safely if ever used together.
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
from build.ingest_junctions import JunctionIngestStats, ingest_junctions
from build.ingest_osm import OsmIngestStats, ingest_osm
from build.ingest_probe import (
    ChunkProbeIngestStats,
    ProbeIngestStats,
    ingest_probe,
    ingest_probe_chunk,
)
from build.ingest_roadnet import RoadnetIngestStats, ingest_roadnet
from build.ingest_srtm import SrtmIngestStats, ingest_srtm_grid
from build.ingest_terrain import (
    TerrainIngestStats,
    ingest_terrain,
    ingest_terrain_chunk,
)
from build.ingest_towns import ingest_towns
from build.region import RegionDefinition
from dcs_data.beacons import parse_beacons_lua
from dcs_data.towns import parse_towns_lua
from elevation.dem import SrtmTile
from osm.features import load_features
from probe_store.models import ChunkStatus
from probe_store.paths import probe_store_path
from probe_store.reader import load_chunk_elevation_window
from probe_store.schema import PROBE_SPACING_M
from probe_store.writer import insert_source as insert_probe_source
from probe_store.writer import (
    open_probe_store,
    replace_chunk_features,
    upsert_chunk_coverage,
    upsert_grid_samples,
)
from roadnet.junctions import DEFAULT_JUNCTION_MIN_DEGREE, DEFAULT_JUNCTION_TOLERANCE_M
from store.chunks import CHUNK_SIZE_M
from store.models import Region, Source
from store.reader import all_features, load_full_grid, load_only_region
from store.schema import SCHEMA_VERSION as BASE_SCHEMA_VERSION
from store.schema import check_schema_version
from store.writer import (
    insert_features,
    insert_grid,
    insert_region,
    insert_source,
    open_for_build,
)
from terrain.curvature import DEFAULT_CURVATURE_THRESHOLD_M
from terrain.features import DEFAULT_MIN_CELL_COUNT

_PROBE_GRID_SPACING_M = 500.0
# Default storage spacing for the M7 Stage 2 SRTM-primary full-theatre
# elevation grid -- deliberately coarser than `_PROBE_GRID_SPACING_M`
# (SRTM's own native ~30-90m sampling density is unaffected; this only
# controls how many of those samples get stored as grid cells). At 500m,
# `syria-full`'s ~827x771 km padded bbox would be ~1,650 x 1,540 = ~2.5M
# grid cells; SQLite handles millions of rows fine per M5, but this is the
# first full-theatre-scale grid this pipeline has built, so the CLI exposes
# this as an override rather than hardcoding either number -- see
# `build.ingest_srtm`'s module docstring and
# `world-model/docs/M7_RUN_INSTRUCTIONS.md`'s Stage 2 section.
DEFAULT_SRTM_GRID_SPACING_M = 1000.0
_TOTAL_STAGES = 8

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
    Stage 3 probe grid: a regular grid covering the whole region rectangle
    at `spacing_m` spacing, `origin` at the region's south-west corner (row
    0 / col 0). `n_rows` spans the x half-extent and `n_cols` spans the z
    half-extent, matching `ElevationGrid`'s `(row, col)` -> `(origin_x + row
    * spacing_m, origin_z + col * spacing_m)` convention. For M5's square
    10,000 m half-extent / 500 m spacing this is 41x41 = 1,681 points,
    matching the checklist's locked grid decision; for a rectangular region
    `n_rows != n_cols` in general."""
    n_rows = round(2 * region.half_extent_x_m / spacing_m) + 1
    n_cols = round(2 * region.half_extent_z_m / spacing_m) + 1
    origin_x = region.centre_x - region.half_extent_x_m
    origin_z = region.centre_z - region.half_extent_z_m
    return origin_x, origin_z, spacing_m, n_rows, n_cols


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
    junction_stats: JunctionIngestStats | None = None
    junction_skipped: bool = False
    osm_skipped: bool = False
    probe_stats: ProbeIngestStats | None = None
    probe_skipped: bool = False
    terrain_stats: TerrainIngestStats | None = None
    terrain_skipped: bool = False
    srtm_stats: SrtmIngestStats | None = None
    srtm_skipped: bool = False


def build_region(
    region: RegionDefinition,
    towns_lua_path: Path,
    beacons_lua_path: Path,
    osm_cache_path: Path | None,
    out_path: Path,
    routes_path: Path | None = None,
    probe_output_path: Path | None = None,
    srtm_tile_path: Path | None = None,
    srtm_tile_paths: list[Path] | None = None,
    srtm_grid_spacing_m: float = DEFAULT_SRTM_GRID_SPACING_M,
    junction_tolerance_m: float = DEFAULT_JUNCTION_TOLERANCE_M,
    junction_min_degree: int = DEFAULT_JUNCTION_MIN_DEGREE,
) -> BuildReport:
    """Build `out_path` from scratch for `region`, ingesting towns.lua,
    beacons.lua, (if `osm_cache_path` is given and exists) the cached
    Overpass response, (if `routes_path` is given and exists) the
    DCS-native `.routes` roadnet layer, and (if `probe_output_path` is
    given and exists) the elevation/surface-type probe grid.
    `srtm_tile_path`, if given, adds an SRTM delta summary to the
    `probe_output_path` elevation grid's metadata (see `ingest_probe`'s
    module docstring -- stats only, never stored samples).

    `junction_tolerance_m`/`junction_min_degree` (M10) control the road-
    junction detection stage, which runs unconditionally whenever the
    roadnet stage actually ran (`not report.roadnet_skipped`) -- it needs no
    path parameter of its own because it reads back the `road` features that
    stage just inserted (`store.reader.all_features`), the same read-back
    pattern the terrain stage already uses for the probe grid it just wrote.
    See `roadnet.junctions`'s module docstring for the clustering/degree
    design and Stage 2's real-data validation numbers.

    `srtm_tile_paths` (M7 Stage 2), if given and non-empty, ingests SRTM as
    the region's **primary** `elevation` grid (`provenance="srtm"`,
    `build.ingest_srtm`), independent of `probe_output_path`/
    `srtm_tile_path` above -- this is the full-theatre path, not the
    single-tile delta-stats path. Stored at `srtm_grid_spacing_m` spacing
    over the same regular grid `probe_grid_for_region` derives for the
    probe grid. If both `srtm_tile_paths` and `probe_output_path` are given
    in the same build, both `elevation` grid rows get inserted; readers
    always see the most recently inserted one (`store.reader`'s
    `ORDER BY id DESC LIMIT 1`) -- for a real `syria-full` build only
    `srtm_tile_paths` is used (see the plan's Stage 2, which repurposes the
    live probe to spot-check validation rather than a stored grid), so this
    ambiguity does not arise in practice for M7's own builds. Returns a
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
                half_extent_x_m=region.half_extent_x_m,
                half_extent_z_m=region.half_extent_z_m,
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
                region.half_extent_x_m,
                region.half_extent_z_m,
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
                region.half_extent_x_m,
                region.half_extent_z_m,
                beacons_source_id,
            )
            insert_features(conn, beacon_features)
            for f in beacon_features:
                report.feature_counts[f.kind] += 1
            report.beacon_stats = beacon_stats

        if osm_cache_path is not None and osm_cache_path.exists():
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
                    region.half_extent_x_m,
                    region.half_extent_z_m,
                    osm_source_id,
                )
                insert_features(conn, osm_features)
                for f in osm_features:
                    report.feature_counts[f.kind] += 1
                report.osm_stats = osm_stats
        else:
            report.osm_skipped = True

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
                    region.half_extent_x_m,
                    region.half_extent_z_m,
                    roadnet_source_id,
                )
                insert_features(conn, road_features)
                for f in road_features:
                    report.feature_counts[f.kind] += 1
                report.roadnet_stats = roadnet_stats
        else:
            report.roadnet_skipped = True

        if not report.roadnet_skipped:
            with _stage("road junctions", 5):
                roads = all_features(conn, ["road"])
                junction_features, junction_stats = ingest_junctions(
                    roads,
                    roadnet_source_id,
                    tolerance_m=junction_tolerance_m,
                    min_degree=junction_min_degree,
                )
                insert_features(conn, junction_features)
                for f in junction_features:
                    report.feature_counts[f.kind] += 1
                report.junction_stats = junction_stats
        else:
            report.junction_skipped = True

        if srtm_tile_paths:
            existing_tile_paths = [p for p in srtm_tile_paths if p.exists()]
            if existing_tile_paths:
                srtm_source_id = insert_source(
                    conn,
                    Source(
                        name="SRTM .hgt tiles",
                        fetched_at=built_at,
                        raw_path=",".join(str(p) for p in existing_tile_paths),
                        attribution="SRTM (processed via viewfinderpanoramas.org "
                        "no-login mirror)",
                        notes="Primary full-theatre elevation source (M7 Stage 2); "
                        "see build.ingest_srtm module docstring.",
                    ),
                )
                tiles = [SrtmTile.from_file(p) for p in existing_tile_paths]
                srtm_origin_x, srtm_origin_z, _, srtm_n_rows, srtm_n_cols = (
                    probe_grid_for_region(region, spacing_m=srtm_grid_spacing_m)
                )
                with _stage(f"SRTM elevation grid ({len(tiles)} tile(s))", 6):
                    srtm_grid, srtm_stats = ingest_srtm_grid(
                        tiles,
                        region.theatre,
                        srtm_origin_x,
                        srtm_origin_z,
                        srtm_grid_spacing_m,
                        srtm_n_rows,
                        srtm_n_cols,
                        srtm_source_id,
                    )
                    insert_grid(conn, srtm_grid)
                    report.srtm_stats = srtm_stats
            else:
                report.srtm_skipped = True
        else:
            report.srtm_skipped = True

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
            with _stage("elevation/surface probe grid", 7):
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

            with _stage("terrain semantics (ridge/valley)", 8):
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


@dataclass
class ProbeChunkReport:
    """Summary of one `add_probe_chunk` call -- the M8 sibling of
    `BuildReport`, scoped to a single chunk rather than a whole region."""

    chunk_ix: int
    chunk_iz: int
    probe_stats: ChunkProbeIngestStats
    terrain_stats: TerrainIngestStats | None
    terrain_skipped: bool


def add_probe_chunk(
    base_db_path: Path,
    probe_output_path: Path,
    chunk_ix: int,
    chunk_iz: int,
    chunk_size_m: float = CHUNK_SIZE_M,
    probe_spacing_m: float = PROBE_SPACING_M,
    curvature_threshold_m: float = DEFAULT_CURVATURE_THRESHOLD_M,
    min_cell_count: int = DEFAULT_MIN_CELL_COUNT,
) -> ProbeChunkReport:
    """Ingest one chunk-scoped probe output file into `base_db_path`'s
    probe-tier sibling store (`probe_store.paths.probe_store_path`).

    Writes **only** to the probe store -- `base_db_path` is opened
    read-only, purely to read the region's `theatre` and confirm its own
    `SCHEMA_VERSION` is what this code expects (`store.schema.
    check_schema_version`), so the probe store's identity meta can be
    checked against it (`probe_store.writer.open_probe_store`'s
    drift-detection contract). `build_region`/the base `.sqlite` are never
    opened for write here -- see the plan's "Storage architecture: two
    stores" and its point-2 argument for why this split matters.

    Order of operations for chunk `(chunk_ix, chunk_iz)`:
    1. Parse `probe_output_path` into `(row, col) -> value` maps
       (`build.ingest_probe.ingest_probe_chunk`).
    2. If the chunk yielded no points at all, mark `elevation` and
       `surface_type` coverage `QUERIED_VOID` for this chunk and return --
       a real, meaningful outcome (see `probe_store.models.ChunkStatus`),
       not an error.
    3. Otherwise, upsert both grids' cells and mark both `QUERIED_WITH_DATA`.
    4. Load a local elevation window (chunk + 1-cell border,
       `probe_store.reader.load_chunk_elevation_window`) and run M6's
       ridge/valley classifier over it unchanged
       (`build.ingest_terrain.ingest_terrain_chunk`), replacing this
       chunk's `"ridge"`/`"valley"` features (and their own coverage)
       independently per kind.
    """
    base_conn = open_region_db(base_db_path)
    try:
        check_schema_version(base_conn)
        region = load_only_region(base_conn)
        if region is None:
            raise ValueError(f"{base_db_path} has no built region row")
        theatre = region.theatre
    finally:
        base_conn.close()

    probe_path = probe_store_path(base_db_path)
    probe_conn = open_probe_store(
        probe_path,
        theatre,
        BASE_SCHEMA_VERSION,
        chunk_size_m=chunk_size_m,
        probe_spacing_m=probe_spacing_m,
    )
    try:
        built_at = datetime.datetime.now(datetime.UTC).isoformat()
        probe_source_id = insert_probe_source(
            probe_conn,
            Source(
                name="terrain_probe chunk (land.getHeight + land.getSurfaceType)",
                fetched_at=built_at,
                raw_path=str(probe_output_path),
                attribution="DCS live mission-scripting probe (Eagle Dynamics)",
                notes=f"Chunk (ix={chunk_ix}, iz={chunk_iz}); see "
                "build.ingest_probe.ingest_probe_chunk module docstring.",
            ),
        )

        elevation_samples, surface_samples, probe_stats = ingest_probe_chunk(
            probe_output_path, chunk_ix, chunk_iz, chunk_size_m, probe_spacing_m
        )

        if not elevation_samples:
            upsert_chunk_coverage(
                probe_conn, "elevation", chunk_ix, chunk_iz, ChunkStatus.QUERIED_VOID
            )
            upsert_chunk_coverage(
                probe_conn, "surface_type", chunk_ix, chunk_iz, ChunkStatus.QUERIED_VOID
            )
            return ProbeChunkReport(
                chunk_ix=chunk_ix,
                chunk_iz=chunk_iz,
                probe_stats=probe_stats,
                terrain_stats=None,
                terrain_skipped=True,
            )

        upsert_grid_samples(
            probe_conn,
            "elevation",
            probe_spacing_m,
            elevation_samples,
            probe_source_id,
            "dcs_probe",
        )
        upsert_grid_samples(
            probe_conn,
            "surface_type",
            probe_spacing_m,
            surface_samples,
            probe_source_id,
            "dcs_probe",
        )
        upsert_chunk_coverage(
            probe_conn, "elevation", chunk_ix, chunk_iz, ChunkStatus.QUERIED_WITH_DATA
        )
        upsert_chunk_coverage(
            probe_conn,
            "surface_type",
            chunk_ix,
            chunk_iz,
            ChunkStatus.QUERIED_WITH_DATA,
        )

        window = load_chunk_elevation_window(
            probe_conn, chunk_ix, chunk_iz, chunk_size_m, probe_spacing_m
        )
        terrain_stats: TerrainIngestStats | None = None
        terrain_skipped = True
        if window is not None:
            features, terrain_stats = ingest_terrain_chunk(
                window, probe_source_id, curvature_threshold_m, min_cell_count
            )
            terrain_skipped = False
            ridge_features = [f for f in features if f.kind == "ridge"]
            valley_features = [f for f in features if f.kind == "valley"]
            replace_chunk_features(
                probe_conn, "ridge", chunk_ix, chunk_iz, ridge_features
            )
            replace_chunk_features(
                probe_conn, "valley", chunk_ix, chunk_iz, valley_features
            )
            upsert_chunk_coverage(
                probe_conn,
                "ridge",
                chunk_ix,
                chunk_iz,
                ChunkStatus.QUERIED_WITH_DATA
                if ridge_features
                else ChunkStatus.QUERIED_VOID,
            )
            upsert_chunk_coverage(
                probe_conn,
                "valley",
                chunk_ix,
                chunk_iz,
                ChunkStatus.QUERIED_WITH_DATA
                if valley_features
                else ChunkStatus.QUERIED_VOID,
            )

        return ProbeChunkReport(
            chunk_ix=chunk_ix,
            chunk_iz=chunk_iz,
            probe_stats=probe_stats,
            terrain_stats=terrain_stats,
            terrain_skipped=terrain_skipped,
        )
    finally:
        probe_conn.close()
