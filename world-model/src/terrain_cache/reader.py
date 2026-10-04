"""Read-side primitives for the terrain-extraction cache."""

import json
import sqlite3
from typing import Any

from store.models import StoredFeature

from .models import TerrainCacheMeta
from .schema import BUILD_COMPLETE_KEY, META_FIELDS

_META_TYPES: dict[str, type] = {
    "dem_identity": str,
    "extractor_version": int,
    "cache_schema_version": int,
    "region_name": str,
    "centre_x": float,
    "centre_z": float,
    "half_extent_x_m": float,
    "half_extent_z_m": float,
    "spacing_m": float,
    "margin_cells": int,
    "lookup_cells": int,
    "flat_deg": float,
    "close_iterations": int,
    "max_turn_cos": float,
    "min_line_length_cells": int,
    "chaikin_iterations": int,
    "min_relief_m": float,
    "decimation_tolerance_fraction": float,
    "built_at": str,
}


def load_cache_meta(conn: sqlite3.Connection) -> TerrainCacheMeta | None:
    """Return the cache's `TerrainCacheMeta`, or `None` if `conn`'s `meta`
    table is empty -- a freshly schema'd cache with no identity written
    yet (absence-as-absence, same convention `osm_cache.reader.
    load_cache_meta` uses for a missing file; here the file always exists
    once opened, so the "nothing written" state is checked via the table
    instead)."""
    values: dict[str, Any] = {}
    for key in META_FIELDS:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        values[key] = _META_TYPES[key](row[0])
    return TerrainCacheMeta(**values)


def is_build_complete(conn: sqlite3.Connection) -> bool:
    """`True` iff `writer.mark_build_complete` has run against this exact
    cache's current contents -- the **only** signal that permits treating
    this cache as a whole-pass fast path (`models.py`'s module docstring);
    an absent row (schema-only cache) is `False`, not an error."""
    row = conn.execute(
        "SELECT value FROM meta WHERE key = ?", (BUILD_COMPLETE_KEY,)
    ).fetchone()
    return row is not None and row[0] == "1"


def completed_tile_ids(conn: sqlite3.Connection) -> set[str]:
    """Every `tile_id` already marked `"complete"` -- what a resumed
    build skips reprocessing."""
    rows = conn.execute("SELECT tile_id FROM tile WHERE status = 'complete'").fetchall()
    return {row[0] for row in rows}


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


def load_tile_features(conn: sqlite3.Connection, tile_id: str) -> list[StoredFeature]:
    """Every cached `feature` row for `tile_id`, in insertion order.
    `source_id`/`id` come back `None` -- the caller retags each with the
    current build's own `source_id` before `store.writer.insert_features`,
    which assigns fresh ids (same contract `osm_cache.reader.
    iter_cached_features` already has)."""
    cursor = conn.execute(
        "SELECT kind, geom_type, geom_json, name, subtype, tags_json, "
        "source_ref, provenance_json, confidence_json, position_uncertainty_m "
        "FROM feature WHERE tile_id = ? ORDER BY id",
        (tile_id,),
    )
    return [_row_to_feature(row) for row in cursor.fetchall()]


def load_all_features(conn: sqlite3.Connection) -> list[StoredFeature]:
    """Every cached `feature` row across every tile, in insertion order --
    the whole-pass fast path a `build_complete=1` cache permits
    (`is_build_complete`)."""
    cursor = conn.execute(
        "SELECT kind, geom_type, geom_json, name, subtype, tags_json, "
        "source_ref, provenance_json, confidence_json, position_uncertainty_m "
        "FROM feature ORDER BY id"
    )
    return [_row_to_feature(row) for row in cursor.fetchall()]
