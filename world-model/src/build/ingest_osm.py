"""Cached Overpass response -> `road` / `settlement` / `water` /
`named_place` features, clipped to a region.

Every vertex goes through `coordinates.wgs84_to_dcs` (`confidence="confirmed"`
per M1) -- `src/raster/` is never consulted, so this layer's positional
uncertainty is M1's ~1.0-1.3 km terrain-art residual, not M3's ~5 km figure
(see `plans/m5-first-persistent-model/plan.md` "Explicit non-dependency").
Every emitted feature carries `provenance={"geometry": "osm", "name": "osm"}`
so `describe_position` can tell it apart from the DCS-sourced layers it sits
beside.

**Multipolygon relations are an explicit, counted skip, not a silent drop**
(the plan's "Multipolygon relations" risk entry): `osm.features.load_features`
already counts `relation` elements; this module carries that count through
as `OsmIngestStats.relations_skipped` for the research note. A way whose
tags don't match any of the four classification rules below, or that closes
into fewer than 3 distinct vertices, is similarly counted rather than
silently dropped.
"""

from dataclasses import dataclass

from coordinates import wgs84_to_dcs
from osm.features import OsmFeatureSet, OsmNode, OsmWay
from store.models import StoredFeature

_OSM_POSITION_UNCERTAINTY_M = 1300.0
_PROVENANCE = {"geometry": "osm", "name": "osm"}
_CONFIDENCE = {"geometry": "medium", "name": "medium"}

# Bump whenever `_classify_way`'s four rules (or any other logic in
# `_ingest_node`/`_ingest_way` that changes what a feature's stored fields
# look like) change. `osm_cache` (`plans/osm-classified-cache/plan.md`)
# includes this in its cache invalidation key: a cached row is this
# function's *output*, so a rule change must force a rebuild even when the
# source `.osm.pbf` is byte-for-byte unchanged.
CLASSIFIER_VERSION = 1


@dataclass
class OsmIngestStats:
    roads: int = 0
    water_features: int = 0
    settlement_features: int = 0
    named_places: int = 0
    relations_skipped: int = 0
    ways_skipped_unclassified: int = 0
    ways_skipped_degenerate: int = 0
    # M9's own `OsmFeatureSet.ways_skipped_unresolved_nodes` had no matching
    # field here until the streaming-ingest fix -- it was silently dropped by
    # `ingest_osm` and never reached `BuildReport` for either OSM path.
    # Surfaced now that the streaming pipeline change threads this count
    # through directly from `osm.pbf.stream_features`'s return value; see
    # `plans/osm-streaming-ingest/plan.md` Step 2.
    ways_skipped_unresolved_nodes: int = 0


def _within_region(
    x: float,
    z: float,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
) -> bool:
    return (
        centre_x - half_extent_x_m <= x <= centre_x + half_extent_x_m
        and centre_z - half_extent_z_m <= z <= centre_z + half_extent_z_m
    )


def _is_closed(points: list[tuple[float, float]]) -> bool:
    return len(points) > 2 and points[0] == points[-1]


def _classify_way(tags: dict[str, str]) -> tuple[str, str | None] | None:
    """Returns `(kind, subtype)` for a way's tags, or `None` if it matches
    none of the four rules this ingest handles."""
    if "highway" in tags:
        return "road", tags["highway"]
    if "waterway" in tags or tags.get("natural") == "water":
        return "water", tags.get("waterway", tags.get("natural"))
    if "landuse" in tags or "place" in tags:
        return "settlement", tags.get("landuse", tags.get("place"))
    return None


def _ingest_node(
    node: OsmNode,
    theatre: str,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    source_id: int | None,
    stats: OsmIngestStats,
) -> StoredFeature | None:
    if "place" not in node.tags or "name" not in node.tags:
        return None
    x, z = wgs84_to_dcs(theatre, node.lat, node.lon)
    if not _within_region(x, z, centre_x, centre_z, half_extent_x_m, half_extent_z_m):
        return None
    stats.named_places += 1
    return StoredFeature(
        kind="named_place",
        geom_type="Point",
        geometry=[(x, z)],
        name=node.tags["name"],
        subtype=node.tags.get("place"),
        tags=dict(node.tags),
        source_id=source_id,
        source_ref=f"node/{node.id}",
        provenance=dict(_PROVENANCE),
        confidence=dict(_CONFIDENCE),
        position_uncertainty_m=_OSM_POSITION_UNCERTAINTY_M,
    )


def _ingest_way(
    way: OsmWay,
    theatre: str,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    source_id: int | None,
    stats: OsmIngestStats,
) -> StoredFeature | None:
    classification = _classify_way(way.tags)
    if classification is None:
        stats.ways_skipped_unclassified += 1
        return None
    kind, subtype = classification

    points = [wgs84_to_dcs(theatre, lat, lon) for lat, lon in way.points]
    if len(points) < 2:
        stats.ways_skipped_degenerate += 1
        return None
    if not any(
        _within_region(x, z, centre_x, centre_z, half_extent_x_m, half_extent_z_m)
        for x, z in points
    ):
        return None

    geom_type = "Polygon" if _is_closed(points) else "LineString"
    if geom_type == "Polygon" and len(points) - 1 < 3:
        stats.ways_skipped_degenerate += 1
        return None

    if kind == "road":
        stats.roads += 1
    elif kind == "water":
        stats.water_features += 1
    else:
        stats.settlement_features += 1

    return StoredFeature(
        kind=kind,
        geom_type=geom_type,
        geometry=points,
        name=way.tags.get("name"),
        subtype=subtype,
        tags=dict(way.tags),
        source_id=source_id,
        source_ref=f"way/{way.id}",
        provenance=dict(_PROVENANCE),
        confidence=dict(_CONFIDENCE),
        position_uncertainty_m=_OSM_POSITION_UNCERTAINTY_M,
    )


def ingest_osm_nodes_batch(
    nodes: list[OsmNode],
    theatre: str,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    source_id: int | None,
    stats: OsmIngestStats,
) -> list[StoredFeature]:
    """Ingest one batch of nodes, mutating `stats` in place and returning the
    batch's kept features -- the batch-scoped body of `ingest_osm`'s node
    loop, extracted so the streaming pipeline path (`build.pipeline`'s
    `osm_pbf_path` branch) can call it once per flushed batch instead of
    once over a whole-file `OsmFeatureSet`."""
    features: list[StoredFeature] = []
    for node in nodes:
        feature = _ingest_node(
            node,
            theatre,
            centre_x,
            centre_z,
            half_extent_x_m,
            half_extent_z_m,
            source_id,
            stats,
        )
        if feature is not None:
            features.append(feature)
    return features


def ingest_osm_ways_batch(
    ways: list[OsmWay],
    theatre: str,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    source_id: int | None,
    stats: OsmIngestStats,
) -> list[StoredFeature]:
    """Ingest one batch of ways, mutating `stats` in place and returning the
    batch's kept features -- see `ingest_osm_nodes_batch`."""
    features: list[StoredFeature] = []
    for way in ways:
        feature = _ingest_way(
            way,
            theatre,
            centre_x,
            centre_z,
            half_extent_x_m,
            half_extent_z_m,
            source_id,
            stats,
        )
        if feature is not None:
            features.append(feature)
    return features


def ingest_osm(
    feature_set: OsmFeatureSet,
    theatre: str,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    source_id: int | None,
) -> tuple[list[StoredFeature], OsmIngestStats]:
    """Convert a parsed Overpass response into `road`/`settlement`/`water`/
    `named_place` features clipped to the rectangular region `(centre_x,
    centre_z) +/- (half_extent_x_m, half_extent_z_m)`.

    A thin wrapper over `ingest_osm_nodes_batch`/`ingest_osm_ways_batch`,
    each called once over the feature set's full node/way lists -- identical
    behaviour to before the streaming-ingest fix split those loop bodies
    out, so the Overpass (M3) path and this module's own tests need no
    change."""
    stats = OsmIngestStats(
        relations_skipped=feature_set.relations_skipped,
        ways_skipped_unresolved_nodes=feature_set.ways_skipped_unresolved_nodes,
    )
    node_features = ingest_osm_nodes_batch(
        feature_set.nodes,
        theatre,
        centre_x,
        centre_z,
        half_extent_x_m,
        half_extent_z_m,
        source_id,
        stats,
    )
    way_features = ingest_osm_ways_batch(
        feature_set.ways,
        theatre,
        centre_x,
        centre_z,
        half_extent_x_m,
        half_extent_z_m,
        source_id,
        stats,
    )
    return node_features + way_features, stats
