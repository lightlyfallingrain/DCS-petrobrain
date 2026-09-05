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
from array import array
from pathlib import Path

import pytest

from build.validate import (
    SpotCheckPoint,
    check_road_count,
    compare_probe_to_srtm,
    spot_check_positions,
)
from elevation.dcs_grid import DcsElevationSample
from elevation.dem import SrtmTile
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


def _uniform_tile(
    sw_lat: float, sw_lon: float, span_deg: float, value: float
) -> SrtmTile:
    """Mirrors `test_ingest_probe.py`'s/`test_ingest_srtm.py`'s uniform-
    value tile fixture: every sample is `value`, so any point inside the
    tile's coverage returns exactly `value` regardless of bilinear
    interpolation position -- keeps expected deltas hand-verifiable."""
    size = 3
    samples = array("h", [int(value)] * (size * size))
    return SrtmTile(
        sw_lat=sw_lat, sw_lon=sw_lon, size=size, samples=samples, span_deg=span_deg
    )


# Real lat/lon envelope of DCS point (41934.892, 5685.076) under Syria's
# projection is ~35.40N, ~35.95E (the Latakia ARP -- see
# tests/control_points.py). A generously-sized tile around it covers every
# point used below.
_TILE = _uniform_tile(sw_lat=35.3, sw_lon=35.85, span_deg=0.3, value=100.0)


def test_compare_probe_to_srtm_computes_delta_per_point() -> None:
    """Generalizes M4's single-region Gemerek delta check to a scattered
    point set: `delta_m` is `dcs_probe_m - srtm_m`, hand-verifiable here
    since every SRTM sample is the same uniform value (100.0)."""
    samples = [
        DcsElevationSample(name="p1", x=41934.892, z=5685.076, height_m=112.0),
        DcsElevationSample(name="p2", x=42934.892, z=6685.076, height_m=88.0),
    ]

    report = compare_probe_to_srtm(samples, [_TILE], "Syria")

    assert len(report.points) == 2
    assert report.points_skipped == 0
    by_name = {p.name: p for p in report.points}
    assert by_name["p1"].delta_m == pytest.approx(12.0)
    assert by_name["p2"].delta_m == pytest.approx(-12.0)
    assert report.mean_delta_m == pytest.approx(0.0)
    assert report.min_delta_m == pytest.approx(-12.0)
    assert report.max_delta_m == pytest.approx(12.0)


def test_compare_probe_to_srtm_skips_points_outside_tile_coverage() -> None:
    """A point far outside every given tile's coverage is counted as
    skipped, not silently dropped or allowed to crash the whole report --
    mirrors `build.ingest_probe`'s existing `srtm_points_skipped` handling,
    generalized to a scattered multi-tile point set."""
    samples = [
        DcsElevationSample(name="in_range", x=41934.892, z=5685.076, height_m=112.0),
        DcsElevationSample(name="far_away", x=5_000_000.0, z=5_000_000.0, height_m=1.0),
    ]

    report = compare_probe_to_srtm(samples, [_TILE], "Syria")

    assert len(report.points) == 1
    assert report.points_skipped == 1
    assert report.points[0].name == "in_range"


def test_compare_probe_to_srtm_empty_result_has_null_stats() -> None:
    samples = [
        DcsElevationSample(name="far_away", x=5_000_000.0, z=5_000_000.0, height_m=1.0)
    ]

    report = compare_probe_to_srtm(samples, [_TILE], "Syria")

    assert report.points == []
    assert report.points_skipped == 1
    assert report.mean_delta_m is None
    assert report.stddev_delta_m is None
