"""Tests for `build.ingest_srtm.ingest_srtm_grid`.

Reuses `test_ingest_probe.py`'s pattern: a small synthetic grid (not a real
41x41+ full-theatre grid) plus tiny uniform-value `SrtmTile`s, so expected
per-cell values are hand-verifiable without needing a real multi-megabyte
`.hgt` file. The tiles' `sw_lat`/`sw_lon`/`span_deg` cover the real lat/lon
envelope of the test grid's DCS points (via `coordinates.dcs_to_wgs84
("Syria", ...)`, a real transform -- only the tile *sample values* are
synthetic).
"""

from array import array

from build.ingest_srtm import GRID_PROVENANCE_SRTM, ingest_srtm_grid
from elevation.dem import SrtmTile

_ORIGIN_X = 0.0
_ORIGIN_Z = 0.0
_SPACING_M = 1000.0
_N_ROWS = 2
_N_COLS = 2


def _uniform_tile(
    sw_lat: float, sw_lon: float, span_deg: float, value: float
) -> SrtmTile:
    size = 3
    samples = array("h", [int(value)] * (size * size))
    return SrtmTile(
        sw_lat=sw_lat, sw_lon=sw_lon, size=size, samples=samples, span_deg=span_deg
    )


def test_ingest_srtm_grid_samples_every_cell_from_one_covering_tile() -> None:
    """All 4 DCS points ((0,0), (0,1000), (1000,0), (1000,1000)) fall inside
    a single generously-sized tile -- same coverage window
    `test_ingest_probe.py` uses (~35.0-35.03N, ~35.85-36.05E)."""
    tile = _uniform_tile(sw_lat=35.0, sw_lon=35.85, span_deg=0.2, value=100.0)

    grid, stats = ingest_srtm_grid(
        [tile], "Syria", _ORIGIN_X, _ORIGIN_Z, _SPACING_M, _N_ROWS, _N_COLS, source_id=1
    )

    assert grid.samples == [[100.0, 100.0], [100.0, 100.0]]
    assert grid.provenance == GRID_PROVENANCE_SRTM
    assert stats.points_expected == 4
    assert stats.points_sampled == 4
    assert stats.points_void_or_uncovered == 0
    assert stats.tiles_used == 1


def test_ingest_srtm_grid_selects_the_right_tile_per_cell() -> None:
    """A full theatre needs multiple tiles; each grid cell must be sampled
    from whichever tile actually covers it, not just the first tile in the
    list -- deliberately puts the covering tile *second* to catch a
    "always use tiles[0]" bug."""
    wrong_tile = _uniform_tile(sw_lat=0.0, sw_lon=0.0, span_deg=0.2, value=999.0)
    right_tile = _uniform_tile(sw_lat=35.0, sw_lon=35.85, span_deg=0.2, value=42.0)

    grid, stats = ingest_srtm_grid(
        [wrong_tile, right_tile],
        "Syria",
        _ORIGIN_X,
        _ORIGIN_Z,
        _SPACING_M,
        _N_ROWS,
        _N_COLS,
        source_id=1,
    )

    assert grid.samples == [[42.0, 42.0], [42.0, 42.0]]
    assert stats.tiles_used == 1


def test_ingest_srtm_grid_leaves_uncovered_cells_none() -> None:
    """A cell whose (lat, lon) isn't covered by any given tile is left
    `None`, not silently guessed or zero-filled -- the same "absence
    reported as absence" contract every other ingest module follows."""
    tile = _uniform_tile(sw_lat=0.0, sw_lon=0.0, span_deg=0.2, value=999.0)

    grid, stats = ingest_srtm_grid(
        [tile], "Syria", _ORIGIN_X, _ORIGIN_Z, _SPACING_M, _N_ROWS, _N_COLS, source_id=1
    )

    assert grid.samples == [[None, None], [None, None]]
    assert stats.points_sampled == 0
    assert stats.points_void_or_uncovered == 4
    assert stats.tiles_used == 0


def test_ingest_srtm_grid_leaves_void_samples_none() -> None:
    """A cell landing on a SRTM data void (`-32768`) is left `None`, same as
    an uncovered cell -- `SrtmTile.height_at` raises `ValueError` for a
    void, which this module must catch rather than propagate (a full-theatre
    grid should run to completion even with some void coverage)."""
    size = 3
    void_samples = array("h", [-32768] * (size * size))
    void_tile = SrtmTile(
        sw_lat=35.0, sw_lon=35.85, size=size, samples=void_samples, span_deg=0.2
    )

    grid, stats = ingest_srtm_grid(
        [void_tile],
        "Syria",
        _ORIGIN_X,
        _ORIGIN_Z,
        _SPACING_M,
        _N_ROWS,
        _N_COLS,
        source_id=1,
    )

    assert grid.samples == [[None, None], [None, None]]
    assert stats.points_void_or_uncovered == 4
