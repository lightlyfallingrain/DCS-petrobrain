"""Tests for `terrain.features` -- Stage C's pure-geometry wrapping,
rewritten (not extended) for the geomorphons mechanism per
`plans/landform-geomorphons/plan.md`'s "What must be rewritten" section:
every basin/watershed-specific test this file used to carry (`grow_basins`,
`qualifying_ridges`/`qualifying_valleys`, `_axis_sliced_line`,
`_principal_axis`, `_minor_axis_extent_m`, `_saddle_elevations`, ...) has
no surviving subject -- `TerrainComponent` no longer has a basin to belong
to."""

import math

import numpy as np
import pytest

from geometry import distance_point_polyline
from terrain.features import (
    TerrainComponent,
    _chaikin_smooth,
    _chaikin_smooth_with_support,
    _decimate_for_storage,
    _smooth_for_storage,
    component_from_trace,
    filter_by_relief,
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


def _component(elevation_range_m: tuple[float, float]) -> TerrainComponent:
    return TerrainComponent(
        kind="ridge",
        cells=[(0, 0), (1, 1)],
        points=[(0.0, 0.0), (90.0, 90.0)],
        elevation_range_m=elevation_range_m,
        orientation_deg=45.0,
    )


def test_filter_by_relief_drops_components_below_threshold() -> None:
    too_flat = _component((1150.0, 1172.0))  # 22 m, below Baalbek's own gap

    assert filter_by_relief([too_flat], min_relief_m=50.0) == []


def test_filter_by_relief_keeps_components_at_or_above_threshold() -> None:
    tall_enough = _component((100.0, 150.0))  # exactly 50 m
    taller = _component((0.0, 200.0))

    kept = filter_by_relief([tall_enough, taller], min_relief_m=50.0)

    assert kept == [tall_enough, taller]


def test_filter_by_relief_default_matches_documented_floor() -> None:
    # The documented floor of the user's maskable-behind band
    # (plans/terrain-feature-probing/explore-notes.md) -- a feature with
    # exactly 49 m of relief never masks anywhere along a plausible
    # sightline per that band; one with exactly 50 m does, at the
    # near-target end.
    below = _component((0.0, 49.0))
    at_floor = _component((0.0, 50.0))

    assert filter_by_relief([below, at_floor]) == [at_floor]


def test_decimate_for_storage_reduces_point_count_on_a_straight_run() -> None:
    # A long, nearly-straight smoothed line (what four Chaikin passes over
    # a real crest segment look like) -- decimation should collapse this
    # to just its two endpoints, since every interior point sits within a
    # fraction of a metre of the straight line between them.
    smoothed = [(float(i) * 10.0, 0.01 * math.sin(i)) for i in range(50)]
    original = smoothed

    decimated = _decimate_for_storage(smoothed, original, tolerance_m=22.5, cap_m=45.0)

    assert len(decimated) < len(smoothed)
    assert decimated[0] == smoothed[0]
    assert decimated[-1] == smoothed[-1]


def test_decimate_for_storage_never_exceeds_the_deviation_cap() -> None:
    # A sharp zigzag: decimating it down to its endpoints would deviate
    # from the real sampled points by far more than a tiny cap allows, so
    # the fallback (keep the full smoothed/original geometry) must win.
    smoothed = [(0.0, 0.0), (10.0, 50.0), (20.0, 0.0), (30.0, 50.0), (40.0, 0.0)]

    decimated = _decimate_for_storage(smoothed, smoothed, tolerance_m=100.0, cap_m=1.0)

    assert decimated == smoothed
    for point in smoothed:
        assert distance_point_polyline(point, decimated) <= 1.0


def test_decimate_for_storage_checks_the_whole_decimated_line_not_one_segment() -> None:
    """Regression for a real bug found on `syria-full` SRTM data while
    verifying this fix: an earlier version of `_decimate_for_storage`
    checked each original point only against the one decimated segment
    its Chaikin support window happened to point at (via a windowed
    `distance_point_segment` call), not the whole decimated polyline. A
    real traced line's support windows are monotonic but can still group
    original points spanning a genuine turn, and a point near such a
    turn can be far from its "assigned" segment while sitting close to a
    *different* decimated segment -- `distance_point_polyline` (which
    scans every segment and takes the minimum) judges that correctly; the
    single-segment check measured 70-155 m on real data for points the
    whole-polyline check puts at 16 m, well inside the cap. This fixture
    is a real traced-ridge fragment (`N35E035.hgt`, coastal-hills
    window, centre (-5000, 15000)) that reproduced the discrepancy."""
    raw_cells_path = [
        (1530.0, 5490.0),
        (1440.0, 5580.0),
        (1350.0, 5580.0),
        (1260.0, 5580.0),
        (1170.0, 5580.0),
        (1080.0, 5490.0),
        (990.0, 5400.0),
        (900.0, 5310.0),
    ]
    smoothed, _ = _chaikin_smooth_with_support(raw_cells_path, 4)
    cap_m = 45.0

    decimated = _decimate_for_storage(
        smoothed, raw_cells_path, tolerance_m=22.5, cap_m=cap_m
    )

    assert len(decimated) < len(smoothed)
    assert max(distance_point_polyline(p, decimated) for p in raw_cells_path) <= cap_m


def test_smooth_for_storage_decimates_a_straight_crest_down() -> None:
    # Many small lattice-spaced points along a near-straight crest -- the
    # real shape `_write_tile`-derived fixtures and real SRTM crests both
    # produce -- should come out of smoothing+decimation as a small
    # handful of points, not Chaikin's ~16x-denser curve.
    points = [(float(i) * 90.0, 2.0 * math.sin(i * 0.3)) for i in range(80)]

    result = _smooth_for_storage(points, position_uncertainty_m=90.0)

    assert len(result) < len(points)
    # The deviation guarantee survives decimation: every real sampled
    # point still sits within half a grid cell of the final stored line.
    cap_m = 0.5 * 90.0
    assert max(distance_point_polyline(p, result) for p in points) <= cap_m


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
