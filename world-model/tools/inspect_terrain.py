#!/usr/bin/env python3
"""Diagnostic: aligned hillshade + geomorphons ridge/valley lines over a
real SRTM window.

Replaces the old PIL-based basin-colour visualiser (watershed-era,
retired -- see `plans/landform-geomorphons/plan.md`'s "Affected modules").
Same alignment method as the `terrain-detection-resolution` spike's own
render tooling (`tools/render_spike_resolution.py`, not committed to this
branch): a lattice sampled in DCS x/z via `terrain.resample`, hillshaded
with `np.gradient` at 315 deg/45 deg illumination -- no raster
registration, features drawn in the same x/z frame the hillshade lattice
is built in, so alignment is by construction. Uses Pillow (an existing
`world-model` dependency) rather than matplotlib (what the spike tooling
used, never added to `pyproject.toml`) -- this is diagnostic tooling, not
pipeline code, but still shouldn't need a dependency this project hasn't
signed off on.

Not part of the pipeline. Runs the real `terrain.geomorphons`/
`terrain.skeleton`/`terrain.features` modules directly over one window
(no tiling/margin/cache -- that machinery is `build.ingest_terrain`'s,
scoped to a whole SRTM tile; this tool exists to look at one window's
output by eye, same as the spike it replaces).

Run from `world-model/`:

    .venv/bin/python tools/inspect_terrain.py \\
        --srtm-dir <path/to/hgt_tiles/> --center X,Z --radius-km R \\
        [--spacing-m 90] [--lookup-cells 15] [--flat-deg 1.0] \\
        [--min-cells 4] [--min-relief-m 50.0] \\
        [--decimation-tolerance-fraction 0.25] [--out out.png]

Renders the same relief-gated, smoothed-and-decimated geometry
`build.ingest_terrain` stores (`--min-relief-m`/
`--decimation-tolerance-fraction` match that module's own defaults), and
prints per-kind line counts, how many lines the relief gate dropped, and
the raw-vs-stored point-count reduction.
"""

import argparse
import math
import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

import numpy as np
from PIL import Image, ImageDraw

from coordinates import dcs_to_wgs84, dcs_to_wgs84_array
from elevation.dem import SrtmTile
from terrain.features import (
    DEFAULT_DECIMATION_TOLERANCE_FRACTION,
    DEFAULT_MIN_RELIEF_M,
    TerrainComponent,
    component_from_trace,
    filter_by_relief,
    to_stored_features,
)
from terrain.geomorphons import RIDGE_KINDS, VALLEY_KINDS, geomorphons
from terrain.resample import lattice_coords, sample_tiles_bilinear
from terrain.skeleton import close_and_thin, family_mask, trace

_PX_PER_CELL = 3.0


def _needed_tile_names(
    theatre: str, centre_x: float, centre_z: float, radius_m: float, margin_deg: float
) -> set[str]:
    corners = [
        (centre_x - radius_m, centre_z - radius_m),
        (centre_x - radius_m, centre_z + radius_m),
        (centre_x + radius_m, centre_z - radius_m),
        (centre_x + radius_m, centre_z + radius_m),
    ]
    lats, lons = [], []
    for x, z in corners:
        lat, lon = dcs_to_wgs84(theatre, x, z)
        lats.append(lat)
        lons.append(lon)
    lat0, lat1 = min(lats) - margin_deg, max(lats) + margin_deg
    lon0, lon1 = min(lons) - margin_deg, max(lons) + margin_deg
    names = set()
    for lat_deg in range(math.floor(lat0), math.ceil(lat1)):
        for lon_deg in range(math.floor(lon0), math.ceil(lon1)):
            ns = "N" if lat_deg >= 0 else "S"
            ew = "E" if lon_deg >= 0 else "W"
            names.add(f"{ns}{abs(lat_deg):02d}{ew}{abs(lon_deg):03d}.hgt")
    return names


def _hillshade(dem: np.ndarray, spacing_m: float) -> np.ndarray:
    grad_x, grad_z = np.gradient(dem, spacing_m, spacing_m)
    slope = np.pi / 2.0 - np.arctan(np.hypot(grad_x, grad_z))
    aspect = np.arctan2(-grad_x, grad_z)
    azimuth_rad = np.deg2rad(315.0)
    altitude_rad = np.deg2rad(45.0)
    shaded = np.sin(altitude_rad) * np.sin(slope) + np.cos(altitude_rad) * np.cos(
        slope
    ) * np.cos(azimuth_rad - aspect)
    return np.clip(np.nan_to_num(shaded, nan=0.5), 0.0, 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--srtm-dir", type=Path, required=True)
    parser.add_argument("--theatre", default="Syria")
    parser.add_argument("--center", required=True, help="DCS x,z, e.g. -5000,15000")
    parser.add_argument("--radius-km", type=float, required=True)
    parser.add_argument("--spacing-m", type=float, default=90.0)
    parser.add_argument("--lookup-cells", type=int, default=15)
    parser.add_argument("--flat-deg", type=float, default=1.0)
    parser.add_argument("--min-cells", type=int, default=4)
    parser.add_argument("--min-relief-m", type=float, default=DEFAULT_MIN_RELIEF_M)
    parser.add_argument(
        "--decimation-tolerance-fraction",
        type=float,
        default=DEFAULT_DECIMATION_TOLERANCE_FRACTION,
    )
    parser.add_argument("--out", type=Path, default=Path("terrain_inspect.png"))
    args = parser.parse_args()

    centre_x, centre_z = (float(v) for v in args.center.split(","))
    radius_m = args.radius_km * 1000.0

    names = _needed_tile_names(
        args.theatre, centre_x, centre_z, radius_m, margin_deg=0.15
    )
    tiles = [
        SrtmTile.from_file(args.srtm_dir / name)
        for name in sorted(names)
        if (args.srtm_dir / name).exists()
    ]
    if not tiles:
        parser.error(f"No .hgt tiles found under {args.srtm_dir} for this window")

    n_cells = 2 * math.ceil(radius_m / args.spacing_m) + 1
    origin_x = centre_x - (n_cells // 2) * args.spacing_m
    origin_z = centre_z - (n_cells // 2) * args.spacing_m

    xx, zz = lattice_coords(origin_x, origin_z, args.spacing_m, n_cells, n_cells)
    lat, lon = dcs_to_wgs84_array(args.theatre, xx, zz)
    dem = sample_tiles_bilinear(tiles, lat, lon)
    classes = geomorphons(
        dem, args.spacing_m, lookup_cells=args.lookup_cells, flat_deg=args.flat_deg
    )

    raw_components: list[TerrainComponent] = []
    for kind, kinds in (("ridge", RIDGE_KINDS), ("valley", VALLEY_KINDS)):
        mask = family_mask(classes, kinds)
        skeleton = close_and_thin(mask)
        for cells in trace(skeleton, min_cells=args.min_cells):
            raw_components.append(
                component_from_trace(
                    kind, cells, dem, origin_x, origin_z, args.spacing_m
                )
            )

    # Apply the same relief gate (`fix/landform-relief-gate` defect 1) and
    # Chaikin-smoothing-plus-decimation (defect 2) `build.ingest_terrain`
    # actually stores, rather than drawing the raw traced skeleton -- so
    # this render shows what a real build puts in `syria-full.sqlite`, not
    # an earlier, denser intermediate stage.
    gated_components = filter_by_relief(raw_components, min_relief_m=args.min_relief_m)
    stored_features = to_stored_features(
        gated_components,
        source_id=None,
        position_uncertainty_m=args.spacing_m,
        decimation_tolerance_fraction=args.decimation_tolerance_fraction,
    )

    raw_cell_count = sum(len(c.points) for c in gated_components)
    # What `_smooth_for_storage` would store with decimation disabled --
    # the actual "before" figure for defect 2's fix (four Chaikin passes
    # multiply point count by exactly 16, per `terrain.features`'s own
    # construction: each pass doubles the point count). Comparing against
    # `raw_cell_count` instead (the pre-Chaikin trace) understates the
    # reduction decimation achieves, since Chaikin's own 16x inflation is
    # what defect 2 was actually about.
    pre_decimation_point_count = sum(
        len(c.points) * 16 if len(c.points) >= 3 else len(c.points)
        for c in gated_components
    )
    stored_point_count = sum(len(f.geometry) for f in stored_features)
    for kind in ("ridge", "valley"):
        kind_features = [f for f in stored_features if f.kind == kind]
        lengths = [
            sum(
                math.hypot(b[0] - a[0], b[1] - a[1])
                for a, b in zip(f.geometry, f.geometry[1:], strict=False)
            )
            for f in kind_features
        ]
        longest_km = max(lengths) / 1000.0 if lengths else 0.0
        dropped = sum(1 for c in raw_components if c.kind == kind) - sum(
            1 for c in gated_components if c.kind == kind
        )
        print(
            f"{kind}: {len(kind_features)} lines, longest {longest_km:.2f} km "
            f"({dropped} dropped by the relief gate)"
        )
    ratio = (
        pre_decimation_point_count / stored_point_count
        if stored_point_count
        else float("nan")
    )
    print(
        f"stored geometry points: {raw_cell_count} (raw traced cells) -> "
        f"{pre_decimation_point_count} (Chaikin-smoothed, pre-decimation) -> "
        f"{stored_point_count} (stored), {ratio:.1f}x reduction from decimation"
    )

    shaded = _hillshade(dem, args.spacing_m)
    gray = (shaded * 255).astype(np.uint8)
    # North (DCS +x) up: row 0 is min-x; flip vertically so it renders at
    # the top, matching `geometry.bearing_deg`'s convention.
    img_array = np.flipud(gray)
    size_px = round(n_cells * _PX_PER_CELL)
    image = (
        Image.fromarray(img_array)
        .resize((size_px, size_px), Image.NEAREST)
        .convert("RGB")
    )
    draw = ImageDraw.Draw(image)

    def to_px(point: tuple[float, float]) -> tuple[float, float]:
        row = (point[0] - origin_x) / args.spacing_m
        col = (point[1] - origin_z) / args.spacing_m
        px = col * _PX_PER_CELL
        py = size_px - row * _PX_PER_CELL
        return px, py

    colors = {"ridge": (220, 40, 40), "valley": (50, 110, 220)}
    for feature in stored_features:
        pixels = [to_px(p) for p in feature.geometry]
        draw.line(pixels, fill=colors[feature.kind], width=2)

    image.save(args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
