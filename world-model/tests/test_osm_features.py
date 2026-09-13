"""Tests for `osm.features.load_features` against a hardcoded fixture.

The fixture below is a literal, hand-copied subset (5 elements: 1 node, 4
ways) of the single real Overpass response fetched for M3's known location
(Gemerek, Sivas Province -- see `world-model/research/` for the M3 research
note and `plans/m3-osm-overlay/plan.md` for the exact bbox/query). Mirrors
`tests/control_points.py`'s pattern of hardcoding real-world-sourced data
directly in the test module rather than reading a file, so tests never touch
the network -- see `world-model/CLAUDE.md`'s testing conventions.

Provenance: `world-model/data/raw/osm/2026-09-03/gemerek_bbox.json`,
elements 146775319 (Gemerek town node), 286447637 (a short residential
way), 286447599 (a building outline), 532529565 (a named mosque way,
`amenity=place_of_worship`). (c) OpenStreetMap contributors.
"""

import json
from pathlib import Path

from osm.features import OsmNode, OsmWay, load_features

_FIXTURE_OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "node",
            "id": 146775319,
            "lat": 39.1831222,
            "lon": 36.0711044,
            "tags": {"name": "Gemerek", "place": "town", "population": "23083"},
        },
        {
            "type": "way",
            "id": 286447637,
            "nodes": [2901248453, 2901248441],
            "geometry": [
                {"lat": 39.1864378, "lon": 36.0802863},
                {"lat": 39.1860337, "lon": 36.0771514},
            ],
            "tags": {"highway": "residential", "source": "bing"},
        },
        {
            "type": "way",
            "id": 286447599,
            "nodes": [2901248465, 2901248470, 2901248471, 2901248467, 2901248465],
            "geometry": [
                {"lat": 39.186931, "lon": 36.0798395},
                {"lat": 39.1872378, "lon": 36.0797568},
                {"lat": 39.1872677, "lon": 36.0799413},
                {"lat": 39.1869609, "lon": 36.080024},
                {"lat": 39.186931, "lon": 36.0798395},
            ],
            "tags": {"building": "yes", "source": "bing"},
        },
        {
            "type": "way",
            "id": 532529565,
            "nodes": [5167373328, 5167372917, 5167373327, 5167372916, 5167373328],
            "geometry": [
                {"lat": 39.1867492, "lon": 36.0796823},
                {"lat": 39.1865537, "lon": 36.079689},
                {"lat": 39.1865578, "lon": 36.0798847},
                {"lat": 39.1867532, "lon": 36.079878},
                {"lat": 39.1867492, "lon": 36.0796823},
            ],
            "tags": {
                "name": "Cami",
                "amenity": "place_of_worship",
                "building": "mosque",
                "denomination": "sunni",
                "religion": "muslim",
            },
        },
        # A "relation" element type is not requested by the plan's query but
        # is included here to verify load_features ignores unrecognized
        # element types rather than raising.
        {"type": "relation", "id": 1, "tags": {}},
    ]
}


def test_load_features_parses_node_and_way_counts(tmp_path: Path) -> None:
    cache_path = tmp_path / "fixture.json"
    cache_path.write_text(json.dumps(_FIXTURE_OVERPASS_RESPONSE), encoding="utf-8")

    feature_set = load_features(cache_path)

    assert len(feature_set.nodes) == 1
    assert len(feature_set.ways) == 3


def test_load_features_parses_place_node_fields(tmp_path: Path) -> None:
    cache_path = tmp_path / "fixture.json"
    cache_path.write_text(json.dumps(_FIXTURE_OVERPASS_RESPONSE), encoding="utf-8")

    feature_set = load_features(cache_path)

    gemerek = feature_set.nodes[0]
    assert gemerek == OsmNode(
        id=146775319,
        tags={"name": "Gemerek", "place": "town", "population": "23083"},
        lat=39.1831222,
        lon=36.0711044,
    )


def test_load_features_parses_way_geometry_in_order(tmp_path: Path) -> None:
    cache_path = tmp_path / "fixture.json"
    cache_path.write_text(json.dumps(_FIXTURE_OVERPASS_RESPONSE), encoding="utf-8")

    feature_set = load_features(cache_path)

    residential_way = next(w for w in feature_set.ways if w.id == 286447637)
    assert residential_way == OsmWay(
        id=286447637,
        tags={"highway": "residential", "source": "bing"},
        points=[(39.1864378, 36.0802863), (39.1860337, 36.0771514)],
    )


def test_load_features_mirrors_closed_tagged_ways_into_areas(tmp_path: Path) -> None:
    """osm-landcover-optimization: every tagged closed way (4+ points,
    first == last) is also emitted as a single-ring, no-holes `OsmArea`,
    alongside its `OsmWay` -- Overpass's flat response carries no relation
    geometry, so multipolygons stay a counted `relations_skipped` skip, but
    a closed way needs no assembly and mirrors `osm.pbf`'s own
    `from_way=True` area shape."""
    cache_path = tmp_path / "fixture.json"
    cache_path.write_text(json.dumps(_FIXTURE_OVERPASS_RESPONSE), encoding="utf-8")

    feature_set = load_features(cache_path)

    # The two closed ways (a building outline and a named mosque) each
    # produce an area; the open residential way does not.
    area_ids = {area.id for area in feature_set.areas}
    assert area_ids == {286447599, 532529565}

    mosque_area = next(a for a in feature_set.areas if a.id == 532529565)
    assert mosque_area.from_way is True
    assert mosque_area.tags == {
        "name": "Cami",
        "amenity": "place_of_worship",
        "building": "mosque",
        "denomination": "sunni",
        "religion": "muslim",
    }
    assert len(mosque_area.rings) == 1
    assert mosque_area.rings[0].inners == []
    assert mosque_area.rings[0].outer[0] == mosque_area.rings[0].outer[-1]


def test_load_features_ignores_unrecognized_element_types(tmp_path: Path) -> None:
    cache_path = tmp_path / "fixture.json"
    cache_path.write_text(json.dumps(_FIXTURE_OVERPASS_RESPONSE), encoding="utf-8")

    feature_set = load_features(cache_path)

    # 1 node + 3 ways = 4 recognized elements; the "relation" element is
    # dropped, not raised on.
    assert len(feature_set.nodes) + len(feature_set.ways) == 4
