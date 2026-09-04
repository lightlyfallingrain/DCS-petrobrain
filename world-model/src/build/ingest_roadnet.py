"""`.routes` region walk -> `road` features, clipped to a region.

**Roads carry `provenance={"geometry": "dcs"}`, `confidence={"geometry":
"high"}`, `position_uncertainty_m=0.0`, `subtype=None`, `name=None`.** Per
plan.md Decision 7 (road type/subtype deferred): `.rn4`'s type index is not
joinable to `.routes` geometry with any confirmed correspondence, and
guessing the join (row order, positional proximity) is explicitly rejected
-- see `roadnet/__init__.py`. This module does not import `roadnet.rn4` at
all, which is itself the scope guard: there is no code path here that could
even attempt the join.

**Orientation** comes from the route's own per-point direction vectors, not
from differentiating the polyline -- the first direction vector's bearing is
computed once at build time and stored in `tags_json["orientation_deg"]`,
per plan.md's "store the segment orientation in tags_json" fallback (storing
a full per-point direction array on `StoredFeature`, which has no such
field, would require a schema change out of Stage 2's scope).

**`source_ref`** is `f"route:{route_index}@{byte_offset}"` -- the roadnet
layer's equivalent of a raw-path citation, so any `road` feature in the
store can be traced back to its bytes in `Syria.routes`.

A route with any point outside the region bbox is stored with its full,
untruncated geometry and flagged `tags_json["clipped"] = true` -- per
plan.md, "never silently truncated".
"""

import math
from dataclasses import dataclass
from pathlib import Path

from roadnet.routes import Point3, RouteWalkStats, iter_routes
from store.models import StoredFeature


@dataclass
class RoadnetIngestStats:
    """Census counters for the roadnet layer. `routes_found_whole_file` is
    the walk's total route count across the *entire* `.routes` file
    (`bbox` only filters what gets yielded/ingested, not what gets walked)
    -- compare this against the file header's speculated total (~11464 at
    byte ~63) as the coverage check plan.md's Stage 2 asks for.
    `routes_in_region` is what actually became `road` features."""

    routes_found_whole_file: int = 0
    routes_in_region: int = 0
    resync_events: int = 0
    sync_loss_events: int = 0
    bytes_covered: int = 0


def _orientation_deg(directions: list[Point3]) -> float | None:
    if not directions:
        return None
    dx, _dy, dz = directions[0]
    if dx == 0.0 and dz == 0.0:
        return None
    return math.degrees(math.atan2(dz, dx)) % 360.0


def ingest_roadnet(
    routes_path: Path,
    centre_x: float,
    centre_z: float,
    half_extent_m: float,
    source_id: int | None,
) -> tuple[list[StoredFeature], RoadnetIngestStats]:
    """Walk `routes_path` (the real `Syria.routes` file, or any file in the
    same format), converting every route intersecting the square region
    `(centre_x, centre_z) +/- half_extent_m` into a `road` feature.

    Walks the *whole* file regardless of region size -- `.routes` has no
    spatial index to seek into, so a bbox only filters what gets yielded,
    not how much of the file is read (see `roadnet.routes.iter_routes`).
    """
    bbox = (
        centre_x - half_extent_m,
        centre_x + half_extent_m,
        centre_z - half_extent_m,
        centre_z + half_extent_m,
    )
    min_x, max_x, min_z, max_z = bbox

    walk_stats = RouteWalkStats()
    features: list[StoredFeature] = []

    for route in iter_routes(routes_path, bbox=bbox, stats=walk_stats):
        geometry = [(x, z) for x, _y, z in route.points]
        clipped = any(
            not (min_x <= x <= max_x and min_z <= z <= max_z) for x, z in geometry
        )

        features.append(
            StoredFeature(
                kind="road",
                geom_type="LineString",
                geometry=geometry,
                name=None,
                subtype=None,
                tags={
                    "route_index": route.route_index,
                    "byte_offset": route.byte_offset,
                    "point_count": len(geometry),
                    "orientation_deg": _orientation_deg(route.directions),
                    "clipped": clipped,
                },
                source_id=source_id,
                source_ref=f"route:{route.route_index}@{route.byte_offset}",
                provenance={"geometry": "dcs"},
                confidence={"geometry": "high"},
                position_uncertainty_m=0.0,
            )
        )

    stats = RoadnetIngestStats(
        routes_found_whole_file=walk_stats.routes_found,
        routes_in_region=len(features),
        resync_events=walk_stats.resync_events,
        sync_loss_events=walk_stats.sync_loss_events,
        bytes_covered=walk_stats.bytes_covered,
    )
    return features, stats
