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

**`ingest_junctions_streaming` (junctions-streaming-fix)**: `ingest_junctions`
above bulk-loads the whole `road` layer via `all_features` before clustering
-- once M9's OSM ingest also emits `kind="road"`, a `syria-full`-scale
combined DCS+OSM road layer made this the confirmed cause of a silent OOM
kill right after roadnet ingest. `ingest_junctions_streaming` is the
bounded-memory replacement: it walks `store.chunks`'s theatre-anchored chunk
lattice and clusters one padded spatial tile at a time via
`roadnet.junctions.extract_clusters`'s new `vertex_bbox` filter, instead of
clustering the whole theatre's vertices in one pass. `ingest_junctions`
itself is left completely unchanged -- still the right choice for any
small-store caller that doesn't need chunking, and untouched by this fix.
"""

import logging
import sqlite3
import time
from collections.abc import Iterator
from dataclasses import dataclass

from build.region import RegionDefinition
from roadnet.junctions import (
    DEFAULT_JUNCTION_MIN_DEGREE,
    DEFAULT_JUNCTION_TOLERANCE_M,
    extract_clusters,
    to_stored_features,
)
from store.chunks import CHUNK_SIZE_M, Bbox, chunk_bounds, chunks_covering
from store.models import StoredFeature
from store.reader import count_features, feature_layer_bbox, features_in_bbox

# Padding applied to a chunk's own core bounds before querying/clustering,
# in metres. Correctness only requires padding_m >= tolerance_m (a pair of
# vertices can only ever union if both lie within tolerance_m of each
# other, so a halo of at least tolerance_m guarantees every possible union
# for a vertex in the chunk's core is seen). 10x plus a floor is generous
# headroom, not a measured number -- reasoned the same way the OSM
# streaming fix's own `_INGEST_BATCH_ELEMENTS` was (see
# `plans/junctions-streaming-fix/plan.md` "Risks & Unknowns"): costs nothing
# at `CHUNK_SIZE_M = 5000` scale, and the user should expect to re-tune this
# after watching a real `syria-full` run rather than treating it as final.
_MIN_PADDING_M = 10.0
_PADDING_MULTIPLE = 10.0

logger = logging.getLogger(__name__)

# How often the chunk loop below logs progress, in seconds. Time-based rather
# than every-N-chunks (cf. `build.ingest_srtm`'s row interval) because per-chunk
# cost varies by orders of magnitude between empty desert and dense city
# chunks; a fixed chunk count would log in bursts, then go silent for minutes
# -- which at `syria-full` scale is indistinguishable from a hang.
_PROGRESS_LOG_INTERVAL_S = 30.0


@dataclass
class JunctionIngestStats:
    """Census of one `ingest_junctions`/`ingest_junctions_streaming` run,
    for the research note and the "did anything actually get extracted"
    sanity check the earlier ingest stages already do (`RoadnetIngestStats`,
    `TerrainIngestStats`, ...)."""

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


def ingest_junctions_streaming(
    conn: sqlite3.Connection,
    region: RegionDefinition,
    source_id: int | None,
    stats: JunctionIngestStats,
    tolerance_m: float = DEFAULT_JUNCTION_TOLERANCE_M,
    min_degree: int = DEFAULT_JUNCTION_MIN_DEGREE,
    chunk_size_m: float = CHUNK_SIZE_M,
) -> Iterator[list[StoredFeature]]:
    """Bounded-memory replacement for `ingest_junctions`: walks
    `store.chunks.chunks_covering(...)` over the `road` layer's **actual
    stored extent** and, per chunk, queries only that chunk's padded
    neighbourhood (`store.reader.features_in_bbox`, R*Tree-pruned), clusters
    within that padded region via `roadnet.junctions.extract_clusters`'s
    `vertex_bbox` filter, keeps only the resulting clusters whose
    **centroid** falls inside the chunk's own unpadded core bounds, and
    yields that chunk's `StoredFeature` rows. A generator, not a list -- the
    caller (`build.pipeline`) is expected to `insert_features` each yielded
    batch immediately rather than collecting every chunk's output before
    writing anything.

    **Chunk coverage is derived from `store.reader.feature_layer_bbox`, not
    from `region`'s own nominal rectangle -- a deliberate deviation from
    this function's original plan, discovered while validating this fix
    against the real `latakia-20km` store.** `build.ingest_roadnet`'s own
    docstring says a route with *any* point inside the built region's bbox
    is stored with its full, unclipped geometry -- confirmed against
    `latakia-20km`, where a real `road` feature's vertices reach tens of
    kilometres outside that store's own 20km-square region. Walking chunks
    over `region`'s bbox alone would silently skip real, store-resident
    vertices (and the junctions they form) that lie outside it -- exactly
    the kind of silent gap this fix exists to prevent, just relocated from
    "whole layer in memory" to "whole layer never visited". `region` is
    still accepted (kept for signature/call-site symmetry with
    `ingest_junctions`-style stage functions and because a future caller may
    want it for logging/validation) but is not used to derive chunk bounds.

    **Ownership-by-centroid** is what makes per-tile clustering equivalent
    to one whole-layer pass: a cluster whose vertices straddle two chunks'
    padded regions is found (in full) by every chunk whose padding reaches
    it, but is *kept* by exactly one of them -- whichever chunk's unpadded
    core contains the cluster's centroid -- so it is never double-counted
    and never dropped. Padding (`>= tolerance_m` is the only correctness
    requirement) guarantees every chunk's padded region sees every vertex
    that could possibly union with something in its own core.

    `stats` is mutated in place (mirroring `build.ingest_osm`'s
    "caller-supplied stats object" convention for streaming/batched ingest)
    rather than returned, since the generator's own return value is used up
    by `yield`. The caller constructs an empty `JunctionIngestStats` first;
    `roads_scanned` is set once, up front, from `store.reader.count_features`
    -- not accumulated per chunk, since a road whose bbox overlaps more than
    one chunk's padded region would otherwise be counted more than once even
    though it is one road.

    **Known, accepted limitation** (not fixed here, not expected to matter
    for real road data -- see the plan's "Risks & Unknowns"): the underlying
    clustering is a transitive union-find, so a pathological chain of
    vertices each within `tolerance_m` of the next, strung out over a long
    physical path, could in principle produce a cluster whose spread exceeds
    the padding margin -- such a cluster could be found only partially by
    each chunk it straddles, and centroid-ownership could then drop or
    double-count it. This has never been observed in this project's real
    data (measured clusters are all near-zero-radius, including the one
    known false-positive population of coincident roads) and is not proven
    impossible; it is a carried-forward assumption, not a guarantee.
    """
    stats.roads_scanned = count_features(conn, ["road"])

    layer_bbox = feature_layer_bbox(conn, ["road"])
    if layer_bbox is None:
        return  # No `road` features at all -- nothing to chunk over.

    padding_m = max(tolerance_m * _PADDING_MULTIPLE, _MIN_PADDING_M)

    chunks = chunks_covering(layer_bbox, chunk_size_m)
    logger.info(
        "ingest_junctions: %d roads, %d chunks of %.0f m (padding %.0f m)",
        stats.roads_scanned,
        len(chunks),
        chunk_size_m,
        padding_m,
    )
    started_at = time.monotonic()
    last_logged_at = started_at

    for index, (ix, iz) in enumerate(chunks):
        now = time.monotonic()
        if index > 0 and now - last_logged_at >= _PROGRESS_LOG_INTERVAL_S:
            elapsed_s = now - started_at
            remaining_s = elapsed_s / index * (len(chunks) - index)
            logger.info(
                "ingest_junctions: chunk %d/%d (%.1f%%, %d junctions kept, "
                "%.0fs elapsed, ~%.0fs remaining)",
                index,
                len(chunks),
                100.0 * index / len(chunks),
                stats.junctions_kept,
                elapsed_s,
                remaining_s,
            )
            last_logged_at = now

        core = chunk_bounds(ix, iz, chunk_size_m)
        padded: Bbox = (
            core[0] - padding_m,
            core[1] + padding_m,
            core[2] - padding_m,
            core[3] + padding_m,
        )
        roads = features_in_bbox(conn, ["road"], padded)
        clusters = extract_clusters(roads, tolerance_m, vertex_bbox=padded)

        owned = [
            cluster
            for cluster in clusters
            if core[0] <= cluster.centroid[0] < core[1]
            and core[2] <= cluster.centroid[1] < core[3]
        ]
        features = to_stored_features(owned, source_id, min_degree=min_degree)

        stats.clusters_found += len(owned)
        stats.junctions_kept += len(features)
        for cluster in owned:
            stats.degree_histogram[cluster.degree] = (
                stats.degree_histogram.get(cluster.degree, 0) + 1
            )

        yield features
