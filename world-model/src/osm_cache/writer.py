"""Write-side primitives for the OSM classified-feature cache.

**Atomicity contract** ("no corrupt half-populated cache" requirement, see
`plans/osm-classified-cache/plan.md`'s "Invalidation & atomicity"): a cache
is populated at `osm_cache_tmp_path(base_db_path)` throughout the whole
streaming pass and is only renamed to its canonical path -- via
`os.replace`, one atomic filesystem operation -- inside `finalize_cache`,
called once after the streaming pass returns successfully. If the caller's
process dies or raises at any point before `finalize_cache` runs, the
`.tmp` file is simply abandoned: nothing exists yet at the canonical path,
so the next build correctly sees "no cache" and falls through to a full
rebuild. No flag column, no "is this valid" query -- the file's *existence
at its canonical path* is the validity signal, matching this project's
absence-as-absence convention.
"""

import json
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path

from build.ingest_osm import OsmIngestStats
from store.models import StoredFeature

from .models import OsmCacheMeta
from .schema import META_FIELDS, STATS_META_KEY, create_osm_cache_schema


def open_osm_cache_for_populate(tmp_path: Path) -> sqlite3.Connection:
    """Open a fresh cache-population connection at `tmp_path`, creating the
    schema on an empty file. Deletes any stray `.tmp` file left over from a
    prior interrupted run first -- that leftover is disk-usage noise, never
    a correctness hazard (see the module docstring), but starting a new
    population on top of a half-written file's tables would raise on the
    `CREATE TABLE` below. Creates parent directories as needed."""
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    if tmp_path.exists():
        tmp_path.unlink()
    conn = sqlite3.connect(tmp_path)
    create_osm_cache_schema(conn)
    return conn


def insert_cached_features(
    conn: sqlite3.Connection, features: list[StoredFeature]
) -> None:
    """Insert one batch of already-classified `features` into the cache
    under population at `conn`. No bbox row (the cache has no
    `feature_bbox` table -- see `schema.py`'s module docstring) and no
    `source_id` (a cache outlives any one build's `source` rows; the
    fast-path reader always retags cached rows with the *current* build's
    own `source_id`, see `build.pipeline`'s cache-hit branch)."""
    for feature in features:
        conn.execute(
            "INSERT INTO feature "
            "(kind, geom_type, geom_json, name, subtype, tags_json, "
            " source_ref, provenance_json, confidence_json, "
            " position_uncertainty_m) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
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
    conn.commit()


def finalize_cache(
    conn: sqlite3.Connection,
    tmp_path: Path,
    final_path: Path,
    meta: OsmCacheMeta,
    stats: OsmIngestStats,
) -> None:
    """Write `meta`'s identity fields and `stats` (serialized) into `conn`'s
    `meta` table, close `conn`, then atomically publish the populated
    `.tmp` file to `final_path` via `os.replace`.

    This is the **only** function that makes a cache visible/valid at its
    canonical path -- see the module docstring. Must only be called after
    the caller's full streaming pass over the source `.osm.pbf` has
    completed without error; a caller that raises before reaching this
    call correctly leaves no file at `final_path`.
    """
    values = {name: getattr(meta, name) for name in META_FIELDS}
    conn.executemany(
        "INSERT INTO meta (key, value) VALUES (?, ?)",
        [(key, str(value)) for key, value in values.items()],
    )
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?)",
        (STATS_META_KEY, json.dumps(asdict(stats))),
    )
    conn.commit()
    conn.close()
    os.replace(tmp_path, final_path)
