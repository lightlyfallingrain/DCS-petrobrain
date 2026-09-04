"""Tests for `roadnet.routes.iter_routes` against a synthetic fixture built
from **literal values copied verbatim from the byte-decode research note**
(`data/` is gitignored, so the real 50 MB/2.25 GB files can never be pytest
fixtures -- see `test_dcs_grid.py`'s established pattern). Literal position
triples and their byte offset (93) are from
`world-model/research/2026-09-03-m5-terrain-file-formats.md` ("Syria.routes'
data region decodes cleanly ... (214985.70, 18.74, -45079.89), ..."); the
literal unit direction vector and its confirmed exact magnitude are from
`world-model/research/2026-09-04-m5-roadnet-byte-decode.md` Session 1
("(-0.291, 0.0, -0.957), magnitude 1.0000000000000002").

The fixture assembles **two** consecutive routes separated by a small
undecoded trailer gap, so the resync-between-routes behaviour (not just a
single well-aligned route) is exercised, matching the real file's structure.
"""

import struct
from pathlib import Path

from roadnet.routes import RouteWalkStats, iter_routes

_ROUTES_CLASS_NAME = "landscape4::lRoutesFile"

# Real, literal first-route position triples -- copied verbatim from
# `2026-09-03-m5-terrain-file-formats.md`, decoded from the real
# `Syria.routes` data-start offset (byte 93, confirmed in
# `2026-09-04-m5-roadnet-byte-decode.md`).
_ROUTE_1_POINTS = [
    (214985.70, 18.74, -45079.89),
    (214985.65, 18.74, -45079.88),
    (214982.84, 18.69, -45078.98),
    (214958.38, 18.07, -45069.10),
    (214958.38, 18.07, -45069.10),
]

# Real, literal unit direction vector (magnitude confirmed
# 1.0000000000000002 in the research note) -- reused for every point since
# only one literal direction value was captured by hand-decoding.
_UNIT_DIRECTION = (-0.291, 0.0, -0.957)

_ROUTE_2_POINTS = [
    (50665.2, -0.56, -38.8),
    (51747.0, -0.00002, -15.6),
    (36793.8, 1046.5, -14.6),
    (36793.8, 1046.5, -14.6),
    (36793.8, 1046.5, -14.6),
]


def _pack_header(class_name: str) -> bytes:
    name_bytes = class_name.encode("ascii")
    return (
        struct.pack("<8i", 2, 48, 0, 0, 0, 0, 0, 0)
        + struct.pack("<i", len(name_bytes))
        + name_bytes
    )


def _pack_point_block(points: list[tuple[float, float, float]]) -> bytes:
    return struct.pack("<i", len(points)) + b"".join(
        struct.pack("<3d", *p) for p in points
    )


def _pack_route(points: list[tuple[float, float, float]]) -> bytes:
    directions = [_UNIT_DIRECTION] * len(points)
    return _pack_point_block(points) + _pack_point_block(directions)


def _undecoded_trailer_gap() -> bytes:
    """A short region standing in for the real per-route trailer (arc
    length / flags / curvature arrays, per the byte-decode research note) --
    deliberately *not* shaped like a valid point block, so walking past it
    requires the scan-forward resync rather than a lucky direct read."""
    return struct.pack("<i", -1) + b"\x00" * 12 + struct.pack("<i", 0)


def _write_fixture(tmp_path: Path) -> Path:
    buf = (
        _pack_header(_ROUTES_CLASS_NAME)
        + _pack_route(_ROUTE_1_POINTS)
        + _undecoded_trailer_gap()
        + _pack_route(_ROUTE_2_POINTS)
    )
    path = tmp_path / "synthetic.routes"
    path.write_bytes(buf)
    return path


def test_iter_routes_decodes_positions_exactly(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path)

    routes = list(iter_routes(path))

    assert len(routes) == 2
    assert routes[0].points == _ROUTE_1_POINTS
    assert routes[1].points == _ROUTE_2_POINTS


def test_iter_routes_direction_vectors_have_unit_magnitude(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path)

    routes = list(iter_routes(path))

    for route in routes:
        for dx, dy, dz in route.directions:
            magnitude = (dx * dx + dy * dy + dz * dz) ** 0.5
            # The research note's literal value is truncated to 3 decimals
            # for readability (the real float64 magnitude is confirmed
            # 1.0000000000000002); tolerance matches routes.py's own
            # `_UNIT_MAGNITUDE_TOLERANCE`, not exact-bit equality.
            assert abs(magnitude - 1.0) < 1e-3


def test_iter_routes_reports_route_index_and_byte_offset(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path)

    routes = list(iter_routes(path))

    assert [r.route_index for r in routes] == [0, 1]
    # Route 1's position block starts exactly at the confirmed real
    # data-start offset (59 + 34 == 93 in the real file; here it's right
    # after our synthetic header, at header.data_offset for this fixture).
    assert routes[0].byte_offset == len(_pack_header(_ROUTES_CLASS_NAME))
    assert routes[1].byte_offset > routes[0].byte_offset


def test_iter_routes_bbox_filters_yielded_routes(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path)
    # A bbox that only covers route 2's coordinate range (x ~36-52k).
    bbox = (30000.0, 60000.0, -60000.0, 0.0)

    routes = list(iter_routes(path, bbox=bbox))

    assert len(routes) == 1
    assert routes[0].points == _ROUTE_2_POINTS


def test_iter_routes_stats_count_both_routes_and_the_resync(tmp_path: Path) -> None:
    path = _write_fixture(tmp_path)
    stats = RouteWalkStats()

    list(iter_routes(path, stats=stats))

    assert stats.routes_found == 2
    # Route 2's position block had to be found via scan-forward past the
    # undecoded trailer gap -- exactly one resync event.
    assert stats.resync_events == 1
    assert stats.sync_loss_events == 0
    assert stats.bytes_covered > 0


def test_iter_routes_skips_denormalized_garbage_false_positive_route(
    tmp_path: Path,
) -> None:
    """Regression test for the real defect found in Stage 4 validation
    (`world-model/research/2026-09-04-m5-stage4-validation.md` Finding 1):
    DCS road feature id=3711 decoded as a false-positive scan-forward resync
    match -- two denormalized-float garbage leading points followed by
    exact-zero padding, which the old envelope check accepted as plausible.
    A garbage pseudo-"route" using those literal values, injected between
    two real routes, must be skipped entirely -- `iter_routes` must yield
    only the two real routes, never a spurious third one sourced from
    garbage geometry."""
    garbage_points: list[tuple[float, float, float]] = [
        (-5.607157514132566e-195, 1.36211130863e-312, 0.0),
        (46368.0, 0.0, 1.371949926365e-312),
    ] + [(0.0, 0.0, 0.0)] * 61
    buf = (
        _pack_header(_ROUTES_CLASS_NAME)
        + _pack_route(_ROUTE_1_POINTS)
        + _undecoded_trailer_gap()
        + _pack_route(garbage_points)
        + _undecoded_trailer_gap()
        + _pack_route(_ROUTE_2_POINTS)
    )
    path = tmp_path / "synthetic_with_garbage.routes"
    path.write_bytes(buf)
    stats = RouteWalkStats()

    routes = list(iter_routes(path, stats=stats))

    assert [r.points for r in routes] == [_ROUTE_1_POINTS, _ROUTE_2_POINTS]
    assert len(routes) == 2


def test_iter_routes_never_loads_whole_file_into_a_python_list_of_bytes(
    tmp_path: Path,
) -> None:
    """Not a memory-profiling test (out of scope for a unit test), but a
    structural guard: `iter_routes` must be a generator, not something that
    reads the whole file up front -- confirmed by checking it's lazy enough
    that no route has been decoded before the first `next()`."""
    import inspect

    path = _write_fixture(tmp_path)

    result = iter_routes(path)

    assert inspect.isgenerator(result)
