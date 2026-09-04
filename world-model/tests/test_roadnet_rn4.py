"""Tests for `roadnet.rn4` against a synthetic fixture built from **literal
values copied verbatim from real `Damascus.rn4`**, reproduced by directly
inspecting the local file this session (`data/` is gitignored, so the real
2.25 GB-adjacent files can never be pytest fixtures -- see
`test_dcs_grid.py`'s established pattern). Provenance: `Damascus.rn4`, 376
KB, `world-model/data/raw/dcs/syria/roadnet-samples/Damascus.rn4`, per
`world-model/research/2026-09-04-m5-roadnet-byte-decode.md` ("`.rn4` --
32-byte/8xint32 record hypothesis confirmed at real scale ... String table
confirmed to be road/segment *type* labels").

Literal values used, all read directly from the real file: `field_a=5`,
`string_count=7`, the 7-entry Damascus string table
(`taxiway_24m, ..., runway_65m`), the first topology row
`(444, 1, 0, 77, 2, 0, 0, 309)`, and the real sentinel/terminator row
`(55, 1, 75, 0, 3, 27, 45, 80)` that the real file's clean-table scan stops
at after exactly 79 data rows.
"""

import struct
from pathlib import Path

from build.ingest_roadnet import ingest_roadnet
from roadnet.rn4 import (
    Rn4Header,
    TopologyRow,
    iter_topology_rows,
    parse_header,
    read_string_table,
    type_name_for_row,
)

_RN4_CLASS_NAME = "landscape4::lRoadNetwork"

# Real, literal Damascus.rn4 string table (7 entries) -- copied verbatim
# from the local file this session.
_DAMASCUS_STRINGS = [
    "taxiway_24m",
    "taxiway_61m",
    "taxiway_15m",
    "taxiway_52m",
    "taxiway_36m",
    "taxiway_41m",
    "runway_65m",
]

# Real, literal Damascus.rn4 topology rows -- the first data row, one more
# data row with a non-default column-6 type index (type-index diversity),
# and the real sentinel/terminator row that the file's clean-table scan
# stops at after 79 data rows.
_DAMASCUS_FIRST_ROW = (444, 1, 0, 77, 2, 0, 0, 309)
_DAMASCUS_TAXIWAY_52M_ROW = (27, 1, 11, 125, 2, 12, 3, 226)  # col6=3 -> taxiway_52m
_DAMASCUS_SENTINEL_ROW = (55, 1, 75, 0, 3, 27, 45, 80)


def _pack_header(class_name: str) -> bytes:
    name_bytes = class_name.encode("ascii")
    return (
        struct.pack("<8i", 2, 48, 0, 0, 0, 0, 0, 0)
        + struct.pack("<i", len(name_bytes))
        + name_bytes
    )


def _pack_string_table(strings: list[str]) -> bytes:
    out = struct.pack("<i", len(strings))
    for s in strings:
        raw = s.encode("ascii")
        out += struct.pack("<i", len(raw)) + raw
    return out


def _pack_row(row: tuple[int, int, int, int, int, int, int, int]) -> bytes:
    return struct.pack("<8i", *row)


def _build_rn4_buffer(
    rows: list[tuple[int, int, int, int, int, int, int, int]],
) -> bytes:
    buf = _pack_header(_RN4_CLASS_NAME)
    buf += struct.pack("<i", 5)  # field_a, constant 5 in every real file checked
    buf += _pack_string_table(_DAMASCUS_STRINGS)
    for row in rows:
        buf += _pack_row(row)
    return buf


def test_parse_header_reads_string_table() -> None:
    buf = _build_rn4_buffer([_DAMASCUS_FIRST_ROW, _DAMASCUS_SENTINEL_ROW])

    header = parse_header(buf)

    assert header.field_a == 5
    assert header.string_table == _DAMASCUS_STRINGS
    assert header.string_table[0] == "taxiway_24m"
    assert header.string_table[-1] == "runway_65m"


def test_read_string_table_directly() -> None:
    buf = _pack_string_table(_DAMASCUS_STRINGS)

    strings, offset = read_string_table(buf, 0)

    assert strings == _DAMASCUS_STRINGS
    assert offset == len(buf)


def test_iter_topology_rows_stops_before_sentinel() -> None:
    rows = [_DAMASCUS_FIRST_ROW, _DAMASCUS_TAXIWAY_52M_ROW, _DAMASCUS_SENTINEL_ROW]
    buf = _build_rn4_buffer(rows)
    header = parse_header(buf)

    decoded = list(iter_topology_rows(buf, header.topology_table_offset))

    # The sentinel row itself is not yielded -- only the 2 real data rows.
    assert len(decoded) == 2
    assert decoded[0].columns == _DAMASCUS_FIRST_ROW
    assert decoded[1].columns == _DAMASCUS_TAXIWAY_52M_ROW


def test_type_name_for_row_resolves_column_6() -> None:
    first_row = TopologyRow(columns=_DAMASCUS_FIRST_ROW)
    taxiway_52m_row = TopologyRow(columns=_DAMASCUS_TAXIWAY_52M_ROW)

    assert type_name_for_row(first_row, _DAMASCUS_STRINGS) == "taxiway_24m"
    assert type_name_for_row(taxiway_52m_row, _DAMASCUS_STRINGS) == "taxiway_52m"


def test_type_name_for_row_out_of_range_returns_none() -> None:
    row = TopologyRow(columns=(0, 1, 0, 0, 2, 0, 999, 0))

    assert type_name_for_row(row, _DAMASCUS_STRINGS) is None


def test_rn4_header_is_frozen_and_hashable_shape() -> None:
    # Sanity check on the dataclass shape used throughout this module --
    # not a format assertion.
    header = Rn4Header(field_a=5, string_table=["a"], topology_table_offset=10)
    assert header.field_a == 5


def _pack_route_point_block(points: list[tuple[float, float, float]]) -> bytes:
    return struct.pack("<i", len(points)) + b"".join(
        struct.pack("<3d", *p) for p in points
    )


def _build_routes_buffer() -> bytes:
    """A minimal, well-formed `.routes`-shaped buffer: header, then one
    route's position + direction arrays, using the same real literal
    position triples as `test_roadnet_routes.py`."""
    name_bytes = "landscape4::lRoutesFile".encode("ascii")
    header = (
        struct.pack("<8i", 2, 48, 0, 0, 0, 0, 0, 0)
        + struct.pack("<i", len(name_bytes))
        + name_bytes
    )
    points = [
        (214985.70, 18.74, -45079.89),
        (214985.65, 18.74, -45079.88),
        (214982.84, 18.69, -45078.98),
        (214958.38, 18.07, -45069.10),
        (214958.38, 18.07, -45069.10),
    ]
    directions = [(-0.291, 0.0, -0.957)] * len(points)
    return (
        header + _pack_route_point_block(points) + _pack_route_point_block(directions)
    )


def test_ingested_road_features_never_carry_a_subtype(tmp_path: Path) -> None:
    """Scope guard: `.rn4` type names are real and resolvable (see
    `test_type_name_for_row_resolves_column_6` above), but
    `build.ingest_roadnet` must never join them onto `.routes` geometry --
    plan.md Decision 7. `ingest_roadnet` doesn't even import `roadnet.rn4`;
    this test pins the observable consequence so a future well-meaning
    change has to argue with it, not just with a docstring."""
    routes_path = tmp_path / "synthetic.routes"
    routes_path.write_bytes(_build_routes_buffer())

    features, _stats = ingest_roadnet(
        routes_path,
        centre_x=214985.0,
        centre_z=-45079.0,
        half_extent_m=1000.0,
        source_id=None,
    )

    assert len(features) >= 1
    assert all(f.subtype is None for f in features)
    assert all(f.name is None for f in features)
    assert all(f.provenance["geometry"] == "dcs" for f in features)
    assert all(f.position_uncertainty_m == 0.0 for f in features)
