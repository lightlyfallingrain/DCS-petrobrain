"""OSM overlay subsystem.

Fetches a small OpenStreetMap region (via the Overpass API) and parses it
into in-memory feature dataclasses, for diagnostic overlay against DCS
coordinate/raster space. Mirrors `coordinates/`/`raster/`'s shape:
network/caching lives in `osm.overpass`, parsing lives in `osm.features`.

M3 does not introduce a persistent spatial storage layer -- see
`world-model/research/` for the M3 research note recording that decision.
Data licensed under the OpenStreetMap ODbL; any rendered or reported output
derived from it must carry an "(c) OpenStreetMap contributors" attribution.
"""

from .features import OsmFeatureSet, OsmNode, OsmWay, load_features
from .overpass import BBox, fetch_bbox

__all__ = [
    "BBox",
    "OsmFeatureSet",
    "OsmNode",
    "OsmWay",
    "fetch_bbox",
    "load_features",
]
