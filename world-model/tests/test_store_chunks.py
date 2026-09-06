"""Tests for `store.chunks` -- the theatre-anchored chunk lattice. Pure
functions, no I/O; see the module docstring for why this is "most worth
exhaustive unit tests"."""

import pytest

from store.chunks import CHUNK_SIZE_M, chunk_bounds, chunk_index_for, chunks_covering


def test_chunk_size_is_multiple_of_probe_spacing() -> None:
    """Locked-parameter invariant restated here as a test (the real
    assertion lives in `probe_store.schema`, which imports `CHUNK_SIZE_M`
    -- this test protects against `CHUNK_SIZE_M` alone changing in a way
    that would silently misalign chunk edges from probe cell boundaries)."""
    from probe_store.schema import PROBE_SPACING_M

    assert CHUNK_SIZE_M % PROBE_SPACING_M == 0


def test_chunk_index_for_origin() -> None:
    assert chunk_index_for(0.0, 0.0) == (0, 0)


def test_chunk_index_for_positive_coordinates() -> None:
    assert chunk_index_for(12000.0, 7000.0) == (2, 1)


def test_chunk_index_for_negative_coordinates() -> None:
    """Syria has DCS coordinates negative on both axes in its western/
    southern reaches -- Python's `//`/`math.floor` handles this correctly,
    unlike a naive `int(x / size)` truncation, which would round toward
    zero instead of down."""
    assert chunk_index_for(-1.0, -1.0) == (-1, -1)
    assert chunk_index_for(-5000.0, -5000.0) == (-1, -1)
    assert chunk_index_for(-5001.0, -5001.0) == (-2, -2)


def test_chunk_bounds_matches_chunk_size() -> None:
    min_x, max_x, min_z, max_z = chunk_bounds(2, 1)
    assert (min_x, max_x) == (10000.0, 15000.0)
    assert (min_z, max_z) == (5000.0, 10000.0)


def test_chunk_bounds_negative_index() -> None:
    min_x, max_x, min_z, max_z = chunk_bounds(-1, -1)
    assert (min_x, max_x) == (-5000.0, 0.0)
    assert (min_z, max_z) == (-5000.0, 0.0)


@pytest.mark.parametrize(
    "ix,iz",
    [(0, 0), (2, 1), (-1, -1), (-2, 3), (100, -50)],
)
def test_chunk_index_round_trips_through_bounds_centre(ix: int, iz: int) -> None:
    """`chunk_index_for(centre_of(chunk_bounds(ix, iz))) == (ix, iz)` --
    the round-trip the plan's Implementation Plan step 1 names explicitly."""
    min_x, max_x, min_z, max_z = chunk_bounds(ix, iz)
    centre_x = (min_x + max_x) / 2.0
    centre_z = (min_z + max_z) / 2.0
    assert chunk_index_for(centre_x, centre_z) == (ix, iz)


def test_chunks_covering_single_chunk_bbox() -> None:
    bbox = chunk_bounds(3, 3)
    # Shrink slightly so the bbox is strictly interior to chunk (3, 3).
    min_x, max_x, min_z, max_z = bbox
    interior = (min_x + 1.0, max_x - 1.0, min_z + 1.0, max_z - 1.0)
    assert chunks_covering(interior) == [(3, 3)]


def test_chunks_covering_spans_multiple_chunks() -> None:
    # A bbox straddling the boundary between chunks (0,0)/(1,0)/(0,1)/(1,1).
    bbox = (-100.0, 100.0, -100.0, 100.0)
    covering = set(chunks_covering(bbox))
    assert covering == {(-1, -1), (-1, 0), (0, -1), (0, 0)}


def test_chunks_covering_raises_on_degenerate_bbox() -> None:
    with pytest.raises(ValueError):
        chunks_covering((100.0, 0.0, 0.0, 100.0))
