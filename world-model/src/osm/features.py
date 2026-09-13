"""Parses a cached Overpass API JSON response into feature dataclasses.

Uses stdlib `json` only -- no new dependency. Handles the two element shapes
produced by the plan's `out geom;` query: `"node"` elements (bare `lat`/`lon`
plus `tags`) and `"way"` elements (a `geometry` list of `{lat, lon}` points
inline, avoiding a separate node-ID resolution pass, plus `tags`).

**Superseded on the pipeline path as of M9** by `osm.pbf.load_features`,
which parses a pre-clipped `.osm.pbf` extract into the exact same
`OsmFeatureSet`/`OsmNode`/`OsmWay` shapes defined below -- this module is
unchanged and still used by `tools/inspect_osm_overlay.py` and any build
that still supplies `osm_cache_path` instead of `osm_pbf_path`
(`build.pipeline.build_region`).

**`OsmArea` (osm-landcover-optimization)**: `osm.pbf.load_features`'s area
assembly (`pbf.py`'s `area()` callback, libosmium's two-pass multipolygon
manager) has no Overpass equivalent -- Overpass never returns assembled
relation geometry, only member references. Per the plan's "Affected
Modules" (M9 Design Decision 3 continuity: the two loaders must keep
producing identical shapes so `build.ingest_osm` never source-branches),
this module's own `load_features` mirrors the *way* half of that: every
tagged closed way (4+ points, first == last) is *also* emitted as an
`OsmArea` with a single ringless-holes outer ring, alongside its `OsmWay`.
Multipolygon *relations* stay a counted skip here (`relations_skipped`) --
assembling a relation's outer/inner rings from Overpass's flat member list
is real work this module was never asked to do, and every current/planned
Overpass caller is a small hand-fetched region where that gap is
acceptable.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OsmNode:
    """A single OSM node feature (e.g. a `place` point)."""

    id: int
    tags: dict[str, str]
    lat: float
    lon: float


@dataclass(frozen=True)
class OsmWay:
    """A single OSM way feature (e.g. a `highway`, `building`, `waterway`).

    `points` is the way's geometry as (lat, lon) pairs, in way order, as
    returned inline by Overpass's `out geom;` -- no separate node-ID
    resolution pass needed.
    """

    id: int
    tags: dict[str, str]
    points: list[tuple[float, float]]


@dataclass(frozen=True)
class OsmRing:
    """One ring of an `OsmArea`'s geometry: an `outer` boundary (a closed
    `(lat, lon)` point list, first point repeated as last, same convention
    `OsmWay.points` uses for a closed way) plus zero or more `inners` (holes),
    each itself a closed `(lat, lon)` point list."""

    outer: list[tuple[float, float]]
    inners: list[list[tuple[float, float]]] = field(default_factory=list)


@dataclass(frozen=True)
class OsmArea:
    """One assembled area feature: either a closed tagged way (`from_way`)
    or a `type=multipolygon`/`boundary` relation. `rings` holds one
    `OsmRing` per outer ring -- almost always one, but a true multipolygon
    (`is_multipolygon()` on the source `osmium.osm.Area`) can have several
    disjoint outer rings sharing one set of tags; this module does not
    collapse them, `build.ingest_osm` stores each ring as its own feature
    (Design D3: "min-area is judged per outer ring, not per relation
    total")."""

    id: int
    from_way: bool
    tags: dict[str, str]
    rings: list[OsmRing]


@dataclass(frozen=True)
class OsmFeatureSet:
    """All features parsed from one Overpass response.

    `relations_skipped` counts `"relation"` elements in the response --
    multipolygon relations (e.g. some large water bodies and settlement
    extents) are not parsed into geometry (real work: outer/inner ring
    assembly), but per
    `plans/m5-first-persistent-model/plan.md`'s "Multipolygon relations"
    risk entry, an unsupported relation must be an explicitly counted skip,
    never a silent drop -- `build/ingest_osm.py` surfaces this count in the
    research note.

    `ways_skipped_unresolved_nodes` is M9's addition, always 0 for this
    module's own Overpass-sourced path (Overpass's `out geom;` never omits a
    way's inline geometry) -- it exists here, on the shared dataclass,
    because `osm.pbf.load_features` produces the exact same `OsmFeatureSet`
    shape and needs a field for a way whose node locations pyosmium's index
    never resolved (should not happen post-`osmium extract
    --strategy=smart`, but is a counted skip rather than assumed away; see
    that module's docstring).

    `areas` is osm-landcover-optimization's addition -- see this module's
    docstring for what this loader does and does not assemble into areas.
    """

    nodes: list[OsmNode] = field(default_factory=list)
    ways: list[OsmWay] = field(default_factory=list)
    areas: list[OsmArea] = field(default_factory=list)
    relations_skipped: int = 0
    ways_skipped_unresolved_nodes: int = 0


def _parse_node(element: dict[str, Any]) -> OsmNode:
    return OsmNode(
        id=element["id"],
        tags=element.get("tags", {}),
        lat=element["lat"],
        lon=element["lon"],
    )


def _parse_way(element: dict[str, Any]) -> OsmWay:
    points = [(point["lat"], point["lon"]) for point in element.get("geometry", [])]
    return OsmWay(
        id=element["id"],
        tags=element.get("tags", {}),
        points=points,
    )


def _is_closed_tagged_way(way: OsmWay) -> bool:
    """True for a tagged way whose geometry closes with 4+ points -- the
    same "closed way, from_way area" shape `osm.pbf`'s libosmium-driven
    `area()` callback produces (see this module's docstring)."""
    return bool(way.tags) and len(way.points) >= 4 and way.points[0] == way.points[-1]


def _way_to_area(way: OsmWay) -> OsmArea:
    """Mirror a closed tagged way into a single-outer-ring, no-holes
    `OsmArea` -- Overpass's flat `out geom;` response carries no hole
    information for a plain closed way (a way itself cannot have holes;
    only a multipolygon relation can, and those stay a counted
    `relations_skipped` skip here, see the module docstring)."""
    return OsmArea(
        id=way.id,
        from_way=True,
        tags=way.tags,
        rings=[OsmRing(outer=way.points, inners=[])],
    )


def load_features(cache_path: Path) -> OsmFeatureSet:
    """Parse a cached Overpass JSON response at `cache_path`.

    Raises `KeyError`/`json.JSONDecodeError` if the file isn't a
    well-formed Overpass `out geom;` response.
    """
    data = json.loads(cache_path.read_text(encoding="utf-8"))

    nodes: list[OsmNode] = []
    ways: list[OsmWay] = []
    areas: list[OsmArea] = []
    relations_skipped = 0
    for element in data["elements"]:
        element_type = element["type"]
        if element_type == "node":
            nodes.append(_parse_node(element))
        elif element_type == "way":
            way = _parse_way(element)
            ways.append(way)
            if _is_closed_tagged_way(way):
                areas.append(_way_to_area(way))
        elif element_type == "relation":
            relations_skipped += 1
        # Any other element type is unrecognized and dropped without a count
        # -- Overpass's `out geom;` only ever emits node/way/relation.

    return OsmFeatureSet(
        nodes=nodes, ways=ways, areas=areas, relations_skipped=relations_skipped
    )
