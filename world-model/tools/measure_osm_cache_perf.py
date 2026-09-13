#!/usr/bin/env python3
"""osm-classified-cache Implementation Plan step 6: performance sanity for
the cache-hit fast path's batched-copy loop -- **not** a real `syria-full`
build (per the plan's Execution boundary, that stays the user's own job, see
`docs/M9_OSM_RUN_INSTRUCTIONS.md`'s precedent).

Builds a synthetic ~100k-row OSM cache (entirely local and disposable, a
`tempfile.TemporaryDirectory`) via the real `osm_cache.writer` primitives,
then times the exact loop `build.pipeline`'s cache-hit branch runs: read
cached feature batches (`osm_cache.reader.iter_cached_features`), retag each
batch's `source_id`, and insert it into a fresh base store via
`store.writer.insert_features` -- establishing this path's per-row cost so
the user has an order-of-magnitude expectation before running a real
cache-hit `syria-full` rebuild.

Prints one JSON object to stdout.

    .venv/bin/python tools/measure_osm_cache_perf.py
"""

import json
import sqlite3
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from build.ingest_osm import OsmIngestStats
from osm_cache.models import OsmCacheMeta
from osm_cache.paths import osm_cache_store_path, osm_cache_tmp_path
from osm_cache.reader import iter_cached_features
from osm_cache.writer import (
    finalize_cache,
    insert_cached_features,
    open_osm_cache_for_populate,
)
from store.models import StoredFeature
from store.writer import insert_features, open_for_build

_N_FEATURES = 100_000
_READ_BATCH_SIZE = 50_000
_WRITE_BATCH_SIZE = 5_000

_META = OsmCacheMeta(
    pbf_sha256="0" * 64,
    pbf_size_bytes=0,
    classifier_version=1,
    cache_schema_version=1,
    region_name="osm-cache-perf-region",
    centre_x=0.0,
    centre_z=0.0,
    half_extent_x_m=1000.0,
    half_extent_z_m=1000.0,
    built_at="2026-01-01T00:00:00+00:00",
)


@dataclass(frozen=True)
class OsmCachePerfReport:
    n_features: int
    populate_cache_ms: float
    fast_path_copy_ms: float
    fast_path_copy_features_per_s: float


def _synthetic_features(n: int) -> list[StoredFeature]:
    """`n` plausible `road` features, varied enough (distinct `source_ref`/
    geometry) to be a realistic write/read workload rather than one
    degenerate repeated row."""
    features = []
    for i in range(n):
        x = float(i % 1000)
        z = float(i // 1000)
        features.append(
            StoredFeature(
                kind="road",
                geom_type="LineString",
                geometry=[(x, z), (x + 1.0, z + 1.0)],
                name=None,
                subtype="residential",
                tags={"highway": "residential"},
                source_id=None,
                source_ref=f"way/{i}",
                provenance={"geometry": "osm", "name": "osm"},
                confidence={"geometry": "medium", "name": "medium"},
                position_uncertainty_m=1300.0,
            )
        )
    return features


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        base_path = tmp_path / "osm-cache-perf-region.sqlite"
        cache_path = osm_cache_store_path(base_path)
        cache_tmp_path = osm_cache_tmp_path(base_path)

        features = _synthetic_features(_N_FEATURES)

        start = time.monotonic()
        populate_conn = open_osm_cache_for_populate(cache_tmp_path)
        for i in range(0, len(features), _WRITE_BATCH_SIZE):
            insert_cached_features(populate_conn, features[i : i + _WRITE_BATCH_SIZE])
        finalize_cache(
            populate_conn,
            cache_tmp_path,
            cache_path,
            _META,
            OsmIngestStats(roads=_N_FEATURES),
        )
        populate_cache_ms = (time.monotonic() - start) * 1000.0

        # Fast-path copy: read cached batches, retag, insert into a fresh
        # base store -- the exact loop `build.pipeline`'s cache-hit branch
        # runs.
        base_conn = open_for_build(base_path)
        cache_conn = sqlite3.connect(f"file:{cache_path}?mode=ro", uri=True)
        start = time.monotonic()
        try:
            for batch in iter_cached_features(cache_conn, _READ_BATCH_SIZE):
                retagged = [replace(f, source_id=1) for f in batch]
                insert_features(base_conn, retagged)
        finally:
            cache_conn.close()
            base_conn.close()
        fast_path_copy_ms = (time.monotonic() - start) * 1000.0

        report = OsmCachePerfReport(
            n_features=_N_FEATURES,
            populate_cache_ms=populate_cache_ms,
            fast_path_copy_ms=fast_path_copy_ms,
            fast_path_copy_features_per_s=_N_FEATURES / (fast_path_copy_ms / 1000.0),
        )
        print(json.dumps(asdict(report), indent=2))


if __name__ == "__main__":
    main()
