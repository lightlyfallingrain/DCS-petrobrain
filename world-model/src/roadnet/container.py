"""Shared `landscape4::` container primitives for `.routes` and `.rn4`.

Both file types share one fixed header shape (8 little-endian int32, then a
length-prefixed ASCII class name) and one point-block schema (`[int32 N][N x
float64 xyz]`), confirmed byte-exact against real files in
`world-model/research/2026-09-04-m5-roadnet-byte-decode.md` and
`.../2026-09-03-m5-terrain-file-formats.md`. This module exists to remove a
*named* duplication: letting `.routes` and `.rn4` each grow their own copy of
this logic is how they would drift.

**Fail loudly on a format change.** `read_header` asserts the class name
exactly; every length prefix is bounds-checked before use. A DCS terrain
update that changes this container must raise `ContainerFormatError`, never
silently produce plausible-looking wrong geometry -- see the project
invariant against convincing-but-wrong outputs.

**Scan-forward resync.** `find_next_point_block` is the validated technique
(research note, both sessions) for walking past a `.routes` route's
intentionally-undecoded trailer, or `.rn4`'s undecoded adjacency section: it
scans forward byte-by-byte from a starting offset for the next plausible
`[int32 N][N x float64 xyz]` block, using a first/middle/last coordinate
pre-filter before paying for a full N-point validation. The pre-filter is
**mandatory, not an optimization** -- a naive "validate every candidate
offset in full" scan was measured at 6+ CPU-minutes on a 50 MB buffer; the
pre-filter reduces the same scan to low single-digit seconds.
"""

import math
import mmap
import struct
from dataclasses import dataclass

Buffer = bytes | bytearray | mmap.mmap

_INT32 = struct.Struct("<i")
_HEADER_PREFIX = struct.Struct("<8i")
_TRIPLE = struct.Struct("<3d")
_TRIPLE_SIZE = 24

# DCS's real coordinate envelope (Syria theatre; generous margins -- this is
# a resync sanity filter, not a precise theatre bound). x/z run to hundreds
# of km; y is altitude in metres.
_COORD_XZ_MAX = 1_000_000.0
_COORD_Y_MIN = -2_000.0
_COORD_Y_MAX = 6_000.0

# A nonzero float64 with magnitude below this is denormalized-float garbage
# from a misaligned/false-positive resync match, never a genuine DCS
# coordinate -- confirmed empirically in
# `world-model/research/2026-09-04-m5-roadnet-byte-decode.md` Session 2
# ("rejecting any value that is nonzero but has magnitude < 1e-6 ... without
# this filter the scan returns thousands of false positives with y/z values
# like 1e-312"). That filter was applied in the exploratory recon script but
# never carried into this production validator -- exactly how DCS road
# feature id=3711 (source_ref "route:3311@464953201") slipped through as a
# false-positive resync match in the real Latakia store (see
# `world-model/research/2026-09-04-m5-stage4-validation.md` Finding 1 and
# this fix's dated correction note). Exact zero is still permitted -- a
# genuine DCS coordinate can legitimately be 0.0 (e.g. sea-level y).
_MIN_NONZERO_MAGNITUDE = 1e-6

# Plausible point-block count range for the resync scan -- per byte-decode
# research note's validated technique.
_MIN_PLAUSIBLE_N = 5
_MAX_PLAUSIBLE_N = 20_000


class ContainerFormatError(ValueError):
    """A `landscape4::` container did not match the expected class name, or
    a length-prefixed field would read past end-of-buffer. Raised instead of
    returning a best-effort guess -- a DCS format change must fail loudly."""


@dataclass(frozen=True)
class ContainerHeader:
    """The fixed `landscape4::` header. `byte_count` mirrors the file's own
    size for `.rn4` but is ~2.3 MB short for `.routes` (unexplained,
    systematic across both Syria and Caucasus -- see the byte-decode
    research note's Unresolved section); never trust it as an authoritative
    length. `data_offset` is the byte offset immediately after the class
    name string, where the format-specific body begins."""

    magic1: int
    magic2: int
    byte_count: int
    class_name: str
    data_offset: int


def read_int32(buf: Buffer, offset: int) -> tuple[int, int]:
    """Read one little-endian int32 at `offset`. Returns `(value,
    offset_after)`. Raises `ContainerFormatError` if it would read past
    end-of-buffer."""
    if offset < 0 or offset + 4 > len(buf):
        raise ContainerFormatError(f"int32 read at offset {offset} exceeds buffer")
    (value,) = _INT32.unpack_from(buf, offset)
    return value, offset + 4


def read_length_prefixed_string(buf: Buffer, offset: int) -> tuple[str, int]:
    """Read a 4-byte little-endian length prefix followed by that many ASCII
    bytes. Returns `(string, offset_after_string)`. Raises
    `ContainerFormatError` if the length is negative or would read past
    end-of-buffer."""
    length, string_offset = read_int32(buf, offset)
    if length < 0 or string_offset + length > len(buf):
        raise ContainerFormatError(
            f"string length {length} at offset {offset} exceeds buffer bounds"
        )
    raw = bytes(buf[string_offset : string_offset + length])
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ContainerFormatError(
            f"string at offset {offset} (length {length}) is not ASCII"
        ) from exc
    return text, string_offset + length


def read_header(buf: Buffer, expected_class_name: str) -> ContainerHeader:
    """Read and validate a `landscape4::` container's fixed header: 8
    little-endian int32 followed by a length-prefixed ASCII class name.
    Raises `ContainerFormatError` if the class name does not exactly match
    `expected_class_name` -- a format change must be a loud exception, not
    silently-wrong parsing downstream."""
    if len(buf) < _HEADER_PREFIX.size:
        raise ContainerFormatError("buffer too short for landscape4:: header")
    magic1, magic2, byte_count, *_reserved = _HEADER_PREFIX.unpack_from(buf, 0)
    class_name, data_offset = read_length_prefixed_string(buf, _HEADER_PREFIX.size)
    if class_name != expected_class_name:
        raise ContainerFormatError(
            f"expected class name {expected_class_name!r}, got {class_name!r} "
            "-- landscape4:: container format may have changed"
        )
    return ContainerHeader(
        magic1=magic1,
        magic2=magic2,
        byte_count=byte_count,
        class_name=class_name,
        data_offset=data_offset,
    )


def read_point_block(
    buf: Buffer, offset: int
) -> tuple[list[tuple[float, float, float]], int]:
    """Read one length-prefixed point block: `int32 N` followed by `N`
    little-endian `float64` (x, y, z) triples, at exactly `offset` (no
    scanning). Returns `(points, offset_after_block)`. Raises
    `ContainerFormatError` if `N` is negative or the block would read past
    end-of-buffer -- this is the strict, non-resyncing reader, used where
    the block is known to start exactly at `offset` (e.g. a `.routes`
    direction array, always immediately adjacent to its position array)."""
    n, points_offset = read_int32(buf, offset)
    if n < 0:
        raise ContainerFormatError(f"negative point count {n} at offset {offset}")
    end = points_offset + n * _TRIPLE_SIZE
    if end > len(buf):
        raise ContainerFormatError(
            f"point block of N={n} at offset {offset} exceeds buffer"
        )
    points = [
        _TRIPLE.unpack_from(buf, points_offset + i * _TRIPLE_SIZE) for i in range(n)
    ]
    return points, end


def _is_denormalized_garbage(value: float) -> bool:
    """True for a nonzero value whose magnitude is implausibly small for a
    genuine DCS coordinate -- the signature of a misaligned/false-positive
    resync match reinterpreting non-float bytes as a float64. Exact 0.0 is
    not garbage (a real coordinate component can legitimately be zero)."""
    return value != 0.0 and abs(value) < _MIN_NONZERO_MAGNITUDE


def _triple_plausible(buf: Buffer, offset: int) -> bool:
    try:
        x, y, z = _TRIPLE.unpack_from(buf, offset)
    except struct.error:
        return False
    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
        return False
    if any(_is_denormalized_garbage(v) for v in (x, y, z)):
        return False
    if abs(x) >= _COORD_XZ_MAX or abs(z) >= _COORD_XZ_MAX:
        return False
    return bool(_COORD_Y_MIN <= y <= _COORD_Y_MAX)


def _prefilter_plausible(buf: Buffer, points_offset: int, n: int) -> bool:
    """Cheap pre-filter: only the first, middle and last triple, before
    paying for a full N-point validation. Mandatory for performance -- see
    module docstring."""
    for i in {0, n // 2, n - 1}:
        if not _triple_plausible(buf, points_offset + i * _TRIPLE_SIZE):
            return False
    return True


def _full_validate(buf: Buffer, points_offset: int, n: int) -> bool:
    return all(
        _triple_plausible(buf, points_offset + i * _TRIPLE_SIZE) for i in range(n)
    )


def find_next_point_block(
    buf: Buffer,
    start: int,
    min_n: int = _MIN_PLAUSIBLE_N,
    max_n: int = _MAX_PLAUSIBLE_N,
) -> tuple[int, list[tuple[float, float, float]], int] | None:
    """Scan forward from `start` for the next well-formed, plausible point
    block -- the scan-forward resync technique that recovers sync after an
    intentionally-undecoded region (a `.routes` route's trailer, `.rn4`'s
    adjacency section).

    For each candidate offset, an `int32 N` in `[min_n, max_n]` whose block
    would fit in the buffer is cheaply pre-filtered on its first/middle/last
    coordinate triple before a full N-point validation is attempted -- see
    module docstring for why the pre-filter is mandatory, not optional.

    Returns `(match_offset, points, offset_after_block)`, or `None` if no
    plausible block is found before end-of-buffer. `match_offset` may equal
    `start` (block found immediately, no resync needed) or be greater
    (resync occurred, having skipped an undecoded region)."""
    limit = len(buf) - 4
    offset = start
    while offset <= limit:
        n, points_offset = read_int32(buf, offset)
        if min_n <= n <= max_n:
            end = points_offset + n * _TRIPLE_SIZE
            if (
                end <= len(buf)
                and _prefilter_plausible(buf, points_offset, n)
                and _full_validate(buf, points_offset, n)
            ):
                points = [
                    _TRIPLE.unpack_from(buf, points_offset + i * _TRIPLE_SIZE)
                    for i in range(n)
                ]
                return offset, points, end
        offset += 1
    return None
