"""`landform-geomorphons`: SRTM tile files -> geomorphons -> ridge/valley
`feature` rows, cached per tile. Replaces the retired marker-controlled-
watershed `ingest_terrain`/`ingest_terrain_chunk` (which took an
already-loaded `ElevationGrid`): this module owns the whole per-tile
pipeline itself -- resample -> classify -> mask -> close -> thin -> trace
-> clip-to-core -> smooth -> wrap -- including the cache check/write and
progress logging, per `plans/landform-geomorphons/plan.md`.

One SRTM `.hgt` tile (1x1 degree) is one processing window, independent of
whatever region a caller is building (plan design decision 2): a window
covers its tile's own footprint plus a `margin_cells`-cell margin pulled
from neighbouring tiles (via `terrain.resample.sample_tiles_bilinear`
reading the whole `tiles` list, not just the one being processed), so
classification/thinning near a tile edge sees real context on both sides.
After tracing, every line is clipped to its own tile's `is_core` region
(`_split_core_segments`) -- a real ridge crossing a tile boundary is
stored as two touching `LineString` rows, a feature-identity
discontinuity accepted elsewhere in this codebase (M10 junction
splitting, the watershed mechanism's own basin-boundary fragmentation),
not a positional one.
"""

import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import numpy.typing as npt

from build.region import RegionDefinition
from coordinates import dcs_to_wgs84_array, wgs84_to_dcs
from elevation.dem import SrtmTile
from store.models import StoredFeature
from terrain.features import (
    DEFAULT_CHAIKIN_ITERATIONS,
    TerrainComponent,
    component_from_trace,
    to_stored_features,
)
from terrain.geomorphons import (
    DEFAULT_FLAT_DEG,
    DEFAULT_LOOKUP_CELLS,
    RIDGE_KINDS,
    VALLEY_KINDS,
    geomorphons,
)
from terrain.resample import lattice_coords, sample_tiles_bilinear
from terrain.skeleton import (
    DEFAULT_CLOSE_ITERATIONS,
    DEFAULT_MAX_TURN_COS,
    DEFAULT_MIN_LINE_LENGTH_CELLS,
    close_and_thin,
    family_mask,
    trace,
)
from terrain_cache.hashing import combined_tile_hash
from terrain_cache.models import TerrainCacheMeta, cache_meta_matches
from terrain_cache.reader import (
    completed_tile_ids,
    is_build_complete,
    load_cache_meta,
    load_tile_features,
)
from terrain_cache.schema import TERRAIN_CACHE_SCHEMA_VERSION
from terrain_cache.writer import (
    mark_build_complete,
    open_terrain_cache,
    reset_terrain_cache,
    write_meta,
    write_tile_features,
)

logger = logging.getLogger(__name__)

# Bump whenever a change to this module's own pipeline (not a knob value,
# which `TerrainCacheMeta` already tracks individually) would change a
# cache's output for the same inputs/knobs -- mirrors `osm_cache`'s
# `classifier_version` convention.
EXTRACTOR_VERSION = 1

# Matches SRTM3's nominal resolution (plan design decision 1).
DEFAULT_SPACING_M = 90.0

# ~1.8 km at the default spacing -- comfortably above the geomorphons
# `lookup_cells` floor, with room for the 3x3 closing/thinning
# neighbourhood (plan design decision 2).
DEFAULT_MARGIN_CELLS = 20

# How often the per-tile loop logs progress -- every tile, since a tile's
# own vectorised pass is fast enough that sub-tile progress isn't needed
# (plan's "Progress logging and resumability" section).
_PROGRESS_LOG_INTERVAL_TILES = 1


@dataclass
class TerrainIngestStats:
    """Census of one `ingest_terrain` run."""

    tiles_total: int
    tiles_cache_hit: int
    tiles_processed: int
    ridge_feature_count: int
    valley_feature_count: int


def _tile_dcs_bbox(
    theatre: str, sw_lat: float, sw_lon: float, span_deg: float
) -> tuple[float, float, float, float]:
    """`(min_x, max_x, min_z, max_z)`: the DCS x/z bounding box of a
    lat/lon tile, sampled at a 5x5 grid across its extent rather than just
    its 4 corners -- a projected lat/lon square's edges bow slightly under
    `tmerc`, and this sizes a processing window, not a per-cell
    classification (that uses the real per-cell lat/lon, not this
    approximation)."""
    fracs = (0.0, 0.25, 0.5, 0.75, 1.0)
    xs: list[float] = []
    zs: list[float] = []
    for frac_lat in fracs:
        for frac_lon in fracs:
            x, z = wgs84_to_dcs(
                theatre, sw_lat + frac_lat * span_deg, sw_lon + frac_lon * span_deg
            )
            xs.append(x)
            zs.append(z)
    return min(xs), max(xs), min(zs), max(zs)


def _split_core_segments(
    cells: list[tuple[int, int]],
    is_core: npt.NDArray[np.bool_],
    min_cells: int,
) -> list[list[tuple[int, int]]]:
    """Split `cells` (one traced line's `(row, col)` path) at every point
    it crosses from `is_core` to not, keeping only the core-side runs of
    at least `min_cells` cells -- plan design decision 2's "clip, don't
    merge" seam handling."""
    segments: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    for row, col in cells:
        if is_core[row, col]:
            current.append((row, col))
        else:
            if len(current) >= min_cells:
                segments.append(current)
            current = []
    if len(current) >= min_cells:
        segments.append(current)
    return segments


def _process_tile(
    tile: SrtmTile,
    all_tiles: list[SrtmTile],
    theatre: str,
    spacing_m: float,
    margin_cells: int,
    lookup_cells: int,
    flat_deg: float,
    close_iterations: int,
    max_turn_cos: float,
    min_line_length_cells: int,
    chaikin_iterations: int,
) -> list[StoredFeature]:
    """The whole per-tile pipeline (module docstring), returning
    cache-ready `StoredFeature`s (`source_id=None` -- the caller retags
    before storing, since a cache outlives any one build's `source_id`,
    same convention `osm_cache` uses)."""
    min_x, max_x, min_z, max_z = _tile_dcs_bbox(
        theatre, tile.sw_lat, tile.sw_lon, tile.span_deg
    )
    margin_m = margin_cells * spacing_m
    origin_x = math.floor((min_x - margin_m) / spacing_m) * spacing_m
    origin_z = math.floor((min_z - margin_m) / spacing_m) * spacing_m
    n_rows = math.ceil((max_x + margin_m - origin_x) / spacing_m) + 1
    n_cols = math.ceil((max_z + margin_m - origin_z) / spacing_m) + 1

    xx, zz = lattice_coords(origin_x, origin_z, spacing_m, n_rows, n_cols)
    lat, lon = dcs_to_wgs84_array(theatre, xx, zz)
    dem = sample_tiles_bilinear(all_tiles, lat, lon)

    north_lat = tile.sw_lat + tile.span_deg
    east_lon = tile.sw_lon + tile.span_deg
    is_core = (
        (lat >= tile.sw_lat)
        & (lat < north_lat)
        & (lon >= tile.sw_lon)
        & (lon < east_lon)
    )

    classes = geomorphons(dem, spacing_m, lookup_cells=lookup_cells, flat_deg=flat_deg)

    components: list[TerrainComponent] = []
    for kind, kinds in (("ridge", RIDGE_KINDS), ("valley", VALLEY_KINDS)):
        mask = family_mask(classes, kinds)
        skeleton = close_and_thin(mask, close_iterations=close_iterations)
        lines = trace(
            skeleton, min_cells=min_line_length_cells, max_turn_cos=max_turn_cos
        )
        for cells in lines:
            for segment in _split_core_segments(cells, is_core, min_line_length_cells):
                components.append(
                    component_from_trace(
                        kind, segment, dem, origin_x, origin_z, spacing_m
                    )
                )

    return to_stored_features(
        components, source_id=None, position_uncertainty_m=spacing_m
    )


def ingest_terrain(
    srtm_tile_paths: list[Path],
    theatre: str,
    region: RegionDefinition,
    cache_path: Path,
    source_id: int | None,
    on_tile_features: Callable[[list[StoredFeature]], None],
    spacing_m: float = DEFAULT_SPACING_M,
    margin_cells: int = DEFAULT_MARGIN_CELLS,
    lookup_cells: int = DEFAULT_LOOKUP_CELLS,
    flat_deg: float = DEFAULT_FLAT_DEG,
    close_iterations: int = DEFAULT_CLOSE_ITERATIONS,
    max_turn_cos: float = DEFAULT_MAX_TURN_COS,
    min_line_length_cells: int = DEFAULT_MIN_LINE_LENGTH_CELLS,
    chaikin_iterations: int = DEFAULT_CHAIKIN_ITERATIONS,
) -> TerrainIngestStats:
    """Extract ridge/valley `StoredFeature`s from `srtm_tile_paths`
    (existing paths only -- a missing path is silently skipped, same
    "absence reported as absence" convention every other ingest module
    uses), cached per tile at `cache_path` (see `terrain_cache/`).

    `region` identifies the cache (name + bbox), it does **not** clip the
    extracted geometry -- a tile is its own processing window regardless
    of which region's build supplied it (plan design decision 2). A
    region-scoped build therefore stores whatever ridge/valley lines its
    given tile(s) produce across their *whole* tile extent, not just the
    region's own smaller bbox; see `plans/landform-geomorphons/
    implementation.md` for why this is left unaddressed rather than
    designed here.

    `source_id` is this build's own elevation `Source` row -- cache rows
    carry no `source_id` (a cache outlives any one build), so every tile's
    features are retagged with it here, cache hit or not, before being
    handed to `on_tile_features`.

    This function **does not accumulate or return the whole theatre's
    features** -- `on_tile_features` is called once per tile (cache hit or
    freshly processed) with that one tile's retagged `StoredFeature`s, and
    the caller is expected to insert/flush them immediately (mirroring
    `build.pipeline`'s OSM streaming-ingest `_flush_nodes`/`_flush_ways`/
    `_flush_areas` callback pattern). A theatre's worth of features held in
    one Python list measured ~22 KB/feature and reached an estimated
    29 GB+ peak RSS extrapolated to a full Syria build
    (`plans/landform-geomorphons/performance.md`'s blocking finding) --
    the per-tile cache this module already writes to proves per-tile
    granularity is a safe, resumable unit, so this streams inserts at that
    same granularity instead of behind one theatre-wide list. Peak memory
    is now bounded by the largest single tile's own feature set, not by
    cumulative theatre feature count.
    """
    started_at = time.monotonic()
    existing_paths = [p for p in srtm_tile_paths if p.exists()]
    tiles = [SrtmTile.from_file(p) for p in existing_paths]
    tile_ids = [p.stem for p in existing_paths]
    n_tiles = len(existing_paths)

    expected_meta = TerrainCacheMeta(
        dem_identity=combined_tile_hash(existing_paths),
        extractor_version=EXTRACTOR_VERSION,
        cache_schema_version=TERRAIN_CACHE_SCHEMA_VERSION,
        region_name=region.name,
        centre_x=region.centre_x,
        centre_z=region.centre_z,
        half_extent_x_m=region.half_extent_x_m,
        half_extent_z_m=region.half_extent_z_m,
        spacing_m=spacing_m,
        margin_cells=margin_cells,
        lookup_cells=lookup_cells,
        flat_deg=flat_deg,
        close_iterations=close_iterations,
        max_turn_cos=max_turn_cos,
        min_line_length_cells=min_line_length_cells,
        chaikin_iterations=chaikin_iterations,
        built_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )

    conn = open_terrain_cache(cache_path)
    stored_meta = load_cache_meta(conn)
    if stored_meta is None or not cache_meta_matches(stored_meta, expected_meta):
        conn.close()
        conn = reset_terrain_cache(cache_path)
        write_meta(conn, expected_meta)

    # A whole-build cache hit is handled by the same per-tile loop as a
    # fresh/resumed build (not a separate `load_all_features` fast path --
    # that call materialised every cached feature across the entire
    # theatre into one list, the same unbounded-accumulation shape this
    # fix removes from the fresh-build path, just hit on a warm rebuild
    # instead). Treating every tile as "already complete" here reuses the
    # one cache-hit branch below, so a warm rebuild is bounded by one
    # tile's features at a time too.
    whole_build_cache_hit = n_tiles > 0 and is_build_complete(conn)
    already_complete = (
        set(tile_ids) if whole_build_cache_hit else completed_tile_ids(conn)
    )

    cache_hit_tiles = 0
    processed_tiles = 0
    ridge_feature_count = 0
    valley_feature_count = 0

    for index, (tile_id, tile) in enumerate(zip(tile_ids, tiles, strict=True)):
        if tile_id in already_complete:
            tile_features = load_tile_features(conn, tile_id)
            cache_hit_tiles += 1
            status = "cache hit"
        else:
            tile_features = _process_tile(
                tile,
                tiles,
                theatre,
                spacing_m,
                margin_cells,
                lookup_cells,
                flat_deg,
                close_iterations,
                max_turn_cos,
                min_line_length_cells,
                chaikin_iterations,
            )
            write_tile_features(conn, tile_id, tile_features)
            processed_tiles += 1
            status = "processed"

        retagged = [replace(f, source_id=source_id) for f in tile_features]
        ridge_feature_count += sum(1 for f in retagged if f.kind == "ridge")
        valley_feature_count += sum(1 for f in retagged if f.kind == "valley")
        on_tile_features(retagged)

        if index % _PROGRESS_LOG_INTERVAL_TILES == 0:
            logger.info(
                "ingest_terrain: tile %d/%d (%s, %.1f%%, %s, ridge=%d valley=%d, "
                "%.1fs elapsed)",
                index + 1,
                n_tiles,
                tile_id,
                100.0 * (index + 1) / n_tiles if n_tiles else 100.0,
                status,
                ridge_feature_count,
                valley_feature_count,
                time.monotonic() - started_at,
            )

    if n_tiles > 0 and not whole_build_cache_hit:
        mark_build_complete(conn)
    conn.close()

    return TerrainIngestStats(
        tiles_total=n_tiles,
        tiles_cache_hit=cache_hit_tiles,
        tiles_processed=processed_tiles,
        ridge_feature_count=ridge_feature_count,
        valley_feature_count=valley_feature_count,
    )
