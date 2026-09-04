#!/usr/bin/env python3
"""M5 Stage 5: perf measurements for the dated research note.

Not part of the pipeline -- a throwaway measurement script per
`plans/m5-first-persistent-model/checklist.md` Stage 5, following
`fetch_m5_stage0_census.py`'s pattern (read-only where possible, no
production code changes). Four independent subcommands so the 2.25 GB
`.routes` walk can be measured **standalone**, isolated from the full
rebuild, per the checklist's explicit "full `.routes` walk wall time + peak
memory ... standalone (not via the full build pipeline)" requirement:

    .venv/bin/python tools/measure_m5_stage5_perf.py latency
    .venv/bin/python tools/measure_m5_stage5_perf.py routes-walk
    .venv/bin/python tools/measure_m5_stage5_perf.py rebuild
    .venv/bin/python tools/measure_m5_stage5_perf.py sqlite-size

Each subcommand prints one JSON object to stdout.

Peak memory for `routes-walk` is read via `resource.getrusage(RUSAGE_SELF)`
after the walk completes. On Darwin (this machine), `ru_maxrss` is reported
in **bytes**; on Linux it would be KB -- this script assumes Darwin and
documents that assumption rather than silently mis-scaling on another
platform. For an independent cross-check, wrap the whole subcommand in
`/usr/bin/time -l` from the shell (its "maximum resident set size" line is
an external measurement of the same process, not self-reported).
"""

import argparse
import json
import random
import resource
import sqlite3
import statistics
import subprocess
import sys
import time
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

_DB_PATH = _WORLD_MODEL_ROOT / "data" / "world-model" / "latakia-20km.sqlite"
_ROUTES_PATH = (
    _WORLD_MODEL_ROOT / "data" / "raw" / "dcs" / "syria" / "roads" / "Syria.routes"
)
_THEATRE = "Syria"


def _sample_points(
    n_in_region: int = 80, n_boundary: int = 20
) -> list[tuple[float, float]]:
    """~100 points across the Latakia region: most uniform within the
    region's own bbox, the rest extended out to 1.5x the half-extent to
    include near-boundary and clearly-outside-coverage points -- mirroring
    Stage 4's "outside-coverage degrades to explicit nulls" spot-check, but
    sampled rather than hand-picked since this is a latency measurement, not
    a correctness check."""
    from build.region import REGIONS

    region = REGIONS["latakia-20km"]
    rng = random.Random(20260904)  # fixed seed: reproducible sample set
    points: list[tuple[float, float]] = []
    for _ in range(n_in_region):
        x = rng.uniform(
            region.centre_x - region.half_extent_m,
            region.centre_x + region.half_extent_m,
        )
        z = rng.uniform(
            region.centre_z - region.half_extent_m,
            region.centre_z + region.half_extent_m,
        )
        points.append((x, z))
    for _ in range(n_boundary):
        x = rng.uniform(
            region.centre_x - 1.5 * region.half_extent_m,
            region.centre_x + 1.5 * region.half_extent_m,
        )
        z = rng.uniform(
            region.centre_z - 1.5 * region.half_extent_m,
            region.centre_z + 1.5 * region.half_extent_m,
        )
        points.append((x, z))
    return points


def _percentile(sorted_values: list[float], p: float) -> float:
    n = len(sorted_values)
    idx = min(n - 1, max(0, round(p * (n - 1))))
    return sorted_values[idx]


def cmd_latency(_args: argparse.Namespace) -> None:
    from query import describe_position

    if not _DB_PATH.exists():
        print(f"error: {_DB_PATH} does not exist -- build it first", file=sys.stderr)
        sys.exit(1)

    points = _sample_points()
    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
    latencies_s: list[float] = []
    try:
        for x, z in points:
            start = time.perf_counter()
            describe_position(conn, _THEATRE, x, z)
            latencies_s.append(time.perf_counter() - start)
    finally:
        conn.close()

    sorted_latencies = sorted(latencies_s)
    print(
        json.dumps(
            {
                "n_points": len(latencies_s),
                "mean_ms": statistics.mean(latencies_s) * 1000,
                "median_ms": statistics.median(latencies_s) * 1000,
                "p95_ms": _percentile(sorted_latencies, 0.95) * 1000,
                "p99_ms": _percentile(sorted_latencies, 0.99) * 1000,
                "min_ms": sorted_latencies[0] * 1000,
                "max_ms": sorted_latencies[-1] * 1000,
            },
            indent=2,
        )
    )


def cmd_routes_walk(_args: argparse.Namespace) -> None:
    from roadnet.routes import RouteWalkStats, iter_routes

    if not _ROUTES_PATH.exists():
        print(f"error: {_ROUTES_PATH} does not exist", file=sys.stderr)
        sys.exit(1)

    stats = RouteWalkStats()
    start = time.perf_counter()
    for _route in iter_routes(_ROUTES_PATH, stats=stats):
        pass
    elapsed_s = time.perf_counter() - start

    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes on Darwin
    file_size_bytes = _ROUTES_PATH.stat().st_size

    print(
        json.dumps(
            {
                "routes_path": str(_ROUTES_PATH),
                "file_size_bytes": file_size_bytes,
                "file_size_mb": file_size_bytes / (1024 * 1024),
                "wall_time_s": elapsed_s,
                "peak_rss_bytes_darwin": peak_rss,
                "peak_rss_mb_darwin": peak_rss / (1024 * 1024),
                "routes_found": stats.routes_found,
                "bytes_covered": stats.bytes_covered,
                "resync_events": stats.resync_events,
                "sync_loss_events": stats.sync_loss_events,
            },
            indent=2,
        )
    )


_PROBE_OUTPUT_PATH = (
    _WORLD_MODEL_ROOT
    / "data"
    / "raw"
    / "dcs"
    / "2026-09-04"
    / "terrain_probe_output_full.jsonl"
)


def cmd_rebuild(_args: argparse.Namespace) -> None:
    """Times `tools/build_world_model.py latakia-20km` end to end (region +
    towns + beacons + osm + roadnet + probe grid ingest, whichever raw
    inputs are staged) as a subprocess, per the checklist's "full rebuild
    wall time" ask. This necessarily re-runs the full `.routes` walk as
    part of the build -- the standalone `routes-walk` subcommand above is
    the isolated measurement the checklist separately asks for.

    `--probe-output` is passed explicitly (`build_world_model.py` has no
    default registered for `latakia-20km`, unlike `--towns`/`--beacons`/
    `--osm-cache`/`--routes`) so this rebuild is a genuine like-for-like
    "full" rebuild against the real Stage 3/4 store, not a probe-skipped
    rebuild that would silently drop the 1,681-point elevation/surface_type
    grid -- see this session's Stage 5 research note for the regression
    this caught. No local SRTM tile for Latakia is staged (`data/raw/dem/`
    only has Gemerek's M4 tile), so `--srtm-tile` is omitted; per
    `build.pipeline.build_region`'s contract this is a safe no-op (the SRTM
    delta stays absent from grid stats, not an error) -- an already-accepted
    deferral, not a Stage 5 gap."""
    cmd = [
        sys.executable,
        str(_WORLD_MODEL_ROOT / "tools" / "build_world_model.py"),
        "latakia-20km",
        "--probe-output",
        str(_PROBE_OUTPUT_PATH),
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
                "rebuild_wall_time_s": elapsed_s,
                "build_stdout": result.stdout,
            },
            indent=2,
        )
    )


def cmd_sqlite_size(_args: argparse.Namespace) -> None:
    if not _DB_PATH.exists():
        print(f"error: {_DB_PATH} does not exist -- build it first", file=sys.stderr)
        sys.exit(1)
    size_bytes = _DB_PATH.stat().st_size
    print(
        json.dumps(
            {
                "sqlite_path": str(_DB_PATH),
                "size_bytes": size_bytes,
                "size_mb": size_bytes / (1024 * 1024),
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("latency")
    subparsers.add_parser("routes-walk")
    subparsers.add_parser("rebuild")
    subparsers.add_parser("sqlite-size")
    args = parser.parse_args()

    {
        "latency": cmd_latency,
        "routes-walk": cmd_routes_walk,
        "rebuild": cmd_rebuild,
        "sqlite-size": cmd_sqlite_size,
    }[args.command](args)


if __name__ == "__main__":
    main()
