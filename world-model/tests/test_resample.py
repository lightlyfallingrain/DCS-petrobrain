"""Tests for `terrain.resample` -- the vectorised DCS-lattice resampler,
plan design decision 1."""

from array import array
from pathlib import Path

import numpy as np
import pytest

from elevation.dem import SrtmTile
from terrain.resample import lattice_coords, resample_window, sample_tiles_bilinear


def _is_little_endian() -> bool:
    return array("h", [1]).tobytes()[0] == 1


def _write_tile(path: Path, size: int, value_fn: object) -> None:
    samples = array("h")
    for row in range(size):
        for col in range(size):
            samples.append(value_fn(row, col))  # type: ignore[operator]
    if _is_little_endian():
        samples.byteswap()
    path.write_bytes(samples.tobytes())


def test_lattice_coords_matches_the_documented_convention() -> None:
    xx, zz = lattice_coords(
        origin_x=100.0, origin_z=-50.0, spacing_m=10.0, n_rows=3, n_cols=2
    )

    assert xx.shape == (3, 2)
    assert zz.shape == (3, 2)
    assert xx[0, 0] == pytest.approx(100.0)
    assert zz[0, 0] == pytest.approx(-50.0)
    assert xx[2, 0] == pytest.approx(120.0)
    assert zz[0, 1] == pytest.approx(-40.0)


def test_sample_tiles_bilinear_flat_tile_returns_constant_value(tmp_path: Path) -> None:
    tile_path = tmp_path / "N36E037.hgt"
    _write_tile(tile_path, size=3, value_fn=lambda r, c: 500)
    tile = SrtmTile.from_file(tile_path)

    lat = np.array([36.5, 36.1, 36.9])
    lon = np.array([37.5, 37.1, 37.9])

    values = sample_tiles_bilinear([tile], lat, lon)

    assert np.allclose(values, 500.0)


def test_sample_tiles_bilinear_outside_every_tile_is_nan(tmp_path: Path) -> None:
    tile_path = tmp_path / "N36E037.hgt"
    _write_tile(tile_path, size=3, value_fn=lambda r, c: 500)
    tile = SrtmTile.from_file(tile_path)

    lat = np.array([10.0])
    lon = np.array([10.0])

    values = sample_tiles_bilinear([tile], lat, lon)

    assert np.isnan(values[0])


def test_sample_tiles_bilinear_void_corner_is_nan(tmp_path: Path) -> None:
    tile_path = tmp_path / "N36E037.hgt"
    # A 3x3 tile with one void (-32768) corner.
    values_grid = [[500, 500, 500], [500, 500, 500], [-32768, 500, 500]]
    samples = array("h", [v for row in values_grid for v in row])
    if _is_little_endian():
        samples.byteswap()
    tile_path.write_bytes(samples.tobytes())
    tile = SrtmTile.from_file(tile_path)

    # Bottom-left corner of the tile (sw_lat, sw_lon) -- its bilinear
    # interpolation cell includes the void sample.
    lat = np.array([36.001])
    lon = np.array([37.001])

    values = sample_tiles_bilinear([tile], lat, lon)

    assert np.isnan(values[0])


def test_sample_tiles_bilinear_matches_scalar_height_at(tmp_path: Path) -> None:
    tile_path = tmp_path / "N36E037.hgt"
    _write_tile(tile_path, size=5, value_fn=lambda r, c: 100 * r + 10 * c)
    tile = SrtmTile.from_file(tile_path)

    lat = np.array([36.37, 36.61])
    lon = np.array([37.22, 37.84])

    values = sample_tiles_bilinear([tile], lat, lon)
    expected = [tile.height_at(float(lat[i]), float(lon[i])) for i in range(2)]

    assert values == pytest.approx(expected)


def test_resample_window_end_to_end(tmp_path: Path) -> None:
    tile_path = tmp_path / "N36E037.hgt"
    _write_tile(tile_path, size=5, value_fn=lambda r, c: 1000)
    tile = SrtmTile.from_file(tile_path)

    dem = resample_window(
        [tile],
        theatre="Syria",
        origin_x=100000.0,
        origin_z=100000.0,
        spacing_m=1000.0,
        n_rows=4,
        n_cols=4,
    )

    assert dem.shape == (4, 4)
