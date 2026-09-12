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
    """

    nodes: list[OsmNode] = field(default_factory=list)
    ways: list[OsmWay] = field(default_factory=list)
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


def load_features(cache_path: Path) -> OsmFeatureSet:
    """Parse a cached Overpass JSON response at `cache_path`.

    Raises `KeyError`/`json.JSONDecodeError` if the file isn't a
    well-formed Overpass `out geom;` response.
    """
    data = json.loads(cache_path.read_text(encoding="utf-8"))

    nodes: list[OsmNode] = []
    ways: list[OsmWay] = []
    relations_skipped = 0
    for element in data["elements"]:
        element_type = element["type"]
        if element_type == "node":
            nodes.append(_parse_node(element))
        elif element_type == "way":
            ways.append(_parse_way(element))
        elif element_type == "relation":
            relations_skipped += 1
        # Any other element type is unrecognized and dropped without a count
        # -- Overpass's `out geom;` only ever emits node/way/relation.

    return OsmFeatureSet(nodes=nodes, ways=ways, relations_skipped=relations_skipped)
