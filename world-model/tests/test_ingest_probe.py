"""Tests for `build.ingest_probe.ingest_probe`.

Uses a small synthetic 2x2 grid (not the real 41x41 Latakia grid -- this is
a wiring test for `ingest_probe`'s row/col placement and stats logic, not a
claim about real DCS terrain; contrast `test_terrain_probe.py`, which as of
the Stage 3 smoke rung uses a real hardcoded fixture) and a tiny,
uniform-value synthetic `SrtmTile` (all samples the same value, so the
expected SRTM delta for every point is exactly `height_m - tile_value`,
independent of bilinear interpolation position -- this keeps the expected
numbers hand-verifiable without needing a real `.hgt` tile). The tile's
`sw_lat`/`sw_lon`/`span_deg` cover the real lat/lon envelope of the test
grid's DCS points (computed via `coordinates.dcs_to_wgs84("Syria", ...)`, a
real transform -- only the tile's *sample values* are synthetic).
"""

from array import array
from pathlib import Path

import pytest

from build.ingest_probe import ingest_probe
from elevation.dem import SrtmTile

_ORIGIN_X = 0.0
_ORIGIN_Z = 0.0
_SPACING_M = 1000.0
_N_ROWS = 2
_N_COLS = 2

# A uniform-value tile: every sample is 100.0, so height_at(...) returns
# exactly 100.0 anywhere inside its coverage regardless of interpolation
# weights. sw_lat/sw_lon/span_deg were chosen to comfortably cover the real
# lat/lon of DCS (0,0)/(1000,0)/(0,1000)/(1000,1000) under Syria's
# projection (~35.02-35.03 N, ~35.90-35.91 E).
_UNIFORM_TILE_VALUE = 100.0


def _uniform_srtm_tile() -> SrtmTile:
    size = 3
    samples = array("h", [int(_UNIFORM_TILE_VALUE)] * (size * size))
    return SrtmTile(sw_lat=35.0, sw_lon=35.85, size=size, samples=samples, span_deg=0.2)


def _write_probe_fixture(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "terrain_probe_output.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


_FULL_FIXTURE_LINES = [
    '{"name": "r0c0", "x": 0.0, "z": 0.0, "height_m": 12.0, "surface_type": 1}',
    '{"name": "r0c1", "x": 0.0, "z": 1000.0, "height_m": 15.0, "surface_type": 3}',
    '{"name": "r1c0", "x": 1000.0, "z": 0.0, "height_m": 20.0, "surface_type": 4}',
    '{"name": "r1c1", "x": 1000.0, "z": 1000.0, "height_m": 25.0, "surface_type": 1}',
]


def test_ingest_probe_places_samples_by_row_col(tmp_path: Path) -> None:
    fixture_path = _write_probe_fixture(tmp_path, _FULL_FIXTURE_LINES)

    elevation_grid, surface_grid, stats = ingest_probe(
        fixture_path,
        "Syria",
        _ORIGIN_X,
        _ORIGIN_Z,
        _SPACING_M,
        _N_ROWS,
        _N_COLS,
        source_id=1,
    )

    assert elevation_grid.samples == [[12.0, 15.0], [20.0, 25.0]]
    assert surface_grid.samples == [[1, 3], [4, 1]]
    assert stats.points_expected == 4
    assert stats.points_received == 4


def test_ingest_probe_leaves_missing_cells_none(tmp_path: Path) -> None:
    """A partial (e.g. smoke-test-only) run must produce a real, sparse
    grid -- missing cells are `None`, not zero or an error."""
    fixture_path = _write_probe_fixture(tmp_path, _FULL_FIXTURE_LINES[:3])

    elevation_grid, surface_grid, stats = ingest_probe(
        fixture_path,
        "Syria",
        _ORIGIN_X,
        _ORIGIN_Z,
        _SPACING_M,
        _N_ROWS,
        _N_COLS,
        source_id=1,
    )

    assert elevation_grid.samples == [[12.0, 15.0], [20.0, None]]
    assert surface_grid.samples == [[1, 3], [4, None]]
    assert stats.points_expected == 4
    assert stats.points_received == 3


def test_ingest_probe_surface_type_counts(tmp_path: Path) -> None:
    fixture_path = _write_probe_fixture(tmp_path, _FULL_FIXTURE_LINES)

    _, _, stats = ingest_probe(
        fixture_path,
        "Syria",
        _ORIGIN_X,
        _ORIGIN_Z,
        _SPACING_M,
        _N_ROWS,
        _N_COLS,
        source_id=1,
    )

    assert stats.surface_type_counts == {"LAND": 2, "WATER": 1, "ROAD": 1}


def test_ingest_probe_rejects_bad_point_name(tmp_path: Path) -> None:
    fixture_path = _write_probe_fixture(
        tmp_path,
        [
            '{"name": "corner_sw", "x": 0.0, "z": 0.0, "height_m": 1.0, "surface_type": 1}'
        ],
    )

    with pytest.raises(ValueError, match="corner_sw"):
        ingest_probe(
            fixture_path,
            "Syria",
            _ORIGIN_X,
            _ORIGIN_Z,
            _SPACING_M,
            _N_ROWS,
            _N_COLS,
            source_id=1,
        )


def test_ingest_probe_rejects_out_of_range_row_col(tmp_path: Path) -> None:
    fixture_path = _write_probe_fixture(
        tmp_path,
        [
            '{"name": "r5c5", "x": 5000.0, "z": 5000.0, "height_m": 1.0, "surface_type": 1}'
        ],
    )

    with pytest.raises(ValueError, match="r5c5"):
        ingest_probe(
            fixture_path,
            "Syria",
            _ORIGIN_X,
            _ORIGIN_Z,
            _SPACING_M,
            _N_ROWS,
            _N_COLS,
            source_id=1,
        )


def test_ingest_probe_without_srtm_tile_has_null_stats(tmp_path: Path) -> None:
    fixture_path = _write_probe_fixture(tmp_path, _FULL_FIXTURE_LINES)

    elevation_grid, _, _ = ingest_probe(
        fixture_path,
        "Syria",
        _ORIGIN_X,
        _ORIGIN_Z,
        _SPACING_M,
        _N_ROWS,
        _N_COLS,
        source_id=1,
    )

    assert elevation_grid.stats["srtm"] is None


def test_ingest_probe_srtm_delta_stats_against_uniform_tile(tmp_path: Path) -> None:
    """Every real DCS point in the fixture falls inside the uniform tile's
    coverage, so the expected mean delta is exactly the mean of
    `height_m - 100.0` across all 4 points: (12+15+20+25)/4 - 100 = -82.0."""
    fixture_path = _write_probe_fixture(tmp_path, _FULL_FIXTURE_LINES)
    tile = _uniform_srtm_tile()

    elevation_grid, _, stats = ingest_probe(
        fixture_path,
        "Syria",
        _ORIGIN_X,
        _ORIGIN_Z,
        _SPACING_M,
        _N_ROWS,
        _N_COLS,
        source_id=1,
        srtm_tile=tile,
    )

    srtm_stats = elevation_grid.stats["srtm"]
    assert srtm_stats["points_compared"] == 4
    assert srtm_stats["points_skipped"] == 0
    assert srtm_stats["mean_delta_m"] == pytest.approx(-82.0)
    assert srtm_stats["min_delta_m"] == pytest.approx(12.0 - 100.0)
    assert srtm_stats["max_delta_m"] == pytest.approx(25.0 - 100.0)
    assert stats.srtm_points_compared == 4
    assert stats.srtm_points_skipped == 0


def test_ingest_probe_skips_points_outside_srtm_tile_coverage(tmp_path: Path) -> None:
    """A point far outside the tile's coverage must be counted as skipped,
    not silently dropped or crash the whole ingest."""
    fixture_path = _write_probe_fixture(
        tmp_path,
        [
            *_FULL_FIXTURE_LINES,
            '{"name": "r2c2", "x": 1000000.0, "z": 1000000.0, "height_m": 1.0, "surface_type": 1}',
        ],
    )
    # r2c2's *name* fits a 3x3 grid; its real x/z (used only for the SRTM
    # lookup, not for grid placement) is far outside the synthetic tile's
    # coverage.
    elevation_grid, _, stats = ingest_probe(
        fixture_path,
        "Syria",
        _ORIGIN_X,
        _ORIGIN_Z,
        _SPACING_M,
        n_rows=3,
        n_cols=3,
        source_id=1,
        srtm_tile=_uniform_srtm_tile(),
    )

    srtm_stats = elevation_grid.stats["srtm"]
    assert srtm_stats["points_compared"] == 4
    assert srtm_stats["points_skipped"] == 1
    assert stats.srtm_points_skipped == 1
