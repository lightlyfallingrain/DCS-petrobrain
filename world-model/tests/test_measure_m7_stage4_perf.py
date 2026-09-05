"""Tests for `tools/measure_m7_stage4_perf.py`'s sampling/reporting logic --
M7 Stage 4's perf-measurement tool. Per the plan's "Execution boundary",
this tool is meant for the user to run against their own real
`syria-full.sqlite`; these tests verify the tool's sampling and latency-
reporting logic against a small synthetic fixture store (same
`store.writer`-direct pattern as `test_build_validate.py`), not real
full-theatre data.

`tools/` is not on `pytest`'s configured `pythonpath` (only `src` is, per
`pyproject.toml`), so this module inserts `tools/` onto `sys.path` itself,
mirroring how `tools/validate_m7_stage3.py` inserts `tests/` to import
`control_points`.
"""

import sqlite3
import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "tools"))

from measure_m7_stage4_perf import (
    LatencyStats,
    measure_describe_position_latency,
    sample_points_for_region,
)

from build.region import RegionDefinition
from control_points import ControlPoint
from store.models import Region, StoredFeature
from store.writer import insert_features, insert_region, open_for_build

# A deliberately rectangular (non-square) region, mirroring `syria-full`'s
# own unequal half-extents -- if `sample_points_for_region` only handled
# the square case, an asymmetric bbox here would catch it (e.g. a bug that
# reused `half_extent_x_m` for both axes).
_TEST_REGION = RegionDefinition(
    theatre="Syria",
    name="test-region",
    centre_x=0.0,
    centre_z=0.0,
    half_extent_x_m=10_000.0,
    half_extent_z_m=5_000.0,
)

_CONTROL_POINTS = [
    ControlPoint(
        theatre="Syria",
        name="Test Point A",
        dcs_x=100.0,
        dcs_z=-200.0,
        real_lat=0.0,
        real_lon=0.0,
        source="synthetic fixture",
        expected_max_residual_m=1500.0,
    ),
    ControlPoint(
        theatre="Syria",
        name="Test Point B",
        dcs_x=-500.0,
        dcs_z=300.0,
        real_lat=0.0,
        real_lon=0.0,
        source="synthetic fixture",
        expected_max_residual_m=1500.0,
    ),
    # A different theatre's control point -- must never appear in the
    # sample for `_TEST_REGION`.
    ControlPoint(
        theatre="Kola",
        name="Not This Theatre",
        dcs_x=0.0,
        dcs_z=0.0,
        real_lat=0.0,
        real_lon=0.0,
        source="synthetic fixture",
        expected_max_residual_m=1500.0,
    ),
]


def test_sample_points_for_region_includes_every_matching_control_point() -> None:
    points = sample_points_for_region(
        _TEST_REGION, _CONTROL_POINTS, n_random=0, n_boundary=0
    )
    labels = {label for label, _x, _z in points}
    assert labels == {"Test Point A", "Test Point B"}


def test_sample_points_for_region_excludes_other_theatres_control_points() -> None:
    points = sample_points_for_region(
        _TEST_REGION, _CONTROL_POINTS, n_random=0, n_boundary=0
    )
    assert all(label != "Not This Theatre" for label, _x, _z in points)


def test_sample_points_for_region_total_count_and_bbox() -> None:
    points = sample_points_for_region(
        _TEST_REGION, _CONTROL_POINTS, n_random=50, n_boundary=10, seed=42
    )
    # 2 matching control points + 50 random + 10 boundary.
    assert len(points) == 62

    random_points = [(x, z) for label, x, z in points if label.startswith("random-")]
    assert len(random_points) == 50
    for x, z in random_points:
        assert -10_000.0 <= x <= 10_000.0
        assert -5_000.0 <= z <= 5_000.0

    boundary_points = [
        (x, z) for label, x, z in points if label.startswith("boundary-")
    ]
    assert len(boundary_points) == 10
    # Boundary points are drawn from a wider (1.05x) box than the random
    # ones -- not a strict superset guarantee point-by-point, but the
    # sampled range itself must extend past the region's own half-extents,
    # otherwise the "near-boundary/outside-coverage" sample would be
    # indistinguishable from the in-region one.
    assert any(abs(x) > 10_000.0 or abs(z) > 5_000.0 for x, z in boundary_points)


def test_sample_points_for_region_is_reproducible_for_a_fixed_seed() -> None:
    points_a = sample_points_for_region(
        _TEST_REGION, _CONTROL_POINTS, n_random=20, n_boundary=5, seed=7
    )
    points_b = sample_points_for_region(
        _TEST_REGION, _CONTROL_POINTS, n_random=20, n_boundary=5, seed=7
    )
    assert points_a == points_b


def _fixture_conn(tmp_path: Path) -> sqlite3.Connection:
    conn = open_for_build(tmp_path / "fixture.sqlite")
    insert_region(
        conn,
        Region(
            name="test-region",
            theatre="Syria",
            centre_x=0.0,
            centre_z=0.0,
            half_extent_x_m=10_000.0,
            half_extent_z_m=5_000.0,
            built_at="2026-09-05T00:00:00+00:00",
        ),
    )
    insert_features(
        conn,
        [
            StoredFeature(
                kind="road",
                geom_type="LineString",
                geometry=[(0.0, -1000.0), (0.0, 1000.0)],
                name=None,
                subtype=None,
                tags={},
                source_id=None,
                source_ref="route/1",
                provenance={"geometry": "dcs", "name": "dcs"},
                confidence={"geometry": "confirmed", "name": "unavailable"},
                position_uncertainty_m=0.0,
            ),
        ],
    )
    return conn


def test_measure_describe_position_latency_reports_one_stat_per_batch(
    tmp_path: Path,
) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        points = sample_points_for_region(
            _TEST_REGION, _CONTROL_POINTS, n_random=5, n_boundary=2
        )
        stats = measure_describe_position_latency(conn, "Syria", points)
    finally:
        conn.close()

    assert isinstance(stats, LatencyStats)
    # 2 control points + 5 random + 2 boundary.
    assert stats.n_points == 9
    assert stats.min_ms >= 0.0
    assert stats.min_ms <= stats.median_ms <= stats.max_ms
    assert stats.median_ms <= stats.p95_ms <= stats.p99_ms <= stats.max_ms
    assert stats.mean_ms >= 0.0


def test_measure_describe_position_latency_handles_a_single_point(
    tmp_path: Path,
) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        stats = measure_describe_position_latency(conn, "Syria", [("solo", 0.0, 0.0)])
    finally:
        conn.close()

    assert stats.n_points == 1
    assert (
        stats.min_ms == stats.max_ms == stats.median_ms == stats.p95_ms == stats.p99_ms
    )
