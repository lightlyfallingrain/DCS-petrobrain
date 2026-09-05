"""M6: elevation grid -> ridge/valley `feature` rows.

Mirrors `build/ingest_probe.py`'s shape -- pure ingest logic over an
already-loaded `ElevationGrid` (no store I/O beyond producing
`StoredFeature`s for the caller to insert), returning a small stats
dataclass for the build report / research note. `build/pipeline.py` supplies
the grid via `store.reader.load_full_grid` after the probe grid has been
inserted (ridge/valley extraction needs the whole grid, not point samples).
"""

from dataclasses import dataclass

from store.models import ElevationGrid, StoredFeature
from terrain.curvature import (
    DEFAULT_CURVATURE_THRESHOLD_M,
    CurvatureClass,
    classify_curvature,
)
from terrain.features import (
    DEFAULT_MIN_CELL_COUNT,
    extract_components,
    to_stored_features,
)


@dataclass
class TerrainIngestStats:
    """Census of one `ingest_terrain` run, for the research note and the
    "did anything actually get extracted" sanity check the earlier ingest
    stages already do (`ProbeIngestStats`, `RoadnetIngestStats`, ...)."""

    cells_classified: int
    ridge_cell_count: int
    valley_cell_count: int
    ridge_feature_count: int
    valley_feature_count: int


def ingest_terrain(
    grid: ElevationGrid,
    source_id: int | None,
    curvature_threshold_m: float = DEFAULT_CURVATURE_THRESHOLD_M,
    min_cell_count: int = DEFAULT_MIN_CELL_COUNT,
) -> tuple[list[StoredFeature], TerrainIngestStats]:
    """Classify `grid`'s curvature, group into connected ridge/valley
    components, and return `(StoredFeature rows, TerrainIngestStats)`.
    `source_id` is the elevation probe's own `Source` row -- ridge/valley
    geometry is derived from that same probe grid, not a separate source."""
    curvature_cells = classify_curvature(grid, threshold_m=curvature_threshold_m)
    ridge_cell_count = sum(
        1 for c in curvature_cells if c.classification == CurvatureClass.RIDGE
    )
    valley_cell_count = sum(
        1 for c in curvature_cells if c.classification == CurvatureClass.VALLEY
    )

    components = extract_components(
        grid, curvature_cells, min_cell_count=min_cell_count
    )
    features = to_stored_features(
        components, source_id, position_uncertainty_m=grid.spacing_m
    )

    stats = TerrainIngestStats(
        cells_classified=len(curvature_cells),
        ridge_cell_count=ridge_cell_count,
        valley_cell_count=valley_cell_count,
        ridge_feature_count=sum(1 for f in features if f.kind == "ridge"),
        valley_feature_count=sum(1 for f in features if f.kind == "valley"),
    )
    return features, stats
