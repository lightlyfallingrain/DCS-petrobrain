"""M6/terrain-feature-probing: elevation grid -> ridge/valley `feature` rows.

Mirrors `build/ingest_probe.py`'s shape -- pure ingest logic over an
already-loaded `ElevationGrid` (no store I/O beyond producing
`StoredFeature`s for the caller to insert), returning a small stats
dataclass for the build report / research note. `build/pipeline.py` supplies
the grid via `store.reader.load_full_grid` after the probe grid has been
inserted (ridge/valley extraction needs the whole grid, not point samples).

Runs Stage 1's full Option C pipeline in order: `curvature.smooth_grid` ->
`curvature.find_basin_seeds` -> `features.grow_basins` -> `features.
extract_components` (which gates and extracts `qualifying_valleys`/
`qualifying_ridges`). See `plans/terrain-feature-probing/plan.md` for the
mechanism rationale.
"""

from dataclasses import dataclass

from store.models import ElevationGrid, StoredFeature
from terrain.curvature import (
    DEFAULT_SEED_FOOTPRINT_CELLS,
    DEFAULT_SMOOTHING_WINDOW_CELLS,
    find_basin_seeds,
    smooth_grid,
)
from terrain.features import (
    DEFAULT_MIN_CELL_COUNT,
    DEFAULT_RELIEF_THRESHOLD_M,
    DEFAULT_WIDTH_CEILING_M,
    extract_components,
    grow_basins,
    to_stored_features,
)


@dataclass
class TerrainIngestStats:
    """Census of one `ingest_terrain` run, for the research note and the
    "did anything actually get extracted" sanity check the earlier ingest
    stages already do (`ProbeIngestStats`, `RoadnetIngestStats`, ...)."""

    basin_count: int
    ridge_feature_count: int
    valley_feature_count: int


def ingest_terrain(
    grid: ElevationGrid,
    source_id: int | None,
    smoothing_window_cells: int = DEFAULT_SMOOTHING_WINDOW_CELLS,
    seed_footprint_cells: int = DEFAULT_SEED_FOOTPRINT_CELLS,
    relief_threshold_m: float = DEFAULT_RELIEF_THRESHOLD_M,
    width_ceiling_m: float = DEFAULT_WIDTH_CEILING_M,
    min_cell_count: int = DEFAULT_MIN_CELL_COUNT,
) -> tuple[list[StoredFeature], TerrainIngestStats]:
    """Smooth `grid`, seed and grow basins, gate them into ridge/valley
    components, and return `(StoredFeature rows, TerrainIngestStats)`.
    `source_id` is the elevation probe's own `Source` row -- ridge/valley
    geometry is derived from that same probe grid, not a separate source.
    """
    smoothed = smooth_grid(grid, window_cells=smoothing_window_cells)
    seeds = find_basin_seeds(smoothed, footprint_cells=seed_footprint_cells)
    labels, basins = grow_basins(smoothed, seeds)

    components = extract_components(
        smoothed,
        basins,
        labels,
        relief_threshold_m=relief_threshold_m,
        width_ceiling_m=width_ceiling_m,
        min_cell_count=min_cell_count,
    )
    features = to_stored_features(
        components, source_id, position_uncertainty_m=grid.spacing_m
    )

    stats = TerrainIngestStats(
        basin_count=len(basins),
        ridge_feature_count=sum(1 for f in features if f.kind == "ridge"),
        valley_feature_count=sum(1 for f in features if f.kind == "valley"),
    )
    return features, stats


def ingest_terrain_chunk(
    elevation_window: ElevationGrid,
    source_id: int | None,
    smoothing_window_cells: int = DEFAULT_SMOOTHING_WINDOW_CELLS,
    seed_footprint_cells: int = DEFAULT_SEED_FOOTPRINT_CELLS,
    relief_threshold_m: float = DEFAULT_RELIEF_THRESHOLD_M,
    width_ceiling_m: float = DEFAULT_WIDTH_CEILING_M,
    min_cell_count: int = DEFAULT_MIN_CELL_COUNT,
) -> tuple[list[StoredFeature], TerrainIngestStats]:
    """M8's chunk-scoped variant: identical pipeline to `ingest_terrain`,
    run over `elevation_window` -- a small local grid covering one chunk
    plus a 1-cell border (see `probe_store.reader.
    load_chunk_elevation_window`) rather than a whole-region grid.

    Not touched by this plan beyond staying call-compatible (`plans/
    terrain-feature-probing/plan.md`: "Not touched: world-model/src/
    probe_store/ (M8)") -- the watershed mechanism's smoothing/seeding
    windows are landform-scale, typically larger than one M8 chunk, so a
    chunk this small routinely grows a single basin with no qualifying
    divide and produces no features; that is an accepted, non-crashing
    degenerate case for infrastructure the plan notes "remains
    unexercised", not a regression to chase here.
    """
    return ingest_terrain(
        elevation_window,
        source_id,
        smoothing_window_cells,
        seed_footprint_cells,
        relief_threshold_m,
        width_ceiling_m,
        min_cell_count,
    )
