"""Tests for `store.schema`/`store.writer`/`store.reader` -- schema
creation, insert/read roundtrip, provenance/confidence JSON preserved
verbatim, and `SCHEMA_VERSION` mismatch detection.
"""

import sqlite3
from pathlib import Path

import pytest

from store.models import Region, Source, StoredFeature
from store.reader import load_only_region, load_region
from store.schema import SCHEMA_VERSION, check_schema_version
from store.writer import insert_features, insert_region, insert_source, open_for_build


def _region() -> Region:
    return Region(
        name="latakia-20km",
        theatre="Syria",
        centre_x=44934.892,
        centre_z=5685.076,
        half_extent_x_m=10000.0,
        half_extent_z_m=10000.0,
        built_at="2026-09-04T00:00:00+00:00",
    )


def _feature() -> StoredFeature:
    return StoredFeature(
        kind="named_place",
        geom_type="Point",
        geometry=[(100.0, 200.0)],
        name="Test Town",
        subtype=None,
        tags={"display_name": "Test Town"},
        source_id=None,
        source_ref="Test Town",
        provenance={"geometry": "dcs", "name": "dcs"},
        confidence={"geometry": "medium", "name": "high"},
        position_uncertainty_m=1300.0,
    )


def test_open_for_build_creates_schema_and_meta_version(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = open_for_build(db_path)
    try:
        check_schema_version(conn)  # must not raise
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row[0] == str(SCHEMA_VERSION)
    finally:
        conn.close()


def test_open_for_build_is_idempotent_deletes_existing_file(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn1 = open_for_build(db_path)
    insert_region(conn1, _region())
    conn1.close()

    conn2 = open_for_build(db_path)
    try:
        # A fresh rebuild must not carry over the prior region row.
        assert load_only_region(conn2) is None
    finally:
        conn2.close()


def test_region_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = open_for_build(db_path)
    try:
        region = _region()
        insert_region(conn, region)

        loaded = load_region(conn, "latakia-20km")
        assert loaded == region
        assert load_only_region(conn) == region
    finally:
        conn.close()


def test_source_insert_returns_id(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = open_for_build(db_path)
    try:
        source_id = insert_source(
            conn,
            Source(
                name="towns.lua",
                fetched_at="2026-09-04T00:00:00+00:00",
                raw_path="data/raw/dcs/syria/map/towns.lua",
                attribution="DCS terrain module (Eagle Dynamics)",
                notes="",
            ),
        )
        assert isinstance(source_id, int)
        row = conn.execute(
            "SELECT name FROM source WHERE id = ?", (source_id,)
        ).fetchone()
        assert row[0] == "towns.lua"
    finally:
        conn.close()


def test_feature_roundtrip_preserves_provenance_and_confidence_json(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = open_for_build(db_path)
    try:
        feature = _feature()
        insert_features(conn, [feature])

        row = conn.execute(
            "SELECT kind, geom_type, geom_json, name, provenance_json, confidence_json, "
            "position_uncertainty_m FROM feature"
        ).fetchone()
        assert row[0] == "named_place"
        assert row[1] == "Point"
        assert row[3] == "Test Town"
        assert row[6] == 1300.0

        import json

        assert json.loads(row[4]) == {"geometry": "dcs", "name": "dcs"}
        assert json.loads(row[5]) == {"geometry": "medium", "name": "high"}
        assert json.loads(row[2]) == [[100.0, 200.0]]
    finally:
        conn.close()


def test_feature_insert_populates_rtree_bbox(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = open_for_build(db_path)
    try:
        insert_features(conn, [_feature()])

        bbox_row = conn.execute(
            "SELECT min_x, max_x, min_z, max_z FROM feature_bbox"
        ).fetchone()
        assert bbox_row == (100.0, 100.0, 200.0, 200.0)
    finally:
        conn.close()


def test_insert_features_raises_on_empty_geometry(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = open_for_build(db_path)
    try:
        bad_feature = StoredFeature(
            kind="named_place",
            geom_type="Point",
            geometry=[],
            name="Bad",
            subtype=None,
            tags={},
            source_id=None,
            source_ref=None,
            provenance={},
            confidence={},
            position_uncertainty_m=None,
        )
        with pytest.raises(ValueError):
            insert_features(conn, [bad_feature])
    finally:
        conn.close()


def test_check_schema_version_raises_on_mismatch(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = open_for_build(db_path)
    try:
        conn.execute(
            "UPDATE meta SET value = ? WHERE key = 'schema_version'",
            (str(SCHEMA_VERSION + 1),),
        )
        conn.commit()
        with pytest.raises(ValueError, match="schema_version"):
            check_schema_version(conn)
    finally:
        conn.close()


def test_check_schema_version_raises_when_meta_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    try:
        with pytest.raises(ValueError, match="not a valid world-model store"):
            check_schema_version(conn)
    finally:
        conn.close()
