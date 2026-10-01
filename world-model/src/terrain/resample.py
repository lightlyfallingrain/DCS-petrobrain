"""Vectorised resampling of one or more SRTM tiles onto a DCS-metre
lattice -- part of `plans/landform-geomorphons/plan.md` design decision 1.

Replaces `build.ingest_srtm.ingest_srtm_grid`'s per-cell Python loop
(`dcs_to_wgs84` + `select_tile` + `height_at`, ~2.2 microsec/cell measured)
for this module's own, much finer-grained (~90m) lattice, where a tile's
worth of cells (~1.5M for a 1x1 degree window at that spacing) would make
the per-cell loop the dominant pipeline cost. The whole lattice's DCS x/z
-> lat/lon conversion is one `coordinates.dcs_to_wgs84_array` call;
bilinear sampling from each covering tile's own `array('h')` buffer
(reshaped once to a 2-D numpy array) is a handful of vectorised
fancy-indexing operations, not a per-point `SrtmTile.height_at` call. Not
a new dependency -- `elevation.dem.SrtmTile`'s own interpolation math,
restated over arrays.
"""

import numpy as np
import numpy.typing as npt

from coordinates import dcs_to_wgs84_array
from elevation.dem import SrtmTile

# Mirrors `elevation.dem._VOID` -- the `.hgt` void marker. Duplicated
# rather than imported (that name is private to `elevation.dem`); both
# values must always agree with the format's own `-32768` convention, not
# with each other by coincidence.
_VOID_SAMPLE = -32768


def lattice_coords(
    origin_x: float, origin_z: float, spacing_m: float, n_rows: int, n_cols: int
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """`(xx, zz)`, each shape `(n_rows, n_cols)`: the DCS x/z coordinate of
    every lattice cell, cell `(row, col)` at `(origin_x + row * spacing_m,
    origin_z + col * spacing_m)` -- the same convention `store.models.
    ElevationGrid` and `build.ingest_srtm` already use."""
    rows = np.arange(n_rows, dtype=np.float64)
    cols = np.arange(n_cols, dtype=np.float64)
    xx, zz = np.meshgrid(
        origin_x + rows * spacing_m, origin_z + cols * spacing_m, indexing="ij"
    )
    return xx, zz


def sample_tiles_bilinear(
    tiles: list[SrtmTile],
    lat: npt.NDArray[np.float64],
    lon: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Bilinearly-interpolated elevation at every `(lat, lon)` pair (same
    shape, broadcast together), vectorised across `tiles` -- the array
    counterpart of `elevation.dem.select_tile` + `SrtmTile.height_at`.

    A point outside every tile's bbox, or whose 4 bilinear-interpolation
    corners include a data void, is `NaN` -- never fabricated, matching
    `SrtmTile.height_at`'s own `ValueError`-on-void contract (here, "raise"
    becomes "leave as NaN", since a lattice is expected to run to
    completion over a whole window). A point covered by more than one
    tile (only possible exactly on a shared tile edge) is sampled from
    whichever tile is first in `tiles`, same arbitrary-but-deterministic
    tie-break `select_tile`'s linear scan already has.
    """
    out = np.full(lat.shape, np.nan, dtype=np.float64)
    remaining = np.ones(lat.shape, dtype=np.bool_)

    for tile in tiles:
        if not remaining.any():
            break
        north_lat = tile.sw_lat + tile.span_deg
        east_lon = tile.sw_lon + tile.span_deg
        covered = (
            remaining
            & (lat >= tile.sw_lat)
            & (lat <= north_lat)
            & (lon >= tile.sw_lon)
            & (lon <= east_lon)
        )
        if not covered.any():
            continue

        grid = np.asarray(tile.samples, dtype=np.int64).reshape(tile.size, tile.size)

        lat_c = lat[covered]
        lon_c = lon[covered]
        row_f = (north_lat - lat_c) * (tile.size - 1) / tile.span_deg
        col_f = (lon_c - tile.sw_lon) * (tile.size - 1) / tile.span_deg
        row0 = np.minimum(row_f.astype(np.int64), tile.size - 2)
        col0 = np.minimum(col_f.astype(np.int64), tile.size - 2)
        row1 = row0 + 1
        col1 = col0 + 1
        frac_row = row_f - row0
        frac_col = col_f - col0

        corner00 = grid[row0, col0].astype(np.float64)
        corner01 = grid[row0, col1].astype(np.float64)
        corner10 = grid[row1, col0].astype(np.float64)
        corner11 = grid[row1, col1].astype(np.float64)
        has_void = (
            (corner00 == _VOID_SAMPLE)
            | (corner01 == _VOID_SAMPLE)
            | (corner10 == _VOID_SAMPLE)
            | (corner11 == _VOID_SAMPLE)
        )

        top = corner00 * (1 - frac_col) + corner01 * frac_col
        bottom = corner10 * (1 - frac_col) + corner11 * frac_col
        value = top * (1 - frac_row) + bottom * frac_row
        value = np.where(has_void, np.nan, value)

        out_flat = out.reshape(-1)
        covered_flat_idx = np.flatnonzero(covered.reshape(-1))
        out_flat[covered_flat_idx] = value
        remaining &= ~covered

    return out


def resample_window(
    tiles: list[SrtmTile],
    theatre: str,
    origin_x: float,
    origin_z: float,
    spacing_m: float,
    n_rows: int,
    n_cols: int,
) -> npt.NDArray[np.float64]:
    """The whole-window counterpart of `build.ingest_srtm.ingest_srtm_grid`,
    for this module's finer lattice: builds the `(n_rows, n_cols)` DCS-metre
    lattice described by `origin_x`/`origin_z`/`spacing_m`, converts every
    cell to lat/lon in one vectorised call, and bilinearly samples `tiles`.
    Returns a plain `float64` array, `NaN` where no tile covers a cell or a
    void was hit -- `terrain.geomorphons.geomorphons`'s own input
    convention."""
    xx, zz = lattice_coords(origin_x, origin_z, spacing_m, n_rows, n_cols)
    lat, lon = dcs_to_wgs84_array(theatre, xx, zz)
    return sample_tiles_bilinear(tiles, lat, lon)
