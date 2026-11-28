"""Tests for `belief.terrain_ahead` -- BL-16 M3 (`plans/
flight-lift-vector/plan.md`, "M3 amendment", sections B/E)."""

from __future__ import annotations

import math

from belief.terrain_ahead import (
    MAX_TERRAIN_POINTS,
    TERRAIN_HALF_WIDTH_M,
    TERRAIN_STEP_M,
    TerrainGrid,
    build_terrain_relay,
    compose_terrain_grid,
)


class TestComposeTerrainGrid:
    #: `TERRAIN_STEP_M`/`TERRAIN_HALF_WIDTH_M` both default to 200.0 --
    #: equal, so an axis swap would read identically on the default
    #: numbers. Every heading test below monkeypatches them to distinct
    #: values first, so a row-distance/column-width (or an axis) swap
    #: fails loudly instead of passing by coincidence.
    @staticmethod
    def _with_distinct_geometry(step: float, half_width: float) -> None:
        import belief.terrain_ahead as terrain_ahead_module

        terrain_ahead_module.TERRAIN_STEP_M = step
        terrain_ahead_module.TERRAIN_HALF_WIDTH_M = half_width

    def test_heading_zero_rows_run_north_columns_east_west(self) -> None:
        """Heading 0 (true north): the nose is `(cos 0, sin 0) = (1, 0)`
        in this project's `x` north / `z` east convention, so rows
        advance in `+x`; the right vector is `(-sin 0, cos 0) = (0, 1)`,
        so the positive-offset column sits at `+z` (east)."""
        import belief.terrain_ahead as terrain_ahead_module

        self._with_distinct_geometry(step=300.0, half_width=150.0)
        try:
            grid = terrain_ahead_module.compose_terrain_grid(
                x=0.0, z=0.0, heading_true_deg=0.0, seq=1
            )
        finally:
            self._with_distinct_geometry(TERRAIN_STEP_M, TERRAIN_HALF_WIDTH_M)
        assert grid.seq == 1
        # Point 0 is the control point beneath the aircraft.
        assert grid.points[0] == (0, 0)
        # Row 1 (at the step, 300), centre column.
        assert grid.points[1] == (300, 0)
        # Row 1, the two side columns: +-150 (half-width) in z, not the
        # step -- a swapped axis or a swapped constant both fail this.
        assert grid.points[2] == (300, -150)
        assert grid.points[3] == (300, 150)

    def test_heading_90_rows_run_east_columns_south_north(self) -> None:
        """Heading 90 (true east): nose is `(cos 90, sin 90) = (0, 1)`
        (rows advance in `+z`); right vector is `(-sin 90, cos 90) =
        (-1, 0)` (south in `x`) -- the recon note's own vector would
        have been `(sin 90, -cos 90) = (1, 0)` (north), the left one
        (M3 amendment, finding 8)."""
        import belief.terrain_ahead as terrain_ahead_module

        self._with_distinct_geometry(step=300.0, half_width=150.0)
        try:
            grid = terrain_ahead_module.compose_terrain_grid(
                x=0.0, z=0.0, heading_true_deg=90.0, seq=2
            )
        finally:
            self._with_distinct_geometry(TERRAIN_STEP_M, TERRAIN_HALF_WIDTH_M)
        assert grid.points[0] == (0, 0)
        assert grid.points[1] == (0, 300)
        # Side columns: +-150 (half-width) along (-1, 0) -- negative
        # offset goes to +x (south), positive offset goes to -x (north).
        assert grid.points[2] == (150, 300)
        assert grid.points[3] == (-150, 300)

    def test_default_geometry_is_sixteen_points_never_coarsened(self) -> None:
        """The user's own default numbers (1 km / 200 m step, +-200 m
        half-width) never reach `MAX_TERRAIN_POINTS` -- 1 + 5*3 = 16."""
        grid = compose_terrain_grid(x=100.0, z=-50.0, heading_true_deg=45.0, seq=3)
        assert len(grid.points) == 16

    def test_coarsens_rather_than_truncates_past_the_cap(self) -> None:
        """A geometry that would exceed `MAX_TERRAIN_POINTS` coarsens
        its rows (doubles the step) rather than silently dropping the
        far ones -- confirmed by monkeypatching the module's own
        constants to force the overflow."""
        import belief.terrain_ahead as terrain_ahead_module

        original_step = terrain_ahead_module.TERRAIN_STEP_M
        original_lookahead = terrain_ahead_module.TERRAIN_LOOKAHEAD_M
        try:
            # 1 + 20*3 = 61 points at the narrow step -- well past the
            # 32-point cap, forcing at least one coarsening pass.
            terrain_ahead_module.TERRAIN_STEP_M = 50.0
            terrain_ahead_module.TERRAIN_LOOKAHEAD_M = 1000.0
            grid = terrain_ahead_module.compose_terrain_grid(
                x=0.0, z=0.0, heading_true_deg=0.0, seq=4
            )
        finally:
            terrain_ahead_module.TERRAIN_STEP_M = original_step
            terrain_ahead_module.TERRAIN_LOOKAHEAD_M = original_lookahead
        assert len(grid.points) <= MAX_TERRAIN_POINTS
        # Still reaches out to (near) the full configured lookahead --
        # the far rows were coarsened, not dropped.
        farthest_x = max(p[0] for p in grid.points)
        assert farthest_x > 900

    def test_control_point_is_always_first(self) -> None:
        grid = compose_terrain_grid(x=12.0, z=-34.0, heading_true_deg=123.0, seq=5)
        assert grid.points[0] == (12, -34)


class TestBuildTerrainRelay:
    def test_encodes_seq_and_finite_heights(self) -> None:
        grid = TerrainGrid(seq=7, points=((0, 0), (100, 0), (100, 200)))
        relay = build_terrain_relay(
            grid,
            (10.0, 20.5, None),
            received_wall_clock_s=1000.0,
            now_wall_clock_s=1000.5,
        )
        assert relay == "7|0,0,10.00;100,0,20.50"

    def test_missing_height_is_omitted_not_zero(self) -> None:
        """A missing height must be dropped, never substituted with
        `0.0` (which would read as low ground and suppress a climb)."""
        grid = TerrainGrid(seq=1, points=((0, 0), (100, 0)))
        relay = build_terrain_relay(
            grid, (None, 5.0), received_wall_clock_s=0.0, now_wall_clock_s=0.0
        )
        assert relay == "1|100,0,5.00"
        assert "0,0,0" not in relay

    def test_non_numeric_or_bool_height_is_dropped_not_a_crash(self) -> None:
        """A height crossed an HTTP/JSON boundary to reach this function
        -- a malformed response (a string, or a JSON `true`) must not
        raise inside `math.isfinite`, same boundary-float standing rule
        every other wire read in this project follows."""
        grid = TerrainGrid(seq=1, points=((0, 0), (100, 0), (200, 0)))
        relay = build_terrain_relay(
            grid,
            ("not_a_number", True, 5.0),  # type: ignore[arg-type]
            received_wall_clock_s=0.0,
            now_wall_clock_s=0.0,
        )
        assert relay == "1|200,0,5.00"

    def test_non_finite_height_is_dropped(self) -> None:
        grid = TerrainGrid(seq=1, points=((0, 0), (100, 0), (200, 0)))
        relay = build_terrain_relay(
            grid,
            (math.nan, math.inf, 5.0),
            received_wall_clock_s=0.0,
            now_wall_clock_s=0.0,
        )
        assert relay == "1|200,0,5.00"

    def test_no_grid_relays_empty(self) -> None:
        assert (
            build_terrain_relay(
                None, None, received_wall_clock_s=None, now_wall_clock_s=0.0
            )
            == ""
        )

    def test_no_heights_relays_empty(self) -> None:
        grid = TerrainGrid(seq=1, points=((0, 0),))
        assert (
            build_terrain_relay(
                grid, None, received_wall_clock_s=0.0, now_wall_clock_s=0.0
            )
            == ""
        )

    def test_stale_grid_relays_empty(self) -> None:
        grid = TerrainGrid(seq=1, points=((0, 0),))
        relay = build_terrain_relay(
            grid, (10.0,), received_wall_clock_s=0.0, now_wall_clock_s=10.0
        )
        assert relay == ""

    def test_all_heights_missing_relays_empty(self) -> None:
        grid = TerrainGrid(seq=1, points=((0, 0), (100, 0)))
        relay = build_terrain_relay(
            grid, (None, None), received_wall_clock_s=0.0, now_wall_clock_s=0.0
        )
        assert relay == ""
