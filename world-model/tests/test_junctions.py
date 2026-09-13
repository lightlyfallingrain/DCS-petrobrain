"""Tests for `roadnet.junctions`: grid-bucketed union-find clustering of
road endpoints/interior vertices and the arm-counting degree rule.

Synthetic fixtures per `plans/m10-road-junctions/plan.md`'s Stage 1 list: a
4-way endpoint cluster (kept), a 3-way endpoint cluster (kept), a plain
2-road endpoint coincidence (dropped -- route continuation), a T-junction
(endpoint-on-interior, kept), and a near-miss pair just outside tolerance
(not clustered). A real-data regression test against `latakia-20km` records
the actual cluster/junction counts this implementation produces there, per
Stage 2 -- skipped if that store is not present in this environment.
"""

import sqlite3
from pathlib import Path

import pytest

from roadnet.junctions import (
    DEFAULT_JUNCTION_MIN_DEGREE,
    DEFAULT_JUNCTION_TOLERANCE_M,
    collect_endpoints,
    collect_interior_vertices,
    extract_clusters,
    to_stored_features,
)
from store.chunks import chunk_bounds, chunks_covering
from store.models import StoredFeature

_TOLERANCE_M = 0.5

_LATAKIA_STORE_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "world-model"
    / "latakia-20km.sqlite"
)


def _road(feature_id: int, geometry: list[tuple[float, float]]) -> StoredFeature:
    return StoredFeature(
        id=feature_id,
        kind="road",
        geom_type="LineString",
        geometry=geometry,
        name=None,
        subtype=None,
        tags={},
        source_id=None,
        source_ref=None,
        provenance={"geometry": "dcs"},
        confidence={"geometry": "high"},
        position_uncertainty_m=0.0,
    )


def test_four_way_endpoint_cluster_is_kept() -> None:
    # Four separate roads, each with one endpoint exactly at the origin,
    # radiating outward -- a clean 4-way intersection, degree 4.
    roads = [
        _road(1, [(0.0, 0.0), (100.0, 0.0)]),
        _road(2, [(0.0, 0.0), (-100.0, 0.0)]),
        _road(3, [(0.0, 0.0), (0.0, 100.0)]),
        _road(4, [(0.0, 0.0), (0.0, -100.0)]),
    ]

    clusters = extract_clusters(roads, tolerance_m=_TOLERANCE_M)

    # Only the 4-way meeting at the origin is a cluster -- each road's own
    # far endpoint is 100m from every other vertex, so it never coincides
    # with anything and is not surfaced as a singleton "cluster".
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.centroid == (0.0, 0.0)
    assert cluster.degree == 4
    assert cluster.connecting_road_ids == [1, 2, 3, 4]
    assert cluster.max_intra_cluster_distance_m == pytest.approx(0.0)

    features = to_stored_features(clusters, source_id=None, min_degree=3)
    assert len(features) == 1
    assert features[0].kind == "junction"
    assert features[0].tags["degree"] == 4


def test_three_way_endpoint_cluster_is_kept() -> None:
    roads = [
        _road(1, [(0.0, 0.0), (100.0, 0.0)]),
        _road(2, [(0.0, 0.0), (-100.0, 0.0)]),
        _road(3, [(0.0, 0.0), (0.0, 100.0)]),
    ]

    clusters = extract_clusters(roads, tolerance_m=_TOLERANCE_M)

    assert len(clusters) == 1
    assert clusters[0].degree == 3

    features = to_stored_features(clusters, source_id=None, min_degree=3)
    assert len(features) == 1


def test_plain_two_road_endpoint_coincidence_is_dropped() -> None:
    # Two roads meeting end-to-end -- one physical road split into two
    # `.routes` polylines continuing through the same point, not a junction.
    roads = [
        _road(1, [(0.0, 0.0), (100.0, 0.0)]),
        _road(2, [(0.0, 0.0), (-100.0, 0.0)]),
    ]

    clusters = extract_clusters(roads, tolerance_m=_TOLERANCE_M)

    assert len(clusters) == 1
    assert clusters[0].degree == 2

    features = to_stored_features(clusters, source_id=None, min_degree=3)
    assert features == []


def test_t_junction_endpoint_on_interior_is_kept() -> None:
    # Road 1 runs straight through (0,0), with an interior vertex there.
    # Road 2's endpoint lands exactly on that interior vertex -- the
    # through-road contributes 2 arms, the branch contributes 1: degree 3,
    # even though only two distinct road ids are involved.
    roads = [
        _road(1, [(-100.0, 0.0), (0.0, 0.0), (100.0, 0.0)]),
        _road(2, [(0.0, 0.0), (0.0, 100.0)]),
    ]

    clusters = extract_clusters(roads, tolerance_m=_TOLERANCE_M)

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.degree == 3
    assert cluster.connecting_road_ids == [1, 2]

    features = to_stored_features(clusters, source_id=None, min_degree=3)
    assert len(features) == 1
    assert features[0].tags["degree"] == 3
    assert features[0].tags["connecting_road_ids"] == [1, 2]


def test_near_miss_pair_is_not_clustered() -> None:
    # Two roads' endpoints sit just outside tolerance_m of each other --
    # they must not be unioned into one cluster.
    gap = _TOLERANCE_M * 3.0
    roads = [
        _road(1, [(0.0, 0.0), (100.0, 0.0)]),
        _road(2, [(gap, 0.0), (-100.0, 0.0)]),
    ]

    clusters = extract_clusters(roads, tolerance_m=_TOLERANCE_M)

    # No vertex is within tolerance_m of any other, so no cluster forms at
    # all -- each endpoint is dropped as a non-coinciding singleton.
    assert clusters == []

    features = to_stored_features(clusters, source_id=None, min_degree=3)
    assert features == []


def test_vertex_bbox_none_matches_pre_fix_behaviour() -> None:
    # Default (no vertex_bbox) must be byte-for-byte identical to calling
    # the collectors with no filtering argument at all -- this is the
    # regression guarantee the whole junctions-streaming-fix plan depends
    # on for the existing bulk path.
    roads = [
        _road(1, [(0.0, 0.0), (100.0, 0.0)]),
        _road(2, [(0.0, 0.0), (-100.0, 0.0)]),
        _road(3, [(-50.0, 0.0), (0.0, 0.0), (50.0, 0.0)]),
    ]

    assert collect_endpoints(roads, vertex_bbox=None) == collect_endpoints(roads)
    assert collect_interior_vertices(
        roads, vertex_bbox=None
    ) == collect_interior_vertices(roads)
    assert extract_clusters(roads, tolerance_m=_TOLERANCE_M, vertex_bbox=None) == (
        extract_clusters(roads, tolerance_m=_TOLERANCE_M)
    )


def test_vertex_bbox_drops_vertex_outside_box() -> None:
    # A vertex outside vertex_bbox is dropped even though it would otherwise
    # cluster with another vertex.
    roads = [
        _road(1, [(0.0, 0.0), (100.0, 0.0)]),
        _road(2, [(0.0, 0.0), (-100.0, 0.0)]),
    ]

    # Box excludes the origin entirely -- neither endpoint at (0,0) survives.
    endpoints = collect_endpoints(roads, vertex_bbox=(10.0, 20.0, 10.0, 20.0))
    assert endpoints == []

    clusters = extract_clusters(
        roads, tolerance_m=_TOLERANCE_M, vertex_bbox=(10.0, 20.0, 10.0, 20.0)
    )
    assert clusters == []


def test_vertex_bbox_boundary_is_inclusive() -> None:
    # A vertex exactly on vertex_bbox's edge is kept (inclusive filtering) --
    # over-inclusion at a padded tile boundary is the safe direction; the
    # downstream centroid-ownership filter is what must be exact.
    roads = [_road(1, [(10.0, 0.0), (0.0, 0.0)])]

    endpoints = collect_endpoints(roads, vertex_bbox=(0.0, 10.0, 0.0, 10.0))
    assert len(endpoints) == 2  # both (10.0, 0.0) and (0.0, 0.0) kept

    interior_roads = [_road(1, [(-10.0, 0.0), (0.0, 0.0), (10.0, 0.0)])]
    interior = collect_interior_vertices(
        interior_roads, vertex_bbox=(0.0, 0.0, 0.0, 0.0)
    )
    assert len(interior) == 1  # the interior vertex sits exactly at (0,0)


def test_chunked_clustering_matches_monolithic_clustering() -> None:
    """Synthetic multi-chunk regression: roads placed across 3 distinct
    5000m-scale tiles, including one junction deliberately placed within
    padding distance of a tile boundary, must produce the exact same
    cluster set whether clustered in one monolithic pass or per-padded-tile
    with centroid-ownership filtering -- the correctness claim
    `build.ingest_junctions.ingest_junctions_streaming` depends on."""
    chunk_size_m = 5000.0
    tolerance_m = _TOLERANCE_M
    padding_m = max(tolerance_m * 10.0, 10.0)

    roads = [
        # Interior-of-tile 4-way junction, well inside chunk (0, 0).
        _road(1, [(1000.0, 1000.0), (1100.0, 1000.0)]),
        _road(2, [(1000.0, 1000.0), (900.0, 1000.0)]),
        _road(3, [(1000.0, 1000.0), (1000.0, 1100.0)]),
        _road(4, [(1000.0, 1000.0), (1000.0, 900.0)]),
        # A 3-way junction deliberately placed 2m from the x=5000 boundary
        # between chunk (0, 0) and chunk (1, 0) -- well within padding_m of
        # that boundary, so both chunks' padded regions see it, and only
        # centroid-ownership decides who keeps it.
        _road(5, [(4998.0, 2000.0), (4900.0, 2000.0)]),
        _road(6, [(4998.0, 2000.0), (5000.0 + 100.0, 2000.0)]),
        _road(7, [(4998.0, 2000.0), (4998.0, 2100.0)]),
        # Interior-of-tile junction far away in a third chunk (0, 2).
        _road(8, [(2000.0, 11000.0), (2100.0, 11000.0)]),
        _road(9, [(2000.0, 11000.0), (1900.0, 11000.0)]),
        _road(10, [(2000.0, 11000.0), (2000.0, 11100.0)]),
    ]

    monolithic = extract_clusters(roads, tolerance_m=tolerance_m)
    monolithic_centroids = sorted(c.centroid for c in monolithic)

    region_bbox = (0.0, 15000.0, 0.0, 15000.0)
    chunked_clusters = []
    for ix, iz in chunks_covering(region_bbox, chunk_size_m):
        core = chunk_bounds(ix, iz, chunk_size_m)
        padded = (
            core[0] - padding_m,
            core[1] + padding_m,
            core[2] - padding_m,
            core[3] + padding_m,
        )
        # `vertex_bbox` alone determines which vertices actually participate
        # in this tile's clustering -- no separate road-level pre-filter is
        # needed for this pure-geometry test (a real store query would add
        # one, `store.reader.features_in_bbox`, purely as an I/O
        # optimization that must not change the result).
        clusters = extract_clusters(roads, tolerance_m=tolerance_m, vertex_bbox=padded)
        owned = [
            c
            for c in clusters
            if core[0] <= c.centroid[0] < core[1] and core[2] <= c.centroid[1] < core[3]
        ]
        chunked_clusters.extend(owned)

    chunked_centroids = sorted(c.centroid for c in chunked_clusters)
    assert chunked_centroids == monolithic_centroids
    assert len(chunked_clusters) == 3
    assert len(monolithic) == 3
    assert sorted(c.degree for c in monolithic) == [3, 3, 4]
    assert sorted(c.degree for c in chunked_clusters) == [3, 3, 4]


def test_source_id_and_default_position_uncertainty_are_plumbed() -> None:
    roads = [
        _road(1, [(0.0, 0.0), (100.0, 0.0)]),
        _road(2, [(0.0, 0.0), (-100.0, 0.0)]),
        _road(3, [(0.0, 0.0), (0.0, 100.0)]),
    ]
    clusters = extract_clusters(roads, tolerance_m=_TOLERANCE_M)

    features = to_stored_features(clusters, source_id=42, min_degree=3)

    assert features[0].source_id == 42
    assert features[0].position_uncertainty_m == pytest.approx(0.0)
    assert features[0].provenance == {"geometry": "dcs_derived"}
    assert features[0].confidence == {"geometry": "high"}


@pytest.mark.skipif(
    not _LATAKIA_STORE_PATH.exists(),
    reason="latakia-20km.sqlite not present in this environment (gitignored "
    "world-model data) -- Stage 2's real-data regression baseline cannot be "
    "established here.",
)
def test_latakia_20km_regression_baseline() -> None:
    """Real-data regression baseline established in Stage 2 against the
    actual `latakia-20km` store's `road` layer -- see
    `plans/m10-road-junctions/implementation.md` for the measurement run
    this asserts against."""
    from store.reader import all_features

    conn = sqlite3.connect(f"file:{_LATAKIA_STORE_PATH}?mode=ro", uri=True)
    try:
        roads = all_features(conn, ["road"])
    finally:
        conn.close()

    clusters = extract_clusters(roads, tolerance_m=DEFAULT_JUNCTION_TOLERANCE_M)
    features = to_stored_features(
        clusters, source_id=None, min_degree=DEFAULT_JUNCTION_MIN_DEGREE
    )

    assert len(roads) == 3266
    assert len(clusters) == _LATAKIA_CLUSTER_COUNT
    assert len(features) == _LATAKIA_JUNCTION_COUNT


@pytest.mark.skipif(
    not _LATAKIA_STORE_PATH.exists(),
    reason="latakia-20km.sqlite not present in this environment (gitignored "
    "world-model data) -- the chunked-vs-bulk comparison cannot be "
    "established here.",
)
def test_latakia_20km_chunked_streaming_matches_bulk() -> None:
    """junctions-streaming-fix regression: the chunked streaming ingest path
    (`build.ingest_junctions.ingest_junctions_streaming`) must produce the
    exact same junction population as the bulk `ingest_junctions` path
    against real (if modest-scale) road geometry, not just a synthetic
    fixture."""
    from build.ingest_junctions import JunctionIngestStats, ingest_junctions_streaming
    from build.region import RegionDefinition
    from store.reader import all_features

    conn = sqlite3.connect(f"file:{_LATAKIA_STORE_PATH}?mode=ro", uri=True)
    try:
        # `latakia-20km.sqlite` is a pre-M7 fixture whose `region` table
        # predates the rectangular half_extent_x_m/half_extent_z_m schema
        # (still the single-column `half_extent_m` -- see
        # `store.reader.load_only_region`'s docstring/schema, which this
        # fixture no longer matches). Read the raw row directly rather than
        # via `load_only_region`, and treat it as the square region it is.
        theatre, centre_x, centre_z, half_extent_m = conn.execute(
            "SELECT theatre, centre_x, centre_z, half_extent_m FROM region LIMIT 1"
        ).fetchone()
        region = RegionDefinition.square(
            theatre=theatre,
            name="latakia-20km",
            centre_x=centre_x,
            centre_z=centre_z,
            half_extent_m=half_extent_m,
        )

        roads = all_features(conn, ["road"])
        bulk_clusters = extract_clusters(
            roads, tolerance_m=DEFAULT_JUNCTION_TOLERANCE_M
        )
        bulk_features = to_stored_features(
            bulk_clusters, source_id=None, min_degree=DEFAULT_JUNCTION_MIN_DEGREE
        )

        stats = JunctionIngestStats(
            roads_scanned=0, clusters_found=0, junctions_kept=0, degree_histogram={}
        )
        streamed_features: list[StoredFeature] = []
        for chunk_features in ingest_junctions_streaming(
            conn,
            region,
            None,
            stats,
            tolerance_m=DEFAULT_JUNCTION_TOLERANCE_M,
            min_degree=DEFAULT_JUNCTION_MIN_DEGREE,
        ):
            streamed_features.extend(chunk_features)
    finally:
        conn.close()

    def _content(f: StoredFeature) -> tuple[object, ...]:
        # `source_ref` (a per-batch "junction_{index}" label) and `id` are
        # deliberately excluded -- the streaming path assigns indices/ids
        # per chunk, not per the whole theatre, so they legitimately differ
        # from the bulk path's numbering even for an identical junction.
        return (
            f.kind,
            f.geom_type,
            f.geometry[0],
            f.tags["degree"],
            tuple(sorted(f.tags["connecting_road_ids"])),
            tuple(sorted(f.provenance.items())),
            tuple(sorted(f.confidence.items())),
            f.position_uncertainty_m,
        )

    streamed_content = sorted(_content(f) for f in streamed_features)
    bulk_content = sorted(_content(f) for f in bulk_features)
    assert streamed_content == bulk_content
    assert len(streamed_features) == len(bulk_features) == _LATAKIA_JUNCTION_COUNT
    assert stats.junctions_kept == _LATAKIA_JUNCTION_COUNT


# Filled in by Stage 2's real measurement run against `latakia-20km`'s 3,266
# real `road` features (6,496 endpoints, 155,900 interior vertices) at the
# default tolerance/min-degree -- see
# `plans/m10-road-junctions/implementation.md`. 346 clusters are degree-2
# (dropped as route continuation); 3,905 of 3,980 clusters are bit-exact
# (max intra-cluster distance < 1e-6 m).
_LATAKIA_CLUSTER_COUNT = 3980
_LATAKIA_JUNCTION_COUNT = 3634
