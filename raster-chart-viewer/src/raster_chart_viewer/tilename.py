"""The universal RasterCharts tile filename grammar.

Every `.tif.dds` entry on every installed terrain (single-zip or
Caucasus's zip-per-sheet layout) matches one regex -- see
`raster-chart-viewer/research/2026-11-16-rastercharts-all-terrains-recon.md`
section B, which measured this against all five installed terrains
(100% match, case-insensitive). `scale` is the only optional group: 62 of
Mariana Islands' entries carry no scale prefix at all (U2, answered
2026-11-16) and are grouped into their own "unscaled" tier rather than
dropped (`mosaic.py`/`discovery.py` both treat a `None` scale as a tier key
on equal footing with a real one).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Groups: scale (optional, digits only -- the "m" suffix and the optional
#: underscore after it are not captured), sheet (letters), level (signed
#: int, the sheet's column index, column within sheet-group), x (tile row
#: within the sheet, south-increasing), z (tile column within the sheet,
#: east-increasing). Case-insensitive: real filenames mix "32m"/"64M",
#: lowercase and uppercase sheet letters.
_TILE_NAME_RE = re.compile(
    r"^(?:(\d+)m_?)?([a-z]+)(-?\d+)_x(\d+)_z(\d+)\.tif\.dds$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class TileKey:
    """One RasterCharts tile entry, fully identified.

    `scale_m` is `None` for Mariana's 62 unscaled entries (U2) -- its
    absence is a real, structural tier distinction, not a parse failure.
    `sheet` is lowercased at parse time (`AA00` and `aa00` are the same
    sheet on every terrain measured); `level`/`x`/`z` are the raw
    integers the filename carries.
    """

    scale_m: int | None
    sheet: str
    level: int
    x: int
    z: int


def parse_tile_name(name: str) -> TileKey | None:
    """Parse one zip-entry basename into a `TileKey`, or `None` if it does
    not match the universal grammar at all (none observed on any measured
    terrain, but a zip could in principle hold something else)."""
    match = _TILE_NAME_RE.match(name)
    if match is None:
        return None
    scale_raw, sheet, level_raw, x_raw, z_raw = match.groups()
    return TileKey(
        scale_m=int(scale_raw) if scale_raw is not None else None,
        sheet=sheet.lower(),
        level=int(level_raw),
        x=int(x_raw),
        z=int(z_raw),
    )
