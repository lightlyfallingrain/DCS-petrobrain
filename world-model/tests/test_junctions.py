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
    extract_clusters,
    to_stored_features,
)
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


# Filled in by Stage 2's real measurement run against `latakia-20km`'s 3,266
# real `road` features (6,496 endpoints, 155,900 interior vertices) at the
# default tolerance/min-degree -- see
# `plans/m10-road-junctions/implementation.md`. 346 clusters are degree-2
# (dropped as route continuation); 3,905 of 3,980 clusters are bit-exact
# (max intra-cluster distance < 1e-6 m).
_LATAKIA_CLUSTER_COUNT = 3980
_LATAKIA_JUNCTION_COUNT = 3634
