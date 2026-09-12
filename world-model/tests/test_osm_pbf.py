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

from pathlib import Path

import osmium
import pytest
from osmium.osm import mutable

from osm.features import OsmNode, OsmWay
from osm.pbf import load_features

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
