#!/usr/bin/env python3
"""Diagnostic: visualize Stage 1's marker-controlled-watershed basins and
gated ridge/valley lines over a built region's elevation grid.

Not part of the pipeline. Loads the full elevation grid from a built
`.sqlite` (via `store.reader.load_full_grid`), runs `terrain.curvature.
smooth_grid`/`find_basin_seeds` and `terrain.features.grow_basins`/
`extract_components` over it, and renders a per-cell basin map (each basin
a distinct colour, ridge/valley lines overdrawn) plus a component-by-
component text report (cell count, orientation, elevation range, and the
relief/width gate values that decided pass/fail). This exists specifically
so the smoothing window, relief threshold, and width ceiling get tuned by
looking at real output over `latakia-20km` and a Bekaa-equivalent region,
not guessed blind -- see `plans/terrain-feature-probing/plan.md` Stage 1/2.

North is drawn up (DCS's `+x`), east is drawn right (DCS's `+z`), matching
`geometry.bearing_deg`'s convention -- one grid cell renders as a
`_CELL_PX`-square block, not to real-world map scale.

A whole-theatre grid (`syria-full`: 1656x1543 cells) renders to a ~19k x 20k
pixel image that is both slow and unreadable, so `--near`/`--center` with
`--radius-km` crop the rendered window to one region. Classification and
component extraction always run over the *full* grid, so what is drawn is
exactly what the pipeline would store -- cropping the render after the fact,
not the analysis, avoids the edge effects a cropped input would introduce.

Run from `world-model/`:

    .venv/bin/python tools/inspect_terrain.py <db_path> \\
        [--near NAME | --center X,Z] [--radius-km R] \\
        [--grid-kind elevation] [--smoothing-window N] [--seed-footprint N] \\
        [--relief-threshold M] [--width-ceiling M] [--min-cells N] [--out out.png]
"""

import argparse
import colorsys
import json
import sqlite3
import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from PIL import Image, ImageDraw

from build.pipeline import open_region_db
from store.models import ElevationGrid
from store.reader import load_full_grid
from terrain.curvature import (
    DEFAULT_SEED_FOOTPRINT_CELLS,
    DEFAULT_SMOOTHING_WINDOW_CELLS,
    find_basin_seeds,
    smooth_grid,
)
from terrain.features import (
    DEFAULT_MIN_CELL_COUNT,
    DEFAULT_RELIEF_THRESHOLD_M,
    DEFAULT_WIDTH_CEILING_M,
    extract_components,
    grow_basins,
)

_CELL_PX = 12
_NEITHER_COLOR = (70, 70, 70)
_UNSAMPLED_COLOR = (15, 15, 15)
_RIDGE_LINE_COLOR = (255, 255, 255)
_VALLEY_LINE_COLOR = (255, 255, 0)
_LINE_WIDTH_PX = 2


def _basin_color(basin_id: int) -> tuple[int, int, int]:
    """A visually distinct, deterministic colour per basin id -- evenly
    spaced hues via the golden-angle increment, so adjacent basin ids
    (likely spatially adjacent, since `grow_basins` assigns ids in seed
    order) don't land on visually similar hues."""
    hue = (basin_id * 0.6180339887) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.55, 0.55)
    return (round(r * 255), round(g * 255), round(b * 255))


def _grid_point_to_pixel(
    x: float,
    z: float,
    origin_x: float,
    origin_z: float,
    spacing_m: float,
    last_row: int,
    first_col: int,
) -> tuple[int, int]:
    """Pixel centre of the grid point `(x, z)` within the rendered window
    whose topmost row index is `last_row` and leftmost column index is
    `first_col` (a full-grid render passes `n_rows - 1` and `0`)."""
    row_f = (x - origin_x) / spacing_m
    col_f = (z - origin_z) / spacing_m
    image_row_f = last_row - row_f  # north drawn up
    px = round((col_f - first_col) * _CELL_PX + _CELL_PX / 2)
    py = round(image_row_f * _CELL_PX + _CELL_PX / 2)
    return px, py


def _resolve_center(conn: sqlite3.Connection, name: str) -> tuple[float, float]:
    """DCS `(x, z)` of the named place/settlement/airfield `name` in this
    region DB -- the centroid of its stored vertices for an area feature."""
    row = conn.execute(
        """
        SELECT kind, name, geom_json FROM feature
        WHERE lower(name) = lower(?)
          AND kind IN ('named_place', 'airfield', 'settlement')
        ORDER BY CASE kind
            WHEN 'named_place' THEN 0 WHEN 'airfield' THEN 1 ELSE 2 END
        LIMIT 1
        """,
        (name,),
    ).fetchone()
    if row is None:
        raise SystemExit(
            f"no named_place/airfield/settlement called {name!r} in this db"
        )
    points = json.loads(row[2])
    xs = [pt[0] for pt in points]
    zs = [pt[1] for pt in points]
    print(f"centred on {row[0]} {row[1]!r}")
    return sum(xs) / len(xs), sum(zs) / len(zs)


def _window(
    grid: ElevationGrid, center: tuple[float, float], radius_m: float
) -> tuple[int, int, int, int]:
    """Inclusive `(first_row, last_row, first_col, last_col)` grid-index
    window of `radius_m` around DCS `center`, clamped to the grid."""
    center_row = (center[0] - grid.origin_x) / grid.spacing_m
    center_col = (center[1] - grid.origin_z) / grid.spacing_m
    radius_cells = radius_m / grid.spacing_m
    first_row = max(0, int(center_row - radius_cells))
    last_row = min(grid.n_rows - 1, int(center_row + radius_cells))
    first_col = max(0, int(center_col - radius_cells))
    last_col = min(grid.n_cols - 1, int(center_col + radius_cells))
    if first_row > last_row or first_col > last_col:
        raise SystemExit(
            f"window around ({center[0]:.0f}, {center[1]:.0f}) falls outside the grid"
        )
    return first_row, last_row, first_col, last_col


def cmd_render(
    db_path: Path,
    grid_kind: str,
    smoothing_window_cells: int,
    seed_footprint_cells: int,
    relief_threshold_m: float,
    width_ceiling_m: float,
    min_cell_count: int,
    out_path: Path | None,
    near: str | None = None,
    center: tuple[float, float] | None = None,
    radius_km: float = 20.0,
) -> None:
    conn = open_region_db(db_path)
    try:
        grid = load_full_grid(conn, grid_kind)
        if grid is not None and near is not None:
            center = _resolve_center(conn, near)
    finally:
        conn.close()
    if grid is None:
        print(f"No {grid_kind!r} grid found in {db_path} -- nothing to render.")
        return

    if center is None:
        window = (0, grid.n_rows - 1, 0, grid.n_cols - 1)
    else:
        window = _window(grid, center, radius_km * 1000.0)
    first_row, last_row, first_col, last_col = window

    smoothed = smooth_grid(grid, window_cells=smoothing_window_cells)
    seeds = find_basin_seeds(smoothed, footprint_cells=seed_footprint_cells)
    labels, basins = grow_basins(smoothed, seeds)
    components = extract_components(
        smoothed,
        basins,
        labels,
        relief_threshold_m=relief_threshold_m,
        width_ceiling_m=width_ceiling_m,
        min_cell_count=min_cell_count,
    )

    width = (last_col - first_col + 1) * _CELL_PX
    height = (last_row - first_row + 1) * _CELL_PX
    img = Image.new("RGB", (width, height), _UNSAMPLED_COLOR)
    draw = ImageDraw.Draw(img)

    for row in range(first_row, last_row + 1):
        image_row = last_row - row
        for col in range(first_col, last_col + 1):
            if smoothed.samples[row][col] is None:
                color = _UNSAMPLED_COLOR
            else:
                basin_id = labels.get((row, col))
                color = _NEITHER_COLOR if basin_id is None else _basin_color(basin_id)
            x0 = (col - first_col) * _CELL_PX
            y0 = image_row * _CELL_PX
            draw.rectangle((x0, y0, x0 + _CELL_PX - 1, y0 + _CELL_PX - 1), fill=color)

    in_window = [
        component
        for component in components
        if any(
            first_row <= cell.row <= last_row and first_col <= cell.col <= last_col
            for cell in component.cells
        )
    ]
    for component in in_window:
        pixels = [
            _grid_point_to_pixel(
                pt[0],
                pt[1],
                smoothed.origin_x,
                smoothed.origin_z,
                smoothed.spacing_m,
                last_row,
                first_col,
            )
            for pt in component.points
        ]
        line_color = (
            _RIDGE_LINE_COLOR if component.kind == "ridge" else _VALLEY_LINE_COLOR
        )
        if len(pixels) >= 2:
            draw.line(pixels, fill=line_color, width=_LINE_WIDTH_PX)

    if out_path is None:
        out_path = db_path.parent / f"{db_path.stem}_terrain.png"
    img.save(out_path)

    ridge_components = [c for c in in_window if c.kind == "ridge"]
    valley_components = [c for c in in_window if c.kind == "valley"]
    basins_in_window = {
        basin_id
        for row in range(first_row, last_row + 1)
        for col in range(first_col, last_col + 1)
        if (basin_id := labels.get((row, col))) is not None
    }

    print(f"wrote {out_path}")
    print(f"grid: {grid.n_rows}x{grid.n_cols} at {grid.spacing_m} m spacing")
    print(
        f"rendered window: rows {first_row}-{last_row}, cols {first_col}-{last_col} "
        f"({(last_row - first_row + 1) * grid.spacing_m / 1000.0:.0f} x "
        f"{(last_col - first_col + 1) * grid.spacing_m / 1000.0:.0f} km); "
        f"components listed below are those with a cell inside it"
    )
    print(
        f"smoothing window: {smoothing_window_cells} cells, "
        f"seed footprint: {seed_footprint_cells} cells"
    )
    print(
        f"relief threshold: {relief_threshold_m} m, "
        f"width ceiling: {width_ceiling_m} m, min cell count: {min_cell_count}"
    )
    print(f"basins (whole grid): {len(basins)}; basins touching this window: {len(basins_in_window)}")
    print(
        f"ridge components (>= min cell count, gate-passed): {len(ridge_components)}, "
        f"valley components: {len(valley_components)}"
    )
    for label, kind_components in (
        ("ridge", ridge_components),
        ("valley", valley_components),
    ):
        for i, component in enumerate(kind_components):
            elev_min, elev_max = component.elevation_range_m
            # NB: this is the extracted cells' own elevation span, not the
            # basin-floor-to-saddle "relief" the gate actually compared
            # against relief_threshold_m -- a ridge's boundary cells can
            # span far less than that (the saddle is one point along it).
            elev_span_m = elev_max - elev_min
            width_note = (
                f" width={component.width_m:.0f} m"
                if component.width_m is not None
                else ""
            )
            print(
                f"  {label} {i}: cells={len(component.cells)} basin_ids={component.basin_ids} "
                f"orientation={component.orientation_deg:.1f} deg "
                f"elevation_range=[{elev_min:.1f}, {elev_max:.1f}] m "
                f"elev_span={elev_span_m:.1f} m{width_note}"
            )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db_path", type=Path)
    parser.add_argument("--grid-kind", default="elevation")
    parser.add_argument(
        "--smoothing-window", type=int, default=DEFAULT_SMOOTHING_WINDOW_CELLS
    )
    parser.add_argument(
        "--seed-footprint", type=int, default=DEFAULT_SEED_FOOTPRINT_CELLS
    )
    parser.add_argument(
        "--relief-threshold", type=float, default=DEFAULT_RELIEF_THRESHOLD_M
    )
    parser.add_argument(
        "--width-ceiling", type=float, default=DEFAULT_WIDTH_CEILING_M
    )
    parser.add_argument("--min-cells", type=int, default=DEFAULT_MIN_CELL_COUNT)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--near",
        default=None,
        help="centre the rendered window on this named place/airfield/settlement",
    )
    parser.add_argument(
        "--center",
        default=None,
        help="centre the rendered window on DCS coordinates, as 'X,Z' in metres",
    )
    parser.add_argument(
        "--radius-km",
        type=float,
        default=20.0,
        help="half-width of the rendered window around --near/--center (default 20)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.near is not None and args.center is not None:
        parser.error("--near and --center are mutually exclusive")
    center: tuple[float, float] | None = None
    if args.center is not None:
        parts = args.center.split(",")
        if len(parts) != 2:
            parser.error("--center takes 'X,Z' in metres")
        center = (float(parts[0]), float(parts[1]))
    cmd_render(
        args.db_path,
        args.grid_kind,
        args.smoothing_window,
        args.seed_footprint,
        args.relief_threshold,
        args.width_ceiling,
        args.min_cells,
        args.out,
        near=args.near,
        center=center,
        radius_km=args.radius_km,
    )


if __name__ == "__main__":
    main()
