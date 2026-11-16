from __future__ import annotations

from raster_chart_viewer.tilename import TileKey, parse_tile_name


def test_scale_underscore_variant() -> None:
    # Kola / Afghanistan's "xad" sheets / most of Mariana: "32m_aa00_x0_z0".
    assert parse_tile_name("32m_aa00_x0_z0.tif.dds") == TileKey(
        scale_m=32, sheet="aa", level=0, x=0, z=0
    )


def test_scale_no_underscore_variant() -> None:
    # Afghanistan's other sheets / all of Syria: "32mab00_x0_z0".
    assert parse_tile_name("32mab00_x0_z0.tif.dds") == TileKey(
        scale_m=32, sheet="ab", level=0, x=0, z=0
    )


def test_no_scale_prefix_variant() -> None:
    # 62 of Mariana's entries (U2) -- scale absent entirely.
    assert parse_tile_name("aa00_x5_z0.tif.dds") == TileKey(
        scale_m=None, sheet="aa", level=0, x=5, z=0
    )


def test_negative_level() -> None:
    assert parse_tile_name("xab-1_x0_z5.tif.dds") == TileKey(
        scale_m=None, sheet="xab", level=-1, x=0, z=5
    )


def test_case_insensitive() -> None:
    assert parse_tile_name("64MAA00_X1_Z6.TIF.DDS") == TileKey(
        scale_m=64, sheet="aa", level=0, x=1, z=6
    )


def test_sheet_lowercased() -> None:
    key = parse_tile_name("128mxAB-1_x2_z3.tif.dds")
    assert key is not None
    assert key.sheet == "xab"


def test_caucasus_inner_entry_no_underscore() -> None:
    assert parse_tile_name("64maa00_x1_z6.tif.dds") == TileKey(
        scale_m=64, sheet="aa", level=0, x=1, z=6
    )


def test_non_matching_name_returns_none() -> None:
    assert parse_tile_name("readme.txt") is None
    assert parse_tile_name("rasterCharts.sup5") is None
    assert parse_tile_name("32m_aa00_x0_z0.tif") is None  # missing .dds
