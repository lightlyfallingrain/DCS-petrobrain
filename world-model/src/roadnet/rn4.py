"""Parses `.rn4` (`landscape4::lRoadNetwork`) files: the road/taxiway
segment *type* vocabulary (a string table) and a sanity read of the
topology table that follows it.

**Non-goals, stated here per `roadnet/__init__.py`'s convention:** the
adjacency/graph section after the topology table is **not decoded**, and
topology rows are **not joined** to any geometry (`.routes` or `.rn4`'s own
embedded geometry blocks) -- M5 uses this module only for the type
vocabulary and to confirm the topology table decodes as expected. Emitted
`road` features carry `subtype=None` regardless of what this module can
read; see `build/ingest_roadnet.py`.

Header layout (byte-decode research note, both sessions): after the
`landscape4::lRoadNetwork` class name, `int32 field_a` (constant `5` in
every file checked, meaning unresolved), `int32 string_count`, then
`string_count` length-prefixed ASCII strings. Immediately after the string
table: rows of 8 little-endian int32 (32 bytes each) where column 1 is a
constant `1` and column 4 is a constant `2` for real data rows -- confirmed
against real `Damascus.rn4` (79 rows) and `Incirlik.rn4` (132 rows). The
table ends at the first row failing that test (its own sentinel/terminator
row, itself not a data row -- confirmed to carry `column 4 == 3` in both
files checked). Column 6 is a confirmed string-table type index.
"""

import struct
from collections.abc import Iterator
from dataclasses import dataclass

from .container import Buffer, read_header, read_int32, read_length_prefixed_string

_CLASS_NAME = "landscape4::lRoadNetwork"
_ROW_STRUCT = struct.Struct("<8i")
_ROW_SIZE = 32


@dataclass(frozen=True)
class Rn4Header:
    """`field_a` is an unidentified constant (`5` in every file checked --
    Damascus, Incirlik, Syria). `string_table` is the road/taxiway type
    vocabulary (e.g. `taxiway_24m`, `runway_65m`). `topology_table_offset`
    is where `iter_topology_rows` should start reading."""

    field_a: int
    string_table: list[str]
    topology_table_offset: int


def parse_header(buf: Buffer) -> Rn4Header:
    """Read and validate the `landscape4::lRoadNetwork` header and its
    string table. Raises `container.ContainerFormatError` if the class name
    doesn't match or any length-prefixed field is malformed."""
    header = read_header(buf, _CLASS_NAME)
    field_a, offset = read_int32(buf, header.data_offset)
    string_table, table_offset = read_string_table(buf, offset)
    return Rn4Header(
        field_a=field_a, string_table=string_table, topology_table_offset=table_offset
    )


def read_string_table(buf: Buffer, offset: int) -> tuple[list[str], int]:
    """Read `int32 count` followed by `count` length-prefixed ASCII
    strings, starting at `offset`. Returns `(strings, offset_after_table)`."""
    count, pos = read_int32(buf, offset)
    strings: list[str] = []
    for _ in range(count):
        text, pos = read_length_prefixed_string(buf, pos)
        strings.append(text)
    return strings, pos


@dataclass(frozen=True)
class TopologyRow:
    """One 8xint32 topology-table row. `columns[6]` is the confirmed
    string-table type index (resolve via `type_name_for_row`). Columns 0, 3
    and 7's semantics are unresolved (byte-decode research note) and are
    exposed verbatim, not interpreted."""

    columns: tuple[int, int, int, int, int, int, int, int]


def iter_topology_rows(buf: Buffer, offset: int) -> Iterator[TopologyRow]:
    """Yield topology rows starting at `offset`, while column 1 == 1 and
    column 4 == 2 -- the confirmed real-data-row signature. Stops (without
    yielding) at the first row failing that test, which is the table's own
    sentinel/terminator row, not a data row."""
    pos = offset
    while pos + _ROW_SIZE <= len(buf):
        row = _ROW_STRUCT.unpack_from(buf, pos)
        if not (row[1] == 1 and row[4] == 2):
            return
        yield TopologyRow(
            columns=(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
        )
        pos += _ROW_SIZE


def type_name_for_row(row: TopologyRow, string_table: list[str]) -> str | None:
    """Resolve a topology row's road/taxiway type name via column 6 (the
    confirmed string-table index). Returns `None` if the index is out of
    range for `string_table` -- not seen in real data, but a defensive
    absence rather than an `IndexError`, consistent with "absence reported
    as absence"."""
    index = row.columns[6]
    if 0 <= index < len(string_table):
        return string_table[index]
    return None
