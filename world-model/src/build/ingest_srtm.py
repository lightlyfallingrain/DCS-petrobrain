"""M7 Stage 2: SRTM `.hgt` tiles -> the primary full-theatre `elevation` grid.

Locked decision (see `plans/m7-full-theatre-pipeline/plan.md` Status /
Locked Decision 1): SRTM becomes the **primary** elevation source for a
full-theatre build, not a comparison-only DEM. SRTM ships at its own native
~30-90m grid density everywhere in the theatre with no probing gap, unlike
the DCS live-mission probe (`build.ingest_probe`), which is repurposed to a
small scattered spot-check control-point set that validates SRTM alignment
accuracy (see `build.validate.compare_probe_to_srtm`) rather than supplying
the primary grid.

Mirrors `ingest_probe`'s shape (a caller-supplied regular grid definition --
`origin_x`/`origin_z`/`spacing_m`/`n_rows`/`n_cols` -- from
`build.pipeline.probe_grid_for_region`), but resamples from one or more
`elevation.dem.SrtmTile`s instead of parsing a probe output file. A single
`.hgt` tile is always exactly 1x1 degree by format, so a full theatre
(Syria spans roughly 7 degrees of latitude and 8 of longitude) needs several
tiles; `elevation.dem.select_tile` picks the tile covering each grid cell's
`(lat, lon)` independently, since SRTM's 1-degree tile boundaries don't line
up with this grid's regular DCS-metre spacing.

A cell whose `(lat, lon)` isn't covered by any given tile, or lands on a
SRTM data void, is left `None` (counted in `points_void_or_uncovered`), the
same "absence reported as absence" contract every other grid/feature ingest
module in this package already follows -- never silently guessed or
zero-filled.

**Row-count sizing is a real, undecided-by-this-module concern.** At the
existing 500m probe-grid spacing, `syria-full`'s ~827x771 km padded bbox
produces on the order of 1,650 x 1,540 = ~2.5 million grid cells -- SQLite
handles millions of rows without issue per M5's own findings, but this is
the first full-theatre-scale grid this pipeline has ever built, and
`build.pipeline.build_region`'s caller (the CLI, ultimately the user
per the plan's "Execution boundary") chooses the actual spacing to use, not
this module.
"""

import logging
import time
from dataclasses import dataclass

from coordinates import dcs_to_wgs84
from elevation.dem import SrtmTile, select_tile
from store.models import ElevationGrid

logger = logging.getLogger(__name__)

# `store.models.ElevationGrid.provenance` tag for grids built by this
# module -- distinct from `build.ingest_probe.GRID_PROVENANCE_DCS_PROBE`.
# See `store/schema.py`'s version-3 note.
GRID_PROVENANCE_SRTM = "srtm"

# How often the row loop below logs progress, in rows. A full-theatre grid
# is on the order of millions of cells (see this module's docstring); without
# periodic feedback, this stage looks indistinguishable from a hang for
# however long it actually takes.
_PROGRESS_LOG_INTERVAL_ROWS = 50


@dataclass
class SrtmIngestStats:
    """Census of one `ingest_srtm_grid` run, for the research note and the
    "did the grid actually get populated" sanity check the other ingest
    modules' stats dataclasses already do."""

    points_expected: int
    points_sampled: int
    points_void_or_uncovered: int
    tiles_used: int


def ingest_srtm_grid(
    tiles: list[SrtmTile],
    theatre: str,
    origin_x: float,
    origin_z: float,
    spacing_m: float,
    n_rows: int,
    n_cols: int,
    source_id: int | None,
) -> tuple[ElevationGrid, SrtmIngestStats]:
    """Build the primary full-theatre `ElevationGrid` (`provenance=
    "srtm"`) by resampling `tiles` onto the regular DCS-metre grid defined
    by `origin_x`/`origin_z`/`spacing_m`/`n_rows`/`n_cols` -- cell `(row,
    col)` sits at `(origin_x + row * spacing_m, origin_z + col * spacing_m)`,
    matching `ElevationGrid`'s documented convention (and
    `build.pipeline.probe_grid_for_region`'s, which supplies these five
    values for a `RegionDefinition`).

    For each cell, transforms its DCS `(x, z)` to WGS84 via `theatre`'s
    projection, finds the covering tile (`elevation.dem.select_tile`), and
    samples `SrtmTile.height_at`. Raises nothing itself: a cell with no
    covering tile, or one whose 4 bilinear-interpolation neighbors include a
    data void, is left `None` rather than raising, since a full-theatre grid
    is expected to run to completion even where SRTM coverage is imperfect
    -- `SrtmIngestStats.points_void_or_uncovered` reports how often that
    happened, for the caller to judge.
    """
    samples: list[list[float | None]] = [[None] * n_cols for _ in range(n_rows)]
    sampled = 0
    void_or_uncovered = 0
    tiles_used: set[tuple[float, float]] = set()
    started_at = time.monotonic()

    for row in range(n_rows):
        if row % _PROGRESS_LOG_INTERVAL_ROWS == 0 and row > 0:
            elapsed_s = time.monotonic() - started_at
            logger.info(
                "ingest_srtm: row %d/%d (%.1f%%, %d sampled, %d void/uncovered, %.1fs elapsed)",
                row,
                n_rows,
                100.0 * row / n_rows,
                sampled,
                void_or_uncovered,
                elapsed_s,
            )
        x = origin_x + row * spacing_m
        for col in range(n_cols):
            z = origin_z + col * spacing_m
            lat, lon = dcs_to_wgs84(theatre, x, z)
            tile = select_tile(tiles, lat, lon)
            if tile is None:
                void_or_uncovered += 1
                continue
            try:
                height = tile.height_at(lat, lon)
            except ValueError:
                void_or_uncovered += 1
                continue
            samples[row][col] = height
            sampled += 1
            tiles_used.add((tile.sw_lat, tile.sw_lon))

    points_expected = n_rows * n_cols
    stats = SrtmIngestStats(
        points_expected=points_expected,
        points_sampled=sampled,
        points_void_or_uncovered=void_or_uncovered,
        tiles_used=len(tiles_used),
    )
    grid = ElevationGrid(
        origin_x=origin_x,
        origin_z=origin_z,
        spacing_m=spacing_m,
        n_rows=n_rows,
        n_cols=n_cols,
        source_id=source_id,
        provenance=GRID_PROVENANCE_SRTM,
        stats={
            "points_expected": points_expected,
            "points_sampled": sampled,
            "points_void_or_uncovered": void_or_uncovered,
            "tiles_used": len(tiles_used),
        },
        samples=samples,
    )
    return grid, stats
