#!/usr/bin/env python3
"""Diagnostic: visualize M6's curvature classification and extracted
ridge/valley lines over a built region's elevation grid.

Not part of the pipeline. Loads the full elevation grid from a built
`.sqlite` (via `store.reader.load_full_grid`), runs
`terrain.curvature.classify_curvature` and `terrain.features.
extract_components` over it, and renders a per-cell classification map
(ridge/valley/neither/unsampled) with the extracted lines overdrawn, plus a
component-by-component text report (cell count, orientation, elevation
range). This exists specifically so curvature/min-cell-count thresholds get
tuned by looking at real output over `latakia-20km`, not guessed blind --
see `plans/m6-terrain-semantics/plan.md` Stage 2.

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
        [--grid-kind elevation] [--threshold M] [--min-cells N] [--out out.png]
"""

import argparse
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
    DEFAULT_CURVATURE_THRESHOLD_M,
    CurvatureClass,
    classify_curvature,
)
from terrain.features import DEFAULT_MIN_CELL_COUNT, extract_components

_CELL_PX = 12
_RIDGE_COLOR = (220, 60, 40)
_VALLEY_COLOR = (50, 110, 230)
_NEITHER_COLOR = (70, 70, 70)
_UNSAMPLED_COLOR = (15, 15, 15)
_RIDGE_LINE_COLOR = (255, 255, 255)
_VALLEY_LINE_COLOR = (255, 255, 0)
_LINE_WIDTH_PX = 2


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
    threshold_m: float,
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

    curvature_cells = classify_curvature(grid, threshold_m=threshold_m)
    cells_by_rc = {(c.row, c.col): c for c in curvature_cells}
    components = extract_components(
        grid, curvature_cells, min_cell_count=min_cell_count
    )

    width = (last_col - first_col + 1) * _CELL_PX
    height = (last_row - first_row + 1) * _CELL_PX
    img = Image.new("RGB", (width, height), _UNSAMPLED_COLOR)
    draw = ImageDraw.Draw(img)

    for row in range(first_row, last_row + 1):
        image_row = last_row - row
        for col in range(first_col, last_col + 1):
            color: tuple[int, int, int]
            if grid.samples[row][col] is None:
                color = _UNSAMPLED_COLOR
            else:
                cell = cells_by_rc.get((row, col))
                if cell is None or cell.classification == CurvatureClass.NEITHER:
                    color = _NEITHER_COLOR
                elif cell.classification == CurvatureClass.RIDGE:
                    color = _RIDGE_COLOR
                else:
                    color = _VALLEY_COLOR
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
                grid.origin_x,
                grid.origin_z,
                grid.spacing_m,
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

    ridge_cell_count = sum(
        1 for c in curvature_cells if c.classification == CurvatureClass.RIDGE
    )
    valley_cell_count = sum(
        1 for c in curvature_cells if c.classification == CurvatureClass.VALLEY
    )
    ridge_components = [c for c in in_window if c.kind == "ridge"]
    valley_components = [c for c in in_window if c.kind == "valley"]

    print(f"wrote {out_path}")
    print(f"grid: {grid.n_rows}x{grid.n_cols} at {grid.spacing_m} m spacing")
    print(
        f"rendered window: rows {first_row}-{last_row}, cols {first_col}-{last_col} "
        f"({(last_row - first_row + 1) * grid.spacing_m / 1000.0:.0f} x "
        f"{(last_col - first_col + 1) * grid.spacing_m / 1000.0:.0f} km); "
        f"components listed below are those with a cell inside it"
    )
    print(f"curvature threshold: {threshold_m} m, min cell count: {min_cell_count}")
    print(f"ridge cells: {ridge_cell_count}, valley cells: {valley_cell_count}")
    print(
        f"ridge components (>= min cell count): {len(ridge_components)}, "
        f"valley components: {len(valley_components)}"
    )
    for label, kind_components in (
        ("ridge", ridge_components),
        ("valley", valley_components),
    ):
        for i, component in enumerate(kind_components):
            elev_min, elev_max = component.elevation_range_m
            print(
                f"  {label} {i}: cells={len(component.cells)} "
                f"orientation={component.orientation_deg:.1f} deg "
                f"elevation_range=[{elev_min:.1f}, {elev_max:.1f}] m"
            )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db_path", type=Path)
    parser.add_argument("--grid-kind", default="elevation")
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_CURVATURE_THRESHOLD_M
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
        args.threshold,
        args.min_cells,
        args.out,
        near=args.near,
        center=center,
        radius_km=args.radius_km,
    )


if __name__ == "__main__":
    main()
