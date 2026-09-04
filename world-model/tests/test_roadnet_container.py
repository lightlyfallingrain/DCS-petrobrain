"""Tests for `roadnet.container`'s shared `landscape4::` primitives, against
**synthetic byte fixtures built in the test** -- `data/` is gitignored, so
real `.routes`/`.rn4` files can never be pytest fixtures (see
`test_dcs_grid.py`'s established pattern). The container header layout (8
int32 + length-prefixed class name) and class names (`landscape4::
lRoutesFile`, `landscape4::lRoadNetwork`) are real, literal values confirmed
against actual files -- see
`world-model/research/2026-09-03-m5-terrain-file-formats.md` ("The
`.rn4`/`.routes` container header is a simple, consistent, fully decodable
structure") and `world-model/research/2026-09-04-m5-roadnet-byte-decode.md`.

The resync test is the most important one here: the whole parser rests on
scan-forward resync being able to recover sync after an unparsed region, so
it is tested directly (a valid block preceded by plausible-looking garbage),
not just implicitly through a well-aligned fixture.
"""

import struct

import pytest

from roadnet.container import (
    ContainerFormatError,
    find_next_point_block,
    read_header,
    read_point_block,
)

_ROUTES_CLASS_NAME = "landscape4::lRoutesFile"


def _pack_header(class_name: str, byte_count: int = 0) -> bytes:
    """8 x int32 `[2, 48, <byte-count>, 0, 0, 0, 0, 0]` then a
    length-prefixed ASCII class name -- literal layout, both real class
    names, per `2026-09-03-m5-terrain-file-formats.md`."""
    name_bytes = class_name.encode("ascii")
    return (
        struct.pack("<8i", 2, 48, byte_count, 0, 0, 0, 0, 0)
        + struct.pack("<i", len(name_bytes))
        + name_bytes
    )


def _pack_point_block(points: list[tuple[float, float, float]]) -> bytes:
    return struct.pack("<i", len(points)) + b"".join(
        struct.pack("<3d", *p) for p in points
    )


def test_read_header_valid() -> None:
    # -2045825944 is the real, literal header int32 read from the actual
    # Syria.routes file (a signed int32 overflow of the file's true
    # ~2.25 GB size -- exactly why `ContainerHeader.byte_count` is
    # documented as unreliable for `.routes`, not a bug in this fixture).
    buf = _pack_header(_ROUTES_CLASS_NAME, byte_count=-2045825944)

    header = read_header(buf, _ROUTES_CLASS_NAME)

    assert header.magic1 == 2
    assert header.magic2 == 48
    assert header.byte_count == -2045825944
    assert header.class_name == _ROUTES_CLASS_NAME
    # 8 int32 (32 bytes) + 4-byte length prefix + 23 ascii bytes = 59, the
    # real, confirmed data-start offset for Syria.routes.
    assert header.data_offset == 59


def test_read_header_wrong_class_name_raises() -> None:
    buf = _pack_header("landscape4::somethingElse")

    with pytest.raises(ContainerFormatError, match="expected class name"):
        read_header(buf, _ROUTES_CLASS_NAME)


def test_read_header_too_short_raises() -> None:
    with pytest.raises(ContainerFormatError):
        read_header(b"\x00" * 4, _ROUTES_CLASS_NAME)


def test_read_point_block_well_formed() -> None:
    points = [(214985.70, 18.74, -45079.89), (214985.65, 18.74, -45079.88)]
    buf = _pack_point_block(points)

    decoded, end = read_point_block(buf, 0)

    assert decoded == points
    assert end == len(buf)


def test_read_point_block_n_past_end_of_buffer_raises() -> None:
    # Declares 100 points but the buffer only holds 2 -- must raise, not
    # read garbage past the end.
    buf = struct.pack("<i", 100) + b"".join(
        struct.pack("<3d", *p) for p in [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
    )

    with pytest.raises(ContainerFormatError, match="exceeds buffer"):
        read_point_block(buf, 0)


def test_read_point_block_negative_n_raises() -> None:
    buf = struct.pack("<i", -1)

    with pytest.raises(ContainerFormatError, match="negative point count"):
        read_point_block(buf, 0)


def test_find_next_point_block_lands_immediately_when_already_aligned() -> None:
    points = [(214985.70, 18.74, -45079.89), (214982.84, 18.69, -45078.98)]
    buf = _pack_point_block(points)

    result = find_next_point_block(buf, 0, min_n=2)

    assert result is not None
    match_offset, decoded, end = result
    assert match_offset == 0
    assert decoded == points
    assert end == len(buf)


def test_find_next_point_block_resyncs_past_garbage() -> None:
    """The core resync test: a real, valid point block preceded by a region
    of plausible-looking garbage (small int32s that could be mistaken for a
    point count, and out-of-envelope-coordinate float64 noise), proving the
    scan-forward technique actually *recovers* sync rather than only
    working on already-aligned input."""
    garbage = (
        struct.pack("<i", 7)  # a small int32 that could look like a count
        + struct.pack("<3d", 1e300, -1e300, 5e9)  # wildly out of envelope
        + struct.pack("<i", -65536)  # sentinel-looking negative int32
        + struct.pack("<i", 65535)
        + b"\x01\x02\x03"  # a few odd, unaligned bytes
    )
    real_points = [
        (214985.70, 18.74, -45079.89),
        (214985.65, 18.74, -45079.88),
        (214982.84, 18.69, -45078.98),
        (214958.38, 18.07, -45069.10),
    ]
    valid_block = _pack_point_block(real_points)
    buf = garbage + valid_block
    expected_offset = len(garbage)

    # min_n=4 (below the production default of 5) since this fixture only
    # has 4 literal points to work with -- the resync mechanics being
    # tested don't depend on the exact threshold.
    result = find_next_point_block(buf, 0, min_n=4)

    assert result is not None
    match_offset, decoded, end = result
    assert match_offset == expected_offset
    assert decoded == real_points
    assert end == len(buf)


def test_find_next_point_block_returns_none_when_nothing_plausible() -> None:
    buf = b"\x00" * 200

    assert find_next_point_block(buf, 0) is None
