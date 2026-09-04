"""Smoke test for `query.describe_position` against a small fixture store
built directly from `store.writer` (not from real DCS/OSM raw files, which
are gitignored).

This is Stage 1's "does it answer without crashing, with the four honesty
rules visibly respected" check. The full control-point tolerance-band test
against the real Latakia data (per
`plans/m5-first-persistent-model/plan.md`'s test spec) is Stage 4's job,
once the elevation/surface-type probe and roadnet layers exist to compare
against -- this test intentionally does not assert on those None-valued
fields as bugs.
"""

import sqlite3
from pathlib import Path

from query import describe_position
from store.models import Region, StoredFeature
from store.writer import insert_features, insert_region, open_for_build


def _fixture_conn(tmp_path: Path) -> sqlite3.Connection:
    conn = open_for_build(tmp_path / "fixture.sqlite")
    insert_region(
        conn,
        Region(
            name="latakia-20km",
            theatre="Syria",
            centre_x=44934.892,
            centre_z=5685.076,
            half_extent_m=10000.0,
            built_at="2026-09-04T00:00:00+00:00",
        ),
    )
    insert_features(
        conn,
        [
            StoredFeature(
                kind="named_place",
                geom_type="Point",
                geometry=[(41934.892, 5685.076)],
                name="Jablah",
                subtype=None,
                tags={"display_name": "Jablah"},
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
                tags={"derivation": "runway_axis_midpoint"},
                source_id=None,
                source_ref="airfield21",
                provenance={"geometry": "derived_from_dcs_beacons", "name": "dcs"},
                confidence={"geometry": "medium", "name": "high"},
                position_uncertainty_m=500.0,
            ),
            StoredFeature(
                kind="water",
                geom_type="LineString",
                geometry=[(30000.0, 0.0), (30000.0, 20000.0)],
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


def test_describe_position_runs_without_crashing_at_arp(tmp_path: Path) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        result = describe_position(conn, "Syria", 41934.892, 5685.076)
    finally:
        conn.close()

    assert result.theatre == "Syria"
    assert result.region is not None
    assert result.region.name == "latakia-20km"


def test_describe_position_finds_nearby_named_place(tmp_path: Path) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        result = describe_position(conn, "Syria", 41934.892, 5685.076)
    finally:
        conn.close()

    names = [p.name for p in result.named_places_within_radius]
    assert "Jablah" in names


def test_describe_position_reports_absence_as_none_far_outside_coverage(
    tmp_path: Path,
) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        # Far from every fixture feature and outside every search radius.
        result = describe_position(conn, "Syria", 5_000_000.0, 5_000_000.0)
    finally:
        conn.close()

    assert result.nearest_settlement is None
    assert result.nearest_airfield is None
    assert result.named_places_within_radius == []
    assert result.elevation.dcs_m is None
    assert result.surface_type.value is None


def test_describe_position_every_present_field_carries_provenance(
    tmp_path: Path,
) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        result = describe_position(conn, "Syria", 41934.892, 5685.076)
    finally:
        conn.close()

    if result.nearest_airfield is not None:
        assert result.nearest_airfield.provenance
    if result.nearest_water is not None:
        assert result.nearest_water.provenance
    for place in result.named_places_within_radius:
        assert place.provenance
