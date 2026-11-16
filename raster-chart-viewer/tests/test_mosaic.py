"""Pins the sheet-mosaic convention against the research note's exact
Syria 32m sheet set. Any future change to `mosaic.py`'s formula must fail
`test_syria_32m_sheet_mosaic_convention` first (plan, "The universal
filename grammar and tile-grid math")."""

from __future__ import annotations

from raster_chart_viewer.mosaic import MosaicGrid
from raster_chart_viewer.tilename import TileKey


def test_syria_32m_sheet_mosaic_convention() -> None:
    # Research note section E: sheets {aa, ab, xab, xac} x levels
    # {-2, -1, 00, 01}, every one full 8x8 -- one representative tile
    # per sheet/level corner is enough to pin the *macro* ordering; the
    # within-sheet x/z placement is checked separately below.
    keys = [
        TileKey(scale_m=32, sheet=sheet, level=level, x=0, z=0)
        for sheet in ("aa", "ab", "xab", "xac")
        for level in (-2, -1, 0, 1)
    ]
    grid = MosaicGrid(keys)

    # Columns, west -> east: level -2, -1, 00, 01. Rows, north -> south:
    # ab, aa, xab, xac. Every (sheet, level) combination must land at
    # exactly its (row, col) under that convention -- not just one axis
    # checked in isolation. All test tiles sit at the sheet's own (x=0,
    # z=0) corner, so each sheet/level block's origin cell is at
    # (sheet_col * 8, sheet_row * 8).
    expected_sheet_col_by_level = {-2: 0, -1: 1, 0: 2, 1: 3}
    expected_sheet_row_by_sheet = {"ab": 0, "aa": 1, "xab": 2, "xac": 3}
    for sheet, expected_sheet_row in expected_sheet_row_by_sheet.items():
        for level, expected_sheet_col in expected_sheet_col_by_level.items():
            key = TileKey(scale_m=32, sheet=sheet, level=level, x=0, z=0)
            assert grid.key_at(expected_sheet_col * 8, expected_sheet_row * 8) == key


def test_within_sheet_x_is_row_z_is_column() -> None:
    # Research note section E, "inside a sheet": z increases east
    # (column), x increases south (row).
    sheet_level_keys = [
        TileKey(scale_m=32, sheet="aa", level=0, x=x, z=z)
        for x in range(8)
        for z in range(8)
    ]
    grid = MosaicGrid(sheet_level_keys)
    # A single sheet at the origin level/row -> grid coords equal (z, x).
    for x in range(8):
        for z in range(8):
            key = TileKey(scale_m=32, sheet="aa", level=0, x=x, z=z)
            assert grid.key_at(z, x) == key


def test_sparse_sheet_leaves_blank_gaps_not_an_error() -> None:
    # A partial sheet (Mariana-style, research note section B) must not
    # raise, and must leave the ungoverned cells as None.
    keys = [
        TileKey(scale_m=16, sheet="ac", level=0, x=x, z=z)
        for x in range(1, 7)
        for z in range(4, 8)
    ]
    grid = MosaicGrid(keys)
    assert grid.key_at(4, 1) is not None  # (z=4, x=1) is present
    assert grid.key_at(0, 0) is None  # (z=0, x=0) was never in range


def test_max_level_from_grid_extent() -> None:
    # A single 8x8 sheet needs ceil(log2(8)) = 3 doublings to reach a
    # single full-mosaic tile.
    keys = [
        TileKey(scale_m=32, sheet="aa", level=0, x=x, z=z)
        for x in range(8)
        for z in range(8)
    ]
    grid = MosaicGrid(keys)
    assert grid.max_level == 3
    assert grid.tiles_wide == 8
    assert grid.tiles_tall == 8


def test_single_tile_grid_has_zero_max_level() -> None:
    grid = MosaicGrid([TileKey(scale_m=32, sheet="aa", level=0, x=0, z=0)])
    assert grid.max_level == 0
    assert grid.tiles_wide == 1
    assert grid.tiles_tall == 1
