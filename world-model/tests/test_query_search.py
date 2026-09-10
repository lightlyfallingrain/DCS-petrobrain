"""Control-point-style tests for `query.search.find_place_by_name` --
`plans/bl5-tool-api/plan.md`'s name->position lookup, the counterpart to
`describe_position`'s position->description direction. Fixture store built
directly from `store.writer`, same posture as `test_describe_position.py`'s
Stage 1 smoke tests (no real DCS/OSM raw files, which are gitignored)."""

import sqlite3
from pathlib import Path

from query.search import PlaceMatch, find_place_by_name
from store.models import StoredFeature
from store.writer import insert_features, open_for_build


def _fixture_conn(tmp_path: Path) -> sqlite3.Connection:
    conn = open_for_build(tmp_path / "fixture.sqlite")
    insert_features(
        conn,
        [
            StoredFeature(
                kind="named_place",
                geom_type="Point",
                geometry=[(41934.892, 5685.076)],
                name="Jablah",
                subtype=None,
                tags={},
                source_id=None,
                source_ref="Jablah",
                provenance={"geometry": "dcs", "name": "dcs"},
                confidence={"geometry": "medium", "name": "high"},
                position_uncertainty_m=1300.0,
            ),
            StoredFeature(
                kind="airfield",
                geom_type="Point",
                geometry=[(41740.5, 5697.8)],
                name="LATAKIA",
                subtype=None,
                tags={},
                source_id=None,
                source_ref="airfield21",
                provenance={"geometry": "derived_from_dcs_beacons", "name": "dcs"},
                confidence={"geometry": "medium", "name": "high"},
                position_uncertainty_m=500.0,
            ),
            StoredFeature(
                kind="road",
                geom_type="LineString",
                geometry=[(30000.0, 0.0), (30200.0, 400.0), (30400.0, 800.0)],
                name="Highway 1",
                subtype="primary",
                tags={},
                source_id=None,
                source_ref="way/2",
                provenance={"geometry": "osm", "name": "osm"},
                confidence={"geometry": "medium", "name": "medium"},
                position_uncertainty_m=1300.0,
            ),
            StoredFeature(
                kind="water",
                geom_type="LineString",
                geometry=[(1000.0, 1000.0), (1000.0, 3000.0)],
                name=None,
                subtype="coastline",
                tags={},
                source_id=None,
                source_ref="way/1",
                provenance={"geometry": "osm", "name": "osm"},
                confidence={"geometry": "medium", "name": "medium"},
                position_uncertainty_m=1300.0,
            ),
        ],
    )
    return conn


def test_find_place_by_name_resolves_known_settlement(tmp_path: Path) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        results = find_place_by_name(conn, "Jablah")
    finally:
        conn.close()

    assert len(results) == 1
    match = results[0]
    assert match.name == "Jablah"
    assert match.kind == "named_place"
    assert match.x == 41934.892
    assert match.z == 5685.076
    assert match.confidence == 1.0
    assert match.provenance == "dcs"


def test_find_place_by_name_case_insensitive_substring(tmp_path: Path) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        results = find_place_by_name(conn, "latak")
    finally:
        conn.close()

    assert len(results) == 1
    assert results[0].name == "LATAKIA"
    assert results[0].confidence == 0.6


def test_find_place_by_name_uses_centroid_for_non_point_geometry(
    tmp_path: Path,
) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        results = find_place_by_name(conn, "Highway 1", kinds=["road"])
    finally:
        conn.close()

    assert len(results) == 1
    match = results[0]
    assert match.x == (30000.0 + 30200.0 + 30400.0) / 3
    assert match.z == (0.0 + 400.0 + 800.0) / 3


def test_find_place_by_name_default_kinds_excludes_roads_and_water(
    tmp_path: Path,
) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        results = find_place_by_name(conn, "Highway")
    finally:
        conn.close()

    assert results == []


def test_find_place_by_name_empty_text_matches_nothing(tmp_path: Path) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        results = find_place_by_name(conn, "   ")
    finally:
        conn.close()

    assert results == []


def test_find_place_by_name_unnamed_feature_never_matches(tmp_path: Path) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        results = find_place_by_name(conn, "coastline", kinds=["water"])
    finally:
        conn.close()

    assert results == []


def test_find_place_by_name_no_match_returns_empty_list(tmp_path: Path) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        results = find_place_by_name(conn, "Nonexistent Place")
    finally:
        conn.close()

    assert results == []


def test_place_match_is_a_frozen_dataclass_with_expected_fields() -> None:
    match = PlaceMatch(
        name="X",
        kind="settlement",
        feature_id=1,
        x=0.0,
        z=0.0,
        confidence=1.0,
        provenance="dcs",
    )
    assert match.name == "X"
