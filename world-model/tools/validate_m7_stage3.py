#!/usr/bin/env python3
"""M7 Stage 3: full `describe_position` + provenance validation pass over a
real `syria-full.sqlite` full-theatre build.

Not part of the pipeline -- a throwaway analysis script per
`plans/m7-full-theatre-pipeline/plan.md` Stage 3 ("Full `describe_position`
correctness pass over a wider, deliberately geographically-spread
control-point set (coastal, mountainous, urban, desert). Confirm
provenance/confidence fields are correctly populated at scale --
specifically that `elevation` features are never ambiguous about `"srtm"`
vs `"dcs_probe"` provenance"). Reuses `build.validate`
(`check_road_count`, `spot_check_positions`, `check_elevation_provenance`),
already unit-tested against small fixtures in `tests/test_build_validate.py`
-- this script is the one thing those tests cannot cover, running the same
logic against a real full-theatre store.

Unlike `validate_m7_stage1.py`, this reads the full `tests/control_points.py`
set -- Stage 1's original four points (Damascus/Latakia/Beirut/Aleppo) plus
Stage 3's four additions spread across the theatre's other terrain types
(coastal: Rene Mouawad/Klieat; urban: Mezzeh; desert: Deir ez-Zor;
mountainous: Kahramanmaras). This does **not** include the M5 roadnet
resync audit -- that is a separate follow-up task, out of scope for M7
(see the plan's "Deferred / Out of Scope").

Per the plan's "Execution boundary", nobody but the user builds
`syria-full.sqlite` -- this script does not build anything, it only reads
an already-built store. See `world-model/docs/M7_RUN_INSTRUCTIONS.md`'s
Stage 3 section for when to run this.

Run from `world-model/`, after building `data/world-model/syria-full.sqlite`
per the run instructions:

    .venv/bin/python tools/validate_m7_stage3.py
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
    check_elevation_provenance,
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
        road_check = check_road_count(road_count)

        spot_points = [
            SpotCheckPoint(name=cp.name, x=cp.dcs_x, z=cp.dcs_z) for cp in CONTROL_POINTS
        ]
        spot_checks = spot_check_positions(conn, _THEATRE, spot_points)

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

        provenance_report = check_elevation_provenance(conn, _THEATRE, spot_points)

        result = {
            "db_path": str(_DB_PATH),
            "control_points_checked": len(CONTROL_POINTS),
            "road_count_check": {
                "expected": road_check.expected,
                "actual": road_check.actual,
                "tolerance_fraction": road_check.tolerance_fraction,
                "within_tolerance": road_check.within_tolerance,
            },
            "coordinate_control_point_checks": coordinate_checks,
            "all_coordinate_checks_within_tolerance": all(
                c["within_tolerance"] for c in coordinate_checks
            ),
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
            "provenance_checks": {
                "all_ok": provenance_report.all_ok,
                "points": [
                    {
                        "name": c.name,
                        "elevation_source": c.elevation_source,
                        "elevation_provenance_ok": c.elevation_provenance_ok,
                        "surface_type_provenance": c.surface_type_provenance,
                        "surface_type_provenance_ok": c.surface_type_provenance_ok,
                    }
                    for c in provenance_report.checks
                ],
            },
        }
        print(json.dumps(result, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
