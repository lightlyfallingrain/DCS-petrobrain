"""A `.routes` region walk cached as JSON Lines (one route per line) plus a
sidecar `manifest.json` -- what makes a region extract *auditable* rather
than an unexplained blob.

Per the M5 acquisition decision (Option A, full local copy of
`Syria.routes`), this is now an optional local cache under
`data/processed/`, not a cross-machine transfer artifact -- development and
Stage 2 rung 3 run against the full local file directly via `routes.
iter_routes`'s `mmap` streaming walk. `build/ingest_roadnet.py` can read
either this extract or walk the full file directly; nothing in the pipeline
requires the extract to exist.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .routes import Bbox, Point3, RoutePolyline, RouteWalkStats, iter_routes

_EXTRACTOR_VERSION = 1


@dataclass(frozen=True)
class ExtractManifest:
    """Provenance and walk statistics for one region extract -- which
    source file (path, size, mtime), which extractor version, which bbox,
    and how the walk went. Keeping this alongside the extract keeps the
    provenance chain intact if the extract is ever regenerated elsewhere."""

    source_path: str
    source_size_bytes: int
    source_mtime: float
    extractor_version: int
    bbox: Bbox
    route_count: int
    point_count: int
    bytes_covered: int
    routes_found_whole_file: int
    resync_events: int
    sync_loss_events: int


def write_region_extract(
    routes_path: Path,
    bbox: Bbox,
    out_jsonl_path: Path,
    out_manifest_path: Path,
) -> ExtractManifest:
    """Walk `routes_path`, write every route intersecting `bbox` as one JSON
    object per line to `out_jsonl_path`, and write `out_manifest_path`
    alongside it. Returns the manifest."""
    stats = RouteWalkStats()
    route_count = 0
    point_count = 0

    out_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl_path.open("w", encoding="utf-8") as f:
        for route in iter_routes(routes_path, bbox=bbox, stats=stats):
            f.write(json.dumps(_route_to_record(route)) + "\n")
            route_count += 1
            point_count += len(route.points)

    source_stat = routes_path.stat()
    manifest = ExtractManifest(
        source_path=str(routes_path),
        source_size_bytes=source_stat.st_size,
        source_mtime=source_stat.st_mtime,
        extractor_version=_EXTRACTOR_VERSION,
        bbox=bbox,
        route_count=route_count,
        point_count=point_count,
        bytes_covered=stats.bytes_covered,
        routes_found_whole_file=stats.routes_found,
        resync_events=stats.resync_events,
        sync_loss_events=stats.sync_loss_events,
    )
    out_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    out_manifest_path.write_text(
        json.dumps(asdict(manifest), indent=2), encoding="utf-8"
    )
    return manifest


def read_region_extract(jsonl_path: Path) -> list[RoutePolyline]:
    """Read a JSON Lines extract written by `write_region_extract`."""
    routes: list[RoutePolyline] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        routes.append(_record_to_route(json.loads(line)))
    return routes


def read_manifest(manifest_path: Path) -> ExtractManifest:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return ExtractManifest(
        source_path=data["source_path"],
        source_size_bytes=data["source_size_bytes"],
        source_mtime=data["source_mtime"],
        extractor_version=data["extractor_version"],
        bbox=tuple(data["bbox"]),
        route_count=data["route_count"],
        point_count=data["point_count"],
        bytes_covered=data["bytes_covered"],
        routes_found_whole_file=data["routes_found_whole_file"],
        resync_events=data["resync_events"],
        sync_loss_events=data["sync_loss_events"],
    )


def _route_to_record(route: RoutePolyline) -> dict[str, object]:
    return {
        "route_index": route.route_index,
        "byte_offset": route.byte_offset,
        "points": [list(p) for p in route.points],
        "directions": [list(d) for d in route.directions],
    }


def _record_to_route(record: dict[str, object]) -> RoutePolyline:
    points_raw = record["points"]
    directions_raw = record["directions"]
    assert isinstance(points_raw, list)
    assert isinstance(directions_raw, list)
    points: list[Point3] = [_to_point3(p) for p in points_raw]
    directions: list[Point3] = [_to_point3(d) for d in directions_raw]
    route_index = record["route_index"]
    byte_offset = record["byte_offset"]
    assert isinstance(route_index, int)
    assert isinstance(byte_offset, int)
    return RoutePolyline(
        route_index=route_index,
        byte_offset=byte_offset,
        points=points,
        directions=directions,
    )


def _to_point3(value: object) -> Point3:
    assert isinstance(value, list) and len(value) == 3
    x, y, z = value
    return float(x), float(y), float(z)
