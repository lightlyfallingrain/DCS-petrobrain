import pytest

from control_points import CONTROL_POINTS, ControlPoint, haversine_distance_m
from coordinates import dcs_to_wgs84, wgs84_to_dcs


def test_round_trip_is_internally_consistent() -> None:
    """dcs_to_wgs84 -> wgs84_to_dcs must return the original point to sub-mm
    precision. This validates the pyproj Transformer wiring (axis order, proj4
    string construction) independent of the projection parameters' real-world
    accuracy — a bug here would mean the transform math itself is broken."""
    x, z = -179748.32812500, 50728.26562500
    lat, lon = dcs_to_wgs84("Syria", x, z)
    round_trip_x, round_trip_z = wgs84_to_dcs("Syria", lat, lon)
    assert round_trip_x == pytest.approx(x, abs=1e-3)
    assert round_trip_z == pytest.approx(z, abs=1e-3)


def test_unknown_theatre_raises_value_error() -> None:
    with pytest.raises(ValueError):
        dcs_to_wgs84("Nevada", 0.0, 0.0)
    with pytest.raises(ValueError):
        wgs84_to_dcs("Nevada", 0.0, 0.0)


@pytest.mark.parametrize(
    "point",
    CONTROL_POINTS,
    ids=[p.name for p in CONTROL_POINTS],
)
def test_control_point_within_expected_residual(point: ControlPoint) -> None:
    """Error against published real-world ARPs is expected to be in the
    ~1.0-1.3km range (measured: Damascus 1137.5m, Latakia 1314.1m, Beirut
    962.8m) — this is DCS's own terrain-art placement error relative to
    real-world geodesy, not coordinate-transform error. See
    world-model/research/2026-09-03-m1-coordinate-transform-verification.md
    Findings 3-4. The 1500m threshold comfortably covers the measured range
    with margin without masking a genuine transform regression (which would
    produce errors an order of magnitude larger, per the prior ~327km
    wrong-axis-order failure mode noted in the M1 research)."""
    lat, lon = dcs_to_wgs84(point.theatre, point.dcs_x, point.dcs_z)
    residual_m = haversine_distance_m(lat, lon, point.real_lat, point.real_lon)
    assert residual_m <= point.expected_max_residual_m


def test_afghanistan_provisional_fit_self_consistency() -> None:
    """**Not** a live-DCS or real-world accuracy check -- this is
    self-consistency with the provisional beacon-fit only, per the M1
    circularity caveat (`beacons.lua`'s own `positionGeo` is computed by
    DCS's internal projection at terrain-build time, not an independent
    real-world source -- see `tests/control_points.py`'s module
    docstring and `world-model/research/2026-09-03-m1-coordinate-
    transform-verification.md` Finding 2). Unlike `CONTROL_POINTS` above
    (always an independently-published real-world ARP), Afghanistan has
    no second source at all yet -- see `world-model/research/2026-10-04-
    multi-theatre-afghanistan-caucasus-recon.md` Q1 -- so this test only
    confirms `dcs_to_wgs84` reproduces the beacon-fit's own input to the
    ~0.03m RMS floor that fit already measured, not that the fit is
    geodetically correct. `THEATRE_PROJECTIONS["Afghanistan"]` stays
    `confidence="provisional"` until Stage 4's live `coord.LOtoLL` probe
    (plan's Stage 4) confirms it independently.

    Point: `beacons.lua` `airfield17_0` ('Kabul', BEACON_TYPE_VOR_DME),
    `position = {81018.583527, 1780.280833, 277427.106402}`,
    `positionGeo = {latitude = 34.545599, longitude = 69.290360}`."""
    lat, lon = dcs_to_wgs84("Afghanistan", 81018.583527, 277427.106402)
    residual_m = haversine_distance_m(lat, lon, 34.545599, 69.290360)
    assert residual_m <= 0.2
