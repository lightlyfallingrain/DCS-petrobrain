"""Tests for `osm.pbf.load_features` against a tiny synthetic `.osm.pbf`.

The plan (`plans/m9-osm-geofabrik/plan.md`, Stage 2) called for a "tiny
committed fixture `.pbf`". This test instead **builds the fixture at test
time** with `osmium.SimpleWriter` (the same "pyosmium's own writer" option
the plan names) into `tmp_path`, rather than committing an opaque binary
blob to the repo: the fixture's exact node/way/tag content is then visible
directly in this file's diff, staying consistent with
`test_osm_features.py`'s "hardcode the fixture in the test module" pattern
for the Overpass-sourced parser one file over. Verified equivalent to a
real `osmium-tool`-built file by round-tripping through
`osmium.SimpleHandler` against the real `data/raw/osm/syria-260911.osm.pbf`
extract during implementation (13M nodes / 1.86M ways / 0 unresolved
way-nodes / 2,818 relations parsed cleanly).

Covers all four `build.ingest_osm._classify_way` rules (`highway`,
`waterway`, `landuse`, `place` on a way) plus a `place`+`name` node
(named_place candidate) and one `type=multipolygon` relation, so
`relations_skipped` stays exercised on the pbf path too.
"""

import tracemalloc
from pathlib import Path

import osmium
import pytest
from osmium.osm import mutable

from osm.features import OsmNode, OsmWay
from osm.pbf import load_features, stream_features

_TIMESTAMP = "2020-01-01T00:00:00Z"
_COMMON = {
    "version": 1,
    "visible": True,
    "changeset": 1,
    "timestamp": _TIMESTAMP,
    "uid": 1,
}


def _write_fixture(path: Path) -> None:
    writer = osmium.SimpleWriter(str(path))
    try:
        # Plain nodes used only for way geometry -- no tags, so
        # `_FeatureCollector.node` must not keep them.
        for node_id, lon, lat in [
            (1, 39.00, 36.00),
            (2, 39.01, 36.01),
            (3, 39.02, 36.02),
            (4, 39.03, 36.03),
            (5, 39.04, 36.04),
            (6, 39.05, 36.04),
            (7, 39.05, 36.05),
        ]:
            writer.add_node(
                mutable.Node(id=node_id, location=(lon, lat), tags={}, **_COMMON)
            )
        # A tagged node -- a named place candidate.
        writer.add_node(
            mutable.Node(
                id=9,
                location=(39.10, 36.10),
                tags={"place": "village", "name": "Testville"},
                **_COMMON,
            )
        )

        # `highway` -> road.
        writer.add_way(
            mutable.Way(
                id=100, nodes=[1, 2], tags={"highway": "residential"}, **_COMMON
            )
        )
        # `waterway` -> water.
        writer.add_way(
            mutable.Way(id=101, nodes=[3, 4], tags={"waterway": "stream"}, **_COMMON)
        )
        # `landuse`, closed -> settlement polygon.
        writer.add_way(
            mutable.Way(
                id=102, nodes=[5, 6, 7, 5], tags={"landuse": "residential"}, **_COMMON
            )
        )
        # An unclassified way -- no highway/waterway/natural/landuse/place tag.
        writer.add_way(
            mutable.Way(id=103, nodes=[1, 2], tags={"building": "yes"}, **_COMMON)
        )

        # A multipolygon relation -- explicit counted skip, never parsed
        # into geometry (Design Decision 5).
        writer.add_relation(
            mutable.Relation(
                id=200,
                members=[("w", 100, "outer")],
                tags={"type": "multipolygon"},
                **_COMMON,
            )
        )
    finally:
        writer.close()


@pytest.fixture
def fixture_pbf_path(tmp_path: Path) -> Path:
    path = tmp_path / "fixture.osm.pbf"
    _write_fixture(path)
    return path


def test_load_features_keeps_only_tagged_nodes(fixture_pbf_path: Path) -> None:
    feature_set = load_features(fixture_pbf_path)

    assert feature_set.nodes == [
        OsmNode(
            id=9,
            tags={"place": "village", "name": "Testville"},
            lat=36.10,
            lon=39.10,
        )
    ]


def test_load_features_parses_all_way_classification_rules(
    fixture_pbf_path: Path,
) -> None:
    feature_set = load_features(fixture_pbf_path)

    ways_by_id = {way.id: way for way in feature_set.ways}
    assert set(ways_by_id) == {100, 101, 102, 103}

    assert ways_by_id[100] == OsmWay(
        id=100,
        tags={"highway": "residential"},
        points=[(36.00, 39.00), (36.01, 39.01)],
    )
    assert ways_by_id[101] == OsmWay(
        id=101,
        tags={"waterway": "stream"},
        points=[(36.02, 39.02), (36.03, 39.03)],
    )
    assert ways_by_id[102] == OsmWay(
        id=102,
        tags={"landuse": "residential"},
        points=[(36.04, 39.04), (36.04, 39.05), (36.05, 39.05), (36.04, 39.04)],
    )
    # `_classify_way` rejects this one downstream (no highway/waterway/
    # natural/landuse/place tag), but `osm.pbf.load_features` itself parses
    # every way regardless of tags -- classification is `ingest_osm`'s job.
    assert ways_by_id[103] == OsmWay(
        id=103, tags={"building": "yes"}, points=[(36.00, 39.00), (36.01, 39.01)]
    )


def test_load_features_counts_relations_skipped(fixture_pbf_path: Path) -> None:
    feature_set = load_features(fixture_pbf_path)

    assert feature_set.relations_skipped == 1


def test_load_features_reports_zero_unresolved_ways_when_all_nodes_present(
    fixture_pbf_path: Path,
) -> None:
    feature_set = load_features(fixture_pbf_path)

    assert feature_set.ways_skipped_unresolved_nodes == 0


def _write_many_elements_fixture(path: Path, n_tagged_nodes: int, n_ways: int) -> None:
    """A fixture with `n_tagged_nodes` tagged (named-place) nodes and
    `n_ways` classified ways, each way with its own two-point geometry --
    large enough (relative to a small `batch_size`) to force multiple
    streaming flushes plus a leftover partial batch, unlike
    `_write_fixture`'s single-digit-element fixture above."""
    writer = osmium.SimpleWriter(str(path))
    try:
        next_node_id = 1
        for i in range(n_tagged_nodes):
            writer.add_node(
                mutable.Node(
                    id=next_node_id,
                    location=(39.0 + i * 0.0001, 36.0 + i * 0.0001),
                    tags={"place": "hamlet", "name": f"Place{i}"},
                    **_COMMON,
                )
            )
            next_node_id += 1

        for i in range(n_ways):
            a_id, b_id = next_node_id, next_node_id + 1
            next_node_id += 2
            writer.add_node(
                mutable.Node(
                    id=a_id,
                    location=(40.0 + i * 0.0001, 37.0),
                    tags={},
                    **_COMMON,
                )
            )
            writer.add_node(
                mutable.Node(
                    id=b_id,
                    location=(40.0 + i * 0.0001, 37.0001),
                    tags={},
                    **_COMMON,
                )
            )
            writer.add_way(
                mutable.Way(
                    id=1000 + i,
                    nodes=[a_id, b_id],
                    tags={"highway": "track"},
                    **_COMMON,
                )
            )
    finally:
        writer.close()


class TestStreamFeaturesChunking:
    def test_flushes_multiple_batches_and_never_exceeds_batch_size(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "many.osm.pbf"
        _write_many_elements_fixture(path, n_tagged_nodes=10, n_ways=10)

        node_batches: list[list[OsmNode]] = []
        way_batches: list[list[OsmWay]] = []
        relations_skipped, ways_skipped_unresolved_nodes = stream_features(
            path,
            node_batches.append,
            way_batches.append,
            batch_size=3,
        )

        assert len(node_batches) > 1
        assert len(way_batches) > 1
        assert all(len(batch) <= 3 for batch in node_batches)
        assert all(len(batch) <= 3 for batch in way_batches)
        assert sum(len(batch) for batch in node_batches) == 10
        assert sum(len(batch) for batch in way_batches) == 10
        assert relations_skipped == 0
        assert ways_skipped_unresolved_nodes == 0

    def test_leftover_partial_batch_is_flushed(self, tmp_path: Path) -> None:
        # 10 elements at batch_size=3 leaves a final partial batch of 1 --
        # must not be silently dropped.
        path = tmp_path / "many.osm.pbf"
        _write_many_elements_fixture(path, n_tagged_nodes=10, n_ways=10)

        nodes: list[OsmNode] = []
        ways: list[OsmWay] = []
        stream_features(path, nodes.extend, ways.extend, batch_size=3)

        assert len(nodes) == 10
        assert len(ways) == 10

    def test_streaming_matches_load_features_on_the_same_file(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "many.osm.pbf"
        _write_many_elements_fixture(path, n_tagged_nodes=10, n_ways=10)

        bulk = load_features(path)

        streamed_nodes: list[OsmNode] = []
        streamed_ways: list[OsmWay] = []
        relations_skipped, ways_skipped_unresolved_nodes = stream_features(
            path, streamed_nodes.extend, streamed_ways.extend, batch_size=3
        )

        assert streamed_nodes == bulk.nodes
        assert streamed_ways == bulk.ways
        assert relations_skipped == bulk.relations_skipped
        assert ways_skipped_unresolved_nodes == bulk.ways_skipped_unresolved_nodes


class TestStreamFeaturesMemoryBound:
    def test_peak_buffered_memory_is_bounded_by_batch_size_not_file_size(
        self, tmp_path: Path
    ) -> None:
        """The test that would have caught the M9-scale gap, scaled down:
        peak traced allocation for the node/way buffers should stay within a
        bound sized to `batch_size`, not grow with the fixture's total
        element count -- proving `stream_features` never holds more than one
        batch's worth of kept elements at a time."""
        path = tmp_path / "many.osm.pbf"
        n_elements = 3000
        _write_many_elements_fixture(path, n_tagged_nodes=n_elements, n_ways=n_elements)
        batch_size = 50

        peak_batch_len = 0

        def _on_nodes(batch: list[OsmNode]) -> None:
            nonlocal peak_batch_len
            peak_batch_len = max(peak_batch_len, len(batch))

        def _on_ways(batch: list[OsmWay]) -> None:
            nonlocal peak_batch_len
            peak_batch_len = max(peak_batch_len, len(batch))

        tracemalloc.start()
        try:
            stream_features(path, _on_nodes, _on_ways, batch_size=batch_size)
            _current, peak_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        # Never handed a batch larger than requested.
        assert peak_batch_len <= batch_size
        # A generous per-element byte budget (tags dict + coordinates), so
        # this bound scales with `batch_size` alone, not with `n_elements`
        # (6000 total kept elements at this fixture size) -- if buffering
        # were unbounded again, peak traced memory would scale with
        # `n_elements` instead and blow well past this bound.
        assert peak_bytes < batch_size * 5_000


@pytest.mark.skipif(
    not Path("data/raw/osm/syria-260911.osm.pbf").exists(),
    reason="requires the real gitignored data/raw/osm/syria-260911.osm.pbf extract",
)
def test_streaming_matches_bulk_load_on_real_syria_extract() -> None:
    """Real-data regression test (plan Step 5, second bullet): proves
    `stream_features`'s batch-accumulated totals exactly match
    `load_features`'s single-shot totals at real theatre scale, not just on
    a synthetic fixture. Gated on the real Geofabrik extract M9's own
    validation used -- gitignored, machine-local data (per
    `docs/M9_OSM_RUN_INSTRUCTIONS.md`'s cross-machine workflow), so this only
    runs where that file has been staged."""
    real_path = Path("data/raw/osm/syria-260911.osm.pbf")

    bulk = load_features(real_path)

    streamed_node_count = 0
    streamed_way_count = 0

    def _count_nodes(batch: list[OsmNode]) -> None:
        nonlocal streamed_node_count
        streamed_node_count += len(batch)

    def _count_ways(batch: list[OsmWay]) -> None:
        nonlocal streamed_way_count
        streamed_way_count += len(batch)

    relations_skipped, ways_skipped_unresolved_nodes = stream_features(
        real_path, _count_nodes, _count_ways
    )

    assert streamed_node_count == len(bulk.nodes)
    assert streamed_way_count == len(bulk.ways)
    assert relations_skipped == bulk.relations_skipped
    assert ways_skipped_unresolved_nodes == bulk.ways_skipped_unresolved_nodes


def test_load_features_counts_way_with_missing_node_as_unresolved(
    tmp_path: Path,
) -> None:
    """A way referencing a node id never written to the file -- the
    "dangling reference" failure mode `--strategy=smart` is meant to avoid
    at a clip boundary, but which `osm.pbf.load_features` must still handle
    as a counted skip rather than crash or silently drop (Design
    Decision 2)."""
    path = tmp_path / "dangling.osm.pbf"
    writer = osmium.SimpleWriter(str(path))
    try:
        writer.add_node(mutable.Node(id=1, location=(39.00, 36.00), tags={}, **_COMMON))
        # Node 999 is never written -- its location will be unresolved.
        writer.add_way(
            mutable.Way(id=100, nodes=[1, 999], tags={"highway": "track"}, **_COMMON)
        )
    finally:
        writer.close()

    feature_set = load_features(path)

    assert feature_set.ways == []
    assert feature_set.ways_skipped_unresolved_nodes == 1
