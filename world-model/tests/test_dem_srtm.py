"""Control-point test for `elevation.dem.SrtmTile.height_at`.

The fixture is a literal, real-data 5x5 crop (samples, not fabricated
values) read directly from the actual `N39E036.hgt` tile fetched for M4
Stage 2 (`world-model/data/raw/dem/N39E036.hgt`, SRTM3/3 arc-second,
1201x1201, gitignored raw input -- see `elevation/dem.py`'s module
docstring). Embedding the whole ~2.75MB tile in a test isn't practical, so
this hardcodes only the 5x5 neighborhood of real int16 samples around the
Gemerek control point, using `SrtmTile`'s `span_deg` field to describe that
crop's true (small) geographic extent rather than pretending it spans a
full degree -- see `SrtmTile`'s docstring. This mirrors
`test_osm_features.py`/`test_dcs_grid.py`'s pattern of hardcoding a small
real subset directly in the test module rather than reading an external
data file, so tests stay reproducible without the (gitignored, multi-MB)
raw tile present.

Control point: Gemerek district center, Sivas Province -- the same point
already used in `test_raster_registration.py::test_held_out_control_point_gemerek`
(39.18194N, 36.06806E, https://en.wikipedia.org/wiki/Gemerek). Wikipedia's
infobox gives Gemerek's elevation as 1,204m. The tolerance below accounts
for SRTM3's ~90m horizontal grid spacing plus the point being a rounded
town-center coordinate, not necessarily the exact spot the published
figure was measured at -- see `test_height_at_gemerek_control_point`.
"""

from array import array
from pathlib import Path

import pytest

from elevation.dem import SrtmTile

# Real int16 samples read from N39E036.hgt, rows 979-983 / cols 79-83
# (row0=981, col0=81 is the cell containing the Gemerek control point;
# 2-sample margin on each side for bilinear-neighbor safety). Row 0 here is
# the crop's north edge, consistent with SrtmTile's row-major-from-NW
# convention.
_GEMEREK_CROP_SAMPLES = [
    [1246, 1240, 1232, 1228, 1224],
    [1242, 1233, 1228, 1225, 1218],
    [1242, 1234, 1228, 1224, 1219],
    [1244, 1235, 1229, 1225, 1219],
    [1244, 1238, 1233, 1228, 1223],
]

# Real tile: sw_lat=39, sw_lon=36, size=1201 (span 1 degree, 1200 intervals
# -> 1/1200 degree per sample). The crop covers rows 979-983 / cols 79-83 of
# that tile -- its own SW corner and span are derived from that position.
_TILE_SIZE = 1201
_SAMPLE_SPACING_DEG = 1.0 / (_TILE_SIZE - 1)
_CROP_ROW_START = 979
_CROP_COL_START = 79
_CROP_SIZE = 5
_CROP_SW_LAT = 39.0 + 1.0 - (_CROP_ROW_START + _CROP_SIZE - 1) * _SAMPLE_SPACING_DEG
_CROP_SW_LON = 36.0 + _CROP_COL_START * _SAMPLE_SPACING_DEG
_CROP_SPAN_DEG = (_CROP_SIZE - 1) * _SAMPLE_SPACING_DEG


def _gemerek_crop_tile() -> SrtmTile:
    flat = array("h")
    for row in _GEMEREK_CROP_SAMPLES:
        flat.extend(row)
    return SrtmTile(
        sw_lat=_CROP_SW_LAT,
        sw_lon=_CROP_SW_LON,
        size=_CROP_SIZE,
        samples=flat,
        span_deg=_CROP_SPAN_DEG,
    )


def test_height_at_gemerek_control_point() -> None:
    """Gemerek's published elevation (Wikipedia infobox) is 1,204m. SRTM3's
    ~90m grid plus Wikipedia's coordinate being a rounded town-center point
    (not necessarily the exact spot the figure was measured at) is expected
    to produce a real, non-zero residual -- not the sub-meter agreement a
    transform-wiring test would need. 50m comfortably covers that expected
    noise without masking a gross bug (wrong axis order, wrong tile, etc.),
    which would be off by hundreds of meters or more."""
    tile = _gemerek_crop_tile()
    real_lat, real_lon = 39.18194, 36.06806

    height = tile.height_at(real_lat, real_lon)

    assert height == pytest.approx(1204.0, abs=50.0)


def test_height_at_matches_full_tile_reading() -> None:
    """Internal-consistency check: the crop's interpolated value at the
    control point should closely match what the full real tile itself
    produced when this fixture was extracted (1225.984m) -- confirms the
    crop was sliced/positioned correctly, independent of published-elevation
    accuracy."""
    tile = _gemerek_crop_tile()
    real_lat, real_lon = 39.18194, 36.06806

    height = tile.height_at(real_lat, real_lon)

    assert height == pytest.approx(1225.984, abs=0.01)


def test_height_at_raises_outside_grid() -> None:
    tile = _gemerek_crop_tile()
    with pytest.raises(ValueError):
        tile.height_at(0.0, 0.0)


def test_height_at_raises_on_void_sample() -> None:
    samples = array("h", [-32768] * 4)
    tile = SrtmTile(sw_lat=39.0, sw_lon=36.0, size=2, samples=samples, span_deg=0.01)
    with pytest.raises(ValueError, match="void"):
        tile.height_at(39.005, 36.005)


def test_from_file_rejects_non_srtm_filename(tmp_path: Path) -> None:
    bad_path = tmp_path / "not_a_tile.hgt"
    bad_path.write_bytes(b"\x00\x00" * 4)
    with pytest.raises(ValueError, match="doesn't match SRTM"):
        SrtmTile.from_file(bad_path)
