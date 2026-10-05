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


def test_afghanistan_beacon_fit_self_consistency() -> None:
    """Kept from the provisional phase; the live check is
    `test_afghanistan_matches_live_coord_lotoll` below. **Not** a live-DCS or real-world accuracy check -- this is
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


# One beacons.lua position/positionGeo pair per provisional theatre, read
# from the installed terrain files on 2026-10-05. Same self-consistency-only
# caveat as the Afghanistan test above: beacons.lua's positionGeo is DCS's
# own projection output, so this checks the registered parameters reproduce
# it, not geodetic accuracy. Each stays `confidence="provisional"` until a
# live coord_probe.lua run -- see world-model/research/2026-10-05-kola-
# caucasus-theatre-recon.md.
PROVISIONAL_BEACON_POINTS = [
    # Kola/beacons.lua airfield18_0 (IVALO, ILS_GLIDESLOPE)
    ("Kola", "Ivalo", 81308.664063, 198170.28125, 68.613852, 27.420317),
    # Kola/beacons.lua airfield3_0 (kemi, ILS_GLIDESLOPE) -- the far south
    ("Kola", "Kemi", -242473.234375, 101148.359375, 65.789776, 24.582205),
    # Caucasus/Beacons.lua airfield29_0 (Tbilisi-Lochini, ILS_FAR_HOMER)
    ("Caucasus", "Tbilisi", -312185.40625, 892170.1875, 41.703274, 44.909623),
]


@pytest.mark.parametrize(
    ("theatre", "name", "x", "z", "lat", "lon"),
    PROVISIONAL_BEACON_POINTS,
    ids=[f"{p[0]}-{p[1]}" for p in PROVISIONAL_BEACON_POINTS],
)
def test_provisional_theatre_beacon_self_consistency(
    theatre: str, name: str, x: float, z: float, lat: float, lon: float
) -> None:
    """The fits' measured max residual is ~0.07m; 0.2m is the same bound
    the Afghanistan beacon test uses, and a wrong central meridian or
    false origin misses by kilometres."""
    got_lat, got_lon = dcs_to_wgs84(theatre, x, z)
    assert haversine_distance_m(got_lat, got_lon, lat, lon) <= 0.2


# DCS coord.LOtoLL output on the Afghanistan terrain, 2026-10-05
# (tools/dcs-mission-probe/coord_probe.lua; raw file
# data/raw/dcs/2026-10-05/coord_probe_output.json, gitignored). Spread over
# the map: origin, NW (Herat), SW (Zaranj), N (Maymana), E (Jalalabad),
# S (Dwyer), plus the Kabul/Bagram area.
AFGHANISTAN_LIVE_POINTS = [
    ("origin", 0.0, 0.0, 33.93461301, 66.24706539),
    ("Herat", 27163.97460938, -371062.81250000, 34.22003121, 62.23012967),
    ("Zaranj", -333294.46875000, -408303.40625000, 30.96580738, 61.86753983),
    ("Maymana", 217346.60937500, -140807.25000000, 35.92439132, 64.76619559),
    ("Jalalabad", 73065.89062500, 388997.62500000, 34.40606726, 70.49063829),
    ("Dwyer", -320083.34375000, -199276.92187500, 31.08563906, 64.05755618),
    ("Kabul", 83220.18750000, 268612.62500000, 34.57023878, 69.19633023),
    ("Bagram", 126849.64843750, 273171.50000000, 34.95879883, 69.27538148),
]


@pytest.mark.parametrize(
    ("name", "x", "z", "lat", "lon"),
    AFGHANISTAN_LIVE_POINTS,
    ids=[p[0] for p in AFGHANISTAN_LIVE_POINTS],
)
def test_afghanistan_matches_live_coord_lotoll(
    name: str, x: float, z: float, lat: float, lon: float
) -> None:
    """The live check behind `confidence="confirmed"`: DCS's own
    coord.LOtoLL, not beacons.lua. Measured worst residual <1 mm; the 1 cm
    bound would still catch the 5 cm offset the beacon fit had."""
    got_lat, got_lon = dcs_to_wgs84("Afghanistan", x, z)
    assert haversine_distance_m(got_lat, got_lon, lat, lon) <= 0.01
