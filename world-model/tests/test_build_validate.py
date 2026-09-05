"""Tests for `build.validate` -- M7 Stage 1's spot-check and road-count
sanity checks. Uses a small synthetic store built directly via
`store.writer` (not real DCS/OSM raw files, which are gitignored), same
pattern as `test_describe_position.py`'s fixture -- this module tests
wiring (does `spot_check_positions` correctly summarize
`describe_position`'s answers, does `check_road_count` correctly bucket a
count into/out of tolerance), not real full-theatre data, which per
`plans/m7-full-theatre-pipeline/plan.md`'s "Execution boundary" only the
user's own build ever produces.
"""

import sqlite3
from pathlib import Path

from build.validate import (
    SpotCheckPoint,
    check_road_count,
    spot_check_positions,
)
from store.models import Region, StoredFeature
from store.writer import insert_features, insert_region, open_for_build

_ROAD_X, _ROAD_Z = 1000.0, 0.0
_SETTLEMENT_X, _SETTLEMENT_Z = 0.0, 1000.0


def _fixture_conn(tmp_path: Path) -> sqlite3.Connection:
    conn = open_for_build(tmp_path / "fixture.sqlite")
    insert_region(
        conn,
        Region(
            name="test-region",
            theatre="Syria",
            centre_x=0.0,
            centre_z=0.0,
            half_extent_x_m=5000.0,
            half_extent_z_m=5000.0,
            built_at="2026-09-05T00:00:00+00:00",
        ),
    )
    insert_features(
        conn,
        [
            StoredFeature(
                kind="road",
                geom_type="LineString",
                geometry=[(_ROAD_X, _ROAD_Z - 500.0), (_ROAD_X, _ROAD_Z + 500.0)],
                name=None,
                subtype=None,
                tags={},
                source_id=None,
                source_ref="route/1",
                provenance={"geometry": "dcs", "name": "dcs"},
                confidence={"geometry": "confirmed", "name": "unavailable"},
                position_uncertainty_m=0.0,
            ),
            StoredFeature(
                kind="settlement",
                geom_type="Point",
                geometry=[(_SETTLEMENT_X, _SETTLEMENT_Z)],
                name="Testville",
                subtype=None,
                tags={},
                source_id=None,
                source_ref="Testville",
                provenance={"geometry": "dcs", "name": "dcs"},
                confidence={"geometry": "medium", "name": "high"},
                position_uncertainty_m=1300.0,
            ),
        ],
    )
    return conn


def test_spot_check_positions_finds_the_nearby_road_and_settlement(
    tmp_path: Path,
) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        results = spot_check_positions(
            conn,
            "Syria",
            [SpotCheckPoint(name="origin", x=0.0, z=0.0)],
        )
    finally:
        conn.close()

    assert len(results) == 1
    result = results[0]
    assert result.name == "origin"
    assert result.nearest_road_found is True
    assert result.nearest_road_distance_m == 1000.0
    assert result.nearest_settlement_found is True
    assert result.nearest_settlement_distance_m == 1000.0


def test_spot_check_positions_reports_absence_far_outside_coverage(
    tmp_path: Path,
) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        results = spot_check_positions(
            conn,
            "Syria",
            [SpotCheckPoint(name="far", x=5_000_000.0, z=5_000_000.0)],
        )
    finally:
        conn.close()

    result = results[0]
    assert result.nearest_road_found is False
    assert result.nearest_road_distance_m is None
    assert result.nearest_settlement_found is False
    assert result.nearest_settlement_distance_m is None


def test_check_road_count_within_tolerance() -> None:
    check = check_road_count(actual_road_count=14_900, expected=14_833)
    assert check.within_tolerance is True


def test_check_road_count_outside_tolerance() -> None:
    check = check_road_count(actual_road_count=1_000, expected=14_833)
    assert check.within_tolerance is False
