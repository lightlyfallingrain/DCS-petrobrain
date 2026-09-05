#!/usr/bin/env python3
"""M7 Stage 1: validate a real `syria-full.sqlite` full-theatre build.

Not part of the pipeline -- a throwaway analysis script per
`plans/m7-full-theatre-pipeline/plan.md` Stage 1 ("Validate: row counts
sane relative to Stage 0's census; `describe_position` returns correct
nearest-road/nearest-settlement at a handful of scattered control points").
Reuses `build.validate` (`check_road_count`, `spot_check_positions`),
already unit-tested against small fixtures in
`tests/test_build_validate.py` -- this script is the one thing those tests
cannot cover, running the same logic against a real full-theatre store.

Per the plan's "Execution boundary", nobody but the user builds
`syria-full.sqlite` -- this script does not build anything, it only reads
an already-built store. See `world-model/docs/M7_RUN_INSTRUCTIONS.md` for
how to build it first.

Run from `world-model/`, after building `data/world-model/syria-full.sqlite`
per the run instructions:

    .venv/bin/python tools/validate_m7_stage1.py
"""

import json
import sqlite3
import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "tests"))

from build.validate import (
    SpotCheckPoint,
    check_road_count,
    spot_check_positions,
)
from control_points import CONTROL_POINTS, haversine_distance_m

_DB_PATH = _WORLD_MODEL_ROOT / "data" / "world-model" / "syria-full.sqlite"
_THEATRE = "Syria"


def main() -> None:
    if not _DB_PATH.exists():
        print(
            f"error: {_DB_PATH} does not exist -- build it first per "
            "world-model/docs/M7_RUN_INSTRUCTIONS.md",
            file=sys.stderr,
        )
        sys.exit(1)

    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
    try:
        (road_count,) = conn.execute(
            "SELECT COUNT(*) FROM feature WHERE kind = 'road'"
        ).fetchone()
        (named_place_count,) = conn.execute(
            "SELECT COUNT(*) FROM feature WHERE kind = 'named_place'"
        ).fetchone()
        (airfield_count,) = conn.execute(
            "SELECT COUNT(*) FROM feature WHERE kind = 'airfield'"
        ).fetchone()

        road_check = check_road_count(road_count)

        spot_checks = spot_check_positions(
            conn,
            _THEATRE,
            [
                SpotCheckPoint(name=cp.name, x=cp.dcs_x, z=cp.dcs_z)
                for cp in CONTROL_POINTS
            ],
        )

        coordinate_checks = []
        for cp, spot_check in zip(CONTROL_POINTS, spot_checks, strict=True):
            residual_m = haversine_distance_m(
                spot_check.lat, spot_check.lon, cp.real_lat, cp.real_lon
            )
            coordinate_checks.append(
                {
                    "name": cp.name,
                    "residual_m": residual_m,
                    "expected_max_residual_m": cp.expected_max_residual_m,
                    "within_tolerance": residual_m <= cp.expected_max_residual_m,
                }
            )

        result = {
            "db_path": str(_DB_PATH),
            "feature_counts": {
                "road": road_count,
                "named_place": named_place_count,
                "airfield": airfield_count,
            },
            "road_count_check": {
                "expected": road_check.expected,
                "actual": road_check.actual,
                "tolerance_fraction": road_check.tolerance_fraction,
                "within_tolerance": road_check.within_tolerance,
            },
            "coordinate_control_point_checks": coordinate_checks,
            "spot_checks": [
                {
                    "name": sc.name,
                    "lat": sc.lat,
                    "lon": sc.lon,
                    "nearest_road_found": sc.nearest_road_found,
                    "nearest_road_distance_m": sc.nearest_road_distance_m,
                    "nearest_settlement_found": sc.nearest_settlement_found,
                    "nearest_settlement_distance_m": sc.nearest_settlement_distance_m,
                }
                for sc in spot_checks
            ],
        }
        print(json.dumps(result, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
