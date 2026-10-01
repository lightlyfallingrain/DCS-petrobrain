"""Tests for `terrain.features`: basin growth (`grow_basins`), divide/ridge
gating (`qualifying_ridges`) and basin/valley gating (`qualifying_valleys`),
and the `extract_components`/`to_stored_features` wiring over them.

Rewritten (not extended) for the marker-controlled-watershed mechanism --
user-approved, per `plans/terrain-feature-probing/plan.md`'s "Decisions
Requiring User Input": `extract_components` used to group
`curvature.classify_curvature`'s per-cell output; it now gates and extracts
geometry from `grow_basins`'s basins.

Fixture: a 7-row x 13-col grid whose elevation depends only on column (so
every row is identical), built so a *deterministic* two-basin, one-ridge
split falls out of `grow_basins`'s ascending-elevation growth with no tied
elevations anywhere (ties would make which basin claims a contested cell
depend on arbitrary heap ordering, which this suite deliberately avoids by
constructing a strictly-monotonic-on-each-side profile):

    col:   0    1   2   3  4    5    6    7  8   9   10   11   12
    elev: 290  180  95  45  0  130  300  140 10  55  110  210  310

Basin A seeds at col 4 (floor 0), basin B at col 8 (floor 10); the single
peak at col 6 (300) is the dividing ridge. Column choice keeps every
basin's low-elevation "core" a clean rectangular, 4-connected block (one
component), and the all-rows-identical construction makes every
`_principal_axis` covariance in this file have an *exactly* zero
cross-term (`cov_rc`) by symmetry -- picked deliberately so axis/width
assertions are exact values, not `pytest.approx` guesses, (see each
function's own comment for the by-hand derivation).
"""

import pytest

from store.models import ElevationGrid
from terrain.features import (
    GridCell,
    _axis_sliced_line,
    _build_component,
    extract_components,
    grow_basins,
    qualifying_ridges,
    qualifying_valleys,
    to_stored_features,
)

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

# Columns forming each basin's own low-elevation "core" at the default
# 0.5 core fraction, derived by hand from the profile above -- see the
# module docstring.
_BASIN_A_CORE_COLS = (2, 3, 4, 5)  # elevations <= 0 + 0.5*300 = 150
_BASIN_B_CORE_COLS = (7, 8, 9, 10)  # elevations <= 10 + 0.5*300 = 160


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


def _seeds() -> list[tuple[int, int]]:
    # Basin A's seed group is listed first, so grow_basins assigns it
    # basin id 0 and basin B id 1 (enumerate() order over _seed_groups,
    # which itself preserves `seeds`' own iteration order) -- deterministic,
    # not assumed.
    return [(row, 4) for row in range(_N_ROWS)] + [(row, 8) for row in range(_N_ROWS)]


def test_grow_basins_splits_the_profile_at_the_ridge() -> None:
    grid = _grid()

    labels, basins = grow_basins(grid, _seeds())

    assert len(basins) == 2
    basin_a = next(b for b in basins if labels[(0, 4)] == b.id)
    basin_b = next(b for b in basins if labels[(0, 8)] == b.id)
    assert basin_a.id != basin_b.id

    # Basin A claims columns 0-6 (up to and including the ridge peak, per
    # the module docstring's by-hand growth trace), basin B claims 7-12.
    for col in range(7):
        assert labels[(0, col)] == basin_a.id
    for col in range(7, 13):
        assert labels[(0, col)] == basin_b.id

    assert basin_a.min_elevation == pytest.approx(0.0)
    assert basin_a.max_elevation == pytest.approx(300.0)
    assert basin_b.min_elevation == pytest.approx(10.0)
    assert basin_b.max_elevation == pytest.approx(310.0)


def test_grow_basins_merges_adjacent_equal_minima_into_one_basin() -> None:
    # A 2-cell flat floor: both cells independently satisfy a seed test,
    # but they must grow into exactly one basin, not two racing for the
    # same plateau (point 3's "_seed_groups" merge).
    grid = ElevationGrid(
        origin_x=0.0,
        origin_z=0.0,
        spacing_m=_SPACING_M,
        n_rows=1,
        n_cols=4,
        source_id=None,
        provenance="srtm",
        stats={},
        samples=[[10.0, 0.0, 0.0, 10.0]],
    )

    _labels, basins = grow_basins(grid, seeds=[(0, 1), (0, 2)])

    assert len(basins) == 1
    assert basins[0].cells == [(0, 1), (0, 2), (0, 0), (0, 3)] or set(
        basins[0].cells
    ) == {(0, 0), (0, 1), (0, 2), (0, 3)}


def test_qualifying_ridges_recovers_the_single_divide() -> None:
    grid = _grid()
    labels, basins = grow_basins(grid, _seeds())
    basins_by_id = {b.id: b for b in basins}

    ridges = qualifying_ridges(
        grid, labels, basins_by_id, relief_threshold_m=80.0, min_cell_count=1
    )

    # Saddle = max(elev at col 6, elev at col 7) = max(300, 140) = 300;
    # lower basin floor = min(0, 10) = 0; relief 300 >= 80.
    assert len(ridges) == 1
    ridge = ridges[0]
    assert ridge.kind == "ridge"
    assert set(ridge.basin_ids) == {labels[(0, col)] for col in (4, 8)}
    assert ridge.elevation_range_m == pytest.approx((140.0, 300.0))
    # The boundary is columns 6 (x7 rows) and 7 (x7 rows) -- 14 cells, one
    # connected component (col6/col7 cells in the same row are
    # 4-adjacent).
    assert len(ridge.cells) == 14


def test_qualifying_ridges_uses_the_per_contact_saddle_not_the_naive_boundary_min() -> (
    None
):
    # Distinguishes the correct saddle formula (min over contact points of
    # max(elev on each side)) from the naive, rejected one (min over the
    # boundary's combined, mixed cell set) -- a 2026-10-01 review found the
    # shipped code computing the latter while `implementation.md` and this
    # module's own docstring claimed the former. The two formulas diverge
    # on this fixture's existing divide (columns 6/7): the naive min over
    # {elev(col6)=300, elev(col7)=140} is 140; the correct min-of-max over
    # contact pairs (col6, col7) is max(300, 140) = 300 (same derivation as
    # test_qualifying_ridges_recovers_the_single_divide's comment). A
    # threshold of 200 sits strictly between them: lower_floor = 0, so the
    # naive formula would reject (140 - 0 = 140 < 200) while the correct
    # formula accepts (300 - 0 = 300 >= 200). Pinning this at a threshold
    # the old test's 80.0 was too generous to reach is the point -- a test
    # that cannot fail under the wrong formula is not a test of this.
    grid = _grid()
    labels, basins = grow_basins(grid, _seeds())
    basins_by_id = {b.id: b for b in basins}

    ridges = qualifying_ridges(
        grid, labels, basins_by_id, relief_threshold_m=200.0, min_cell_count=1
    )

    assert len(ridges) == 1
    assert ridges[0].elevation_range_m == pytest.approx((140.0, 300.0))


def test_qualifying_ridges_rejects_a_divide_below_the_relief_threshold() -> None:
    grid = _grid()
    labels, basins = grow_basins(grid, _seeds())
    basins_by_id = {b.id: b for b in basins}

    ridges = qualifying_ridges(
        grid, labels, basins_by_id, relief_threshold_m=500.0, min_cell_count=1
    )

    assert ridges == []


def test_qualifying_valleys_recovers_both_basin_cores() -> None:
    grid = _grid()
    _labels, basins = grow_basins(grid, _seeds())

    valleys = qualifying_valleys(
        grid,
        basins,
        relief_threshold_m=80.0,
        width_ceiling_m=1000.0,
        min_cell_count=1,
        # Pinned independent of DEFAULT_VALLEY_CORE_FRACTION (a tuned
        # production value, not an algorithm control point) -- 0.5 is what
        # the module docstring's by-hand derivation of _BASIN_A/B_CORE_COLS
        # assumes.
        core_fraction=0.5,
    )

    assert len(valleys) == 2

    valley_a = next(v for v in valleys if v.elevation_range_m[0] == pytest.approx(0.0))
    valley_b = next(v for v in valleys if v.elevation_range_m[0] == pytest.approx(10.0))
    assert valley_a.kind == "valley"
    assert valley_a.elevation_range_m == pytest.approx((0.0, 130.0))
    assert valley_a.width_m == pytest.approx(
        300.0
    )  # 4 cols wide at 100 m spacing - 1 cell
    assert len(valley_a.cells) == len(_BASIN_A_CORE_COLS) * _N_ROWS

    assert valley_b.kind == "valley"
    assert valley_b.elevation_range_m == pytest.approx((10.0, 140.0))
    assert valley_b.width_m == pytest.approx(300.0)
    assert len(valley_b.cells) == len(_BASIN_B_CORE_COLS) * _N_ROWS


def test_qualifying_valleys_rejects_below_relief_threshold() -> None:
    grid = _grid()
    _labels, basins = grow_basins(grid, _seeds())

    valleys = qualifying_valleys(
        grid,
        basins,
        relief_threshold_m=500.0,
        width_ceiling_m=1000.0,
        min_cell_count=1,
    )

    assert valleys == []


def test_qualifying_valleys_rejects_above_width_ceiling() -> None:
    # The Bekaa-exclusion gate, structurally: a basin whose core is wider
    # than width_ceiling_m contributes no valley row, same as the plan's
    # "kilometres-wide flat bottom" rule -- here the computed core width
    # is 300 m, so a 250 m ceiling must reject both basins.
    grid = _grid()
    _labels, basins = grow_basins(grid, _seeds())

    valleys = qualifying_valleys(
        grid,
        basins,
        relief_threshold_m=80.0,
        width_ceiling_m=250.0,
        min_cell_count=1,
        core_fraction=0.5,  # see test_qualifying_valleys_recovers_both_basin_cores
    )

    assert valleys == []


def test_qualifying_functions_respect_min_cell_count() -> None:
    grid = _grid()
    labels, basins = grow_basins(grid, _seeds())
    basins_by_id = {b.id: b for b in basins}

    valleys = qualifying_valleys(
        grid,
        basins,
        relief_threshold_m=80.0,
        width_ceiling_m=1000.0,
        min_cell_count=100,
    )
    ridges = qualifying_ridges(
        grid, labels, basins_by_id, relief_threshold_m=80.0, min_cell_count=100
    )

    assert valleys == []
    assert ridges == []


def test_extract_components_combines_gated_valleys_and_ridges() -> None:
    grid = _grid()
    labels, basins = grow_basins(grid, _seeds())

    components = extract_components(
        grid,
        basins,
        labels,
        relief_threshold_m=80.0,
        width_ceiling_m=1000.0,
        min_cell_count=1,
        core_fraction=0.5,  # see test_qualifying_valleys_recovers_both_basin_cores
    )

    kinds = sorted(c.kind for c in components)
    assert kinds == ["ridge", "valley", "valley"]


def test_to_stored_features_shapes_tags_and_provenance() -> None:
    grid = _grid()
    labels, basins = grow_basins(grid, _seeds())
    components = extract_components(
        grid,
        basins,
        labels,
        relief_threshold_m=80.0,
        width_ceiling_m=1000.0,
        min_cell_count=1,
        core_fraction=0.5,  # see test_qualifying_valleys_recovers_both_basin_cores
    )

    features = to_stored_features(components, source_id=7, position_uncertainty_m=100.0)

    assert len(features) == 3
    for feature in features:
        assert feature.geom_type == "LineString"
        assert feature.provenance == {"geometry": "dcs_derived"}
        assert feature.confidence == {"geometry": "low"}
        assert feature.source_id == 7
        assert feature.position_uncertainty_m == 100.0
        assert "elevation_range_m" in feature.tags
        assert "orientation_deg" in feature.tags
        assert "cell_count" in feature.tags

    valley_features = [f for f in features if f.kind == "valley"]
    ridge_features = [f for f in features if f.kind == "ridge"]
    assert len(valley_features) == 2
    assert len(ridge_features) == 1
    for feature in valley_features:
        assert feature.tags["basin_width_m"] == pytest.approx(300.0)
    for feature in ridge_features:
        assert "basin_width_m" not in feature.tags
        # adjacent_feature_ids is Stage 3's -- not populated here.
        assert "adjacent_feature_ids" not in feature.tags


# --- `_axis_sliced_line`/`_build_component` degenerate-shape coverage ---
#
# A 2026-10-01 review found a plain 2x2 square component collapses to a
# single point: `round()`'s round-half-to-even sends both of a symmetric
# pair's +-0.5 axis projections to bin 0. None of the module's existing
# fixtures hit this -- they are deliberately asymmetric/monotonic to avoid
# tie ambiguity entirely (see the module docstring) -- so this section
# exercises `_axis_sliced_line`/`_build_component` directly, against the
# review's own reproduction plus the other degenerate shapes it named.


def _unit_test_grid() -> ElevationGrid:
    # 5x5, every cell a distinct elevation -- large enough to host every
    # shape below, distinct values so "pick the extreme" is unambiguous.
    samples: list[list[float | None]] = [
        [float(row * 5 + col) for col in range(5)] for row in range(5)
    ]
    return ElevationGrid(
        origin_x=0.0,
        origin_z=0.0,
        spacing_m=100.0,
        n_rows=5,
        n_cols=5,
        source_id=None,
        provenance="srtm",
        stats={},
        samples=samples,
    )


def test_axis_sliced_line_symmetric_square_no_longer_collapses_to_one_point() -> None:
    # The review's own reproduction: a plain 2x2 square, symmetric about its
    # own mean, used to collapse to exactly one point under round()'s
    # round-half-to-even tie-break.
    grid = _unit_test_grid()
    cells = [GridCell(0, 0), GridCell(0, 1), GridCell(1, 0), GridCell(1, 1)]

    points = _axis_sliced_line(grid, cells, kind="ridge")

    assert len(points) == 2
    component = _build_component(grid, cells, kind="ridge", basin_ids=(0, 1))
    assert len(component.points) == 2


def test_axis_sliced_line_single_cell_produces_exactly_one_point() -> None:
    # A single real sampled cell has only one position -- one point is the
    # correct, honest answer here, not a defect (unlike the multi-cell
    # collapse above). `_build_component`'s invariant guard only applies
    # from 2 input cells upward for exactly this reason.
    grid = _unit_test_grid()
    cells = [GridCell(2, 2)]

    points = _axis_sliced_line(grid, cells, kind="valley")

    assert points == [(200.0, 200.0)]


def test_axis_sliced_line_one_cell_wide_line_emits_one_point_per_cell() -> None:
    # A straight, one-cell-wide line: every cell sits at a distinct
    # along-axis position, so none of them should ever share a bin.
    grid = _unit_test_grid()
    cells = [GridCell(0, col) for col in range(4)]

    points = _axis_sliced_line(grid, cells, kind="ridge")

    assert len(points) == 4


def test_axis_sliced_line_symmetric_cross_merges_only_the_shared_minor_axis_cells() -> (
    None
):
    # A plus/cross shape: centre, up, down, left, right. Its principal axis
    # ties (cov_rr == cov_cc == 0.4, cov_rc == 0) and resolves to the row
    # axis, under which centre/left/right legitimately share one bin (same
    # row, differing only across the minor/column axis -- exactly what
    # binning is supposed to collapse), while up/down each keep their own.
    # Three cells correctly landing in one bin is the intended behaviour,
    # not the collapse the fix targets; distinguishing the two is the point
    # of this test (named explicitly by the review as "all cells landing
    # in one bin").
    grid = _unit_test_grid()
    cells = [
        GridCell(1, 1),  # centre
        GridCell(0, 1),  # up
        GridCell(2, 1),  # down
        GridCell(1, 0),  # left
        GridCell(1, 2),  # right
    ]

    points = _axis_sliced_line(grid, cells, kind="ridge")

    assert len(points) == 3
    component = _build_component(grid, cells, kind="ridge", basin_ids=(0, 1))
    assert len(component.points) == 3
