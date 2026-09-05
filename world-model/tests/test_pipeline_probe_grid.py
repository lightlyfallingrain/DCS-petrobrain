"""Test for `build.pipeline.probe_grid_for_region`.

Pins the exact grid derivation the M5 checklist locks: 500 m spacing over
the `latakia-20km` region's 10,000 m half-extent must produce 41x41 = 1,681
points, origin at the region's south-west corner.
"""

from build.pipeline import probe_grid_for_region
from build.region import REGIONS


def test_probe_grid_for_latakia_is_41x41_at_500m_spacing() -> None:
    region = REGIONS["latakia-20km"]

    origin_x, origin_z, spacing_m, n_rows, n_cols = probe_grid_for_region(region)

    assert spacing_m == 500.0
    assert n_rows == 41
    assert n_cols == 41
    assert origin_x == region.centre_x - region.half_extent_x_m
    assert origin_z == region.centre_z - region.half_extent_z_m


def test_probe_grid_origin_is_south_west_corner_of_the_square() -> None:
    region = REGIONS["latakia-20km"]

    origin_x, origin_z, spacing_m, n_rows, n_cols = probe_grid_for_region(region)

    max_x = origin_x + (n_rows - 1) * spacing_m
    max_z = origin_z + (n_cols - 1) * spacing_m
    assert max_x == region.centre_x + region.half_extent_x_m
    assert max_z == region.centre_z + region.half_extent_z_m


def test_probe_grid_respects_custom_spacing() -> None:
    region = REGIONS["latakia-20km"]

    _, _, spacing_m, n_rows, n_cols = probe_grid_for_region(region, spacing_m=1000.0)

    assert spacing_m == 1000.0
    assert n_rows == 21
    assert n_cols == 21
