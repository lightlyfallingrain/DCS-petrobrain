"""Tests for M8's `build.pipeline.add_probe_chunk` and its supporting
`build.ingest_probe.ingest_probe_chunk` -- driven entirely by a synthetic
fixture probe output file, never live DCS, mirroring how M7 verified
pipeline code against fixtures (per `plans/m8-incremental-store/plan.md`'s
Implementation Plan step 4).

`ingest_terrain_chunk` (and the chunk-scoped ridge/valley extraction it
powered) no longer exists -- `landform-geomorphons` replaced the
watershed mechanism it was part of with one whose own processing unit is
a whole SRTM tile, not a probe chunk, and did not design a chunk-scoped
equivalent (see `build.pipeline.add_probe_chunk`'s own docstring). Tests
that asserted specific ridge/valley extraction results from a chunk are
rewritten below to assert the new, honest behaviour instead:
`terrain_skipped=True`/`terrain_stats=None` always, and `"ridge"`/
`"valley"` chunk coverage staying `UNQUERIED`.

`chunk_size_m=200.0`/`probe_spacing_m=100.0` (a 3x3 = 9-point chunk) are
used here instead of the locked production defaults (5,000 m / 100 m, a
2,601-point chunk) -- a fixture this small keeps the test readable while
exercising the exact same code paths; the locked defaults are `store.
chunks.CHUNK_SIZE_M`/`probe_store.schema.PROBE_SPACING_M`'s own concern,
already covered by `test_store_chunks.py`.
"""

import json
from pathlib import Path

import pytest

from build.pipeline import add_probe_chunk, build_region
from build.region import RegionDefinition
from probe_store.models import ChunkStatus
from probe_store.paths import probe_store_path
from probe_store.reader import chunk_status, sample_probe_grid
from probe_store.writer import open_probe_store
from store.chunks import chunk_index_for
from store.reader import load_only_region
from store.schema import SCHEMA_VERSION

_TEST_REGION = RegionDefinition.square(
    theatre="Syria",
    name="test-probe-chunk-region",
    centre_x=1100.0,
    centre_z=1100.0,
    half_extent_m=5000.0,
)
_CHUNK_SIZE_M = 200.0
_PROBE_SPACING_M = 100.0


@pytest.fixture(autouse=True)
def _patch_parsers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("build.pipeline.parse_towns_lua", lambda path: [])
    monkeypatch.setattr("build.pipeline.parse_beacons_lua", lambda path: [])


def _build_base(tmp_path: Path) -> Path:
    out_path = tmp_path / "test-probe-chunk-region.sqlite"
    build_region(
        _TEST_REGION,
        towns_lua_path=Path("unused-towns.lua"),
        beacons_lua_path=Path("unused-beacons.lua"),
        osm_cache_path=None,
        out_path=out_path,
    )
    return out_path


def _write_probe_fixture(
    path: Path, points: list[tuple[float, float, float]], surface_type: int = 1
) -> None:
    with path.open("w", encoding="utf-8") as f:
        for i, (x, z, height_m) in enumerate(points):
            f.write(
                json.dumps(
                    {
                        "name": f"p{i}",
                        "x": x,
                        "z": z,
                        "height_m": height_m,
                        "surface_type": surface_type,
                    }
                )
                + "\n"
            )


# A single low cell at the chunk's own centre (1100, 1100), surrounded by
# higher cells on all four sides -- a small, real (non-flat) elevation
# grid for the grid-ingestion tests below. No longer read by any terrain
# extraction (see this module's own docstring).
_VALLEY_CHUNK_POINTS = [
    (1000.0, 1000.0, 10.0),
    (1000.0, 1100.0, 10.0),
    (1000.0, 1200.0, 10.0),
    (1100.0, 1000.0, 10.0),
    (1100.0, 1100.0, -190.0),
    (1100.0, 1200.0, 10.0),
    (1200.0, 1000.0, 10.0),
    (1200.0, 1100.0, 10.0),
    (1200.0, 1200.0, 10.0),
]


# A larger (19x19) double-V elevation profile -- kept from the
# watershed-era fixture set as a nontrivial, non-flat grid-ingestion
# exercise for `test_add_probe_chunk_ingests_grids_but_no_longer_extracts_
# terrain` below, even though no terrain extraction reads it any more.
# `_RIDGE_CHUNK_COLS` is replicated across every row for a uniform-along-z
# structure.
#
# `_RIDGE_CHUNK_SIZE_M` (2000, not 1800) is deliberately wider than the
# 19-point profile's own 0-1800 m span: `store.chunks.chunk_bounds` is
# half-open (`[ix*size, (ix+1)*size)`), so a profile spanning exactly
# 0-1800 at a 1800 m chunk size would place its own rightmost point
# (x=1800) in the *next* chunk, tripping `ingest_probe.ingest_probe_chunk`'s
# "outside chunk" guard -- confirmed by hitting that guard before widening
# the chunk.
_RIDGE_CHUNK_COLS = [
    400.0,
    350.0,
    300.0,
    250.0,
    200.0,
    150.0,
    100.0,
    50.0,
    0.0,
    50.0,
    100.0,
    150.0,
    300.0,
    150.0,
    100.0,
    50.0,
    0.0,
    50.0,
    100.0,
]
_RIDGE_CHUNK_SIZE_M = 2000.0
_RIDGE_PROBE_SPACING_M = 100.0
_RIDGE_CHUNK_CENTER = (900.0, 900.0)


def _write_ridge_chunk_fixture(path: Path) -> None:
    points = [
        (float(col) * _RIDGE_PROBE_SPACING_M, float(row) * _RIDGE_PROBE_SPACING_M, elev)
        for row in range(len(_RIDGE_CHUNK_COLS))
        for col, elev in enumerate(_RIDGE_CHUNK_COLS)
    ]
    _write_probe_fixture(path, points)


def test_add_probe_chunk_ingests_grids_but_no_longer_extracts_terrain(
    tmp_path: Path,
) -> None:
    base_path = _build_base(tmp_path)
    probe_output = tmp_path / "chunk.jsonl"
    _write_ridge_chunk_fixture(probe_output)

    chunk_ix, chunk_iz = chunk_index_for(
        *_RIDGE_CHUNK_CENTER, chunk_size_m=_RIDGE_CHUNK_SIZE_M
    )
    report = add_probe_chunk(
        base_path,
        probe_output,
        chunk_ix,
        chunk_iz,
        chunk_size_m=_RIDGE_CHUNK_SIZE_M,
        probe_spacing_m=_RIDGE_PROBE_SPACING_M,
    )

    assert report.chunk_ix == chunk_ix
    assert report.chunk_iz == chunk_iz
    assert report.probe_stats.points_received == len(_RIDGE_CHUNK_COLS) ** 2
    # No chunk-scoped ridge/valley extraction any more -- see this
    # module's own docstring and `build.pipeline.add_probe_chunk`'s.
    assert report.terrain_skipped is True
    assert report.terrain_stats is None

    probe_path = probe_store_path(base_path)
    assert probe_path.exists()

    probe_conn = open_probe_store(
        probe_path,
        "Syria",
        SCHEMA_VERSION,
        chunk_size_m=_RIDGE_CHUNK_SIZE_M,
        probe_spacing_m=_RIDGE_PROBE_SPACING_M,
    )
    try:
        # Column 8 (x=800) is the first valley's own floor, elevation 0.
        assert sample_probe_grid(probe_conn, "elevation", 800.0, 800.0) == 0.0
        assert sample_probe_grid(probe_conn, "surface_type", 800.0, 800.0) == 1.0
        assert (
            chunk_status(probe_conn, "elevation", chunk_ix, chunk_iz)
            == ChunkStatus.QUERIED_WITH_DATA
        )
        assert (
            chunk_status(probe_conn, "surface_type", chunk_ix, chunk_iz)
            == ChunkStatus.QUERIED_WITH_DATA
        )
        # Neither kind is ever touched any more -- UNQUERIED, not VOID
        # (VOID would mean "extraction ran and found nothing").
        assert (
            chunk_status(probe_conn, "valley", chunk_ix, chunk_iz)
            == ChunkStatus.UNQUERIED
        )
        assert (
            chunk_status(probe_conn, "ridge", chunk_ix, chunk_iz)
            == ChunkStatus.UNQUERIED
        )
    finally:
        probe_conn.close()


def test_add_probe_chunk_never_writes_base_store(tmp_path: Path) -> None:
    base_path = _build_base(tmp_path)
    probe_output = tmp_path / "chunk.jsonl"
    _write_probe_fixture(probe_output, _VALLEY_CHUNK_POINTS)
    chunk_ix, chunk_iz = chunk_index_for(1100.0, 1100.0, chunk_size_m=_CHUNK_SIZE_M)

    base_mtime_before = base_path.stat().st_mtime_ns

    add_probe_chunk(
        base_path,
        probe_output,
        chunk_ix,
        chunk_iz,
        chunk_size_m=_CHUNK_SIZE_M,
        probe_spacing_m=_PROBE_SPACING_M,
    )

    assert base_path.stat().st_mtime_ns == base_mtime_before

    import sqlite3

    conn = sqlite3.connect(f"file:{base_path}?mode=ro", uri=True)
    try:
        region = load_only_region(conn)
        assert region is not None
        assert region.name == "test-probe-chunk-region"
    finally:
        conn.close()


def test_add_probe_chunk_marks_void_coverage_when_no_points_in_chunk(
    tmp_path: Path,
) -> None:
    """A chunk output file with zero points (e.g. the whole chunk is open
    water and the probe's own logic emitted nothing) must mark coverage
    `QUERIED_VOID`, never leave it `UNQUERIED` -- a real, meaningful
    outcome per `probe_store.models.ChunkStatus`'s docstring."""
    base_path = _build_base(tmp_path)
    probe_output = tmp_path / "empty_chunk.jsonl"
    _write_probe_fixture(probe_output, [])
    chunk_ix, chunk_iz = chunk_index_for(9999.0, 9999.0, chunk_size_m=_CHUNK_SIZE_M)

    report = add_probe_chunk(
        base_path,
        probe_output,
        chunk_ix,
        chunk_iz,
        chunk_size_m=_CHUNK_SIZE_M,
        probe_spacing_m=_PROBE_SPACING_M,
    )

    assert report.terrain_skipped is True
    assert report.terrain_stats is None

    probe_path = probe_store_path(base_path)
    probe_conn = open_probe_store(
        probe_path,
        "Syria",
        SCHEMA_VERSION,
        chunk_size_m=_CHUNK_SIZE_M,
        probe_spacing_m=_PROBE_SPACING_M,
    )
    try:
        assert (
            chunk_status(probe_conn, "elevation", chunk_ix, chunk_iz)
            == ChunkStatus.QUERIED_VOID
        )
        assert (
            chunk_status(probe_conn, "surface_type", chunk_ix, chunk_iz)
            == ChunkStatus.QUERIED_VOID
        )
    finally:
        probe_conn.close()


def test_add_probe_chunk_raises_on_point_outside_claimed_chunk(tmp_path: Path) -> None:
    base_path = _build_base(tmp_path)
    probe_output = tmp_path / "bad_chunk.jsonl"
    # This point belongs to a different chunk than the one claimed below.
    _write_probe_fixture(probe_output, [(50000.0, 50000.0, 10.0)])
    chunk_ix, chunk_iz = chunk_index_for(1100.0, 1100.0, chunk_size_m=_CHUNK_SIZE_M)

    with pytest.raises(ValueError, match="outside chunk"):
        add_probe_chunk(
            base_path,
            probe_output,
            chunk_ix,
            chunk_iz,
            chunk_size_m=_CHUNK_SIZE_M,
            probe_spacing_m=_PROBE_SPACING_M,
        )


def test_add_probe_chunk_second_call_accumulates_across_chunks(tmp_path: Path) -> None:
    """A probe store must accumulate across separate `add_probe_chunk`
    calls -- unlike the base store's delete-and-recreate rebuild, this is
    the whole point of the probe tier surviving a base rebuild."""
    base_path = _build_base(tmp_path)

    chunk_a = chunk_index_for(1100.0, 1100.0, chunk_size_m=_CHUNK_SIZE_M)
    probe_output_a = tmp_path / "chunk_a.jsonl"
    _write_probe_fixture(probe_output_a, _VALLEY_CHUNK_POINTS)
    add_probe_chunk(
        base_path,
        probe_output_a,
        *chunk_a,
        chunk_size_m=_CHUNK_SIZE_M,
        probe_spacing_m=_PROBE_SPACING_M,
    )

    chunk_b = chunk_index_for(9999.0, 9999.0, chunk_size_m=_CHUNK_SIZE_M)
    probe_output_b = tmp_path / "chunk_b.jsonl"
    _write_probe_fixture(probe_output_b, [])
    add_probe_chunk(
        base_path,
        probe_output_b,
        *chunk_b,
        chunk_size_m=_CHUNK_SIZE_M,
        probe_spacing_m=_PROBE_SPACING_M,
    )

    probe_path = probe_store_path(base_path)
    probe_conn = open_probe_store(
        probe_path,
        "Syria",
        SCHEMA_VERSION,
        chunk_size_m=_CHUNK_SIZE_M,
        probe_spacing_m=_PROBE_SPACING_M,
    )
    try:
        # Chunk A's data from the first call must still be present after
        # the second call touched only chunk B.
        assert sample_probe_grid(probe_conn, "elevation", 1100.0, 1100.0) == -190.0
        assert (
            chunk_status(probe_conn, "elevation", *chunk_a)
            == ChunkStatus.QUERIED_WITH_DATA
        )
        assert (
            chunk_status(probe_conn, "elevation", *chunk_b) == ChunkStatus.QUERIED_VOID
        )
    finally:
        probe_conn.close()
