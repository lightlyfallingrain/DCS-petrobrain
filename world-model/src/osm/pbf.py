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

**Area assembly (osm-landcover-optimization)**: `_FeatureCollector` also
defines `area()`, which makes `apply_file` run libosmium's two-pass
multipolygon manager automatically (fixture-verified against the installed
pyosmium 4.3.1/libosmium 2.20.0 -- see the plan's "Context verified for this
plan" section) -- no separate manager object, no second explicit pass coded
here. A closed tagged way is delivered to *both* `way()` and `area()`; a
`type=multipolygon`/`type=boundary` relation is delivered to `area()` only
(never `way()`). Areas are buffered and flushed in their own batches
(`_INGEST_BATCH_AREAS`, smaller than `_INGEST_BATCH_ELEMENTS` -- an area's
ring geometry is far more vertex-heavy per object than a bare node/way).

**`KeyFilter`**: `stream_features`/`load_features` pass
`osmium.filter.KeyFilter(*_CLASSIFIER_TAG_KEYS)` to `apply_file`, restricting
which elements reach `node()`/`way()`/`area()`/`relation()` at all (an
untagged, or tagged-but-irrelevant, way/node is never handed to Python --
fixture-verified: location resolution and multipolygon assembly are
unaffected, they still see every element in the file regardless of the
filter). This is the second, in-process filter alongside job (a)'s
`osmium tags-filter` pre-filter (`tools/osm_tags_filter.txt`) -- additive,
not a replacement; see the plan's mechanism-substitution note 3.

**`relation()`'s `multipolygon_relations_seen` vs `relations_skipped`**: a
relation reaching `relation()` (i.e. one whose own tags passed `KeyFilter`)
is counted as `multipolygon_relations_seen` when its `type` tag is
`"multipolygon"` or `"boundary"` -- libosmium's default area manager
assembles both of those relation types into areas (fixture-verified: a
`type=boundary` relation with a matching tag produced an `area()` call just
like a `type=multipolygon` one). Any other relation type that still passed
the tag filter (e.g. `type=site`) is not assembled into geometry by this
module and is counted as `relations_skipped`, preserving the "unsupported
construct, not a silent drop" precedent for that name.

**Progress reporting (progress-logging fix)**: the old mechanism here logged
every `_PROGRESS_LOG_INTERVAL_ELEMENTS` raw elements *seen*, counted from
inside `node()`/`way()`/`relation()`. That undercounted badly: `KeyFilter`
stops most elements from ever reaching those callbacks, and a closed-way/
relation two-pass area assembly runs in `apply_file`'s C++ core with no
Python callback at all -- a real `syria-full`-scale run logged one progress
line at 68.3s into an 81.0s parse of a single ~160MB pre-filtered extract,
then nothing until it finished (measured against a tags-filtered Turkey
extract; see `plans/osm-landcover-optimization/progress-logging.md`).
`stream_features` now wraps the whole `apply_file` call in `progress.
Heartbeat` instead: a background thread that logs every `_PROGRESS_LOG_
INTERVAL_S` regardless of what's happening on the main thread, reading
`_FeatureCollector`'s running counters. This only works because pyosmium
4.3.1's `apply_file` releases the GIL periodically on its own even when no
Python callback fires -- confirmed by measurement (a heartbeat thread ticked
every ~1.0s throughout a 10.3s filtered `apply_file` call), not assumed; see
the plan's "GIL release" finding. Since there is no exact byte- or
element-progress signal available during the silent stretches, the percent-
complete/ETA the heartbeat reports is a **calibrated estimate** (elapsed
time against `_PBF_CALIBRATED_BYTES_PER_S` applied to the input file's
size), always logged via `estimated=True` so it reads as `~` in the log
line -- the exact counters (`elements_seen`, `nodes_kept`, ...) alongside it
are real, not estimated.
"""

import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import osmium
import osmium.filter
import osmium.osm

from osm.features import OsmArea, OsmFeatureSet, OsmNode, OsmRing, OsmWay
from progress import Heartbeat, ThrottledProgress

logger = logging.getLogger(__name__)

# How often the `apply_file` heartbeat logs, in seconds -- this project's
# standing "at most every 30s, at least every ~30s" convention (see
# `progress.py`), not a per-module judgment call.
_PROGRESS_LOG_INTERVAL_S = 30.0

# Rough parse throughput for `stream_features` (KeyFilter + two-pass area
# assembly included), in bytes/second of *pre-filtered* `.osm.pbf` input --
# used only to give the heartbeat a rough ETA during `apply_file`'s silent
# stretches (see the module docstring's "Progress reporting"). Calibrated
# 2026-09-15 against a real Geofabrik extract: `osmium tags-filter` applied
# to the full (unclipped) Turkey country extract -> 160,387,119 bytes, 31.6M
# nodes / 736K ways / 33.8K relations -> `stream_features` end-to-end in
# 81.0s = ~1.98 MB/s. One data point, not a profiled average across tag
# densities/relation complexity -- good enough for a rough ETA, not treated
# as exact (see `plans/osm-landcover-optimization/progress-logging.md`).
_PBF_CALIBRATED_BYTES_PER_S = 1_980_000

# How many kept nodes/ways `_FeatureCollector` buffers before flushing to its
# callbacks, in the streaming (`stream_features`) path. Deliberately separate
# from, and much smaller than, the raw *elements seen* count `progress_counts`
# reports (which includes discarded untagged nodes), not kept objects
# actually held in memory. At ~8.6M ways total (the stalled
# `syria-full` run's own progress log), 50,000 keeps peak buffered way
# objects to roughly 0.5% of the old unbounded case -- tens of MB, not
# gigabytes -- while keeping the resulting SQLite commit count reasonable
# (~170-ish commits for the full ways total, not thousands). See
# `plans/osm-streaming-ingest/plan.md`'s "Risks & Unknowns" -- this number is
# a rough estimate, not a profiled one, and may need re-tuning after a real
# `syria-full` run.
_INGEST_BATCH_ELEMENTS = 50_000

# Same idea as `_INGEST_BATCH_ELEMENTS`, but for areas: deliberately smaller,
# because one `OsmArea` can carry thousands of ring vertices (a large forest
# or reservoir relation), unlike a node/way's handful of fields -- see
# `plans/osm-landcover-optimization/plan.md` Implementation Plan step 1.
_INGEST_BATCH_AREAS = 5_000

# The tag keys `KeyFilter` restricts `node()`/`way()`/`area()`/`relation()`
# callbacks to -- must stay a superset of everything `build.ingest_osm`'s
# classifier reads (mirrors `tools/osm_tags_filter.txt`'s role for job (a)'s
# `osmium tags-filter` pre-filter, one layer further in). Fixture-verified
# not to affect location resolution or multipolygon assembly (see module
# docstring).
_CLASSIFIER_TAG_KEYS = ("landuse", "natural", "place", "waterway", "water")

# Relation `type` tag values libosmium's default area manager assembles into
# areas (fixture-verified against a `type=boundary` relation, not just
# `type=multipolygon`) -- see the module docstring's `relation()` note.
_AREA_ASSEMBLED_RELATION_TYPES = frozenset({"multipolygon", "boundary"})


@dataclass(frozen=True)
class StreamFeaturesResult:
    """`stream_features`'s summary counts, returned once `apply_file` (and
    the trailing `flush()`) has completed -- a small named result rather
    than a growing positional tuple, since osm-landcover-optimization added
    a third count alongside the two `M9`/streaming-ingest-fix already
    returned."""

    relations_skipped: int
    ways_skipped_unresolved_nodes: int
    multipolygon_relations_seen: int


class _FeatureCollector(osmium.SimpleHandler):
    """Buffers tagged nodes, geometry-resolved ways, and assembled areas in
    bounded-size batches during one `apply_file` pass, flushing each batch
    to a caller-supplied callback once it reaches its own batch size. Not
    part of the public API -- use `stream_features` or `load_features`."""

    def __init__(
        self,
        on_nodes: Callable[[list[OsmNode]], None],
        on_ways: Callable[[list[OsmWay]], None],
        on_areas: Callable[[list[OsmArea]], None],
        batch_size: int,
        area_batch_size: int,
    ) -> None:
        super().__init__()
        self._on_nodes = on_nodes
        self._on_ways = on_ways
        self._on_areas = on_areas
        self._batch_size = batch_size
        self._area_batch_size = area_batch_size
        self._node_buffer: list[OsmNode] = []
        self._way_buffer: list[OsmWay] = []
        self._area_buffer: list[OsmArea] = []
        self.relations_skipped = 0
        self.multipolygon_relations_seen = 0
        self.ways_skipped_unresolved_nodes = 0
        self._nodes_kept_total = 0
        self._ways_kept_total = 0
        self._areas_kept_total = 0
        self._elements_seen = 0

    def progress_counts(self) -> dict[str, int]:
        """A snapshot of this collector's running counters, safe to call
        from another thread while `apply_file` is still running (plain
        attribute reads under the GIL -- see `progress.Heartbeat`'s
        docstring on why no lock is needed here). Used by `stream_features`'s
        heartbeat to report real, non-estimated counts alongside its
        estimated elapsed-time-based ETA."""
        return {
            "elements_seen": self._elements_seen,
            "nodes_kept": self._nodes_kept_total,
            "ways_kept": self._ways_kept_total,
            "areas_kept": self._areas_kept_total,
        }

    def node(self, n: osmium.osm.Node) -> None:
        self._elements_seen += 1
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
        self._elements_seen += 1
        if len(w.tags) == 0:
            # Under `KeyFilter`, a way with no tags at all should never
            # reach this callback (fixture-verified) -- this is a defensive
            # backstop, not the primary filtering mechanism, so a way is
            # never materialized into a `points` list for nothing.
            return
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

    def area(self, a: osmium.osm.Area) -> None:
        # `_elements_seen` is deliberately not incremented here -- an area
        # is always derived from a way or relation already counted via
        # `way()`/`relation()` above; counting it again here would
        # double-count `_elements_seen`.
        rings: list[OsmRing] = []
        for outer in a.outer_rings():
            outer_points = [
                (node_ref.location.lat, node_ref.location.lon) for node_ref in outer
            ]
            inner_rings = [
                [(node_ref.location.lat, node_ref.location.lon) for node_ref in inner]
                for inner in a.inner_rings(outer)
            ]
            rings.append(OsmRing(outer=outer_points, inners=inner_rings))
        self._area_buffer.append(
            OsmArea(
                id=a.orig_id(),
                from_way=a.from_way(),
                tags={tag.k: tag.v for tag in a.tags},
                rings=rings,
            )
        )
        self._areas_kept_total += 1
        if len(self._area_buffer) >= self._area_batch_size:
            self._on_areas(self._area_buffer)
            self._area_buffer = []

    def relation(self, r: osmium.osm.Relation) -> None:
        self._elements_seen += 1
        if r.tags.get("type") in _AREA_ASSEMBLED_RELATION_TYPES:
            self.multipolygon_relations_seen += 1
        else:
            self.relations_skipped += 1

    def flush(self) -> None:
        """Flush any leftover partial batch below batch size for nodes,
        ways, and areas -- must be called once after `apply_file` returns,
        or the tail of the file silently vanishes."""
        if self._node_buffer:
            self._on_nodes(self._node_buffer)
            self._node_buffer = []
        if self._way_buffer:
            self._on_ways(self._way_buffer)
            self._way_buffer = []
        if self._area_buffer:
            self._on_areas(self._area_buffer)
            self._area_buffer = []


def stream_features(
    pbf_path: Path,
    on_nodes: Callable[[list[OsmNode]], None],
    on_ways: Callable[[list[OsmWay]], None],
    on_areas: Callable[[list[OsmArea]], None],
    batch_size: int = _INGEST_BATCH_ELEMENTS,
    area_batch_size: int = _INGEST_BATCH_AREAS,
) -> StreamFeaturesResult:
    """Parse one pre-clipped, pre-merged `.osm.pbf` file at `pbf_path`,
    calling `on_nodes`/`on_ways`/`on_areas` with each batch of up to
    `batch_size`/`area_batch_size` kept nodes/ways/areas as they are
    collected -- bounded peak memory, independent of the file's total
    element count, unlike `load_features`'s old accumulate-everything
    behaviour.

    Uses `locations=True, idx="sparse_mem_array"` so pyosmium's C++ side
    resolves way-node geometry inline via a memory-efficient index, not a
    naive Python dict -- see the module docstring. `filters=
    [osmium.filter.KeyFilter(*_CLASSIFIER_TAG_KEYS)]` restricts which
    elements reach the Python callbacks at all -- see the module docstring.

    The `apply_file` call itself is wrapped in a `progress.Heartbeat` --
    see the module docstring's "Progress reporting" for why a heartbeat
    thread is needed here rather than the in-callback throttled logging
    every other stage uses.

    Returns a `StreamFeaturesResult`.
    """
    collector = _FeatureCollector(
        on_nodes, on_ways, on_areas, batch_size, area_batch_size
    )
    key_filter = osmium.filter.KeyFilter(*_CLASSIFIER_TAG_KEYS)

    estimated_total_s = pbf_path.stat().st_size / _PBF_CALIBRATED_BYTES_PER_S
    reporter = ThrottledProgress(
        logger, "osm.pbf", total=estimated_total_s, interval_s=_PROGRESS_LOG_INTERVAL_S
    )
    started_at = time.monotonic()

    def _report() -> None:
        reporter.log(
            done=time.monotonic() - started_at,
            estimated=True,
            **collector.progress_counts(),
        )

    with Heartbeat(_report, interval_s=_PROGRESS_LOG_INTERVAL_S):
        collector.apply_file(
            str(pbf_path), locations=True, idx="sparse_mem_array", filters=[key_filter]
        )
    collector.flush()
    return StreamFeaturesResult(
        relations_skipped=collector.relations_skipped,
        ways_skipped_unresolved_nodes=collector.ways_skipped_unresolved_nodes,
        multipolygon_relations_seen=collector.multipolygon_relations_seen,
    )


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
    areas: list[OsmArea] = []
    result = stream_features(
        pbf_path,
        nodes.extend,
        ways.extend,
        areas.extend,
        batch_size=sys.maxsize,
        area_batch_size=sys.maxsize,
    )
    return OsmFeatureSet(
        nodes=nodes,
        ways=ways,
        areas=areas,
        relations_skipped=result.relations_skipped,
        ways_skipped_unresolved_nodes=result.ways_skipped_unresolved_nodes,
    )
