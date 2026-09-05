"""Tests for `build.ingest_terrain.ingest_terrain`: the wiring that turns a
loaded `ElevationGrid` into the `(StoredFeature list, stats)` shape
`build.pipeline.build_region` inserts. Uses the same row-3 ridge fixture as
`test_terrain_curvature.py`/`test_terrain_features.py` -- this module tests
wiring (threshold/min-cell-count plumbing, stats bookkeeping), not the
classification/extraction algorithm itself, which those two files already
cover. `_TEST_THRESHOLD_M`/`_TEST_MIN_CELL_COUNT` are passed explicitly
rather than relying on `ingest_terrain`'s defaults, so this fixture stays
independent of Stage 2's real-data-tuned production defaults (see
`terrain.curvature`'s module docstring).
"""

from build.ingest_terrain import ingest_terrain
from store.models import ElevationGrid

_SPACING_M = 100.0
_N = 7
_RIDGE_ROW = 3
_TEST_THRESHOLD_M = 3.0
_TEST_MIN_CELL_COUNT = 4


def _ridge_grid() -> ElevationGrid:
    samples: list[list[float | None]] = [
        [100.0 - 10.0 * abs(row - _RIDGE_ROW) + 2.0 * col for col in range(_N)]
        for row in range(_N)
    ]
    return ElevationGrid(
        origin_x=0.0,
        origin_z=0.0,
        spacing_m=_SPACING_M,
        n_rows=_N,
        n_cols=_N,
        source_id=None,
        provenance="dcs_probe",
        stats={},
        samples=samples,
    )


def test_ingest_terrain_produces_one_ridge_feature() -> None:
    grid = _ridge_grid()

    features, stats = ingest_terrain(
        grid,
        source_id=3,
        curvature_threshold_m=_TEST_THRESHOLD_M,
        min_cell_count=_TEST_MIN_CELL_COUNT,
    )

    assert len(features) == 1
    assert features[0].kind == "ridge"
    assert features[0].source_id == 3
    assert stats.ridge_feature_count == 1
    assert stats.valley_feature_count == 0
    assert stats.ridge_cell_count == 5
    assert stats.valley_cell_count == 0
    assert stats.cells_classified == (grid.n_rows - 2) * (grid.n_cols - 2)


def test_ingest_terrain_respects_min_cell_count() -> None:
    grid = _ridge_grid()

    features, stats = ingest_terrain(
        grid, source_id=3, curvature_threshold_m=_TEST_THRESHOLD_M, min_cell_count=6
    )

    assert features == []
    assert stats.ridge_feature_count == 0
    # Cells are still classified even when no component survives the size
    # filter -- min_cell_count only prunes components, not classification.
    assert stats.ridge_cell_count == 5


def test_ingest_terrain_respects_curvature_threshold() -> None:
    grid = _ridge_grid()

    # A threshold far above the fixture's curvature magnitude means nothing
    # is classified as ridge/valley at all.
    features, stats = ingest_terrain(grid, source_id=3, curvature_threshold_m=1000.0)

    assert features == []
    assert stats.ridge_cell_count == 0
    assert stats.valley_cell_count == 0
