#!/usr/bin/env python3
"""M7 Stage 4: perf measurements for a real full-theatre `syria-full.sqlite`.

Not part of the pipeline -- a throwaway measurement script per
`plans/m7-full-theatre-pipeline/plan.md` Stage 4 ("`.sqlite` file size, full
rebuild wall time, `describe_position` latency over a full-theatre-scale
sample of points ... mirrors M5 Stage 5's format"). Mirrors
`measure_m5_stage5_perf.py`'s three-subcommand shape (`latency`,
`rebuild`, `sqlite-size` -- M5's fourth subcommand, `routes-walk`, measured
the `.routes` streaming claim directly and doesn't need re-measuring here,
that claim doesn't change with region size) and its module docstring's
convention of documenting platform-specific `resource.getrusage` behaviour
inline rather than assuming it.

Per the plan's "Execution boundary": nobody but the user builds or measures
the real `syria-full.sqlite` -- this script is code the user runs
themselves, on their own machine, against their own real build. It is not
run here against real full-theatre data; `tests/test_measure_m7_stage4_
perf.py` verifies the sampling/reporting logic against a small synthetic
fixture store instead (same posture as every other M7 stage's test suite).

    .venv/bin/python tools/measure_m7_stage4_perf.py latency [--region syria-full] [--n-random 300] [--n-boundary 40]
    .venv/bin/python tools/measure_m7_stage4_perf.py sqlite-size [--region syria-full]
    .venv/bin/python tools/measure_m7_stage4_perf.py rebuild syria-full -- --towns <path> --beacons <path> --routes <path> --srtm-dir <path>

Each subcommand prints one JSON object to stdout.
"""

import argparse
import json
import random
import sqlite3
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "tests"))

from build.region import REGIONS, RegionDefinition
from control_points import CONTROL_POINTS, ControlPoint

_DEFAULT_REGION = "syria-full"


def _db_path_for_region(region_name: str) -> Path:
    return _WORLD_MODEL_ROOT / "data" / "world-model" / f"{region_name}.sqlite"


@dataclass(frozen=True)
class LatencyStats:
    """Summary of a batch of individually-timed `describe_position` calls,
    same shape as M5 Stage 5's inline dict so the two notes are directly
    comparable."""

    n_points: int
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float


def _percentile(sorted_values: list[float], p: float) -> float:
    n = len(sorted_values)
    idx = min(n - 1, max(0, round(p * (n - 1))))
    return sorted_values[idx]


def sample_points_for_region(
    region: RegionDefinition,
    control_points: list[ControlPoint],
    n_random: int = 300,
    n_boundary: int = 40,
    seed: int = 20260905,
) -> list[tuple[str, float, float]]:
    """A full-theatre-scale sample -- the change Stage 4 exists to make
    relative to M5 Stage 5's 100 points confined to one 20km box:

    - every registered control point for this region's theatre (named,
      independently-verified real-world locations already spread across
      coastal/urban/desert/mountainous terrain per M7 Stage 3 -- reusing
      them here means a latency point double-checks a location this
      project already has an independent correctness opinion about, not
      just a fresh random coordinate);
    - `n_random` points drawn uniformly across the region's **entire**
      bbox (not a small sub-box);
    - `n_boundary` points extended to 1.05x the half-extents in each axis,
      to include near-boundary/outside-coverage points, mirroring M5
      Stage 5's own 1.5x-extension idea but scaled down since a
      full-theatre region's edges are far more remote than a 20km box's.

    Returns `(label, x, z)` triples so a report can distinguish real
    control points from random fill.
    """
    rng = random.Random(seed)
    points: list[tuple[str, float, float]] = []
    for cp in control_points:
        if cp.theatre == region.theatre:
            points.append((cp.name, cp.dcs_x, cp.dcs_z))
    for i in range(n_random):
        x = rng.uniform(
            region.centre_x - region.half_extent_x_m,
            region.centre_x + region.half_extent_x_m,
        )
        z = rng.uniform(
            region.centre_z - region.half_extent_z_m,
            region.centre_z + region.half_extent_z_m,
        )
        points.append((f"random-{i}", x, z))
    for i in range(n_boundary):
        x = rng.uniform(
            region.centre_x - 1.05 * region.half_extent_x_m,
            region.centre_x + 1.05 * region.half_extent_x_m,
        )
        z = rng.uniform(
            region.centre_z - 1.05 * region.half_extent_z_m,
            region.centre_z + 1.05 * region.half_extent_z_m,
        )
        points.append((f"boundary-{i}", x, z))
    return points


def measure_describe_position_latency(
    conn: sqlite3.Connection,
    theatre: str,
    points: list[tuple[str, float, float]],
) -> LatencyStats:
    """Times one `describe_position` call per point individually (not
    batch wall-clock divided by count), same measurement discipline as
    M5 Stage 5's `cmd_latency`."""
    from query import describe_position

    latencies_s: list[float] = []
    for _label, x, z in points:
        start = time.perf_counter()
        describe_position(conn, theatre, x, z)
        latencies_s.append(time.perf_counter() - start)

    sorted_latencies = sorted(latencies_s)
    return LatencyStats(
        n_points=len(latencies_s),
        mean_ms=statistics.mean(latencies_s) * 1000,
        median_ms=statistics.median(latencies_s) * 1000,
        p95_ms=_percentile(sorted_latencies, 0.95) * 1000,
        p99_ms=_percentile(sorted_latencies, 0.99) * 1000,
        min_ms=sorted_latencies[0] * 1000,
        max_ms=sorted_latencies[-1] * 1000,
    )


def cmd_latency(args: argparse.Namespace) -> None:
    region = REGIONS[args.region]
    db_path = args.db_path or _db_path_for_region(args.region)
    if not db_path.exists():
        print(f"error: {db_path} does not exist -- build it first", file=sys.stderr)
        sys.exit(1)

    points = sample_points_for_region(
        region,
        CONTROL_POINTS,
        n_random=args.n_random,
        n_boundary=args.n_boundary,
        seed=args.seed,
    )
    n_control_points = sum(1 for cp in CONTROL_POINTS if cp.theatre == region.theatre)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        stats = measure_describe_position_latency(conn, region.theatre, points)
    finally:
        conn.close()

    print(
        json.dumps(
            {
                "region": args.region,
                "db_path": str(db_path),
                "n_control_points": n_control_points,
                "n_random": args.n_random,
                "n_boundary": args.n_boundary,
                **asdict(stats),
            },
            indent=2,
        )
    )


def cmd_sqlite_size(args: argparse.Namespace) -> None:
    db_path = args.db_path or _db_path_for_region(args.region)
    if not db_path.exists():
        print(f"error: {db_path} does not exist -- build it first", file=sys.stderr)
        sys.exit(1)
    size_bytes = db_path.stat().st_size
    print(
        json.dumps(
            {
                "region": args.region,
                "sqlite_path": str(db_path),
                "size_bytes": size_bytes,
                "size_mb": size_bytes / (1024 * 1024),
            },
            indent=2,
        )
    )


def cmd_rebuild(args: argparse.Namespace) -> None:
    """Times `tools/build_world_model.py <region> <build_args...>` end to
    end as a subprocess, mirroring M5 Stage 5's `cmd_rebuild` but
    generalized to forward arbitrary `build_world_model.py` flags rather
    than hardcoding `latakia-20km`'s -- `syria-full` has no registered
    default raw paths (see `build_world_model.py`'s module docstring) so
    every flag (`--towns`/`--beacons`/`--routes`/`--srtm-dir`/...) must be
    passed through explicitly by the caller."""
    cmd = [
        sys.executable,
        str(_WORLD_MODEL_ROOT / "tools" / "build_world_model.py"),
        args.region,
        *args.build_args,
    ]
    start = time.perf_counter()
    result = subprocess.run(
        cmd, cwd=_WORLD_MODEL_ROOT, capture_output=True, text=True, check=False
    )
    elapsed_s = time.perf_counter() - start

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

    print(
        json.dumps(
            {
                "region": args.region,
                "rebuild_wall_time_s": elapsed_s,
                "build_stdout": result.stdout,
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    latency_parser = subparsers.add_parser("latency")
    latency_parser.add_argument(
        "--region", default=_DEFAULT_REGION, choices=sorted(REGIONS)
    )
    latency_parser.add_argument("--db-path", type=Path, default=None)
    latency_parser.add_argument("--n-random", type=int, default=300)
    latency_parser.add_argument("--n-boundary", type=int, default=40)
    latency_parser.add_argument("--seed", type=int, default=20260905)

    size_parser = subparsers.add_parser("sqlite-size")
    size_parser.add_argument(
        "--region", default=_DEFAULT_REGION, choices=sorted(REGIONS)
    )
    size_parser.add_argument("--db-path", type=Path, default=None)

    rebuild_parser = subparsers.add_parser("rebuild")
    rebuild_parser.add_argument("region", choices=sorted(REGIONS))
    rebuild_parser.add_argument("build_args", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    {
        "latency": cmd_latency,
        "sqlite-size": cmd_sqlite_size,
        "rebuild": cmd_rebuild,
    }[args.command](args)


if __name__ == "__main__":
    main()
