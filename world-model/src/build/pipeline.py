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

`osm_pbf_path` (M9) is an alternative OSM source: a pre-clipped,
pre-merged Geofabrik `.osm.pbf` extract, parsed with `osm.pbf.load_features`
instead of `osm.features.load_features`. When both `osm_pbf_path` and
`osm_cache_path` are given, `osm_pbf_path` wins -- it is the real-data path
this milestone exists for; `osm_cache_path` stays purely for continuity
with pre-M9 Overpass-cache-based builds/tooling. Downstream of the parse,
both paths are identical: the same `ingest_osm`/`OsmFeatureSet` shape, the
same `BuildReport.osm_stats`/`osm_skipped` fields (see
`plans/m9-osm-geofabrik/plan.md` Design Decision 3 -- nothing past the
parse needed to change).

`srtm_tile_paths` is M7 Stage 2's addition: SRTM as the region's *primary*
`elevation` grid (`build.ingest_srtm`, `provenance="srtm"`), run before the
pre-existing live-probe grid stage (`probe_output_path`,
`provenance="dcs_probe"`) so that a build supplying both still lets the
probe grid win as "most recent" for M6's ridge/valley classifier. **The
terrain-semantics stage now runs over whichever grid wins** -- SRTM alone,
or probe-over-SRTM when both are supplied -- per
`plans/terrain-feature-probing/plan.md` Stage 1; it used to run only
inside the probe branch, so an SRTM-only build (every real `syria-full`-
scale build) never reached it at all. In practice a real `syria-full`
build supplies only `srtm_tile_paths`, since M7 repurposes the live probe
to a small spot-check validation set
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
from dataclasses import dataclass, field, replace
from pathlib import Path

from build.ingest_beacons import BeaconIngestStats, ingest_beacons
from build.ingest_junctions import (
    JunctionIngestStats,
    ingest_junctions_streaming,
)
from build.ingest_osm import (
    CLASSIFIER_VERSION,
    OsmIngestStats,
    ingest_osm,
    ingest_osm_areas_batch,
    ingest_osm_nodes_batch,
    ingest_osm_ways_batch,
)
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
    tiles_for_region,
)
from build.ingest_towns import ingest_towns
from build.region import RegionDefinition
from dcs_data.beacons import parse_beacons_lua
from dcs_data.towns import parse_towns_lua
from elevation.dem import SrtmTile
from osm.features import OsmArea, OsmNode, OsmWay, load_features
from osm.pbf import stream_features as stream_features_from_pbf
from osm_cache.hashing import sha256_file
from osm_cache.models import OsmCacheMeta, cache_meta_matches
from osm_cache.paths import osm_cache_store_path, osm_cache_tmp_path
from osm_cache.reader import iter_cached_features, load_cache_meta, load_cached_stats
from osm_cache.schema import OSM_CACHE_SCHEMA_VERSION
from osm_cache.writer import (
    finalize_cache,
    insert_cached_features,
    open_osm_cache_for_populate,
)
from probe_store.models import ChunkStatus
from probe_store.paths import probe_store_path
from probe_store.schema import PROBE_SPACING_M
from probe_store.writer import insert_source as insert_probe_source
from probe_store.writer import (
    open_probe_store,
    upsert_chunk_coverage,
    upsert_grid_samples,
)
from roadnet.junctions import DEFAULT_JUNCTION_MIN_DEGREE, DEFAULT_JUNCTION_TOLERANCE_M
from store.chunks import CHUNK_SIZE_M
from store.models import Region, Source, StoredFeature
from store.reader import load_only_region
from store.schema import SCHEMA_VERSION as BASE_SCHEMA_VERSION
from store.schema import check_schema_version
from store.writer import (
    insert_features,
    insert_grid,
    insert_region,
    insert_source,
    open_for_build,
)
from terrain_cache.paths import terrain_cache_store_path

_PROBE_GRID_SPACING_M = 500.0
# Default storage spacing for the M7 Stage 2 SRTM-primary full-theatre
# elevation grid. Raised from the original 1000m to match
# `_PROBE_GRID_SPACING_M` (2026-09-29, plans/terrain-feature-probing/
# plan.md Stage 1/2): the user rejected 1000m for the terrain-semantics
# (ridge/valley) stage this grid now also feeds -- "an entire mountain can
# fit inside it" -- and a real sweep over `latakia-20km` SRTM data
# (`world-model/research/2026-09-29-terrain-feature-probing-spacing.md`)
# confirmed it empirically: at 1000m the curvature classifier both loses
# real secondary relief and never reproduces more than a handful of
# components at any workable threshold. 500m reproduces M6's own
# already-validated probe-grid tuning (the old per-cell discrete-Laplacian
# classifier's threshold, since removed -- see `terrain.curvature`'s
# current module docstring) almost exactly on real SRTM data, and the
# same sweep found no landmark-quality benefit from going finer (250m/100m
# still checkerboard at every threshold tested -- a resolution ceiling, not
# a threshold-tuning gap, matching M6's own finding). The marker-
# controlled-watershed mechanism that replaced that classifier (2026-10-01,
# `research/2026-10-01-terrain-feature-probing-watershed-sweep.md`)
# independently re-confirmed 500m for a mechanism-specific reason (finer
# spacing raises the absolute cell count the shared geometry-extraction
# step threads into a line, worsening its zigzag), rather than inheriting
# this note's finding blind. At 500m,
# `syria-full`'s ~827x771 km padded bbox is ~1,650 x 1,540 = ~2.5M grid
# cells; SQLite handles millions of rows fine per M5, and the stored
# `grid_sample` cost scales to roughly 49 MB (linear in cell count from the
# 1000m baseline's 12.2 MB) -- a modest, affordable increase, not a
# storage-cost concern. The CLI still exposes this as an override rather
# than hardcoding it -- see `build.ingest_srtm`'s module docstring and
# `world-model/docs/M7_RUN_INSTRUCTIONS.md`'s Stage 2 section.
DEFAULT_SRTM_GRID_SPACING_M = 500.0
_TOTAL_STAGES = 8

# How many `StoredFeature` rows `osm_pbf_path`'s cache-hit fast path reads
# from `<region>-osm-cache.sqlite` (and re-inserts via `store.writer.
# insert_features`) per batch -- deliberately the same order of magnitude as
# `osm.pbf._INGEST_BATCH_ELEMENTS`, so a cache-hit build commits to the base
# store in roughly the same number of transactions a cache-miss build does.
_OSM_CACHE_READ_BATCH_SIZE = 50_000

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
    osm_pbf_path: Path | None = None,
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
    stage just inserted, chunk by chunk
    (`build.ingest_junctions.ingest_junctions_streaming`, per
    `plans/junctions-streaming-fix/plan.md`), the same read-back pattern the
    terrain stage already uses for the probe grid it just wrote -- just
    bounded to one spatial tile's worth of features at a time rather than
    the whole `road` layer in one `store.reader.all_features` call, since a
    `syria-full`-scale combined DCS+OSM road layer OOM'd the old whole-layer
    approach. **osm-landcover-optimization**: this stage now sees DCS-sourced
    `road` features only -- no code change here (it still reads
    `kind="road"`), but `build.ingest_osm` no longer classifies anything as
    `road` at all (roads are dropped from OSM ingest entirely; DCS's own
    `.routes` layer is authoritative), so junction detection's candidate
    pool is smaller and single-provenance now. See `roadnet.junctions`'s
    module docstring for the clustering/degree design and Stage 2's
    real-data validation numbers (measured before this change, against a
    combined DCS+OSM road layer).

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
    ambiguity does not arise in practice for M7's own builds.

    `osm_pbf_path` (M9) takes precedence over `osm_cache_path` when both are
    given -- see the module docstring. It is a keyword-only-by-convention
    trailing parameter (added after `junction_min_degree`) rather than
    inserted next to `osm_cache_path`/`routes_path`, so it does not shift
    the positional slots `tools/build_world_model.py`'s existing positional
    call already relies on.

    Returns a `BuildReport` with per-kind feature counts."""
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
            towns = parse_towns_lua(towns_lua_path, region.theatre)
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
            beacons = parse_beacons_lua(beacons_lua_path, region.theatre)
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

        if osm_pbf_path is not None and osm_pbf_path.exists():
            osm_source_id = insert_source(
                conn,
                Source(
                    name="OpenStreetMap (Geofabrik .osm.pbf)",
                    fetched_at=built_at,
                    raw_path=str(osm_pbf_path),
                    attribution="(c) OpenStreetMap contributors, ODbL",
                    notes="Pre-clipped, pre-merged Geofabrik extract; see "
                    "osm.pbf module docstring and "
                    "docs/M9_OSM_RUN_INSTRUCTIONS.md.",
                ),
            )
            with _stage("OSM overlay (.osm.pbf)", 3):
                # M-osm-classified-cache: before parsing anything, check
                # whether a valid classified-feature cache already exists
                # for this exact `.osm.pbf` (by content hash, not path/mtime)
                # + classifier rules + cache schema + region bbox. On a hit,
                # skip the ~25-30+ minute pyosmium-parse-plus-`_classify_way`
                # pass entirely and copy pre-classified rows straight into
                # the fresh base store instead. See
                # `plans/osm-classified-cache/plan.md`.
                cache_path = osm_cache_store_path(out_path)
                cached_meta = load_cache_meta(cache_path)
                expected_meta = OsmCacheMeta(
                    pbf_sha256=sha256_file(osm_pbf_path),
                    pbf_size_bytes=osm_pbf_path.stat().st_size,
                    classifier_version=CLASSIFIER_VERSION,
                    cache_schema_version=OSM_CACHE_SCHEMA_VERSION,
                    region_name=region.name,
                    centre_x=region.centre_x,
                    centre_z=region.centre_z,
                    half_extent_x_m=region.half_extent_x_m,
                    half_extent_z_m=region.half_extent_z_m,
                    built_at=built_at,
                )

                if cached_meta is not None and cache_meta_matches(
                    cached_meta, expected_meta
                ):
                    logger.info(
                        "osm_cache: %s matches current .osm.pbf/classifier/"
                        "region -- serving OSM overlay from cache, skipping "
                        "the parse",
                        cache_path,
                    )
                    cache_conn = sqlite3.connect(f"file:{cache_path}?mode=ro", uri=True)
                    try:
                        osm_stats = load_cached_stats(cache_conn)
                        for batch in iter_cached_features(
                            cache_conn, _OSM_CACHE_READ_BATCH_SIZE
                        ):
                            retagged = [
                                replace(f, source_id=osm_source_id) for f in batch
                            ]
                            insert_features(conn, retagged)
                            for f in retagged:
                                report.feature_counts[f.kind] += 1
                    finally:
                        cache_conn.close()
                    report.osm_stats = osm_stats
                else:
                    # Cache miss (absent, or any invalidation-key field
                    # mismatched) -- streams the file in bounded batches
                    # rather than parsing it into one whole-file
                    # `OsmFeatureSet` first -- at `syria-full` scale (~8.6M
                    # ways kept) that reproduced a memory blowup severe
                    # enough to stall and require killing the run; see
                    # `plans/osm-streaming-ingest/plan.md`. Each batch's
                    # features are classified and committed immediately (a
                    # separate SQLite transaction per batch, not one atomic
                    # transaction for the whole stage) into one running
                    # `OsmIngestStats` shared by every batch. Safe because
                    # `open_for_build` always deletes-and-recreates
                    # `out_path` from scratch, so a crash mid-stage never
                    # leaves stale partial data mistaken for a complete
                    # build -- the next build overwrites the file entirely
                    # rather than resuming it.
                    #
                    # Every flushed batch is also written to the OSM cache
                    # under population at `tmp_path` -- one extra
                    # `insert_cached_features` call per batch, riding along
                    # on the one required pass over the file rather than a
                    # second pass, so a cache-miss build's cost is
                    # unchanged except for this write and the `sha256_file`
                    # read above.
                    osm_stats = OsmIngestStats()
                    tmp_path = osm_cache_tmp_path(out_path)
                    cache_populate_conn = open_osm_cache_for_populate(tmp_path)

                    def _flush_nodes(nodes: list[OsmNode]) -> None:
                        node_features = ingest_osm_nodes_batch(
                            nodes,
                            region.theatre,
                            region.centre_x,
                            region.centre_z,
                            region.half_extent_x_m,
                            region.half_extent_z_m,
                            osm_source_id,
                            osm_stats,
                        )
                        insert_features(conn, node_features)
                        insert_cached_features(cache_populate_conn, node_features)
                        for f in node_features:
                            report.feature_counts[f.kind] += 1

                    def _flush_ways(ways: list[OsmWay]) -> None:
                        way_features = ingest_osm_ways_batch(
                            ways,
                            region.theatre,
                            region.centre_x,
                            region.centre_z,
                            region.half_extent_x_m,
                            region.half_extent_z_m,
                            osm_source_id,
                            osm_stats,
                        )
                        insert_features(conn, way_features)
                        insert_cached_features(cache_populate_conn, way_features)
                        for f in way_features:
                            report.feature_counts[f.kind] += 1

                    def _flush_areas(areas: list[OsmArea]) -> None:
                        area_features = ingest_osm_areas_batch(
                            areas,
                            region.theatre,
                            region.centre_x,
                            region.centre_z,
                            region.half_extent_x_m,
                            region.half_extent_z_m,
                            osm_source_id,
                            osm_stats,
                        )
                        insert_features(conn, area_features)
                        insert_cached_features(cache_populate_conn, area_features)
                        for f in area_features:
                            report.feature_counts[f.kind] += 1

                    try:
                        result = stream_features_from_pbf(
                            osm_pbf_path, _flush_nodes, _flush_ways, _flush_areas
                        )
                        osm_stats.relations_skipped = result.relations_skipped
                        osm_stats.multipolygon_relations_seen = (
                            result.multipolygon_relations_seen
                        )
                        osm_stats.ways_skipped_unresolved_nodes = (
                            result.ways_skipped_unresolved_nodes
                        )
                        finalize_cache(
                            cache_populate_conn,
                            tmp_path,
                            cache_path,
                            expected_meta,
                            osm_stats,
                        )
                    except BaseException:
                        # `finalize_cache` never ran, so nothing exists yet
                        # at `cache_path` -- the next build correctly sees
                        # "no cache". Close the population connection so the
                        # abandoned `.tmp` file isn't left with an open
                        # handle; the file itself is disk-usage noise, not a
                        # correctness hazard (see `osm_cache.writer`'s
                        # module docstring).
                        cache_populate_conn.close()
                        raise
                    report.osm_stats = osm_stats
        elif osm_cache_path is not None and osm_cache_path.exists():
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
                    name=routes_path.name,
                    fetched_at=built_at,
                    raw_path=str(routes_path),
                    attribution="DCS terrain module (Eagle Dynamics)",
                    notes="Whole-theatre road centerline geometry; see "
                    "roadnet package docstring and "
                    "research/2026-09-04-m5-roadnet-byte-decode.md.",
                ),
            )
            with _stage(f"{routes_path.name} ({routes_path.stat().st_size} bytes)", 4):
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
                # Streams one chunk-of-`store.chunks.CHUNK_SIZE_M` at a time
                # rather than loading the whole `road` layer into memory --
                # see `build.ingest_junctions.ingest_junctions_streaming`'s
                # docstring and `plans/junctions-streaming-fix/plan.md`. Each
                # chunk's features are inserted (one SQLite transaction per
                # chunk, not one atomic transaction for the whole stage) into
                # one running `JunctionIngestStats` shared by every chunk --
                # safe for the same reason the OSM streaming fix's per-batch
                # commits are safe: `open_for_build` always
                # deletes-and-recreates `out_path` from scratch, so a crash
                # mid-stage just means the next build starts over, never a
                # stale-partial-data hazard.
                junction_stats = JunctionIngestStats(
                    roads_scanned=0,
                    clusters_found=0,
                    junctions_kept=0,
                    degree_histogram={},
                )
                for chunk_features in ingest_junctions_streaming(
                    conn,
                    region,
                    roadnet_source_id,
                    junction_stats,
                    tolerance_m=junction_tolerance_m,
                    min_degree=junction_min_degree,
                ):
                    insert_features(conn, chunk_features)
                    for f in chunk_features:
                        report.feature_counts[f.kind] += 1
                report.junction_stats = junction_stats
        else:
            report.junction_skipped = True

        # `elevation_source_id` tracks whichever `Source` row actually
        # produced the "elevation" grid the terrain-semantics stage below
        # will read back -- SRTM is inserted first, so a probe grid
        # inserted afterwards overwrites it as `store.reader`'s "most
        # recently inserted" `elevation` row, per this function's own
        # docstring on the two paths composing safely together. Tracked
        # here (rather than re-derived from `report.srtm_skipped`/
        # `probe_skipped`) so the terrain stage below attributes its
        # features to the grid it actually classified, not a guess.
        elevation_source_id: int | None = None

        # Captured once, ahead of the SRTM grid-insert block below, so the
        # terrain-semantics stage (further down) can gate on it directly
        # (plan design decision 1's "do not depend on the stored grid")
        # rather than re-deriving it from `elevation_source_id`.
        existing_srtm_tile_paths: list[Path] = (
            [p for p in srtm_tile_paths if p.exists()] if srtm_tile_paths else []
        )

        if srtm_tile_paths:
            if existing_srtm_tile_paths:
                srtm_source_id = insert_source(
                    conn,
                    Source(
                        name="SRTM .hgt tiles",
                        fetched_at=built_at,
                        raw_path=",".join(str(p) for p in existing_srtm_tile_paths),
                        attribution="SRTM (processed via viewfinderpanoramas.org "
                        "no-login mirror)",
                        notes="Primary full-theatre elevation source (M7 Stage 2); "
                        "see build.ingest_srtm module docstring.",
                    ),
                )
                tiles = [SrtmTile.from_file(p) for p in existing_srtm_tile_paths]
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
                    elevation_source_id = srtm_source_id
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
                elevation_source_id = probe_source_id
        else:
            report.probe_skipped = True

        # `landform-geomorphons` plan, design decision 1: gated on the
        # staged SRTM tiles directly, independent of whether an
        # "elevation" grid was ever inserted into the store -- this stage
        # resamples straight from the SRTM tile files itself (via
        # `build.ingest_terrain`'s own per-tile pipeline), it does not
        # read the stored grid at all. Only the tiles the region touches
        # (plus the neighbours feeding their processing-window margin) are
        # passed: `ingest_terrain` extracts across each given tile's whole
        # extent, so every other staged tile is time spent on terrain
        # outside the region -- see `tiles_for_region`.
        terrain_tile_paths = tiles_for_region(existing_srtm_tile_paths, region)
        if existing_srtm_tile_paths:
            logger.info(
                "terrain semantics: %d of %d staged tile(s) touch the region",
                len(terrain_tile_paths),
                len(existing_srtm_tile_paths),
            )
        if terrain_tile_paths:
            with _stage(
                f"terrain semantics (ridge/valley), {len(terrain_tile_paths)} tile(s)",
                8,
            ):

                def _flush_terrain_tile(tile_features: list[StoredFeature]) -> None:
                    # One `insert_features` call (one SQLite transaction)
                    # per tile, not one call over the whole theatre's
                    # features -- `ingest_terrain`'s own docstring and
                    # `plans/landform-geomorphons/performance.md`'s
                    # blocking memory finding. Mirrors the OSM
                    # streaming-ingest `_flush_nodes`/`_flush_ways`/
                    # `_flush_areas` callbacks above: safe because
                    # `open_for_build` always deletes-and-recreates
                    # `out_path` from scratch, so a crash partway through
                    # this stage never leaves stale partial terrain data
                    # mistaken for a complete build -- the next build
                    # overwrites `out_path` entirely rather than resuming
                    # it. (The terrain *cache* at `terrain_cache_store_
                    # path` is the one place resumption is meaningful, and
                    # it already tracks per-tile completion independently
                    # of this store.)
                    insert_features(conn, tile_features)
                    for f in tile_features:
                        report.feature_counts[f.kind] += 1

                terrain_stats = ingest_terrain(
                    terrain_tile_paths,
                    region.theatre,
                    region,
                    terrain_cache_store_path(out_path),
                    elevation_source_id,
                    _flush_terrain_tile,
                )
                report.terrain_stats = terrain_stats
        else:
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

    **No chunk-scoped ridge/valley extraction any more.** The retired
    watershed mechanism's `ingest_terrain_chunk` ran M6's classifier over a
    chunk + 1-cell-border window; `landform-geomorphons` replaced it with a
    geomorphons mechanism whose own processing unit is a whole SRTM tile
    (with a multi-kilometre margin, see `build.ingest_terrain`'s module
    docstring), not a 5 km probe chunk, and that plan did not design a
    chunk-scoped variant (discovered while implementing this plan -- see
    `plans/landform-geomorphons/implementation.md`). `terrain_stats`/
    `terrain_skipped` are kept on `ProbeChunkReport` for shape
    compatibility but always come back `None`/`True` now; the old
    mechanism's own docstring already called the chunk-scoped case "an
    accepted, non-crashing degenerate case... not a regression to chase
    here", since a chunk this small routinely produced no features anyway.
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

        # No chunk-scoped ridge/valley extraction any more -- see this
        # function's own docstring.
        return ProbeChunkReport(
            chunk_ix=chunk_ix,
            chunk_iz=chunk_iz,
            probe_stats=probe_stats,
            terrain_stats=None,
            terrain_skipped=True,
        )
    finally:
        probe_conn.close()
