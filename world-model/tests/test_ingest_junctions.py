"""Tests for `build.ingest_junctions.ingest_junctions` and
`ingest_junctions_streaming`: the wiring that turns an already-loaded (or,
for the streaming path, store-resident) `list[StoredFeature]` of `road` rows
into the `(StoredFeature list, stats)` shape `build.pipeline.build_region`
inserts. This module tests wiring (tolerance/min-degree plumbing, stats
bookkeeping, empty-input behaviour, chunking correctness/memory bound), not
the clustering/arm-counting algorithm itself, which `test_junctions.py`
already covers.
"""

import datetime
import logging
import sqlite3
from pathlib import Path

import pytest

import build.ingest_junctions as ingest_junctions_module
from build.ingest_junctions import (
    JunctionIngestStats,
    ingest_junctions,
    ingest_junctions_streaming,
)
from build.region import RegionDefinition
from store.models import Region, StoredFeature
from store.reader import all_features
from store.writer import insert_features, insert_region, open_for_build


def _road(feature_id: int | None, geometry: list[tuple[float, float]]) -> StoredFeature:
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


def _build_store(tmp_path: Path, roads: list[StoredFeature]) -> Path:
    """Build a minimal on-disk store with one region and `roads` (no `id`
    set -- `insert_features` assigns real ids) already inserted, so
    `ingest_junctions_streaming` can query it via `features_in_bbox`."""
    db_path = tmp_path / "test.sqlite"
    conn = open_for_build(db_path)
    try:
        insert_region(
            conn,
            Region(
                name="test-region",
                theatre="test-theatre",
                centre_x=0.0,
                centre_z=0.0,
                half_extent_x_m=15000.0,
                half_extent_z_m=15000.0,
                built_at=datetime.datetime.now(datetime.UTC).isoformat(),
            ),
        )
        insert_features(conn, roads)
    finally:
        conn.close()
    return db_path


_TEST_REGION = RegionDefinition(
    theatre="test-theatre",
    name="test-region",
    centre_x=0.0,
    centre_z=0.0,
    half_extent_x_m=15000.0,
    half_extent_z_m=15000.0,
)


def _empty_stats() -> JunctionIngestStats:
    return JunctionIngestStats(
        roads_scanned=0, clusters_found=0, junctions_kept=0, degree_histogram={}
    )


def _content(f: StoredFeature) -> tuple[object, ...]:
    # `source_ref`/`id` deliberately excluded -- the streaming path assigns
    # indices/ids per chunk, not per the whole theatre, so they legitimately
    # differ from the bulk path's numbering for an identical junction.
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


def test_ingest_junctions_streaming_matches_bulk_across_chunk_boundary(
    tmp_path: Path,
) -> None:
    """A junction placed within padding distance of a chunk boundary (x =
    5000, `store.chunks.CHUNK_SIZE_M`) must be detected exactly once by the
    streaming path -- neither double-counted (each of the two adjoining
    chunks claiming it) nor dropped (both discarding it) -- and the overall
    streamed population must match the bulk path exactly."""
    roads = [
        # Interior-of-tile cluster, well inside chunk (0, 0).
        _road(None, [(1000.0, 1000.0), (1100.0, 1000.0)]),
        _road(None, [(1000.0, 1000.0), (900.0, 1000.0)]),
        _road(None, [(1000.0, 1000.0), (1000.0, 1100.0)]),
        # 3-way junction 2m from the x=5000 chunk boundary -- both chunk
        # (0, 0) and chunk (1, 0)'s padded regions see it.
        _road(None, [(4998.0, 2000.0), (4900.0, 2000.0)]),
        _road(None, [(4998.0, 2000.0), (5100.0, 2000.0)]),
        _road(None, [(4998.0, 2000.0), (4998.0, 2100.0)]),
    ]
    db_path = _build_store(tmp_path, roads)

    conn = sqlite3.connect(db_path)
    try:
        stored_roads = all_features(conn, ["road"])
        bulk_features, bulk_stats = ingest_junctions(
            stored_roads, source_id=None, tolerance_m=0.5, min_degree=3
        )

        streaming_stats = _empty_stats()
        streamed_features: list[StoredFeature] = []
        for chunk_features in ingest_junctions_streaming(
            conn,
            _TEST_REGION,
            None,
            streaming_stats,
            tolerance_m=0.5,
            min_degree=3,
        ):
            streamed_features.extend(chunk_features)
    finally:
        conn.close()

    assert sorted(streamed_features, key=_content) == sorted(
        bulk_features, key=_content
    )
    assert len(streamed_features) == 2  # both clusters kept, neither twice
    assert streaming_stats.roads_scanned == bulk_stats.roads_scanned == 6
    assert streaming_stats.clusters_found == bulk_stats.clusters_found == 2
    assert streaming_stats.junctions_kept == bulk_stats.junctions_kept == 2
    assert streaming_stats.degree_histogram == bulk_stats.degree_histogram


def _two_chunk_roads() -> list[StoredFeature]:
    # One 3-way junction straddling the x=5000 chunk boundary: the road
    # layer's bbox spans chunks (0, 0) and (1, 0), and nothing else.
    return [
        _road(None, [(4998.0, 2000.0), (4900.0, 2000.0)]),
        _road(None, [(4998.0, 2000.0), (5100.0, 2000.0)]),
        _road(None, [(4998.0, 2000.0), (4998.0, 2100.0)]),
    ]


def _drain_streaming(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        for _ in ingest_junctions_streaming(
            conn, _TEST_REGION, None, _empty_stats(), tolerance_m=0.5, min_degree=3
        ):
            pass
    finally:
        conn.close()


def test_ingest_junctions_streaming_logs_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """With the interval forced to zero, every chunk after the first logs a
    progress line; the up-front line reports the chunk total so a long
    `syria-full` run shows how far it has to go."""
    db_path = _build_store(tmp_path, _two_chunk_roads())
    monkeypatch.setattr(ingest_junctions_module, "_PROGRESS_LOG_INTERVAL_S", 0.0)

    with caplog.at_level(logging.INFO, logger="build.ingest_junctions"):
        _drain_streaming(db_path)

    messages = [r.getMessage() for r in caplog.records]
    assert any("3 roads, 2 chunks" in m for m in messages)
    assert any(m.startswith("ingest_junctions: chunk 1/2 (50.0%") for m in messages)


def test_ingest_junctions_streaming_progress_is_throttled(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """At the default interval a fast run logs only the up-front line, not a
    line per chunk."""
    db_path = _build_store(tmp_path, _two_chunk_roads())

    with caplog.at_level(logging.INFO, logger="build.ingest_junctions"):
        _drain_streaming(db_path)

    messages = [r.getMessage() for r in caplog.records]
    assert any("2 chunks" in m for m in messages)
    assert not any("ingest_junctions: chunk " in m for m in messages)


def test_ingest_junctions_streaming_empty_store(tmp_path: Path) -> None:
    db_path = _build_store(tmp_path, [])

    conn = sqlite3.connect(db_path)
    try:
        stats = _empty_stats()
        features = [
            f
            for chunk in ingest_junctions_streaming(conn, _TEST_REGION, None, stats)
            for f in chunk
        ]
    finally:
        conn.close()

    assert features == []
    assert stats.roads_scanned == 0
    assert stats.clusters_found == 0
    assert stats.junctions_kept == 0
    assert stats.degree_histogram == {}


def test_ingest_junctions_streaming_bounded_peak_roads_per_chunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Memory-bound validation: as the total road count grows across many
    widely-separated chunks, the number of roads returned to any single
    `features_in_bbox` call -- i.e. the peak simultaneously-resident road
    list -- must stay bounded to roughly one chunk's own content, not scale
    with the total. This is the direct proof of the fix: the old bulk path's
    peak was exactly the total road count. Asserted via a row-count proxy on
    `features_in_bbox` itself (not `tracemalloc`, whose byte counts carry
    enough unrelated-allocation noise to make a tight bound flaky) -- the
    row count is what actually determines peak `Vertex`-object memory."""
    n_clusters = 40
    roads: list[StoredFeature] = []
    # Spread clusters 20,000m apart (four chunk-widths) so no two clusters'
    # padded regions ever overlap, and each cluster is placed well inside
    # its own chunk's core (no boundary-straddling in this test).
    for i in range(n_clusters):
        cx = 1000.0 + i * 20000.0
        roads.append(_road(None, [(cx, 1000.0), (cx + 100.0, 1000.0)]))
        roads.append(_road(None, [(cx, 1000.0), (cx - 100.0, 1000.0)]))
        roads.append(_road(None, [(cx, 1000.0), (cx, 1100.0)]))

    db_path = _build_store(tmp_path, roads)

    region = RegionDefinition(
        theatre="test-theatre",
        name="test-region",
        centre_x=n_clusters * 10000.0,
        centre_z=0.0,
        half_extent_x_m=n_clusters * 10000.0 + 20000.0,
        half_extent_z_m=20000.0,
    )

    conn = sqlite3.connect(db_path)
    peak_roads_per_call = 0
    original_features_in_bbox = ingest_junctions_module.features_in_bbox

    def _tracking_features_in_bbox(
        c: object, kinds: object, bbox: object
    ) -> list[StoredFeature]:
        nonlocal peak_roads_per_call
        result = original_features_in_bbox(c, kinds, bbox)  # type: ignore[arg-type]
        peak_roads_per_call = max(peak_roads_per_call, len(result))
        return result

    monkeypatch.setattr(
        ingest_junctions_module, "features_in_bbox", _tracking_features_in_bbox
    )

    try:
        stats = _empty_stats()
        total_features = 0
        for chunk in ingest_junctions_streaming(
            conn, region, None, stats, tolerance_m=0.5, min_degree=3
        ):
            total_features += len(chunk)
    finally:
        conn.close()

    total_roads = len(roads)
    assert total_features == n_clusters
    # The key claim: peak roads seen by any single query call is bounded to
    # one cluster's own worth of roads (3, plus generous slack for
    # candidates whose bbox happens to overlap a padded tile edge), even
    # though total_roads scales linearly with n_clusters -- if the old
    # whole-layer `all_features` call were still in play, this would equal
    # total_roads instead.
    assert peak_roads_per_call <= 10
    assert peak_roads_per_call < total_roads
