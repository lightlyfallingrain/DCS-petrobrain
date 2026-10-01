"""Tests for `terrain.features` -- Stage C's pure-geometry wrapping,
rewritten (not extended) for the geomorphons mechanism per
`plans/landform-geomorphons/plan.md`'s "What must be rewritten" section:
every basin/watershed-specific test this file used to carry (`grow_basins`,
`qualifying_ridges`/`qualifying_valleys`, `_axis_sliced_line`,
`_principal_axis`, `_minor_axis_extent_m`, `_saddle_elevations`, ...) has
no surviving subject -- `TerrainComponent` no longer has a basin to belong
to."""

import numpy as np
import pytest

from terrain.features import (
    TerrainComponent,
    _chaikin_smooth,
    _smooth_for_storage,
    component_from_trace,
    to_stored_features,
)


def test_component_from_trace_builds_real_dcs_points() -> None:
    dem = np.array([[100.0, 110.0], [120.0, 130.0]])
    cells = [(0, 0), (0, 1), (1, 1)]

    component = component_from_trace(
        "ridge", cells, dem, origin_x=1000.0, origin_z=2000.0, spacing_m=90.0
    )

    assert component.points == [
        (1000.0, 2000.0),
        (1000.0, 2090.0),
        (1090.0, 2090.0),
    ]
    assert component.elevation_range_m == (100.0, 130.0)
    assert component.cells == cells


def test_component_from_trace_orientation_deg_is_mod_180() -> None:
    dem = np.full((2, 2), 100.0)
    cells = [(0, 0), (1, 1)]  # 45 deg direction

    component = component_from_trace(
        "ridge", cells, dem, origin_x=0.0, origin_z=0.0, spacing_m=10.0
    )

    assert component.orientation_deg == pytest.approx(45.0)


def test_component_from_trace_degenerate_same_point_orientation_zero() -> None:
    dem = np.full((1, 1), 100.0)
    cells = [(0, 0), (0, 0)]

    component = component_from_trace(
        "valley", cells, dem, origin_x=0.0, origin_z=0.0, spacing_m=10.0
    )

    assert component.orientation_deg == 0.0


def test_chaikin_smooth_holds_endpoints_fixed() -> None:
    points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]

    smoothed = _chaikin_smooth(points, iterations=2)

    assert smoothed[0] == points[0]
    assert smoothed[-1] == points[-1]
    assert len(smoothed) > len(points)


def test_chaikin_smooth_short_line_unchanged() -> None:
    points = [(0.0, 0.0), (10.0, 0.0)]

    assert _chaikin_smooth(points, iterations=4) == points


def test_smooth_for_storage_falls_back_if_deviation_exceeds_cap() -> None:
    # A sharp zigzag whose Chaikin-smoothed curve would deviate from the
    # original polyline by more than half a (tiny) grid cell -- the
    # fallback should return the original, unsmoothed points.
    points = [(0.0, 0.0), (100.0, 100.0), (0.0, 200.0), (100.0, 300.0)]

    result = _smooth_for_storage(points, position_uncertainty_m=1.0)

    assert result == points


def test_smooth_for_storage_smooths_when_within_cap() -> None:
    points = [(0.0, 0.0), (90.0, 0.0), (180.0, 5.0), (270.0, 0.0), (360.0, 0.0)]

    result = _smooth_for_storage(points, position_uncertainty_m=90.0)

    assert result != points
    assert result[0] == points[0]
    assert result[-1] == points[-1]


def test_to_stored_features_sets_provenance_and_tags() -> None:
    component = TerrainComponent(
        kind="ridge",
        cells=[(0, 0), (1, 1), (2, 2)],
        points=[(0.0, 0.0), (90.0, 90.0), (180.0, 180.0)],
        elevation_range_m=(100.0, 200.0),
        orientation_deg=45.0,
    )

    features = to_stored_features([component], source_id=7, position_uncertainty_m=90.0)

    assert len(features) == 1
    feature = features[0]
    assert feature.kind == "ridge"
    assert feature.geom_type == "LineString"
    assert feature.source_id == 7
    assert feature.source_ref == "ridge_0"
    assert feature.provenance == {"geometry": "dcs_derived"}
    assert feature.confidence == {"geometry": "low"}
    assert feature.tags["elevation_range_m"] == [100.0, 200.0]
    assert feature.tags["orientation_deg"] == 45.0
    assert feature.tags["cell_count"] == 3
    assert "basin_width_m" not in feature.tags


def test_to_stored_features_no_basin_width_tag_for_valleys_either() -> None:
    component = TerrainComponent(
        kind="valley",
        cells=[(0, 0), (1, 1)],
        points=[(0.0, 0.0), (90.0, 90.0)],
        elevation_range_m=(0.0, 50.0),
        orientation_deg=45.0,
    )

    features = to_stored_features(
        [component], source_id=None, position_uncertainty_m=90.0
    )

    assert "basin_width_m" not in features[0].tags
