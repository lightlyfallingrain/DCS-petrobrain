"""Tests for `build.ingest_junctions.ingest_junctions`: the wiring that turns
an already-loaded `list[StoredFeature]` of `road` rows into the
`(StoredFeature list, stats)` shape `build.pipeline.build_region` inserts.
This module tests wiring (tolerance/min-degree plumbing, stats bookkeeping,
empty-input behaviour), not the clustering/arm-counting algorithm itself,
which `test_junctions.py` already covers.
"""

from build.ingest_junctions import ingest_junctions
from store.models import StoredFeature


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


def test_ingest_junctions_produces_one_junction_feature() -> None:
    roads = [
        _road(1, [(0.0, 0.0), (100.0, 0.0)]),
        _road(2, [(0.0, 0.0), (-100.0, 0.0)]),
        _road(3, [(0.0, 0.0), (0.0, 100.0)]),
    ]

    features, stats = ingest_junctions(
        roads, source_id=5, tolerance_m=0.5, min_degree=3
    )

    assert len(features) == 1
    assert features[0].kind == "junction"
    assert features[0].source_id == 5
    assert stats.roads_scanned == 3
    assert stats.clusters_found == 1
    assert stats.junctions_kept == 1
    assert stats.degree_histogram == {3: 1}


def test_ingest_junctions_respects_min_degree() -> None:
    roads = [
        _road(1, [(0.0, 0.0), (100.0, 0.0)]),
        _road(2, [(0.0, 0.0), (-100.0, 0.0)]),
    ]

    features, stats = ingest_junctions(
        roads, source_id=5, tolerance_m=0.5, min_degree=3
    )

    assert features == []
    assert stats.clusters_found == 1
    assert stats.junctions_kept == 0
    # Clusters are still found even when none survives the degree filter --
    # min_degree only prunes emitted features, not clustering.
    assert stats.degree_histogram == {2: 1}


def test_ingest_junctions_empty_input() -> None:
    features, stats = ingest_junctions([], source_id=None)

    assert features == []
    assert stats.roads_scanned == 0
    assert stats.clusters_found == 0
    assert stats.junctions_kept == 0
    assert stats.degree_histogram == {}
