"""RasterCharts tile subsystem.

Loads Syria's `RasterCharts` DXT5/BC3 DDS tile set and provides DCS x/z <->
tile-pixel conversion. Mirrors `coordinates/`'s shape: theatre-specific
registration parameters are confined to `raster.registration`, and the
functions here are theatre-agnostic. See
`world-model/research/2026-09-03-m2-rastercharts-recon.md` for the format and
registration recon behind this module.

Tile filenames follow `{scale}m{sheet}{level}_x{X}_z{Z}.tif.dds`, e.g.
`64maa00_x0_z1.tif.dds` (scale=64, sheet="aa", level="00", x=0, z=1).
"""

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .registration import dcs_to_tile_pixel as _dcs_to_tile_pixel
from .registration import get_registration
from .registration import tile_pixel_to_dcs as _tile_pixel_to_dcs

_TILE_FILENAME_RE = re.compile(
    r"^(?P<scale>\d+)m(?P<sheet>[a-z]+)(?P<level>-?\d{2})"
    r"_x(?P<x>\d+)_z(?P<z>\d+)\.tif\.dds$"
)


@dataclass(frozen=True)
class TileId:
    """Identifies one RasterCharts tile by its parsed filename fields."""

    scale: int
    sheet: str
    level: str
    x: int
    z: int

    @property
    def filename(self) -> str:
        return f"{self.scale}m{self.sheet}{self.level}_x{self.x}_z{self.z}.tif.dds"


def parse_tile_filename(name: str) -> TileId:
    """Parse a RasterCharts tile filename into its `TileId` fields.

    Raises ValueError if `name` doesn't match the
    `{scale}m{sheet}{level}_x{X}_z{Z}.tif.dds` naming scheme.
    """
    match = _TILE_FILENAME_RE.match(name)
    if match is None:
        raise ValueError(
            f"{name!r} doesn't match the RasterCharts tile filename scheme "
            "'{scale}m{sheet}{level}_x{X}_z{Z}.tif.dds'"
        )
    return TileId(
        scale=int(match["scale"]),
        sheet=match["sheet"],
        level=match["level"],
        x=int(match["x"]),
        z=int(match["z"]),
    )


def load_tile(path: Path) -> Image.Image:
    """Decode a RasterCharts DDS tile at `path` to an RGB Pillow image."""
    return Image.open(path).convert("RGB")


def dcs_to_pixel(theatre: str, x: float, z: float) -> tuple[TileId, int, int]:
    """Convert DCS-native (x, z) to the tile and in-tile pixel that covers it.

    Uses `theatre`'s registered scale/sheet/level (see
    `raster.registration.RasterRegistration`) -- other sheets/levels for the
    same theatre are not guaranteed to share this registration's origin.

    Raises ValueError if `theatre` has no registered raster registration.
    """
    reg = get_registration(theatre)
    x_tile_index, z_tile_index, px, py = _dcs_to_tile_pixel(theatre, x, z)
    tile = TileId(
        scale=int(reg.scale_m),
        sheet=reg.default_sheet,
        level=reg.default_level,
        x=x_tile_index,
        z=z_tile_index,
    )
    return tile, px, py


def pixel_to_dcs(theatre: str, tile: TileId, px: int, py: int) -> tuple[float, float]:
    """Convert a tile + in-tile pixel position to DCS-native (x, z).

    Inverse of `dcs_to_pixel`. Raises ValueError if `theatre` has no
    registered raster registration.
    """
    return _tile_pixel_to_dcs(theatre, tile.x, tile.z, px, py)
