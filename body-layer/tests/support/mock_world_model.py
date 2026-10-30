"""Synthetic world-model store for the mock-flight chain tests, built
directly via world-model's `store.writer` -- the same "wiring test, not a
terrain-accuracy claim" precedent `world-model/tests/test_describe_position.py`
already establishes for a synthetic fixture store, applied here so
`NakedEyePerceptionSource`'s real terrain line-of-sight gate
(`perception.geometry.line_of_sight_clear`) actually runs against real
elevation-grid data instead of being monkeypatched to always pass (the
per-file convention `test_emission_pipeline.py`/`test_naked_eye_source.py`
use, deliberately not reused here -- see `plans/mock-flight-fixture/plan.md`'s
"Decisions made" section).

Coverage is a flat, low (50m) elevation plane over the small rectangle the
canonical fixture's ownship track and world objects actually occupy (DCS x
in roughly [-500, 2000], z in [-500, 500] -- see
`tests/fixtures/mock_flight_canonical.json`'s own positions). Flat and low
relative to every ownship/object altitude in that fixture (500-700m) is a
deliberate choice: it makes every line-of-sight check in the fixture clear
by construction, so this store's only job is to prove the LOS *wiring*
works, exactly as `test_describe_position.py`'s own docstring frames it --
real-terrain LOS correctness stays the World Model Builder's own
control-point tests' job, never this fixture's."""

from __future__ import annotations

from pathlib import Path

from store.models import ElevationGrid, Region
from store.writer import insert_grid, insert_region, open_for_build

#: Flat elevation (metres MSL) for every cell -- well below every ownship/
#: object altitude the canonical fixture uses (500-700m), so every
#: straight-line sightline in that fixture clears it by construction.
FLAT_ELEVATION_M = 50.0

GRID_ORIGIN_X = -500.0
GRID_ORIGIN_Z = -500.0
GRID_SPACING_M = 500.0
#: Rows cover x in [-500, 2000] (six rows at 500m spacing), enough to
#: contain the canonical fixture's ownship track (x 0-1140) and both world
#: objects (x 1400, 1800) with margin.
GRID_N_ROWS = 6
#: Cols cover z in [-500, 500] (three cols at 500m spacing) -- the canonical
#: fixture keeps ownship and both objects at z=0, so this is generous
#: margin, not a tight fit.
GRID_N_COLS = 3

REGION_NAME = "mock-flight-fixture"
REGION_THEATRE = "Syria"


def build_mock_world_model(db_path: Path) -> None:
    """Build a fresh region `.sqlite` at `db_path` containing a `Region`
    row and one flat elevation grid covering the canonical fixture's own
    geometry. Callers open the result read-only via
    `perception.geometry.open_world_model`, mirroring how a real built
    region is consumed everywhere else in this project. A thin wrapper
    over `build_flat_world_model` (BL-B104 Stage 7) with this file's
    original fixed bounds -- unchanged behaviour for every existing
    caller of this name."""
    build_flat_world_model(
        db_path,
        region_name=REGION_NAME,
        theatre=REGION_THEATRE,
        centre_x=750.0,
        centre_z=0.0,
        half_extent_x_m=1500.0,
        half_extent_z_m=500.0,
        origin_x=GRID_ORIGIN_X,
        origin_z=GRID_ORIGIN_Z,
        spacing_m=GRID_SPACING_M,
        n_rows=GRID_N_ROWS,
        n_cols=GRID_N_COLS,
    )


def build_flat_world_model(
    db_path: Path,
    *,
    region_name: str,
    theatre: str,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    origin_x: float,
    origin_z: float,
    spacing_m: float,
    n_rows: int,
    n_cols: int,
    elevation_m: float = FLAT_ELEVATION_M,
) -> None:
    """`build_mock_world_model`'s general form (BL-B104 Stage 7,
    `plans/bl-b104-ground-contacts-on-ground/plan.md`): a flat elevation
    plane over a caller-sized rectangle, for scenarios whose ownship
    track/placed units range further than the canonical fixture's small
    bounding box (e.g. a 5 km closing run). Deletes any existing file at
    `db_path` first, per `store.writer.open_for_build`'s own contract."""
    conn = open_for_build(db_path)
    try:
        insert_region(
            conn,
            Region(
                name=region_name,
                theatre=theatre,
                centre_x=centre_x,
                centre_z=centre_z,
                half_extent_x_m=half_extent_x_m,
                half_extent_z_m=half_extent_z_m,
                built_at="2026-09-10T00:00:00+00:00",
            ),
        )
        samples: list[list[float | None]] = [
            [elevation_m for _ in range(n_cols)] for _ in range(n_rows)
        ]
        insert_grid(
            conn,
            ElevationGrid(
                origin_x=origin_x,
                origin_z=origin_z,
                spacing_m=spacing_m,
                n_rows=n_rows,
                n_cols=n_cols,
                source_id=None,
                provenance="dcs_probe",
                stats={
                    "points_expected": n_rows * n_cols,
                    "points_received": n_rows * n_cols,
                },
                samples=samples,
            ),
        )
    finally:
        conn.close()
