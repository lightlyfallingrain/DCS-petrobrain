#!/usr/bin/env python3
"""Diagnostic: inspect RasterCharts tiles and render a marker for a DCS coordinate.

Not part of the pipeline. Two subcommands:

`scan` — dump tile dimensions/format/grid layout for a directory of
`*.tif.dds` tiles, parsing each filename via `raster.parse_tile_filename`.

`mark` — the "render a known DCS coordinate onto the raster" diagnostic:
convert a DCS-native (x, z) to its tile + in-tile pixel via
`raster.dcs_to_pixel`, draw a small crosshair at that pixel on the covering
tile, and save the result as a PNG for human inspection.

Run from `world-model/`:

    .venv/bin/python tools/inspect_raster.py scan <tile_dir>
    .venv/bin/python tools/inspect_raster.py mark <tile_dir> <theatre> <x> <z> [--out out.png]
"""

import argparse
import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from PIL import Image, ImageDraw

from raster import TileId, dcs_to_pixel, load_tile, parse_tile_filename

_CROSSHAIR_COLOR = (255, 0, 0)
_CROSSHAIR_ARM_PX = 20
_CROSSHAIR_RADIUS_PX = 6
_CROSSHAIR_WIDTH_PX = 2


def _scan_tiles(tile_dir: Path) -> list[tuple[TileId, Path]]:
    tiles = []
    for path in sorted(tile_dir.glob("*.tif.dds")):
        try:
            tile_id = parse_tile_filename(path.name)
        except ValueError:
            print(f"skipping unparseable filename: {path.name}")
            continue
        tiles.append((tile_id, path))
    return tiles


def cmd_scan(tile_dir: Path) -> None:
    tiles = _scan_tiles(tile_dir)
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
            row = "".join("#" if (x, z) in coords else "." for z in range(max_z + 1))
            print(f"  x={x}: {row}")
        print()


def _draw_crosshair(draw: ImageDraw.ImageDraw, px: int, py: int) -> None:
    """Draw a small crosshair (cross + circle) centered on (px, py)."""
    draw.line(
        (px - _CROSSHAIR_ARM_PX, py, px + _CROSSHAIR_ARM_PX, py),
        fill=_CROSSHAIR_COLOR,
        width=_CROSSHAIR_WIDTH_PX,
    )
    draw.line(
        (px, py - _CROSSHAIR_ARM_PX, px, py + _CROSSHAIR_ARM_PX),
        fill=_CROSSHAIR_COLOR,
        width=_CROSSHAIR_WIDTH_PX,
    )
    draw.ellipse(
        (
            px - _CROSSHAIR_RADIUS_PX,
            py - _CROSSHAIR_RADIUS_PX,
            px + _CROSSHAIR_RADIUS_PX,
            py + _CROSSHAIR_RADIUS_PX,
        ),
        outline=_CROSSHAIR_COLOR,
        width=_CROSSHAIR_WIDTH_PX,
    )


def cmd_mark(
    tile_dir: Path, theatre: str, x: float, z: float, out_path: Path | None
) -> None:
    """Render a crosshair at the pixel location for DCS (x, z) and save a PNG.

    Raises ValueError if `theatre` has no registered raster registration
    (propagated from `raster.dcs_to_pixel`). Exits with an error message if
    the covering tile isn't present in `tile_dir` -- this is a diagnostic
    over a local sample directory, not the full tile set.
    """
    tile, px, py = dcs_to_pixel(theatre, x, z)
    tile_path = tile_dir / tile.filename
    if not tile_path.exists():
        print(
            f"DCS ({x}, {z}) maps to tile {tile.filename} pixel ({px}, {py}), "
            f"but that tile isn't present in {tile_dir}"
        )
        sys.exit(1)

    if out_path is None:
        stem = tile_path.name.removesuffix(".tif.dds")
        out_path = tile_dir / f"{stem}_marked_x{px}_z{py}.png"

    img = load_tile(tile_path).copy()
    _draw_crosshair(ImageDraw.Draw(img), px, py)
    img.save(out_path)
    print(
        f"DCS ({x}, {z}) -> tile {tile.filename} pixel ({px}, {py}); "
        f"wrote {out_path}"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser(
        "scan", help="dump tile dimensions/format/grid layout for a directory"
    )
    scan_parser.add_argument("tile_dir", type=Path)

    mark_parser = subparsers.add_parser(
        "mark", help="render a crosshair marker for a DCS coordinate"
    )
    mark_parser.add_argument("tile_dir", type=Path)
    mark_parser.add_argument("theatre")
    mark_parser.add_argument("x", type=float)
    mark_parser.add_argument("z", type=float)
    mark_parser.add_argument("--out", type=Path, default=None)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(args.tile_dir)
    elif args.command == "mark":
        cmd_mark(args.tile_dir, args.theatre, args.x, args.z, args.out)


if __name__ == "__main__":
    main()
