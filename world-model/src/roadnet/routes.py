"""Parses `.routes` (`landscape4::lRoutesFile`) files: whole-theatre road
centerline geometry with per-point heading, one route (polyline) at a time.

Each route is `[int32 N][N x float64 xyz position][int32 N][N x float64 xyz
unit direction]`, followed by an intentionally-undecoded trailer (per-point
cumulative arc-length, an int32 flags array, a bounded float32 array, then
an undecoded ~64-byte-per-point region -- see `roadnet/__init__.py`). The
position and direction arrays are always immediately adjacent (no scan
needed between them); the trailer is skipped via `container.
find_next_point_block`'s scan-forward resync to reach the next route.

`iter_routes` is a **streaming generator over an `mmap`** -- it never loads
`.routes` into memory, which matters at `Syria.routes`' real size (2.25 GB).
"""

import mmap
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .container import (
    Buffer,
    ContainerFormatError,
    find_next_point_block,
    read_header,
    read_point_block,
)

_CLASS_NAME = "landscape4::lRoutesFile"

Point3 = tuple[float, float, float]
Bbox = tuple[float, float, float, float]  # (min_x, max_x, min_z, max_z)


@dataclass(frozen=True)
class RoutePolyline:
    """One decoded route: a centerline polyline plus its per-point unit
    direction (tangent) vectors, read directly from the file rather than
    numerically differentiated. `byte_offset` is the position array's start
    offset in the source file -- the roadnet layer's equivalent of a
    raw-path citation, carried into `StoredFeature.source_ref`."""

    route_index: int
    byte_offset: int
    points: list[Point3]
    directions: list[Point3]


@dataclass
class RouteWalkStats:
    """Self-diagnostic counters for one `iter_routes` walk -- the parser's
    only visibility into its own health over a 2.25 GB file it cannot be
    exhaustively hand-checked against. `resync_events` counts every route
    boundary (normal and expected -- the trailer is always skipped by scan,
    never parsed). `sync_loss_events` counts cases where the direction array
    was *not* found immediately adjacent to its position array, or failed
    the unit-magnitude sanity check -- both would indicate the walk has
    drifted off true route boundaries, which the confirmed format model says
    should not happen."""

    bytes_covered: int = 0
    routes_found: int = 0
    resync_events: int = 0
    sync_loss_events: int = 0


_UNIT_MAGNITUDE_TOLERANCE = 1e-3


def _is_unit_vector(v: Point3) -> bool:
    magnitude_sq = v[0] * v[0] + v[1] * v[1] + v[2] * v[2]
    return abs(magnitude_sq - 1.0) < _UNIT_MAGNITUDE_TOLERANCE


def _directions_plausible(directions: list[Point3]) -> bool:
    if not directions:
        return True
    sample_indices = {0, len(directions) // 2, len(directions) - 1}
    return all(_is_unit_vector(directions[i]) for i in sample_indices)


def _route_intersects_bbox(points: list[Point3], bbox: Bbox) -> bool:
    min_x, max_x, min_z, max_z = bbox
    return any(min_x <= x <= max_x and min_z <= z <= max_z for x, _y, z in points)


def iter_routes(
    path: Path,
    bbox: Bbox | None = None,
    stats: RouteWalkStats | None = None,
) -> Iterator[RoutePolyline]:
    """Stream every route in the `.routes` file at `path`, in file order.

    `bbox = (min_x, max_x, min_z, max_z)` in DCS metres, if given, filters
    which routes are *yielded* -- a route is yielded if any of its points
    falls inside `bbox`. The walk itself always covers the whole file
    regardless of `bbox`, so `stats.routes_found` after exhausting the
    generator is the *whole-theatre* route count, comparable against the
    file header's speculated total (see `roadnet/__init__.py` and the
    byte-decode research note).

    `stats`, if given, is populated in place as the walk proceeds -- pass a
    `RouteWalkStats()` and inspect it after the generator is exhausted (a
    generator's `return` value is awkward to retrieve mid-iteration, so a
    mutable out-parameter is used instead).

    Never loads the file into memory: `path` is opened and `mmap`-ed
    read-only, and only single-route slices are ever materialized as Python
    objects.
    """
    if stats is None:
        stats = RouteWalkStats()

    with path.open("rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as buf:
        yield from _walk(buf, bbox, stats)


def _walk(
    buf: Buffer, bbox: Bbox | None, stats: RouteWalkStats
) -> Iterator[RoutePolyline]:
    header = read_header(buf, _CLASS_NAME)
    offset = header.data_offset
    route_index = 0

    while True:
        found = find_next_point_block(buf, offset)
        if found is None:
            break
        pos_offset, points, pos_end = found
        if pos_offset != offset:
            stats.resync_events += 1

        try:
            directions, dir_end = read_point_block(buf, pos_end)
        except ContainerFormatError:
            stats.sync_loss_events += 1
            offset = pos_end
            continue

        if not _directions_plausible(directions):
            stats.sync_loss_events += 1

        stats.routes_found += 1
        stats.bytes_covered = dir_end - header.data_offset

        route = RoutePolyline(
            route_index=route_index,
            byte_offset=pos_offset,
            points=points,
            directions=directions,
        )
        route_index += 1
        if bbox is None or _route_intersects_bbox(points, bbox):
            yield route

        offset = dir_end
