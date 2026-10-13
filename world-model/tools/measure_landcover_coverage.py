"""Measure landcover coverage and point-in-polygon cost against a built store.

Written for `plans/forest-occlusion/plan.md`, where three numbers decided the
design and none of them could be reasoned to:

- the **cost** of `store.reader.containing_polygons` per point, which is what a
  per-candidate-per-poll forest gate pays against body-layer's 12.6 ms poll
  budget (`describe_position`, the obvious route, is 84.6 ms per call in situ);
- the **blast radius** -- what fraction of plausible ground-unit positions sit
  inside a `forest` polygon, i.e. how many contacts the gate removes;
- the fraction of positions with **no mapped landcover at all**, which is what
  settles whether `inside_landcover`'s `None` may be read as "open ground".
  It is the majority answer, which is why `None` must mean *not* forest.

Read-only. Run against a built region store:

    world-model/.venv/bin/python world-model/tools/measure_landcover_coverage.py \\
        world-model/data/world-model/syria-full.sqlite

Two samplings, because they answer different questions and disagree:
`--mode grid` is an unbiased areal sample (what fraction of the ground is
forest), `--mode road` samples road vertices with jitter (where mission authors
actually put vehicles -- roads largely avoid woods, so this reads lower).
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from store.reader import containing_polygons

LANDCOVER_KINDS = ["landcover"]


def open_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def class_census(conn: sqlite3.Connection) -> None:
    print("landcover_class census (polygon count, mean bbox extent):")
    for lc, n, w, h in conn.execute(
        "select json_extract(f.tags_json,'$.landcover_class') lc, count(*), "
        "avg(b.max_x-b.min_x), avg(b.max_z-b.min_z) "
        "from feature f join feature_bbox b using(id) "
        "where lc is not null group by lc order by 2 desc"
    ):
        print(f"  {lc:12s} {n:6d}  {w:7.0f} x {h:.0f} m")


def anchor(conn: sqlite3.Connection, name: str) -> tuple[float, float] | None:
    row = conn.execute(
        "select geom_json from feature where kind='named_place' and name like ? limit 1",
        (name + "%",),
    ).fetchone()
    if row is None:
        return None
    pt = json.loads(row[0])
    while isinstance(pt[0], list):
        pt = pt[0]
    return float(pt[0]), float(pt[1])


def grid_points(
    box: tuple[float, float, float, float], step: float
) -> list[tuple[float, float]]:
    mnx, mxx, mnz, mxz = box
    pts = []
    x = mnx
    while x < mxx:
        z = mnz
        while z < mxz:
            pts.append((x, z))
            z += step
        x += step
    return pts


def road_points(
    conn: sqlite3.Connection,
    box: tuple[float, float, float, float],
    n: int,
    jitter_m: float,
    seed: int,
) -> list[tuple[float, float]]:
    rnd = random.Random(seed)
    ids = [
        r[0]
        for r in conn.execute(
            "select f.id from feature f join feature_bbox b using(id) "
            "where f.kind='road' and b.min_x>=? and b.max_x<=? "
            "and b.min_z>=? and b.max_z<=?",
            box,
        )
    ]
    pts: list[tuple[float, float]] = []
    while ids and len(pts) < n:
        (g,) = conn.execute(
            "select geom_json from feature where id=?", (rnd.choice(ids),)
        ).fetchone()
        coords = json.loads(g)
        if not coords:
            continue
        x, z = coords[rnd.randrange(len(coords))][:2]
        pts.append(
            (x + rnd.uniform(-jitter_m, jitter_m), z + rnd.uniform(-jitter_m, jitter_m))
        )
    return pts


def measure(
    conn: sqlite3.Connection, pts: list[tuple[float, float]], label: str
) -> None:
    if not pts:
        print(f"  {label}: no points")
        return
    times: list[float] = []
    tally: dict[str, int] = {}
    for x, z in pts:
        t0 = time.perf_counter()
        polys = containing_polygons(conn, LANDCOVER_KINDS, x, z)
        times.append((time.perf_counter() - t0) * 1000.0)
        classes = {
            p.tags.get("landcover_class")
            for p in polys
            if p.tags.get("landcover_class")
        }
        if not classes:
            tally["<none>"] = tally.get("<none>", 0) + 1
        for cl in classes:
            tally[str(cl)] = tally.get(str(cl), 0) + 1
    times.sort()
    n = len(pts)
    print(
        f"  {label}: n={n}  cost median={statistics.median(times):.3f} ms "
        f"p95={times[int(n * 0.95)]:.3f} ms max={times[-1]:.3f} ms"
    )
    print(
        "    "
        + "  ".join(
            f"{k}={100.0 * v / n:.1f}%"
            for k, v in sorted(tally.items(), key=lambda kv: -kv[1])
        )
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("store", type=Path)
    ap.add_argument("--mode", choices=["grid", "road", "both"], default="both")
    ap.add_argument("--half-extent-m", type=float, default=30000.0)
    ap.add_argument("--grid-step-m", type=float, default=2000.0)
    ap.add_argument("--road-samples", type=int, default=300)
    ap.add_argument("--road-jitter-m", type=float, default=300.0)
    ap.add_argument(
        "--region",
        action="append",
        default=None,
        help="named_place to centre a box on; repeatable (default: a Syria spread)",
    )
    args = ap.parse_args()

    conn = open_ro(args.store)
    class_census(conn)

    regions = args.region or ["Latakia", "Damascus", "Aleppo", "Hama", "Palmyra"]
    half = args.half_extent_m
    for name in regions:
        a = anchor(conn, name)
        if a is None:
            print(f"\n{name}: not found in this store")
            continue
        x, z = a
        box = (x - half, x + half, z - half, z + half)
        print(f"\n{name} +/- {half / 1000:.0f} km:")
        if args.mode in ("grid", "both"):
            measure(conn, grid_points(box, args.grid_step_m), "uniform grid")
        if args.mode in ("road", "both"):
            measure(
                conn,
                road_points(
                    conn, box, args.road_samples, args.road_jitter_m, seed=len(name)
                ),
                "road-adjacent",
            )


if __name__ == "__main__":
    main()
