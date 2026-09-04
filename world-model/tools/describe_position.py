#!/usr/bin/env python3
"""CLI over `query.describe_position` -- the human-inspectable diagnostic
this project's testing philosophy asks for (a human should be able to look
at a query result and say whether it is sane).

Run from `world-model/`:

    .venv/bin/python tools/describe_position.py <db> <theatre> <x> <z>
    .venv/bin/python tools/describe_position.py <db> <theatre> \\
        --latlon <lat> <lon>

Prints the `PositionDescription` as JSON.
"""

import argparse
import dataclasses
import json
import sqlite3
import sys
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from coordinates import wgs84_to_dcs
from query import describe_position


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", type=Path)
    parser.add_argument("theatre")
    parser.add_argument("x", type=float, nargs="?")
    parser.add_argument("z", type=float, nargs="?")
    parser.add_argument(
        "--latlon",
        nargs=2,
        type=float,
        metavar=("LAT", "LON"),
        default=None,
        help="Give the query point as WGS84 lat/lon instead of DCS x/z.",
    )
    args = parser.parse_args()

    if args.latlon is not None:
        lat, lon = args.latlon
        x, z = wgs84_to_dcs(args.theatre, lat, lon)
    else:
        if args.x is None or args.z is None:
            parser.error("Either both x and z, or --latlon LAT LON, are required")
        x, z = args.x, args.z

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        description = describe_position(conn, args.theatre, x, z)
    finally:
        conn.close()

    print(json.dumps(dataclasses.asdict(description), indent=2))


if __name__ == "__main__":
    main()
