"""Build temp directory trees mimicking both RasterCharts layouts.

Never built from, and never contains, any real DCS chart data -- entry
*names* follow the real universal grammar so discovery/mosaic code is
exercised faithfully, but entry *bytes* are whatever the caller supplies
(arbitrary placeholder bytes for discovery/mosaic tests that never decode
a tile, or a `synthetic_dds.build_multi_mip_dds` fixture for tests that
do).
"""

from __future__ import annotations

import zipfile
from collections.abc import Callable, Mapping
from pathlib import Path


def tile_entry_name(scale_m: int | None, sheet: str, level: int, x: int, z: int) -> str:
    """The reverse of `tilename.parse_tile_name` -- builds a filename the
    universal grammar accepts. Mirrors the most common real spelling
    (scale + underscore, two-digit non-negative level) rather than every
    variant `tilename.py` also accepts; the parser's own tests cover the
    other spellings."""
    scale_part = f"{scale_m}m_" if scale_m is not None else ""
    level_part = f"{level:02d}" if level >= 0 else str(level)
    return f"{scale_part}{sheet}{level_part}_x{x}_z{z}.tif.dds"


def full_sheet_entries(
    scale_m: int | None,
    sheet: str,
    level: int,
    tile_bytes: Callable[[int, int], bytes],
    *,
    x_range: range = range(8),
    z_range: range = range(8),
) -> dict[str, bytes]:
    """Every entry for one sheet/level, or a sparse subset of it via
    `x_range`/`z_range` -- how the sparse-sheet fixtures (Mariana-style
    partial coverage) are built: a smaller range than `range(8)` leaves
    the rest of that sheet's 8x8 cells absent, the same as a real sparse
    sheet on disk."""
    return {
        tile_entry_name(scale_m, sheet, level, x, z): tile_bytes(x, z)
        for x in x_range
        for z in z_range
    }


def build_single_zip_terrain(
    dcs_install: Path, terrain_name: str, entries: Mapping[str, bytes]
) -> Path:
    """The single-`rasterCharts.zip` layout (four of five real terrains).
    Returns the zip path, mainly so a test can wrap zip reads for
    counting (`discovery.read_tile_bytes` opens a fresh `ZipFile` per
    call, so a counting wrapper around that function, not this one, is
    the right place to count "entries opened")."""
    rastercharts_dir = dcs_install / "Mods" / "terrains" / terrain_name / "RasterCharts"
    rastercharts_dir.mkdir(parents=True, exist_ok=True)
    zip_path = rastercharts_dir / "rasterCharts.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return zip_path


def build_caucasus_style_terrain(
    dcs_install: Path,
    terrain_name: str,
    zips: Mapping[str, Mapping[str, bytes]],
) -> list[Path]:
    """The zip-per-sheet layout (Caucasus): `zips` maps a path relative to
    `RasterCharts/` (e.g. `"0.25M/16m_AA-1.zip"`) to that zip's own
    entries. The relative path's own spelling is deliberately not
    parsed by discovery -- only entry names are -- so callers are free to
    use any sheet-naming case/underscore style here, mirroring the real
    terrain's inconsistency (research note section D)."""
    rastercharts_dir = dcs_install / "Mods" / "terrains" / terrain_name / "RasterCharts"
    paths: list[Path] = []
    for rel_zip_path, entries in zips.items():
        zip_path = rastercharts_dir / rel_zip_path
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w") as zf:
            for name, data in entries.items():
                zf.writestr(name, data)
        paths.append(zip_path)
    return paths
