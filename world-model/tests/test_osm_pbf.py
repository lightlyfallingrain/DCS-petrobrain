"""Tests for `osm.pbf.load_features`/`stream_features` against a tiny
synthetic `.osm.pbf`.

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
extract during M9 implementation (13M nodes / 1.86M ways / 0 unresolved
way-nodes / 2,818 relations parsed cleanly).

**osm-landcover-optimization update**: `osm.pbf`'s `KeyFilter` now
restricts every element reaching `node()`/`way()`/`area()`/`relation()` to
`landuse`/`natural`/`place`/`waterway`/`water` keys -- fixture tags below
use only those keys (plus a couple of tags in an excluded key, `building`/
`amenity`/`highway`, specifically to prove `KeyFilter` drops them). This
covers the plan's Stage 1 test list: a closed landuse way producing both a
`way()` and an `area()` callback, a closed coastline way doing the same, a
two-piece multipolygon relation with an inner ring assembling into one area
with one hole, an untagged closed way (standalone, and as a multipolygon
member) producing no area, and `highway`/`building`-tagged ways never
reaching the Python callbacks at all.
"""

import tracemalloc
from pathlib import Path

import osmium
import pytest
from osmium.osm import mutable

from osm.features import OsmArea, OsmNode, OsmWay
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
        # --- Plain (untagged) nodes, purely for way geometry. ---
        plain_nodes = [
            # Landuse square (closed).
            (1, 39.00, 36.00),
            (2, 39.01, 36.00),
            (3, 39.01, 36.01),
            (4, 39.00, 36.01),
            # Waterway line (open).
            (11, 39.10, 36.00),
            (12, 39.11, 36.01),
            # Coastline island square (closed).
            (21, 39.20, 36.00),
            (22, 39.21, 36.00),
            (23, 39.21, 36.01),
            (24, 39.20, 36.01),
            # Standalone untagged closed way (no relation).
            (31, 39.30, 36.00),
            (32, 39.31, 36.00),
            (33, 39.31, 36.01),
            (34, 39.30, 36.01),
            # Multipolygon outer ring, two pieces.
            (41, 39.40, 36.00),
            (42, 39.41, 36.00),
            (43, 39.41, 36.01),
            (44, 39.40, 36.01),
            # Multipolygon inner ring (hole).
            (45, 39.404, 36.004),
            (46, 39.406, 36.004),
            (47, 39.406, 36.006),
            (48, 39.404, 36.006),
            # A second, standalone multipolygon-member way for the
            # `type=site` (not area-assembled) relation.
            (51, 39.50, 36.00),
            (52, 39.51, 36.00),
            (53, 39.51, 36.01),
            (54, 39.50, 36.01),
        ]
        for node_id, lon, lat in plain_nodes:
            writer.add_node(
                mutable.Node(id=node_id, location=(lon, lat), tags={}, **_COMMON)
            )

        # A tagged node -- a named place candidate (matches `place`).
        writer.add_node(
            mutable.Node(
                id=9,
                location=(39.90, 36.90),
                tags={"place": "village", "name": "Testville"},
                **_COMMON,
            )
        )
        # A tagged node whose only key (`amenity`) `KeyFilter` must drop.
        writer.add_node(
            mutable.Node(
                id=10,
                location=(39.91, 36.91),
                tags={"amenity": "school", "name": "School"},
                **_COMMON,
            )
        )

        # `landuse`, closed -> settlement-shaped area, and also a `way()` call.
        writer.add_way(
            mutable.Way(
                id=101,
                nodes=[1, 2, 3, 4, 1],
                tags={"landuse": "residential"},
                **_COMMON,
            )
        )
        # `waterway`, open -> line only, no area.
        writer.add_way(
            mutable.Way(id=102, nodes=[11, 12], tags={"waterway": "stream"}, **_COMMON)
        )
        # `natural=coastline`, closed (island) -> a line and an area (D1's
        # fixture-verified fact).
        writer.add_way(
            mutable.Way(
                id=103,
                nodes=[21, 22, 23, 24, 21],
                tags={"natural": "coastline"},
                **_COMMON,
            )
        )
        # `building` -- key excluded from `KeyFilter`; must never reach `way()`.
        writer.add_way(
            mutable.Way(id=104, nodes=[1, 2], tags={"building": "yes"}, **_COMMON)
        )
        # `highway` -- key excluded from `KeyFilter`; must never reach `way()`.
        writer.add_way(
            mutable.Way(
                id=105, nodes=[1, 2], tags={"highway": "residential"}, **_COMMON
            )
        )
        # Untagged, closed, standalone (not a relation member) -- must
        # reach neither `way()` nor `area()`.
        writer.add_way(
            mutable.Way(id=106, nodes=[31, 32, 33, 34, 31], tags={}, **_COMMON)
        )

        # Multipolygon relation: two untagged outer piece ways + one
        # untagged inner-ring way -> one area, one outer ring, one hole.
        writer.add_way(mutable.Way(id=200, nodes=[41, 42], tags={}, **_COMMON))
        writer.add_way(mutable.Way(id=201, nodes=[42, 43, 44, 41], tags={}, **_COMMON))
        writer.add_way(
            mutable.Way(id=202, nodes=[45, 46, 47, 48, 45], tags={}, **_COMMON)
        )
        writer.add_relation(
            mutable.Relation(
                id=300,
                members=[("w", 200, "outer"), ("w", 201, "outer"), ("w", 202, "inner")],
                tags={"type": "multipolygon", "natural": "wood"},
                **_COMMON,
            )
        )

        # A `type=site` relation whose own tags still pass `KeyFilter`
        # (`natural=wood`) but whose `type` libosmium's area manager does
        # not assemble -- a genuinely unsupported construct, counted
        # `relations_skipped`, not `multipolygon_relations_seen`.
        writer.add_way(
            mutable.Way(id=203, nodes=[51, 52, 53, 54, 51], tags={}, **_COMMON)
        )
        writer.add_relation(
            mutable.Relation(
                id=301,
                members=[("w", 203, "outer")],
                tags={"type": "site", "natural": "wood"},
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


def test_load_features_keeps_only_tagged_nodes_matching_filter_keys(
    fixture_pbf_path: Path,
) -> None:
    feature_set = load_features(fixture_pbf_path)

    assert feature_set.nodes == [
        OsmNode(
            id=9,
            tags={"place": "village", "name": "Testville"},
            lat=36.90,
            lon=39.90,
        )
    ]


def test_load_features_drops_ways_whose_key_is_not_in_the_filter(
    fixture_pbf_path: Path,
) -> None:
    feature_set = load_features(fixture_pbf_path)

    way_ids = {way.id for way in feature_set.ways}
    assert 104 not in way_ids  # building
    assert 105 not in way_ids  # highway


def test_load_features_drops_untagged_standalone_closed_way(
    fixture_pbf_path: Path,
) -> None:
    feature_set = load_features(fixture_pbf_path)

    way_ids = {way.id for way in feature_set.ways}
    area_ids = {area.id for area in feature_set.areas}
    assert 106 not in way_ids
    assert 106 not in area_ids


def test_load_features_parses_the_kept_way_geometry(fixture_pbf_path: Path) -> None:
    feature_set = load_features(fixture_pbf_path)

    ways_by_id = {way.id: way for way in feature_set.ways}
    assert set(ways_by_id) == {101, 102, 103}

    assert ways_by_id[101] == OsmWay(
        id=101,
        tags={"landuse": "residential"},
        points=[
            (36.00, 39.00),
            (36.00, 39.01),
            (36.01, 39.01),
            (36.01, 39.00),
            (36.00, 39.00),
        ],
    )
    assert ways_by_id[102] == OsmWay(
        id=102,
        tags={"waterway": "stream"},
        points=[(36.00, 39.10), (36.01, 39.11)],
    )
    assert ways_by_id[103] == OsmWay(
        id=103,
        tags={"natural": "coastline"},
        points=[
            (36.00, 39.20),
            (36.00, 39.21),
            (36.01, 39.21),
            (36.01, 39.20),
            (36.00, 39.20),
        ],
    )


def test_load_features_closed_landuse_way_also_produces_an_area(
    fixture_pbf_path: Path,
) -> None:
    feature_set = load_features(fixture_pbf_path)

    areas_by_id = {area.id: area for area in feature_set.areas}
    assert 101 in areas_by_id
    area = areas_by_id[101]
    assert area.from_way is True
    assert area.tags == {"landuse": "residential"}
    assert len(area.rings) == 1
    assert area.rings[0].inners == []
    assert area.rings[0].outer[0] == area.rings[0].outer[-1]  # closed
    assert len(area.rings[0].outer) == 5


def test_load_features_closed_coastline_way_also_produces_an_area(
    fixture_pbf_path: Path,
) -> None:
    feature_set = load_features(fixture_pbf_path)

    areas_by_id = {area.id: area for area in feature_set.areas}
    assert 103 in areas_by_id
    area = areas_by_id[103]
    assert area.from_way is True
    assert area.tags == {"natural": "coastline"}
    assert len(area.rings) == 1
    assert area.rings[0].inners == []


def test_load_features_open_way_produces_no_area(fixture_pbf_path: Path) -> None:
    feature_set = load_features(fixture_pbf_path)

    area_ids = {area.id for area in feature_set.areas}
    assert 102 not in area_ids


def test_load_features_multipolygon_relation_assembles_one_area_with_one_hole(
    fixture_pbf_path: Path,
) -> None:
    feature_set = load_features(fixture_pbf_path)

    areas_by_id = {area.id: area for area in feature_set.areas}
    assert 300 in areas_by_id
    area = areas_by_id[300]
    assert area.from_way is False
    # libosmium strips the relation's own `type` tag (role metadata, not a
    # feature tag) from the assembled area's tags.
    assert area.tags == {"natural": "wood"}
    assert len(area.rings) == 1
    ring = area.rings[0]
    assert ring.outer[0] == ring.outer[-1]  # the two outer pieces merged into one ring
    assert len(ring.inners) == 1
    assert ring.inners[0][0] == ring.inners[0][-1]  # the hole is closed too


def test_load_features_untagged_multipolygon_member_ways_are_not_kept_as_ways(
    fixture_pbf_path: Path,
) -> None:
    feature_set = load_features(fixture_pbf_path)

    way_ids = {way.id for way in feature_set.ways}
    assert not way_ids & {200, 201, 202}


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
            mutable.Way(id=100, nodes=[1, 999], tags={"waterway": "stream"}, **_COMMON)
        )
    finally:
        writer.close()

    feature_set = load_features(path)

    assert feature_set.ways == []
    assert feature_set.ways_skipped_unresolved_nodes == 1


class TestStreamFeaturesRelationCounts:
    def test_multipolygon_type_relation_counts_as_seen_not_skipped(
        self, fixture_pbf_path: Path
    ) -> None:
        nodes: list[OsmNode] = []
        ways: list[OsmWay] = []
        areas: list[OsmArea] = []
        result = stream_features(
            fixture_pbf_path, nodes.extend, ways.extend, areas.extend
        )

        assert result.multipolygon_relations_seen == 1
        assert result.relations_skipped == 1


def _write_many_elements_fixture(
    path: Path, n_tagged_nodes: int, n_ways: int, n_areas: int = 0
) -> None:
    """A fixture with `n_tagged_nodes` tagged (named-place) nodes,
    `n_ways` classified line ways (`waterway=stream`, matching `KeyFilter`),
    and `n_areas` classified closed-way areas (`landuse=residential`), each
    with its own geometry -- large enough (relative to a small `batch_size`)
    to force multiple streaming flushes plus a leftover partial batch,
    unlike `_write_fixture`'s single-digit-element fixture above."""
    writer = osmium.SimpleWriter(str(path))
    try:
        next_node_id = 1
        # A single monotonically-increasing id counter shared by every line
        # and area way below -- `osmium.SimpleWriter` requires way ids to be
        # written in strictly increasing order, so two independent
        # `1000 + i` / `2000 + i` counters (one per loop) can collide or go
        # out of order once `n_ways`/`n_areas` are large (as they are in
        # `TestStreamFeaturesMemoryBound`).
        next_way_id = 1_000_000

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
                    id=a_id, location=(40.0 + i * 0.0001, 37.0), tags={}, **_COMMON
                )
            )
            writer.add_node(
                mutable.Node(
                    id=b_id, location=(40.0 + i * 0.0001, 37.0001), tags={}, **_COMMON
                )
            )
            writer.add_way(
                mutable.Way(
                    id=next_way_id,
                    nodes=[a_id, b_id],
                    tags={"waterway": "stream"},
                    **_COMMON,
                )
            )
            next_way_id += 1

        for i in range(n_areas):
            corner_ids = [next_node_id + j for j in range(4)]
            next_node_id += 4
            base_lon, base_lat = 41.0 + i * 0.001, 38.0
            corners = [
                (base_lon, base_lat),
                (base_lon + 0.0001, base_lat),
                (base_lon + 0.0001, base_lat + 0.0001),
                (base_lon, base_lat + 0.0001),
            ]
            for node_id, (lon, lat) in zip(corner_ids, corners):
                writer.add_node(
                    mutable.Node(id=node_id, location=(lon, lat), tags={}, **_COMMON)
                )
            writer.add_way(
                mutable.Way(
                    id=next_way_id,
                    nodes=[*corner_ids, corner_ids[0]],
                    tags={"landuse": "residential"},
                    **_COMMON,
                )
            )
            next_way_id += 1
    finally:
        writer.close()


class TestStreamFeaturesChunking:
    def test_flushes_multiple_batches_and_never_exceeds_batch_size(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "many.osm.pbf"
        _write_many_elements_fixture(path, n_tagged_nodes=10, n_ways=10, n_areas=10)

        node_batches: list[list[OsmNode]] = []
        way_batches: list[list[OsmWay]] = []
        area_batches: list[list[OsmArea]] = []
        result = stream_features(
            path,
            node_batches.append,
            way_batches.append,
            area_batches.append,
            batch_size=3,
            area_batch_size=3,
        )

        assert len(node_batches) > 1
        assert len(way_batches) > 1
        assert len(area_batches) > 1
        assert all(len(batch) <= 3 for batch in node_batches)
        assert all(len(batch) <= 3 for batch in way_batches)
        assert all(len(batch) <= 3 for batch in area_batches)
        assert sum(len(batch) for batch in node_batches) == 10
        # The 10 closed (`landuse`) area ways each also reach `way()`,
        # alongside the 10 open (`waterway`) line ways -- see this module's
        # docstring on a closed tagged way reaching both callbacks.
        assert sum(len(batch) for batch in way_batches) == 20
        assert sum(len(batch) for batch in area_batches) == 10
        assert result.relations_skipped == 0
        assert result.ways_skipped_unresolved_nodes == 0

    def test_leftover_partial_batch_is_flushed(self, tmp_path: Path) -> None:
        # 10 elements at batch_size=3 leaves a final partial batch of 1 --
        # must not be silently dropped.
        path = tmp_path / "many.osm.pbf"
        _write_many_elements_fixture(path, n_tagged_nodes=10, n_ways=10, n_areas=10)

        nodes: list[OsmNode] = []
        ways: list[OsmWay] = []
        areas: list[OsmArea] = []
        stream_features(
            path,
            nodes.extend,
            ways.extend,
            areas.extend,
            batch_size=3,
            area_batch_size=3,
        )

        assert len(nodes) == 10
        assert len(ways) == 20  # 10 line ways + 10 closed area ways (see above)
        assert len(areas) == 10

    def test_streaming_matches_load_features_on_the_same_file(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "many.osm.pbf"
        _write_many_elements_fixture(path, n_tagged_nodes=10, n_ways=10, n_areas=10)

        bulk = load_features(path)

        streamed_nodes: list[OsmNode] = []
        streamed_ways: list[OsmWay] = []
        streamed_areas: list[OsmArea] = []
        result = stream_features(
            path,
            streamed_nodes.extend,
            streamed_ways.extend,
            streamed_areas.extend,
            batch_size=3,
            area_batch_size=3,
        )

        assert streamed_nodes == bulk.nodes
        assert streamed_ways == bulk.ways
        assert streamed_areas == bulk.areas
        assert result.relations_skipped == bulk.relations_skipped
        assert (
            result.ways_skipped_unresolved_nodes == bulk.ways_skipped_unresolved_nodes
        )


class TestStreamFeaturesMemoryBound:
    def test_peak_buffered_memory_is_bounded_by_batch_size_not_file_size(
        self, tmp_path: Path
    ) -> None:
        """The test that would have caught the M9-scale gap, scaled down:
        peak traced allocation for the node/way/area buffers should stay
        within a bound sized to `batch_size`, not grow with the fixture's
        total element count -- proving `stream_features` never holds more
        than one batch's worth of kept elements at a time."""
        path = tmp_path / "many.osm.pbf"
        n_elements = 1500
        _write_many_elements_fixture(
            path,
            n_tagged_nodes=n_elements,
            n_ways=n_elements,
            n_areas=n_elements,
        )
        batch_size = 50

        peak_batch_len = 0

        def _on_nodes(batch: list[OsmNode]) -> None:
            nonlocal peak_batch_len
            peak_batch_len = max(peak_batch_len, len(batch))

        def _on_ways(batch: list[OsmWay]) -> None:
            nonlocal peak_batch_len
            peak_batch_len = max(peak_batch_len, len(batch))

        def _on_areas(batch: list[OsmArea]) -> None:
            nonlocal peak_batch_len
            peak_batch_len = max(peak_batch_len, len(batch))

        tracemalloc.start()
        try:
            stream_features(
                path,
                _on_nodes,
                _on_ways,
                _on_areas,
                batch_size=batch_size,
                area_batch_size=batch_size,
            )
            _current, peak_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        # Never handed a batch larger than requested.
        assert peak_batch_len <= batch_size
        # A generous per-element byte budget (tags dict + coordinates), so
        # this bound scales with `batch_size` alone, not with `n_elements`
        # (4500 total kept elements at this fixture size) -- if buffering
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
    streamed_area_count = 0

    def _count_nodes(batch: list[OsmNode]) -> None:
        nonlocal streamed_node_count
        streamed_node_count += len(batch)

    def _count_ways(batch: list[OsmWay]) -> None:
        nonlocal streamed_way_count
        streamed_way_count += len(batch)

    def _count_areas(batch: list[OsmArea]) -> None:
        nonlocal streamed_area_count
        streamed_area_count += len(batch)

    result = stream_features(real_path, _count_nodes, _count_ways, _count_areas)

    assert streamed_node_count == len(bulk.nodes)
    assert streamed_way_count == len(bulk.ways)
    assert streamed_area_count == len(bulk.areas)
    assert result.relations_skipped == bulk.relations_skipped
    assert result.ways_skipped_unresolved_nodes == bulk.ways_skipped_unresolved_nodes
