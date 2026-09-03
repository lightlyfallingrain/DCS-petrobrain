"""Control-point tests for the RasterCharts tile registration hypothesis.

Reuses the real-world control points identified during M2 recon (Sivas,
Kahramanmaras, Hama, Erzincan) -- see
`world-model/research/2026-09-03-m2-rastercharts-recon.md` sessions 7-8 for
the by-eye pixel reads and residuals these tolerances are derived from. Each
point's real-world (lat, lon) is run through the already-validated
`coordinates.wgs84_to_dcs`, so the DCS-native coordinate fed into the raster
registration is never hardcoded/circular -- mirrors `test_coordinates.py`'s
pattern.

Tolerances are asymmetric per axis, reflecting the research findings: the
x-tile-index (row/south) axis fit tightly (<0.2% residual, session 8) while
the z-tile-index (column/east) axis fit far more loosely (~9% residual,
session 7) -- see each constant's comment below for how it was derived.
"""

import pytest

from coordinates import wgs84_to_dcs
from raster import TileId, dcs_to_pixel, parse_tile_filename, pixel_to_dcs
from raster.registration import dcs_to_tile_pixel, get_registration

_THEATRE = "Syria"

# x-axis (row/py) tolerance: session 8's 3-point origin_x fit spread only
# ~463m (<0.1% of the x-range), well inside by-eye pixel-read error alone
# (+/-50px at 64m/px = +/-3200m). 100px comfortably covers both.
_ROW_TOLERANCE_PX = 100

# z-axis (column/px) tolerance: session 7's origin_z fit had a much wider
# ~18,000m spread (~9% residual) -- at 64m/px that's ~281px. 350px covers
# the documented residual plus by-eye read error without masking a gross
# hypothesis failure (which would be off by a full tile, i.e. 1024px+).
_COLUMN_TOLERANCE_PX = 350


def test_tile_filename_round_trips() -> None:
    name = "64maa00_x0_z1.tif.dds"
    tile = parse_tile_filename(name)
    assert tile == TileId(scale=64, sheet="aa", level="00", x=0, z=1)
    assert tile.filename == name


def test_parse_tile_filename_rejects_unrecognized_name() -> None:
    with pytest.raises(ValueError):
        parse_tile_filename("not_a_tile.png")


def test_unknown_theatre_raises_value_error() -> None:
    with pytest.raises(ValueError):
        get_registration("Nevada")
    with pytest.raises(ValueError):
        dcs_to_pixel("Nevada", 0.0, 0.0)
    with pytest.raises(ValueError):
        pixel_to_dcs("Nevada", TileId(scale=64, sheet="aa", level="00", x=0, z=0), 0, 0)


def test_dcs_to_pixel_round_trips_to_within_one_pixel() -> None:
    """dcs_to_pixel -> pixel_to_dcs should recover the original point to
    within one tile pixel's worth of DCS meters (64m for the Syria 64m
    sheet) -- this validates the arithmetic wiring itself, independent of
    the registration's real-world accuracy (covered by the control-point
    tests below)."""
    reg = get_registration(_THEATRE)
    x, z = 100_000.0, 200_000.0
    tile, px, py = dcs_to_pixel(_THEATRE, x, z)
    round_trip_x, round_trip_z = pixel_to_dcs(_THEATRE, tile, px, py)
    assert round_trip_x == pytest.approx(x, abs=reg.scale_m)
    assert round_trip_z == pytest.approx(z, abs=reg.scale_m)


@pytest.mark.parametrize(
    (
        "real_lat",
        "real_lon",
        "expected_x_tile",
        "expected_z_tile",
        "expected_py",
        "expected_px",
    ),
    [
        # Sivas city center, tile x0_z1, by-eye pixel (col=820, row=30).
        # https://en.wikipedia.org/wiki/Sivas (39°45'02"N 37°00'54"E).
        pytest.param(39.75056, 37.01500, 0, 1, 30, 820, id="Sivas"),
        # Kahramanmaras city center, tile x3_z1, by-eye pixel (col=583, row=707).
        # https://en.wikipedia.org/wiki/Kahramanmaras
        pytest.param(37.583, 36.933, 3, 1, 707, 583, id="Kahramanmaras"),
        # Hama city center, tile x7_z1, by-eye pixel (col=230, row=850).
        # https://en.wikipedia.org/wiki/Hama
        pytest.param(35.135, 36.750, 7, 1, 850, 230, id="Hama"),
        # Erzincan Airport (LTCD) ARP, stand-in for the co-located VOR/DME/
        # NDB, tile x0_z4, by-eye pixel (col=830, row=90).
        pytest.param(39.71000, 39.52694, 0, 4, 90, 830, id="Erzincan"),
    ],
)
def test_control_point_maps_to_expected_tile_and_pixel(
    real_lat: float,
    real_lon: float,
    expected_x_tile: int,
    expected_z_tile: int,
    expected_py: int,
    expected_px: int,
) -> None:
    dcs_x, dcs_z = wgs84_to_dcs(_THEATRE, real_lat, real_lon)
    x_tile_index, z_tile_index, px, py = dcs_to_tile_pixel(_THEATRE, dcs_x, dcs_z)

    assert x_tile_index == expected_x_tile
    assert z_tile_index == expected_z_tile
    assert py == pytest.approx(expected_py, abs=_ROW_TOLERANCE_PX)
    assert px == pytest.approx(expected_px, abs=_COLUMN_TOLERANCE_PX)
