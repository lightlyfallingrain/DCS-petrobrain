"""M7 Stage 1 validation: sanity checks for a full-theatre build, run
against an already-built `.sqlite` (via `spot_check_positions`) or against
a `BuildReport`'s road count (via `check_road_count`).

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
"""

import sqlite3
from dataclasses import dataclass

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
