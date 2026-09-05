"""M5 Stage 3: the DCS terrain probe (`land.getHeight` + `land.getSurfaceType`)
-> `ElevationGrid` / `SurfaceGrid`.

Grid shape is caller-supplied (`origin_x`/`origin_z`/`spacing_m`/`n_rows`/
`n_cols`) rather than hardcoded here, so `build/pipeline.py` derives it once
from a `RegionDefinition` and this module stays region-agnostic -- see
`pipeline.probe_grid_for_region`.

**Incremental ladder, not all-at-once.** M5's checklist reaches the full
41x41 (1,681-point) grid via a 100-200pt smoke test, then ~500, then the
full grid -- never jumped to. Each rung's probe output is a JSON-lines file
whose point *names* encode `r{row}c{col}` into this same coordinate system
(see `tools/dcs-mission-probe/terrain_probe_{smoke,500,full}.lua`), so
`ingest_probe` accepts a **partial** grid: any `(row, col)` not present in
`probe_output_path` is left `None` in the resulting grid's `samples`, and
`store.writer.insert_grid` already skips `None` cells rather than inserting
a row for them (see `writer.insert_grid`). A smoke-test-only run therefore
produces a real, queryable (if sparse) grid, not a placeholder.

**SRTM delta is metadata stats only -- never stored samples**, per the M5
checklist ("SRTM delta as metadata stats only (not stored samples)"). This
module never creates SRTM-sourced `grid`/`grid_sample` rows; it only folds
summary statistics (mean/median/stddev/min/max delta, points compared vs.
skipped) into `ElevationGrid.stats`, reusing `elevation.dem.SrtmTile` (M4)
for the external comparison and `coordinates.dcs_to_wgs84` for the point
transform. A point is skipped from the SRTM comparison (counted, not
silently dropped) if it falls outside the supplied tile's coverage or lands
on a data-void sample -- both raise `ValueError` from `SrtmTile.height_at`.
"""

import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from coordinates import dcs_to_wgs84
from elevation.dcs_grid import DcsTerrainSample, parse_terrain_probe_output
from elevation.dem import SrtmTile
from store.models import ElevationGrid, SurfaceGrid

_NAME_RE = re.compile(r"^r(\d+)c(\d+)$")

# `store.models.ElevationGrid`/`SurfaceGrid.provenance` tag for grids built
# from this module's live-mission `land.getHeight`/`land.getSurfaceType`
# probe -- distinct from `build.ingest_srtm.GRID_PROVENANCE_SRTM` (M7 Stage
# 2's primary full-theatre elevation source). See `store/schema.py`'s
# version-3 note.
GRID_PROVENANCE_DCS_PROBE = "dcs_probe"

_SURFACE_TYPE_LABELS: dict[int, str] = {
    1: "LAND",
    2: "SHALLOW_WATER",
    3: "WATER",
    4: "ROAD",
    5: "RUNWAY",
}


@dataclass
class ProbeIngestStats:
    """Census of one `ingest_probe` run, for the research note and the
    "did the grid actually get populated" sanity check the earlier ingest
    stages already do (`BeaconIngestStats`, `OsmIngestStats`,
    `RoadnetIngestStats`)."""

    points_expected: int
    points_received: int
    surface_type_counts: dict[str, int] = field(default_factory=dict)
    srtm_points_compared: int = 0
    srtm_points_skipped: int = 0


def _parse_row_col(name: str, n_rows: int, n_cols: int) -> tuple[int, int]:
    match = _NAME_RE.match(name)
    if match is None:
        raise ValueError(
            f"Probe point name {name!r} doesn't match the expected "
            "'r{row}c{col}' grid-index naming"
        )
    row, col = int(match.group(1)), int(match.group(2))
    if not (0 <= row < n_rows) or not (0 <= col < n_cols):
        raise ValueError(
            f"Probe point {name!r} decodes to (row={row}, col={col}), "
            f"outside the {n_rows}x{n_cols} grid"
        )
    return row, col


def _srtm_delta_stats(
    samples: list[DcsTerrainSample],
    theatre: str,
    srtm_tile: SrtmTile,
) -> tuple[dict[str, Any], int, int]:
    deltas: list[float] = []
    skipped = 0
    for sample in samples:
        lat, lon = dcs_to_wgs84(theatre, sample.x, sample.z)
        try:
            external_m = srtm_tile.height_at(lat, lon)
        except ValueError:
            skipped += 1
            continue
        deltas.append(sample.height_m - external_m)

    if not deltas:
        stats: dict[str, Any] = {
            "points_compared": 0,
            "points_skipped": skipped,
        }
        return stats, 0, skipped

    stats = {
        "points_compared": len(deltas),
        "points_skipped": skipped,
        "mean_delta_m": statistics.mean(deltas),
        "median_delta_m": statistics.median(deltas),
        "stddev_delta_m": statistics.stdev(deltas) if len(deltas) > 1 else 0.0,
        "min_delta_m": min(deltas),
        "max_delta_m": max(deltas),
    }
    return stats, len(deltas), skipped


def ingest_probe(
    probe_output_path: Path,
    theatre: str,
    origin_x: float,
    origin_z: float,
    spacing_m: float,
    n_rows: int,
    n_cols: int,
    source_id: int | None,
    srtm_tile: SrtmTile | None = None,
) -> tuple[ElevationGrid, SurfaceGrid, ProbeIngestStats]:
    """Build `(ElevationGrid, SurfaceGrid, ProbeIngestStats)` from one
    `terrain_probe_*.lua` JSON-lines output file.

    `origin_x`/`origin_z`/`spacing_m`/`n_rows`/`n_cols` define the grid
    coordinate system every point's `r{row}c{col}` name is relative to --
    see `pipeline.probe_grid_for_region`. `srtm_tile`, if given, adds an
    SRTM delta summary to the elevation grid's `stats` (metadata only, per
    the module docstring); if omitted, `stats["srtm"]` is `None`.
    """
    samples = parse_terrain_probe_output(probe_output_path)
    points_expected = n_rows * n_cols

    elevation_samples: list[list[float | None]] = [
        [None] * n_cols for _ in range(n_rows)
    ]
    surface_samples: list[list[int | None]] = [[None] * n_cols for _ in range(n_rows)]
    surface_counts: dict[str, int] = {}

    for sample in samples:
        row, col = _parse_row_col(sample.name, n_rows, n_cols)
        elevation_samples[row][col] = sample.height_m
        surface_samples[row][col] = sample.surface_type
        label = _SURFACE_TYPE_LABELS.get(
            sample.surface_type, f"UNKNOWN_{sample.surface_type}"
        )
        surface_counts[label] = surface_counts.get(label, 0) + 1

    srtm_stats: dict[str, Any] | None
    srtm_compared = 0
    srtm_skipped = 0
    if srtm_tile is not None:
        srtm_stats, srtm_compared, srtm_skipped = _srtm_delta_stats(
            samples, theatre, srtm_tile
        )
    else:
        srtm_stats = None

    stats = ProbeIngestStats(
        points_expected=points_expected,
        points_received=len(samples),
        surface_type_counts=surface_counts,
        srtm_points_compared=srtm_compared,
        srtm_points_skipped=srtm_skipped,
    )

    elevation_grid = ElevationGrid(
        origin_x=origin_x,
        origin_z=origin_z,
        spacing_m=spacing_m,
        n_rows=n_rows,
        n_cols=n_cols,
        source_id=source_id,
        provenance=GRID_PROVENANCE_DCS_PROBE,
        stats={
            "points_expected": points_expected,
            "points_received": len(samples),
            "srtm": srtm_stats,
        },
        samples=elevation_samples,
    )
    surface_grid = SurfaceGrid(
        origin_x=origin_x,
        origin_z=origin_z,
        spacing_m=spacing_m,
        n_rows=n_rows,
        n_cols=n_cols,
        source_id=source_id,
        provenance=GRID_PROVENANCE_DCS_PROBE,
        stats={
            "points_expected": points_expected,
            "points_received": len(samples),
            "counts": surface_counts,
        },
        samples=surface_samples,
    )
    return elevation_grid, surface_grid, stats
