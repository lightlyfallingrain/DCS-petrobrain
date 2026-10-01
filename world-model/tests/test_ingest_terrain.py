"""Tests for `build.ingest_terrain.ingest_terrain`/`ingest_terrain_chunk`:
the wiring that runs Stage 1's full pipeline (`curvature.smooth_grid` ->
`curvature.find_basin_seeds` -> `features.grow_basins` -> `features.
extract_components`) over an already-loaded `ElevationGrid` and returns the
`(StoredFeature list, stats)` shape `build.pipeline.build_region` inserts.

Rewritten (not extended) for the marker-controlled-watershed mechanism --
user-approved, per `plans/terrain-feature-probing/plan.md`'s "Decisions
Requiring User Input": `ingest_terrain` used to take a curvature threshold
and min-cell-count; it now takes the smoothing window, seed footprint,
relief threshold, width ceiling, and (basin) min-cell-count.

Reuses `test_terrain_features.py`'s two-basin, one-ridge profile fixture
(see that module's docstring for the by-hand derivation) with
`smoothing_window_cells=1` throughout -- a 1x1 "window" is an identity
transform, so this fixture's hand-derived basin/ridge numbers carry over
unchanged. This module tests wiring (parameter plumbing, stats bookkeeping),
not the algorithm itself, which `test_terrain_curvature.py`/
`test_terrain_features.py` already cover.
"""

from build.ingest_terrain import ingest_terrain
from store.models import ElevationGrid

_SPACING_M = 100.0
_N_ROWS = 7
_PROFILE = [
    290.0,
    180.0,
    95.0,
    45.0,
    0.0,
    130.0,
    300.0,
    140.0,
    10.0,
    55.0,
    110.0,
    210.0,
    310.0,
]
_N_COLS = len(_PROFILE)


def _grid() -> ElevationGrid:
    samples: list[list[float | None]] = [list(_PROFILE) for _ in range(_N_ROWS)]
    return ElevationGrid(
        origin_x=0.0,
        origin_z=0.0,
        spacing_m=_SPACING_M,
        n_rows=_N_ROWS,
        n_cols=_N_COLS,
        source_id=None,
        provenance="srtm",
        stats={},
        samples=samples,
    )


def test_ingest_terrain_produces_two_valleys_and_one_ridge() -> None:
    grid = _grid()

    features, stats = ingest_terrain(
        grid,
        source_id=3,
        smoothing_window_cells=1,
        seed_footprint_cells=3,
        relief_threshold_m=80.0,
        width_ceiling_m=1000.0,
        min_cell_count=1,
    )

    assert stats.basin_count == 2
    assert stats.ridge_feature_count == 1
    assert stats.valley_feature_count == 2
    assert len(features) == 3
    assert all(f.source_id == 3 for f in features)


def test_ingest_terrain_respects_relief_threshold() -> None:
    grid = _grid()

    features, stats = ingest_terrain(
        grid,
        source_id=3,
        smoothing_window_cells=1,
        seed_footprint_cells=3,
        relief_threshold_m=500.0,  # above the fixture's 300 m relief
        width_ceiling_m=1000.0,
        min_cell_count=1,
    )

    assert features == []
    assert stats.ridge_feature_count == 0
    assert stats.valley_feature_count == 0
    # Basins are still grown even when nothing survives the relief gate --
    # the gate only prunes components, same discipline the old
    # min_cell_count test documented for curvature cells.
    assert stats.basin_count == 2


def test_ingest_terrain_respects_width_ceiling_independent_of_ridges() -> None:
    grid = _grid()

    features, stats = ingest_terrain(
        grid,
        source_id=3,
        smoothing_window_cells=1,
        seed_footprint_cells=3,
        relief_threshold_m=80.0,
        width_ceiling_m=-1.0,  # negative: no basin's core width can pass
        min_cell_count=1,
    )

    # Point 4: the width gate is valley-only. The ridge between the two
    # (both too-wide-for-valley) basins still qualifies.
    assert stats.valley_feature_count == 0
    assert stats.ridge_feature_count == 1
    assert len(features) == 1


def test_ingest_terrain_respects_min_cell_count() -> None:
    grid = _grid()

    features, stats = ingest_terrain(
        grid,
        source_id=3,
        smoothing_window_cells=1,
        seed_footprint_cells=3,
        relief_threshold_m=80.0,
        width_ceiling_m=1000.0,
        min_cell_count=100,  # larger than any component in the fixture
    )

    assert features == []
    assert stats.ridge_feature_count == 0
    assert stats.valley_feature_count == 0
    assert stats.basin_count == 2


def test_ingest_terrain_chunk_delegates_to_ingest_terrain() -> None:
    from build.ingest_terrain import ingest_terrain_chunk

    grid = _grid()

    features, stats = ingest_terrain_chunk(
        grid,
        source_id=3,
        smoothing_window_cells=1,
        seed_footprint_cells=3,
        relief_threshold_m=80.0,
        width_ceiling_m=1000.0,
        min_cell_count=1,
    )

    assert stats.ridge_feature_count == 1
    assert stats.valley_feature_count == 2
    assert len(features) == 3
