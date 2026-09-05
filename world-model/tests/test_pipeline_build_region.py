"""M7 Stage 1 wiring tests for `build.pipeline.build_region`: a rectangular
(non-square) region builds correctly, and an absent OSM cache is skipped
rather than required -- the two things Stage 1 changes about `build_region`
(`syria-full` is rectangular and, per the plan's clarification 2, has no
OSM cache at all).

`parse_towns_lua`/`parse_beacons_lua` are monkeypatched rather than reading
real files: both raise `ValueError` unless their input has *exactly*
`EXPECTED_TOWN_COUNT` (1,182) / `EXPECTED_BEACON_COUNT` (151) entries (a
deliberate DCS-format-drift guard, see `dcs_data.towns`/`dcs_data.beacons`
module docstrings), so a hand-written small fixture file cannot go through
the real parsers -- this module tests `build_region`'s wiring, not those
parsers, which already have their own fixture-based tests
(`test_towns_lua.py`, `test_beacons_lua.py`).
"""

import sqlite3
from array import array
from pathlib import Path

import pytest

from build.pipeline import build_region
from build.region import RegionDefinition
from dcs_data.towns import TownEntry
from store.reader import grid_provenance, load_full_grid

# A real towns.lua entry (world-model/research/2026-09-03-m5-recon.md
# Finding 17) whose DCS-projected position is known to fall well inside a
# region centred nearby -- see the Aleppo beacon control point in
# tests/control_points.py for the corresponding DCS x/z.
_ALEPPO_TOWN = TownEntry(
    name="Aleppo", display_name="Aleppo", lat=36.219471, lon=37.142091
)
_FAR_AWAY_TOWN = TownEntry(name="Nowhere", display_name="Nowhere", lat=0.0, lon=0.0)

# Centred near the Aleppo beacon control point (126175.3, 123040.0),
# generous enough to contain the Aleppo town entry above. Deliberately
# rectangular (unequal half-extents), the M7 Stage 0 generalization this
# test exercises -- every pre-M7 region was square.
_TEST_REGION = RegionDefinition(
    theatre="Syria",
    name="test-rectangular-region",
    centre_x=126175.3,
    centre_z=123040.0,
    half_extent_x_m=5000.0,
    half_extent_z_m=20000.0,
)


@pytest.fixture(autouse=True)
def _patch_parsers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "build.pipeline.parse_towns_lua",
        lambda path: [_ALEPPO_TOWN, _FAR_AWAY_TOWN],
    )
    monkeypatch.setattr("build.pipeline.parse_beacons_lua", lambda path: [])


def test_build_region_rectangular_region_without_osm_cache(tmp_path: Path) -> None:
    """The exact shape of an M7 `syria-full`-style build: a rectangular
    region, no `osm_cache_path`, no `routes_path`, no `probe_output_path`.
    Should build successfully, clip the far-away town, keep the in-region
    one, and report every optional layer as skipped rather than erroring."""
    report = build_region(
        _TEST_REGION,
        towns_lua_path=Path("unused-towns.lua"),
        beacons_lua_path=Path("unused-beacons.lua"),
        osm_cache_path=None,
        out_path=tmp_path / "test-rectangular-region.sqlite",
    )

    assert report.feature_counts["named_place"] == 1
    assert report.osm_skipped is True
    assert report.roadnet_skipped is True
    assert report.probe_skipped is True
    assert report.terrain_skipped is True
    assert report.srtm_skipped is True


def test_build_region_osm_cache_path_given_but_missing_is_skipped_not_an_error(
    tmp_path: Path,
) -> None:
    """A stale/nonexistent `--osm-cache` path degrades the same way a
    missing `--routes`/`--probe-output` already does -- skipped and
    reported, never a crash (mirrors `routes_path`'s existing "absence
    reported as absence" contract, see `build.pipeline` module docstring)."""
    report = build_region(
        _TEST_REGION,
        towns_lua_path=Path("unused-towns.lua"),
        beacons_lua_path=Path("unused-beacons.lua"),
        osm_cache_path=tmp_path / "does-not-exist.json",
        out_path=tmp_path / "test-rectangular-region-2.sqlite",
    )

    assert report.osm_skipped is True
    assert "road" not in report.feature_counts


def _write_fake_hgt_tile(path: Path, value: int) -> None:
    """A minimal (2x2, span exactly 1 degree by `SrtmTile.from_file`'s
    assumption) synthetic tile -- real SRTM tiles are much larger, but
    `SrtmTile.from_file` only requires the byte count to match a square
    16-bit grid, so this is a real, from_file-parseable tile, not a
    fabricated in-memory shortcut. Filename encodes sw_lat=36, sw_lon=37,
    covering 36-37N/37-38E -- squarely inside `_TEST_REGION`'s Aleppo-area
    footprint (see `_ALEPPO_TOWN`)."""
    samples = array("h", [value] * 4)
    if array("h", [1]).tobytes()[0] == 1:  # little-endian host
        samples.byteswap()  # .hgt samples are big-endian
    path.write_bytes(samples.tobytes())


def test_build_region_srtm_tile_paths_becomes_the_primary_elevation_grid(
    tmp_path: Path,
) -> None:
    """M7 Stage 2's wiring: `srtm_tile_paths` ingests SRTM as the region's
    primary `elevation` grid, provenance-tagged `"srtm"` -- independent of
    `probe_output_path` (absent here, so the DCS-probe path stays skipped,
    same as before this parameter existed)."""
    tile_path = tmp_path / "N36E037.hgt"
    _write_fake_hgt_tile(tile_path, value=250)
    out_path = tmp_path / "test-rectangular-region-srtm.sqlite"

    report = build_region(
        _TEST_REGION,
        towns_lua_path=Path("unused-towns.lua"),
        beacons_lua_path=Path("unused-beacons.lua"),
        osm_cache_path=None,
        out_path=out_path,
        srtm_tile_paths=[tile_path],
        srtm_grid_spacing_m=2000.0,
    )

    assert report.srtm_skipped is False
    assert report.srtm_stats is not None
    assert report.srtm_stats.points_sampled > 0
    # SRTM never runs M6's ridge/valley classifier -- locked out of M7.
    assert report.terrain_skipped is True

    conn = sqlite3.connect(f"file:{out_path}?mode=ro", uri=True)
    try:
        assert grid_provenance(conn, "elevation") == "srtm"
        grid = load_full_grid(conn, "elevation")
        assert grid is not None
        assert grid.provenance == "srtm"
        assert any(
            value == pytest.approx(250.0)
            for row in grid.samples
            for value in row
            if value is not None
        )
    finally:
        conn.close()


def test_build_region_srtm_tile_paths_given_but_missing_is_skipped_not_an_error(
    tmp_path: Path,
) -> None:
    report = build_region(
        _TEST_REGION,
        towns_lua_path=Path("unused-towns.lua"),
        beacons_lua_path=Path("unused-beacons.lua"),
        osm_cache_path=None,
        out_path=tmp_path / "test-rectangular-region-srtm-missing.sqlite",
        srtm_tile_paths=[tmp_path / "does-not-exist.hgt"],
    )

    assert report.srtm_skipped is True
    assert report.srtm_stats is None
