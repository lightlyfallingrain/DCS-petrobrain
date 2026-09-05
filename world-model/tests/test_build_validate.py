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
    check_elevation_provenance,
    check_road_count,
    compare_probe_to_srtm,
    spot_check_positions,
)
from elevation.dcs_grid import DcsElevationSample
from elevation.dem import SrtmTile
from store.models import ElevationGrid, Region, StoredFeature, SurfaceGrid
from store.writer import insert_features, insert_grid, insert_region, open_for_build

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


def _fixture_conn_with_region(tmp_path: Path) -> sqlite3.Connection:
    """A store with a region but deliberately no grid at all -- the
    "missing" half of Stage 3's provenance check."""
    conn = open_for_build(tmp_path / "fixture-provenance.sqlite")
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
    return conn


def _small_elevation_grid(provenance: str) -> ElevationGrid:
    return ElevationGrid(
        origin_x=0.0,
        origin_z=0.0,
        spacing_m=100.0,
        n_rows=2,
        n_cols=2,
        source_id=None,
        provenance=provenance,
        stats={},
        samples=[[0.0, 100.0], [200.0, 300.0]],
    )


def _small_surface_grid(provenance: str) -> SurfaceGrid:
    return SurfaceGrid(
        origin_x=0.0,
        origin_z=0.0,
        spacing_m=100.0,
        n_rows=2,
        n_cols=2,
        source_id=None,
        provenance=provenance,
        stats={},
        samples=[[1, 1], [1, 1]],
    )


def test_check_elevation_provenance_all_ok_for_real_srtm_and_dcs_probe_values(
    tmp_path: Path,
) -> None:
    """A store whose `elevation` grid came from SRTM and whose
    `surface_type` grid came from the DCS live probe (M7 Stage 2's real
    shape for a `syria-full` build) reports both provenances as ok, and
    with the exact source strings a caller would want to display."""
    conn = _fixture_conn_with_region(tmp_path)
    try:
        insert_grid(conn, _small_elevation_grid("srtm"))
        insert_grid(conn, _small_surface_grid("dcs_probe"))

        report = check_elevation_provenance(
            conn, "Syria", [SpotCheckPoint(name="centre", x=50.0, z=50.0)]
        )
    finally:
        conn.close()

    assert report.all_ok is True
    assert len(report.checks) == 1
    check = report.checks[0]
    assert check.elevation_source == "srtm"
    assert check.elevation_provenance_ok is True
    assert check.surface_type_provenance == "dcs_probe"
    assert check.surface_type_provenance_ok is True


def test_check_elevation_provenance_flags_a_stale_ambiguous_value(
    tmp_path: Path,
) -> None:
    """Deliberately-bad fixture: an `elevation` grid tagged with the
    pre-M7-Stage-2 hardcoded `"dcs"` literal (the exact bug
    `query/describe.py`'s provenance fix replaced -- see its module
    docstring) is neither `"srtm"` nor `"dcs_probe"`, and the check must
    flag it rather than passing silently. Proves the check actually catches
    an ambiguous provenance value, not just that it passes on good data."""
    conn = _fixture_conn_with_region(tmp_path)
    try:
        insert_grid(conn, _small_elevation_grid("dcs"))
        insert_grid(conn, _small_surface_grid("dcs_probe"))

        report = check_elevation_provenance(
            conn, "Syria", [SpotCheckPoint(name="centre", x=50.0, z=50.0)]
        )
    finally:
        conn.close()

    assert report.all_ok is False
    check = report.checks[0]
    assert check.elevation_source == "dcs"
    assert check.elevation_provenance_ok is False
    # The unrelated, correctly-tagged surface_type grid is not dragged down
    # by the elevation grid's bad value -- each is checked independently.
    assert check.surface_type_provenance_ok is True


def test_check_elevation_provenance_flags_a_missing_grid_as_not_ok(
    tmp_path: Path,
) -> None:
    """No grid built at all reports `"unavailable"` (absence-as-absence,
    per `query/describe.py`), which the provenance check must also treat
    as not-ok -- Stage 3 cares that provenance is never ambiguous *or*
    silently missing where a real build should have populated it."""
    conn = _fixture_conn_with_region(tmp_path)
    try:
        report = check_elevation_provenance(
            conn, "Syria", [SpotCheckPoint(name="centre", x=50.0, z=50.0)]
        )
    finally:
        conn.close()

    assert report.all_ok is False
    check = report.checks[0]
    assert check.elevation_source == "unavailable"
    assert check.elevation_provenance_ok is False
    assert check.surface_type_provenance == "unavailable"
    assert check.surface_type_provenance_ok is False


def test_check_elevation_provenance_covers_every_point_given(
    tmp_path: Path,
) -> None:
    """A scattered multi-point set (Stage 3's "wider, geographically-spread
    control-point set") produces one `ProvenanceSpotCheck` per point, all
    reporting the store's real, unambiguous grid provenance -- not just the
    first point checked. Grid provenance is store-wide (one "most recent"
    grid per kind, per `store.reader`'s convention), so being outside the
    grid's own sampled coverage changes `elevation.dcs_m`, not the
    provenance label itself; `all_ok` aggregating across every point (not
    just the first) is proven together with the ambiguous/missing cases
    above, which fail on a single point."""
    conn = _fixture_conn_with_region(tmp_path)
    try:
        insert_grid(conn, _small_elevation_grid("srtm"))
        insert_grid(conn, _small_surface_grid("dcs_probe"))

        report = check_elevation_provenance(
            conn,
            "Syria",
            [
                SpotCheckPoint(name="inside_grid", x=50.0, z=50.0),
                SpotCheckPoint(name="outside_grid", x=4000.0, z=4000.0),
            ],
        )
    finally:
        conn.close()

    assert report.all_ok is True
    assert len(report.checks) == 2
    assert {check.name for check in report.checks} == {"inside_grid", "outside_grid"}
