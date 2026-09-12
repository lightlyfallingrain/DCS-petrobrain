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
`docs/M9_OSM_RUN_INSTRUCTIONS.md`. `load_features`/`stream_features` take
exactly one path.

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

**Bounded batching (M9 streaming-ingest fix)**: `_FeatureCollector` no
longer accumulates every kept node/way in memory for the whole `apply_file`
pass -- at `syria-full` scale (~8.6M ways kept) that reproduced the exact
memory blowup this module was written to avoid, just one layer up (Python
object overhead across millions of live `OsmWay` instances, not raw
coordinate data). `stream_features` is the new bounded-memory entry point:
it flushes kept nodes/ways to caller-supplied callbacks every `batch_size`
elements, so peak memory is bounded by `batch_size`, not by the file's total
element count. `load_features` is now a thin wrapper over `stream_features`
with a single accumulate-everything callback and an effectively-unbounded
batch size, so its existing public signature/behaviour is unchanged and
`tests/test_osm_pbf.py`'s pre-existing correctness tests still pass as-is.
See `plans/osm-streaming-ingest/plan.md`.
"""

import logging
import sys
import time
from collections.abc import Callable
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

# How many kept nodes/ways `_FeatureCollector` buffers before flushing to its
# callbacks, in the streaming (`stream_features`) path. Deliberately separate
# from, and much smaller than, `_PROGRESS_LOG_INTERVAL_ELEMENTS` above, which
# counts *raw* elements seen (including discarded untagged nodes), not kept
# objects actually held in memory. At ~8.6M ways total (the stalled
# `syria-full` run's own progress log), 50,000 keeps peak buffered way
# objects to roughly 0.5% of the old unbounded case -- tens of MB, not
# gigabytes -- while keeping the resulting SQLite commit count reasonable
# (~170-ish commits for the full ways total, not thousands). See
# `plans/osm-streaming-ingest/plan.md`'s "Risks & Unknowns" -- this number is
# a rough estimate, not a profiled one, and may need re-tuning after a real
# `syria-full` run.
_INGEST_BATCH_ELEMENTS = 50_000


class _FeatureCollector(osmium.SimpleHandler):
    """Buffers tagged nodes and geometry-resolved ways in bounded-size
    batches during one `apply_file` pass, flushing each batch to a
    caller-supplied callback once it reaches `batch_size`. Not part of the
    public API -- use `stream_features` or `load_features`."""

    def __init__(
        self,
        on_nodes: Callable[[list[OsmNode]], None],
        on_ways: Callable[[list[OsmWay]], None],
        batch_size: int,
    ) -> None:
        super().__init__()
        self._on_nodes = on_nodes
        self._on_ways = on_ways
        self._batch_size = batch_size
        self._node_buffer: list[OsmNode] = []
        self._way_buffer: list[OsmWay] = []
        self.relations_skipped = 0
        self.ways_skipped_unresolved_nodes = 0
        self._nodes_kept_total = 0
        self._ways_kept_total = 0
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
            self._nodes_kept_total,
            self._ways_kept_total,
            elapsed_s,
        )

    def node(self, n: osmium.osm.Node) -> None:
        self._log_progress_if_due()
        if len(n.tags) == 0:
            return
        self._node_buffer.append(
            OsmNode(
                id=n.id,
                tags={tag.k: tag.v for tag in n.tags},
                lat=n.location.lat,
                lon=n.location.lon,
            )
        )
        self._nodes_kept_total += 1
        if len(self._node_buffer) >= self._batch_size:
            self._on_nodes(self._node_buffer)
            self._node_buffer = []

    def way(self, w: osmium.osm.Way) -> None:
        self._log_progress_if_due()
        points: list[tuple[float, float]] = []
        for node_ref in w.nodes:
            if not node_ref.location.valid():
                self.ways_skipped_unresolved_nodes += 1
                return
            points.append((node_ref.location.lat, node_ref.location.lon))
        self._way_buffer.append(
            OsmWay(id=w.id, tags={tag.k: tag.v for tag in w.tags}, points=points)
        )
        self._ways_kept_total += 1
        if len(self._way_buffer) >= self._batch_size:
            self._on_ways(self._way_buffer)
            self._way_buffer = []

    def relation(self, r: osmium.osm.Relation) -> None:
        self._log_progress_if_due()
        self.relations_skipped += 1

    def flush(self) -> None:
        """Flush any leftover partial batch below `batch_size` for both
        nodes and ways -- must be called once after `apply_file` returns, or
        the tail of the file silently vanishes."""
        if self._node_buffer:
            self._on_nodes(self._node_buffer)
            self._node_buffer = []
        if self._way_buffer:
            self._on_ways(self._way_buffer)
            self._way_buffer = []


def stream_features(
    pbf_path: Path,
    on_nodes: Callable[[list[OsmNode]], None],
    on_ways: Callable[[list[OsmWay]], None],
    batch_size: int = _INGEST_BATCH_ELEMENTS,
) -> tuple[int, int]:
    """Parse one pre-clipped, pre-merged `.osm.pbf` file at `pbf_path`,
    calling `on_nodes`/`on_ways` with each batch of up to `batch_size` kept
    nodes/ways as they are collected -- bounded peak memory, independent of
    the file's total element count, unlike `load_features`'s old
    accumulate-everything behaviour.

    Uses `locations=True, idx="sparse_mem_array"` so pyosmium's C++ side
    resolves way-node geometry inline via a memory-efficient index, not a
    naive Python dict -- see the module docstring.

    Returns `(relations_skipped, ways_skipped_unresolved_nodes)`.
    """
    collector = _FeatureCollector(on_nodes, on_ways, batch_size)
    collector.apply_file(str(pbf_path), locations=True, idx="sparse_mem_array")
    collector.flush()
    return collector.relations_skipped, collector.ways_skipped_unresolved_nodes


def load_features(pbf_path: Path) -> OsmFeatureSet:
    """Parse one pre-clipped, pre-merged `.osm.pbf` file at `pbf_path` into
    an `OsmFeatureSet`, the same shape `osm.features.load_features` produces
    from a cached Overpass response.

    A thin wrapper over `stream_features` with a single
    accumulate-everything callback and an effectively-unbounded batch size,
    kept for callers (and tests) that want the whole file's features in one
    in-memory object rather than streaming them -- not recommended for
    theatre-scale extracts, see `build.pipeline`'s `osm_pbf_path` branch for
    the streaming path those use instead.
    """
    nodes: list[OsmNode] = []
    ways: list[OsmWay] = []
    relations_skipped, ways_skipped_unresolved_nodes = stream_features(
        pbf_path, nodes.extend, ways.extend, batch_size=sys.maxsize
    )
    return OsmFeatureSet(
        nodes=nodes,
        ways=ways,
        relations_skipped=relations_skipped,
        ways_skipped_unresolved_nodes=ways_skipped_unresolved_nodes,
    )
