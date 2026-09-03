#!/usr/bin/env python3
"""Diagnostic: human-readable table of coordinate-transform control-point errors.

Not part of the pipeline — reuses tests/control_points.py to print, for each
known control point, the DCS-native coordinate, the transformed lat/lon, the
published real-world lat/lon, and the resulting error in meters. Run from the
world-model/ directory:

    .venv/bin/python tools/report_control_point_errors.py
"""

import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "tests"))

from control_points import CONTROL_POINTS, haversine_distance_m

from coordinates import dcs_to_wgs84


def main() -> None:
    header = (
        f"{'Theatre':<8} {'Point':<32} {'DCS (x, z)':<28} "
        f"{'Transformed lat/lon':<24} {'Real-world lat/lon':<24} {'Error (m)':>10}"
    )
    print(header)
    print("-" * len(header))
    for point in CONTROL_POINTS:
        lat, lon = dcs_to_wgs84(point.theatre, point.dcs_x, point.dcs_z)
        error_m = haversine_distance_m(lat, lon, point.real_lat, point.real_lon)
        dcs_coord = f"({point.dcs_x:.1f}, {point.dcs_z:.1f})"
        transformed = f"{lat:.5f}, {lon:.5f}"
        real_world = f"{point.real_lat:.5f}, {point.real_lon:.5f}"
        print(
            f"{point.theatre:<8} {point.name:<32} {dcs_coord:<28} "
            f"{transformed:<24} {real_world:<24} {error_m:>10.1f}"
        )


if __name__ == "__main__":
    main()
