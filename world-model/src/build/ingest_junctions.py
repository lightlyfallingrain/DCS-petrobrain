"""M10: `road` features (already inserted this same build) -> `junction`
`feature` rows.

Thin wrapper mirroring `ingest_terrain.py`'s shape -- pure ingest logic over
an already-loaded `list[StoredFeature]` (no store I/O beyond producing
`StoredFeature`s for the caller to insert), returning a small stats
dataclass for the build report / research note. `build/pipeline.py` supplies
`roads` via `store.reader.all_features(conn, ["road"])`, reading back what
the roadnet stage just inserted in the same open connection -- the same
read-back-what-was-just-written pattern M6's terrain stage already relies on
for the probe grid it just inserted (see the plan's "Risks & Unknowns").
"""

from dataclasses import dataclass

from roadnet.junctions import (
    DEFAULT_JUNCTION_MIN_DEGREE,
    DEFAULT_JUNCTION_TOLERANCE_M,
    extract_clusters,
    to_stored_features,
)
from store.models import StoredFeature


@dataclass
class JunctionIngestStats:
    """Census of one `ingest_junctions` run, for the research note and the
    "did anything actually get extracted" sanity check the earlier ingest
    stages already do (`RoadnetIngestStats`, `TerrainIngestStats`, ...)."""

    roads_scanned: int
    clusters_found: int
    junctions_kept: int
    degree_histogram: dict[int, int]


def ingest_junctions(
    roads: list[StoredFeature],
    source_id: int | None,
    tolerance_m: float = DEFAULT_JUNCTION_TOLERANCE_M,
    min_degree: int = DEFAULT_JUNCTION_MIN_DEGREE,
) -> tuple[list[StoredFeature], JunctionIngestStats]:
    """Cluster `roads`' endpoints/interior vertices and return `(StoredFeature
    rows, JunctionIngestStats)`. `source_id` is the roadnet layer's own
    `Source` row -- junction geometry is derived from that same `.routes`
    data, not a separate source."""
    clusters = extract_clusters(roads, tolerance_m=tolerance_m)
    features = to_stored_features(clusters, source_id, min_degree=min_degree)

    degree_histogram: dict[int, int] = {}
    for cluster in clusters:
        degree_histogram[cluster.degree] = degree_histogram.get(cluster.degree, 0) + 1

    stats = JunctionIngestStats(
        roads_scanned=len(roads),
        clusters_found=len(clusters),
        junctions_kept=len(features),
        degree_histogram=degree_histogram,
    )
    return features, stats
