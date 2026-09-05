"""M7 validation: sanity checks for a full-theatre build.

**Stage 1** (sanity checks against an already-built `.sqlite`): run against
an already-built `.sqlite` (via `spot_check_positions`) or against a
`BuildReport`'s road count (via `check_road_count`).

Per `plans/m7-full-theatre-pipeline/plan.md` Stage 1 ("Validate: row counts
sane relative to Stage 0's census; `describe_position` returns correct
nearest-road/nearest-settlement at a handful of scattered control points")
and the plan's "Execution boundary": nobody but the user runs the real
full-theatre build, so this module is deliberately store-agnostic wiring
that can be, and is, tested against small fixtures -- the real check
against `syria-full.sqlite` is something the run-instructions doc tells the
user to run themselves (`tools/validate_m7_stage1.py`), not something this
implementation demonstrates against real data.

`SpotCheckPoint` is intentionally its own small type, not a reuse of
`tests/control_points.py`'s `ControlPoint` -- `src/` must not import from
`tests/` (test fixtures are not pipeline dependencies), and this check only
needs a DCS-native `(x, z)` and a label, not a published real-world lat/lon
(that coordinate-tolerance check is `tests/control_points.py`'s job, wired
through `query.describe_position`'s `lat`/`lon` fields directly, not
through this module).

**Stage 2** (`compare_probe_to_srtm`): generalizes M4's single-region
Gemerek DCS-vs-SRTM delta check (mean +13.89m, stddev 28.02m) to a
scattered, theatre-spread control-point set. Takes DCS live-probe elevation
samples (`elevation.dcs_grid.parse_probe_output`'s output --
`elevation_probe.lua`'s spot-check mission run, per the plan's Stage 2
"reused as-is" decision) and one or more `elevation.dem.SrtmTile`s, and
reports the alignment delta at each shared point plus mean/median/stddev/
min/max summary stats -- independent of `store`/`sqlite3`, since this
answers "does DCS agree with SRTM here", not "what's in the built store".

**Stage 3** (`check_elevation_provenance`): per the plan's Stage 3
("Confirm provenance/confidence fields are correctly populated at scale --
specifically that `elevation` features are never ambiguous about `"srtm"`
vs `"dcs_probe"` provenance"), runs `describe_position` at a scattered
point set and checks that `elevation.source`/`surface_type.provenance` are
each one of the two real grid-provenance values
(`store.reader.grid_provenance`'s documented `"srtm"`/`"dcs_probe"`
contract) -- never `"unavailable"` (no grid built at all) and never some
other/stale string (e.g. the hardcoded `"dcs"` this project shipped before
M7 Stage 2 fixed it, see `query/describe.py`'s module docstring). This
reuses Stage 1's `SpotCheckPoint`/`describe_position` plumbing rather than
adding a second store-reading path.
"""

import sqlite3
import statistics
from dataclasses import dataclass, field

from coordinates import dcs_to_wgs84
from elevation.dcs_grid import DcsElevationSample
from elevation.dem import SrtmTile, select_tile
from query import describe_position

# Real full-theatre `.routes` walk result, `syria-full` region -- see
# world-model/research/2026-09-05-m7-stage0-roadnet-census.md. Stage 1's
# road-count check compares a real build's road feature count against this
# reference, not a re-derived guess: Stage 0 already found
# `routes_in_region == routes_found_whole_file`, so a Stage 1 build's `road`
# feature count should land close to this number (a small amount of
# difference is possible from clipped/degenerate-geometry rows dropped
# during feature construction, not from region-bbox filtering).
SYRIA_FULL_EXPECTED_ROAD_COUNT = 14_833


@dataclass(frozen=True)
class SpotCheckPoint:
    """One DCS-native `(x, z)` location to sanity-check `describe_position`
    against. Deliberately independent of `tests/control_points.py`'s
    `ControlPoint` -- see module docstring."""

    name: str
    x: float
    z: float


@dataclass(frozen=True)
class SpotCheckResult:
    """What `describe_position` answered for one `SpotCheckPoint` -- enough
    to eyeball "did this location get real nearest-road/nearest-settlement
    answers, or is the store empty/broken here" without asserting an exact
    expected value (Stage 1 has no independent ground truth for "the
    nearest road to this exact point", unlike the coordinate-tolerance
    control-point check)."""

    name: str
    lat: float
    lon: float
    nearest_road_found: bool
    nearest_road_distance_m: float | None
    nearest_settlement_found: bool
    nearest_settlement_distance_m: float | None


def spot_check_positions(
    conn: sqlite3.Connection, theatre: str, points: list[SpotCheckPoint]
) -> list[SpotCheckResult]:
    """Run `describe_position` at each of `points` and summarize whether a
    nearest road/settlement was found, for a human (or the DoD gate) to
    scan for suspicious gaps -- e.g. every point coming back with no
    nearest road at all would indicate a broken roadnet layer, not that
    every scattered point happens to be far from any road."""
    results = []
    for point in points:
        description = describe_position(conn, theatre, point.x, point.z)
        results.append(
            SpotCheckResult(
                name=point.name,
                lat=description.lat,
                lon=description.lon,
                nearest_road_found=description.nearest_road is not None,
                nearest_road_distance_m=(
                    description.nearest_road.distance_m
                    if description.nearest_road is not None
                    else None
                ),
                nearest_settlement_found=description.nearest_settlement is not None,
                nearest_settlement_distance_m=(
                    description.nearest_settlement.distance_m
                    if description.nearest_settlement is not None
                    else None
                ),
            )
        )
    return results


@dataclass(frozen=True)
class RoadCountCheck:
    """Whether a build's road-feature count is "sane relative to Stage 0's
    census" (the plan's phrase) -- a tolerance band around a known real
    count, not an exact match (feature construction can drop a small
    number of degenerate/clipped rows the raw route walk still counted)."""

    expected: int
    actual: int
    tolerance_fraction: float
    within_tolerance: bool


def check_road_count(
    actual_road_count: int,
    expected: int = SYRIA_FULL_EXPECTED_ROAD_COUNT,
    tolerance_fraction: float = 0.05,
) -> RoadCountCheck:
    """`actual_road_count` is sane if it's within `tolerance_fraction` of
    `expected` (default 5%, generous relative to Stage 0's ~1.5%
    `sync_loss_events` rate and the 2-of-14,833 clipped-route count -- see
    `world-model/research/2026-09-05-m7-stage0-roadnet-census.md`)."""
    lower = expected * (1.0 - tolerance_fraction)
    upper = expected * (1.0 + tolerance_fraction)
    return RoadCountCheck(
        expected=expected,
        actual=actual_road_count,
        tolerance_fraction=tolerance_fraction,
        within_tolerance=lower <= actual_road_count <= upper,
    )


@dataclass(frozen=True)
class ElevationAlignmentPoint:
    """One spot-check point's DCS-probe vs SRTM elevation comparison.
    `delta_m` is `dcs_probe_m - srtm_m`, matching
    `build.ingest_probe`'s existing delta-sign convention."""

    name: str
    dcs_probe_m: float
    srtm_m: float
    delta_m: float


@dataclass(frozen=True)
class ElevationAlignmentReport:
    """Theatre-spread generalization of M4's single-region Gemerek delta
    check (mean +13.89m, stddev 28.02m) -- summary stats plus the individual
    per-point deltas, so a caller can see whether alignment quality is
    uniform across the theatre or clusters/degrades with distance from a
    reference point, per the plan's Stage 2 Risk note."""

    points: list[ElevationAlignmentPoint] = field(default_factory=list)
    points_skipped: int = 0
    mean_delta_m: float | None = None
    median_delta_m: float | None = None
    stddev_delta_m: float | None = None
    min_delta_m: float | None = None
    max_delta_m: float | None = None


def compare_probe_to_srtm(
    probe_samples: list[DcsElevationSample],
    tiles: list[SrtmTile],
    theatre: str,
) -> ElevationAlignmentReport:
    """Compare each of `probe_samples` (DCS live-probe spot-check points,
    DCS-native x/z + `land.getHeight`) against SRTM at the same point, via
    whichever of `tiles` covers it (`elevation.dem.select_tile`).

    A sample with no covering tile, or landing on a SRTM data void, is
    counted in `points_skipped`, not silently dropped or allowed to skew the
    summary stats -- mirrors `build.ingest_probe`'s existing
    `srtm_points_skipped` handling for the single-region case, generalized
    here to a scattered multi-tile point set instead of one shared tile.
    """
    points: list[ElevationAlignmentPoint] = []
    skipped = 0
    for sample in probe_samples:
        lat, lon = dcs_to_wgs84(theatre, sample.x, sample.z)
        tile = select_tile(tiles, lat, lon)
        if tile is None:
            skipped += 1
            continue
        try:
            srtm_m = tile.height_at(lat, lon)
        except ValueError:
            skipped += 1
            continue
        points.append(
            ElevationAlignmentPoint(
                name=sample.name,
                dcs_probe_m=sample.height_m,
                srtm_m=srtm_m,
                delta_m=sample.height_m - srtm_m,
            )
        )

    if not points:
        return ElevationAlignmentReport(points=points, points_skipped=skipped)

    deltas = [p.delta_m for p in points]
    return ElevationAlignmentReport(
        points=points,
        points_skipped=skipped,
        mean_delta_m=statistics.mean(deltas),
        median_delta_m=statistics.median(deltas),
        stddev_delta_m=statistics.stdev(deltas) if len(deltas) > 1 else 0.0,
        min_delta_m=min(deltas),
        max_delta_m=max(deltas),
    )


# The only two provenance values `build.ingest_srtm`/`build.ingest_probe`
# ever write (`GRID_PROVENANCE_SRTM`/`GRID_PROVENANCE_DCS_PROBE`). Not
# imported directly from those modules to avoid a cross-import cycle purely
# for two string literals; pinned here and cross-checked by
# `tests/test_build_validate.py` against the real constants.
_VALID_GRID_PROVENANCE = frozenset({"srtm", "dcs_probe"})


@dataclass(frozen=True)
class ProvenanceSpotCheck:
    """One point's `describe_position` elevation/surface_type provenance
    labels, plus whether each is unambiguously one of the two real grid
    sources. `"unavailable"` (no grid built for that kind at all) and any
    other/stale string both count as not-ok -- Stage 3 is checking that
    provenance is never ambiguous, not merely that it is present."""

    name: str
    elevation_source: str
    elevation_provenance_ok: bool
    surface_type_provenance: str
    surface_type_provenance_ok: bool


@dataclass(frozen=True)
class ProvenanceCheckReport:
    """Whole-set summary of `ProvenanceSpotCheck` results -- `all_ok` is
    `False` if even one point's elevation or surface_type provenance is
    ambiguous/missing, so a caller doesn't have to scan `checks` by hand to
    notice a single bad point in an otherwise-clean scattered set."""

    checks: list[ProvenanceSpotCheck]
    all_ok: bool


def check_elevation_provenance(
    conn: sqlite3.Connection, theatre: str, points: list[SpotCheckPoint]
) -> ProvenanceCheckReport:
    """Run `describe_position` at each of `points` and confirm its
    `elevation.source`/`surface_type.provenance` are each unambiguously
    `"srtm"` or `"dcs_probe"` -- the store-level half of the M7 Stage 2
    provenance-separation fix (`query/describe.py`'s `grid_provenance`
    read), exercised here at a wider, theatre-spread point set per the
    plan's Stage 3 ("Confirm provenance/confidence fields are correctly
    populated at scale")."""
    checks = []
    for point in points:
        description = describe_position(conn, theatre, point.x, point.z)
        elevation_source = description.elevation.source
        surface_type_provenance = description.surface_type.provenance
        checks.append(
            ProvenanceSpotCheck(
                name=point.name,
                elevation_source=elevation_source,
                elevation_provenance_ok=elevation_source in _VALID_GRID_PROVENANCE,
                surface_type_provenance=surface_type_provenance,
                surface_type_provenance_ok=surface_type_provenance
                in _VALID_GRID_PROVENANCE,
            )
        )
    return ProvenanceCheckReport(
        checks=checks,
        all_ok=all(
            check.elevation_provenance_ok and check.surface_type_provenance_ok
            for check in checks
        ),
    )
