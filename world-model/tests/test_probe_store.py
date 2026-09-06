"""Tests for `probe_store.schema`/`writer`/`reader` -- the M8 probe store.

Covers: schema creation + `open_probe_store`'s create-vs-reopen contract,
the identity-drift detection required by the plan's "Risks & Unknowns",
chunk coverage tri-state semantics, grid sample round-trip (re-upsert
doesn't double cell counts), feature replace-in-place with R*Tree row-count
parity, and the extensibility requirement -- a wholly new raster and vector
`kind`, registered through the exact same generic write/read paths, with no
schema change and no interference with an existing kind's rows or coverage.
"""

from pathlib import Path

import pytest

from probe_store.models import Chunk, ChunkStatus
from probe_store.reader import (
    chunk_status,
    chunks_in_bbox,
    load_chunk_elevation_window,
    sample_probe_grid,
)
from probe_store.schema import PROBE_SCHEMA_VERSION, check_probe_schema_version
from probe_store.writer import (
    insert_source,
    open_probe_store,
    replace_chunk_features,
    upsert_chunk_coverage,
    upsert_grid_samples,
)
from store.models import Source, StoredFeature

_THEATRE = "Syria"
_BASE_SCHEMA_VERSION = 3


def _open(tmp_path: Path, name: str = "region-probe.sqlite") -> object:
    return open_probe_store(tmp_path / name, _THEATRE, _BASE_SCHEMA_VERSION)


def test_open_probe_store_creates_schema_and_meta(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    try:
        check_probe_schema_version(conn)  # must not raise
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row[0] == str(PROBE_SCHEMA_VERSION)
        theatre_row = conn.execute(
            "SELECT value FROM meta WHERE key = 'theatre'"
        ).fetchone()
        assert theatre_row[0] == _THEATRE
    finally:
        conn.close()


def test_open_probe_store_is_not_delete_and_recreate(tmp_path: Path) -> None:
    """Unlike the base store, reopening must preserve prior writes -- the
    probe store accumulates across calls."""
    db_path = tmp_path / "region-probe.sqlite"
    conn1 = open_probe_store(db_path, _THEATRE, _BASE_SCHEMA_VERSION)
    upsert_chunk_coverage(conn1, "elevation", 2, 1, ChunkStatus.QUERIED_WITH_DATA)
    conn1.close()

    conn2 = open_probe_store(db_path, _THEATRE, _BASE_SCHEMA_VERSION)
    try:
        assert chunk_status(conn2, "elevation", 2, 1) == ChunkStatus.QUERIED_WITH_DATA
    finally:
        conn2.close()


def test_open_probe_store_raises_on_theatre_mismatch(tmp_path: Path) -> None:
    db_path = tmp_path / "region-probe.sqlite"
    conn1 = open_probe_store(db_path, _THEATRE, _BASE_SCHEMA_VERSION)
    conn1.close()

    with pytest.raises(ValueError, match="mismatch"):
        open_probe_store(db_path, "Kola", _BASE_SCHEMA_VERSION)


def test_open_probe_store_raises_on_base_schema_version_mismatch(
    tmp_path: Path,
) -> None:
    """The main drift-detection scenario from the plan's 'Risks &
    Unknowns': a probe store paired with a base store rebuilt at a
    different schema version must fail loudly, not silently mis-place
    chunks."""
    db_path = tmp_path / "region-probe.sqlite"
    conn1 = open_probe_store(db_path, _THEATRE, _BASE_SCHEMA_VERSION)
    conn1.close()

    with pytest.raises(ValueError, match="mismatch"):
        open_probe_store(db_path, _THEATRE, _BASE_SCHEMA_VERSION + 1)


def test_open_probe_store_raises_on_chunk_size_or_spacing_mismatch(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "region-probe.sqlite"
    conn1 = open_probe_store(
        db_path, _THEATRE, _BASE_SCHEMA_VERSION, chunk_size_m=5000.0
    )
    conn1.close()

    with pytest.raises(ValueError, match="mismatch"):
        open_probe_store(db_path, _THEATRE, _BASE_SCHEMA_VERSION, chunk_size_m=10000.0)


def test_chunk_status_absent_row_is_unqueried(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    try:
        assert chunk_status(conn, "elevation", 0, 0) == ChunkStatus.UNQUERIED
    finally:
        conn.close()


def test_chunk_status_reports_queried_void_distinct_from_unqueried(
    tmp_path: Path,
) -> None:
    conn = _open(tmp_path)
    try:
        upsert_chunk_coverage(conn, "elevation", 5, 5, ChunkStatus.QUERIED_VOID)
        assert chunk_status(conn, "elevation", 5, 5) == ChunkStatus.QUERIED_VOID
        # A neighbouring, never-probed chunk of the same kind stays unqueried.
        assert chunk_status(conn, "elevation", 6, 5) == ChunkStatus.UNQUERIED
    finally:
        conn.close()


def test_chunk_status_is_scoped_by_kind() -> None:
    """The `kind` component of the coverage key is load-bearing (plan's
    design decision) -- marking `elevation` covered must not mark
    `surface_type` covered for the same chunk."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        conn = open_probe_store(Path(tmp) / "p.sqlite", _THEATRE, _BASE_SCHEMA_VERSION)
        try:
            upsert_chunk_coverage(
                conn, "elevation", 1, 1, ChunkStatus.QUERIED_WITH_DATA
            )
            assert (
                chunk_status(conn, "elevation", 1, 1) == ChunkStatus.QUERIED_WITH_DATA
            )
            assert chunk_status(conn, "surface_type", 1, 1) == ChunkStatus.UNQUERIED
        finally:
            conn.close()


def test_chunks_in_bbox_reports_every_covering_chunk(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    try:
        upsert_chunk_coverage(conn, "elevation", 0, 0, ChunkStatus.QUERIED_WITH_DATA)
        result = chunks_in_bbox(conn, "elevation", (-100.0, 100.0, -100.0, 100.0))
        by_index = {(c.chunk_ix, c.chunk_iz): c.status for c in result}
        assert by_index[(0, 0)] == ChunkStatus.QUERIED_WITH_DATA
        assert by_index[(-1, -1)] == ChunkStatus.UNQUERIED
        assert all(isinstance(c, Chunk) for c in result)
    finally:
        conn.close()


def test_grid_samples_roundtrip(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    try:
        source_id = insert_source(
            conn,
            Source(
                name="terrain_probe chunk",
                fetched_at="2026-09-06T00:00:00+00:00",
                raw_path="chunk_2_1.jsonl",
                attribution="DCS live mission-scripting probe (Eagle Dynamics)",
                notes="",
            ),
        )
        samples = {(100, 50): 123.4, (100, 51): 125.0}
        upsert_grid_samples(conn, "elevation", 100.0, samples, source_id, "dcs_probe")

        assert sample_probe_grid(conn, "elevation", 10000.0, 5000.0) == 123.4
        assert sample_probe_grid(conn, "elevation", 10000.0, 5100.0) == 125.0
        # An un-upserted cell in the same grid stays absent, not fabricated.
        assert sample_probe_grid(conn, "elevation", 10000.0, 5200.0) is None
        # A grid of a different kind never existed at all.
        assert sample_probe_grid(conn, "surface_type", 10000.0, 5000.0) is None
    finally:
        conn.close()


def test_grid_samples_reupsert_replaces_not_doubles(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    try:
        upsert_grid_samples(conn, "elevation", 100.0, {(1, 1): 10.0}, None, "dcs_probe")
        upsert_grid_samples(conn, "elevation", 100.0, {(1, 1): 20.0}, None, "dcs_probe")

        count = conn.execute("SELECT COUNT(*) FROM grid_sample").fetchone()[0]
        assert count == 1
        assert sample_probe_grid(conn, "elevation", 100.0, 100.0) == 20.0
    finally:
        conn.close()


def test_upsert_grid_samples_raises_on_spacing_change(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    try:
        upsert_grid_samples(conn, "elevation", 100.0, {(1, 1): 10.0}, None, "dcs_probe")
        with pytest.raises(ValueError):
            upsert_grid_samples(
                conn, "elevation", 200.0, {(1, 1): 10.0}, None, "dcs_probe"
            )
    finally:
        conn.close()


def _ridge_feature(chunk_ix: int, chunk_iz: int) -> StoredFeature:
    return StoredFeature(
        kind="ridge",
        geom_type="LineString",
        geometry=[
            (chunk_ix * 5000.0 + 100.0, chunk_iz * 5000.0 + 100.0),
            (chunk_ix * 5000.0 + 200.0, chunk_iz * 5000.0 + 200.0),
        ],
        name=None,
        subtype=None,
        tags={"orientation_deg": 45.0},
        source_id=None,
        source_ref="ridge_0",
        provenance={"geometry": "dcs_derived"},
        confidence={"geometry": "low"},
        position_uncertainty_m=100.0,
    )


def test_replace_chunk_features_roundtrip_and_bbox_parity(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    try:
        replace_chunk_features(conn, "ridge", 1, 1, [_ridge_feature(1, 1)])

        feature_count = conn.execute(
            "SELECT COUNT(*) FROM feature WHERE kind = 'ridge' AND chunk_ix = 1 "
            "AND chunk_iz = 1"
        ).fetchone()[0]
        bbox_count = conn.execute("SELECT COUNT(*) FROM feature_bbox").fetchone()[0]
        assert feature_count == 1
        assert bbox_count == 1
    finally:
        conn.close()


def test_replace_chunk_features_replaces_not_accumulates(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    try:
        replace_chunk_features(conn, "ridge", 1, 1, [_ridge_feature(1, 1)])
        replace_chunk_features(conn, "ridge", 1, 1, [_ridge_feature(1, 1)])

        feature_count = conn.execute("SELECT COUNT(*) FROM feature").fetchone()[0]
        bbox_count = conn.execute("SELECT COUNT(*) FROM feature_bbox").fetchone()[0]
        assert feature_count == 1
        assert bbox_count == 1
    finally:
        conn.close()


def test_replace_chunk_features_scoped_by_kind_and_chunk(tmp_path: Path) -> None:
    """Re-probing one kind's chunk must leave another kind's rows (same
    chunk) and another chunk's rows (same kind) untouched."""
    conn = _open(tmp_path)
    try:
        valley = StoredFeature(
            kind="valley",
            geom_type="LineString",
            geometry=[(5100.0, 5100.0), (5200.0, 5200.0)],
            name=None,
            subtype=None,
            tags={},
            source_id=None,
            source_ref="valley_0",
            provenance={"geometry": "dcs_derived"},
            confidence={"geometry": "low"},
            position_uncertainty_m=100.0,
        )
        replace_chunk_features(conn, "ridge", 1, 1, [_ridge_feature(1, 1)])
        replace_chunk_features(conn, "valley", 1, 1, [valley])
        replace_chunk_features(conn, "ridge", 2, 2, [_ridge_feature(2, 2)])

        # Re-probe only ridge/(1,1); the other two rows must survive.
        replace_chunk_features(conn, "ridge", 1, 1, [_ridge_feature(1, 1)])

        total = conn.execute("SELECT COUNT(*) FROM feature").fetchone()[0]
        assert total == 3
    finally:
        conn.close()


def test_replace_chunk_features_raises_on_kind_mismatch(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    try:
        with pytest.raises(ValueError):
            replace_chunk_features(conn, "valley", 1, 1, [_ridge_feature(1, 1)])
    finally:
        conn.close()


def test_load_chunk_elevation_window_none_without_grid(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    try:
        assert load_chunk_elevation_window(conn, 0, 0) is None
    finally:
        conn.close()


def test_load_chunk_elevation_window_shape_and_border(tmp_path: Path) -> None:
    conn = _open(tmp_path)
    try:
        # Probe spacing 100m, chunk size 5000m -> chunk (0, 0) spans grid
        # rows/cols 0..50 inclusive (51 points/side); the window adds a
        # 1-cell border, so it should span rows/cols -1..51 (53 points/side).
        samples = {(25, 25): 111.0, (-1, -1): 5.0, (51, 51): 9.0}
        upsert_grid_samples(conn, "elevation", 100.0, samples, None, "dcs_probe")

        window = load_chunk_elevation_window(conn, 0, 0)
        assert window is not None
        assert window.n_rows == 53
        assert window.n_cols == 53
        assert window.origin_x == -100.0
        assert window.origin_z == -100.0
        # (25, 25) is interior; local index offset by the border row0=-1.
        assert window.samples[25 - (-1)][25 - (-1)] == 111.0
        assert window.samples[0][0] == 5.0
        assert window.samples[52][52] == 9.0
    finally:
        conn.close()


# --- Extensibility test: an invented second raster + vector kind, never
# added to src/, registered through the exact same generic write/read
# paths as elevation/surface_type/ridge/valley. ---

_INVENTED_RASTER_KIND = "test_invented_raster"
_INVENTED_VECTOR_KIND = "test_invented_vector"


def test_extensibility_new_raster_and_vector_kind_need_no_schema_change(
    tmp_path: Path,
) -> None:
    conn = _open(tmp_path)
    try:
        # Raster-shaped: a brand-new grid kind, never named in src/.
        upsert_grid_samples(
            conn, _INVENTED_RASTER_KIND, 100.0, {(3, 3): 42.0}, None, "test_source"
        )
        assert sample_probe_grid(conn, _INVENTED_RASTER_KIND, 300.0, 300.0) == 42.0

        # Vector-shaped: a brand-new feature kind.
        invented_feature = StoredFeature(
            kind=_INVENTED_VECTOR_KIND,
            geom_type="Point",
            geometry=[(4000.0, 4000.0)],
            name="invented",
            subtype=None,
            tags={},
            source_id=None,
            source_ref="invented_0",
            provenance={"geometry": "test"},
            confidence={"geometry": "test"},
            position_uncertainty_m=0.0,
        )
        replace_chunk_features(conn, _INVENTED_VECTOR_KIND, 0, 0, [invented_feature])

        # Coverage tracked independently, per kind.
        upsert_chunk_coverage(
            conn, _INVENTED_RASTER_KIND, 0, 0, ChunkStatus.QUERIED_WITH_DATA
        )
        upsert_chunk_coverage(
            conn, _INVENTED_VECTOR_KIND, 0, 0, ChunkStatus.QUERIED_VOID
        )
        assert (
            chunk_status(conn, _INVENTED_RASTER_KIND, 0, 0)
            == ChunkStatus.QUERIED_WITH_DATA
        )
        assert (
            chunk_status(conn, _INVENTED_VECTOR_KIND, 0, 0) == ChunkStatus.QUERIED_VOID
        )
        # Untouched real kinds stay unqueried -- no cross-kind bleed.
        assert chunk_status(conn, "elevation", 0, 0) == ChunkStatus.UNQUERIED

        # Re-probing the invented raster kind leaves the invented vector
        # kind's rows and coverage untouched.
        upsert_grid_samples(
            conn, _INVENTED_RASTER_KIND, 100.0, {(3, 3): 99.0}, None, "test_source"
        )
        feature_count = conn.execute(
            "SELECT COUNT(*) FROM feature WHERE kind = ?", (_INVENTED_VECTOR_KIND,)
        ).fetchone()[0]
        assert feature_count == 1
        assert (
            chunk_status(conn, _INVENTED_VECTOR_KIND, 0, 0) == ChunkStatus.QUERIED_VOID
        )

        # No table/column named after either invented kind exists --
        # confirmed by construction (same generic `grid`/`feature` tables),
        # spot-checked here via a schema introspection query.
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert not any(_INVENTED_RASTER_KIND in name for name in table_names)
        assert not any(_INVENTED_VECTOR_KIND in name for name in table_names)
    finally:
        conn.close()
