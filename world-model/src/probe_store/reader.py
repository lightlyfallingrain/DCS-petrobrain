"""Read-only primitives for the probe store.

Every function takes a `schema` parameter (default `"main"`) naming which
attached database's tables to read -- `"main"` for a bare probe-store
connection (as `test_probe_store.py` uses throughout), or the alias a
caller `ATTACH`ed the probe store under on an existing connection (e.g.
`query.describe.describe_position` attaches it as `"probe"` so it can read
both the base store's `main` schema and the probe store's `probe` schema on
one `sqlite3.Connection`, per the plan's ATTACH-based read integration).
This is the one design choice that keeps `store/reader.py` completely
unmodified: nothing here ever needs the base store's reader to become
schema-aware.
"""

import sqlite3
from dataclasses import dataclass

from store.chunks import CHUNK_SIZE_M, chunk_bounds, chunks_covering
from store.models import ElevationGrid

from .models import Chunk, ChunkStatus
from .schema import PROBE_SPACING_M


def chunk_status(
    conn: sqlite3.Connection,
    kind: str,
    chunk_ix: int,
    chunk_iz: int,
    schema: str = "main",
) -> ChunkStatus:
    """Return `(kind, chunk_ix, chunk_iz)`'s coverage status. Never
    `None` -- an absent row means `ChunkStatus.UNQUERIED`, keeping the
    tri-state total at the API surface."""
    row = conn.execute(
        f"SELECT status FROM {schema}.chunk_coverage "
        "WHERE kind = ? AND chunk_ix = ? AND chunk_iz = ?",
        (kind, chunk_ix, chunk_iz),
    ).fetchone()
    if row is None:
        return ChunkStatus.UNQUERIED
    return ChunkStatus(row[0])


def chunks_in_bbox(
    conn: sqlite3.Connection,
    kind: str,
    bbox: tuple[float, float, float, float],
    chunk_size_m: float = CHUNK_SIZE_M,
    schema: str = "main",
) -> list[Chunk]:
    """Return one `Chunk` (status included) for every chunk of `kind`
    whose square overlaps `bbox`, covering the whole `bbox` -- chunks with
    no `chunk_coverage` row come back as `ChunkStatus.UNQUERIED`, never
    omitted."""
    candidates = chunks_covering(bbox, chunk_size_m)
    if not candidates:
        return []
    placeholders = ",".join("(?, ?)" for _ in candidates)
    params: list[object] = [kind]
    for ix, iz in candidates:
        params.extend((ix, iz))
    rows = conn.execute(
        f"SELECT chunk_ix, chunk_iz, status FROM {schema}.chunk_coverage "
        f"WHERE kind = ? AND (chunk_ix, chunk_iz) IN ({placeholders})",
        params,
    ).fetchall()
    statuses = {(row[0], row[1]): ChunkStatus(row[2]) for row in rows}
    return [
        Chunk(
            kind=kind,
            chunk_ix=ix,
            chunk_iz=iz,
            status=statuses.get((ix, iz), ChunkStatus.UNQUERIED),
        )
        for ix, iz in candidates
    ]


@dataclass(frozen=True)
class _GridMeta:
    grid_id: int
    spacing_m: float


def grid_spacing_m(
    conn: sqlite3.Connection, kind: str, schema: str = "main"
) -> float | None:
    """Return the `kind` grid's `spacing_m`, or `None` if no such grid
    exists yet. Mirrors `store.reader.grid_spacing_m`'s naming/shape --
    `query.describe.describe_position` uses this so a probe-answered
    `surface_type.sampled_at_m` reports the probe store's own spacing, not
    the base store's."""
    meta = _load_grid_meta(conn, kind, schema)
    return None if meta is None else meta.spacing_m


def _load_grid_meta(
    conn: sqlite3.Connection, kind: str, schema: str = "main"
) -> _GridMeta | None:
    row = conn.execute(
        f"SELECT id, spacing_m FROM {schema}.grid WHERE kind = ?", (kind,)
    ).fetchone()
    if row is None:
        return None
    return _GridMeta(grid_id=row[0], spacing_m=row[1])


def _grid_cell_value(
    conn: sqlite3.Connection, grid_id: int, row: int, col: int, schema: str = "main"
) -> float | None:
    result = conn.execute(
        f"SELECT value FROM {schema}.grid_sample "
        "WHERE grid_id = ? AND row = ? AND col = ?",
        (grid_id, row, col),
    ).fetchone()
    return None if result is None else float(result[0])


def sample_probe_grid(
    conn: sqlite3.Connection, kind: str, x: float, z: float, schema: str = "main"
) -> float | None:
    """Sample the probe store's single `kind` grid at `(x, z)`, or `None`
    if no such grid exists yet, or if the exact cell it resolves to has
    never been written.

    Deliberately **nearest-cell only**, never bilinear -- unlike
    `store.reader.sample_grid`. The base store's dense, whole-region grid
    can safely interpolate between four always-present neighbours; the
    probe store's grid is sparse by construction (built chunk by chunk),
    so a neighbouring cell being unwritten is the common case, not an edge
    case, and interpolating from a partially-sampled 2x2 window would
    silently fabricate a value between a real probe reading and an absent
    one. `describe_position`'s probe-then-base fallback already lets the
    base store's own (denser) grid answer with real interpolation wherever
    the probe store hasn't been filled in.
    """
    meta = _load_grid_meta(conn, kind, schema)
    if meta is None:
        return None
    row = round(x / meta.spacing_m)
    col = round(z / meta.spacing_m)
    return _grid_cell_value(conn, meta.grid_id, row, col, schema)


def load_chunk_elevation_window(
    conn: sqlite3.Connection,
    chunk_ix: int,
    chunk_iz: int,
    chunk_size_m: float = CHUNK_SIZE_M,
    probe_spacing_m: float = PROBE_SPACING_M,
    schema: str = "main",
) -> ElevationGrid | None:
    """Load a local `ElevationGrid` window covering chunk `(chunk_ix,
    chunk_iz)` plus a **1-cell border on every side**, from the `"elevation"`
    grid -- or `None` if no `"elevation"` grid exists in this store at all.

    The border originally existed so the old per-cell discrete-Laplacian
    `terrain.curvature.classify_curvature`'s full-4-neighbour-window rule
    gave every one of the chunk's own cells a verdict without a feature
    ever bleeding from one chunk's classification into another's stored
    rows (that rule excluded a grid's outermost ring; a 1-cell border made
    the chunk's own interior exactly the classifiable region).

    `terrain-feature-probing`'s marker-controlled-watershed mechanism
    (`build.ingest_terrain.ingest_terrain_chunk`, since removed) replaced
    that per-cell rule and had no equivalent single-ring edge-exclusion
    guarantee. `landform-geomorphons` removed chunk-scoped ridge/valley
    extraction from `build.pipeline.add_probe_chunk` entirely -- its own
    processing unit is a whole SRTM tile with a multi-kilometre margin, not
    a chunk-sized window -- so this function no longer has a terrain
    consumer at all; it is kept as a general-purpose local elevation-
    window accessor (still exercised directly by `tests/test_probe_store.py`)
    in case a future chunk-scoped consumer needs one.

    Border cells that fall in a chunk nobody has probed yet come back as
    `None` samples, same as any other unsampled cell -- never fabricated
    from missing data.
    """
    meta = _load_grid_meta(conn, "elevation", schema)
    if meta is None:
        return None

    min_x, max_x, min_z, max_z = chunk_bounds(chunk_ix, chunk_iz, chunk_size_m)
    r0 = round(min_x / probe_spacing_m) - 1
    r1 = round(max_x / probe_spacing_m) + 1
    c0 = round(min_z / probe_spacing_m) - 1
    c1 = round(max_z / probe_spacing_m) + 1
    n_rows = r1 - r0 + 1
    n_cols = c1 - c0 + 1

    samples: list[list[float | None]] = [[None] * n_cols for _ in range(n_rows)]
    for row, col, value in conn.execute(
        f"SELECT row, col, value FROM {schema}.grid_sample "
        "WHERE grid_id = ? AND row BETWEEN ? AND ? AND col BETWEEN ? AND ?",
        (meta.grid_id, r0, r1, c0, c1),
    ):
        samples[row - r0][col - c0] = float(value)

    return ElevationGrid(
        origin_x=r0 * probe_spacing_m,
        origin_z=c0 * probe_spacing_m,
        spacing_m=probe_spacing_m,
        n_rows=n_rows,
        n_cols=n_cols,
        source_id=None,
        provenance="dcs_probe",
        stats={},
        samples=samples,
    )
