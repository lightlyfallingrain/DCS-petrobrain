"""Parses a cached Overpass API JSON response into feature dataclasses.

Uses stdlib `json` only -- no new dependency. Handles the two element shapes
produced by the plan's `out geom;` query: `"node"` elements (bare `lat`/`lon`
plus `tags`) and `"way"` elements (a `geometry` list of `{lat, lon}` points
inline, avoiding a separate node-ID resolution pass, plus `tags`).
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
    """All features parsed from one Overpass response."""

    nodes: list[OsmNode] = field(default_factory=list)
    ways: list[OsmWay] = field(default_factory=list)


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
    for element in data["elements"]:
        element_type = element["type"]
        if element_type == "node":
            nodes.append(_parse_node(element))
        elif element_type == "way":
            ways.append(_parse_way(element))
        # "relation" elements are not requested by the plan's query and are
        # ignored if present.

    return OsmFeatureSet(nodes=nodes, ways=ways)
