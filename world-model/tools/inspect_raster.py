#!/usr/bin/env python3
"""Diagnostic: dump RasterCharts tile dimensions/format/grid layout.

Not part of the pipeline. Scans a directory of `*.tif.dds` tiles, parses each
filename via `raster.parse_tile_filename`, decodes each tile's dimensions and
pixel format via Pillow, and prints a per-sheet/level x/z grid showing which
tiles are present in the sampled directory. Run from `world-model/`:

    .venv/bin/python tools/inspect_raster.py <tile_dir>
"""

import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from PIL import Image

from raster import TileId, parse_tile_filename


def _scan(tile_dir: Path) -> list[tuple[TileId, Path]]:
    tiles = []
    for path in sorted(tile_dir.glob("*.tif.dds")):
        try:
            tile_id = parse_tile_filename(path.name)
        except ValueError:
            print(f"skipping unparseable filename: {path.name}")
            continue
        tiles.append((tile_id, path))
    return tiles


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    tile_dir = Path(sys.argv[1])
    tiles = _scan(tile_dir)
    if not tiles:
        print(f"No *.tif.dds tiles found in {tile_dir}")
        return

    print(f"{'File':<28} {'Size':<12} {'Mode':<6} scale sheet level x z")
    print("-" * 78)
    groups: dict[tuple[int, str, str], set[tuple[int, int]]] = {}
    for tile_id, path in tiles:
        with Image.open(path) as img:
            size = f"{img.width}x{img.height}"
            mode = img.mode
        print(
            f"{path.name:<28} {size:<12} {mode:<6} "
            f"{tile_id.scale:<5} {tile_id.sheet:<5} {tile_id.level:<5} "
            f"{tile_id.x} {tile_id.z}"
        )
        key = (tile_id.scale, tile_id.sheet, tile_id.level)
        groups.setdefault(key, set()).add((tile_id.x, tile_id.z))

    print()
    for (scale, sheet, level), coords in sorted(groups.items()):
        print(f"Grid layout: {scale}m sheet={sheet!r} level={level!r}")
        max_x = max(x for x, _ in coords)
        max_z = max(z for _, z in coords)
        for x in range(max_x + 1):
            row = "".join(
                "#" if (x, z) in coords else "." for z in range(max_z + 1)
            )
            print(f"  x={x}: {row}")
        print()


if __name__ == "__main__":
    main()
