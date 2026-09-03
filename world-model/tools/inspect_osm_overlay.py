#!/usr/bin/env python3
"""Diagnostic: overlay a cached OSM feature set onto a RasterCharts tile.

Not part of the pipeline. Loads a cached Overpass response (via
`osm.load_features`), runs each feature's WGS84 coordinates through
`coordinates.wgs84_to_dcs` then `raster.registration.dcs_to_tile_pixel`
(the same chain M1/M2 already validated -- see
`world-model/research/2026-09-03-m1-coordinate-transform-verification.md`
and `.../2026-09-03-m2-rastercharts-recon.md`), draws the transformed
geometry onto a copy of the given tile image, and prints a displacement
report for named point (`place`) features.

Depends on `raster.registration`'s `default_sheet="aa"`/`default_level="00"`
tile -- if a future session changes that default, this tool's assumption
that the given tile is the one every feature's transform lands on no longer
holds (see plan's "Risks & Unknowns").

Attribution: rendered output and reports derived from OSM data must carry
"(c) OpenStreetMap contributors" -- see `docs/concept/WORLD_MODEL_BUILDER.md`.

Run from `world-model/`:

    .venv/bin/python tools/inspect_osm_overlay.py overlay \\
        <cache_path> <tile_path> <theatre> [--out out.png]
"""

import argparse
import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont

from coordinates import wgs84_to_dcs
from osm import load_features
from raster import TileId, load_tile, parse_tile_filename
from raster.registration import dcs_to_tile_pixel, get_registration

_ROAD_COLOR = (255, 220, 0)
_BUILDING_COLOR = (0, 220, 255)
_PLACE_COLOR = (255, 0, 0)
_LINE_WIDTH_PX = 2
_MARKER_RADIUS_PX = 5

_ATTRIBUTION = "(c) OpenStreetMap contributors"
_ATTRIBUTION_TEXT_COLOR = (255, 255, 255)
_ATTRIBUTION_BG_COLOR = (0, 0, 0)
_ATTRIBUTION_MARGIN_PX = 6

# M2 session 12's by-eye pixel read of the Gemerek town-symbol icon on this
# same tile (64maa00_x0_z0.tif.dds), used below as an internal-consistency
# cross-check -- the OSM town node's transformed pixel is expected to
# roughly agree with this independently-recorded reading, not exactly match
# it (different source point: chart symbol vs. OSM node coordinate).
_GEMEREK_SESSION_12_PIXEL = (490, 975)


def _point_to_tile_pixel(
    theatre: str, tile: TileId, lat: float, lon: float
) -> tuple[int, int] | None:
    """Return (px, py) if the point falls on `tile`, else None."""
    dcs_x, dcs_z = wgs84_to_dcs(theatre, lat, lon)
    x_tile_index, z_tile_index, px, py = dcs_to_tile_pixel(theatre, dcs_x, dcs_z)
    if (x_tile_index, z_tile_index) != (tile.x, tile.z):
        return None
    return px, py


def _draw_attribution(img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
    """Draw the OSM attribution string into the bottom-left corner of `img`.

    Required per `docs/concept/WORLD_MODEL_BUILDER.md`: any rendered overlay
    derived from OSM data must carry the attribution on the image itself, not
    only in console/research-note text. Uses Pillow's built-in bitmap font
    (no external font dependency) with a filled background box behind the
    text so it stays legible against whatever tile imagery is underneath.
    """
    font = ImageFont.load_default()
    text_bbox = draw.textbbox((0, 0), _ATTRIBUTION, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    x0 = _ATTRIBUTION_MARGIN_PX
    y0 = img.height - _ATTRIBUTION_MARGIN_PX - text_height - 2 * _ATTRIBUTION_MARGIN_PX
    x1 = x0 + text_width + 2 * _ATTRIBUTION_MARGIN_PX
    y1 = img.height - _ATTRIBUTION_MARGIN_PX

    draw.rectangle((x0, y0, x1, y1), fill=_ATTRIBUTION_BG_COLOR)
    draw.text(
        (x0 + _ATTRIBUTION_MARGIN_PX, y0 + _ATTRIBUTION_MARGIN_PX),
        _ATTRIBUTION,
        fill=_ATTRIBUTION_TEXT_COLOR,
        font=font,
    )


def cmd_overlay(
    cache_path: Path, tile_path: Path, theatre: str, out_path: Path | None
) -> None:
    feature_set = load_features(cache_path)
    tile = parse_tile_filename(tile_path.name)
    reg = get_registration(theatre)

    img = load_tile(tile_path).copy()
    draw = ImageDraw.Draw(img)

    ways_drawn = 0
    ways_off_tile = 0
    for way in feature_set.ways:
        pixels: list[tuple[int, int]] = []
        off_tile = False
        for lat, lon in way.points:
            result = _point_to_tile_pixel(theatre, tile, lat, lon)
            if result is None:
                off_tile = True
                break
            pixels.append(result)
        if off_tile or len(pixels) < 2:
            ways_off_tile += 1
            continue
        color = _BUILDING_COLOR if "building" in way.tags else _ROAD_COLOR
        draw.line(pixels, fill=color, width=_LINE_WIDTH_PX)
        ways_drawn += 1

    place_report: list[tuple[str, int, int]] = []
    nodes_off_tile = 0
    for node in feature_set.nodes:
        result = _point_to_tile_pixel(theatre, tile, node.lat, node.lon)
        if result is None:
            nodes_off_tile += 1
            continue
        px, py = result
        draw.ellipse(
            (
                px - _MARKER_RADIUS_PX,
                py - _MARKER_RADIUS_PX,
                px + _MARKER_RADIUS_PX,
                py + _MARKER_RADIUS_PX,
            ),
            outline=_PLACE_COLOR,
            width=_LINE_WIDTH_PX,
        )
        name = node.tags.get("name", f"node {node.id}")
        place_report.append((name, px, py))

    _draw_attribution(img, draw)

    if out_path is None:
        stem = tile_path.name.removesuffix(".tif.dds")
        out_path = tile_path.parent / f"{stem}_osm_overlay.png"
    img.save(out_path)

    print(f"{_ATTRIBUTION}")
    print(f"wrote {out_path}")
    print(
        f"ways drawn: {ways_drawn}, ways off-tile/degenerate: {ways_off_tile}, "
        f"place nodes off-tile: {nodes_off_tile}"
    )
    print()
    print("Displacement report (place nodes):")
    header = (
        f"{'Name':<30} {'OSM px (x,y)':<16} {'M2 session-12 px':<20} "
        f"{'delta (px)':<12} {'delta (m, x-axis approx)':<26}"
    )
    print(header)
    print("-" * len(header))
    for name, px, py in place_report:
        dx = px - _GEMEREK_SESSION_12_PIXEL[0]
        dy = py - _GEMEREK_SESSION_12_PIXEL[1]
        delta_px = (dx**2 + dy**2) ** 0.5
        delta_m = delta_px * reg.scale_m
        print(
            f"{name:<30} ({px}, {py}){'':<6} {_GEMEREK_SESSION_12_PIXEL!s:<20} "
            f"{delta_px:<12.1f} {delta_m:<26.1f}"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    overlay_parser = subparsers.add_parser(
        "overlay", help="render a cached OSM feature set onto a RasterCharts tile"
    )
    overlay_parser.add_argument("cache_path", type=Path)
    overlay_parser.add_argument("tile_path", type=Path)
    overlay_parser.add_argument("theatre")
    overlay_parser.add_argument("--out", type=Path, default=None)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "overlay":
        cmd_overlay(args.cache_path, args.tile_path, args.theatre, args.out)


if __name__ == "__main__":
    main()
