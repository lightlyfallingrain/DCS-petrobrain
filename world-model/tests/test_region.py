"""Tests for `build.region.RegionDefinition` -- the M7 Stage 0 rectangular
half-extent generalization.

Covers: a square region behaves identically to the pre-generalization
square-only model (regression), a genuinely rectangular region's envelope
is computed independently per axis (not forced square), and the registered
`syria-full` region matches the confirmed padded bbox from
`world-model/research/2026-09-05-m7-syria-theatre-extent.md`.
"""

import pytest

from build.region import REGIONS, RegionDefinition
from coordinates import dcs_to_wgs84


def test_square_via_classmethod_sets_both_extents_equal() -> None:
    region = RegionDefinition.square(
        theatre="Syria",
        name="test-square",
        centre_x=44934.892,
        centre_z=5685.076,
        half_extent_m=10000.0,
    )
    assert region.half_extent_x_m == 10000.0
    assert region.half_extent_z_m == 10000.0


def test_square_region_envelope_matches_prior_square_only_behavior() -> None:
    """Regression: for a square region the four corners computed by the
    generalized (rectangular) `to_wgs84_envelope` must be identical to
    what the pre-M7 square-only `centre +/- half_extent_m` formula would
    have produced -- i.e. `latakia-20km` keeps working unchanged."""
    half_extent_m = 10000.0
    centre_x, centre_z = 44934.892, 5685.076
    square = RegionDefinition.square(
        theatre="Syria",
        name="test-square",
        centre_x=centre_x,
        centre_z=centre_z,
        half_extent_m=half_extent_m,
    )

    expected_corners = [
        (centre_x - half_extent_m, centre_z - half_extent_m),
        (centre_x - half_extent_m, centre_z + half_extent_m),
        (centre_x + half_extent_m, centre_z - half_extent_m),
        (centre_x + half_extent_m, centre_z + half_extent_m),
    ]
    expected_lat_lon = [dcs_to_wgs84("Syria", x, z) for x, z in expected_corners]
    expected_lats = [lat for lat, _ in expected_lat_lon]
    expected_lons = [lon for _, lon in expected_lat_lon]
    expected_envelope = (
        min(expected_lats),
        min(expected_lons),
        max(expected_lats),
        max(expected_lons),
    )

    assert square.to_wgs84_envelope() == expected_envelope


def test_latakia_20km_region_is_still_registered_as_a_square() -> None:
    region = REGIONS["latakia-20km"]
    assert region.half_extent_x_m == region.half_extent_z_m == 10000.0


def test_rectangular_region_envelope_is_wider_on_its_longer_axis() -> None:
    """A synthetic non-square region -- half-extent along x much larger
    than along z -- must produce an envelope that is correspondingly wider
    in longitude than in latitude, not a square envelope forced from a
    single extent."""
    rect = RegionDefinition(
        theatre="Syria",
        name="test-rect",
        centre_x=0.0,
        centre_z=0.0,
        half_extent_x_m=100000.0,
        half_extent_z_m=10000.0,
    )
    south, west, north, east = rect.to_wgs84_envelope()
    lon_span = east - west
    lat_span = north - south

    # DCS x maps roughly to the north-south (latitude) axis and z to the
    # east-west (longitude) axis (`+axis=neu` -- confirmed empirically:
    # dcs_to_wgs84("Syria", 100000, 0) moves lat far more than lon, and
    # dcs_to_wgs84("Syria", 0, 100000) moves lon far more than lat). A 10x
    # larger x half-extent than z half-extent should therefore produce a
    # much larger lat span than lon span (not an exact 10x ratio, since
    # tmerc distorts scale with distance from the central meridian, but
    # decisively larger).
    assert lat_span > 5 * lon_span


def test_syria_full_is_registered_with_the_confirmed_padded_bbox() -> None:
    """Pins `syria-full`'s centre/half-extents against the confirmed padded
    bbox in world-model/research/2026-09-05-m7-syria-theatre-extent.md:
    x in [-421,912.2, 345,432.4] m, z in [-320,441.1, 390,774.9] m, padded
    +30 km/side to x in [-451,912.2, 375,432.4] m, z in [-350,441.1,
    420,774.9] m."""
    region = REGIONS["syria-full"]

    assert region.theatre == "Syria"
    assert region.centre_x == pytest.approx(-38239.9, abs=0.1)
    assert region.centre_z == pytest.approx(35166.9, abs=0.1)
    assert region.half_extent_x_m == pytest.approx(413672.3, abs=0.1)
    assert region.half_extent_z_m == pytest.approx(385608.0, abs=0.1)

    min_x = region.centre_x - region.half_extent_x_m
    max_x = region.centre_x + region.half_extent_x_m
    min_z = region.centre_z - region.half_extent_z_m
    max_z = region.centre_z + region.half_extent_z_m
    assert min_x == pytest.approx(-451912.2, abs=0.1)
    assert max_x == pytest.approx(375432.4, abs=0.1)
    assert min_z == pytest.approx(-350441.1, abs=0.1)
    assert max_z == pytest.approx(420774.9, abs=0.1)

    # ~827.3 x 771.2 km, aspect ratio ~1.07 -- rectangular, not square.
    width_x_km = (max_x - min_x) / 1000.0
    width_z_km = (max_z - min_z) / 1000.0
    assert width_x_km == pytest.approx(827.3, abs=0.1)
    assert width_z_km == pytest.approx(771.2, abs=0.1)
    assert region.half_extent_x_m != region.half_extent_z_m
