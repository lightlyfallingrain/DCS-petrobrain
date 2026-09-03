"""Composes `coordinates.wgs84_to_dcs` + `raster.registration.dcs_to_tile_pixel`
against the OSM fixture's Gemerek town node, extending
`tests/test_raster_registration.py::test_held_out_control_point_gemerek`'s
control-point pattern to a real OSM-sourced coordinate rather than a
by-eye/Wikipedia one.

The OSM town node (39.1831222N, 36.0711044E -- see
`test_osm_features.py`'s fixture provenance comment) is a different source
point than the Wikipedia-sourced control point used in M2's held-out test
(39.18194N, 36.06806E) -- some divergence between the two transformed
pixels is therefore expected, not a bug. This test asserts the OSM node's
pixel lands on the same tile and within a generous tolerance of M2 session
12's by-eye reading (490, 975), per the plan's "extends the existing
control-point-test pattern rather than inventing a new one."
"""

import pytest

from coordinates import wgs84_to_dcs
from raster.registration import dcs_to_tile_pixel

_THEATRE = "Syria"

# Wider than test_raster_registration.py's tolerances (100px row / 350px
# column) since this compares two different source points (OSM node vs.
# Wikipedia-published coordinate) for the same town, not a fit-vs-reading
# check of the registration itself -- see module docstring.
_ROW_TOLERANCE_PX = 150
_COLUMN_TOLERANCE_PX = 400


def test_osm_gemerek_node_transforms_to_expected_tile_and_pixel() -> None:
    # OSM node id 146775319 -- see test_osm_features.py fixture provenance.
    osm_lat, osm_lon = 39.1831222, 36.0711044
    expected_x_tile, expected_z_tile = 0, 0
    # M2 session 12's by-eye reading of the Gemerek town symbol, tile
    # 64maa00_x0_z0.tif.dds.
    expected_py, expected_px = 975, 490

    dcs_x, dcs_z = wgs84_to_dcs(_THEATRE, osm_lat, osm_lon)
    x_tile_index, z_tile_index, px, py = dcs_to_tile_pixel(_THEATRE, dcs_x, dcs_z)

    assert x_tile_index == expected_x_tile
    assert z_tile_index == expected_z_tile
    assert py == pytest.approx(expected_py, abs=_ROW_TOLERANCE_PX)
    assert px == pytest.approx(expected_px, abs=_COLUMN_TOLERANCE_PX)
