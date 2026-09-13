"""Classifies parsed OSM features (nodes/lines/areas) into DCS-subordinate
`named_place` / `water` / `coastline` / `settlement` / `landcover` features,
clipped to a region -- `plans/osm-landcover-optimization/plan.md` Design D2.

Every vertex goes through `coordinates.wgs84_to_dcs` (`confidence="confirmed"`
per M1) -- `src/raster/` is never consulted, so this layer's positional
uncertainty is M1's ~1.0-1.3 km terrain-art residual, not M3's ~5 km figure
(see `plans/m5-first-persistent-model/plan.md` "Explicit non-dependency").
Every emitted feature carries `provenance={"geometry": "osm", "name": "osm"}`
so `describe_position` can tell it apart from the DCS-sourced layers it sits
beside.

**Three pure classification functions, one per element shape** (D2):
`_classify_node` (place/peak/dam points), `_classify_line` (river/coastline
LineStrings -- the `waterway=dam` line rule is handled directly in
`_ingest_line`, since it produces a *Point*, not a LineString), and
`_classify_area` (water/settlement/landcover polygons, evaluated in a fixed
precedence order so conflicting tags resolve deterministically). None of the
three ever sees a raw geometry -- they take a tag dict and return a
classification tuple or `None`. `road` is no longer classified at all: the
brief drops OSM roads from the store entirely (DCS's own `.routes` layer is
authoritative for roads; see `nearest_road_osm`'s removal in `query/describe.py`).

**The road/OSM overlap this file used to reconcile is gone.** Roads used to
be the single biggest OSM layer by volume; dropping them (and everything
`osmium tags-filter`/`osmium.filter.KeyFilter` now exclude upstream) is most
of this milestone's parse-time win.

**Multipolygon relations are no longer a silent skip -- they assemble.**
`osm.pbf`'s `area()` callback (libosmium's two-pass multipolygon manager)
and `osm.features.load_features`'s closed-way mirror both produce `OsmArea`
objects with real ring/hole geometry; only a relation type libosmium's
manager itself does not assemble (anything but `multipolygon`/`boundary`)
stays a genuinely unsupported, explicitly counted construct
(`OsmFeatureSet.relations_skipped`, `osm.pbf`'s `multipolygon_relations_seen`
being the assembled-vs-skipped split -- see that module's docstring).

**Per-ring geometry pipeline (Design D3)**: each `OsmArea` may carry more
than one outer ring (a true multipolygon); each ring becomes its own stored
`Polygon` feature (`source_ref = way/<id>` or `relation/<id>`), independently
region-clipped, min-area-filtered and simplified. A ring's kept holes (each
independently min-area-filtered and simplified) are stored as a derived
`tags["inner_rings"]` entry rather than a new geometry column -- see
`store/models.py`'s docstring and the plan's mechanism-substitution note 2
(this keeps `store.schema.SCHEMA_VERSION` unchanged, so an existing M8 probe
store stays paired with the base store it was built against). `tags["area_m2"]`
is the ring's unsimplified net area (outer minus kept holes) -- computed
once, before simplification, and never recomputed afterwards.

`MIN_AREA_M2` (5 ha) applies to `water`/`landcover`/built-up-`settlement`
rings and to every hole, but **not** to a named place-area settlement (a
`place=city|town|village` polygon) -- those are rare and named, so size is
not evidence they are noise the way a tiny mapped `landuse=grass` sliver is.
`SIMPLIFY_TOLERANCE_M` (30 m) applies to every ring (outer and kept holes)
and to every line -- see `geometry.simplify_ring`/`simplify_polyline`.

A way/area whose tags match no classification rule, or whose geometry
degenerates below the minimum vertex count (before ever reaching the store)
at any stage, is always a counted skip on `OsmIngestStats`, never a silent
drop.
"""

from dataclasses import dataclass, field
from typing import Any

from coordinates import wgs84_to_dcs
from geometry import (
    Point,
    distance_point_point,
    ring_area_m2,
    simplify_polyline,
    simplify_ring,
)
from osm.features import OsmArea, OsmFeatureSet, OsmNode, OsmRing, OsmWay
from store.models import StoredFeature

_OSM_POSITION_UNCERTAINTY_M = 1300.0
_PROVENANCE = {"geometry": "osm", "name": "osm"}
_CONFIDENCE = {"geometry": "medium", "name": "medium"}

#: Minimum ring/hole area, in square metres (5 ha) -- applied to `water`,
#: `landcover`, and built-up `settlement` rings and to every hole. See the
#: module docstring's "Per-ring geometry pipeline" section and Design D3
#: step 4.
MIN_AREA_M2 = 50_000.0

#: Simplification tolerance, in metres, for every stored ring (outer and
#: kept holes) and every line -- `geometry.simplify_ring`/`simplify_polyline`.
SIMPLIFY_TOLERANCE_M = 30.0

# Bump whenever the classification rules below, or `_ingest_node`/
# `_ingest_line`/`_ingest_area`/`_ingest_ring`'s field-shaping logic,
# change. `osm_cache` (`plans/osm-classified-cache/plan.md`) includes this
# in its cache invalidation key: a cached row is this module's *output*, so
# a rule change must force a rebuild even when the source `.osm.pbf` is
# byte-for-byte unchanged. A change to `OsmIngestStats`' fields also
# requires a bump, because the cache stores it (`osm_cache.writer.
# finalize_cache`/`osm_cache.reader.load_cached_stats`).
CLASSIFIER_VERSION = 2

#: `place=*` values a *node* classifies as a named settlement point. Other
#: `place` values (`hamlet`, `isolated_dwelling`, `suburb`, `neighbourhood`,
#: `quarter`, ...) are not classified at all -- D2 "Nodes".
_NODE_PLACE_VALUES = frozenset({"city", "town", "village"})

#: `place=*` values an *area* classifies as a named place-area settlement --
#: same vocabulary as `_NODE_PLACE_VALUES`, kept as its own constant since
#: the two rules (D2 "Nodes" vs "Areas" rule 2) are independent and must not
#: silently drift together.
_AREA_PLACE_VALUES = frozenset({"city", "town", "village"})

#: `landuse=*` values an area classifies as built-up settlement (D2 "Areas"
#: rule 3), and the `landcover_class="built_up"` tag rule 2's place-area
#: exemption still applies (D2 "Areas" rule 2's own note).
_BUILT_UP_LANDUSE_VALUES = frozenset(
    {"residential", "commercial", "retail", "industrial", "military", "construction"}
)

#: `natural=water`'s own `water=*` tag mapped to the stored `water` subtype
#: (D2 "Areas" rule 1). A `natural=water` area with no `water` tag at all is
#: also accepted, as the generic `"lake"` subtype (mechanism-substitution
#: note 7: "the same three categories under older tagging").
_WATER_TAG_TO_SUBTYPE = {
    "lake": "lake",
    "reservoir": "reservoir",
    "river": "river_area",
}

#: `landuse=*` values mapped to a landcover class (D2 "Areas" rule 4, first
#: half).
_LANDUSE_TO_LANDCOVER_CLASS = {
    "forest": "forest",
    "orchard": "orchard",
    "vineyard": "orchard",
    "plantation": "orchard",
    "farmland": "fields",
    "meadow": "fields",
    "grass": "fields",
    "quarry": "barren",
}

#: `natural=*` values mapped to a landcover class (D2 "Areas" rule 4, second
#: half -- evaluated only when `landuse` did not already match).
_NATURAL_TO_LANDCOVER_CLASS = {
    "wood": "forest",
    "scrub": "scrub",
    "heath": "scrub",
    "grassland": "fields",
    "sand": "barren",
    "bare_rock": "barren",
    "scree": "barren",
}


@dataclass
class OsmIngestStats:
    """Per-build census: per-kind feature counts, per-landcover-class
    counts, every independently-counted drop reason, and vertex totals
    before/after simplification (Stage 6's validation tool reports the
    single *largest* stored polygon's vertex count directly from the built
    store; these two totals are the aggregate figures a running ingest can
    cheaply keep). Never a silent drop -- see the module docstring."""

    named_places: int = 0
    water_features: int = 0
    coastline_features: int = 0
    settlement_features: int = 0
    landcover_features: int = 0
    landcover_by_class: dict[str, int] = field(default_factory=dict)

    unnamed_dams_dropped: int = 0
    unnamed_peaks_dropped: int = 0
    lines_skipped_unclassified: int = 0
    lines_skipped_degenerate: int = 0
    areas_skipped_unclassified: int = 0
    rings_dropped_min_area: int = 0
    rings_dropped_degenerate_after_simplify: int = 0
    holes_kept: int = 0
    holes_dropped_below_min_area: int = 0
    holes_dropped_degenerate_after_simplify: int = 0
    vertices_before_simplify: int = 0
    vertices_after_simplify: int = 0

    # Carried through unchanged from `OsmFeatureSet`/`osm.pbf`'s
    # `StreamFeaturesResult` -- see those modules' own docstrings for what
    # each one means.
    relations_skipped: int = 0
    multipolygon_relations_seen: int = 0
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


def _classify_node(tags: dict[str, str]) -> tuple[str, str] | None:
    """Returns `(kind, subtype)` for a node classification rule (D2
    "Nodes"), or `None` if no rule matches. The `name` requirement is the
    caller's job (`_ingest_node`), not this function's -- classification and
    the name requirement are independent concerns (an unnamed match is a
    counted drop for `peak`/`dam`, a silent drop for `place`)."""
    place = tags.get("place")
    if place in _NODE_PLACE_VALUES:
        return ("named_place", place)
    if tags.get("natural") == "peak":
        return ("named_place", "peak")
    if tags.get("waterway") == "dam":
        return ("named_place", "dam")
    return None


def _classify_line(tags: dict[str, str]) -> tuple[str, str | None] | None:
    """Returns `(kind, subtype)` for a LineString-producing line
    classification rule (D2 "Lines"): `waterway=river` or `natural=coastline`.
    The `waterway=dam` rule is **not** covered here -- it produces a `Point`
    feature (at the polyline's half-length vertex), not a `LineString`, and
    is handled directly by `_ingest_line`."""
    if tags.get("waterway") == "river":
        return ("water", "river")
    if tags.get("natural") == "coastline":
        return ("coastline", None)
    return None


def _classify_area(tags: dict[str, str]) -> tuple[str, str, str | None] | None:
    """Returns `(kind, subtype, landcover_class)` for an area classification
    rule (D2 "Areas", precedence rules 1-4 below), or `None` if no rule
    matches (rule 5's "anything else"). `natural=coastline`/`waterway=dam`
    areas are the caller's job to skip *before* calling this (`_ingest_area`)
    -- D2 rule 5's note that `way()` already handles those."""
    natural = tags.get("natural")
    landuse = tags.get("landuse")

    # Rule 1: water (`natural=water`, `landuse=reservoir`, `waterway=riverbank`).
    if natural == "water":
        water_tag = tags.get("water")
        if water_tag is None:
            return ("water", "lake", None)
        subtype = _WATER_TAG_TO_SUBTYPE.get(water_tag)
        if subtype is not None:
            return ("water", subtype, None)
        return None  # every other water=* value: dropped, counted unclassified
    if landuse == "reservoir":
        return ("water", "reservoir", None)
    if tags.get("waterway") == "riverbank":
        return ("water", "river_area", None)

    # Rule 2: named place-area settlement.
    place = tags.get("place")
    if place in _AREA_PLACE_VALUES:
        landcover_class = "built_up" if landuse in _BUILT_UP_LANDUSE_VALUES else None
        return ("settlement", place, landcover_class)

    # Rule 3: built-up landuse settlement.
    if landuse in _BUILT_UP_LANDUSE_VALUES:
        return ("settlement", "built_up", "built_up")

    # Rule 4: landcover, by landuse first, then by natural.
    if landuse is not None:
        landcover_class = _LANDUSE_TO_LANDCOVER_CLASS.get(landuse)
        if landcover_class is not None:
            return ("landcover", landcover_class, landcover_class)
    if natural is not None:
        landcover_class = _NATURAL_TO_LANDCOVER_CLASS.get(natural)
        if landcover_class is not None:
            return ("landcover", landcover_class, landcover_class)

    return None  # rule 5: anything else


def _polyline_half_length_point(points: list[Point]) -> Point:
    """The point at half the polyline's total arc length -- D2's "half-length
    vertex" for collapsing a `waterway=dam` line into a single `named_place`
    Point. Interpolated along the segment straddling the midpoint, not
    snapped to the nearest existing vertex, so the result is stable
    regardless of how unevenly the source way's vertices are spaced."""
    if len(points) == 1:
        return points[0]
    segment_lengths = [
        distance_point_point(points[i], points[i + 1]) for i in range(len(points) - 1)
    ]
    total_length = sum(segment_lengths)
    if total_length == 0.0:
        return points[0]

    target = total_length / 2.0
    accumulated = 0.0
    for i, segment_length in enumerate(segment_lengths):
        if accumulated + segment_length >= target:
            t = (target - accumulated) / segment_length if segment_length > 0 else 0.0
            ax, az = points[i]
            bx, bz = points[i + 1]
            return (ax + t * (bx - ax), az + t * (bz - az))
        accumulated += segment_length
    return points[-1]


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
    classification = _classify_node(node.tags)
    if classification is None:
        return None
    kind, subtype = classification

    if "name" not in node.tags:
        if subtype == "dam":
            stats.unnamed_dams_dropped += 1
        elif subtype == "peak":
            stats.unnamed_peaks_dropped += 1
        return None

    x, z = wgs84_to_dcs(theatre, node.lat, node.lon)
    if not _within_region(x, z, centre_x, centre_z, half_extent_x_m, half_extent_z_m):
        return None

    stats.named_places += 1
    return StoredFeature(
        kind=kind,
        geom_type="Point",
        geometry=[(x, z)],
        name=node.tags["name"],
        subtype=subtype,
        tags={},
        source_id=source_id,
        source_ref=f"node/{node.id}",
        provenance=dict(_PROVENANCE),
        confidence=dict(_CONFIDENCE),
        position_uncertainty_m=_OSM_POSITION_UNCERTAINTY_M,
    )


def _ingest_line(
    way: OsmWay,
    theatre: str,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    source_id: int | None,
    stats: OsmIngestStats,
) -> StoredFeature | None:
    points = [wgs84_to_dcs(theatre, lat, lon) for lat, lon in way.points]
    if len(points) < 2:
        stats.lines_skipped_degenerate += 1
        return None

    if way.tags.get("waterway") == "dam":
        if "name" not in way.tags:
            stats.unnamed_dams_dropped += 1
            return None
        dam_point = _polyline_half_length_point(points)
        x, z = dam_point
        if not _within_region(
            x, z, centre_x, centre_z, half_extent_x_m, half_extent_z_m
        ):
            return None
        stats.named_places += 1
        return StoredFeature(
            kind="named_place",
            geom_type="Point",
            geometry=[dam_point],
            name=way.tags["name"],
            subtype="dam",
            tags={},
            source_id=source_id,
            source_ref=f"way/{way.id}",
            provenance=dict(_PROVENANCE),
            confidence=dict(_CONFIDENCE),
            position_uncertainty_m=_OSM_POSITION_UNCERTAINTY_M,
        )

    classification = _classify_line(way.tags)
    if classification is None:
        stats.lines_skipped_unclassified += 1
        return None
    kind, subtype = classification

    if not any(
        _within_region(x, z, centre_x, centre_z, half_extent_x_m, half_extent_z_m)
        for x, z in points
    ):
        return None

    stats.vertices_before_simplify += len(points)
    simplified = simplify_polyline(points, SIMPLIFY_TOLERANCE_M)
    if len(simplified) < 2:
        stats.lines_skipped_degenerate += 1
        return None
    stats.vertices_after_simplify += len(simplified)

    if kind == "water":
        stats.water_features += 1
    else:
        stats.coastline_features += 1

    return StoredFeature(
        kind=kind,
        geom_type="LineString",
        geometry=simplified,
        name=way.tags.get("name"),
        subtype=subtype,
        tags={},
        source_id=source_id,
        source_ref=f"way/{way.id}",
        provenance=dict(_PROVENANCE),
        confidence=dict(_CONFIDENCE),
        position_uncertainty_m=_OSM_POSITION_UNCERTAINTY_M,
    )


def _ingest_ring(
    ring: OsmRing,
    kind: str,
    subtype: str,
    landcover_class: str | None,
    name: str | None,
    source_ref: str,
    theatre: str,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    source_id: int | None,
    stats: OsmIngestStats,
) -> StoredFeature | None:
    """The Design D3 per-ring pipeline: project, region-clip, min-area
    filter (outer ring and each hole independently), simplify (outer ring
    and each kept hole), and shape the stored feature -- one ring in, one
    `StoredFeature` or `None` out."""
    outer = [wgs84_to_dcs(theatre, lat, lon) for lat, lon in ring.outer]
    if not any(
        _within_region(x, z, centre_x, centre_z, half_extent_x_m, half_extent_z_m)
        for x, z in outer
    ):
        return None

    holes = [
        [wgs84_to_dcs(theatre, lat, lon) for lat, lon in inner] for inner in ring.inners
    ]

    kept_holes: list[list[Point]] = []
    for hole in holes:
        if ring_area_m2(hole) < MIN_AREA_M2:
            stats.holes_dropped_below_min_area += 1
            continue
        kept_holes.append(hole)

    net_area_m2 = ring_area_m2(outer) - sum(ring_area_m2(h) for h in kept_holes)

    needs_min_area_check = (
        kind == "water"
        or kind == "landcover"
        or (kind == "settlement" and subtype == "built_up")
    )
    if needs_min_area_check and net_area_m2 < MIN_AREA_M2:
        stats.rings_dropped_min_area += 1
        return None

    stats.vertices_before_simplify += len(outer) + sum(len(h) for h in kept_holes)

    simplified_outer = simplify_ring(outer, SIMPLIFY_TOLERANCE_M)
    if simplified_outer is None:
        stats.rings_dropped_degenerate_after_simplify += 1
        return None

    simplified_holes: list[list[Point]] = []
    for hole in kept_holes:
        simplified_hole = simplify_ring(hole, SIMPLIFY_TOLERANCE_M)
        if simplified_hole is None:
            stats.holes_dropped_degenerate_after_simplify += 1
            continue
        simplified_holes.append(simplified_hole)
        stats.holes_kept += 1

    stats.vertices_after_simplify += len(simplified_outer) + sum(
        len(h) for h in simplified_holes
    )

    tags: dict[str, Any] = {"area_m2": net_area_m2}
    if simplified_holes:
        tags["inner_rings"] = simplified_holes
    if landcover_class is not None:
        tags["landcover_class"] = landcover_class

    return StoredFeature(
        kind=kind,
        geom_type="Polygon",
        geometry=simplified_outer,
        name=name,
        subtype=subtype,
        tags=tags,
        source_id=source_id,
        source_ref=source_ref,
        provenance=dict(_PROVENANCE),
        confidence=dict(_CONFIDENCE),
        position_uncertainty_m=_OSM_POSITION_UNCERTAINTY_M,
    )


def _ingest_area(
    area: OsmArea,
    theatre: str,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    source_id: int | None,
    stats: OsmIngestStats,
) -> list[StoredFeature]:
    # D2 rule 5's note: a closed `natural=coastline` way (an island) and a
    # `waterway=dam` area both also reach `way()` -- the line/point path
    # already handles them, so they are silently skipped here, not counted
    # as unclassified.
    if area.tags.get("natural") == "coastline" or area.tags.get("waterway") == "dam":
        return []

    classification = _classify_area(area.tags)
    if classification is None:
        stats.areas_skipped_unclassified += 1
        return []
    kind, subtype, landcover_class = classification

    name = area.tags.get("name")
    source_prefix = "way" if area.from_way else "relation"
    features: list[StoredFeature] = []
    for ring in area.rings:
        feature = _ingest_ring(
            ring,
            kind,
            subtype,
            landcover_class,
            name,
            f"{source_prefix}/{area.id}",
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

    if kind == "settlement":
        stats.settlement_features += len(features)
    elif kind == "landcover":
        stats.landcover_features += len(features)
        stats.landcover_by_class[subtype] = stats.landcover_by_class.get(
            subtype, 0
        ) + len(features)
    elif kind == "water":
        stats.water_features += len(features)

    return features


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
    """Ingest one batch of ways as lines/dam-points (`_ingest_line`),
    mutating `stats` in place and returning the batch's kept features -- see
    `ingest_osm_nodes_batch`. A closed tagged way also reaches `osm.pbf`'s
    `area()` callback and is separately ingested as an area by
    `ingest_osm_areas_batch`; this function never classifies area kinds
    (water/settlement/landcover) itself."""
    features: list[StoredFeature] = []
    for way in ways:
        feature = _ingest_line(
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


def ingest_osm_areas_batch(
    areas: list[OsmArea],
    theatre: str,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    source_id: int | None,
    stats: OsmIngestStats,
) -> list[StoredFeature]:
    """Ingest one batch of areas, mutating `stats` in place and returning
    every kept ring's feature (one `OsmArea` can yield zero, one, or several
    `StoredFeature`s -- see `_ingest_area`) -- see `ingest_osm_nodes_batch`."""
    features: list[StoredFeature] = []
    for area in areas:
        features.extend(
            _ingest_area(
                area,
                theatre,
                centre_x,
                centre_z,
                half_extent_x_m,
                half_extent_z_m,
                source_id,
                stats,
            )
        )
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
    """Convert a parsed `OsmFeatureSet` into `named_place`/`water`/
    `coastline`/`settlement`/`landcover` features clipped to the rectangular
    region `(centre_x, centre_z) +/- (half_extent_x_m, half_extent_z_m)`.

    A thin wrapper over `ingest_osm_nodes_batch`/`ingest_osm_ways_batch`/
    `ingest_osm_areas_batch`, each called once over the feature set's full
    node/way/area lists -- identical behaviour to before the streaming-ingest
    fix split the node/way loop bodies out, so the Overpass (M3) path and
    this module's own tests need no change."""
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
    area_features = ingest_osm_areas_batch(
        feature_set.areas,
        theatre,
        centre_x,
        centre_z,
        half_extent_x_m,
        half_extent_z_m,
        source_id,
        stats,
    )
    return node_features + way_features + area_features, stats
