#!/usr/bin/env python3
"""Walk a DCS `<Theatre>.surface5` node index and test it against real
`land.getHeight` samples.

Throwaway investigation tool for X-B26 ("terrain file route vs. live
probe"), not pipeline code -- nothing imports it and nothing in the build
depends on it. It exists so the 2026-09-29 finding can be re-run rather
than believed: `world-model/research/2026-09-29-surface5-elevation-
confirmed.md`.

What it does, and why in this order:

1. Walks the **node-descriptor region** of `.surface5` -- the first ~130 MB
   of a 30 GB file. The remaining 30.3 GB is undecoded `TRI` payload and is
   never read, which is the whole point: the descriptors alone carry a
   per-tile elevation envelope.
2. For each descriptor it reads the tile's world origin (`tr`) and its
   local axis-aligned bounding box, and derives the world bbox as
   `tr + bbox`.
3. It then checks that derivation the only way that actually settles it:
   against DCS's own `land.getHeight` output, captured by the M4/M5
   mission-editor probes and still on disk in
   `Saved Games/DCS/Logs/*.jsonl`. Every ground-truth height must fall
   inside the y-range of the smallest tile containing its (x, z).
4. It runs a **null control** -- the same test with the heights shuffled
   between points. Without it "129/129 passed" means nothing, because
   large tiles with wide bands would pass anything; the null says how much
   of the result is the format and how much is the test being easy.

The grammar, established by inspection (see the research note for the hex):
each descriptor is a self-describing record containing the ASCII field
names `Surface5.0`, `Land`, `shaderDefine`, `NODEFINITIONS`, `Pbase`,
`nextLodIndex`, `Nbase`, `maxEdge`, `depth`, `TRITYPE`, `TRI`, each
preceded by a `<u32 namelen>`. `TRITYPE` is used as the anchor because it
is the one field at a fixed negative offset from the transform block --
record length itself varies.

**`Pbase` is NOT decoded.** Its per-node payload could not be located: the
u64 that follows the field name does not resolve to a file offset holding
position data (it lands inside a later descriptor record). So this tool
yields a per-tile min/max envelope, never a per-node height.

Usage (from `world-model/`, on the machine with DCS installed):

    .venv/bin/python tools/probe_surface5_elevation.py \\
        --surface5 "$DCS_INSTALL_PATH/Mods/terrains/Syria/surface/Syria.surface5" \\
        --ground-truth "$DCS_SAVED_GAMES_PATH/Logs/terrain_probe_output.jsonl" \\
        --ground-truth "$DCS_SAVED_GAMES_PATH/Logs/elevation_probe_output.jsonl"
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

# The descriptor region is front-loaded; 150 MB covers all of Syria's with
# room to spare (records stop between 100 and 150 MB). Reading more costs
# minutes of disk for nothing.
DEFAULT_SCAN_BYTES = 150 * 1024 * 1024

# Offsets back from the `TRITYPE` field name to the transform block. Fixed
# across every record observed; the record's overall length is not.
_TR_BACK = 0x44
_BBOX_BACK = 0x34

_SANE_COORD_LIMIT = 1e7


@dataclass(frozen=True)
class Tile:
    """One node-descriptor record's world-space extent."""

    x_min: float
    x_max: float
    z_min: float
    z_max: float
    y_min: float
    y_max: float
    nodes: int

    def contains_xz(self, x: float, z: float) -> bool:
        return self.x_min <= x <= self.x_max and self.z_min <= z <= self.z_max

    @property
    def area(self) -> float:
        return (self.x_max - self.x_min) * (self.z_max - self.z_min)


def walk_descriptors(path: Path, scan_bytes: int) -> list[Tile]:
    """Return every valid node descriptor in the file's first `scan_bytes`."""
    with path.open("rb") as fh:
        buf = fh.read(scan_bytes)

    tiles: list[Tile] = []
    start = 0
    while True:
        i = buf.find(b"Surface5.0", start)
        if i < 0:
            break
        start = i + 1
        # A real field name is preceded by its own u32 length. Without this
        # check the same bytes match inside TRI payload often enough to
        # poison the result.
        if i < 4 or struct.unpack_from("<I", buf, i - 4)[0] != 10:
            continue
        anchor = buf.find(b"TRITYPE", i)
        if anchor < 0 or anchor - _TR_BACK < 0:
            continue

        def f(off: int) -> float:
            value: float = struct.unpack_from("<f", buf, off)[0]
            return value

        tr = [f(anchor - _TR_BACK + 4 * k) for k in range(3)]
        bb = [f(anchor - _BBOX_BACK + 4 * k) for k in range(6)]

        # A record whose bbox is not ordered, or whose numbers are absurd,
        # is a mis-anchored read rather than a tile. Drop it rather than
        # letting it widen the envelope and flatter the result.
        if not (bb[0] < bb[3] and bb[1] < bb[4] and bb[2] < bb[5]):
            continue
        if not all(abs(v) < _SANE_COORD_LIMIT for v in (*bb, *tr)):
            continue

        depth_at = buf.find(b"depth", i, anchor)
        nodes = 0
        if depth_at >= 0:
            nodes = struct.unpack_from("<Q", buf, depth_at + len(b"depth") + 8)[0]

        tiles.append(
            Tile(
                x_min=tr[0] + bb[0],
                x_max=tr[0] + bb[3],
                z_min=tr[2] + bb[2],
                z_max=tr[2] + bb[5],
                y_min=bb[1],
                y_max=bb[4],
                nodes=nodes,
            )
        )
    return tiles


def load_ground_truth(paths: list[Path]) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for p in paths:
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            points.append((d["x"], d["z"], d["height_m"]))
    return points


def smallest_containing(tiles: list[Tile], x: float, z: float) -> Tile | None:
    best: Tile | None = None
    for t in tiles:
        if t.contains_xz(x, z) and (best is None or t.area < best.area):
            best = t
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--surface5", type=Path, required=True)
    ap.add_argument("--ground-truth", type=Path, action="append", required=True)
    ap.add_argument("--scan-bytes", type=int, default=DEFAULT_SCAN_BYTES)
    ap.add_argument("--null-trials", type=int, default=200)
    args = ap.parse_args()

    if not args.surface5.exists():
        print(f"error: {args.surface5} does not exist", file=sys.stderr)
        sys.exit(1)

    tiles = walk_descriptors(args.surface5, args.scan_bytes)
    if not tiles:
        print(
            "error: no descriptors found -- wrong file or wrong theatre?",
            file=sys.stderr,
        )
        sys.exit(1)

    spans = sorted(t.x_max - t.x_min for t in tiles)
    spacing = sorted((t.area / t.nodes) ** 0.5 for t in tiles if t.nodes > 0)
    print(f"descriptors: {len(tiles):,}   total nodes: {sum(t.nodes for t in tiles):,}")
    print(
        f"tile x-span (m): min={spans[0]:.0f} "
        f"med={spans[len(spans) // 2]:.0f} max={spans[-1]:.0f}"
    )
    if spacing:
        print(
            f"node spacing sqrt(area/nodes) (m): min={spacing[0]:.1f} "
            f"p10={spacing[len(spacing) // 10]:.1f} "
            f"med={spacing[len(spacing) // 2]:.1f}"
        )

    gt = load_ground_truth(args.ground_truth)
    matched = [(smallest_containing(tiles, x, z), h) for x, z, h in gt]
    covered = [(t, h) for t, h in matched if t is not None]
    inside = [(t, h) for t, h in covered if t.y_min <= h <= t.y_max]

    print(f"\nground truth: {len(gt)} real land.getHeight samples")
    print(f"  covered by some tile          : {len(covered)}/{len(gt)}")
    print(f"  height strictly inside y-range: {len(inside)}/{len(gt)}")
    if covered:
        widths = sorted(t.y_max - t.y_min for t, _ in covered)
        print(
            f"  smallest-tile y-range width (m): med={widths[len(widths) // 2]:.1f} max={widths[-1]:.1f}"
        )

    # Null control: if the heights are reassigned at random between points,
    # how many still land in band? The gap between that and the real score
    # is the finding.
    rng = random.Random(1)
    heights = [h for _, h in covered]
    null_scores = []
    for _ in range(args.null_trials):
        shuffled = heights[:]
        rng.shuffle(shuffled)
        null_scores.append(
            sum(1 for (t, _), h in zip(covered, shuffled) if t.y_min <= h <= t.y_max)
        )
    print(
        f"  NULL control (heights shuffled): mean "
        f"{statistics.mean(null_scores):.1f}/{len(covered)} max {max(null_scores)}"
    )


if __name__ == "__main__":
    main()
