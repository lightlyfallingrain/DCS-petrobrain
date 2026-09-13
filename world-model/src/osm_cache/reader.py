"""Read-only primitives for the OSM classified-feature cache.

Every function here takes a path or connection to the cache's canonical
file only -- a caller must have already confirmed the file exists at that
path (i.e. it was fully populated and published by `writer.finalize_cache`)
before calling anything except `load_cache_meta`, which is the one function
safe to call against a path that may not exist at all (see its docstring).
"""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from build.ingest_osm import OsmIngestStats
from store.models import StoredFeature

from .models import OsmCacheMeta
from .schema import META_FIELDS, STATS_META_KEY

_META_TYPES: dict[str, type] = {
    "pbf_sha256": str,
    "pbf_size_bytes": int,
    "classifier_version": int,
    "cache_schema_version": int,
    "region_name": str,
    "centre_x": float,
    "centre_z": float,
    "half_extent_x_m": float,
    "half_extent_z_m": float,
    "built_at": str,
}


def load_cache_meta(path: Path) -> OsmCacheMeta | None:
    """Return the cache's `OsmCacheMeta`, or `None` if `path` does not
    exist -- absence-as-absence, this project's standing convention for "no
    cache yet" (never an error). A file that exists but is missing a
    required meta key raises `ValueError`, since that means the cache is
    not a `finalize_cache`-published file at all."""
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        values: dict[str, Any] = {}
        for key in META_FIELDS:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                raise ValueError(
                    f"OSM cache {path} has no {key!r} meta row -- not a "
                    "valid finalize_cache-published cache"
                )
            values[key] = _META_TYPES[key](row[0])
        return OsmCacheMeta(**values)
    finally:
        conn.close()


def load_cached_stats(conn: sqlite3.Connection) -> OsmIngestStats:
    """Return the `OsmIngestStats` recorded by `writer.finalize_cache` --
    the already-correct aggregate counts from the build that populated this
    cache, not recomputed from the cached rows."""
    row = conn.execute(
        "SELECT value FROM meta WHERE key = ?", (STATS_META_KEY,)
    ).fetchone()
    if row is None:
        raise ValueError(
            "OSM cache has no stored OsmIngestStats meta row -- not a "
            "valid finalize_cache-published cache"
        )
    return OsmIngestStats(**json.loads(row[0]))


def _row_to_feature(row: tuple[Any, ...]) -> StoredFeature:
    (
        kind,
        geom_type,
        geom_json,
        name,
        subtype,
        tags_json,
        source_ref,
        provenance_json,
        confidence_json,
        position_uncertainty_m,
    ) = row
    return StoredFeature(
        kind=kind,
        geom_type=geom_type,
        geometry=[(x, z) for x, z in json.loads(geom_json)],
        name=name,
        subtype=subtype,
        tags=json.loads(tags_json),
        source_id=None,
        source_ref=source_ref,
        provenance=json.loads(provenance_json),
        confidence=json.loads(confidence_json),
        position_uncertainty_m=position_uncertainty_m,
        id=None,
    )


def iter_cached_features(
    conn: sqlite3.Connection, batch_size: int
) -> Iterator[list[StoredFeature]]:
    """Yield the cache's `feature` rows as `StoredFeature` batches of up to
    `batch_size`, ordered by `id` (insertion order) so results are
    deterministic across repeated reads. `source_id`/`id` come back `None`
    -- the caller (`build.pipeline`'s cache-hit fast path) retags each
    batch with the current build's own `source_id` before handing it to
    `store.writer.insert_features`, which assigns fresh ids."""
    cursor = conn.execute(
        "SELECT kind, geom_type, geom_json, name, subtype, tags_json, "
        "source_ref, provenance_json, confidence_json, position_uncertainty_m "
        "FROM feature ORDER BY id"
    )
    while rows := cursor.fetchmany(batch_size):
        yield [_row_to_feature(row) for row in rows]
