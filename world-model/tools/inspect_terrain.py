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

Run from `world-model/`:

    .venv/bin/python tools/inspect_terrain.py <db_path> \\
        [--grid-kind elevation] [--threshold M] [--min-cells N] [--out out.png]
"""

import argparse
import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from PIL import Image, ImageDraw

from build.pipeline import open_region_db
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
    x: float, z: float, origin_x: float, origin_z: float, spacing_m: float, n_rows: int
) -> tuple[int, int]:
    row_f = (x - origin_x) / spacing_m
    col_f = (z - origin_z) / spacing_m
    image_row_f = (n_rows - 1) - row_f  # north drawn up
    px = round(col_f * _CELL_PX + _CELL_PX / 2)
    py = round(image_row_f * _CELL_PX + _CELL_PX / 2)
    return px, py


def cmd_render(
    db_path: Path,
    grid_kind: str,
    threshold_m: float,
    min_cell_count: int,
    out_path: Path | None,
) -> None:
    conn = open_region_db(db_path)
    try:
        grid = load_full_grid(conn, grid_kind)
    finally:
        conn.close()
    if grid is None:
        print(f"No {grid_kind!r} grid found in {db_path} -- nothing to render.")
        return

    curvature_cells = classify_curvature(grid, threshold_m=threshold_m)
    cells_by_rc = {(c.row, c.col): c for c in curvature_cells}
    components = extract_components(
        grid, curvature_cells, min_cell_count=min_cell_count
    )

    width = grid.n_cols * _CELL_PX
    height = grid.n_rows * _CELL_PX
    img = Image.new("RGB", (width, height), _UNSAMPLED_COLOR)
    draw = ImageDraw.Draw(img)

    for row in range(grid.n_rows):
        image_row = (grid.n_rows - 1) - row
        for col in range(grid.n_cols):
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
            x0 = col * _CELL_PX
            y0 = image_row * _CELL_PX
            draw.rectangle((x0, y0, x0 + _CELL_PX - 1, y0 + _CELL_PX - 1), fill=color)

    for component in components:
        pixels = [
            _grid_point_to_pixel(
                pt[0], pt[1], grid.origin_x, grid.origin_z, grid.spacing_m, grid.n_rows
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
    ridge_components = [c for c in components if c.kind == "ridge"]
    valley_components = [c for c in components if c.kind == "valley"]

    print(f"wrote {out_path}")
    print(f"grid: {grid.n_rows}x{grid.n_cols} at {grid.spacing_m} m spacing")
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
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    cmd_render(args.db_path, args.grid_kind, args.threshold, args.min_cells, args.out)


if __name__ == "__main__":
    main()
