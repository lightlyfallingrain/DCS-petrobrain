"""Parses a pre-clipped, pre-merged `.osm.pbf` extract into an
`OsmFeatureSet` using `pyosmium` (PyPI/import name `osmium` -- "pyosmium" is
the project's own name, not the distribution name; see
`docs/M9_OSM_RUN_INSTRUCTIONS.md`).

This is the M9 real-data path: `osm.features.load_features` (Overpass JSON)
and this module both produce the exact same `OsmFeatureSet`/`OsmNode`/
`OsmWay` shapes, so everything downstream (`build.ingest_osm.ingest_osm`)
needs no source-specific branching -- see `plans/m9-osm-geofabrik/plan.md`
Design Decision 3.

**One pre-clipped, pre-merged file only** (Design Decision 2): this module
never juggles multiple country extracts or derives a clip bbox itself --
that is `osmium-tool`'s job, run by the user per
`docs/M9_OSM_RUN_INSTRUCTIONS.md`. `load_features` takes exactly one path.

**Only tagged nodes are kept** as `OsmNode` instances -- untagged nodes
exist purely to give ways their geometry, which pyosmium's location index
(`locations=True, idx="sparse_mem_array"`) resolves internally without ever
handing them to Python. Keeping every untagged node in a Python list (tens
of millions in a country extract) would reproduce the exact memory blowup
this milestone chose pyosmium specifically to avoid -- see the plan's "What
changed from the deferred plan". This matches Overpass's own `out geom;`
behaviour, which likewise never emits an untagged node as a standalone
element.

A way with any node whose location the index never resolved (should not
happen after `osmium extract --strategy=smart`, but is not assumed away) is
a counted skip, `ways_skipped_unresolved_nodes`, following this project's
`relations_skipped` precedent for "unsupported construct, not a silent
drop" (see `osm.features.OsmFeatureSet`'s docstring).
"""

import logging
import time
from pathlib import Path

import osmium
import osmium.osm

from osm.features import OsmFeatureSet, OsmNode, OsmWay

logger = logging.getLogger(__name__)

# How often `_FeatureCollector` logs progress while `apply_file` is running,
# in raw elements seen (tagged or not -- pyosmium calls back on every element
# in the file, so this is a real progress signal even though only tagged
# nodes/geometry-resolved ways are kept). A country-scale merged extract can
# run `apply_file` for minutes with no other feedback; without this, a long
# OSM stage looks indistinguishable from a hang. See `docs/M9_OSM_RUN_INSTRUCTIONS.md`.
_PROGRESS_LOG_INTERVAL_ELEMENTS = 500_000


class _FeatureCollector(osmium.SimpleHandler):
    """Accumulates tagged nodes and geometry-resolved ways in memory for one
    `apply_file` pass. Not part of the public API -- use `load_features`."""

    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[OsmNode] = []
        self.ways: list[OsmWay] = []
        self.relations_skipped = 0
        self.ways_skipped_unresolved_nodes = 0
        self._elements_seen = 0
        self._started_at = time.monotonic()

    def _log_progress_if_due(self) -> None:
        self._elements_seen += 1
        if self._elements_seen % _PROGRESS_LOG_INTERVAL_ELEMENTS != 0:
            return
        elapsed_s = time.monotonic() - self._started_at
        logger.info(
            "osm.pbf: %d elements seen (%d tagged nodes, %d ways kept, %.1fs elapsed)",
            self._elements_seen,
            len(self.nodes),
            len(self.ways),
            elapsed_s,
        )

    def node(self, n: osmium.osm.Node) -> None:
        self._log_progress_if_due()
        if len(n.tags) == 0:
            return
        self.nodes.append(
            OsmNode(
                id=n.id,
                tags={tag.k: tag.v for tag in n.tags},
                lat=n.location.lat,
                lon=n.location.lon,
            )
        )

    def way(self, w: osmium.osm.Way) -> None:
        self._log_progress_if_due()
        points: list[tuple[float, float]] = []
        for node_ref in w.nodes:
            if not node_ref.location.valid():
                self.ways_skipped_unresolved_nodes += 1
                return
            points.append((node_ref.location.lat, node_ref.location.lon))
        self.ways.append(
            OsmWay(id=w.id, tags={tag.k: tag.v for tag in w.tags}, points=points)
        )

    def relation(self, r: osmium.osm.Relation) -> None:
        self._log_progress_if_due()
        self.relations_skipped += 1


def load_features(pbf_path: Path) -> OsmFeatureSet:
    """Parse one pre-clipped, pre-merged `.osm.pbf` file at `pbf_path` into
    an `OsmFeatureSet`, the same shape `osm.features.load_features` produces
    from a cached Overpass response.

    Uses `locations=True, idx="sparse_mem_array"` so pyosmium's C++ side
    resolves way-node geometry inline via a memory-efficient index, not a
    naive Python dict -- see the module docstring.
    """
    collector = _FeatureCollector()
    collector.apply_file(str(pbf_path), locations=True, idx="sparse_mem_array")
    return OsmFeatureSet(
        nodes=collector.nodes,
        ways=collector.ways,
        relations_skipped=collector.relations_skipped,
        ways_skipped_unresolved_nodes=collector.ways_skipped_unresolved_nodes,
    )
