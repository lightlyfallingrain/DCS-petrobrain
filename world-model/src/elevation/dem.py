"""Reads a single SRTM `.hgt` tile and interpolates elevation at a point.

Format (per `world-model/research/2026-09-03-m4-elevation-recon.md` Finding
9): one file per 1x1 degree tile, named `<N|S><lat><E|W><lon>.hgt` for the
tile's south-west corner (e.g. `N39E036.hgt` covers 39-40N, 36-37E). SRTM1
tiles are a flat 3601x3601 grid of big-endian signed 16-bit samples,
row-major starting at the tile's north-west corner, with `-32768` marking a
data void. Parsed with stdlib `struct`/`array` only -- no GDAL/rasterio
dependency, per the recon note's Finding 12 recommendation.

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
    """One parsed SRTM `.hgt` tile.

    `sw_lat`/`sw_lon` are the tile's south-west corner (whole degrees, from
    the filename). `samples` is the raw `size x size` grid, row-major from
    the tile's *north-west* corner (row 0 = northmost).
    """

    sw_lat: float
    sw_lon: float
    size: int
    samples: array  # type: ignore[type-arg]

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

        Row 0 is the tile's north edge (sw_lat + 1), increasing southward;
        col 0 is the tile's west edge (sw_lon), increasing eastward. Raises
        `ValueError` if (lat, lon) falls outside this tile.
        """
        if not (
            self.sw_lat <= lat <= self.sw_lat + 1
            and self.sw_lon <= lon <= self.sw_lon + 1
        ):
            raise ValueError(
                f"({lat}, {lon}) falls outside tile "
                f"[{self.sw_lat}, {self.sw_lat + 1}] x [{self.sw_lon}, {self.sw_lon + 1}]"
            )
        row = (self.sw_lat + 1 - lat) * (self.size - 1)
        col = (lon - self.sw_lon) * (self.size - 1)
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


def _is_little_endian() -> bool:
    return array("h", [1]).tobytes()[0] == 1
