"""Reads a single SRTM `.hgt` tile and interpolates elevation at a point.

Format (per `world-model/research/2026-09-03-m4-elevation-recon.md` Finding
9): one file per 1x1 degree tile, named `<N|S><lat><E|W><lon>.hgt` for the
tile's south-west corner (e.g. `N39E036.hgt` covers 39-40N, 36-37E). Both
SRTM1 (1 arc-second, 3601x3601, ~30m) and SRTM3 (3 arc-second, 1201x1201,
~90m) use the same flat grid of big-endian signed 16-bit samples, row-major
starting at the tile's north-west corner, with `-32768` marking a data void
-- they differ only in grid resolution. `SrtmTile.from_file` derives the
grid size from the file's byte length rather than hardcoding either, so it
parses whichever resolution it's given. M4's actual tile (Stage 2,
`data/raw/dem/N39E036.hgt`) is SRTM3 (1201x1201, 2,884,802 bytes) -- the
user fetched 3 arc-second from viewfinderpanoramas.org, not the 1
arc-second the recon note anticipated; this module's dynamic sizing meant
no code change was needed to accommodate that. Parsed with stdlib
`array` only -- no GDAL/rasterio dependency, per the recon note's Finding 12
recommendation.

Source: `viewfinderpanoramas.org` no-login mirror (recon Finding 10) -- a
third-party-processed SRTM derivative, not the raw NASA product; see the
module docstring in `elevation/__init__.py` and the M4 research note for
provenance.
"""

import re
from array import array
from dataclasses import dataclass
from pathlib import Path

_VOID = -32768
_FILENAME_RE = re.compile(r"^([NS])(\d{2})([EW])(\d{3})\.hgt$", re.IGNORECASE)


@dataclass(frozen=True)
class SrtmTile:
    """One parsed SRTM `.hgt` tile (or a small real-data crop of one, for
    tests -- see `span_deg`).

    `sw_lat`/`sw_lon` are the grid's south-west corner. `samples` is the raw
    `size x size` grid, row-major from the *north-west* corner (row 0 =
    northmost). `span_deg` is the degrees spanned corner-to-corner -- always
    `1.0` for a real `.hgt` file (`from_file` always sets it that way, since
    SRTM tiles are always exactly 1x1 degree by format), but a test can
    construct a `SrtmTile` directly with a smaller `span_deg` to embed a
    small, literal, real-data crop (e.g. a 5x5 window around one control
    point) rather than an entire multi-megabyte tile -- see `test_dem_srtm.py`.
    """

    sw_lat: float
    sw_lon: float
    size: int
    samples: array  # type: ignore[type-arg]
    span_deg: float = 1.0

    @classmethod
    def from_file(cls, path: Path) -> "SrtmTile":
        """Parse a `.hgt` tile at `path`. Raises `ValueError` if the
        filename doesn't match SRTM naming or the file size doesn't match a
        square grid of 16-bit samples."""
        match = _FILENAME_RE.match(path.name)
        if match is None:
            raise ValueError(
                f"{path.name!r} doesn't match SRTM .hgt naming "
                "(<N|S><lat><E|W><lon>.hgt, e.g. N39E036.hgt)"
            )
        lat_sign = 1 if match.group(1).upper() == "N" else -1
        lon_sign = 1 if match.group(3).upper() == "E" else -1
        sw_lat = lat_sign * int(match.group(2))
        sw_lon = lon_sign * int(match.group(4))

        raw = path.read_bytes()
        sample_count = len(raw) // 2
        size = round(sample_count**0.5)
        if size * size * 2 != len(raw):
            raise ValueError(
                f"{path.name}: file size {len(raw)} bytes isn't a square "
                "grid of 16-bit samples"
            )

        samples = array("h")
        samples.frombytes(raw)
        if _is_little_endian():
            samples.byteswap()  # .hgt samples are big-endian

        return cls(
            sw_lat=float(sw_lat), sw_lon=float(sw_lon), size=size, samples=samples
        )

    def _row_col(self, lat: float, lon: float) -> tuple[float, float]:
        """Fractional (row, col) into `samples` for (lat, lon).

        Row 0 is the grid's north edge (sw_lat + span_deg), increasing
        southward; col 0 is the west edge (sw_lon), increasing eastward.
        Raises `ValueError` if (lat, lon) falls outside this grid.
        """
        north_lat = self.sw_lat + self.span_deg
        east_lon = self.sw_lon + self.span_deg
        if not (self.sw_lat <= lat <= north_lat and self.sw_lon <= lon <= east_lon):
            raise ValueError(
                f"({lat}, {lon}) falls outside tile "
                f"[{self.sw_lat}, {north_lat}] x [{self.sw_lon}, {east_lon}]"
            )
        row = (north_lat - lat) * (self.size - 1) / self.span_deg
        col = (lon - self.sw_lon) * (self.size - 1) / self.span_deg
        return row, col

    def _sample(self, row: int, col: int) -> int:
        return int(self.samples[row * self.size + col])

    def height_at(self, lat: float, lon: float) -> float:
        """Bilinearly interpolated elevation in meters at (lat, lon).

        Raises `ValueError` if (lat, lon) is outside this tile, or if any of
        the 4 nearest grid cells is a data void (`-32768`).
        """
        row_f, col_f = self._row_col(lat, lon)
        row0 = min(int(row_f), self.size - 2)
        col0 = min(int(col_f), self.size - 2)
        row1, col1 = row0 + 1, col0 + 1
        frac_row = row_f - row0
        frac_col = col_f - col0

        corners = {
            (row0, col0): self._sample(row0, col0),
            (row0, col1): self._sample(row0, col1),
            (row1, col0): self._sample(row1, col0),
            (row1, col1): self._sample(row1, col1),
        }
        for (r, c), value in corners.items():
            if value == _VOID:
                raise ValueError(
                    f"void sample at grid cell ({r}, {c}) near ({lat}, {lon})"
                )

        top = corners[(row0, col0)] * (1 - frac_col) + corners[(row0, col1)] * frac_col
        bottom = (
            corners[(row1, col0)] * (1 - frac_col) + corners[(row1, col1)] * frac_col
        )
        return top * (1 - frac_row) + bottom * frac_row


def select_tile(tiles: list[SrtmTile], lat: float, lon: float) -> SrtmTile | None:
    """Return whichever of `tiles` covers `(lat, lon)`, or `None` if none
    does.

    A full theatre needs many `.hgt` tiles (each a fixed 1x1 degree by
    format), so any full-theatre elevation grid or multi-location
    validation report (M7 Stage 2) must pick the right tile per point
    rather than assume one shared tile/origin -- SRTM's native 1-degree
    tile registration doesn't line up with a DCS-metre grid's regular
    spacing. Linear scan is fine here: real tile lists are at most a few
    dozen entries (a whole theatre spans on the order of 10 degrees per
    side), nowhere near where an index would matter.
    """
    for tile in tiles:
        north_lat = tile.sw_lat + tile.span_deg
        east_lon = tile.sw_lon + tile.span_deg
        if tile.sw_lat <= lat <= north_lat and tile.sw_lon <= lon <= east_lon:
            return tile
    return None


def _is_little_endian() -> bool:
    return array("h", [1]).tobytes()[0] == 1
