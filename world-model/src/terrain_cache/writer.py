"""Write-side primitives for the terrain-extraction cache.

**Atomicity contract** -- see `schema.py`'s module docstring for why this
differs from `osm_cache.writer`'s rename-at-the-end pattern: every write
here happens inside its own SQLite transaction, committed before the
function returns, directly against the cache's canonical file. A crash
mid-tile rolls that tile's own transaction back entirely (SQLite's
guarantee); on reopen, that tile is simply absent from `tile` and gets
reprocessed -- no `.tmp` file, no separate resume-state, the cache *is*
the resume state.
"""

import json
import sqlite3
from pathlib import Path

from store.models import StoredFeature

from .models import TerrainCacheMeta
from .schema import BUILD_COMPLETE_KEY, META_FIELDS, create_terrain_cache_schema


def open_terrain_cache(path: Path) -> sqlite3.Connection:
    """Open the cache at `path`, creating the schema if `path` doesn't
    exist yet (a brand-new cache) or is empty. Does **not** create parent
    directories by itself beyond what `sqlite3.connect` already does for
    an existing directory -- callers build caches as a sibling of an
    already-creatable base store path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    conn = sqlite3.connect(path)
    if is_new:
        create_terrain_cache_schema(conn)
    return conn


def reset_terrain_cache(path: Path) -> sqlite3.Connection:
    """Delete any existing cache at `path` and open a fresh, schema-only
    one -- the "any identity mismatch -> full rebuild, never partial
    reuse" step (`models.py`'s docstring)."""
    if path.exists():
        path.unlink()
    return open_terrain_cache(path)


def write_meta(conn: sqlite3.Connection, meta: TerrainCacheMeta) -> None:
    """Replace `conn`'s `meta` identity rows (and reset `build_complete`
    to `0`) with `meta`'s own fields -- called once, right after a fresh
    or reset cache is opened, before any tile is processed."""
    values = {name: getattr(meta, name) for name in META_FIELDS}
    conn.execute("DELETE FROM meta")
    conn.executemany(
        "INSERT INTO meta (key, value) VALUES (?, ?)",
        [(key, str(value)) for key, value in values.items()],
    )
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?)", (BUILD_COMPLETE_KEY, "0")
    )
    conn.commit()


def write_tile_features(
    conn: sqlite3.Connection, tile_id: str, features: list[StoredFeature]
) -> None:
    """Insert `tile_id`'s `features` and mark it `"complete"` in one
    transaction -- the per-tile durability unit `schema.py`'s module
    docstring describes. Safe to call again for a `tile_id` already
    marked complete (e.g. a forced reprocess): deletes that tile's own
    prior rows first, so no duplicate features accumulate."""
    conn.execute("DELETE FROM feature WHERE tile_id = ?", (tile_id,))
    conn.execute("DELETE FROM tile WHERE tile_id = ?", (tile_id,))
    for feature in features:
        conn.execute(
            "INSERT INTO feature "
            "(tile_id, kind, geom_type, geom_json, name, subtype, tags_json, "
            " source_ref, provenance_json, confidence_json, "
            " position_uncertainty_m) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tile_id,
                feature.kind,
                feature.geom_type,
                json.dumps([list(p) for p in feature.geometry]),
                feature.name,
                feature.subtype,
                json.dumps(feature.tags),
                feature.source_ref,
                json.dumps(feature.provenance),
                json.dumps(feature.confidence),
                feature.position_uncertainty_m,
            ),
        )
    conn.execute(
        "INSERT INTO tile (tile_id, status, feature_count) VALUES (?, 'complete', ?)",
        (tile_id, len(features)),
    )
    conn.commit()


def mark_build_complete(conn: sqlite3.Connection) -> None:
    """Set `build_complete=1` in its own tiny final transaction, once
    every planned tile has a `complete` row -- the only thing a reader may
    treat as permission for the OSM-cache-style whole-pass fast path."""
    conn.execute("UPDATE meta SET value = '1' WHERE key = ?", (BUILD_COMPLETE_KEY,))
    conn.commit()
