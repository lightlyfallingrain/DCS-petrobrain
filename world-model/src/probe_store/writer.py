"""Write-side primitives for the probe store.

Every function here operates on a **direct connection to the probe store
only** -- never one with the base store `ATTACH`ed -- so a chunk write is
physically incapable of touching base data (see the plan's "Storage
architecture" point 2). Every write is scoped by `kind`, so re-probing one
kind's chunk never disturbs another kind's rows or coverage (the plan's
"Idempotency scope").
"""

import datetime
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path

from geometry import bbox_of
from store.chunks import CHUNK_SIZE_M
from store.models import Source, StoredFeature

from .models import ChunkStatus
from .schema import PROBE_SPACING_M, check_probe_schema_version, create_probe_schema

_META_KEYS = ("theatre", "chunk_size_m", "probe_spacing_m", "base_schema_version")


def open_probe_store(
    db_path: Path,
    theatre: str,
    base_schema_version: int,
    chunk_size_m: float = CHUNK_SIZE_M,
    probe_spacing_m: float = PROBE_SPACING_M,
) -> sqlite3.Connection:
    """Open the probe store at `db_path`, creating it (schema + identity
    meta rows) on first use.

    Unlike `store.writer.open_for_build`, this is **not**
    delete-and-recreate -- the probe store accumulates across calls, and a
    prior call's chunks must survive this one. Creates parent directories
    as needed.

    If `db_path` already exists, its recorded `PROBE_SCHEMA_VERSION` and
    identity meta (`theatre`, `chunk_size_m`, `probe_spacing_m`,
    `base_schema_version`) must agree with what is being requested here --
    this is the drift-detection contract from the plan's "Risks &
    Unknowns": a probe store paired with a base store built at a different
    extent/schema must fail loudly, not silently mis-place chunks. Raises
    `ValueError` on any mismatch.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not db_path.exists()
    conn = sqlite3.connect(db_path)

    requested = {
        "theatre": theatre,
        "chunk_size_m": repr(chunk_size_m),
        "probe_spacing_m": repr(probe_spacing_m),
        "base_schema_version": str(base_schema_version),
    }

    if is_new:
        create_probe_schema(conn)
        conn.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            list(requested.items()),
        )
        conn.commit()
        return conn

    check_probe_schema_version(conn)
    stored: dict[str, str] = {}
    for key in _META_KEYS:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row is not None:
            stored[key] = str(row[0])
    mismatches = {
        key: (stored.get(key), requested[key])
        for key in _META_KEYS
        if stored.get(key) != requested[key]
    }
    if mismatches:
        conn.close()
        raise ValueError(
            f"Probe store {db_path} identity mismatch (stored vs requested): "
            f"{mismatches!r} -- a probe store must never be paired with a "
            "base store or chunk lattice it was not created against"
        )
    return conn


def insert_source(conn: sqlite3.Connection, source: Source) -> int:
    """Insert a `Source` row into the probe store and return its id.
    Identical shape to `store.writer.insert_source`, duplicated rather than
    imported because the two write to structurally identical but distinct
    `source` tables in different files."""
    cursor = conn.execute(
        "INSERT INTO source (name, fetched_at, raw_path, attribution, notes) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            source.name,
            source.fetched_at,
            source.raw_path,
            source.attribution,
            source.notes,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    assert row_id is not None
    return row_id


def upsert_chunk_coverage(
    conn: sqlite3.Connection,
    kind: str,
    chunk_ix: int,
    chunk_iz: int,
    status: ChunkStatus,
    updated_at: str | None = None,
) -> None:
    """Record `(kind, chunk_ix, chunk_iz)`'s coverage as `status`,
    overwriting any prior status for that exact key (a chunk can be
    re-probed)."""
    if updated_at is None:
        updated_at = datetime.datetime.now(datetime.UTC).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO chunk_coverage "
        "(kind, chunk_ix, chunk_iz, status, updated_at) VALUES (?, ?, ?, ?, ?)",
        (kind, chunk_ix, chunk_iz, status.value, updated_at),
    )
    conn.commit()


def _ensure_grid(
    conn: sqlite3.Connection,
    kind: str,
    spacing_m: float,
    source_id: int | None,
    provenance: str,
) -> int:
    """Return the single `grid.id` for `kind`, creating it (anchored at
    the DCS origin `(0, 0)`, per the theatre-anchored chunk lattice --
    see `store.chunks`'s module docstring) if it does not already exist.

    Raises `ValueError` if a `grid` row for `kind` already exists with a
    different `spacing_m` -- changing spacing is documented as a
    "discard and re-probe" event (see the plan's "Risks & Unknowns"), never
    a silent grid mutation.
    """
    row = conn.execute(
        "SELECT id, spacing_m FROM grid WHERE kind = ?", (kind,)
    ).fetchone()
    if row is not None:
        grid_id, existing_spacing_m = row
        if existing_spacing_m != spacing_m:
            raise ValueError(
                f"grid kind={kind!r} already exists at spacing_m="
                f"{existing_spacing_m}, cannot upsert at spacing_m={spacing_m} "
                "-- changing probe spacing is a discard-and-re-probe event"
            )
        return int(grid_id)

    cursor = conn.execute(
        "INSERT INTO grid (kind, origin_x, origin_z, spacing_m, source_id, "
        "provenance, stats_json) VALUES (?, 0.0, 0.0, ?, ?, ?, ?)",
        (kind, spacing_m, source_id, provenance, "{}"),
    )
    grid_id = cursor.lastrowid
    assert grid_id is not None
    return grid_id


def upsert_grid_samples(
    conn: sqlite3.Connection,
    kind: str,
    spacing_m: float,
    samples: Mapping[tuple[int, int], float],
    source_id: int | None,
    provenance: str,
) -> int:
    """Ensure a `grid` row exists for `kind` (`UNIQUE(kind)` keeps this to
    exactly one grid per kind), then upsert `samples` -- `(row, col) ->
    value`, global grid indices anchored at the DCS origin, i.e. `row =
    round(x / spacing_m)` -- as `grid_sample` cells via a single
    `executemany` batch. Returns the grid's id.

    Re-upserting the same `(row, col)` replaces its value (`INSERT OR
    REPLACE`); this is the mechanism `store.reader`'s round-trip test
    exercises to confirm re-probing a chunk doesn't double its cell count.
    """
    grid_id = _ensure_grid(conn, kind, spacing_m, source_id, provenance)
    conn.executemany(
        "INSERT OR REPLACE INTO grid_sample (grid_id, row, col, value) "
        "VALUES (?, ?, ?, ?)",
        [(grid_id, row, col, value) for (row, col), value in samples.items()],
    )
    conn.commit()
    return grid_id


def replace_chunk_features(
    conn: sqlite3.Connection,
    kind: str,
    chunk_ix: int,
    chunk_iz: int,
    features: list[StoredFeature],
) -> None:
    """Replace every `feature` row of `kind` in chunk `(chunk_ix,
    chunk_iz)` with `features`, in one transaction, taking the
    `feature_bbox` R*Tree rows with it -- deleting a `feature` row without
    its `feature_bbox` counterpart would orphan a bbox hit whose `feature`
    join then fails (see the plan's "Risks & Unknowns"). Re-probing kind
    `X` for this chunk never touches another kind's rows, nor this chunk's
    rows of another kind, nor another chunk's rows of this same kind.

    Raises `ValueError` if any `feature.kind` disagrees with `kind`, or if
    a feature has empty geometry (bbox undefined) -- mirroring
    `store.writer.insert_features`'s same guard.
    """
    existing_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM feature WHERE kind = ? AND chunk_ix = ? AND chunk_iz = ?",
            (kind, chunk_ix, chunk_iz),
        )
    ]
    if existing_ids:
        placeholders = ",".join("?" for _ in existing_ids)
        conn.execute(
            f"DELETE FROM feature_bbox WHERE id IN ({placeholders})", existing_ids
        )
        conn.execute(f"DELETE FROM feature WHERE id IN ({placeholders})", existing_ids)

    for feature in features:
        if feature.kind != kind:
            raise ValueError(
                f"replace_chunk_features(kind={kind!r}, ...) received a "
                f"feature of kind={feature.kind!r}"
            )
        if not feature.geometry:
            raise ValueError(
                f"Cannot insert feature (kind={feature.kind!r}, "
                f"name={feature.name!r}) with empty geometry"
            )
        cursor = conn.execute(
            "INSERT INTO feature "
            "(kind, chunk_ix, chunk_iz, geom_type, geom_json, name, subtype, "
            " tags_json, source_id, source_ref, provenance_json, "
            " confidence_json, position_uncertainty_m) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                feature.kind,
                chunk_ix,
                chunk_iz,
                feature.geom_type,
                json.dumps([list(p) for p in feature.geometry]),
                feature.name,
                feature.subtype,
                json.dumps(feature.tags),
                feature.source_id,
                feature.source_ref,
                json.dumps(feature.provenance),
                json.dumps(feature.confidence),
                feature.position_uncertainty_m,
            ),
        )
        feature_id = cursor.lastrowid
        assert feature_id is not None

        min_x, max_x, min_z, max_z = bbox_of(feature.geometry)
        conn.execute(
            "INSERT INTO feature_bbox (id, min_x, max_x, min_z, max_z) "
            "VALUES (?, ?, ?, ?, ?)",
            (feature_id, min_x, max_x, min_z, max_z),
        )
    conn.commit()
