from __future__ import annotations

from pathlib import Path

from fixtures.fake_terrain_trees import (
    build_caucasus_style_terrain,
    build_single_zip_terrain,
    full_sheet_entries,
    tile_entry_name,
)

from raster_chart_viewer.discovery import discover_terrains, read_tile_bytes
from raster_chart_viewer.tilename import TileKey


def _placeholder(x: int, z: int) -> bytes:
    # Discovery/indexing never decodes a tile -- only entry names matter
    # here, so the bytes can be anything distinguishable for assertions.
    return f"x{x}z{z}".encode()


def test_single_zip_layout_discovers_every_tier(tmp_path: Path) -> None:
    entries = {
        **full_sheet_entries(32, "aa", 0, _placeholder),
        **full_sheet_entries(64, "aa", 0, _placeholder),
    }
    build_single_zip_terrain(tmp_path, "Syria", entries)

    terrains = discover_terrains(tmp_path)
    assert set(terrains) == {"Syria"}
    syria = terrains["Syria"]
    assert set(syria.tiers) == {32, 64}
    assert syria.tier_labels() == ["32m", "64m"]
    assert len(syria.tiers[32]) == 64
    assert len(syria.tiers[64]) == 64


def test_single_zip_layout_reads_real_bytes(tmp_path: Path) -> None:
    entries = full_sheet_entries(32, "aa", 0, _placeholder)
    build_single_zip_terrain(tmp_path, "Syria", entries)

    terrains = discover_terrains(tmp_path)
    key = TileKey(scale_m=32, sheet="aa", level=0, x=3, z=5)
    location = terrains["Syria"].tiers[32][key]
    assert read_tile_bytes(location) == _placeholder(3, 5)


def test_no_scale_prefix_tiles_become_unscaled_tier(tmp_path: Path) -> None:
    # U2: Mariana's 62 scale-less entries become their own "unscaled"
    # tier, not dropped.
    entries = {
        tile_entry_name(None, "aa", -1, 0, 0): _placeholder(0, 0),
        tile_entry_name(None, "aa", -1, 1, 2): _placeholder(1, 2),
        **full_sheet_entries(16, "ac", 0, _placeholder),
    }
    build_single_zip_terrain(tmp_path, "MarianaIslands", entries)

    terrains = discover_terrains(tmp_path)
    mariana = terrains["MarianaIslands"]
    assert mariana.tier_labels() == ["16m", "unscaled"]
    unscaled = mariana.tiles_for_label("unscaled")
    assert unscaled is not None
    assert len(unscaled) == 2
    assert TileKey(scale_m=None, sheet="aa", level=-1, x=0, z=0) in unscaled


def test_sparse_sheet_is_not_an_error(tmp_path: Path) -> None:
    # Mariana-style partial sheet coverage (research note section B).
    entries = full_sheet_entries(
        16, "ac", 0, _placeholder, x_range=range(1, 7), z_range=range(4, 8)
    )
    build_single_zip_terrain(tmp_path, "MarianaIslands", entries)

    terrains = discover_terrains(tmp_path)
    tiles = terrains["MarianaIslands"].tiers[16]
    # 6 x 4 rectangle (x1-6, z4-7) -- a simplified stand-in for the real
    # ac00 sheet's 22-tile, non-rectangular partial coverage (research
    # note section B); the point here is only that a sheet short of 64
    # tiles discovers cleanly, not that the shape matches exactly.
    assert len(tiles) == 24
    assert TileKey(scale_m=16, sheet="ac", level=0, x=0, z=0) not in tiles


def test_caucasus_zip_per_sheet_layout(tmp_path: Path) -> None:
    # Caucasus: no root zip, many small per-sheet zips nested under a
    # scale subfolder. The scale/sheet come from the inner entry names,
    # never the zip's own filename -- deliberately spelled inconsistently
    # here (case/underscore), mirroring the real terrain (research note
    # section D).
    build_caucasus_style_terrain(
        tmp_path,
        "Caucasus",
        {
            "0.25M/16m_AA-1.zip": full_sheet_entries(16, "aa", -1, _placeholder),
            "0.5M/32M_AG00.zip": full_sheet_entries(32, "ag", 0, _placeholder),
            "1M/64maa00.zip": full_sheet_entries(64, "aa", 0, _placeholder),
        },
    )

    terrains = discover_terrains(tmp_path)
    assert set(terrains) == {"Caucasus"}
    caucasus = terrains["Caucasus"]
    assert caucasus.tier_labels() == ["16m", "32m", "64m"]
    assert len(caucasus.tiers[16]) == 64
    assert len(caucasus.tiers[32]) == 64
    assert len(caucasus.tiers[64]) == 64


def test_terrain_with_no_rastercharts_dir_is_absent(tmp_path: Path) -> None:
    terrains_root = tmp_path / "Mods" / "terrains" / "SomeTerrainStub"
    terrains_root.mkdir(parents=True)
    (terrains_root / "entry.lua").write_text("-- stub\n")

    terrains = discover_terrains(tmp_path)
    assert terrains == {}


def test_missing_mods_terrains_dir_returns_empty(tmp_path: Path) -> None:
    assert discover_terrains(tmp_path) == {}
